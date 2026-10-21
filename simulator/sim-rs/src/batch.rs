//! Restartable bounded diagnostics. A plan never evaluates a game.
use crate::{data::Data, engine::Tables, research};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::Write,
    path::{Path, PathBuf},
};

fn key(spec: &Value) -> String {
    format!("{:x}", Sha256::digest(serde_json::to_vec(spec).unwrap()))
}
fn cached(dir: &Path, spec: &Value) -> Option<Value> {
    let path = dir.join(format!("{}.json", key(spec)));
    match fs::read(&path) {
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => None,
        Err(e) => panic!("read {}: {e}", path.display()),
        Ok(bytes) => {
            let row: Value = serde_json::from_slice(&bytes).expect("corrupt checkpoint JSON");
            assert_eq!(row["spec"], *spec, "checkpoint identity mismatch");
            assert_eq!(row["rankingReady"], false, "diagnostic checkpoint only");
            for field in ["time", "kills", "bosses", "dealt", "hp", "maxHp", "level"] {
                assert!(
                    row["result"][field].as_f64().is_some_and(f64::is_finite),
                    "invalid checkpoint {field}"
                );
            }
            for field in [
                "contactAttempts",
                "hits",
                "damage",
                "contactSeconds",
                "surroundedSeconds",
                "maxSurrounded",
                "invulnerableSeconds",
                "dashCasts",
                "dashHitsAfter",
            ] {
                assert!(
                    row["result"]["risk"][field]
                        .as_f64()
                        .is_some_and(|n| n.is_finite() && n >= 0.),
                    "invalid checkpoint exposure {field}"
                );
            }
            Some(row)
        }
    }
}
fn save(dir: &Path, spec: &Value, row: &Value) {
    let final_path = dir.join(format!("{}.json", key(spec)));
    let tmp = dir.join(format!("{}.pending", key(spec)));
    let mut f = fs::File::create(&tmp).expect("create checkpoint");
    serde_json::to_writer(&mut f, row).expect("serialize checkpoint");
    f.write_all(b"\n").unwrap();
    f.sync_all().expect("sync checkpoint");
    fs::rename(tmp, final_path).expect("atomic checkpoint rename");
    fs::File::open(dir)
        .unwrap()
        .sync_all()
        .expect("sync checkpoint directory");
}
struct Lock(PathBuf);
impl Drop for Lock {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.0);
    }
}

pub fn command(data: &Data, args: &[String]) {
    assert_eq!(
        args.len(),
        3,
        "usage: pokesim plan|resume manifest.jsonl checkpoint-directory"
    );
    // Validate every input before creating a directory, writing a checkpoint or running.
    let tasks = research::prepare(data, &args[1]);
    let dir = Path::new(&args[2]);
    let mut unique = std::collections::BTreeSet::new();
    for task in &tasks {
        assert!(unique.insert(key(&task.spec)), "duplicate manifest task");
    }
    if args[0] == "plan" {
        let hits = tasks
            .iter()
            .filter(|task| cached(dir, &task.spec).is_some())
            .count();
        let remaining: f64 = tasks
            .iter()
            .filter(|task| cached(dir, &task.spec).is_none())
            .map(|task| task.spec["seconds"].as_f64().unwrap())
            .sum();
        println!(
            "{}",
            json!({"tasks":tasks.len(),"cached":hits,"remaining":tasks.len()-hits,"remainingSimulatedSeconds":remaining,"wallCostEstimate":null,"engineFingerprint":research::fingerprint(),"rankingReady":false,"limit":{"runs":20,"secondsPerRun":15},"note":"Simulated seconds are not wall time. No calibrated cost estimate or ranking authorization."})
        );
        return;
    }
    fs::create_dir_all(dir).expect("checkpoint directory");
    let lock_path = dir.join("writer.lock");
    let mut lock = fs::OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&lock_path)
        .expect(
            "checkpoint writer already locked; verify no live writer before removing stale lock",
        );
    writeln!(lock, "{}", std::process::id()).unwrap();
    lock.sync_all().unwrap();
    let _guard = Lock(lock_path);
    // Check every checkpoint before running anything, including files later in the manifest.
    let previous: Vec<_> = tasks.iter().map(|task| cached(dir, &task.spec)).collect();
    let tables = Tables::new();
    for (task, old) in tasks.iter().zip(previous) {
        let reused = old.is_some();
        let row = old.unwrap_or_else(|| {
            let row = research::execute(data, &tables, task);
            save(dir, &task.spec, &row);
            row
        });
        println!("{}", json!({"cached":reused,"record":row}));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn identity_covers_seed_profile_and_engine() {
        let a = json!({"seed":1,"nature":"hardy","engineFingerprint":"a"});
        for b in [
            json!({"seed":2,"nature":"hardy","engineFingerprint":"a"}),
            json!({"seed":1,"nature":"brave","engineFingerprint":"a"}),
            json!({"seed":1,"nature":"hardy","engineFingerprint":"b"}),
        ] {
            assert_ne!(key(&a), key(&b));
        }
        assert_eq!(
            key(&a),
            key(&serde_json::from_str::<Value>(
                r#"{"nature":"hardy","engineFingerprint":"a","seed":1}"#
            )
            .unwrap())
        );
    }
    #[test]
    fn atomic_record_roundtrip_does_not_recompute() {
        let dir = std::env::temp_dir().join(format!("pokesim-checkpoint-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let spec = json!({"seed":9});
        let row = json!({"spec":spec,"rankingReady":false,"result":{"time":15,"kills":2,"bosses":0,"dealt":42,"hp":99,"maxHp":100,"level":1,"risk":{"contactAttempts":0,"hits":0,"damage":0,"contactSeconds":0,"surroundedSeconds":0,"maxSurrounded":0,"invulnerableSeconds":0,"dashCasts":0,"dashHitsAfter":0}}});
        save(&dir, &spec, &row);
        assert_eq!(cached(&dir, &spec), Some(row));
        assert!(cached(&dir, &json!({"seed":10})).is_none());
        assert!(!dir.join(format!("{}.pending", key(&spec))).exists());
        fs::remove_dir_all(dir).unwrap();
    }
}
