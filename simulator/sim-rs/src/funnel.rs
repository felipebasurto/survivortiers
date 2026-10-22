//! Staged survival search. Planning counts tasks and writes no match.
//! Run and resume share one cache of atomic per-task checkpoints.
use crate::{
    data::{Data, Kind, Mon},
    engine::Tables,
    production::{
        atomic_json, canonical_bytes, compiler_version, config_proxy, hash_value, normalized_exposure,
        paired_interval, run_configuration, task_id, taught_tm_cost, visit_groups,
    },
    research,
    selection::{self, BuildStyle, CombatRole, Configuration},
};
use rayon::prelude::*;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet, HashMap},
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicU32, Ordering},
        OnceLock,
    },
    time::Instant,
};

const POLICY: &str = "survivortiers-funnel-v1";
const MARGIN: f64 = 0.10;
const FALLBACK_GROUPS: usize = 30;
const MORNING_GROUPS_B: u64 = 4;
const MORNING_GROUPS_C: u64 = 2;
const MORNING_SEEDS_A: u64 = 4;
const MORNING_SEEDS_B: u64 = 32;
const MORNING_SEEDS_C: u64 = 4;
const MORNING_SEEDS_D: u64 = 32;
const MATCH_CEILING: u64 = 17_116 * 72_000 / 100;
// Longer than the 2.5 h wrapper. A 900 s plan wall returned on purpose and the
// next resume reloaded the plan and reread finished checkpoints.
const FUNNEL_WALL_LIMIT: f64 = 10800.0;

struct Spec {
    raw: Value,
    dex: Vec<u32>,
    seconds: f64,
    threads: usize,
    max_wall: f64,
    max_failed: u32,
    max_matches: u64,
    tm_budget: Option<u64>,
    groups_a: usize,
    groups_b: usize,
    groups_c: usize,
    seeds_a: Vec<u32>,
    seeds_b: Vec<u32>,
    seeds_c: Vec<u32>,
    seeds_d: Vec<u32>,
    recall: Vec<u32>,
    hash: String,
}

struct Proposal {
    config: Configuration,
    score: f64,
    moves: Vec<usize>,
}

fn u32_list(v: &Value, name: &str) -> Result<Vec<u32>, String> {
    let a = v
        .as_array()
        .ok_or_else(|| format!("{name} must be an array"))?;
    let mut out = Vec::new();
    let mut seen = BTreeSet::new();
    for x in a {
        let n = x
            .as_u64()
            .filter(|n| *n <= u32::MAX as u64)
            .ok_or_else(|| format!("{name} values must be u32"))? as u32;
        if !seen.insert(n) {
            return Err(format!("duplicate {name} seed {n}"));
        }
        out.push(n);
    }
    if out.is_empty() {
        return Err(format!("{name} must not be empty"));
    }
    Ok(out)
}

fn parse_spec(data: &Data, v: Value) -> Result<Spec, String> {
    if v["schema"].as_u64() != Some(1) || v["kind"].as_str() != Some("funnel") {
        return Err("funnel manifest schema/kind mismatch".into());
    }
    if v["gameCommit"].as_str() != Some(research::GAME_COMMIT) {
        return Err("manifest gameCommit is stale".into());
    }
    if v["engineFingerprint"].as_str() != Some(research::fingerprint().as_str()) {
        return Err("manifest engineFingerprint is stale".into());
    }
    if v["policyVersion"].as_str() != Some(POLICY) {
        return Err("unsupported funnel policyVersion".into());
    }
    let mut dex = Vec::new();
    if v["dex"].as_str() == Some("all") {
        dex.extend(data.dex.iter().map(|m| m.dex));
    } else if let Some(a) = v["dex"].as_array() {
        for x in a {
            let n = x.as_u64().ok_or("dex ids must be u32")? as u32;
            if !data.dex.iter().any(|m| m.dex == n) {
                return Err(format!("unknown dex {n}"));
            }
            dex.push(n);
        }
    } else {
        return Err("dex must be 'all' or an array".into());
    }
    if dex.is_empty() || dex.iter().copied().collect::<BTreeSet<_>>().len() != dex.len() {
        return Err("dex list must be nonempty and unique".into());
    }
    let seconds = v["secondsPerMatch"]
        .as_f64()
        .filter(|n| *n > 0. && *n <= 900.)
        .ok_or("secondsPerMatch must be in (0,900]")?;
    let limits = &v["limits"];
    let threads = limits["threads"]
        .as_u64()
        .filter(|n| (1..=256).contains(n))
        .ok_or("threads must be 1..=256")? as usize;
    let max_wall = limits["maxWallSeconds"]
        .as_f64()
        .filter(|n| *n > 0. && *n <= FUNNEL_WALL_LIMIT)
        .ok_or("maxWallSeconds must be in (0,10800]")?;
    let max_failed = limits["maxFailedTasks"].as_u64().ok_or("maxFailedTasks")? as u32;
    let max_matches = limits["maxMatches"].as_u64().ok_or("maxMatches")?;
    let tm_budget = match v.get("tmBudget") {
        None | Some(Value::Null) => None,
        Some(n) => Some(n.as_u64().ok_or("tmBudget must be a nonnegative integer")?),
    };
    let stages = &v["stages"];
    let groups_a = stages["A"]["groups"].as_u64().ok_or("stages.A.groups")? as usize;
    let groups_b = stages["B"]["groups"].as_u64().ok_or("stages.B.groups")? as usize;
    let groups_c = stages["C"]["groups"].as_u64().ok_or("stages.C.groups")? as usize;
    let seeds_a = u32_list(&stages["A"]["seeds"], "stages.A.seeds")?;
    let seeds_b = u32_list(&stages["B"]["seeds"], "stages.B.seeds")?;
    let seeds_c = u32_list(&stages["C"]["seeds"], "stages.C.seeds")?;
    let seeds_d = u32_list(&stages["D"]["seeds"], "stages.D.seeds")?;
    let screen: BTreeSet<_> = seeds_a.iter().chain(&seeds_b).chain(&seeds_c).copied().collect();
    if seeds_d.iter().any(|s| screen.contains(s)) {
        return Err("stage D seeds overlap an earlier stage".into());
    }
    let mut recall = Vec::new();
    if let Some(list) = v.get("recallDexes").and_then(Value::as_array) {
        for item in list {
            if item.as_str() == Some("smallest") {
                recall.push(smallest_dex(data)?);
            } else {
                let n = item.as_u64().ok_or("recall dex must be an id or 'smallest'")? as u32;
                if !data.dex.iter().any(|m| m.dex == n) {
                    return Err(format!("unknown recall dex {n}"));
                }
                recall.push(n);
            }
        }
    }
    recall.sort();
    recall.dedup();
    let hash = hash_value(&v);
    Ok(Spec {
        raw: v,
        dex,
        seconds,
        threads,
        max_wall,
        max_failed,
        max_matches,
        tm_budget,
        groups_a,
        groups_b,
        groups_c,
        seeds_a,
        seeds_b,
        seeds_c,
        seeds_d,
        recall,
        hash,
    })
}

fn mon<'a>(data: &'a Data, dex: u32) -> Result<&'a Mon, String> {
    data.dex
        .iter()
        .find(|m| m.dex == dex)
        .ok_or_else(|| format!("unknown dex {dex}"))
}

fn style_name(style: &BuildStyle) -> &'static str {
    match style {
        BuildStyle::Melee => "melee",
        BuildStyle::Ranged => "ranged",
    }
}

fn style_from(name: &str) -> Result<BuildStyle, String> {
    match name {
        "melee" => Ok(BuildStyle::Melee),
        "ranged" => Ok(BuildStyle::Ranged),
        other => Err(format!("unknown style {other}")),
    }
}

fn attack_indexes(data: &Data, base: &Mon) -> Vec<usize> {
    let mut ids = base
        .pool
        .iter()
        .copied()
        .chain(base.tms.iter().copied())
        .chain(std::iter::once(base.start))
        .filter(|&i| data.moves[i].is_attack())
        .collect::<Vec<_>>();
    ids.sort();
    ids.dedup();
    ids
}

fn smallest_dex(data: &Data) -> Result<u32, String> {
    let min_attacks = data
        .dex
        .iter()
        .map(|m| attack_indexes(data, m).len())
        .min()
        .ok_or("no species")?;
    let mut best: Option<(usize, u32)> = None;
    for base in data.dex.iter().filter(|m| attack_indexes(data, m).len() == min_attacks) {
        let n = legal_groups(data, base).len();
        if best.is_none_or(|(count, _)| n < count) {
            best = Some((n, base.dex));
        }
    }
    best.map(|(_, dex)| dex).ok_or("no smallest species".into())
}

fn choose(items: &[usize], need: usize, from: usize, acc: &mut Vec<usize>, out: &mut Vec<Vec<usize>>) {
    if need == 0 {
        out.push(acc.clone());
        return;
    }
    for i in from..=items.len() - need {
        acc.push(items[i]);
        choose(items, need - 1, i + 1, acc, out);
        acc.pop();
    }
}

fn opener_indexes(data: &Data, base: &Mon) -> BTreeSet<usize> {
    let mut legal: BTreeSet<usize> = base
        .start_choices(&data.moves)
        .into_iter()
        .filter(|&i| data.moves[i].is_attack())
        .collect();
    for &ix in &base.tms {
        if data.moves[ix].is_attack() {
            legal.insert(ix);
        }
    }
    legal
}

fn buff_indexes(data: &Data, base: &Mon) -> Vec<usize> {
    let mut buffs: Vec<usize> = base
        .pool
        .iter()
        .copied()
        .filter(|&i| data.moves[i].kind_name == "buff" && data.moves[i].levels[0].buff != 0)
        .collect();
    for &ix in &base.tms {
        if buffs.contains(&ix) {
            continue;
        }
        if data.moves[ix].kind_name == "buff" && data.moves[ix].levels[0].buff != 0 {
            buffs.push(ix);
        }
    }
    buffs
}

fn each_legal_group(data: &Data, base: &Mon, f: &mut impl FnMut(&[usize])) {
    let legal = opener_indexes(data, base);
    // Taught buffs are partners, not starts. Dragon Dance is the only taught move that can
    // sit in a melee group for 12 species. Leaving it out dropped those optimized_tm strata.
    let buffs = buff_indexes(data, base);
    for melee in [true, false] {
        let attacks = attack_indexes(data, base)
            .into_iter()
            .filter(|&i| (data.moves[i].kind == Kind::Melee) == melee)
            .collect::<Vec<_>>();
        if attacks.is_empty() {
            continue;
        }
        for size in 1..=4.min(attacks.len()) {
            let mut combos = Vec::new();
            choose(&attacks, size, 0, &mut Vec::new(), &mut combos);
            for combo in combos {
                for &lead in combo.iter().filter(|i| legal.contains(i)) {
                    let mut rest = combo.iter().copied().filter(|&i| i != lead).collect::<Vec<_>>();
                    rest.sort();
                    rest.insert(0, lead);
                    f(&rest);
                    if rest.len() < 4 {
                        for &b in &buffs {
                            if !rest.contains(&b) {
                                let mut with = rest.clone();
                                with.push(b);
                                f(&with);
                            }
                        }
                    }
                    if rest.len() <= 2 {
                        for i in 0..buffs.len() {
                            for j in (i + 1)..buffs.len() {
                                if !rest.contains(&buffs[i]) && !rest.contains(&buffs[j]) {
                                    let mut with = rest.clone();
                                    with.push(buffs[i]);
                                    with.push(buffs[j]);
                                    f(&with);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

pub(crate) fn legal_groups(data: &Data, base: &Mon) -> BTreeSet<Vec<usize>> {
    let mut groups = BTreeSet::new();
    each_legal_group(data, base, &mut |group| {
        groups.insert(group.to_vec());
    });
    groups
}

fn branch_of(data: &Data, base: &Mon, group: &[usize]) -> &'static str {
    if group.iter().all(|&i| base.pool.contains(&i) || i == base.start) {
        "optimized_no_tm"
    } else {
        let _ = data;
        "optimized_tm"
    }
}

fn style_of_group(data: &Data, group: &[usize]) -> Option<&'static str> {
    let mut melee = false;
    let mut ranged = false;
    for &i in group {
        if !data.moves[i].is_attack() {
            continue;
        }
        if data.moves[i].kind == Kind::Melee {
            melee = true;
        } else {
            ranged = true;
        }
    }
    match (melee, ranged) {
        (true, false) => Some("melee"),
        (false, true) => Some("ranged"),
        _ => None,
    }
}

fn tm_list(data: &Data, base: &Mon, group: &[usize]) -> Vec<String> {
    let mut tms = group
        .iter()
        .filter(|&&i| !base.pool.contains(&i) && i != base.start)
        .map(|&i| data.moves[i].id.clone())
        .collect::<Vec<_>>();
    tms.sort();
    tms.dedup();
    tms
}

fn second_start(data: &Data, base: &Mon, group: &[usize]) -> Option<String> {
    if group[0] != base.start && group.contains(&base.start) && !base.pool.contains(&base.start) {
        Some(data.moves[base.start].id.clone())
    } else {
        None
    }
}

fn build_config(
    data: &Data,
    base: &Mon,
    group: &[usize],
    nature: &str,
    ability: Option<String>,
    style: &str,
    branch: &str,
) -> Result<Configuration, String> {
    let moves = group.iter().map(|&i| data.moves[i].id.clone()).collect::<Vec<_>>();
    let tms = tm_list(data, base, group);
    let second = second_start(data, base, group);
    let eq = selection::nature_equivalence(data, base, nature)?;
    let aid = ability.as_deref().unwrap_or("default");
    let id = format!(
        "funnel|dex{}|moves:{}|tm:{}|second:{}|style:{style}|branch:{branch}|nature:{eq}|ability:{aid}",
        base.dex,
        moves.join(","),
        if tms.is_empty() { "natural".into() } else { tms.join(",") },
        second.as_deref().unwrap_or("none"),
    );
    let configured = data.configure(base, nature, ability.as_deref(), &tms)?;
    if !configured.start_choices(&data.moves).contains(&group[0]) || !data.moves[group[0]].is_attack() {
        return Err(format!("illegal lead for dex {}", base.dex));
    }
    let taught_lead = group[0] != base.start && !base.pool.contains(&group[0]);
    if taught_lead && branch != "optimized_tm" {
        return Err(format!("TM opener for dex {} belongs on the TM branch", base.dex));
    }
    if !tms.is_empty() && branch != "optimized_tm" {
        return Err(format!("taught moves for dex {} belong on the TM branch", base.dex));
    }
    if let Some(other) = second.as_deref() {
        if other == data.moves[group[0]].id {
            return Err(format!("second start repeats the opener for dex {}", base.dex));
        }
    }
    Ok(Configuration {
        id,
        dex: base.dex,
        moves,
        tms,
        second,
        nature: nature.into(),
        ability,
        nature_equivalence: eq,
        style: style_from(style)?,
        role: CombatRole::Base,
    })
}

fn stock_control(data: &Data, base: &Mon) -> Result<Configuration, String> {
    let style = if data.moves[base.start].kind == Kind::Melee {
        "melee"
    } else {
        "ranged"
    };
    build_config(data, base, &[base.start], "hardy", base.abilities.iter().flatten().next().cloned(), style, "control_no_tm")
}

fn config_json(data: &Data, base: &Mon, config: &Configuration, score: f64) -> Result<Value, String> {
    let tm_cost = taught_tm_cost(data, base, &config.tms)?;
    Ok(json!({
        "id": config.id,
        "dex": config.dex,
        "group": config.moves,
        "tms": config.tms,
        "tmCost": tm_cost,
        "secondStart": config.second,
        "nature": config.nature,
        "ability": config.ability,
        "natureEquivalence": config.nature_equivalence,
        "build": style_name(&config.style),
        "role": "base",
        "branch": if config.id.contains("|branch:control_no_tm|") { "control_no_tm" } else { branch_key(config) },
        "proxyDps": score,
    }))
}

fn branch_key(config: &Configuration) -> &'static str {
    if config.tms.is_empty() { "optimized_no_tm" } else { "optimized_tm" }
}

fn config_from_json(v: &Value) -> Result<Configuration, String> {
    let strings = |key: &str| -> Result<Vec<String>, String> {
        v[key]
            .as_array()
            .ok_or_else(|| format!("{key} missing"))?
            .iter()
            .map(|x| x.as_str().map(str::to_owned).ok_or_else(|| format!("{key} item")))
            .collect()
    };
    Ok(Configuration {
        id: v["id"].as_str().ok_or("id")?.into(),
        dex: v["dex"].as_u64().ok_or("dex")? as u32,
        moves: strings("group")?,
        tms: strings("tms")?,
        second: v["secondStart"].as_str().map(str::to_owned),
        nature: v["nature"].as_str().ok_or("nature")?.into(),
        ability: v["ability"].as_str().map(str::to_owned),
        nature_equivalence: v["natureEquivalence"].as_str().ok_or("natureEquivalence")?.into(),
        style: style_from(v["build"].as_str().ok_or("build")?)?,
        role: CombatRole::Base,
    })
}

fn default_ability(base: &Mon) -> Option<String> {
    base.abilities.iter().flatten().next().cloned()
}

struct Tally {
    style: &'static str,
    branch: &'static str,
    groups: usize,
    sample: Vec<usize>,
}

fn tally_species(data: &Data, base: &Mon) -> Vec<Tally> {
    let mut rows: Vec<Tally> = Vec::new();
    each_legal_group(data, base, &mut |group| {
        let Some(style) = style_of_group(data, group) else {
            return;
        };
        let branch = branch_of(data, base, group);
        if let Some(row) = rows.iter_mut().find(|row| row.style == style && row.branch == branch) {
            row.groups += 1;
        } else {
            rows.push(Tally { style, branch, groups: 1, sample: group.to_vec() });
        }
    });
    rows
}

struct BudgetRow {
    groups: usize,
    profiles: usize,
}

struct Roster {
    cap: usize,
    tasks: u64,
    stage_a: u64,
    full_strata: usize,
    beam_strata: usize,
    enumerated_groups: u64,
    beamed_groups: u64,
    recall_tasks: u64,
}

fn morning_cost(rows: &[BudgetRow], cap: usize, species: u64, recall_tasks: u64) -> Roster {
    let mut stage_a = 0u64;
    let mut stage_b = 0u64;
    let mut stage_c = 0u64;
    let mut stage_d = 0u64;
    let mut full_strata = 0usize;
    let mut beam_strata = 0usize;
    let mut enumerated_groups = 0u64;
    let mut beamed_groups = 0u64;
    for row in rows {
        let under = row.groups <= cap;
        let kept = if under {
            row.groups as u64
        } else {
            (row.groups as u64).min(FALLBACK_GROUPS as u64)
        };
        let stage_b_groups = kept.min(MORNING_GROUPS_B);
        let stage_c_groups = stage_b_groups.min(MORNING_GROUPS_C);
        stage_a += kept * MORNING_SEEDS_A;
        stage_b += stage_b_groups * MORNING_SEEDS_B;
        stage_c += stage_c_groups * row.profiles.max(1) as u64 * MORNING_SEEDS_C;
        stage_d += MORNING_SEEDS_D;
        if under {
            full_strata += 1;
            enumerated_groups += kept;
        } else {
            beam_strata += 1;
            beamed_groups += kept;
        }
    }
    let controls = species * (MORNING_SEEDS_A + MORNING_SEEDS_B + MORNING_SEEDS_D);
    Roster {
        cap,
        tasks: stage_a + stage_b + stage_c + stage_d + controls + recall_tasks,
        stage_a,
        full_strata,
        beam_strata,
        enumerated_groups,
        beamed_groups,
        recall_tasks,
    }
}

fn recall_upper(data: &Data, dex: u32, confirm_seeds: u64) -> Result<u64, String> {
    let rows = tally_species(data, mon(data, dex)?);
    let groups = rows.iter().map(|row| row.groups as u64).sum::<u64>();
    let confirm = rows.iter().map(|row| (row.groups as u64).min(50) * confirm_seeds).sum::<u64>();
    Ok(groups * MORNING_SEEDS_A + confirm)
}

fn roster(data: &Data) -> &'static Roster {
    static CELL: OnceLock<Roster> = OnceLock::new();
    CELL.get_or_init(|| {
        let species = data.dex.len() as u64;
        let rows = data
            .dex
            .par_iter()
            .flat_map(|base| {
                tally_species(data, base)
                    .into_iter()
                    .map(|row| {
                        let profiles = profile_count(data, base, &row.sample, row.style, None).unwrap_or(1);
                        BudgetRow { groups: row.groups, profiles }
                    })
                    .collect::<Vec<_>>()
            })
            .collect::<Vec<_>>();
        let smallest = smallest_dex(data).unwrap_or(132);
        let mut recall_dexes = vec![54, smallest];
        recall_dexes.sort_unstable();
        recall_dexes.dedup();
        let recall_tasks = recall_dexes
            .into_iter()
            .filter_map(|dex| recall_upper(data, dex, MORNING_SEEDS_D).ok())
            .sum();
        let mut caps = rows.iter().map(|row| row.groups).collect::<Vec<_>>();
        caps.push(0);
        caps.sort_unstable();
        caps.dedup();
        let mut chosen = morning_cost(&rows, 0, species, recall_tasks);
        for candidate in caps {
            let cost = morning_cost(&rows, candidate, species, recall_tasks);
            if cost.tasks <= MATCH_CEILING {
                chosen = cost;
            } else {
                break;
            }
        }
        chosen
    })
}

fn sort_proposals(list: &mut [Proposal]) {
    list.sort_by(|a, b| b.score.total_cmp(&a.score).then_with(|| a.config.id.cmp(&b.config.id)));
}

fn has_key(set: &BTreeSet<(String, String)>, style: &str, branch: &str) -> bool {
    set.iter().any(|(have_style, have_branch)| have_style == style && have_branch == branch)
}

fn push_proposal(
    data: &Data,
    base: &Mon,
    group: &[usize],
    ability: &Option<String>,
    budget: Option<u64>,
    grouped: &mut BTreeMap<(String, String), Vec<Proposal>>,
) {
    let Some(style) = style_of_group(data, group) else {
        return;
    };
    let branch = branch_of(data, base, group);
    let Ok(config) = build_config(data, base, group, "hardy", ability.clone(), style, branch) else {
        return;
    };
    if !within_budget(data, base, &config, budget) {
        return;
    }
    let (score, _, _) = config_proxy(data, base, &config);
    grouped.entry((style.to_string(), branch.to_string())).or_default().push(Proposal {
        config,
        score,
        moves: group.to_vec(),
    });
}

fn groups_for(
    data: &Data,
    base: &Mon,
    spec: &Spec,
    cap: usize,
) -> Result<(BTreeMap<(String, String), Vec<Proposal>>, BTreeSet<(String, String)>), String> {
    let tallies = tally_species(data, base);
    let mut under = BTreeSet::new();
    let mut over = BTreeSet::new();
    for row in &tallies {
        let key = (row.style.to_string(), row.branch.to_string());
        if row.groups <= cap {
            under.insert(key);
        } else {
            over.insert(key);
        }
    }
    let ability = default_ability(base);
    let mut grouped = BTreeMap::new();
    if !under.is_empty() {
        each_legal_group(data, base, &mut |group| {
            let Some(style) = style_of_group(data, group) else {
                return;
            };
            let branch = branch_of(data, base, group);
            if !has_key(&under, style, branch) {
                return;
            }
            push_proposal(data, base, group, &ability, spec.tm_budget, &mut grouped);
        });
    }
    if !over.is_empty() {
        let mut taught = base.tms.iter().map(|&ix| data.moves[ix].id.clone()).collect::<Vec<_>>();
        taught.sort();
        let mon = data.configure(base, "hardy", ability.as_deref(), &taught)?;
        visit_groups(data, base, &mon, &mut |group| {
            let Some(style) = style_of_group(data, &group) else {
                return;
            };
            let branch = branch_of(data, base, &group);
            if !has_key(&over, style, branch) {
                return;
            }
            push_proposal(data, base, &group, &ability, spec.tm_budget, &mut grouped);
        });
    }
    for (key, list) in &mut grouped {
        sort_proposals(list);
        if has_key(&over, &key.0, &key.1) {
            list.truncate(spec.groups_a);
        }
    }
    Ok((grouped, over))
}

fn profile_count(
    data: &Data,
    base: &Mon,
    sample: &[usize],
    style: &str,
    budget: Option<u64>,
) -> Result<usize, String> {
    let ids = sample.iter().map(|&i| data.moves[i].id.clone()).collect::<Vec<_>>();
    let cfgs = selection::configurations(data, base.dex, &[ids], style_from(style)?, CombatRole::Base)?;
    let kept = cfgs.iter().filter(|c| within_budget(data, base, c, budget)).count();
    Ok(kept.max(1))
}

fn within_budget(data: &Data, base: &Mon, config: &Configuration, budget: Option<u64>) -> bool {
    let Ok(cost) = taught_tm_cost(data, base, &config.tms) else {
        return false;
    };
    budget.is_none_or(|limit| cost <= limit)
}

struct PartGuard {
    paths: Vec<PathBuf>,
}

impl Drop for PartGuard {
    fn drop(&mut self) {
        for path in &self.paths {
            let _ = fs::remove_file(path);
        }
    }
}

struct Sink {
    inner: File,
    hash: Sha256,
}

impl Sink {
    fn push(&mut self, bytes: &[u8]) -> Result<(), String> {
        self.hash.update(bytes);
        self.inner.write_all(bytes).map_err(|e| e.to_string())
    }

    fn finish(mut self) -> Result<String, String> {
        self.inner.flush().map_err(|e| e.to_string())?;
        self.inner.sync_all().map_err(|e| e.to_string())?;
        Ok(format!("{:x}", self.hash.finalize()))
    }
}

fn write_value(file: &mut File, started: &mut bool, item: &Value) -> Result<(), String> {
    if *started {
        file.write_all(b",").map_err(|e| e.to_string())?;
    }
    *started = true;
    file.write_all(&canonical_bytes(item)).map_err(|e| e.to_string())
}

fn push_field(sink: &mut Sink, started: &mut bool, name: &str, value: &Value) -> Result<(), String> {
    if *started {
        sink.push(b",")?;
    }
    *started = true;
    sink.push(b"\"")?;
    sink.push(name.as_bytes())?;
    sink.push(b"\":")?;
    sink.push(&canonical_bytes(value))
}

fn copy_into(sink: &mut Sink, path: &Path) -> Result<(), String> {
    let mut input = File::open(path).map_err(|e| e.to_string())?;
    let mut buf = vec![0u8; 1 << 20];
    loop {
        let n = input.read(&mut buf).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        sink.push(&buf[..n])?;
    }
    Ok(())
}

fn seal_plan(unsigned: &Path, out: &Path, digest: &str) -> Result<(), String> {
    let mut input = File::open(unsigned).map_err(|e| e.to_string())?;
    let len = input.metadata().map_err(|e| e.to_string())?.len();
    if len == 0 {
        return Err("empty funnel plan".into());
    }
    let tmp = out.with_extension(format!("tmp-{}", std::process::id()));
    let mut output = File::create(&tmp).map_err(|e| e.to_string())?;
    let mut left = len - 1;
    let mut buf = vec![0u8; 1 << 20];
    while left > 0 {
        let want = left.min(buf.len() as u64) as usize;
        let n = input.read(&mut buf[..want]).map_err(|e| e.to_string())?;
        if n == 0 {
            return Err("funnel plan ended early".into());
        }
        output.write_all(&buf[..n]).map_err(|e| e.to_string())?;
        left -= n as u64;
    }
    let mut last = [0u8; 1];
    input.read_exact(&mut last).map_err(|e| e.to_string())?;
    if last[0] != b'}' {
        return Err("funnel plan did not end on an object".into());
    }
    write!(output, ",\"planHash\":\"{digest}\"}}").map_err(|e| e.to_string())?;
    output.sync_all().map_err(|e| e.to_string())?;
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::rename(&tmp, out).map_err(|e| e.to_string())
}

fn morning_shape(spec: &Spec, species: usize) -> bool {
    spec.dex.len() == species
        && spec.groups_a == FALLBACK_GROUPS
        && spec.groups_b == MORNING_GROUPS_B as usize
        && spec.groups_c == MORNING_GROUPS_C as usize
        && spec.seeds_a.len() == MORNING_SEEDS_A as usize
        && spec.seeds_b.len() == MORNING_SEEDS_B as usize
        && spec.seeds_c.len() == MORNING_SEEDS_C as usize
        && spec.seeds_d.len() == MORNING_SEEDS_D as usize
}

fn write_plan(data: &Data, spec: &Spec, out: &str) -> Result<Value, String> {
    let width = roster(data);
    let parent = Path::new(out).parent().filter(|path| !path.as_os_str().is_empty()).unwrap_or_else(|| Path::new("."));
    fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    let token = format!("{}-{}", std::process::id(), out.len());
    let tasks_path = parent.join(format!(".funnel-tasks-{token}.part"));
    let strata_path = parent.join(format!(".funnel-strata-{token}.part"));
    let unsigned_path = parent.join(format!(".funnel-unsigned-{token}.part"));
    let _cleanup = PartGuard { paths: vec![tasks_path.clone(), strata_path.clone(), unsigned_path.clone()] };
    let mut tasks_file = File::create(&tasks_path).map_err(|e| e.to_string())?;
    let mut strata_file = File::create(&strata_path).map_err(|e| e.to_string())?;
    let mut task_started = false;
    let mut strata_started = false;
    let mut controls = Vec::new();
    let mut control_configs = Vec::new();
    let mut unavailable = Vec::new();
    let mut stage_a_tasks = 0u64;
    let mut stage_b_upper = 0u64;
    let mut stage_c_upper = 0u64;
    let mut stage_d_upper = 0u64;
    let mut strata_n = 0u64;
    let mut strata_full = 0u64;
    let mut strata_beam = 0u64;
    for &dex in &spec.dex {
        let base = mon(data, dex)?;
        let control = stock_control(data, base)?;
        controls.push(config_json(data, base, &control, config_proxy(data, base, &control).0)?);
        control_configs.push(control);
        let (grouped, over) = groups_for(data, base, spec, width.cap)?;
        let mut seen = BTreeSet::new();
        for ((style, branch), proposals) in &grouped {
            if proposals.is_empty() {
                continue;
            }
            seen.insert((style.clone(), branch.clone()));
            let profiles = profile_count(data, base, &proposals[0].moves, style, spec.tm_budget).unwrap_or(1);
            let n_a = proposals.len();
            let n_b = n_a.min(spec.groups_b);
            let n_c = n_b.min(spec.groups_c);
            stage_a_tasks += (n_a * spec.seeds_a.len()) as u64;
            stage_b_upper += (n_b * spec.seeds_b.len()) as u64;
            stage_c_upper += (n_c * profiles * spec.seeds_c.len()) as u64;
            stage_d_upper += spec.seeds_d.len() as u64;
            let beamed = has_key(&over, style, branch);
            if beamed {
                strata_beam += 1;
            } else {
                strata_full += 1;
            }
            let mut rows = Vec::new();
            for proposal in proposals {
                rows.push(config_json(data, base, &proposal.config, proposal.score)?);
                for &seed in &spec.seeds_a {
                    write_value(&mut tasks_file, &mut task_started, &json!({
                        "taskId": task_id(&spec.hash, &proposal.config.id, "A", seed),
                        "configurationId": proposal.config.id,
                        "stage": "A",
                        "seed": seed,
                    }))?;
                }
            }
            strata_n += 1;
            write_value(&mut strata_file, &mut strata_started, &json!({
                "dex": dex,
                "style": style,
                "branch": branch,
                "search": if beamed { "beam" } else { "full" },
                "profilesPerGroup": profiles,
                "candidates": rows,
            }))?;
        }
        for style in ["melee", "ranged"] {
            for branch in ["optimized_no_tm", "optimized_tm"] {
                if seen.contains(&(style.into(), branch.into())) {
                    continue;
                }
                let reason = if branch == "optimized_tm" && base.tms.is_empty() {
                    "species has no legal TM"
                } else if spec.tm_budget.is_some() && branch == "optimized_tm" {
                    "tm budget or the move beam left no base-role group"
                } else if has_key(&over, style, branch) {
                    "prior shortlist left no base-role group"
                } else {
                    "no legal base-role group"
                };
                unavailable.push(json!({"dex": dex, "variantId": format!("{style}:base:{branch}"), "reason": reason}));
                for role in ["aggro", "coverage", "both"] {
                    unavailable.push(json!({
                        "dex": dex,
                        "variantId": format!("{style}:{role}:{branch}"),
                        "reason": "funnel v1 measures the base role only",
                    }));
                }
            }
        }
        for (style, branch) in &seen {
            for role in ["aggro", "coverage", "both"] {
                unavailable.push(json!({
                    "dex": dex,
                    "variantId": format!("{style}:{role}:{branch}"),
                    "reason": "funnel v1 measures the base role only",
                }));
            }
        }
    }
    for control in &control_configs {
        for seed in spec.seeds_a.iter().chain(&spec.seeds_b).chain(&spec.seeds_d) {
            let stage = if spec.seeds_d.contains(seed) {
                "D"
            } else if spec.seeds_b.contains(seed) {
                "B"
            } else {
                "A"
            };
            write_value(&mut tasks_file, &mut task_started, &json!({
                "taskId": task_id(&spec.hash, &control.id, stage, *seed),
                "configurationId": control.id,
                "stage": stage,
                "seed": *seed,
            }))?;
        }
    }
    tasks_file.sync_all().map_err(|e| e.to_string())?;
    strata_file.sync_all().map_err(|e| e.to_string())?;
    drop(tasks_file);
    drop(strata_file);
    let control_tasks = spec.dex.len() as u64 * (spec.seeds_a.len() + spec.seeds_b.len() + spec.seeds_d.len()) as u64;
    let mut recall_tasks = 0u64;
    let mut recall_detail = Vec::new();
    for &dex in &spec.recall {
        let rows = tally_species(data, mon(data, dex)?);
        let groups = rows.iter().map(|row| row.groups as u64).sum::<u64>();
        let screen = groups * 4;
        let confirm = rows.iter().map(|row| (row.groups as u64).min(50) * spec.seeds_d.len() as u64).sum::<u64>();
        recall_tasks += screen + confirm;
        recall_detail.push(json!({"dex": dex, "groups": groups, "screeningTasks": screen, "confirmationUpper": confirm}));
    }
    let tasks_upper = stage_a_tasks + stage_b_upper + stage_c_upper + stage_d_upper + control_tasks + recall_tasks;
    if tasks_upper > spec.max_matches {
        return Err(format!("funnel ceiling {tasks_upper} exceeds maxMatches"));
    }
    if morning_shape(spec, data.dex.len()) && tasks_upper > MATCH_CEILING {
        return Err(format!(
            "funnel ceiling {tasks_upper} exceeds the measured 2.5 h budget {MATCH_CEILING} at cap {}",
            width.cap
        ));
    }
    let counts = json!({
        "stageA": stage_a_tasks,
        "stageBUpper": stage_b_upper,
        "stageCUpper": stage_c_upper,
        "stageDUpper": stage_d_upper,
        "controlTasks": control_tasks,
        "recallTasksUpper": recall_tasks,
        "tasksUpperBound": tasks_upper,
        "strata": strata_n,
        "strataFull": strata_full,
        "strataBeam": strata_beam,
        "species": spec.dex.len(),
        "fullGroupCap": width.cap,
        "matchCeiling": MATCH_CEILING,
        "rosterTasksUpper": width.tasks,
        "rosterStageA": width.stage_a,
        "rosterStrataFull": width.full_strata,
        "rosterStrataBeam": width.beam_strata,
        "rosterEnumeratedGroups": width.enumerated_groups,
        "rosterBeamedGroups": width.beamed_groups,
        "rosterRecallTasks": width.recall_tasks,
    });
    let mut sink = Sink { inner: File::create(&unsigned_path).map_err(|e| e.to_string())?, hash: Sha256::new() };
    sink.push(b"{")?;
    let mut started = false;
    push_field(&mut sink, &mut started, "controls", &Value::Array(controls))?;
    push_field(&mut sink, &mut started, "counts", &counts)?;
    push_field(&mut sink, &mut started, "engineFingerprint", &json!(research::fingerprint()))?;
    push_field(&mut sink, &mut started, "gameCommit", &json!(research::GAME_COMMIT))?;
    push_field(&mut sink, &mut started, "kind", &json!("funnel"))?;
    if started {
        sink.push(b",")?;
    }
    sink.push(b"\"ledger\":{\"stageATasks\":[")?;
    copy_into(&mut sink, &tasks_path)?;
    sink.push(b"]}")?;
    started = true;
    push_field(&mut sink, &mut started, "manifest", &spec.raw)?;
    push_field(&mut sink, &mut started, "manifestHash", &json!(spec.hash))?;
    push_field(&mut sink, &mut started, "marginFraction", &json!(MARGIN))?;
    push_field(&mut sink, &mut started, "policyVersion", &json!(POLICY))?;
    push_field(&mut sink, &mut started, "rankingReady", &json!(false))?;
    push_field(&mut sink, &mut started, "recall", &Value::Array(recall_detail))?;
    push_field(&mut sink, &mut started, "rustc", &json!(compiler_version()))?;
    push_field(&mut sink, &mut started, "schema", &json!(1))?;
    if started {
        sink.push(b",")?;
    }
    sink.push(b"\"strata\":[")?;
    copy_into(&mut sink, &strata_path)?;
    sink.push(b"]")?;
    started = true;
    push_field(&mut sink, &mut started, "unavailable", &Value::Array(unavailable))?;
    sink.push(b"}")?;
    let digest = sink.finish()?;
    seal_plan(&unsigned_path, Path::new(out), &digest)?;
    Ok(counts)
}

struct Lock {
    path: PathBuf,
    _file: File,
}

impl Lock {
    fn acquire(path: PathBuf) -> Result<Self, String> {
        Self::acquire_once(path, true)
    }

    fn acquire_once(path: PathBuf, retry: bool) -> Result<Self, String> {
        match OpenOptions::new().write(true).create_new(true).open(&path) {
            Ok(mut file) => {
                let _ = writeln!(file, "{}", std::process::id());
                Ok(Self { path, _file: file })
            }
            Err(_) => {
                let pid = fs::read_to_string(&path).ok().and_then(|text| text.trim().parse::<u32>().ok());
                let stale = pid.is_none_or(|pid| !Path::new(&format!("/proc/{pid}")).exists());
                if stale && retry && fs::remove_file(&path).is_ok() {
                    return Self::acquire_once(path, false);
                }
                Err("funnel cache is locked by a live process".into())
            }
        }
    }
}

impl Drop for Lock {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.path);
    }
}

fn load_plan(data: &Data, path: &str) -> Result<(Value, Spec, HashMap<String, Configuration>), String> {
    let plan: Value = serde_json::from_slice(&fs::read(path).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    if plan["kind"] != "funnel" || plan["engineFingerprint"].as_str() != Some(research::fingerprint().as_str()) {
        return Err("funnel plan does not match this engine".into());
    }
    if plan["rustc"].as_str() != Some(compiler_version().as_str()) {
        return Err("funnel plan rustc does not match this compiler".into());
    }
    let mut unsigned = plan.clone();
    unsigned.as_object_mut().ok_or("plan")?.remove("planHash");
    if plan["planHash"].as_str() != Some(hash_value(&unsigned).as_str()) {
        return Err("funnel plan hash mismatch".into());
    }
    let spec = parse_spec(data, plan["manifest"].clone())?;
    let mut configs = HashMap::new();
    for row in plan["controls"].as_array().into_iter().flatten() {
        let config = config_from_json(row)?;
        configs.insert(config.id.clone(), config);
    }
    for stratum in plan["strata"].as_array().into_iter().flatten() {
        for row in stratum["candidates"].as_array().into_iter().flatten() {
            let config = config_from_json(row)?;
            configs.insert(config.id.clone(), config);
        }
    }
    Ok((plan, spec, configs))
}

fn cached(cache: &Path, task_id: &str) -> Option<Value> {
    let path = cache.join(format!("{task_id}.json"));
    let bytes = fs::read(path).ok()?;
    serde_json::from_slice(&bytes).ok()
}

fn run_tasks(
    data: &Data,
    tables: &Tables,
    pool: &rayon::ThreadPool,
    cache: &Path,
    configs: &HashMap<String, Configuration>,
    tasks: &[&Value],
    seconds: f64,
    started: Instant,
    max_wall: f64,
    max_failed: u32,
    stage: &str,
) -> Result<(), String> {
    let pending = tasks
        .iter()
        .filter(|task| cached(cache, task["taskId"].as_str().unwrap_or("")).is_none())
        .copied()
        .collect::<Vec<_>>();
    let batch = pool.current_num_threads().max(1) * 8;
    let mut cursor = 0;
    let mut failures = 0u32;
    while cursor < pending.len() {
        if started.elapsed().as_secs_f64() >= max_wall {
            eprintln!("funnel wall reached during stage {stage} with {} tasks left", pending.len() - cursor);
            return Ok(());
        }
        let end = (cursor + batch).min(pending.len());
        let slice = &pending[cursor..end];
        let rows = pool.install(|| {
            slice
                .par_iter()
                .map(|task| {
                    let id = task["configurationId"].as_str().unwrap_or("");
                    let config = configs.get(id).ok_or_else(|| format!("missing config {id}"))?;
                    let seed = task["seed"].as_u64().ok_or("seed")? as u32;
                    let row = run_configuration(data, tables, config, seed, seconds)?;
                    let record = json!({
                        "taskId": task["taskId"],
                        "configurationId": id,
                        "stage": task["stage"],
                        "seed": seed,
                        "row": row,
                    });
                    atomic_json(&cache.join(format!("{}.json", task["taskId"].as_str().unwrap_or("x"))), &record)?;
                    Ok::<(), String>(())
                })
                .collect::<Vec<_>>()
        });
        for result in rows {
            if let Err(error) = result {
                failures += 1;
                eprintln!("funnel task failed: {error}");
                if failures > max_failed {
                    return Err(format!("{failures} failed tasks"));
                }
            }
        }
        cursor = end;
        eprintln!("funnel stage {stage} checkpoint {}/{}", cursor, pending.len());
    }
    Ok(())
}

type MetricIndex = HashMap<String, HashMap<u32, Value>>;

fn metric_index(cache: &Path, tasks: &[Value]) -> MetricIndex {
    let mut out: MetricIndex = HashMap::new();
    for task in tasks {
        let Some(id) = task["configurationId"].as_str() else { continue };
        let Some(seed) = task["seed"].as_u64() else { continue };
        let Some(row) = cached(cache, task["taskId"].as_str().unwrap_or("")) else { continue };
        out.entry(id.to_string()).or_default().insert(seed as u32, row["row"]["metrics"].clone());
    }
    out
}

fn overlay(mut base: HashMap<u32, Value>, over: &HashMap<u32, Value>) -> HashMap<u32, Value> {
    for (seed, metrics) in over {
        base.insert(*seed, metrics.clone());
    }
    base
}

fn paired(candidate: &HashMap<u32, Value>, control: &HashMap<u32, Value>, seeds: &[u32]) -> Option<[Vec<f64>; 4]> {
    let mut ds = [Vec::new(), Vec::new(), Vec::new(), Vec::new()];
    for seed in seeds {
        let (Some(a), Some(b)) = (candidate.get(seed), control.get(seed)) else {
            continue;
        };
        let ae = normalized_exposure(a);
        let be = normalized_exposure(b);
        ds[0].push(a["survivalSeconds"].as_f64().unwrap_or(0.) - b["survivalSeconds"].as_f64().unwrap_or(0.));
        ds[1].push(ae[0] - be[0]);
        ds[2].push(ae[1] - be[1]);
        ds[3].push(ae[2] - be[2]);
    }
    if ds[0].is_empty() { None } else { Some(ds) }
}

fn control_means(control: &HashMap<u32, Value>, seeds: &[u32]) -> [f64; 4] {
    let mut acc = [0.; 4];
    let mut n = 0.0;
    for seed in seeds {
        let Some(m) = control.get(seed) else { continue };
        let e = normalized_exposure(m);
        acc[0] += m["survivalSeconds"].as_f64().unwrap_or(0.);
        acc[1] += e[0];
        acc[2] += e[1];
        acc[3] += e[2];
        n += 1.;
    }
    if n == 0. { return [0.; 4]; }
    acc.map(|x| x / n)
}

fn passes(ds: &[Vec<f64>; 4], control_mean: [f64; 4], fraction: f64) -> bool {
    if ds[0].len() < 2 {
        return false;
    }
    let intervals = ds.iter().map(|xs| paired_interval(xs)).collect::<Vec<_>>();
    let survival = intervals[0]["lower"].as_f64().unwrap_or(f64::MIN);
    let exposure_ok = (1..4).all(|i| {
        intervals[i]["upper"].as_f64().unwrap_or(f64::MAX) <= fraction * control_mean[i].max(0.)
    });
    survival >= -fraction * control_mean[0].max(0.) && exposure_ok
}

fn mean_survival(ds: &[Vec<f64>; 4]) -> f64 {
    ds[0].iter().sum::<f64>() / ds[0].len().max(1) as f64
}

fn execute(data: &Data, plan_path: &str, cache_dir: &str, out: &str) -> Result<(), String> {
    let (plan, spec, mut configs) = load_plan(data, plan_path)?;
    let cache = PathBuf::from(cache_dir);
    fs::create_dir_all(&cache).map_err(|e| e.to_string())?;
    let _lock = Lock::acquire(cache.join(".funnel.lock"))?;
    let started = Instant::now();
    let pool = rayon::ThreadPoolBuilder::new().num_threads(spec.threads).build().map_err(|e| e.to_string())?;
    let tables = Tables::new();
    let stage_a = plan["ledger"]["stageATasks"].as_array().cloned().unwrap_or_default();
    let refs = stage_a.iter().collect::<Vec<_>>();
    run_tasks(data, &tables, &pool, &cache, &configs, &refs, spec.seconds, started, spec.max_wall, spec.max_failed, "A")?;
    if started.elapsed().as_secs_f64() >= spec.max_wall {
        return write_partial(&plan, &spec, &cache, out, started, "A");
    }
    let index_a = metric_index(&cache, &stage_a);
    let empty = HashMap::new();
    let mut stage_b_tasks = Vec::new();
    let mut promoted: BTreeMap<(u32, String, String), Vec<String>> = BTreeMap::new();
    for stratum in plan["strata"].as_array().into_iter().flatten() {
        let dex = stratum["dex"].as_u64().unwrap_or(0) as u32;
        let style = stratum["style"].as_str().unwrap_or("");
        let branch = stratum["branch"].as_str().unwrap_or("");
        let control_id = configs.values().find(|c| c.dex == dex && c.id.contains("|branch:control_no_tm|")).map(|c| c.id.clone());
        let control_rows = control_id.as_deref().and_then(|id| index_a.get(id)).unwrap_or(&empty);
        let mut ranked = Vec::new();
        for candidate in stratum["candidates"].as_array().into_iter().flatten() {
            let id = candidate["id"].as_str().unwrap_or("");
            let mine = index_a.get(id).unwrap_or(&empty);
            if let Some(ds) = paired(mine, control_rows, &spec.seeds_a) {
                ranked.push((mean_survival(&ds), id.to_string()));
            }
        }
        ranked.sort_by(|a, b| b.0.total_cmp(&a.0).then_with(|| a.1.cmp(&b.1)));
        let chosen = ranked.into_iter().take(spec.groups_b).map(|(_, id)| id).collect::<Vec<_>>();
        for id in &chosen {
            for &seed in &spec.seeds_b {
                stage_b_tasks.push(json!({
                    "taskId": task_id(&spec.hash, id, "B", seed),
                    "configurationId": id,
                    "stage": "B",
                    "seed": seed,
                }));
            }
        }
        promoted.insert((dex, style.into(), branch.into()), chosen);
    }
    let refs = stage_b_tasks.iter().collect::<Vec<_>>();
    run_tasks(data, &tables, &pool, &cache, &configs, &refs, spec.seconds, started, spec.max_wall, spec.max_failed, "B")?;
    if started.elapsed().as_secs_f64() >= spec.max_wall {
        return write_partial(&plan, &spec, &cache, out, started, "B");
    }
    let index_b = metric_index(&cache, &stage_b_tasks);
    let mut stage_c_tasks = Vec::new();
    let mut stage_c_ids: BTreeMap<(u32, String, String), Vec<String>> = BTreeMap::new();
    for ((dex, style, branch), ids) in &promoted {
        let base = mon(data, *dex)?;
        let control_id = configs.values().find(|c| c.dex == *dex && c.id.contains("|branch:control_no_tm|")).map(|c| c.id.clone());
        let control_rows = control_id.as_deref().map(|id| {
            overlay(index_b.get(id).cloned().unwrap_or_default(), index_a.get(id).unwrap_or(&empty))
        }).unwrap_or_default();
        let mut ranked = Vec::new();
        for id in ids {
            let mine = index_b.get(id).unwrap_or(&empty);
            if let Some(ds) = paired(mine, &control_rows, &spec.seeds_b) {
                ranked.push((mean_survival(&ds), id.clone()));
            }
        }
        ranked.sort_by(|a, b| b.0.total_cmp(&a.0).then_with(|| a.1.cmp(&b.1)));
        let mut expanded = Vec::new();
        for (_, id) in ranked.into_iter().take(spec.groups_c) {
            let Some(sample) = configs.get(&id) else { continue };
            let moves = sample.moves.clone();
            let cfgs = selection::configurations(data, *dex, &[moves], style_from(style)?, CombatRole::Base)?;
            for config in cfgs {
                if !within_budget(data, base, &config, spec.tm_budget) {
                    continue;
                }
                for &seed in &spec.seeds_c {
                    stage_c_tasks.push(json!({
                        "taskId": task_id(&spec.hash, &config.id, "C", seed),
                        "configurationId": config.id,
                        "stage": "C",
                        "seed": seed,
                    }));
                }
                expanded.push(config.id.clone());
                configs.insert(config.id.clone(), config);
            }
        }
        stage_c_ids.insert((*dex, style.clone(), branch.clone()), expanded);
    }
    let refs = stage_c_tasks.iter().collect::<Vec<_>>();
    run_tasks(data, &tables, &pool, &cache, &configs, &refs, spec.seconds, started, spec.max_wall, spec.max_failed, "C")?;
    if started.elapsed().as_secs_f64() >= spec.max_wall {
        return write_partial(&plan, &spec, &cache, out, started, "C");
    }
    let index_c = metric_index(&cache, &stage_c_tasks);
    let mut stage_d_tasks = Vec::new();
    let mut chosen_d: BTreeMap<(u32, String, String), String> = BTreeMap::new();
    for ((dex, style, branch), ids) in &stage_c_ids {
        let control_id = configs.values().find(|c| c.dex == *dex && c.id.contains("|branch:control_no_tm|")).map(|c| c.id.clone());
        let control_rows = control_id.as_deref().and_then(|id| index_a.get(id)).unwrap_or(&empty);
        let means = control_means(control_rows, &spec.seeds_c);
        let mut ranked = Vec::new();
        for id in ids {
            let mine = index_c.get(id).unwrap_or(&empty);
            if let Some(ds) = paired(mine, control_rows, &spec.seeds_c) {
                ranked.push((passes(&ds, means, MARGIN), mean_survival(&ds), id.clone()));
            }
        }
        ranked.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| b.1.total_cmp(&a.1)).then_with(|| a.2.cmp(&b.2)));
        if let Some((_, _, id)) = ranked.first() {
            for &seed in &spec.seeds_d {
                stage_d_tasks.push(json!({
                    "taskId": task_id(&spec.hash, id, "D", seed),
                    "configurationId": id,
                    "stage": "D",
                    "seed": seed,
                }));
            }
            chosen_d.insert((*dex, style.clone(), branch.clone()), id.clone());
        }
    }
    let refs = stage_d_tasks.iter().collect::<Vec<_>>();
    run_tasks(data, &tables, &pool, &cache, &configs, &refs, spec.seconds, started, spec.max_wall, spec.max_failed, "D")?;
    let complete = stage_d_tasks.iter().all(|task| cached(&cache, task["taskId"].as_str().unwrap_or("")).is_some())
        && stage_a.iter().filter(|task| task["stage"] == "D" || spec.seeds_d.contains(&(task["seed"].as_u64().unwrap_or(0) as u32))).all(|task| cached(&cache, task["taskId"].as_str().unwrap_or("")).is_some());
    write_results(data, &plan, &spec, &cache, &configs, &index_a, &stage_d_tasks, &chosen_d, out, started, complete)
}

fn write_partial(plan: &Value, spec: &Spec, cache: &Path, out: &str, started: Instant, stage: &str) -> Result<(), String> {
    let done = fs::read_dir(cache).map(|rd| rd.filter(|e| e.as_ref().ok().is_some_and(|e| e.path().extension().is_some_and(|x| x == "json"))).count()).unwrap_or(0);
    let value = json!({
        "schema": 1,
        "kind": "funnel-results",
        "complete": false,
        "stage": stage,
        "rankingReady": false,
        "missingTasks": 1,
        "completedTasks": done,
        "elapsedWallSeconds": started.elapsed().as_secs_f64(),
        "planHash": plan["planHash"],
        "engineFingerprint": research::fingerprint(),
        "gameCommit": research::GAME_COMMIT,
        "policyVersion": POLICY,
        "threads": spec.threads,
    });
    atomic_json(Path::new(out), &value)
}

fn absolute_mean(rows: &HashMap<u32, Value>, seeds: &[u32], key: &str) -> f64 {
    let xs = seeds.iter().filter_map(|s| rows.get(s)).filter_map(|m| m[key].as_f64()).collect::<Vec<_>>();
    if xs.is_empty() { 0. } else { xs.iter().sum::<f64>() / xs.len() as f64 }
}

fn write_results(
    data: &Data,
    plan: &Value,
    spec: &Spec,
    cache: &Path,
    configs: &HashMap<String, Configuration>,
    index_a: &MetricIndex,
    stage_d: &[Value],
    chosen: &BTreeMap<(u32, String, String), String>,
    out: &str,
    started: Instant,
    complete: bool,
) -> Result<(), String> {
    let index_d = metric_index(cache, stage_d);
    let empty = HashMap::new();
    let mut winners = Vec::new();
    let mut rates = [0u64; 3];
    let mut strata_n = 0u64;
    for ((dex, style, branch), id) in chosen {
        let Some(config) = configs.get(id) else { continue };
        let Some(base) = data.dex.iter().find(|m| m.dex == *dex) else { continue };
        let control = configs.values().find(|c| c.dex == *dex && c.id.contains("|branch:control_no_tm|"));
        let mine = index_d.get(id).unwrap_or(&empty);
        let control_rows = control.and_then(|c| index_a.get(&c.id)).unwrap_or(&empty);
        let Some(ds) = paired(&mine, &control_rows, &spec.seeds_d) else { continue };
        let means = control_means(&control_rows, &spec.seeds_d);
        strata_n += 1;
        for (i, fraction) in [0.0, 0.05, 0.10].into_iter().enumerate() {
            if !passes(&ds, means, fraction) {
                rates[i] += 1;
            }
        }
        let safe = passes(&ds, means, MARGIN);
        let intervals = ds.iter().map(|xs| paired_interval(xs)).collect::<Vec<_>>();
        let status = if ds[0].len() < 2 {
            "inconclusive"
        } else if safe {
            "best_observed"
        } else {
            "no_safe_candidate"
        };
        let tm_cost = taught_tm_cost(data, base, &config.tms).unwrap_or(0);
        winners.push(json!({
            "dex": dex,
            "variantId": format!("{style}:base:{branch}"),
            "status": status,
            "winnerConfirmed": safe && ds[0].len() >= 2,
            "configurationId": id,
            "configuration": {
                "id": id,
                "group": config.moves,
                "tms": config.tms,
                "tmCost": tm_cost,
                "secondStart": config.second,
                "nature": config.nature,
                "ability": config.ability,
                "natureEquivalence": config.nature_equivalence,
                "build": style,
                "role": "base",
                "branch": branch,
            },
            "meanSurvival": absolute_mean(&mine, &spec.seeds_d, "survivalSeconds"),
            "ci95": intervals[0],
            "seeds": spec.seeds_d,
            "exposure": {
                "contactDamagePerMinute": intervals[1],
                "contactFraction": intervals[2],
                "trappedFraction": intervals[3],
            },
            "safe": safe,
            "fingerprint": research::fingerprint(),
            "pairedConfirmation": {
                "n": ds[0].len(),
                "survivalSeconds": intervals[0],
                "contactDamagePerMinute": intervals[1],
                "contactFraction": intervals[2],
                "trappedFraction": intervals[3],
                "meanDelta": {
                    "survivalSeconds": mean_survival(&ds),
                    "contactDamagePerMinute": ds[1].iter().sum::<f64>() / ds[1].len().max(1) as f64,
                    "contactFraction": ds[2].iter().sum::<f64>() / ds[2].len().max(1) as f64,
                    "trappedFraction": ds[3].iter().sum::<f64>() / ds[3].len().max(1) as f64,
                },
            },
        }));
    }
    let mut controls = Vec::new();
    let control_ids = configs
        .values()
        .filter(|config| config.id.contains("|branch:control_no_tm|"))
        .map(|config| config.id.clone())
        .collect::<Vec<_>>();
    for id in control_ids {
        let Some(config) = configs.get(&id) else { continue };
        let Some(base) = data.dex.iter().find(|mon| mon.dex == config.dex) else { continue };
        let mine = index_a.get(&id).unwrap_or(&empty);
        let lives = spec
            .seeds_d
            .iter()
            .filter_map(|seed| mine.get(seed))
            .filter_map(|metrics| metrics["survivalSeconds"].as_f64())
            .collect::<Vec<_>>();
        if lives.len() < 2 {
            continue;
        }
        controls.push(json!({
            "dex": config.dex,
            "meanSurvival": lives.iter().sum::<f64>() / lives.len() as f64,
            "ci95": paired_interval(&lives),
            "seeds": spec.seeds_d,
            "fingerprint": research::fingerprint(),
            "configuration": {
                "id": id,
                "group": config.moves,
                "tms": config.tms,
                "tmCost": taught_tm_cost(data, base, &config.tms).unwrap_or(0),
                "secondStart": config.second,
                "nature": config.nature,
                "ability": config.ability,
                "build": style_name(&config.style),
                "role": "base",
                "branch": "control_no_tm",
            },
        }));
    }
    let completed = fs::read_dir(cache).map(|rd| rd.filter(|e| e.as_ref().ok().is_some_and(|e| e.path().extension().is_some_and(|x| x == "json"))).count()).unwrap_or(0);
    let value = json!({
        "schema": 1,
        "kind": "funnel-results",
        "complete": complete,
        "rankingReady": false,
        "missingTasks": if complete { 0 } else { 1 },
        "completedTasks": completed,
        "elapsedWallSeconds": started.elapsed().as_secs_f64(),
        "threads": spec.threads,
        "failureCount": 0,
        "planHash": plan["planHash"],
        "manifestHash": spec.hash,
        "policyVersion": POLICY,
        "policyHash": hash_value(&spec.raw),
        "gameCommit": research::GAME_COMMIT,
        "engineFingerprint": research::fingerprint(),
        "seedSets": {"screening": spec.seeds_a.iter().chain(&spec.seeds_b).chain(&spec.seeds_c).copied().collect::<BTreeSet<_>>(), "confirmation": spec.seeds_d},
        "winners": winners,
        "controls": controls,
        "unavailable": plan["unavailable"],
        "noSafeCandidate": {
            "strata": strata_n,
            "at0": rates[0],
            "at5": rates[1],
            "at10": rates[2],
        },
        "counts": plan["counts"],
    });
    atomic_json(Path::new(out), &value)
}

fn write_report(results_path: &str, report_path: &str, recall_path: Option<&str>) -> Result<(), String> {
    let results: Value = serde_json::from_slice(&fs::read(results_path).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    let recall = recall_path.and_then(|path| fs::read(path).ok()).and_then(|bytes| serde_json::from_slice::<Value>(&bytes).ok());
    let mut text = String::new();
    match &recall {
        Some(doc) if doc["ok"] == true => {
            let failed = doc["rows"].as_array().into_iter().flatten().filter(|row| row["pass"] != true).count();
            let total = doc["rows"].as_array().map(Vec::len).unwrap_or(0);
            text.push_str(&format!("Recall: {failed} of {total} style/branch rows failed the 5% gap.\n\n"));
        }
        _ => text.push_str("Recall failed or was not run. The funnel rows below are not a recall verdict.\n\n"),
    }
    text.push_str("The funnel keeps four builds when a species has a legal TM, and two when it does not. Ranking ready stays false.\n\n");
    let rates = &results["noSafeCandidate"];
    let strata = rates["strata"].as_u64().unwrap_or(0).max(1);
    text.push_str(&format!(
        "no_safe_candidate rate at 0%: {:.1}%. At 5%: {:.1}%. At 10%: {:.1}%. Strata in this file: {}.\n\n",
        100.0 * rates["at0"].as_u64().unwrap_or(0) as f64 / strata as f64,
        100.0 * rates["at5"].as_u64().unwrap_or(0) as f64 / strata as f64,
        100.0 * rates["at10"].as_u64().unwrap_or(0) as f64 / strata as f64,
        rates["strata"].as_u64().unwrap_or(0),
    ));
    text.push_str("dex | style | branch | nature | ability | tmCost | mean survival | CI95 | safe\n");
    for winner in results["winners"].as_array().into_iter().flatten() {
        let config = &winner["configuration"];
        text.push_str(&format!(
            "{} | {} | {} | {} | {} | {} | {:.1} | {} | {}\n",
            winner["dex"].as_u64().unwrap_or(0),
            config["build"].as_str().unwrap_or(""),
            config["branch"].as_str().unwrap_or(""),
            config["nature"].as_str().unwrap_or(""),
            config["ability"].as_str().unwrap_or("none"),
            config["tmCost"].as_u64().unwrap_or(0),
            winner["meanSurvival"].as_f64().unwrap_or(0.),
            winner["ci95"],
            winner["safe"].as_bool().unwrap_or(false),
        ));
    }
    if let Some(doc) = recall.filter(|doc| doc["ok"] == true) {
        text.push_str("\nRecall rows\n");
        for row in doc["rows"].as_array().into_iter().flatten() {
            text.push_str(&format!(
                "dex {} {} {}: rank {} gap upper {} pass {}\n",
                row["dex"].as_u64().unwrap_or(0),
                row["style"].as_str().unwrap_or(""),
                row["branch"].as_str().unwrap_or(""),
                row["rank"].as_str().unwrap_or("absent"),
                row["gapUpper"].as_f64().unwrap_or(f64::NAN),
                row["pass"].as_bool().unwrap_or(false),
            ));
        }
    }
    if let Some(parent) = Path::new(report_path).parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    fs::write(report_path, text).map_err(|e| e.to_string())
}

pub(crate) fn gap_passes(deltas: &[f64], real_mean: f64) -> (f64, bool) {
    let interval = paired_interval(deltas);
    let upper = interval["upper"].as_f64().unwrap_or(f64::MAX);
    (upper, deltas.len() >= 2 && upper <= 0.05 * real_mean.max(0.))
}

fn recall_one(data: &Data, dex: u32, cache: &Path, threads: usize, seconds: f64) -> Result<Vec<Value>, String> {
    let base = mon(data, dex)?;
    let groups = legal_groups(data, base);
    let ability = default_ability(base);
    let mut proposals = Vec::new();
    for group in &groups {
        let Some(style) = style_of_group(data, group) else { continue };
        let branch = branch_of(data, base, group);
        let config = build_config(data, base, group, "hardy", ability.clone(), style, branch)?;
        let (score, _, _) = config_proxy(data, base, &config);
        proposals.push((score, style.to_string(), branch.to_string(), config));
    }
    let pool = rayon::ThreadPoolBuilder::new().num_threads(threads).build().map_err(|e| e.to_string())?;
    let tables = Tables::new();
    let seeds_a = (1001..=1004).collect::<Vec<_>>();
    let seeds_d = (3001..=3032).collect::<Vec<_>>();
    let tasks = proposals.iter().flat_map(|(_, _, _, config)| {
        seeds_a.iter().copied().map(|seed| (config.clone(), seed, "recall-a"))
    }).collect::<Vec<_>>();
    pool.install(|| {
        tasks.par_iter().for_each(|(config, seed, stage)| {
            let id = task_id("recall", &config.id, stage, *seed);
            if cached(cache, &id).is_some() {
                return;
            }
            if let Ok(row) = run_configuration(data, &tables, config, *seed, seconds) {
                let record = json!({"taskId": id, "configurationId": config.id, "stage": stage, "seed": seed, "row": row});
                let _ = atomic_json(&cache.join(format!("{id}.json")), &record);
            }
        });
    });
    let mut by_key: BTreeMap<(String, String), Vec<(f64, String, f64)>> = BTreeMap::new();
    for (score, style, branch, config) in &proposals {
        let mut lives = Vec::new();
        for seed in &seeds_a {
            let id = task_id("recall", &config.id, "recall-a", *seed);
            if let Some(row) = cached(cache, &id) {
                lives.push(row["row"]["metrics"]["survivalSeconds"].as_f64().unwrap_or(0.));
            }
        }
        if lives.len() == seeds_a.len() {
            let mean = lives.iter().sum::<f64>() / lives.len() as f64;
            by_key.entry((style.clone(), branch.clone())).or_default().push((*score, config.id.clone(), mean));
        }
    }
    let mut rows = Vec::new();
    let mut confirm = Vec::new();
    for ((style, branch), mut list) in by_key {
        list.sort_by(|a, b| b.2.total_cmp(&a.2).then_with(|| a.1.cmp(&b.1)));
        let real_id = list.first().map(|row| row.1.clone());
        let mut by_prior = list.clone();
        by_prior.sort_by(|a, b| b.0.total_cmp(&a.0).then_with(|| a.1.cmp(&b.1)));
        let shortlist = if list.len() <= roster(data).cap {
            by_prior.iter().map(|row| row.1.clone()).collect::<Vec<_>>()
        } else {
            by_prior.iter().take(FALLBACK_GROUPS).map(|row| row.1.clone()).collect::<Vec<_>>()
        };
        let funnel_id = list.iter().filter(|row| shortlist.contains(&row.1)).max_by(|a, b| a.2.total_cmp(&b.2)).map(|row| row.1.clone());
        let rank = real_id.as_ref().and_then(|id| shortlist.iter().position(|x| x == id).map(|i| i + 1));
        let mut confirm_ids = list.iter().take(50).map(|row| row.1.clone()).collect::<Vec<_>>();
        if let Some(id) = &funnel_id {
            if !confirm_ids.iter().any(|existing| existing == id) {
                confirm_ids.push(id.clone());
            }
        }
        for id in &confirm_ids {
            let config = proposals.iter().find(|row| row.3.id == *id).map(|row| row.3.clone());
            if let Some(config) = config {
                for seed in &seeds_d {
                    confirm.push((config.clone(), *seed));
                }
            }
        }
        rows.push(json!({
            "dex": dex,
            "style": style,
            "branch": branch,
            "rank": rank.map(|n| n.to_string()).unwrap_or_else(|| "absent".into()),
            "realId": real_id,
            "funnelId": funnel_id,
            "confirmIds": confirm_ids,
        }));
    }
    pool.install(|| {
        confirm.par_iter().for_each(|(config, seed)| {
            let id = task_id("recall", &config.id, "recall-d", *seed);
            if cached(cache, &id).is_some() {
                return;
            }
            if let Ok(row) = run_configuration(data, &tables, config, *seed, seconds) {
                let record = json!({"taskId": id, "configurationId": config.id, "stage": "recall-d", "seed": seed, "row": row});
                let _ = atomic_json(&cache.join(format!("{id}.json")), &record);
            }
        });
    });
    for row in &mut rows {
        let funnel = row["funnelId"].as_str().unwrap_or("").to_string();
        let ids = row["confirmIds"].as_array().cloned().unwrap_or_default();
        let mut best_id = String::new();
        let mut best_mean = f64::MIN;
        let mut means: HashMap<String, Vec<f64>> = HashMap::new();
        for id_value in &ids {
            let Some(id) = id_value.as_str() else { continue };
            let mut lives = Vec::new();
            for seed in &seeds_d {
                if let Some(saved) = cached(cache, &task_id("recall", id, "recall-d", *seed)) {
                    lives.push(saved["row"]["metrics"]["survivalSeconds"].as_f64().unwrap_or(0.));
                }
            }
            if lives.len() != seeds_d.len() {
                continue;
            }
            let mean = lives.iter().sum::<f64>() / lives.len() as f64;
            if mean > best_mean || (mean == best_mean && (best_id.is_empty() || id < best_id.as_str())) {
                best_mean = mean;
                best_id = id.to_string();
            }
            means.insert(id.to_string(), lives);
        }
        let mut deltas = Vec::new();
        if let (Some(real_lives), Some(funnel_lives)) = (means.get(&best_id), means.get(&funnel)) {
            for (ar, br) in real_lives.iter().zip(funnel_lives.iter()) {
                deltas.push(ar - br);
            }
        }
        let real_mean = if best_id.is_empty() { 0. } else { best_mean };
        let (upper, pass) = gap_passes(&deltas, real_mean);
        row["confirmedRealId"] = json!(best_id);
        row["gapUpper"] = json!(upper);
        row["realMean"] = json!(real_mean);
        row["pass"] = json!(pass);
        row.as_object_mut().map(|obj| obj.remove("confirmIds"));
    }
    Ok(rows)
}

fn recall(data: &Data, args: &[String]) -> Result<(), String> {
    if args.len() < 3 {
        return Err("usage: funnel recall <dex> <out.json> <cache-dir>".into());
    }
    let dex: u32 = args[0].parse().map_err(|_| "dex")?;
    let cache = PathBuf::from(&args[2]);
    fs::create_dir_all(&cache).map_err(|e| e.to_string())?;
    let _lock = Lock::acquire(cache.join(".funnel.lock"))?;
    let rows = recall_one(data, dex, &cache, std::thread::available_parallelism().map(|n| n.get()).unwrap_or(1), 900.)?;
    let doc = json!({"ok": true, "dex": dex, "rows": rows, "rankingReady": false, "engineFingerprint": research::fingerprint()});
    atomic_json(Path::new(&args[1]), &doc)?;
    println!("{}", serde_json::to_string(&doc).map_err(|e| e.to_string())?);
    Ok(())
}

fn calibrate(data: &Data, threads: usize) -> Result<(), String> {
    let base = mon(data, 133)?;
    let config = stock_control(data, base)?;
    let pool = rayon::ThreadPoolBuilder::new().num_threads(threads).build().map_err(|e| e.to_string())?;
    let tables = Tables::new();
    let seeds = (1..=200).collect::<Vec<_>>();
    let failures = AtomicU32::new(0);
    let started = Instant::now();
    pool.install(|| {
        seeds.par_iter().for_each(|seed| {
            if run_configuration(data, &tables, &config, *seed, 900.).is_err() {
                failures.fetch_add(1, Ordering::Relaxed);
            }
        });
    });
    let wall = started.elapsed().as_secs_f64();
    let failed = failures.load(Ordering::Relaxed);
    let completed = seeds.len() as u32 - failed;
    let rate = f64::from(completed) / wall;
    println!("{}", serde_json::to_string(&json!({
        "threads": threads,
        "tasks": seeds.len(),
        "failures": failed,
        "elapsedWallSeconds": wall,
        "matchesPerSecond": rate,
        "cores": std::thread::available_parallelism().map(|n| n.get()).unwrap_or(threads),
        "note": "one calibrate run of 200 full matches, stock Eevee, 900s cap",
    })).map_err(|e| e.to_string())?);
    Ok(())
}

pub fn command(data: &Data, args: &[String]) {
    let result = (|| -> Result<(), String> {
        match args.first().map(String::as_str) {
            Some("plan") if args.len() == 3 => {
                let text = fs::read_to_string(&args[1]).map_err(|e| e.to_string())?;
                let value: Value = serde_json::from_str(&text).map_err(|e| e.to_string())?;
                let spec = parse_spec(data, value)?;
                let counts = write_plan(data, &spec, &args[2])?;
                println!("{}", serde_json::to_string(&counts).map_err(|e| e.to_string())?);
                Ok(())
            }
            Some("run") | Some("resume") if args.len() == 4 => execute(data, &args[1], &args[2], &args[3]),
            Some("report") if args.len() == 3 || args.len() == 4 => {
                write_report(&args[1], &args[2], args.get(3).map(String::as_str))
            }
            Some("recall") => recall(data, &args[1..]),
            Some("calibrate") => {
                let threads = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(1);
                calibrate(data, threads)
            }
            _ => Err("usage: funnel plan <manifest.json> <plan.json> | run|resume <plan.json> <cache> <results.json> | report <results.json> <report.md> [recall.json] | recall <dex> <out.json> <cache> | calibrate [threads]".into()),
        }
    })();
    if let Err(error) = result {
        eprintln!("funnel: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn data() -> Data {
        Data::load(Path::new(env!("CARGO_MANIFEST_DIR")).join("../data/game.json").to_str().unwrap())
    }

    #[test]
    fn gap_upper_bound_uses_the_five_percent_rule() {
        let (_, pass) = gap_passes(&[1.0, 1.0, 1.0], 100.0);
        assert!(pass);
        let (upper, fail) = gap_passes(&[10.0, 10.0, 10.0], 100.0);
        assert!(!fail);
        assert!((upper - 10.0).abs() < 1e-9);
    }

    #[test]
    fn psyduck_confusion_is_a_natural_opener_and_a_tm_opener_is_charged() {
        let data = data();
        let psy = data.dex.iter().find(|m| m.dex == 54).unwrap();
        let ix = |id: &str| data.move_ix[id];
        assert_eq!(data.moves[psy.start].id, "confusion");
        assert_ne!(data.moves[psy.start].levels[0].ty, psy.types[0]);
        let ability = psy.abilities.iter().flatten().next().cloned();
        let natural = build_config(
            &data,
            psy,
            &[ix("confusion")],
            "hardy",
            ability.clone(),
            "ranged",
            "optimized_no_tm",
        )
        .unwrap();
        assert!(natural.tms.is_empty());
        assert_eq!(taught_tm_cost(&data, psy, &natural.tms).unwrap(), 0);
        let tm = build_config(
            &data,
            psy,
            &[ix("ice-beam")],
            "hardy",
            ability.clone(),
            "ranged",
            "optimized_tm",
        )
        .unwrap();
        assert_eq!(tm.tms, vec!["ice-beam".to_string()]);
        assert!(taught_tm_cost(&data, psy, &tm.tms).unwrap() > 0);
        assert!(build_config(
            &data,
            psy,
            &[ix("ice-beam")],
            "hardy",
            ability.clone(),
            "ranged",
            "optimized_no_tm",
        )
        .is_err());
        assert!(build_config(&data, psy, &[ix("ember")], "hardy", ability.clone(), "ranged", "optimized_no_tm").is_err());
        let mut confusion_lead = false;
        let mut ice_lead = false;
        let mut ember_lead = false;
        let mut tm_lead_off_branch = false;
        each_legal_group(&data, psy, &mut |group| {
            let lead = data.moves[group[0]].id.as_str();
            if lead == "confusion" {
                confusion_lead = true;
            } else if lead == "ice-beam" {
                ice_lead = true;
                if branch_of(&data, psy, group) != "optimized_tm"
                    || taught_tm_cost(&data, psy, &tm_list(&data, psy, group)).unwrap() == 0
                {
                    tm_lead_off_branch = true;
                }
            } else if lead == "ember" {
                ember_lead = true;
            }
        });
        assert!(confusion_lead);
        assert!(ice_lead);
        assert!(!ember_lead);
        assert!(!tm_lead_off_branch);
        let mut prior_ember = false;
        visit_groups(&data, psy, psy, &mut |group| {
            if data.moves[group[0]].id == "ember" {
                prior_ember = true;
            }
        });
        let taught = data
            .configure(psy, "hardy", ability.as_deref(), &["ice-beam".to_string()])
            .unwrap();
        let mut prior_ice = false;
        visit_groups(&data, psy, &taught, &mut |group| {
            if data.moves[group[0]].id == "ice-beam" {
                prior_ice = true;
            }
        });
        assert!(prior_ice);
        assert!(!prior_ember);
    }

    #[test]
    fn onix_melee_keeps_dragon_dance_on_the_tm_branch() {
        let data = data();
        let onix = data.dex.iter().find(|m| m.dex == 95).unwrap();
        let ability = default_ability(onix);
        let ix = |id: &str| data.move_ix[id];
        let config = build_config(
            &data,
            onix,
            &[ix("body-slam"), ix("dragon-dance")],
            "hardy",
            ability.clone(),
            "melee",
            "optimized_tm",
        )
        .unwrap();
        assert_eq!(config.moves[0], "body-slam");
        assert_eq!(config.tms, vec!["dragon-dance".to_string()]);
        assert!(taught_tm_cost(&data, onix, &config.tms).unwrap() > 0);
        assert!(build_config(
            &data,
            onix,
            &[ix("body-slam"), ix("dragon-dance")],
            "hardy",
            ability,
            "melee",
            "optimized_no_tm",
        )
        .is_err());
        let mut dance_lead = false;
        let mut melee_tm = false;
        each_legal_group(&data, onix, &mut |group| {
            if data.moves[group[0]].id == "dragon-dance" {
                dance_lead = true;
            }
            if style_of_group(&data, group) == Some("melee") && branch_of(&data, onix, group) == "optimized_tm" {
                melee_tm = true;
            }
        });
        assert!(melee_tm);
        assert!(!dance_lead);
        let tallies = tally_species(&data, onix);
        assert!(tallies.iter().any(|row| row.style == "melee" && row.branch == "optimized_tm" && row.groups > 0));
    }

    #[test]
    fn enumeration_keeps_the_strata_the_prior_can_reach() {
        let data = data();
        let mut missing = Vec::new();
        let mut enum_n = 0usize;
        let mut beam_n = 0usize;
        for base in &data.dex {
            let enum_keys: BTreeSet<(String, String)> = tally_species(&data, base)
                .into_iter()
                .map(|row| (row.style.to_string(), row.branch.to_string()))
                .collect();
            enum_n += enum_keys.len();
            let ability = default_ability(base);
            let mut taught = base.tms.iter().map(|&ix| data.moves[ix].id.clone()).collect::<Vec<_>>();
            taught.sort();
            let mon = data.configure(base, "hardy", ability.as_deref(), &taught).unwrap();
            let mut beam_keys = BTreeSet::new();
            visit_groups(&data, base, &mon, &mut |group| {
                let Some(style) = style_of_group(&data, &group) else {
                    return;
                };
                let branch = branch_of(&data, base, &group);
                if build_config(&data, base, &group, "hardy", ability.clone(), style, branch).is_err() {
                    return;
                }
                beam_keys.insert((style.to_string(), branch.to_string()));
            });
            beam_n += beam_keys.len();
            for key in beam_keys.difference(&enum_keys) {
                missing.push(format!("{} {} {} {}", base.dex, base.name, key.0, key.1));
            }
        }
        assert!(missing.is_empty(), "{}", missing.join("; "));
        assert_eq!(enum_n, 3010, "enum {enum_n} beam {beam_n}");
        assert_eq!(beam_n, 3010);
    }

    #[test]
    fn ditto_has_the_fewest_legal_groups_among_the_smallest_pools() {
        let data = data();
        let min_attacks = data.dex.iter().map(|m| attack_indexes(&data, m).len()).min().unwrap();
        let ditto = data.dex.iter().find(|m| m.dex == 132).unwrap();
        let ditto_groups = legal_groups(&data, ditto).len();
        assert_eq!(attack_indexes(&data, ditto).len(), min_attacks);
        for base in data.dex.iter().filter(|m| attack_indexes(&data, m).len() == min_attacks) {
            assert!(ditto_groups <= legal_groups(&data, base).len(), "dex {}", base.dex);
        }
    }

    #[test]
    fn plan_for_ditto_writes_a_ledger_and_runs_no_match() {
        let data = data();
        let manifest = json!({
            "schema": 1,
            "kind": "funnel",
            "gameCommit": research::GAME_COMMIT,
            "engineFingerprint": research::fingerprint(),
            "policyVersion": POLICY,
            "dex": [132],
            "secondsPerMatch": 900,
            "limits": {"threads": 1, "maxWallSeconds": 30, "maxFailedTasks": 1, "maxMatches": 1000000},
            "stages": {
                "A": {"groups": 30, "seeds": [1001, 1002, 1003, 1004]},
                "B": {"groups": 4, "seeds": [1101, 1102]},
                "C": {"groups": 2, "seeds": [1001, 1002, 1003, 1004]},
                "D": {"seeds": [3001, 3002]},
            },
            "recallDexes": [],
        });
        let spec = parse_spec(&data, manifest).unwrap();
        let dir = std::env::temp_dir().join("funnel-ditto-plan.json");
        let counts = write_plan(&data, &spec, dir.to_str().unwrap()).unwrap();
        assert!(counts["tasksUpperBound"].as_u64().unwrap() > 0);
        assert!(counts["stageA"].as_u64().unwrap() > 0);
        let plan: Value = serde_json::from_slice(&fs::read(&dir).unwrap()).unwrap();
        assert_eq!(plan["rankingReady"], false);
        assert!(plan["ledger"]["stageATasks"].as_array().unwrap().iter().all(|task| task["stage"].as_str().is_some()));
        let (loaded, _, _) = load_plan(&data, dir.to_str().unwrap()).unwrap();
        assert_eq!(loaded["planHash"], plan["planHash"]);
        let ditto = data.dex.iter().find(|m| m.dex == 132).unwrap();
        let tallies = tally_species(&data, ditto);
        let cap = counts["fullGroupCap"].as_u64().unwrap() as usize;
        assert!(!plan["strata"].as_array().unwrap().is_empty());
        for stratum in plan["strata"].as_array().unwrap() {
            assert_eq!(stratum["search"], "full");
            let style = stratum["style"].as_str().unwrap();
            let branch = stratum["branch"].as_str().unwrap();
            let tally = tallies.iter().find(|row| row.style == style && row.branch == branch).unwrap();
            assert_eq!(stratum["candidates"].as_array().unwrap().len(), tally.groups);
            assert!(tally.groups <= cap);
        }
    }

    #[test]
    fn canonical_bytes_are_what_hash_value_digests() {
        let value = json!({"b": 1, "a": [true, null], "nested": {"z": "x", "m": 0.5}});
        let bytes = canonical_bytes(&value);
        assert_eq!(hash_value(&value), format!("{:x}", Sha256::digest(bytes)));
    }

    #[test]
    fn morning_manifest_matches_the_budget_constants() {
        let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("../runpod/funnel-full.json");
        let value: Value = serde_json::from_slice(&fs::read(path).unwrap()).unwrap();
        assert_eq!(value["stages"]["A"]["groups"].as_u64(), Some(FALLBACK_GROUPS as u64));
        assert_eq!(value["stages"]["B"]["groups"].as_u64(), Some(MORNING_GROUPS_B));
        assert_eq!(value["stages"]["C"]["groups"].as_u64(), Some(MORNING_GROUPS_C));
        assert_eq!(value["stages"]["A"]["seeds"].as_array().unwrap().len() as u64, MORNING_SEEDS_A);
        assert_eq!(value["stages"]["B"]["seeds"].as_array().unwrap().len() as u64, MORNING_SEEDS_B);
        assert_eq!(value["stages"]["C"]["seeds"].as_array().unwrap().len() as u64, MORNING_SEEDS_C);
        assert_eq!(value["stages"]["D"]["seeds"].as_array().unwrap().len() as u64, MORNING_SEEDS_D);
        assert_eq!(value["recallDexes"][0], 54);
        assert_eq!(value["recallDexes"][1], "smallest");
        assert_eq!(value["limits"]["maxWallSeconds"].as_u64(), Some(10800));
    }

    #[test]
    fn roster_cap_stays_inside_the_measured_budget() {
        let data = data();
        let width = roster(&data);
        assert!(width.tasks <= MATCH_CEILING, "tasks {}", width.tasks);
        assert!(width.cap > FALLBACK_GROUPS, "cap {}", width.cap);
        assert!(width.full_strata > 0);
        assert!(width.beam_strata > 0);
        eprintln!(
            "cap={} tasks={} stageA={} full={} beam={} enumerated={} beamed={} recall={}",
            width.cap,
            width.tasks,
            width.stage_a,
            width.full_strata,
            width.beam_strata,
            width.enumerated_groups,
            width.beamed_groups,
            width.recall_tasks
        );
    }

    #[test]
    fn mew_keeps_small_strata_whole_and_beams_the_rest() {
        let data = data();
        let manifest = json!({
            "schema": 1,
            "kind": "funnel",
            "gameCommit": research::GAME_COMMIT,
            "engineFingerprint": research::fingerprint(),
            "policyVersion": POLICY,
            "dex": [151],
            "secondsPerMatch": 900,
            "limits": {"threads": 1, "maxWallSeconds": 30, "maxFailedTasks": 1, "maxMatches": 5000000},
            "stages": {
                "A": {"groups": 30, "seeds": [1001, 1002, 1003, 1004]},
                "B": {"groups": 4, "seeds": [1101, 1102]},
                "C": {"groups": 2, "seeds": [1001, 1002, 1003, 1004]},
                "D": {"seeds": [3001, 3002]},
            },
            "recallDexes": [],
        });
        let spec = parse_spec(&data, manifest).unwrap();
        let path = std::env::temp_dir().join(format!("funnel-mew-{}.json", std::process::id()));
        let counts = write_plan(&data, &spec, path.to_str().unwrap()).unwrap();
        let plan: Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        load_plan(&data, path.to_str().unwrap()).unwrap();
        let _ = fs::remove_file(&path);
        let mew = data.dex.iter().find(|m| m.dex == 151).unwrap();
        let tallies = tally_species(&data, mew);
        let cap = counts["fullGroupCap"].as_u64().unwrap() as usize;
        let mut saw_full = false;
        let mut saw_beam = false;
        for stratum in plan["strata"].as_array().unwrap() {
            let style = stratum["style"].as_str().unwrap();
            let branch = stratum["branch"].as_str().unwrap();
            let tally = tallies.iter().find(|row| row.style == style && row.branch == branch).unwrap();
            let n = stratum["candidates"].as_array().unwrap().len();
            if stratum["search"] == "full" {
                assert_eq!(n, tally.groups, "{style} {branch}");
                assert!(tally.groups <= cap);
                saw_full = true;
            } else {
                assert_eq!(stratum["search"], "beam");
                assert!(n <= spec.groups_a);
                assert!(tally.groups > cap);
                saw_beam = true;
            }
        }
        assert!(saw_full);
        assert!(saw_beam);
    }

    #[test]
    fn metric_index_keeps_each_config_and_a_later_row_replaces_the_seed() {
        let dir = std::env::temp_dir().join(format!("funnel-index-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        let tasks = vec![
            json!({"taskId": "t1", "configurationId": "cfg-a", "seed": 1001}),
            json!({"taskId": "t2", "configurationId": "cfg-b", "seed": 1001}),
            json!({"taskId": "t3", "configurationId": "cfg-a", "seed": 1001}),
            json!({"taskId": "missing", "configurationId": "cfg-a", "seed": 1002}),
        ];
        for (id, survival) in [("t1", 1.0), ("t2", 9.0), ("t3", 4.0)] {
            fs::write(dir.join(format!("{id}.json")), serde_json::to_vec(&json!({
                "seed": 1001,
                "row": {"metrics": {"survivalSeconds": survival, "contactDamage": 0.0, "contactSeconds": 0.0, "trappedSeconds": 0.0}},
            })).unwrap()).unwrap();
        }
        let index = metric_index(&dir, &tasks);
        assert_eq!(index["cfg-a"][&1001]["survivalSeconds"], 4.0);
        assert!(index["cfg-a"].get(&1002).is_none());
        assert_eq!(index["cfg-b"][&1001]["survivalSeconds"], 9.0);
        assert!(!index.contains_key("other"));
        let stage_b = index.get("cfg-a").cloned().unwrap();
        let mut stage_a = HashMap::new();
        stage_a.insert(1001, json!({"survivalSeconds": 7.0, "contactDamage": 0.0, "contactSeconds": 0.0, "trappedSeconds": 0.0}));
        let merged = overlay(stage_b, &stage_a);
        let candidate = HashMap::from([(1001, json!({"survivalSeconds": 10.0, "contactDamage": 0.0, "contactSeconds": 0.0, "trappedSeconds": 0.0}))]);
        let ds = paired(&candidate, &merged, &[1001]).unwrap();
        assert!((mean_survival(&ds) - 3.0).abs() < 1e-9);
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    #[ignore = "writes a stage-sized checkpoint directory under /tmp"]
    fn metric_index_one_pass_stays_under_the_wall() {
        let n: usize = std::env::var("FUNNEL_INDEX_N").ok().and_then(|s| s.parse().ok()).unwrap_or(1_193_640);
        let dir = std::env::temp_dir().join(format!("funnel-index-scale-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        let _cleanup = DirGuard(dir.clone());
        let body = br#"{"seed":1001,"row":{"metrics":{"survivalSeconds":1.0,"contactDamage":0.0,"contactSeconds":0.0,"trappedSeconds":0.0}}}"#;
        let mut tasks = Vec::with_capacity(n);
        let write_started = Instant::now();
        for i in 0..n {
            let task_id = format!("t{i:07}");
            fs::write(dir.join(format!("{task_id}.json")), body).unwrap();
            tasks.push(json!({
                "taskId": task_id,
                "configurationId": format!("c{}", i / 4),
                "seed": 1001 + (i % 4) as u32,
            }));
        }
        let write_s = write_started.elapsed().as_secs_f64();
        let dropped = std::process::Command::new("sh")
            .arg("-c")
            .arg("sync; echo 3 > /proc/sys/vm/drop_caches")
            .stderr(std::process::Stdio::null())
            .status()
            .map(|status| status.success())
            .unwrap_or(false);
        let mut walls = Vec::new();
        let mut cpus = Vec::new();
        let mut indexed = 0usize;
        for _ in 0..3 {
            let cpu_before = proc_cpu_seconds();
            let started = Instant::now();
            let index = metric_index(&dir, &tasks);
            walls.push(started.elapsed().as_secs_f64());
            cpus.push(proc_cpu_seconds() - cpu_before);
            indexed = index.len();
            assert_eq!(index.get("c0").and_then(|m| m.get(&1001)).and_then(|m| m["survivalSeconds"].as_f64()), Some(1.0));
        }
        let mut candidate = HashMap::new();
        let mut control = HashMap::new();
        for seed in 1001..1005 {
            candidate.insert(seed, json!({"survivalSeconds": 3.0, "contactDamage": 0.0, "contactSeconds": 0.0, "trappedSeconds": 0.0}));
            control.insert(seed, json!({"survivalSeconds": 1.0, "contactDamage": 0.0, "contactSeconds": 0.0, "trappedSeconds": 0.0}));
        }
        let rank_started = Instant::now();
        let mut acc = 0.0;
        for _ in 0..(n / 4) {
            acc += mean_survival(&paired(&candidate, &control, &[1001, 1002, 1003, 1004]).unwrap());
        }
        let rank_s = rank_started.elapsed().as_secs_f64();
        assert!((acc - 2.0 * (n / 4) as f64).abs() < 1e-6);
        eprintln!(
            "index_n={n} configs={indexed} write_s={write_s:.3} dropped_caches={dropped} walls={walls:?} cpu_s={cpus:?} rank_s={rank_s:.3} acc={acc}"
        );
        assert!(walls.iter().all(|wall| *wall < 900.0), "index walls {walls:?}");
        assert_eq!(indexed, n.div_ceil(4));
    }

    struct DirGuard(PathBuf);
    impl Drop for DirGuard {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn proc_cpu_seconds() -> f64 {
        let text = fs::read_to_string("/proc/self/stat").unwrap_or_default();
        let rest = text.split_once(')').map(|(_, tail)| tail).unwrap_or("");
        let fields = rest.split_whitespace().collect::<Vec<_>>();
        let utime = fields.get(11).and_then(|s| s.parse::<u64>().ok()).unwrap_or(0);
        let stime = fields.get(12).and_then(|s| s.parse::<u64>().ok()).unwrap_or(0);
        (utime + stime) as f64 / 100.0
    }
}
