//! Bounded follow-up measurements for attack-lab candidates.
use crate::{
    cache_lock::WriterLock,
    data::{Data, Move},
    engine::laboratory_scene,
    production::{atomic_json, hash_value},
    research,
};
use rayon::prelude::*;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeSet,
    fs,
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicUsize, Ordering},
        mpsc, Arc,
    },
    thread,
    time::{Duration, Instant},
};

const POLICY: &str = "synergy-lab-v1";
const SEEDS: [u32; 2] = [11014, 25025];
const SCENES: [(&str, usize); 7] = [
    ("boss", 1),
    ("line", 3),
    ("line", 12),
    ("surround", 3),
    ("surround", 12),
    ("approach", 3),
    ("approach", 12),
];
const MAX_GROUPS: usize = 24;

pub fn command(data: &Data, args: &[String]) -> Result<(), String> {
    if args.first().map(String::as_str) != Some("run") || !(4..=6).contains(&args.len()) {
        return Err(
            "usage: synergy-lab run <lab.json> <out.json> <cache-dir> [threads] [seconds]".into(),
        );
    }
    let input_path = PathBuf::from(&args[1]);
    let out_path = PathBuf::from(&args[2]);
    let cache_path = PathBuf::from(&args[3]);
    let threads = args
        .get(4)
        .map(|s| {
            s.parse::<usize>()
                .map_err(|_| "threads must be an integer".to_string())
        })
        .transpose()?
        .unwrap_or_else(|| {
            thread::available_parallelism()
                .map(|n| n.get())
                .unwrap_or(1)
        });
    if threads == 0 {
        return Err("threads must be greater than zero".into());
    }
    let seconds = args
        .get(5)
        .map(|s| {
            s.parse::<f64>()
                .map_err(|_| "seconds must be numeric".to_string())
        })
        .transpose()?
        .unwrap_or(60.0);
    if !seconds.is_finite() || seconds <= 0.0 {
        return Err("seconds must be finite and greater than zero".into());
    }
    let input: Value = serde_json::from_slice(
        &fs::read(&input_path).map_err(|e| format!("read {}: {e}", input_path.display()))?,
    )
    .map_err(|e| format!("parse lab JSON: {e}"))?;
    validate_lab(data, &input)?;
    let artifact_seconds = input["secondsPerScenario"]
        .as_f64()
        .ok_or("attack-lab secondsPerScenario is missing")?;
    if (artifact_seconds - seconds).abs() > f64::EPSILON * artifact_seconds.abs().max(1.0) {
        return Err(format!("synergy seconds ({seconds}) must match attack-lab secondsPerScenario ({artifact_seconds})"));
    }
    let proposals = propose(data, &input)?;
    fs::create_dir_all(&cache_path).map_err(|e| format!("create cache directory: {e}"))?;
    let _lock = WriterLock::acquire(&cache_path.join(".synergy-lab.lock"))?;
    if let Some(parent) = out_path.parent().filter(|p| !p.as_os_str().is_empty()) {
        fs::create_dir_all(parent).map_err(|e| format!("create output directory: {e}"))?;
    }
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(threads)
        .build()
        .map_err(|e| e.to_string())?;
    let simulation_fingerprint = core_fingerprint();
    let total = proposals.len();
    let mut rows = Vec::with_capacity(total);
    let done = Arc::new(AtomicUsize::new(0));
    let (tx, rx) = mpsc::channel();
    let heartbeat = {
        let done = Arc::clone(&done);
        thread::spawn(move || {
            let start = Instant::now();
            loop {
                match rx.recv_timeout(Duration::from_secs(60)) {
                    Ok(()) | Err(mpsc::RecvTimeoutError::Disconnected) => break,
                    Err(mpsc::RecvTimeoutError::Timeout) => eprintln!(
                        "synergy-lab heartbeat: {:.0}s elapsed, {}/{} groups completed",
                        start.elapsed().as_secs_f64(),
                        done.load(Ordering::Relaxed),
                        total
                    ),
                }
            }
        })
    };
    let solo_scores = input["moves"]
        .as_array()
        .unwrap()
        .iter()
        .map(|r| {
            (
                r["id"].as_str().unwrap().to_string(),
                r["score"].as_f64().unwrap(),
            )
        })
        .collect::<std::collections::HashMap<_, _>>();
    for (n, proposal) in proposals.iter().enumerate() {
        eprintln!(
            "synergy-lab group {}/{}: attacks={:?} buffs={:?}",
            n + 1,
            total,
            proposal
                .attacks
                .iter()
                .map(|&i| &data.moves[i].id)
                .collect::<Vec<_>>(),
            proposal
                .buffs
                .iter()
                .map(|&i| &data.moves[i].id)
                .collect::<Vec<_>>()
        );
        let row = pool.install(|| {
            measure(
                data,
                proposal,
                seconds,
                &cache_path,
                &solo_scores,
                &simulation_fingerprint,
            )
        })?;
        rows.push(row);
        done.fetch_add(1, Ordering::Relaxed);
    }
    let _ = tx.send(());
    let _ = heartbeat.join();
    let mut output = input;
    let obj = output
        .as_object_mut()
        .ok_or("lab artifact must be an object")?;
    obj.insert("synergyPolicyVersion".into(), json!(POLICY));
    obj.insert("synergySecondsPerScenario".into(), json!(seconds));
    obj.insert("synergyScoreMeaning".into(), json!("descriptive equal-weight mean DPS across the fixed synergy scenes; attack pairs are compared with the sum of their attack-lab solo scores, and attack+buff groups with the best other attack measured in the same slot (baselineKind). relativeGain is not a causal independence estimate"));
    obj.insert("measuredSynergies".into(), Value::Array(rows));
    atomic_json(&out_path, &output)
}

fn validate_lab(data: &Data, v: &Value) -> Result<(), String> {
    if v["kind"] != "attack-lab-results"
        || v["complete"] != true
        || v["partialScope"] == true
        || v["scope"] != "all-supported-attacks"
    {
        return Err("input must be a complete, unfiltered attack-lab-results artifact".into());
    }
    if v["engineFingerprint"].as_str() != Some(&research::fingerprint()) {
        return Err("attack-lab engineFingerprint does not match current engine".into());
    }
    if v["gameCommit"].as_str() != Some(data.commit.as_str()) {
        return Err("attack-lab gameCommit does not match loaded game data".into());
    }
    let moves = v["moves"]
        .as_array()
        .ok_or("attack-lab moves must be an array")?;
    if moves.is_empty() {
        return Err("attack-lab moves is empty".into());
    }
    let mut ids = BTreeSet::new();
    for row in moves {
        let id = row["id"].as_str().ok_or("attack-lab move missing id")?;
        let score = row["score"]
            .as_f64()
            .ok_or_else(|| format!("attack-lab move {id} missing score"))?;
        if !score.is_finite() {
            return Err(format!("attack-lab move {id} score is non-finite"));
        }
        let ix = *data
            .move_ix
            .get(id)
            .ok_or_else(|| format!("unknown attack-lab move id {id}"))?;
        if !data.moves[ix].is_attack() {
            return Err(format!("attack-lab id {id} is not a supported attack"));
        }
        if !ids.insert(id.to_owned()) {
            return Err(format!("duplicate attack-lab move id {id}"));
        }
    }
    let supported = data
        .moves
        .iter()
        .filter(|m| m.is_attack())
        .map(|m| m.id.clone())
        .collect::<BTreeSet<_>>();
    if ids != supported {
        return Err("attack-lab move list does not cover all supported attacks".into());
    }
    Ok(())
}

#[derive(Clone)]
struct Proposal {
    attacks: Vec<usize>,
    buffs: Vec<usize>,
    /// Attacks that would fill the same slots without the buff: the baseline an offensive
    /// buff has to beat, since it takes a place an attack could have had.
    slot_alternative: Option<Vec<usize>>,
}
fn propose(data: &Data, v: &Value) -> Result<Vec<Proposal>, String> {
    let rows = v["moves"].as_array().unwrap();
    let mut ranked = rows
        .iter()
        .map(|r| {
            (
                data.move_ix[r["id"].as_str().unwrap()],
                r["score"].as_f64().unwrap(),
            )
        })
        .collect::<Vec<_>>();
    ranked.sort_by(|a, b| {
        b.1.total_cmp(&a.1)
            .then_with(|| data.moves[a.0].id.cmp(&data.moves[b.0].id))
    });
    let mut out = Vec::new();
    let mut seen = BTreeSet::new();
    let status = ranked
        .iter()
        .filter(|(ix, _)| {
            data.moves[*ix]
                .levels
                .iter()
                .any(|l| l.slow.is_finite() || l.burn.is_finite() || l.poison.is_finite())
        })
        .take(3)
        .map(|x| x.0)
        .collect::<Vec<_>>();
    let hex = ranked
        .iter()
        .filter(|(ix, _)| data.moves[*ix].levels.iter().any(|l| l.hex > 0.0))
        .take(3)
        .map(|x| x.0)
        .collect::<Vec<_>>();
    for a in hex {
        for &b in &status {
            if a != b {
                add(&mut out, &mut seen, vec![a, b], vec![], None);
            }
        }
    }
    let buffs = [
        (data.swords_dance, 1),
        (data.dragon_dance, 1),
        (data.nasty_plot, 2),
    ];
    for (b, category) in buffs {
        if data.moves[b].kind_name != "buff" || data.moves[b].levels[0].buff == 0 {
            continue;
        }
        let attacks = ranked
            .iter()
            .filter(|(ix, _)| {
                data.moves[*ix].is_attack() && data.moves[*ix].levels[0].cat == category
            })
            .take(4)
            .map(|x| x.0)
            .collect::<Vec<_>>();
        for a in attacks {
            let filler = ranked.iter().map(|x| x.0).find(|&x| x != a);
            add(
                &mut out,
                &mut seen,
                vec![a],
                vec![b],
                filler.map(|x| vec![a, x]),
            );
        }
    }
    out.truncate(MAX_GROUPS);
    Ok(out)
}
fn add(
    out: &mut Vec<Proposal>,
    seen: &mut BTreeSet<(Vec<usize>, Vec<usize>)>,
    a: Vec<usize>,
    b: Vec<usize>,
    slot_alternative: Option<Vec<usize>>,
) {
    let mut canonical = a.clone();
    canonical.sort_unstable();
    let key = (canonical, b.clone());
    if out.len() < MAX_GROUPS && seen.insert(key) {
        out.push(Proposal {
            attacks: a,
            buffs: b,
            slot_alternative,
        });
    }
}

fn measure(
    data: &Data,
    p: &Proposal,
    seconds: f64,
    cache: &Path,
    solo_scores: &std::collections::HashMap<String, f64>,
    simulation_fingerprint: &str,
) -> Result<Value, String> {
    let attacks = p
        .attacks
        .iter()
        .map(|&i| data.moves[i].id.clone())
        .collect::<Vec<_>>();
    let buffs = p
        .buffs
        .iter()
        .map(|&i| data.moves[i].id.clone())
        .collect::<Vec<_>>();
    let solo_sum = p
        .attacks
        .iter()
        .map(|&i| {
            solo_scores
                .get(&data.moves[i].id)
                .copied()
                .ok_or_else(|| format!("solo baseline missing {}", data.moves[i].id))
        })
        .collect::<Result<Vec<_>, _>>()?
        .iter()
        .sum::<f64>();
    let (score, scenarios) = measure_group(
        data,
        &p.attacks,
        &p.buffs,
        seconds,
        cache,
        simulation_fingerprint,
    )?;
    // An offensive buff is compared with the best other attack in its slot, measured in the
    // same scenes; pairs of attacks are compared with their solo scores added.
    let (baseline, baseline_kind, alternative) = match &p.slot_alternative {
        Some(attacks) => {
            let (alt, _) =
                measure_group(data, attacks, &[], seconds, cache, simulation_fingerprint)?;
            (
                alt,
                "slot-alternative-measured",
                json!(attacks.iter().map(|&i| &data.moves[i].id).collect::<Vec<_>>()),
            )
        }
        None => (solo_sum, "solo-score-sum", Value::Null),
    };
    Ok(
        json!({"attacks":attacks,"buffs":buffs,"score":score,"baselineScore":baseline,"baselineKind":baseline_kind,"slotAlternative":alternative,"soloScoreSum":solo_sum,"relativeGain":if baseline>0.0{score/baseline}else{0.0},"scenarios":scenarios}),
    )
}
fn measure_group(
    data: &Data,
    attacks: &[usize],
    buffs: &[usize],
    seconds: f64,
    cache: &Path,
    simulation_fingerprint: &str,
) -> Result<(f64, Vec<Value>), String> {
    let level = attacks
        .iter()
        .map(|&i| data.moves[i].max_lvl)
        .max()
        .unwrap_or(1);
    let tasks = SCENES
        .iter()
        .flat_map(|&(scene, foes)| {
            [
                (scene, foes, 1usize, "initial"),
                (scene, foes, level, "maximum"),
            ]
        })
        .collect::<Vec<_>>();
    let scenarios: Vec<Value> = tasks.par_iter().map(|&(scene,foes,phase_level,phase)| -> Result<Value,String> {
        let mut ds=Vec::new(); let mut ks=Vec::new();
        for seed in SEEDS {
            let r=run_cached(data,attacks,buffs,scene,foes,phase_level,seconds,seed,cache,simulation_fingerprint)?;
            ds.push(r.0); ks.push(r.1);
        }
        Ok(json!({"id":format!("{scene}-{foes}-{phase}"),"phase":phase,"level":phase_level,"seeds":SEEDS,"damagePerSecond":mean(&ds),"killsPerMinute":mean(&ks)}))
    }).collect::<Result<Vec<_>,_>>()?;
    let score = mean(
        &scenarios
            .iter()
            .map(|x| x["damagePerSecond"].as_f64().unwrap_or(0.))
            .collect::<Vec<_>>(),
    );
    Ok((score, scenarios))
}
fn run_cached(
    data: &Data,
    a: &[usize],
    b: &[usize],
    scene: &str,
    foes: usize,
    level: usize,
    seconds: f64,
    seed: u32,
    cache: &Path,
    simulation_fingerprint: &str,
) -> Result<(f64, f64), String> {
    let mut raw = serde_json::Map::new();
    for &i in a.iter().chain(b) {
        let m = &data.moves[i];
        raw.insert(m.id.clone(), move_numeric(m));
    }
    let key = hash_value(&json!([
        POLICY,
        simulation_fingerprint,
        raw,
        a.iter().map(|&i| &data.moves[i].id).collect::<Vec<_>>(),
        b.iter().map(|&i| &data.moves[i].id).collect::<Vec<_>>(),
        scene,
        foes,
        level,
        seconds.to_bits(),
        seed
    ]));
    let path = cache.join(format!("{key}.json"));
    if let Ok(bytes) = fs::read(&path) {
        if let Ok(v) = serde_json::from_slice::<Value>(&bytes) {
            if v["cacheKey"] == key {
                return Ok((
                    v["dps"].as_f64().unwrap_or(0.),
                    v["kpm"].as_f64().unwrap_or(0.),
                ));
            }
        }
    }
    let r = laboratory_scene(data, a, b, scene, foes, level, seconds, seed)?;
    let val = json!({"cacheKey":key,"dps":r.dealt/seconds,"kpm":r.kills as f64*60.0/seconds});
    atomic_json(&path, &val)?;
    Ok((val["dps"].as_f64().unwrap(), val["kpm"].as_f64().unwrap()))
}
fn core_fingerprint() -> String {
    let mut h = Sha256::new();
    let lab = include_str!("engine/laboratory.rs");
    let lab = lab.split("\n#[cfg(test)]\nmod tests").next().unwrap_or(lab);
    for b in [
        include_bytes!("engine.rs").as_slice(),
        include_bytes!("engine/abilities.rs"),
        include_bytes!("engine/kinds.rs"),
        lab.as_bytes(),
        include_bytes!("data.rs"),
        include_bytes!("terrain.rs"),
        include_bytes!("radii.rs"),
        include_bytes!("rng.rs"),
        include_bytes!("math.rs"),
        include_bytes!("../Cargo.toml"),
        include_bytes!("../Cargo.lock"),
    ] {
        h.update((b.len() as u64).to_le_bytes());
        h.update(b)
    }
    format!("{:x}", h.finalize())
}
fn move_numeric(m: &Move) -> Value {
    json!({"kind":m.kind_name,"maxLevel":m.max_lvl,"levels":m.levels.iter().map(|l|json!([l.tags,l.base_dmg,l.kind as u8,l.ty,l.cd,l.dmg,l.radius,l.arc,l.width,l.speed,l.count,l.spread,l.pierce,l.life,l.size,l.homing,l.amount,l.dur,l.stacks,l.status,l.burn,l.poison,l.slow,l.xk,l.hex,l.drain,l.rate,l.range,l.knock,l.bounce,l.charge,l.pull,l.stun,l.buff,l.cat])).collect::<Vec<_>>()})
}
fn mean(xs: &[f64]) -> f64 {
    if xs.is_empty() {
        0.0
    } else {
        xs.iter().sum::<f64>() / xs.len() as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn proposals_are_capped_and_use_supported_hex_status_and_category_buffs() {
        let game_path = Path::new(env!("CARGO_MANIFEST_DIR")).join("../data/game.json");
        let data = Data::load(game_path.to_str().expect("game data path is UTF-8"));
        let moves = data
            .moves
            .iter()
            .filter(|m| m.is_attack())
            .map(|m| json!({"id":m.id,"score":1.0}))
            .collect::<Vec<_>>();
        let lab = json!({"kind":"attack-lab-results","complete":true,"partialScope":false,"scope":"all-supported-attacks","engineFingerprint":research::fingerprint(),"gameCommit":data.commit,"moves":moves});
        validate_lab(&data, &lab).unwrap();
        let groups = propose(&data, &lab).unwrap();
        assert!(groups.len() <= MAX_GROUPS);
        assert!(!groups.is_empty());
        let hex = *data.move_ix.get("hex").expect("pinned Hex move");
        assert!(groups
            .iter()
            .any(|p| p.attacks.contains(&hex) && p.attacks.len() == 2));
        assert!(
            groups
                .iter()
                .any(|p| p.buffs == [data.swords_dance]
                    && data.moves[p.attacks[0]].levels[0].cat == 1)
        );
        assert!(groups
            .iter()
            .any(|p| p.buffs == [data.nasty_plot] && data.moves[p.attacks[0]].levels[0].cat == 2));
        assert!(
            groups
                .iter()
                .filter(|p| !p.buffs.is_empty())
                .all(|p| p.slot_alternative.as_ref().is_some_and(|alt| alt.len() == 2)),
            "an offensive buff is measured against the attack that would take its slot"
        );
        let selected = groups
            .iter()
            .find(|p| p.attacks.contains(&hex) && p.attacks.len() == 2)
            .unwrap();
        let result = laboratory_scene(
            &data,
            &selected.attacks,
            &selected.buffs,
            "line",
            3,
            1,
            0.05,
            SEEDS[0],
        )
        .unwrap();
        assert!(result.dealt.is_finite() && result.kills <= 3);
    }
}
