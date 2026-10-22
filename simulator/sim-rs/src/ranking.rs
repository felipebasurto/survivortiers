//! Laboratory-guided, bounded attack ranking. This path constructs a small heuristic
//! frontier directly and evaluates it with the production Rust combat engine.
use crate::{
    data::{Data, Kind, Mon},
    engine::{ranking_prior, PriorAttack, Tables},
    production::{atomic_json, hash_value, paired_interval, run_configuration},
    research,
    selection::{self, BuildStyle, CombatRole, Configuration},
};
use rayon::prelude::*;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicBool, AtomicU64, Ordering as AtomicOrdering},
        Arc, Mutex,
    },
    thread,
    time::Instant,
};

const POLICY: &str = "bounded-ranking-v2";
const CAP: usize = 12;

/// Fingerprint match dependencies, intentionally independent of roster-wide `Data::dex`.
/// Data tables used by combat (global moves, enemies, terrain and type chart) remain included.
struct FingerprintContext {
    global: String,
    species: BTreeMap<u32, String>,
}
impl FingerprintContext {
    fn new(data: &Data) -> Self {
        let mut h = Sha256::new();
        for src in [
            include_bytes!("engine.rs").as_slice(),
            include_bytes!("engine/abilities.rs"),
            include_bytes!("engine/kinds.rs"),
            include_bytes!("data.rs"),
            include_bytes!("terrain.rs"),
            include_bytes!("radii.rs"),
            include_bytes!("rng.rs"),
            include_bytes!("math.rs"),
            include_bytes!("combat_runner.rs"),
            include_bytes!("../Cargo.toml"),
            include_bytes!("../Cargo.lock"),
        ] {
            h.update((src.len() as u64).to_le_bytes());
            h.update(src);
        }
        let mut game: Value =
            serde_json::from_str(include_str!("../../data/game.json")).expect("pinned game data");
        if let Some(o) = game.as_object_mut() {
            for k in ["dex", "gameCommit", "sourceHashes"] {
                o.remove(k);
            }
        }
        h.update(serde_json::to_vec(&game).unwrap());
        // Boss selection reads global dex order, BST/legendary flags, and enemy combat stats.
        let enemies = data
            .dex
            .iter()
            .map(|m| {
                json!([
                    m.dex, m.bst, m.leg, m.spd, m.types, m.r, m.pa, m.sa, m.df, m.sd, m.hp, m.atk
                ])
            })
            .collect::<Vec<_>>();
        h.update(serde_json::to_vec(&enemies).unwrap());
        let parsed_moves = data
            .moves
            .iter()
            .map(|m| {
                json!([
                    m.id,
                    m.kind_name,
                    format!("{:?}", m.kind),
                    m.max_lvl,
                    m.levels
                        .iter()
                        .map(|l| format!("{l:?}"))
                        .collect::<Vec<_>>(),
                    m.evo.as_ref().map(|l| format!("{l:?}")),
                    format!("{:?}", m.needs)
                ])
            })
            .collect::<Vec<_>>();
        h.update(serde_json::to_vec(&parsed_moves).unwrap());
        h.update(serde_json::to_vec(&data.combos).unwrap());
        h.update(serde_json::to_vec(&data.tmult).unwrap());
        h.update(format!("{:?}", data.tiers).as_bytes());
        let raw: Value =
            serde_json::from_str(include_str!("../../data/game.json")).expect("pinned game data");
        let mut species = BTreeMap::new();
        for m in &data.dex {
            let source = raw["dex"]
                .as_array()
                .and_then(|xs| xs.iter().find(|x| x["dex"].as_u64() == Some(m.dex as u64)))
                .cloned()
                .unwrap_or(Value::Null);
            let move_ids = |xs: &[usize]| {
                xs.iter()
                    .map(|i| data.moves[*i].id.clone())
                    .collect::<Vec<_>>()
            };
            let mut sh = Sha256::new();
            sh.update(serde_json::to_vec(&source).unwrap());
            sh.update(
                serde_json::to_vec(&json!([
                    m.dex,
                    m.name,
                    m.types,
                    m.hp,
                    m.spd,
                    m.atk,
                    m.r,
                    m.pa,
                    m.sa,
                    m.df,
                    m.sd,
                    m.start,
                    move_ids(&m.pool),
                    move_ids(&m.tms),
                    m.abilities,
                    m.leg,
                    m.bst
                ]))
                .unwrap(),
            );
            species.insert(m.dex, format!("{:x}", sh.finalize()));
        }
        Self {
            global: format!("{:x}", h.finalize()),
            species,
        }
    }
}
fn config_fingerprint(context: &FingerprintContext, config: &Configuration) -> String {
    hash_value(&json!([
        context.global,
        context.species.get(&config.dex),
        config.moves,
        config.tms,
        config.second,
        config.nature,
        config.ability,
        config.nature_equivalence
    ]))
}
#[cfg(test)]
pub(crate) fn simulation_fingerprint(data: &Data, config: &Configuration) -> String {
    config_fingerprint(&FingerprintContext::new(data), config)
}

fn read(path: &str) -> Result<Value, String> {
    serde_json::from_slice(&fs::read(path).map_err(|e| format!("{path}: {e}"))?)
        .map_err(|e| e.to_string())
}
fn save(path: &str, v: &Value) -> Result<(), String> {
    atomic_json(Path::new(path), v)
}
fn strings(v: &Value) -> Result<Vec<String>, String> {
    v.as_array()
        .ok_or("expected array")?
        .iter()
        .map(|x| {
            x.as_str()
                .map(str::to_owned)
                .ok_or_else(|| "expected string".into())
        })
        .collect()
}
fn move_score(lab: &Value, id: &str) -> (f64, f64, f64) {
    lab["moves"]
        .as_array()
        .into_iter()
        .flatten()
        .find(|x| x["id"].as_str() == Some(id))
        .map(|x| {
            (
                x["score"].as_f64().unwrap_or(0.),
                x["earlyScore"].as_f64().unwrap_or(0.),
                x["lateScore"].as_f64().unwrap_or(0.),
            )
        })
        .unwrap_or((0., 0., 0.))
}
fn lab_move_rank(data: &Data, base: &Mon, lab: &Value, ix: usize) -> (f64, f64, f64) {
    let m = &data.moves[ix];
    let l = &m.levels[0];
    let (score, early, late) = move_score(lab, &m.id);
    let catfit = match l.cat {
        1 => base.pa / base.atk.max(f64::MIN_POSITIVE),
        2 => base.sa / base.atk.max(f64::MIN_POSITIVE),
        _ => 1.0,
    };
    let hit = PriorAttack {
        ty: l.ty,
        cat: l.cat,
        primary: base.types.first().copied().unwrap_or(0),
        own: base.types.contains(&l.ty),
        melee: m.kind == Kind::Melee,
        dash: m.kind_name == "dash" || l.xk == 5,
        base_dmg: l.dmg,
        count: l.count,
        bounce: l.bounce > 0.,
        has_effect: l.status || l.slow > 0. || l.burn > 0. || l.poison > 0.,
        tags: l.tags,
    };
    let ability = base
        .abilities
        .iter()
        .flatten()
        .next()
        .map(String::as_str)
        .unwrap_or("");
    let prior = ranking_prior(ability, hit).0;
    let proxy = score.max(0.)
        * catfit
        * prior
        * if base.types.len() == 1 && base.types[0] == l.ty {
            1.2
        } else {
            1.
        };
    (proxy, early, late)
}
fn attack(data: &Data, ix: usize) -> bool {
    data.moves[ix].is_attack()
}
fn compatible(data: &Data, a: usize, b: usize) -> bool {
    let x = &data.moves[a].levels[0];
    let y = &data.moves[b].levels[0];
    (x.hex > 0. && (y.burn > 0. || y.poison > 0. || y.slow > 0.))
        || (y.hex > 0. && (x.burn > 0. || x.poison > 0. || x.slow > 0.))
}
fn style(data: &Data, ix: usize) -> bool {
    data.moves[ix].kind == Kind::Melee
}

fn config(
    data: &Data,
    base: &Mon,
    group: &[usize],
    branch: &str,
    st: &str,
) -> Result<Configuration, String> {
    configure_build(data, base, group, branch, st, "hardy")
}

/// Natures the ranking tries for one move group: neutral, plus every nature that raises the
/// group's dominant offensive stat (physical `cat` 1 -> `pa`, special `cat` 2 -> `sa`). Each of
/// those natures lowers a different stat, so the search decides which drop costs least.
fn nature_options(data: &Data, group: &[usize]) -> Result<Vec<String>, String> {
    let attacks = || group.iter().copied().filter(|&i| data.moves[i].is_attack());
    let physical = attacks().filter(|&i| data.moves[i].levels[0].cat == 1).count();
    let special = attacks().filter(|&i| data.moves[i].levels[0].cat == 2).count();
    let raised = if physical >= special { "pa" } else { "sa" };
    let natures = data.natures.as_array().ok_or("nature table missing")?;
    let mut out = vec!["hardy".to_string()];
    for n in natures {
        if n["up"].as_str() == Some(raised) {
            out.push(n["id"].as_str().ok_or("nature id missing")?.to_string());
        }
    }
    Ok(out)
}

fn configure_build(
    data: &Data,
    base: &Mon,
    group: &[usize],
    branch: &str,
    st: &str,
    nature: &str,
) -> Result<Configuration, String> {
    let mut ordered = group.to_vec();
    let teach_ids = group
        .iter()
        .filter(|&&i| !base.pool.contains(&i) && i != base.start)
        .map(|&i| data.moves[i].id.clone())
        .collect::<Vec<_>>();
    let configured = data.configure(base, "hardy", None, &teach_ids)?;
    let opener = ordered
        .iter()
        .copied()
        .find(|&i| data.moves[i].is_attack() && configured.start_choices(&data.moves).contains(&i))
        .ok_or("proposal has no legal attack opener")?;
    ordered.retain(|&i| i != opener);
    ordered.insert(0, opener);
    let ids = ordered
        .iter()
        .map(|&i| data.moves[i].id.clone())
        .collect::<Vec<_>>();
    let tms = group
        .iter()
        .filter(|&&i| !base.pool.contains(&i) && i != base.start)
        .map(|&i| data.moves[i].id.clone())
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect::<Vec<_>>();
    // Starter must be an actual starting attack; stock is retained as second when displaced.
    let second = if opener != base.start && group.contains(&base.start) {
        Some(data.moves[base.start].id.clone())
    } else {
        None
    };
    let eq = selection::nature_equivalence(data, base, nature)?;
    // The stock control keeps the species' own default ability; only candidates choose by prior.
    let ability = if branch == "control" {
        None
    } else {
        base.abilities
        .iter()
        .flatten()
        .max_by(|a, b| {
            let prior = |id: &str| {
                group
                    .iter()
                    .filter(|&&i| data.moves[i].is_attack())
                    .map(|&i| {
                        let m = &data.moves[i];
                        let l = &m.levels[0];
                        ranking_prior(
                            id,
                            PriorAttack {
                                ty: l.ty,
                                cat: l.cat,
                                primary: base.types[0],
                                own: base.types.contains(&l.ty),
                                melee: m.kind == Kind::Melee,
                                dash: m.kind_name == "dash" || l.xk == 5,
                                base_dmg: l.dmg,
                                count: l.count,
                                bounce: l.bounce > 0.,
                                has_effect: l.status || l.slow > 0. || l.burn > 0. || l.poison > 0.,
                                tags: l.tags,
                            },
                        )
                        .0
                    })
                    .sum::<f64>()
            };
            prior(a).total_cmp(&prior(b)).then_with(|| a.cmp(b))
        })
        .cloned()
    };
    let dex = base.dex;
    let moves = ids.clone();
    let id = format!(
        "dex{dex}|{}|{branch}|{st}|ability:{}|nature:{nature}",
        ids.join(","),
        ability.as_deref().unwrap_or("default")
    );
    Ok(Configuration {
        id,
        dex,
        moves,
        tms,
        second,
        nature: nature.into(),
        ability,
        nature_equivalence: eq,
        style: if st == "melee" {
            BuildStyle::Melee
        } else {
            BuildStyle::Ranged
        },
        role: CombatRole::Base,
    })
}
fn config_json(c: &Configuration) -> Value {
    json!({"id":c.id,"dex":c.dex,"moves":c.moves,"tms":c.tms,"second":c.second,"nature":c.nature,"ability":c.ability,"nature_equivalence":c.nature_equivalence,"style":if c.style==BuildStyle::Melee{"melee"}else{"ranged"},"role":"base"})
}
fn export_config(c: &Configuration, branch: &str, data: &Data) -> Value {
    let tm_cost = c
        .tms
        .iter()
        .map(|id| data.tm_prices.get(id).copied().unwrap_or(0) as u64)
        .sum::<u64>();
    json!({"id":c.id,"dex":c.dex,"group":c.moves,"moves":c.moves,"tms":c.tms,"tmCost":tm_cost,"secondStart":c.second,"second":c.second,"nature":c.nature,"ability":c.ability,"natureEquivalence":c.nature_equivalence,"nature_equivalence":c.nature_equivalence,"style":if c.style==BuildStyle::Melee{"melee"}else{"ranged"},"build":if c.style==BuildStyle::Melee{"melee"}else{"ranged"},"role":"base","branch":branch})
}
fn propose(
    data: &Data,
    base: &Mon,
    lab: &Value,
    branch: &str,
    st: &str,
    tm_budget: Option<u64>,
    cap: usize,
) -> Result<Vec<Configuration>, String> {
    let taught = branch == "taught";
    let mut legal = base
        .pool
        .iter()
        .copied()
        .chain(std::iter::once(base.start))
        .chain(if taught {
            base.tms.iter().copied().collect::<Vec<_>>()
        } else {
            vec![]
        })
        .filter(|&i| attack(data, i))
        .collect::<Vec<_>>();
    legal.sort_unstable();
    legal.dedup();
    let candidates = legal
        .iter()
        .copied()
        .filter(|&i| style(data, i) == (st == "melee"))
        .collect::<Vec<_>>();
    let mut ranked = candidates
        .iter()
        .copied()
        .map(|i| (i, lab_move_rank(data, base, lab, i)))
        .collect::<Vec<_>>();
    ranked.sort_by(|a, b| {
        b.1 .0
            .total_cmp(&a.1 .0)
            .then_with(|| data.moves[a.0].id.cmp(&data.moves[b.0].id))
    });
    let taught_ids = if taught {
        base.tms.iter().map(|&i| data.moves[i].id.clone()).collect()
    } else {
        Vec::new()
    };
    let opener_mon = data.configure(base, "hardy", None, &taught_ids)?;
    let legal_openers = opener_mon.start_choices(&data.moves);
    let anchor = ranked
        .iter()
        .find(|(i, _)| legal_openers.contains(i))
        .map(|(i, _)| *i);
    let mut groups = Vec::<Vec<usize>>::new();
    let mut add = |mut g: Vec<usize>| {
        if !g
            .iter()
            .any(|i| data.moves[*i].is_attack() && legal_openers.contains(i))
        {
            let Some(lead) = anchor else {
                return;
            };
            if g.len() < 4 {
                g.push(lead);
            } else if let Some(slot) = g.iter().rposition(|i| data.moves[*i].is_attack()) {
                g[slot] = lead;
            }
        }
        g.sort_unstable();
        g.dedup();
        if !g.is_empty() && g.len() <= 4 && groups.len() < 48 && !groups.contains(&g) {
            groups.push(g)
        }
    };

    // `add` keeps insertion order and the stratum is cut at the candidate ceiling, so the
    // families below are listed by priority: each must reach the frontier before the fillers.
    let has_move =
        |ix: usize| base.pool.contains(&ix) || base.start == ix || (taught && base.tms.contains(&ix));
    // First legal physical (Swords/Dragon Dance) or special (Nasty Plot) offensive buff.
    let attack_buff = |cat: u8| -> Option<usize> {
        let options: &[usize] = match cat {
            1 => &[data.swords_dance, data.dragon_dance],
            2 => &[data.nasty_plot],
            _ => &[],
        };
        options.iter().copied().find(|&b| has_move(b))
    };
    // Fortaleza/Agilidad are only ever judged by survival matches (the laboratory player is
    // immune), so they must be proposed here for the rounds to see them at all.
    let defense_buffs = [data.harden, data.agility]
        .into_iter()
        .filter(|&b| has_move(b))
        .collect::<Vec<_>>();
    // The leading pure-damage candidate is a four-attack bonded group when legal.
    if ranked.len() >= 4 {
        add(ranked.iter().take(4).map(|x| x.0).collect());
    }
    if let Some(&(i, _)) = ranked.first() {
        add(vec![i]);
    }
    if taught {
        // Keep a genuine taught alternative even when the best natural attacks rank higher.
        if let Some(&(tm, _)) = ranked
            .iter()
            .find(|(i, _)| !base.pool.contains(i) && *i != base.start)
        {
            let mut group = vec![tm];
            group.extend(
                ranked
                    .iter()
                    .filter(|(i, _)| *i != tm)
                    .take(3)
                    .map(|(i, _)| *i),
            );
            add(group);
        }
    }
    // Measured interactions nominate legal groups, ordered by their gain over the baseline
    // (components played together, or the slot filled by the best other attack). Survival
    // still decides the winner.
    let mut hints = lab["measuredSynergies"]
        .as_array()
        .into_iter()
        .flatten()
        .filter(|h| h["relativeGain"].as_f64().is_some_and(|g| g > 1.0))
        .collect::<Vec<_>>();
    hints.sort_by(|a, b| {
        b["relativeGain"]
            .as_f64()
            .unwrap_or(0.)
            .total_cmp(&a["relativeGain"].as_f64().unwrap_or(0.))
    });
    let hint_groups = hints
        .into_iter()
        .filter_map(|h| {
            let attacks = h["attacks"].as_array()?;
            let buffs = h["buffs"].as_array()?;
            let ids = attacks
                .iter()
                .chain(buffs)
                .map(|v| data.move_ix.get(v.as_str()?).copied())
                .collect::<Option<Vec<_>>>()?;
            let allowed = ids.iter().all(|i| {
                if data.moves[*i].is_attack() {
                    candidates.contains(i)
                } else {
                    has_move(*i)
                }
            });
            allowed.then_some(ids)
        })
        .take(3)
        .map(|mut assembled| {
            for &(i, _) in &ranked {
                if assembled.len() >= 4 {
                    break;
                }
                if !assembled.contains(&i) {
                    assembled.push(i);
                }
            }
            assembled
        })
        .collect::<Vec<_>>();
    if let Some(first) = hint_groups.first() {
        add(first.clone());
    }
    // Three attacking moves plus a matching physical/special attack buff. Buff legality
    // comes from this species' actual natural pool or TM list; never inject global buffs.
    for (buff, cat) in [
        (data.swords_dance, 1u8),
        (data.dragon_dance, 1u8),
        (data.nasty_plot, 2u8),
    ] {
        if !has_move(buff) {
            continue;
        }
        let mut group = ranked
            .iter()
            .filter(|x| data.moves[x.0].levels[0].cat == cat)
            .take(3)
            .map(|x| x.0)
            .collect::<Vec<_>>();
        if !group.is_empty() {
            group.push(buff);
            add(group);
        }
    }
    // Defensive buffs: three attacks plus Harden or Agility, and the two-attack shape with
    // one offensive and one defensive buff that the site's builds describe.
    for &buff in &defense_buffs {
        let mut group = ranked.iter().take(3).map(|x| x.0).collect::<Vec<_>>();
        if !group.is_empty() {
            group.push(buff);
            add(group);
        }
    }
    if let (Some(&(lead, _)), Some(&defense)) = (ranked.first(), defense_buffs.first()) {
        if let Some(buff) = attack_buff(data.moves[lead].levels[0].cat) {
            let mut group = ranked.iter().take(2).map(|x| x.0).collect::<Vec<_>>();
            group.extend([buff, defense]);
            add(group);
        }
    }
    // Engine-supported hex/status pairs and their companion group. Hex needs a burning,
    // poisoned or slowed target; the first pair in damage order is kept early and a second
    // distinct pair after the scene specialists.
    let mut pairs = Vec::<(usize, usize)>::new();
    'pairs: for &(i, _) in &ranked {
        for &(j, _) in ranked.iter().filter(|x| x.0 != i) {
            if compatible(data, i, j) && !pairs.contains(&(j, i)) {
                pairs.push((i, j));
                if pairs.len() == 2 {
                    break 'pairs;
                }
                break;
            }
        }
    }
    let add_pair = |add: &mut dyn FnMut(Vec<usize>), (i, j): (usize, usize)| {
        add(vec![i, j]);
        if let Some(&(k, _)) = ranked.iter().find(|x| x.0 != i && x.0 != j) {
            let mut combo = vec![i, j, k];
            if let Some(b) = attack_buff(data.moves[k].levels[0].cat) {
                combo.push(b);
            }
            add(combo);
        }
    };
    if let Some(&pair) = pairs.first() {
        add_pair(&mut add, pair);
    }
    // Keep specialists for each enemy geometry, rather than relying only on headline DPS.
    let scene_score = |ix: usize, scene: &str| -> f64 {
        lab["moves"]
            .as_array()
            .into_iter()
            .flatten()
            .find(|m| m["id"] == data.moves[ix].id)
            .and_then(|m| m["scenarios"].as_array())
            .map(|scenes| {
                let values = scenes
                    .iter()
                    .filter(|row| row["id"].as_str().is_some_and(|id| id.starts_with(scene)))
                    .filter_map(|row| row["damagePerSecond"].as_f64())
                    .collect::<Vec<_>>();
                values.iter().sum::<f64>() / values.len().max(1) as f64
            })
            .unwrap_or(0.)
    };
    for scene in ["boss-", "surround-", "approach-"] {
        if let Some(&(leader, _)) = ranked.iter().max_by(|a, b| {
            scene_score(a.0, scene)
                .total_cmp(&scene_score(b.0, scene))
                .then_with(|| b.0.cmp(&a.0))
        }) {
            let mut group = vec![leader];
            group.extend(
                ranked
                    .iter()
                    .filter(|(i, _)| *i != leader)
                    .take(3)
                    .map(|(i, _)| *i),
            );
            add(group);
        }
    }
    // Complementary pair: the best early-level attack with the best late-level attack.
    let mut early = ranked.clone();
    early.sort_by(|a, b| {
        b.1 .1
            .total_cmp(&a.1 .1)
            .then_with(|| data.moves[a.0].id.cmp(&data.moves[b.0].id))
    });
    let mut late = ranked.clone();
    late.sort_by(|a, b| {
        b.1 .2
            .total_cmp(&a.1 .2)
            .then_with(|| data.moves[a.0].id.cmp(&data.moves[b.0].id))
    });
    if let (Some((e, _)), Some((l, _))) = (early.first(), late.iter().find(|x| x.0 != early[0].0)) {
        add(vec![*e, *l]);
    }
    for group in hint_groups.iter().skip(1) {
        add(group.clone());
    }
    if let Some(&pair) = pairs.get(1) {
        add_pair(&mut add, pair);
    }
    // Deterministic one-slot substitutions explore distinct top attacks without a cartesian scan.
    if ranked.len() >= 4 {
        let seed = ranked.iter().take(4).map(|x| x.0).collect::<Vec<_>>();
        for (slot, &(replacement, _)) in ranked.iter().skip(4).take(4).enumerate() {
            let mut g = seed.clone();
            let replace_slot = slot % g.len();
            g[replace_slot] = replacement;
            add(g);
        }
    }
    for &(i, _) in ranked.iter().take(8) {
        add(vec![i]);
    }
    let mut out = Vec::new();
    let mut taken = 0usize;
    for mut g in groups {
        g.sort_by(|a, b| {
            lab_move_rank(data, base, lab, *b)
                .0
                .total_cmp(&lab_move_rank(data, base, lab, *a).0)
                .then_with(|| a.cmp(b))
        });
        let teach = g
            .iter()
            .filter(|&&i| !base.pool.contains(&i) && i != base.start)
            .map(|&i| data.moves[i].id.clone())
            .collect::<Vec<_>>();
        if taught && teach.is_empty() {
            continue;
        }
        if !taught && !teach.is_empty() {
            continue;
        }
        let cost = teach
            .iter()
            .map(|id| data.tm_prices.get(id).copied().unwrap_or(0) as u64)
            .sum::<u64>();
        if tm_budget.is_some_and(|m| cost > m) {
            continue;
        }
        // The move cap bounds groups; each group then fans out over its nature options.
        for nature in nature_options(data, &g)? {
            if let Ok(c) = configure_build(data, base, &g, branch, st, &nature) {
                out.push(c);
            }
        }
        taken += 1;
        if taken == cap.min(CAP) {
            break;
        }
    }
    Ok(out)
}

fn manifest(
    data: &Data,
    v: &Value,
) -> Result<
    (
        Vec<u32>,
        f64,
        usize,
        Option<u64>,
        Vec<u32>,
        Vec<u32>,
        Vec<u32>,
        usize,
    ),
    String,
> {
    if v["schema"].as_u64() != Some(1)
        || v["kind"].as_str() != Some("bounded-ranking")
        || v["policyVersion"].as_str() != Some(POLICY)
    {
        return Err("manifest schema/kind/policyVersion mismatch".into());
    }
    if v["gameCommit"].as_str() != Some(research::GAME_COMMIT)
        || v["engineFingerprint"].as_str() != Some(research::fingerprint().as_str())
    {
        return Err("manifest gameCommit or engineFingerprint is stale".into());
    }
    let seconds = v["secondsPerMatch"]
        .as_f64()
        .ok_or("secondsPerMatch missing")?;
    let threads = v["threads"]
        .as_u64()
        .filter(|n| *n > 0 && *n <= 32)
        .ok_or("threads must be in 1..=32")? as usize;
    let cap = v["candidatesPerStratum"]
        .as_u64()
        .filter(|n| *n > 0 && *n <= 12)
        .ok_or("candidatesPerStratum must be in 1..=12")? as usize;
    if !seconds.is_finite() || seconds <= 0. || seconds > 900. {
        return Err("secondsPerMatch must be in (0,900]".into());
    }
    let dex = if v["dex"].as_str() == Some("all") {
        data.dex.iter().map(|m| m.dex).collect()
    } else {
        v["dex"]
            .as_array()
            .ok_or("dex must be all or an array")?
            .iter()
            .map(|x| {
                x.as_u64()
                    .map(|n| n as u32)
                    .ok_or_else(|| String::from("dex IDs must be u32"))
            })
            .collect::<Result<Vec<_>, _>>()?
    };
    let mut seen = BTreeSet::new();
    let dex = dex
        .into_iter()
        .filter(|d| seen.insert(*d))
        .collect::<Vec<_>>();
    if dex.is_empty() || dex.iter().any(|d| !data.dex.iter().any(|m| m.dex == *d)) {
        return Err("dex must be nonempty, unique, and present in data".into());
    }
    let seeds = |key: &str| -> Result<Vec<u32>, String> {
        let a = v["seeds"][key]
            .as_array()
            .ok_or_else(|| format!("seeds.{key} must be an array"))?;
        let xs = a
            .iter()
            .map(|x| {
                x.as_u64()
                    .filter(|n| *n <= u32::MAX as u64)
                    .map(|n| n as u32)
                    .ok_or_else(|| format!("seeds.{key} values must be u32"))
            })
            .collect::<Result<Vec<_>, _>>()?;
        if xs.is_empty() || xs.iter().copied().collect::<BTreeSet<_>>().len() != xs.len() {
            return Err(format!("seeds.{key} must be nonempty and unique"));
        }
        Ok(xs)
    };
    let a = seeds("A")?;
    let b = seeds("B")?;
    let d = seeds("D")?;
    if a.len() != 2
        || b.len() != 8
        || d.len() != 16
        || a.iter()
            .chain(&b)
            .chain(&d)
            .copied()
            .collect::<BTreeSet<_>>()
            .len()
            != 26
    {
        return Err("seed sets must be disjoint A2/B8/D16".into());
    }
    let budget = match v.get("tmBudget") {
        None | Some(Value::Null) => None,
        Some(value) => Some(
            value
                .as_u64()
                .ok_or("tmBudget must be a nonnegative integer")?,
        ),
    };
    Ok((dex, seconds, threads, budget, a, b, d, cap))
}

fn build_plan(data: &Data, mv: &Value, lab: &Value) -> Result<Value, String> {
    let (dex, seconds, threads, tm_budget, a, b, d, cap) = manifest(data, mv)?;
    if lab["schema"].as_u64() != Some(1)
        || lab["kind"].as_str() != Some("attack-lab-results")
        || lab["complete"].as_bool() != Some(true)
        || lab["policyVersion"].as_str() != Some("attack-lab-v1")
        || lab["gameCommit"].as_str() != Some(research::GAME_COMMIT)
        || lab["scope"].as_str() != Some("all-supported-attacks")
        || lab["partialScope"].as_bool() != Some(false)
        || lab["engineFingerprint"].as_str() != Some(research::fingerprint().as_str())
    {
        return Err("attack lab is incomplete or stale".into());
    }
    let lab_moves = lab["moves"].as_array().ok_or("lab move list missing")?;
    let mut covered = BTreeSet::new();
    for row in lab_moves {
        let id = row["id"].as_str().ok_or("lab move id missing")?;
        if !covered.insert(id) || !data.move_ix.contains_key(id) {
            return Err("lab has duplicate or unknown moves".into());
        }
        for key in ["score", "earlyScore", "lateScore"] {
            if !row[key].as_f64().is_some_and(|v| v.is_finite() && v >= 0.) {
                return Err(format!("invalid lab {key} for {id}"));
            }
        }
    }
    if data
        .moves
        .iter()
        .filter(|m| m.is_attack())
        .any(|m| !covered.contains(m.id.as_str()))
    {
        return Err("lab is missing attack measurements".into());
    }
    let mut rows = Vec::new();
    let mut controls = Vec::new();
    let mut counts = BTreeMap::<String, u64>::new();
    for id in dex {
        let base = data.dex.iter().find(|m| m.dex == id).unwrap();
        for branch in ["natural", "taught"] {
            for st in ["melee", "ranged"] {
                let mut cs = propose(data, base, lab, branch, st, tm_budget, cap)?;
                let published = if branch == "natural" {
                    "optimized_no_tm"
                } else {
                    "optimized_tm"
                };
                let key = format!("{id}|{published}|{st}");
                counts.insert(key.clone(), cs.len() as u64);
                for (rank, c) in cs.drain(..).enumerate() {
                    rows.push(json!({"stratum":key,"rank":rank,"branch":published,"config":config_json(&c)}));
                }
                // One stock control per species (stock opener, default ability, neutral nature). It does not
                // depend on branch or style, so every stratum of the species is compared against it.
                let stock = base.start;
                if attack(data, stock)
                    && !controls
                        .iter()
                        .any(|r: &Value| r["config"]["dex"].as_u64() == Some(id as u64))
                {
                    let stock_style = if style(data, stock) {
                        "melee"
                    } else {
                        "ranged"
                    };
                    let c = config(data, base, &[stock], "control", stock_style)?;
                    controls.push(json!({"stratum":format!("{id}|control"),"branch":"control","config":config_json(&c)}));
                }
            }
        }
    }
    let stage_a = (rows.len() + controls.len()) as u64 * a.len() as u64;
    let mut stage_b = 0u64;
    let mut stage_d = 0u64;
    let mut active_dex = BTreeSet::new();
    for (stratum, n) in &counts {
        if *n > 0 {
            let dex = stratum
                .split('|')
                .next()
                .and_then(|s| s.parse::<u32>().ok())
                .unwrap_or(0);
            active_dex.insert(dex);
            stage_b += (*n).min(3) * b.len() as u64;
            stage_d += d.len() as u64;
        }
    }
    let controlled_dex = controls
        .iter()
        .filter(|r| active_dex.contains(&(r["config"]["dex"].as_u64().unwrap_or(0) as u32)))
        .count() as u64;
    stage_b += controlled_dex * b.len() as u64;
    stage_d += controlled_dex * d.len() as u64;
    let unsigned = json!({"schema":1,"kind":"bounded-ranking-plan","policyVersion":POLICY,"gameCommit":research::GAME_COMMIT,"engineFingerprint":research::fingerprint(),"manifestHash":hash_value(mv),"labHash":hash_value(lab),"secondsPerMatch":seconds,"threads":threads,"seeds":{"A":a,"B":b,"D":d},"candidates":rows,"controls":controls,"counts":{"strata":counts,"candidateConfigurations":rows.len(),"controlConfigurations":controls.len(),"stageAMatchesUpperBound":stage_a,"stageBMatchesUpperBound":stage_b,"stageDMatchesUpperBound":stage_d,"matchesUpperBound":stage_a+stage_b+stage_d,"simulatedSecondsUpperBound":(stage_a+stage_b+stage_d) as f64*seconds}});
    let mut plan = unsigned.clone();
    plan["planHash"] = json!(hash_value(&unsigned));
    Ok(plan)
}

fn decode_config(v: &Value) -> Result<Configuration, String> {
    let dex = v["dex"].as_u64().ok_or("config dex missing")? as u32;
    let moves = strings(&v["moves"])?;
    let tms = strings(&v["tms"])?;
    let second = v["second"].as_str().map(str::to_owned);
    let nature = v["nature"].as_str().ok_or("nature missing")?.to_owned();
    let ability = v["ability"].as_str().map(str::to_owned);
    let eq = v["nature_equivalence"]
        .as_str()
        .or(v["natureEquivalence"].as_str())
        .unwrap_or("")
        .to_owned();
    // serde uses snake_case for this internally created JSON row.
    Ok(Configuration {
        id: v["id"].as_str().ok_or("config id missing")?.into(),
        dex,
        moves,
        tms,
        second,
        nature,
        ability,
        nature_equivalence: eq,
        style: if v["style"].as_str() == Some("melee") || v["style"].as_str() == Some("Melee") {
            BuildStyle::Melee
        } else {
            BuildStyle::Ranged
        },
        role: CombatRole::Base,
    })
}
fn get_config(row: &Value) -> Result<Configuration, String> {
    decode_config(&row["config"])
}
fn match_key(context: &FingerprintContext, c: &Configuration, seed: u32, seconds: f64) -> String {
    hash_value(&json!([config_fingerprint(context, c), seed, seconds]))
}
fn cached_run(
    data: &Data,
    tables: &Tables,
    c: &Configuration,
    seed: u32,
    seconds: f64,
    dir: &Path,
    context: &FingerprintContext,
) -> Result<Value, String> {
    fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    let key = match_key(context, c, seed, seconds);
    let path = dir.join(format!("{key}.json"));
    if path.exists() {
        let v: Value = serde_json::from_slice(&fs::read(&path).map_err(|e| e.to_string())?)
            .map_err(|e| e.to_string())?;
        if v["cacheKey"].as_str() == Some(key.as_str()) {
            return Ok(v["match"].clone());
        }
        return Err(format!("cache entry invalid: {}", path.display()));
    }
    let result = run_configuration(data, tables, c, seed, seconds)?;
    let envelope = json!({"cacheKey":key,"match":result});
    atomic_json(&path, &envelope)?;
    Ok(result)
}
fn outcome(
    row: &Value,
    cache: &Path,
    data: &Data,
    tables: &Tables,
    stage: &str,
    seeds: &[u32],
    seconds: f64,
    context: &FingerprintContext,
) -> Result<Value, String> {
    let c = get_config(row)?;
    let mut observations = Vec::new();
    for &seed in seeds {
        let m = cached_run(data, tables, &c, seed, seconds, cache, context)?;
        observations.push(m["metrics"].clone());
    }
    let mean = |k: &str| {
        observations
            .iter()
            .map(|m| m[k].as_f64().unwrap_or(0.))
            .sum::<f64>()
            / observations.len().max(1) as f64
    };
    let survived = observations
        .iter()
        .map(|m| m["survivalSeconds"].as_f64().unwrap_or(0.))
        .sum::<f64>();
    let damage = observations
        .iter()
        .map(|m| m["damage"].as_f64().unwrap_or(0.))
        .sum::<f64>();
    let kills = observations
        .iter()
        .map(|m| m["kills"].as_f64().unwrap_or(0.))
        .sum::<f64>();
    Ok(
        json!({"config":export_config(&c,row["branch"].as_str().unwrap_or("optimized_no_tm"),data),"branch":row["branch"],"stratum":row["stratum"],"stage":stage,"seeds":seeds,"meanSurvival":mean("survivalSeconds"),"meanDamagePerSecond":damage/survived.max(f64::MIN_POSITIVE),"meanDamage":mean("damage"),"meanKills":mean("kills"),"meanKillsPerMinute":60.*kills/survived.max(f64::MIN_POSITIVE),"exposureDiagnostic":{"contactDamage":mean("contactDamage"),"contactSeconds":mean("contactSeconds"),"trappedSeconds":mean("trappedSeconds")},"matches":observations}),
    )
}

fn group_by_stratum(rows: &[Value]) -> BTreeMap<String, Vec<Value>> {
    let mut out = BTreeMap::<String, Vec<Value>>::new();
    for row in rows {
        if let Some(s) = row["stratum"].as_str() {
            out.entry(s.to_owned()).or_default().push(row.clone());
        }
    }
    out
}
fn rank_rows(rows: &mut [Value]) {
    rows.sort_by(|x, y| {
        y["meanSurvival"]
            .as_f64()
            .unwrap_or(0.)
            .total_cmp(&x["meanSurvival"].as_f64().unwrap_or(0.))
            .then_with(|| {
                y["meanDamagePerSecond"]
                    .as_f64()
                    .unwrap_or(0.)
                    .total_cmp(&x["meanDamagePerSecond"].as_f64().unwrap_or(0.))
            })
    });
}

/// Live counters shared with the heartbeat thread. Stage sizes after A depend on earlier
/// results, so the file reports the current stage and what the plan still has to play.
struct Progress {
    completed: AtomicU64,
    stage_total: AtomicU64,
    stage_done: AtomicU64,
    stage: Mutex<String>,
    started: Instant,
}
impl Progress {
    fn snapshot(&self) -> Value {
        let stage = self
            .stage
            .lock()
            .map(|s| s.clone())
            .unwrap_or_else(|_| "unknown".into());
        let remaining: &[&str] = match stage.as_str() {
            "initializing" => &["A", "B", "D"],
            "A" => &["B", "D"],
            "B" => &["D"],
            _ => &[],
        };
        json!({"kind":"bounded-ranking-progress","stage":stage,
            "completedConfigurationRuns":self.completed.load(AtomicOrdering::Relaxed),
            "stageConfigurations":self.stage_total.load(AtomicOrdering::Relaxed),
            "stageCompletedConfigurations":self.stage_done.load(AtomicOrdering::Relaxed),
            "pendingStagesAfterCurrent":remaining,
            "elapsedWallSeconds":self.started.elapsed().as_secs_f64()})
    }
    fn write(&self, path: &str) -> Value {
        let row = self.snapshot();
        let _ = atomic_json(Path::new(path), &row);
        row
    }
}

fn run(data: &Data, plan_path: &str, cache_path: &str, result_path: &str) -> Result<(), String> {
    let stop = Arc::new(AtomicBool::new(false));
    let progress = Arc::new(Progress {
        completed: AtomicU64::new(0),
        stage_total: AtomicU64::new(0),
        stage_done: AtomicU64::new(0),
        stage: Mutex::new(String::from("initializing")),
        started: Instant::now(),
    });
    let stop_bg = stop.clone();
    let progress_bg = progress.clone();
    let path = format!("{result_path}.progress.json");
    let heartbeat = thread::spawn(move || {
        let mut last = Instant::now();
        while !stop_bg.load(AtomicOrdering::Relaxed) {
            if last.elapsed() >= std::time::Duration::from_secs(60) {
                let row = progress_bg.write(&path);
                eprintln!(
                    "bounded-ranking heartbeat: stage={}, stage runs={}/{}, runs={}, elapsed={}s",
                    row["stage"],
                    row["stageCompletedConfigurations"],
                    row["stageConfigurations"],
                    row["completedConfigurationRuns"],
                    row["elapsedWallSeconds"]
                );
                last = Instant::now();
            }
            thread::sleep(std::time::Duration::from_secs(1));
        }
    });
    let result = run_inner(data, plan_path, cache_path, result_path, &progress);
    stop.store(true, AtomicOrdering::Relaxed);
    let _ = heartbeat.join();
    result
}
fn run_inner(
    data: &Data,
    plan_path: &str,
    cache_path: &str,
    result_path: &str,
    progress: &Progress,
) -> Result<(), String> {
    let progress_path = format!("{result_path}.progress.json");
    let plan = read(plan_path)?;
    if plan["kind"].as_str() != Some("bounded-ranking-plan")
        || plan["schema"].as_u64() != Some(1)
        || plan["gameCommit"].as_str() != Some(research::GAME_COMMIT)
        || plan["engineFingerprint"].as_str() != Some(research::fingerprint().as_str())
    {
        return Err("plan kind/schema/game/engine mismatch".into());
    }
    let mut unsigned = plan.clone();
    let ph = unsigned["planHash"]
        .as_str()
        .ok_or("planHash missing")?
        .to_owned();
    unsigned.as_object_mut().unwrap().remove("planHash");
    if hash_value(&unsigned) != ph {
        return Err("planHash mismatch".into());
    }
    let candidates = plan["candidates"]
        .as_array()
        .ok_or("candidate list missing")?;
    let controls = plan["controls"].as_array().ok_or("control list missing")?;
    let seeds = &plan["seeds"];
    let a = seeds["A"]
        .as_array()
        .ok_or("seed A missing")?
        .iter()
        .map(|x| x.as_u64().unwrap() as u32)
        .collect::<Vec<_>>();
    let b = seeds["B"]
        .as_array()
        .ok_or("seed B missing")?
        .iter()
        .map(|x| x.as_u64().unwrap() as u32)
        .collect::<Vec<_>>();
    let d = seeds["D"]
        .as_array()
        .ok_or("seed D missing")?
        .iter()
        .map(|x| x.as_u64().unwrap() as u32)
        .collect::<Vec<_>>();
    let seconds = plan["secondsPerMatch"].as_f64().ok_or("seconds missing")?;
    let threads = plan["threads"]
        .as_u64()
        .filter(|n| *n > 0 && *n <= 32)
        .ok_or("plan threads invalid")? as usize;
    let cache = PathBuf::from(cache_path);
    fs::create_dir_all(&cache).map_err(|e| format!("create cache directory: {e}"))?;
    let _writer_lock = crate::cache_lock::WriterLock::acquire(&cache.join(".ranking.lock"))?;
    let tables = Tables::new();
    let fingerprints = FingerprintContext::new(data);
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(threads)
        .build()
        .map_err(|e| e.to_string())?;
    let start = Instant::now();
    let mut candidate_obs = Vec::<Value>::new();
    let mut control_obs = Vec::<Value>::new();
    let run_stage = |stage: &str, rows: &[Value], seeds: &[u32]| -> Result<Vec<Value>, String> {
        if let Ok(mut s) = progress.stage.lock() {
            *s = stage.to_owned();
        }
        progress
            .stage_total
            .store(rows.len() as u64, AtomicOrdering::Relaxed);
        progress.stage_done.store(0, AtomicOrdering::Relaxed);
        progress.write(&progress_path);
        eprintln!(
            "bounded-ranking round {stage}: {} configurations x {} seeds",
            rows.len(),
            seeds.len()
        );
        let out = pool.install(|| {
            rows.par_iter()
                .map(|row| {
                    let r = outcome(
                        row,
                        &cache,
                        data,
                        &tables,
                        stage,
                        seeds,
                        seconds,
                        &fingerprints,
                    );
                    progress.completed.fetch_add(1, AtomicOrdering::Relaxed);
                    progress.stage_done.fetch_add(1, AtomicOrdering::Relaxed);
                    r
                })
                .collect::<Result<Vec<_>, _>>()
        })?;
        Ok(out)
    };
    let arows = run_stage("A", candidates, &a)?;
    let ac = run_stage("A", controls, &a)?;
    candidate_obs.extend(arows.clone());
    control_obs.extend(ac.clone());
    let a_by = group_by_stratum(&arows);
    let candidate_by = group_by_stratum(candidates);
    let mut bsource = Vec::<Value>::new();
    for (stratum, mut group) in a_by {
        rank_rows(&mut group);
        let source = candidate_by.get(&stratum).and_then(|xs| xs.first());
        for obs in group.into_iter().take(3) {
            bsource.push(json!({"stratum":stratum,"branch":source.map(|r|r["branch"].clone()).unwrap_or(Value::Null),"config":obs["config"]}));
        }
    }
    let brows = run_stage("B", &bsource, &b)?;
    candidate_obs.extend(brows.clone());
    let b_by = group_by_stratum(&brows);
    let mut dsource = Vec::<Value>::new();
    for (stratum, mut group) in b_by {
        rank_rows(&mut group);
        if let Some(best) = group.into_iter().next() {
            dsource
                .push(json!({"stratum":stratum,"branch":best["branch"],"config":best["config"]}));
        }
    }
    let drows = run_stage("D", &dsource, &d)?;
    candidate_obs.extend(drows.clone());
    let controls_b = run_stage(
        "B",
        controls
            .iter()
            .filter(|r| {
                bsource
                    .iter()
                    .any(|c| c["config"]["dex"] == r["config"]["dex"])
            })
            .cloned()
            .collect::<Vec<_>>()
            .as_slice(),
        &b,
    )?;
    control_obs.extend(controls_b.clone());
    let controls_d = run_stage(
        "D",
        controls
            .iter()
            .filter(|r| {
                dsource
                    .iter()
                    .any(|c| c["config"]["dex"] == r["config"]["dex"])
            })
            .cloned()
            .collect::<Vec<_>>()
            .as_slice(),
        &d,
    )?;
    control_obs.extend(controls_d.clone());
    let winner_rows = drows.iter().map(|o| {
        let dex = o["config"]["dex"].as_u64();
        let control = controls_d.iter().find(|c| c["config"]["dex"].as_u64() == dex);
        let deltas = o["matches"].as_array().into_iter().flatten()
            .zip(control.and_then(|c| c["matches"].as_array()).into_iter().flatten())
            .map(|(candidate, stock)| candidate["survivalSeconds"].as_f64().unwrap_or(0.) - stock["survivalSeconds"].as_f64().unwrap_or(0.))
            .collect::<Vec<_>>();
        json!({"dex":o["config"]["dex"],"branch":o["branch"],"style":o["config"]["build"],
            "configuration":o["config"],"status":"best_observed","winnerConfirmed":deltas.len() == d.len(),
            "meanSurvival":o["meanSurvival"],"meanDamagePerSecond":o["meanDamagePerSecond"],
            "meanKills":o["meanKills"],"meanKillsPerMinute":o["meanKillsPerMinute"],
            "exposureDiagnostic":o["exposureDiagnostic"],
            "pairedConfirmation":{"n":deltas.len(),"seeds":d,"survivalDelta":paired_interval(&deltas),
                "candidateMatches":o["matches"],"controlMatches":control.map(|c|c["matches"].clone()).unwrap_or(Value::Null),
                "controlMeanSurvival":control.map(|c|c["meanSurvival"].clone()).unwrap_or(Value::Null)}})
    }).collect::<Vec<_>>();
    let control_rows=controls_d.iter().map(|o|json!({"complete":true,"dex":o["config"]["dex"],"stratum":o["stratum"],"configuration":o["config"],"meanSurvival":o["meanSurvival"],"meanDamagePerSecond":o["meanDamagePerSecond"],"meanKills":o["meanKills"],"matches":o["matches"]})).collect::<Vec<_>>();
    let unavailable=plan["counts"]["strata"].as_object().into_iter().flatten().filter_map(|(key,n)|{if n.as_u64().unwrap_or(0)>0{return None}let mut p=key.split('|');let dex=p.next()?.parse::<u32>().ok()?;let branch=p.next()?;let style=p.next()?;Some(json!({"dex":dex,"variantId":format!("{style}:base:{branch}"),"reason":"no legal candidate in bounded proposal frontier"}))}).collect::<Vec<_>>();
    let result = json!({"schema":1,"kind":"bounded-ranking-results","complete":true,"rankingReady":false,"policyVersion":POLICY,"gameCommit":research::GAME_COMMIT,"engineFingerprint":research::fingerprint(),"planHash":ph,"seedSets":{"A":a,"B":b,"D":d,"screening":a.iter().chain(&b).copied().collect::<BTreeSet<_>>(),"confirmation":d},"elapsedWallSeconds":start.elapsed().as_secs_f64(),"candidateObservations":candidate_obs,"controlObservations":control_obs,"winners":winner_rows,"controls":control_rows,"unavailable":unavailable,"counts":{"candidateMatchesCompleted":candidate_obs.iter().map(|r| r["seeds"].as_array().map_or(0, Vec::len)).sum::<usize>(),"controlMatchesCompleted":control_obs.iter().map(|r| r["seeds"].as_array().map_or(0, Vec::len)).sum::<usize>()}});
    save(result_path, &result)?;
    if let Ok(mut s) = progress.stage.lock() {
        *s = "complete".into();
    }
    progress.write(&progress_path);
    Ok(())
}

/// CLI contract: `plan <manifest.json> <lab.json> <plan.json>` and
/// `run|resume <plan.json> <cache-dir> <results.json>`.
pub fn command(data: &Data, args: &[String]) -> Result<(), String> {
    match args.first().map(String::as_str){
    Some("plan") if args.len()==4=>{let mv=read(&args[1])?;let lab=read(&args[2])?;let p=build_plan(data,&mv,&lab)?;save(&args[3],&p)},
    Some("run"|"resume") if args.len()==4=>run(data,&args[1],&args[2],&args[3]),
    _=>Err("usage: ranking plan <manifest.json> <lab.json> <plan.json> | ranking run|resume <plan.json> <cache-dir> <results.json>".into())
}
}

#[cfg(test)]
mod tests {
    use super::*;

    fn data() -> Data {
        Data::load(
            Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("../data/game.json")
                .to_str()
                .unwrap(),
        )
    }
    fn lab(data: &Data) -> Value {
        json!({"schema":1,"kind":"attack-lab-results","complete":true,"policyVersion":"attack-lab-v1","gameCommit":research::GAME_COMMIT,"scope":"all-supported-attacks","partialScope":false,"engineFingerprint":research::fingerprint(),"moves":data.moves.iter().filter(|m|m.is_attack()).enumerate().map(|(i,m)|json!({"id":m.id,"score":1000.-i as f64,"earlyScore":if i%2==0{10.}else{1.},"lateScore":if i%2==1{10.}else{1.},"scenarios":[{"id":"test","level":10,"seeds":[1],"damagePerSecond":10.,"killsPerMinute":1.}]})).collect::<Vec<_>>()})
    }
    fn manifest(_data: &Data) -> Value {
        json!({"schema":1,"kind":"bounded-ranking","policyVersion":POLICY,"gameCommit":research::GAME_COMMIT,"engineFingerprint":research::fingerprint(),"dex":"all","secondsPerMatch":0.1,"threads":2,"candidatesPerStratum":12,"seeds":{"A":[1001,1002],"B":[1101,1102,1103,1104,1105,1106,1107,1108],"D":[3001,3002,3003,3004,3005,3006,3007,3008,3009,3010,3011,3012,3013,3014,3015,3016]}})
    }

    #[test]
    fn all_roster_plan_is_bounded_legal_and_has_only_genuinely_taught_tm_rows() {
        let data = data();
        let p = build_plan(&data, &manifest(&data), &lab(&data)).unwrap();
        let rows = p["candidates"].as_array().unwrap();
        let mut counts = BTreeMap::<String, usize>::new();
        let mut retained_status = false;
        let mut retained_buff = false;
        let mut retained_taught_buff = false;
        let mut retained_defense = false;
        let defense_ids = [
            data.moves[data.harden].id.clone(),
            data.moves[data.agility].id.clone(),
        ];
        // Each of the 12 move groups per stratum fans out to at most 5 natures (neutral plus the
        // four that raise the dominant offensive stat). Measured full roster upper bound: 441,506.
        assert!(p["counts"]["matchesUpperBound"].as_u64().unwrap() < 500_000);
        for row in rows {
            *counts
                .entry(row["stratum"].as_str().unwrap().to_owned())
                .or_default() += 1;
            assert!(counts[row["stratum"].as_str().unwrap()] <= 12 * 5);
            let c = &row["config"];
            let dex = c["dex"].as_u64().unwrap() as u32;
            let base = data.dex.iter().find(|m| m.dex == dex).unwrap();
            let group = strings(&c["moves"]).unwrap();
            let tms = strings(&c["tms"]).unwrap();
            assert!(!group.is_empty() && group.len() <= 4);
            let taught = tms
                .iter()
                .map(|id| *data.move_ix.get(id.as_str()).unwrap())
                .collect::<Vec<_>>();
            assert!(taught
                .iter()
                .all(|ix| base.tms.contains(ix) && !base.pool.contains(ix)));
            assert_eq!(
                row["branch"].as_str() == Some("optimized_tm"),
                !tms.is_empty()
            );
            let configured = data
                .configure(base, "hardy", c["ability"].as_str(), &tms)
                .unwrap();
            let lead = *data.move_ix.get(group[0].as_str()).unwrap();
            assert!(data.moves[lead].is_attack());
            assert!(configured.start_choices(&data.moves).contains(&lead));
            for id in &group {
                let ix = *data.move_ix.get(id.as_str()).unwrap();
                assert!(base.pool.contains(&ix) || base.start == ix || taught.contains(&ix));
                if data.moves[ix].is_attack() {
                    assert_eq!(style(&data, ix), c["style"] == "melee");
                }
            }
            let indices = group
                .iter()
                .map(|id| data.move_ix[id.as_str()])
                .collect::<Vec<_>>();
            for &i in &indices {
                for &j in &indices {
                    if compatible(&data, i, j) {
                        retained_status = true;
                    }
                }
            }
            let buffs = indices
                .iter()
                .filter(|&&i| !data.moves[i].is_attack())
                .count();
            assert!(buffs <= 2, "the engine admits at most two planned buffs");
            if group.iter().any(|id| defense_ids.contains(id)) {
                retained_defense = true;
            }
            if buffs > 0
                && indices
                    .iter()
                    .filter(|&&i| data.moves[i].is_attack())
                    .count()
                    >= 3
            {
                retained_buff = true;
                if !tms.is_empty() {
                    retained_taught_buff = true;
                }
            }
        }
        assert!(
            retained_status,
            "reserved engine-supported hex/status synergy must survive stratum truncation"
        );
        assert!(
            retained_buff,
            "reserved three-attacks-plus-legal-buff proposal must survive stratum truncation"
        );
        assert!(
            retained_taught_buff,
            "at least one retained buff group must be genuinely taught"
        );
        assert!(
            retained_defense,
            "Harden/Agility proposals must reach the survival rounds"
        );
    }

    #[test]
    fn nature_options_follow_the_groups_dominant_offense() {
        let data = data();
        let physical = data
            .moves
            .iter()
            .position(|m| m.is_attack() && m.levels[0].cat == 1)
            .unwrap();
        let special = data
            .moves
            .iter()
            .position(|m| m.is_attack() && m.levels[0].cat == 2)
            .unwrap();
        let p = nature_options(&data, &[physical]).unwrap();
        assert_eq!(p[0], "hardy");
        assert_eq!(p.len(), 5);
        assert!(p.iter().any(|n| n == "adamant"));
        assert!(!p.iter().any(|n| n == "modest"));
        let s = nature_options(&data, &[special]).unwrap();
        assert_eq!(s[0], "hardy");
        assert_eq!(s.len(), 5);
        assert!(s.iter().any(|n| n == "modest"));
        assert!(!s.iter().any(|n| n == "adamant"));
    }

    #[test]
    fn stock_control_keeps_the_default_ability_while_candidates_choose_one() {
        let data = data();
        let base = data
            .dex
            .iter()
            .find(|m| m.abilities.iter().flatten().count() > 1)
            .expect("a species with a choice of abilities");
        let control = config(&data, base, &[base.start], "control", "ranged").unwrap();
        assert_eq!(control.ability, None);
        let candidate = config(&data, base, &[base.start], "natural", "ranged").unwrap();
        assert!(candidate.ability.is_some());
    }

    #[test]
    fn only_measured_gains_nominate_a_hint_group() {
        let data = data();
        let lab = lab(&data);
        let (base, st, ranked) = data
            .dex
            .iter()
            .find_map(|base| {
                ["melee", "ranged"].into_iter().find_map(|st| {
                    let mut legal = base
                        .pool
                        .iter()
                        .copied()
                        .chain(std::iter::once(base.start))
                        .filter(|&i| attack(&data, i) && style(&data, i) == (st == "melee"))
                        .collect::<Vec<_>>();
                    legal.sort_unstable();
                    legal.dedup();
                    let mut ranked = legal
                        .into_iter()
                        .map(|i| (i, lab_move_rank(&data, base, &lab, i).0))
                        .collect::<Vec<_>>();
                    ranked.sort_by(|a, b| {
                        b.1.total_cmp(&a.1)
                            .then_with(|| data.moves[a.0].id.cmp(&data.moves[b.0].id))
                    });
                    (ranked.len() >= 8)
                        .then(|| (base.clone(), st, ranked.iter().map(|x| x.0).collect::<Vec<_>>()))
                })
            })
            .expect("a species with enough attacks of one style");
        let (a, b) = (data.moves[ranked[5]].id.clone(), data.moves[ranked[6]].id.clone());
        let propose_with = |gain: f64| {
            let mut guided = lab.clone();
            guided["measuredSynergies"] =
                json!([{"attacks":[a, b],"buffs":[],"score":1e9,"relativeGain":gain}]);
            propose(&data, &base, &guided, "natural", st, None, 12).unwrap()
        };
        let has_pair = |groups: &[Configuration]| {
            groups
                .iter()
                .any(|c| c.moves.contains(&a) && c.moves.contains(&b))
        };
        assert!(has_pair(&propose_with(2.0)));
        assert!(!has_pair(&propose_with(0.8)));
    }

    #[test]
    fn match_cache_reuses_real_metrics_across_stage_independent_keys() {
        let data = data();
        let base = data.dex.iter().find(|m| m.dex == 25).unwrap();
        let c = config(&data, base, &[base.start], "natural", "ranged").unwrap();
        let root = std::env::temp_dir().join(format!(
            "bounded-ranking-cache-{}-{}",
            std::process::id(),
            std::thread::current().name().unwrap_or("test")
        ));
        let _ = fs::remove_dir_all(&root);
        let tables = Tables::new();
        let context = FingerprintContext::new(&data);
        let first = cached_run(&data, &tables, &c, 77, 0.1, &root, &context).unwrap();
        let second = cached_run(&data, &tables, &c, 77, 0.1, &root, &context).unwrap();
        assert_eq!(first, second);
        assert!(first["metrics"]["survivalSeconds"].as_f64().is_some());
        assert_eq!(fs::read_dir(&root).unwrap().count(), 1);
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn unrelated_learnset_reuses_but_boss_stats_and_move_damage_invalidate() {
        let mut data = data();
        let base = data.dex.iter().find(|m| m.dex == 25).unwrap().clone();
        let c = config(&data, &base, &[base.start], "natural", "ranged").unwrap();
        let before = simulation_fingerprint(&data, &c);
        let other = data.dex.iter_mut().find(|m| m.dex == 54).unwrap();
        other.pool.pop();
        assert_eq!(before, simulation_fingerprint(&data, &c));
        data.dex.iter_mut().find(|m| m.dex == 54).unwrap().spd += 1.;
        assert_ne!(before, simulation_fingerprint(&data, &c));
        let mut move_change = self::data();
        move_change.moves[base.start].levels[0].dmg += 1.;
        assert_ne!(before, simulation_fingerprint(&move_change, &c));
    }

    #[test]
    fn runtime_species_stats_participate_in_cache_fingerprint() {
        let mut data = data();
        let base = data.dex.iter().find(|m| m.dex == 25).unwrap().clone();
        let c = config(&data, &base, &[base.start], "natural", "ranged").unwrap();
        let before = simulation_fingerprint(&data, &c);
        data.dex.iter_mut().find(|m| m.dex == 25).unwrap().hp += 1.;
        let after = simulation_fingerprint(&data, &c);
        assert_ne!(before, after);
    }

    #[test]
    fn short_plan_runs_and_resumes_through_all_three_rounds() {
        let data = data();
        let base = data.dex.iter().find(|m| m.dex == 25).unwrap();
        let st = if style(&data, base.start) {
            "melee"
        } else {
            "ranged"
        };
        let cfg = config(&data, base, &[base.start], "natural", st).unwrap();
        let config_value = config_json(&cfg);
        let stratum = format!("25|optimized_no_tm|{st}");
        let mut plan = json!({"schema":1,"kind":"bounded-ranking-plan","policyVersion":POLICY,"gameCommit":research::GAME_COMMIT,"engineFingerprint":research::fingerprint(),"secondsPerMatch":0.05,"threads":2,"seeds":{"A":[1,2],"B":[3,4,5,6,7,8,9,10],"D":[11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26]},"candidates":[{"stratum":stratum,"branch":"optimized_no_tm","config":config_value}],"controls":[{"stratum":stratum,"branch":"optimized_no_tm","config":config_value}]});
        let ph = hash_value(&plan);
        plan["planHash"] = json!(ph);
        let dir = std::env::temp_dir().join(format!("bounded-ranking-e2e-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        let plan_path = dir.join("plan.json");
        let result_path = dir.join("results.json");
        let cache = dir.join("cache");
        save(plan_path.to_str().unwrap(), &plan).unwrap();
        run(
            &data,
            plan_path.to_str().unwrap(),
            cache.to_str().unwrap(),
            result_path.to_str().unwrap(),
        )
        .unwrap();
        let first = read(result_path.to_str().unwrap()).unwrap();
        run(
            &data,
            plan_path.to_str().unwrap(),
            cache.to_str().unwrap(),
            result_path.to_str().unwrap(),
        )
        .unwrap();
        let second = read(result_path.to_str().unwrap()).unwrap();
        assert_eq!(
            first["winners"][0]["meanSurvival"],
            second["winners"][0]["meanSurvival"]
        );
        assert_eq!(
            first["winners"][0]["meanDamagePerSecond"],
            second["winners"][0]["meanDamagePerSecond"]
        );
        assert_eq!(first["complete"], true);
        let progress = read(&format!("{}.progress.json", result_path.display())).unwrap();
        assert_eq!(progress["stage"], "complete");
        assert_eq!(progress["pendingStagesAfterCurrent"], json!([]));
        let _ = fs::remove_dir_all(dir);
    }
}
