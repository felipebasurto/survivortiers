//! Current build configuration, exhaustive move candidates and bounded diagnostics.
//! No historical score is used to filter candidates or to declare a new ranking.
use crate::{data::*, engine::*, math::Libm};
use serde_json::{json, Value};
use std::{
    collections::BTreeSet,
    io::{self, Write},
    time::Instant,
};
pub const GAME_COMMIT: &str = "ce5785313b0205af8b9477423f64b0a7b7039dcd";
pub const ENGINE_VERSION: u32 = 4;
pub fn fingerprint() -> String {
    use sha2::{Digest, Sha256};
    let mut h = Sha256::new();
    for source in [
        include_bytes!("engine.rs").as_slice(),
        include_bytes!("engine/abilities.rs"),
        include_bytes!("engine/kinds.rs"),
        include_bytes!("data.rs"),
        include_bytes!("terrain.rs"),
        include_bytes!("radii.rs"),
        include_bytes!("rng.rs"),
        include_bytes!("math.rs"),
        include_bytes!("main.rs"),
        include_bytes!("research.rs"),
        include_bytes!("selection.rs"),
        include_bytes!("selection_io.rs"),
        include_bytes!("batch.rs"),
        include_bytes!("../Cargo.toml"),
        include_bytes!("../Cargo.lock"),
        include_bytes!("../../data/game.json"),
    ] {
        h.update((source.len() as u64).to_le_bytes());
        h.update(source);
    }
    format!("{:x}", h.finalize())
}
fn base(data: &Data, dex: u32) -> &Mon {
    data.dex.iter().find(|p| p.dex == dex).expect("unknown dex")
}
fn index(data: &Data, id: &str) -> usize {
    *data
        .move_ix
        .get(id)
        .unwrap_or_else(|| panic!("unknown move {id}"))
}
/// Emit only combinations the engine can represent, with every possible lead.
/// The role is descriptive. Normal moves and MTs compete without hard-coded type quotas.
pub fn candidates(data: &Data, dex: u32, list: bool, expand_profiles: bool) {
    let base = base(data, dex);
    let taught: Vec<String> = base.tms.iter().map(|&i| data.moves[i].id.clone()).collect();
    let mon = data
        .configure(base, "hardy", None, &taught)
        .expect("all legal TMs");
    let leads = mon.start_choices(&data.moves);
    let attacks: Vec<usize> = mon
        .pool
        .iter()
        .copied()
        .chain(std::iter::once(mon.start))
        .filter(|&i| data.moves[i].is_attack())
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let profiles = base
        .abilities
        .iter()
        .flatten()
        .collect::<BTreeSet<_>>()
        .len()
        * data.natures.as_array().unwrap().len();
    let equivalences: BTreeSet<_> = data
        .natures
        .as_array()
        .unwrap()
        .iter()
        .map(|n| {
            crate::selection::nature_equivalence(data, base, n["id"].as_str().unwrap()).unwrap()
        })
        .collect();
    let distinct_profiles = equivalences.len()
        * base
            .abilities
            .iter()
            .flatten()
            .collect::<BTreeSet<_>>()
            .len()
            .max(1);
    let mut count = 0usize;
    let mut natural_count = 0usize;
    let engine_fingerprint = fingerprint();
    let mut out = io::BufWriter::new(io::stdout().lock());
    let mut emit = |group: Vec<usize>| {
        count += 1;
        if group
            .iter()
            .all(|i| base.pool.contains(i) || *i == base.start)
        {
            natural_count += 1;
        }
        if !list {
            return;
        }
        let group_ids: Vec<_> = group.iter().map(|&i| &data.moves[i].id).collect();
        let tms: Vec<_> = group
            .iter()
            .filter(|&&i| !base.pool.contains(&i) && i != base.start)
            .map(|&i| &data.moves[i].id)
            .collect();
        let own = group
            .iter()
            .filter(|&&i| {
                data.moves[i].is_attack() && base.types.contains(&data.moves[i].levels[0].ty)
            })
            .count();
        let melee = group.iter().any(|&i| data.moves[i].kind == Kind::Melee);
        let mut seen = BTreeSet::new();
        let mut resist = 0;
        for tier in &data.tiers {
            for e in &tier.cands {
                if seen.insert(e.dex)
                    && group
                        .iter()
                        .filter(|&&i| data.moves[i].is_attack())
                        .all(|&i| {
                            data.tmult[data.moves[i].levels[0].ty as usize][e.combo as usize] < 1.
                        })
                {
                    resist += 1;
                }
            }
        }
        let defense = group.iter().any(|&i| i == data.harden || i == data.agility);
        if expand_profiles {
            use crate::selection::{configurations, BuildStyle, CombatRole};
            let ids: Vec<String> = group_ids.iter().map(|id| (*id).clone()).collect();
            let configs = configurations(
                data,
                dex,
                &[ids],
                if melee {
                    BuildStyle::Melee
                } else {
                    BuildStyle::Ranged
                },
                CombatRole::Base,
            )
            .expect("legal generated group");
            for c in configs {
                writeln!(out,"{}",json!({"configurationId":c.id,"dex":c.dex,"group":c.moves,"nature":c.nature,"natureEquivalence":c.nature_equivalence,"ability":c.ability,"tms":c.tms,"second":c.second,"build":if melee {"melee"}else{"ranged"},"role":"base","gameCommit":GAME_COMMIT,"engine":ENGINE_VERSION,"engineFingerprint":engine_fingerprint})).unwrap();
            }
            return;
        }
        writeln!(out,"{}",json!({"dex":dex,"group":group_ids,"second":if group[0]!=base.start&&group.contains(&base.start)&&!base.pool.contains(&base.start){Some(&data.moves[base.start].id)}else{None},"tms":tms,"build":if melee{"melee"}else{"ranged"},"aggro":!defense,"ownAttacks":own,"resistedSpecies":resist})).expect("write candidate");
    };
    let fills = |xs: &[usize], n: usize| -> Vec<Vec<usize>> {
        let mut buffs = Vec::new();
        for (i, cat) in [
            (data.swords_dance, 1),
            (data.nasty_plot, 2),
            (data.dragon_dance, 1),
        ] {
            if mon.pool.contains(&i) && xs.iter().any(|&x| data.moves[x].levels[0].cat == cat) {
                if n == 2 {
                    for def in [data.harden, data.agility] {
                        let mut g = xs.to_vec();
                        g.extend([i, def]);
                        buffs.push(g);
                    }
                } else {
                    let mut g = xs.to_vec();
                    g.push(i);
                    buffs.push(g);
                }
            }
        }
        if n == 3 {
            for def in [data.harden, data.agility] {
                let mut g = xs.to_vec();
                g.push(def);
                buffs.push(g);
            }
        }
        buffs
    };
    for &lead in &leads {
        if !data.moves[lead].is_attack() {
            continue;
        }
        for &b in &attacks {
            if b == lead {
                continue;
            }
            for g in fills(&[lead, b], 2) {
                emit(g);
            }
        }
        for (i, &b) in attacks.iter().enumerate() {
            if b == lead {
                continue;
            }
            for (j, &c) in attacks.iter().enumerate().skip(i + 1) {
                if c == lead {
                    continue;
                }
                for &d in attacks.iter().skip(j + 1) {
                    if d != lead {
                        emit(vec![lead, b, c, d]);
                    }
                }
            }
        }
        for (j, &b) in attacks.iter().enumerate() {
            if b == lead {
                continue;
            }
            for &c in &attacks[j + 1..] {
                if c == lead {
                    continue;
                }
                for g in fills(&[lead, b, c], 3) {
                    emit(g);
                }
            }
        }
    }
    out.flush().unwrap();
    if !list {
        println!(
            "{}",
            json!({"dex":dex,"moveGroups":count,"natureAbilityProfiles":profiles,"distinctNatureAbilityProfiles":distinct_profiles,"jointConfigurations":count as u64*distinct_profiles as u64,"noTmGroups":natural_count,"noTmConfigurations":natural_count as u64*distinct_profiles as u64,"unsupportedMoves":["aqua-ring"],"gameCommit":data.commit,"engine":ENGINE_VERSION,"engineFingerprint":fingerprint(),"rankingReady":false})
        );
    }
}
pub(crate) fn run_value(r: &RunResult) -> Value {
    json!({"time":r.time,"kills":r.kills,"bosses":r.bosses,"dealt":r.dealt,"hp":r.hp,"maxHp":r.max_hp,"level":r.level,
 "risk":{"contactAttempts":r.risk.contact_attempts,"hits":r.risk.hits,"damage":r.risk.damage,"contactSeconds":r.risk.contact_seconds,"surroundedSeconds":r.risk.surrounded_seconds,"maxSurrounded":r.risk.max_surrounded,"invulnerableSeconds":r.risk.invulnerable_seconds,"dashCasts":r.risk.dash_casts,"dashHitsAfter":r.risk.dash_hits_after}})
}
/// Max 20 runs, max 15 simulated seconds each. Validate all rows before starting any run.
pub(crate) struct Task {
    pub spec: Value,
    mon: Mon,
    start: usize,
    opts: Opts,
}

pub(crate) fn prepare(data: &Data, path: &str) -> Vec<Task> {
    let text = std::fs::read_to_string(path).expect("read diagnostic JSONL");
    let rows: Vec<Value> = text
        .lines()
        .filter(|s| !s.trim().is_empty())
        .map(|s| serde_json::from_str(s).expect("JSONL row"))
        .collect();
    assert!(
        !rows.is_empty() && rows.len() <= 20,
        "diagnostics require 1..20 runs"
    );
    let mut tasks = Vec::new();
    for row in rows {
        assert_eq!(
            row["gameCommit"], GAME_COMMIT,
            "manifest must identify current game"
        );
        assert_eq!(row["engine"], ENGINE_VERSION);
        assert_eq!(
            row["engineFingerprint"],
            fingerprint(),
            "stale engine/data manifest"
        );
        let dex = row["dex"].as_u64().expect("dex") as u32;
        let nature = row["nature"].as_str().expect("explicit nature");
        let ab = row["ability"].as_str().expect("explicit ability");
        let taught: Vec<String> = row["tms"]
            .as_array()
            .expect("tms")
            .iter()
            .map(|x| x.as_str().expect("TM id").into())
            .collect();
        let mon = data
            .configure(base(data, dex), nature, Some(ab), &taught)
            .expect("legal species configuration");
        let group: Vec<usize> = row["group"]
            .as_array()
            .expect("group")
            .iter()
            .map(|s| index(data, s.as_str().expect("move")))
            .collect();
        assert!(
            !group.is_empty()
                && group.len() <= 4
                && group.iter().copied().collect::<BTreeSet<_>>().len() == group.len(),
            "distinct moves, 1..4 slots"
        );
        assert!(
            mon.start_choices(&data.moves).contains(&group[0]),
            "attack must be a legal starter"
        );
        assert!(
            group
                .iter()
                .all(|i| mon.pool.contains(i) || *i == mon.start),
            "teach required TMs"
        );
        let seconds = row["seconds"].as_f64().expect("seconds");
        assert!(
            seconds > 0. && seconds <= 15.,
            "diagnostics are limited to 15s"
        );
        let seed = row["seed"].as_u64().expect("seed");
        assert!(seed <= u32::MAX as u64);
        let mode = row["mode"].as_str().expect("mode: opening or assembled");
        assert!(["opening", "assembled"].contains(&mode));
        let second = row["second"].as_str().map(|id| index(data, id));
        if let Some(i) = second {
            assert!(
                i != group[0] && mon.start_choices(&data.moves).contains(&i),
                "legal second starting attack"
            );
        }
        let mut known = group.iter().copied().collect::<BTreeSet<_>>();
        if let Some(i) = second {
            known.insert(i);
        }
        assert!(
            known.len() <= 4,
            "second starting attack occupies one of four learned slots"
        );
        let stock = base(data, dex).start;
        assert!(
            stock == group[0]
                || !group.contains(&stock)
                || mon.pool.contains(&stock)
                || second == Some(stock),
            "off-pool stock attack requires the second starting slot"
        );
        let mut ext = Ext {
            ability: Some(ab.into()),
            bonded: mode == "assembled",
            rift: mode == "opening",
            bosses: true,
            full_cards: true,
            initial_second: second,
            alt: if mode == "opening" { second } else { None },
            ..Ext::default()
        };
        for &i in &group[1..] {
            if data.moves[i].is_attack() {
                ext.companions.push(i);
            } else if i == data.swords_dance || i == data.nasty_plot || i == data.dragon_dance {
                assert!(ext.buffs & 1 == 0, "only one attack buff supported");
                ext.buffs |= 1;
                ext.np = i == data.nasty_plot;
                ext.dd = i == data.dragon_dance;
            } else if i == data.harden || i == data.agility {
                assert!(ext.buffs & 2 == 0, "only one defense buff supported");
                ext.buffs |= 2;
                ext.agi = i == data.agility;
            } else {
                panic!("unsupported buff: {}", data.moves[i].id);
            }
        }
        tasks.push(Task {
            spec: row,
            mon,
            start: group[0],
            opts: Opts {
                seed: seed as u32,
                seconds,
                cards: true,
                bot: Bot::Play,
                terrain: true,
                trace: false,
                ext,
            },
        });
    }
    tasks
}

pub(crate) fn execute(data: &Data, tables: &Tables, task: &Task) -> Value {
    let t = Instant::now();
    let result = run_match(&Libm, data, tables, &task.mon, task.start, &task.opts);
    assert!(
        [result.time, result.hp, result.dealt, result.risk.damage]
            .iter()
            .all(|x| x.is_finite()),
        "non-finite result"
    );
    json!({"spec":task.spec,"result":run_value(&result),"elapsedMs":t.elapsed().as_millis(),"rankingReady":false})
}

pub fn evaluate(data: &Data, path: &str) {
    let tasks = prepare(data, path);
    let tables = Tables::new();
    for task in tasks {
        println!("{}", execute(data, &tables, &task));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn reject(name: &str, mutate: impl FnOnce(&mut Vec<Value>)) {
        let data = Data::load(concat!(env!("CARGO_MANIFEST_DIR"), "/../data/game.json"));
        let mut row: Value = serde_json::from_str(
            include_str!("../../tests/smoke.jsonl")
                .lines()
                .next()
                .unwrap(),
        )
        .unwrap();
        row["engineFingerprint"] = json!(fingerprint());
        let mut rows = vec![row];
        mutate(&mut rows);
        let path = std::env::temp_dir().join(format!(
            "pokesim-reject-{}-{name}.jsonl",
            std::process::id()
        ));
        std::fs::write(
            &path,
            rows.iter()
                .map(Value::to_string)
                .collect::<Vec<_>>()
                .join("\n"),
        )
        .unwrap();
        let result = std::panic::catch_unwind(|| prepare(&data, path.to_str().unwrap()));
        std::fs::remove_file(path).unwrap();
        assert!(
            result.is_err(),
            "invalid manifest must be rejected before execution"
        );
    }
    #[test]
    fn rejects_over_budget_without_running() {
        reject("time", |r| r[0]["seconds"] = json!(16));
        reject("count", |r| *r = vec![r[0].clone(); 21]);
    }
    #[test]
    fn rejects_stale_or_illegal_profiles_without_running() {
        reject("stale", |r| r[0]["engineFingerprint"] = json!("stale"));
        reject("ability", |r| r[0]["ability"] = json!("huge-power"));
        reject("slots", |r| r[0]["second"] = json!("psybeam"));
    }
    #[test]
    fn validates_later_rows_before_any_execution() {
        reject("later", |r| {
            r.push(r[0].clone());
            r[1]["seconds"] = json!(16);
        });
    }
}
