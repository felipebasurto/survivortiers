//! JSONL-free, read-only selection policy command. Output is an exploratory diagnostic,
//! never a calibrated ranking or unique winner.
use crate::{
    research,
    selection::{self, Margin, Metrics, Observation, Policy},
};
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::{collections::BTreeSet, io::Write};

fn field<'a>(v: &'a Value, key: &str) -> Result<&'a Value, String> {
    v.get(key).ok_or_else(|| format!("missing field {key}"))
}
fn number(v: &Value, key: &str) -> Result<f64, String> {
    let x = field(v, key)?
        .as_f64()
        .ok_or_else(|| format!("{key} must be a number"))?;
    if !x.is_finite() || x < 0. {
        return Err(format!("{key} must be finite and nonnegative"));
    }
    Ok(x)
}
fn seeds(v: &Value, name: &str) -> Result<BTreeSet<u64>, String> {
    let xs = v
        .as_array()
        .ok_or_else(|| format!("{name} must be an array"))?;
    let mut out = BTreeSet::new();
    for x in xs {
        let n = x
            .as_u64()
            .filter(|&n| n <= u32::MAX as u64)
            .ok_or_else(|| format!("{name} values must be u32 integers"))?;
        if !out.insert(n) {
            return Err(format!("duplicate seed {n} in {name}"));
        }
    }
    if out.is_empty() {
        return Err(format!("{name} must not be empty"));
    }
    Ok(out)
}
fn canonical(v: &Value, out: &mut Vec<u8>) -> Result<(), String> {
    match v {
        Value::Object(obj) => {
            out.push(b'{');
            let sorted: BTreeSet<_> = obj.keys().collect();
            for (i, key) in sorted.iter().enumerate() {
                if i > 0 {
                    out.push(b',');
                }
                out.extend(serde_json::to_vec(*key).map_err(|e| e.to_string())?);
                out.push(b':');
                canonical(&obj[*key], out)?;
            }
            out.push(b'}');
        }
        Value::Array(xs) => {
            out.push(b'[');
            for (i, x) in xs.iter().enumerate() {
                if i > 0 {
                    out.push(b',');
                }
                canonical(x, out)?;
            }
            out.push(b']');
        }
        _ => out.extend(serde_json::to_vec(v).map_err(|e| e.to_string())?),
    }
    Ok(())
}
fn policy_hash(v: &Value) -> Result<String, String> {
    let mut bytes = Vec::new();
    canonical(v, &mut bytes)?;
    let mut h = Sha256::new();
    h.update(bytes);
    Ok(format!("{:x}", h.finalize()))
}

fn parse(
    value: &Value,
    expected_fingerprint: &str,
) -> Result<(String, Policy, Vec<Observation>, String), String> {
    let provenance = field(value, "provenance")?;
    let commit = field(provenance, "gameCommit")?
        .as_str()
        .ok_or("provenance.gameCommit must be a string")?;
    if commit != research::GAME_COMMIT {
        return Err("gameCommit does not match this simulator".into());
    }
    let fingerprint = field(provenance, "engineFingerprint")?
        .as_str()
        .ok_or("provenance.engineFingerprint must be a string")?;
    if fingerprint != expected_fingerprint {
        return Err("engineFingerprint does not match this simulator".into());
    }
    let incumbent = field(value, "incumbent")?
        .as_str()
        .filter(|s| !s.trim().is_empty())
        .ok_or("incumbent must be a nonempty configuration ID")?
        .to_string();
    let p = field(value, "policy")?;
    let screening_seeds = seeds(field(p, "screeningSeeds")?, "screeningSeeds")?;
    let confirmation_seeds = seeds(field(p, "confirmationSeeds")?, "confirmationSeeds")?;
    if !screening_seeds.is_disjoint(&confirmation_seeds) {
        return Err("screeningSeeds and confirmationSeeds must be disjoint".into());
    }
    let margins = field(p, "margins")?;
    let policy = Policy {
        screening_seeds,
        confirmation_seeds,
        margins: Margin {
            contact_damage: number(margins, "contactDamage")?,
            contact_seconds: number(margins, "contactSeconds")?,
            trapped_seconds: number(margins, "trappedSeconds")?,
        },
    };
    let raw = field(value, "observations")?
        .as_array()
        .ok_or("observations must be an array")?;
    if raw.is_empty() {
        return Err("observations must not be empty".into());
    }
    let mut observations = Vec::with_capacity(raw.len());
    for (i, row) in raw.iter().enumerate() {
        let id = field(row, "configurationId")?
            .as_str()
            .filter(|s| !s.trim().is_empty())
            .ok_or_else(|| format!("observations[{i}].configurationId must be a nonempty string"))?
            .to_string();
        let seed = field(row, "seed")?
            .as_u64()
            .filter(|&n| n <= u32::MAX as u64)
            .ok_or_else(|| format!("observations[{i}].seed must be a u32 integer"))?;
        let m = field(row, "metrics")?;
        observations.push(Observation {
            config_id: id,
            seed,
            metrics: Metrics {
                damage: number(m, "damage")?,
                contact_damage: number(m, "contactDamage")?,
                contact_seconds: number(m, "contactSeconds")?,
                trapped_seconds: number(m, "trappedSeconds")?,
                kills: number(m, "kills")?,
                bosses: number(m, "bosses")?,
                survival_seconds: number(m, "survivalSeconds")?,
            },
        });
    }
    Ok((incumbent, policy, observations, policy_hash(p)?))
}

/// Read one selector manifest, validate current simulator provenance, and print a JSON report.
pub fn command(path: &str) {
    let text = std::fs::read_to_string(path).unwrap_or_else(|e| panic!("read {path}: {e}"));
    let value: Value =
        serde_json::from_str(&text).unwrap_or_else(|e| panic!("parse selection JSON: {e}"));
    let (incumbent, policy, observations, hash) = parse(&value, &research::fingerprint())
        .unwrap_or_else(|e| panic!("invalid selection input: {e}"));
    let report = selection::select(&observations, &incumbent, &policy)
        .unwrap_or_else(|e| panic!("selection rejected: {e}"));
    let mut excluded = Map::new();
    for (id, reason) in report.excluded_safety {
        excluded.insert(id, Value::String(reason));
    }
    let output = json!({"screened":report.screened,"eligible":report.eligible,"pareto":report.pareto,
        "excludedSafety":excluded,"confidenceUnresolved":true,"winner":null,"rankingReady":false,"policyHash":hash});
    let stdout = std::io::stdout();
    let mut lock = stdout.lock();
    writeln!(lock, "{}", output).expect("write selection report");
}

#[cfg(test)]
mod tests {
    use super::*;
    fn input() -> Value {
        json!({"provenance":{"gameCommit":research::GAME_COMMIT,"engineFingerprint":"test-fingerprint"},"incumbent":"base",
            "policy":{"screeningSeeds":[1],"confirmationSeeds":[2],"margins":{"contactDamage":0,"contactSeconds":0,"trappedSeconds":0}},
            "observations":[{"configurationId":"base","seed":1,"metrics":{"damage":1,"contactDamage":0,"contactSeconds":0,"trappedSeconds":0,"kills":1,"bosses":0,"survivalSeconds":1}},
              {"configurationId":"base","seed":2,"metrics":{"damage":1,"contactDamage":0,"contactSeconds":0,"trappedSeconds":0,"kills":1,"bosses":0,"survivalSeconds":1}}]})
    }
    #[test]
    fn accepts_valid_payload_and_hashes_canonical_policy() {
        let v = input();
        let (_, p, obs, h) = parse(&v, "test-fingerprint").unwrap();
        assert_eq!(p.screening_seeds, [1].into());
        assert_eq!(obs.len(), 2);
        assert_eq!(h.len(), 64);
    }
    #[test]
    fn rejects_negative_metric_and_margin() {
        let mut v = input();
        v["observations"][0]["metrics"]["damage"] = json!(-1);
        assert!(parse(&v, "test-fingerprint")
            .unwrap_err()
            .contains("nonnegative"));
        let mut v = input();
        v["policy"]["margins"]["contactDamage"] = json!(-0.1);
        assert!(parse(&v, "test-fingerprint")
            .unwrap_err()
            .contains("nonnegative"));
    }
    #[test]
    fn rejects_duplicate_and_out_of_range_seeds_and_bad_provenance() {
        let mut v = input();
        v["policy"]["screeningSeeds"] = json!([1, 1]);
        assert!(parse(&v, "test-fingerprint")
            .unwrap_err()
            .contains("duplicate seed"));
        let mut v = input();
        v["policy"]["confirmationSeeds"] = json!([4294967296u64]);
        assert!(parse(&v, "test-fingerprint").unwrap_err().contains("u32"));
        let mut v = input();
        v["provenance"]["engineFingerprint"] = json!("stale");
        assert!(parse(&v, "test-fingerprint")
            .unwrap_err()
            .contains("engineFingerprint"));
    }
}
