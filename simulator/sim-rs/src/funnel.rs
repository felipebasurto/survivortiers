//! Staged survival search. Planning counts tasks and writes no match.
//! Run and resume share one cache of atomic per-task checkpoints.
use crate::{
    data::{Data, Kind, Mon},
    engine::Tables,
    production::{
        atomic_json, compiler_version, config_proxy, hash_value, normalized_exposure,
        paired_interval, run_configuration, task_id, taught_tm_cost, visit_groups,
    },
    research,
    selection::{self, BuildStyle, CombatRole, Configuration},
};
use rayon::prelude::*;
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, BTreeSet, HashMap},
    fs::{self, File, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    sync::atomic::{AtomicU32, Ordering},
    time::Instant,
};

const POLICY: &str = "survivortiers-funnel-v1";
const MARGIN: f64 = 0.10;

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
        .filter(|n| *n > 0. && *n <= 900.)
        .ok_or("maxWallSeconds must be in (0,900]")?;
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

pub(crate) fn legal_groups(data: &Data, base: &Mon) -> BTreeSet<Vec<usize>> {
    let legal: BTreeSet<usize> = base
        .start_choices(&data.moves)
        .into_iter()
        .filter(|&i| data.moves[i].is_attack())
        .collect();
    let mut groups = BTreeSet::new();
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
                    groups.insert(rest);
                }
            }
        }
    }
    let buffs = base
        .pool
        .iter()
        .copied()
        .filter(|&i| data.moves[i].kind_name == "buff" && data.moves[i].levels[0].buff != 0)
        .collect::<Vec<_>>();
    let attacks_only = groups.iter().cloned().collect::<Vec<_>>();
    for g in attacks_only {
        if g.len() < 4 {
            for &b in &buffs {
                if !g.contains(&b) {
                    let mut x = g.clone();
                    x.push(b);
                    groups.insert(x);
                }
            }
        }
        if g.len() <= 2 {
            for i in 0..buffs.len() {
                for j in (i + 1)..buffs.len() {
                    if !g.contains(&buffs[i]) && !g.contains(&buffs[j]) {
                        let mut x = g.clone();
                        x.push(buffs[i]);
                        x.push(buffs[j]);
                        groups.insert(x);
                    }
                }
            }
        }
    }
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

fn beam_for_stratum(
    data: &Data,
    base: &Mon,
    spec: &Spec,
) -> Result<BTreeMap<(String, String), Vec<Proposal>>, String> {
    let ability = default_ability(base);
    let mut taught = base.tms.iter().map(|&ix| data.moves[ix].id.clone()).collect::<Vec<_>>();
    taught.sort();
    let mon = data.configure(base, "hardy", ability.as_deref(), &taught)?;
    let mut grouped: BTreeMap<(String, String), Vec<Proposal>> = BTreeMap::new();
    visit_groups(data, base, &mon, &mut |group| {
        let Some(style) = style_of_group(data, &group) else {
            return;
        };
        let branch = branch_of(data, base, &group);
        let Ok(config) = build_config(data, base, &group, "hardy", ability.clone(), style, branch) else {
            return;
        };
        if !within_budget(data, base, &config, spec.tm_budget) {
            return;
        }
        let (score, _, _) = config_proxy(data, base, &config);
        grouped.entry((style.into(), branch.into())).or_default().push(Proposal {
            config,
            score,
            moves: group,
        });
    });
    for list in grouped.values_mut() {
        list.sort_by(|a, b| {
            b.score
                .total_cmp(&a.score)
                .then_with(|| a.config.id.cmp(&b.config.id))
        });
        list.truncate(spec.groups_a);
    }
    Ok(grouped)
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

struct PlanBuild {
    value: Value,
    counts: Value,
}

fn build_plan(data: &Data, spec: &Spec) -> Result<PlanBuild, String> {
    let mut strata = Vec::new();
    let mut stage_a = Vec::new();
    let mut configs = BTreeMap::new();
    let mut controls = Vec::new();
    let mut unavailable = Vec::new();
    let mut stage_a_tasks = 0u64;
    let mut stage_b_upper = 0u64;
    let mut stage_c_upper = 0u64;
    let mut stage_d_upper = 0u64;
    for &dex in &spec.dex {
        let base = mon(data, dex)?;
        let control = stock_control(data, base)?;
        let control_json = config_json(data, base, &control, config_proxy(data, base, &control).0)?;
        controls.push(control_json);
        configs.insert(control.id.clone(), control);
        let grouped = beam_for_stratum(data, base, spec)?;
        let mut seen = BTreeSet::new();
        for ((style, branch), proposals) in &grouped {
            seen.insert((style.clone(), branch.clone()));
            let profiles = profile_count(data, base, &proposals[0].moves, style, spec.tm_budget).unwrap_or(1);
            let n_a = proposals.len();
            let n_b = n_a.min(spec.groups_b);
            let n_c = n_b.min(spec.groups_c);
            stage_a_tasks += (n_a * spec.seeds_a.len()) as u64;
            stage_b_upper += (n_b * spec.seeds_b.len()) as u64;
            stage_c_upper += (n_c * profiles * spec.seeds_c.len()) as u64;
            stage_d_upper += spec.seeds_d.len() as u64;
            let mut rows = Vec::new();
            for proposal in proposals {
                rows.push(config_json(data, base, &proposal.config, proposal.score)?);
                for &seed in &spec.seeds_a {
                    stage_a.push(json!({
                        "taskId": task_id(&spec.hash, &proposal.config.id, "A", seed),
                        "configurationId": proposal.config.id,
                        "stage": "A",
                        "seed": seed,
                    }));
                }
                configs.insert(proposal.config.id.clone(), proposal.config.clone());
            }
            strata.push(json!({
                "dex": dex,
                "style": style,
                "branch": branch,
                "profilesPerGroup": profiles,
                "candidates": rows,
            }));
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
                } else {
                    "no legal base-role group in the move beam"
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
    for control in configs.values().filter(|c| c.id.contains("|branch:control_no_tm|")) {
        for seed in spec.seeds_a.iter().chain(&spec.seeds_b).chain(&spec.seeds_d) {
            stage_a.push(json!({
                "taskId": task_id(&spec.hash, &control.id, if spec.seeds_d.contains(seed) { "D" } else if spec.seeds_b.contains(seed) { "B" } else { "A" }, *seed),
                "configurationId": control.id,
                "stage": if spec.seeds_d.contains(seed) { "D" } else if spec.seeds_b.contains(seed) { "B" } else { "A" },
                "seed": *seed,
            }));
        }
    }
    let control_tasks = spec.dex.len() as u64 * (spec.seeds_a.len() + spec.seeds_b.len() + spec.seeds_d.len()) as u64;
    let mut recall_tasks = 0u64;
    let mut recall_detail = Vec::new();
    for &dex in &spec.recall {
        let base = mon(data, dex)?;
        let groups = legal_groups(data, base);
        let mut per_branch: BTreeMap<(String, String), u64> = BTreeMap::new();
        for group in &groups {
            let Some(style) = style_of_group(data, group) else { continue };
            let branch = branch_of(data, base, group);
            *per_branch.entry((style.to_string(), branch.to_string())).or_default() += 1;
        }
        let screen = groups.len() as u64 * 4;
        let confirm = per_branch
            .values()
            .map(|n| n.min(&50) * spec.seeds_d.len() as u64)
            .sum::<u64>();
        recall_tasks += screen + confirm;
        recall_detail.push(json!({"dex": dex, "groups": groups.len(), "screeningTasks": screen, "confirmationUpper": confirm}));
    }
    let tasks_upper = stage_a_tasks + stage_b_upper + stage_c_upper + stage_d_upper + control_tasks + recall_tasks;
    if tasks_upper > spec.max_matches {
        return Err(format!("funnel ceiling {tasks_upper} exceeds maxMatches"));
    }
    let counts = json!({
        "stageA": stage_a_tasks,
        "stageBUpper": stage_b_upper,
        "stageCUpper": stage_c_upper,
        "stageDUpper": stage_d_upper,
        "controlTasks": control_tasks,
        "recallTasksUpper": recall_tasks,
        "tasksUpperBound": tasks_upper,
        "strata": strata.len(),
        "species": spec.dex.len(),
    });
    let mut plan = json!({
        "schema": 1,
        "kind": "funnel",
        "policyVersion": POLICY,
        "rankingReady": false,
        "manifest": spec.raw,
        "manifestHash": spec.hash,
        "gameCommit": research::GAME_COMMIT,
        "engineFingerprint": research::fingerprint(),
        "rustc": compiler_version(),
        "marginFraction": MARGIN,
        "controls": controls,
        "strata": strata,
        "unavailable": unavailable,
        "recall": recall_detail,
        "ledger": {"stageATasks": stage_a},
        "counts": counts,
    });
    plan["planHash"] = json!(hash_value(&plan));
    Ok(PlanBuild { value: plan, counts })
}

fn write_plan(data: &Data, spec: &Spec, out: &str) -> Result<Value, String> {
    let built = build_plan(data, spec)?;
    atomic_json(Path::new(out), &built.value)?;
    Ok(built.counts)
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
        let shortlist = by_prior.iter().take(30).map(|row| row.1.clone()).collect::<Vec<_>>();
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
