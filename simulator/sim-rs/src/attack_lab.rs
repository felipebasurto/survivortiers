//! Bounded, deterministic attack lab. Results are fixture measurements, not global rankings.
use crate::{
    data::{Data, Move},
    engine::laboratory_scene,
    research,
};
use rayon::prelude::*;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    fs,
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicUsize, Ordering},
        mpsc, Arc,
    },
    thread,
    time::{Duration, Instant},
};

const POLICY: &str = "attack-lab-v1";
// Cache identity for this deliberately synthetic scene contract; update when any fixture constant
// or formation changes. This excludes reporting, ordering, CLI, ranking, and main.rs behavior.
const FIXTURE_POLICY: &str = "neutral-mon-v1;types=normal+fire;stats=1;hp=100000;player=stationary-immune;foe-hp=120;boss-hp=600;resistant-guard=0.35;line=32+12i;surround=35+17(i%3);approach=260+36(i%3);boss-distance=35;move-level-only;bonded-group;status-dot-on";
const SEEDS: [u32; 2] = [11014, 25025];
const SCENES: [(&str, usize); 7] = [
    ("line", 3),
    ("line", 12),
    ("surround", 3),
    ("surround", 12),
    ("approach", 3),
    ("approach", 12),
    ("boss", 1),
];

/// `run <out.json> <cache-dir> [threads] [seconds] [move-id,...]`.
pub fn command(data: &Data, args: &[String]) -> Result<(), String> {
    if args.first().map(String::as_str) != Some("run") || args.len() < 3 || args.len() > 6 {
        return Err(
            "usage: attack-lab run <out.json> <cache-dir> [threads] [seconds] [move-id,...]".into(),
        );
    }
    let args = &args[1..];
    let (out_path, cache_path) = (PathBuf::from(&args[0]), PathBuf::from(&args[1]));
    let threads = args
        .get(2)
        .map(|s| parse_usize(s, "threads"))
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
        .get(3)
        .map(|s| {
            s.parse::<f64>()
                .map_err(|_| "seconds must be numeric".to_string())
        })
        .transpose()?
        .unwrap_or(60.0);
    if !seconds.is_finite() || seconds <= 0.0 {
        return Err("seconds must be finite and greater than zero".into());
    }
    let filter: Option<Vec<String>> = args
        .get(4)
        .map(|s| {
            let ids: Vec<_> = s
                .split(',')
                .filter(|id| !id.is_empty())
                .map(str::to_owned)
                .collect();
            if ids.is_empty() {
                Err("move filter must contain at least one move id".to_string())
            } else {
                Ok(ids)
            }
        })
        .transpose()?;

    fs::create_dir_all(&cache_path).map_err(|e| format!("create cache directory: {e}"))?;
    let _cache_lock = crate::cache_lock::WriterLock::acquire(&cache_path.join(".attack-lab.lock"))?;
    if let Some(parent) = out_path.parent().filter(|p| !p.as_os_str().is_empty()) {
        fs::create_dir_all(parent).map_err(|e| format!("create output directory: {e}"))?;
    }
    let mut move_ids: Vec<String> = match filter {
        Some(ids) => ids,
        None => data
            .moves
            .iter()
            .filter(|mv| mv.is_attack())
            .map(|mv| mv.id.clone())
            .collect(),
    };
    move_ids.sort();
    move_ids.dedup();
    let supported_ids: std::collections::BTreeSet<String> = data
        .moves
        .iter()
        .filter(|mv| mv.is_attack())
        .map(|mv| mv.id.clone())
        .collect();
    let partial_scope = move_ids
        .iter()
        .cloned()
        .collect::<std::collections::BTreeSet<_>>()
        != supported_ids;
    let mut selected = Vec::with_capacity(move_ids.len());
    for id in &move_ids {
        let ix = *data
            .move_ix
            .get(id)
            .ok_or_else(|| format!("unknown move id {id}"))?;
        if !data.moves[ix].is_attack() {
            return Err(format!("{id} is not a supported attack"));
        }
        selected.push((id.clone(), ix));
    }
    let core_fingerprint = core_fingerprint();
    let done = Arc::new(AtomicUsize::new(0));
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(threads)
        .build()
        .map_err(|e| e.to_string())?;
    let (heartbeat_tx, heartbeat_rx) = mpsc::channel();
    let heartbeat = {
        let done = Arc::clone(&done);
        thread::spawn(move || {
            let start = Instant::now();
            loop {
                match heartbeat_rx.recv_timeout(Duration::from_secs(60)) {
                    Ok(()) | Err(mpsc::RecvTimeoutError::Disconnected) => break,
                    Err(mpsc::RecvTimeoutError::Timeout) => {
                        eprintln!(
                            "attack-lab heartbeat: {:.0}s elapsed, {} scenarios completed",
                            start.elapsed().as_secs_f64(),
                            done.load(Ordering::Relaxed)
                        );
                    }
                }
            }
        })
    };
    let result: Result<Vec<Value>, String> = pool.install(|| {
        selected.par_iter().map(|(id, ix)| {
            let mv = &data.moves[*ix];
            let mut scenarios = Vec::new();
            for (level, phase) in [(1usize, "initial"), (mv.max_lvl, "maximum")] {
                for &(shape, foes) in &SCENES {
                    let scenario_id = format!("{shape}-{foes}-{phase}");
                    let cache_id = scenario_cache_key(&core_fingerprint, mv, &scenario_id, seconds);
                    let cache_file = cache_path.join(format!("{cache_id}.json"));
                    let row = if let Some(v) = read_cache(&cache_file, &cache_id) {
                        v
                    } else {
                        let mut seed_rows = Vec::new();
                        for seed in SEEDS {
                            let r = laboratory_scene(data, &[*ix], &[], shape, foes, level, seconds, seed)?;
                            seed_rows.push(json!({
                                "seed": seed,
                                "damage": r.dealt,
                                "damagePerSecond": r.dealt / seconds,
                                "kills": r.kills,
                                "killsPerMinute": r.kills as f64 * 60.0 / seconds,
                            }));
                        }
                        let value = json!({"cacheId": cache_id, "results": seed_rows});
                        atomic_json(&cache_file, &value)?;
                        value
                    };
                    done.fetch_add(1, Ordering::Relaxed);
                    let results = row["results"].as_array().ok_or("cached scenario has no results")?;
                    let dps = mean(results.iter().filter_map(|r| r["damagePerSecond"].as_f64()))?;
                    let kpm = mean(results.iter().filter_map(|r| r["killsPerMinute"].as_f64()))?;
                    scenarios.push(json!({
                        "id": scenario_id,
                        "level": level,
                        "maxLevel": mv.max_lvl,
                        "phase": phase,
                        "seeds": SEEDS,
                        "damagePerSecond": dps,
                        "killsPerMinute": kpm,
                    }));
                }
            }
            let early = mean(scenarios.iter().filter(|s| s["phase"] == "initial").filter_map(|s| s["damagePerSecond"].as_f64()))?;
            let late = mean(scenarios.iter().filter(|s| s["phase"] == "maximum").filter_map(|s| s["damagePerSecond"].as_f64()))?;
            let score = mean(scenarios.iter().filter_map(|s| s["damagePerSecond"].as_f64()))?;
            Ok(json!({"id": id, "maxLevel": mv.max_lvl, "score": score, "earlyScore": early, "lateScore": late, "scenarios": scenarios}))
        }).collect()
    });
    let _ = heartbeat_tx.send(());
    let _ = heartbeat.join();
    let mut moves = result?;
    moves.sort_by(|a, b| {
        b["score"]
            .as_f64()
            .unwrap_or(0.0)
            .total_cmp(&a["score"].as_f64().unwrap_or(0.0))
            .then_with(|| a["id"].as_str().cmp(&b["id"].as_str()))
    });
    let doc = json!({
        "schema": 1,
        "kind": "attack-lab-results",
        "complete": true,
        "scope": if partial_scope { "filtered-moves" } else { "all-supported-attacks" },
        "partialScope": partial_scope,
        "policyVersion": POLICY,
        "gameCommit": data.commit,
        "engineFingerprint": research::fingerprint(),
        "cacheFingerprint": core_fingerprint,
        "scoreMeaning": "equal-weight mean scenario damage per second over this deterministic synthetic fixture; not a global ranking",
        "fixture": {"player": "neutral balanced synthetic Mon; stationary; immune to death, status and knockback", "foes": "finite HP; one resistant target in crowd scenes; one finite boss in boss scene; deterministic replenishment", "styles": ["line", "surround", "approach", "boss"], "foeCounts": [1, 3, 12], "levels": ["initial", "maximum"], "seeds": SEEDS, "defaultSeconds": 60.0},
        "secondsPerScenario": seconds,
        "moveIds": move_ids,
        "moves": moves,
    });
    atomic_json(&out_path, &doc)
}

fn parse_usize(value: &str, name: &str) -> Result<usize, String> {
    value
        .parse()
        .map_err(|_| format!("{name} must be an integer"))
}

fn mean(values: impl Iterator<Item = f64>) -> Result<f64, String> {
    let values: Vec<f64> = values.collect();
    if values.is_empty() {
        return Err("cannot average empty scenario set".into());
    }
    Ok(values.iter().sum::<f64>() / values.len() as f64)
}

fn read_cache(path: &Path, expected: &str) -> Option<Value> {
    let value: Value = serde_json::from_slice(&fs::read(path).ok()?).ok()?;
    let rows = value["results"].as_array()?;
    let valid_rows = rows.len() == SEEDS.len()
        && rows.iter().all(|row| {
            row["seed"].as_u64().is_some()
                && row["damage"].as_f64().is_some()
                && row["damagePerSecond"].as_f64().is_some()
                && row["kills"].as_u64().is_some()
                && row["killsPerMinute"].as_f64().is_some()
        });
    (value["cacheId"].as_str() == Some(expected) && valid_rows).then_some(value)
}

fn atomic_json(path: &Path, value: &Value) -> Result<(), String> {
    let tmp = path.with_extension(format!("tmp-{}", std::process::id()));
    let bytes = serde_json::to_vec(value).map_err(|e| e.to_string())?;
    fs::write(&tmp, bytes)
        .map_err(|e| format!("write cache/output temp {}: {e}", tmp.display()))?;
    fs::rename(&tmp, path).map_err(|e| format!("replace {}: {e}", path.display()))
}

fn scenario_cache_key(core: &str, mv: &Move, scenario: &str, seconds: f64) -> String {
    let mut h = Sha256::new();
    h.update(POLICY.as_bytes());
    h.update(FIXTURE_POLICY.as_bytes());
    h.update(core.as_bytes());
    h.update(scenario.as_bytes());
    h.update(seconds.to_bits().to_le_bytes());
    h.update(mv.id.as_bytes());
    h.update(mv.kind_name.as_bytes());
    h.update((mv.max_lvl as u64).to_le_bytes());
    h.update([mv.kind as u8]);
    for seed in SEEDS {
        h.update(seed.to_le_bytes());
    }
    for l in &mv.levels {
        for n in [
            l.base_dmg, l.cd, l.dmg, l.radius, l.arc, l.width, l.speed, l.count, l.spread,
            l.pierce, l.life, l.size, l.homing, l.amount, l.dur, l.stacks, l.burn, l.poison,
            l.slow, l.hex, l.drain, l.rate, l.range, l.knock, l.bounce, l.charge, l.pull, l.stun,
        ] {
            h.update(n.to_bits().to_le_bytes());
        }
        for n in [
            l.tags,
            l.ty as u16,
            l.xk as u16,
            l.buff as u16,
            l.cat as u16,
        ] {
            h.update(n.to_le_bytes());
        }
        h.update([l.status as u8]);
        h.update([l.kind as u8]);
    }
    format!("{:x}", h.finalize())
}

fn core_fingerprint() -> String {
    let mut h = Sha256::new();
    let lab_source = include_str!("engine/laboratory.rs");
    let lab_simulation = lab_source
        .split("\n#[cfg(test)]\nmod tests")
        .next()
        .unwrap_or(lab_source)
        .as_bytes();
    for bytes in [
        include_bytes!("engine.rs").as_slice(),
        include_bytes!("engine/abilities.rs"),
        include_bytes!("engine/kinds.rs"),
        lab_simulation,
        include_bytes!("data.rs"),
        include_bytes!("terrain.rs"),
        include_bytes!("radii.rs"),
        include_bytes!("rng.rs"),
        include_bytes!("math.rs"),
        include_bytes!("../Cargo.toml"),
        include_bytes!("../Cargo.lock"),
    ] {
        h.update((bytes.len() as u64).to_le_bytes());
        h.update(bytes);
    }
    format!("{:x}", h.finalize())
}
