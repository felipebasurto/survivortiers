//! Bounded, restartable heuristic search. Planning is exhaustive counting only; execution
//! requires an explicit `run`/`resume` command and is always fenced by the plan's budgets.
use crate::{
    data::{Data, Kind, Mon},
    engine::{ranking_prior, ranking_speed, run_match, Bot, Ext, Opts, PriorAttack, Tables},
    math::Libm,
    research,
    selection::{self, BuildStyle, CombatRole, Configuration},
};
use rayon::prelude::*;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    cmp::Ordering,
    collections::{BTreeMap, BTreeSet, HashMap},
    fs::{self, File, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    process::Command,
    time::Instant,
};

const POLICY_VERSION: &str = "survivortiers-survival-safety-v1";
const SELECTION_METHOD: &str =
    "paired student-t 95% descriptive intervals; no multiple-comparison claim";
const MAX_LEDGER_TASKS: u64 = 1_000_000;
const MOVE_BEAM_CAP: usize = 24;

#[derive(Clone, Debug)]
struct Limits {
    max_configurations: u64,
    max_matches: u64,
    max_simulated_seconds: f64,
    max_wall_seconds: f64,
    max_failed_tasks: u32,
    threads: usize,
}
#[derive(Clone, Debug)]
struct SearchPolicy {
    group_quota: usize,
    shortlist_per_stratum: usize,
    confirm_per_stratum: usize,
    exposure_margins: [f64; 3],
    survival_margin: f64,
}
#[derive(Clone, Debug)]
struct Manifest {
    raw: Value,
    dex: Vec<u32>,
    screen: BTreeSet<u32>,
    confirm: BTreeSet<u32>,
    seconds: f64,
    limits: Limits,
    policy: SearchPolicy,
    hash: String,
    rustc: String,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
struct Stratum {
    dex: u32,
    style: String,
    role: String,
    branch: String,
}
#[derive(Clone, Debug)]
struct Candidate {
    config: Configuration,
    branch: String,
    stratum: Stratum,
    proxy_dps: f64,
    coverage_types: usize,
    own_type_attacks: usize,
}

fn canonical(v: &Value, out: &mut Vec<u8>) {
    match v {
        Value::Object(obj) => {
            out.push(b'{');
            let keys = obj.keys().collect::<BTreeSet<_>>();
            for (i, k) in keys.iter().enumerate() {
                if i > 0 {
                    out.push(b',');
                }
                out.extend(serde_json::to_vec(*k).unwrap());
                out.push(b':');
                canonical(&obj[*k], out);
            }
            out.push(b'}');
        }
        Value::Array(xs) => {
            out.push(b'[');
            for (i, x) in xs.iter().enumerate() {
                if i > 0 {
                    out.push(b',');
                }
                canonical(x, out);
            }
            out.push(b']');
        }
        _ => out.extend(serde_json::to_vec(v).unwrap()),
    }
}
fn hash_value(v: &Value) -> String {
    let mut b = Vec::new();
    canonical(v, &mut b);
    format!("{:x}", Sha256::digest(b))
}
fn compiler_version() -> String {
    Command::new("rustc")
        .arg("--version")
        .output()
        .ok()
        .filter(|o| o.status.success())
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .unwrap_or_else(|| "unavailable".into())
}
fn u32_set(v: &Value, name: &str) -> Result<BTreeSet<u32>, String> {
    let a = v
        .as_array()
        .ok_or_else(|| format!("{name} must be an array"))?;
    let mut s = BTreeSet::new();
    for x in a {
        let n = x
            .as_u64()
            .filter(|n| *n <= u32::MAX as u64)
            .ok_or_else(|| format!("{name} values must be u32 integers"))? as u32;
        if !s.insert(n) {
            return Err(format!("duplicate {name} seed {n}"));
        }
    }
    if s.is_empty() {
        return Err(format!("{name} must not be empty"));
    }
    Ok(s)
}
fn num(v: &Value, k: &str) -> Result<f64, String> {
    let n = v
        .get(k)
        .and_then(Value::as_f64)
        .ok_or_else(|| format!("{k} must be numeric"))?;
    if !n.is_finite() || n < 0. {
        return Err(format!("{k} must be finite and nonnegative"));
    }
    Ok(n)
}
fn parse_manifest_value(data: &Data, v: Value) -> Result<Manifest, String> {
    if v["schema"].as_u64() != Some(1) {
        return Err("manifest schema must be 1".into());
    }
    if v["gameCommit"].as_str() != Some(research::GAME_COMMIT) {
        return Err("manifest gameCommit is stale".into());
    }
    if v["engineFingerprint"].as_str() != Some(research::fingerprint().as_str()) {
        return Err("manifest engineFingerprint is stale".into());
    }
    if v["policyVersion"].as_str() != Some(POLICY_VERSION) {
        return Err("unsupported policyVersion".into());
    }
    let mut dex = Vec::new();
    if v["dex"].as_str() == Some("all") {
        dex.extend(data.dex.iter().map(|m| m.dex));
    } else if let Some(a) = v["dex"].as_array() {
        for x in a {
            let n = x
                .as_u64()
                .filter(|n| *n <= u32::MAX as u64)
                .ok_or("dex IDs must be u32")? as u32;
            if !data.dex.iter().any(|m| m.dex == n) {
                return Err(format!("unknown dex {n}"));
            }
            dex.push(n);
        }
    } else {
        return Err("dex must be 'all' or an array of IDs".into());
    }
    if dex.is_empty() || dex.iter().copied().collect::<BTreeSet<_>>().len() != dex.len() {
        return Err("dex list must be nonempty and unique".into());
    }
    let screen = u32_set(&v["screeningSeeds"], "screeningSeeds")?;
    let confirm = u32_set(&v["confirmationSeeds"], "confirmationSeeds")?;
    if !screen.is_disjoint(&confirm) {
        return Err("seed blocks must be disjoint".into());
    }
    let seconds = num(&v, "secondsPerMatch")?;
    if seconds <= 0. || seconds > 900. {
        return Err("secondsPerMatch must be in (0,900]".into());
    }
    let l = &v["limits"];
    let max_configurations = l["maxConfigurations"]
        .as_u64()
        .ok_or("maxConfigurations is required")?;
    let max_matches = l["maxMatches"].as_u64().ok_or("maxMatches is required")?;
    let max_simulated_seconds = num(l, "maxSimulatedSeconds")?;
    let max_wall_seconds = num(l, "maxWallSeconds")?;
    let max_failed_tasks = l["maxFailedTasks"]
        .as_u64()
        .ok_or("maxFailedTasks is required")?;
    let threads = l["threads"].as_u64().ok_or("threads is required")? as usize;
    if max_configurations == 0
        || max_matches == 0
        || max_simulated_seconds <= 0.
        || max_wall_seconds <= 0.
        || max_wall_seconds > 900.
        || threads == 0
        || threads > 256
        || max_failed_tasks > u32::MAX as u64
    {
        return Err("limits must be positive, maxWallSeconds <=900, and threads <=256".into());
    }
    let p = &v["searchPolicy"];
    if p["version"].as_str() != Some(POLICY_VERSION) {
        return Err("searchPolicy.version must match policyVersion".into());
    }
    let group_quota = p["groupsPerStratum"]
        .as_u64()
        .filter(|n| *n > 0)
        .ok_or("groupsPerStratum must be positive")? as usize;
    let shortlist_per_stratum = p["shortlistPerStratum"]
        .as_u64()
        .filter(|n| *n > 0)
        .ok_or("shortlistPerStratum must be positive")? as usize;
    let confirm_per_stratum = p["confirmPerStratum"]
        .as_u64()
        .filter(|n| *n > 0)
        .ok_or("confirmPerStratum must be positive")? as usize;
    let margins = &p["exposureMargins"];
    let exposure_margins = [
        num(margins, "contactDamagePerMinute")?,
        num(margins, "contactFraction")?,
        num(margins, "trappedFraction")?,
    ];
    if v["searchPolicy"]["exposureMargins"]
        .get("contactDamagePerMinute")
        .is_none()
        || v["searchPolicy"]["exposureMargins"]
            .get("contactFraction")
            .is_none()
        || v["searchPolicy"]["exposureMargins"]
            .get("trappedFraction")
            .is_none()
    {
        return Err("exposureMargins must define contactDamagePerMinute, contactFraction, and trappedFraction".into());
    }
    let survival_margin = num(p, "survivalNoninferioritySeconds")?;
    let hash = hash_value(&v);
    Ok(Manifest {
        raw: v,
        dex,
        screen,
        confirm,
        seconds,
        limits: Limits {
            max_configurations,
            max_matches,
            max_simulated_seconds,
            max_wall_seconds,
            max_failed_tasks: max_failed_tasks as u32,
            threads,
        },
        policy: SearchPolicy {
            group_quota,
            shortlist_per_stratum,
            confirm_per_stratum,
            exposure_margins,
            survival_margin,
        },
        hash,
        rustc: compiler_version(),
    })
}
fn parse_manifest(data: &Data, path: &str) -> Result<Manifest, String> {
    let text = fs::read_to_string(path).map_err(|e| format!("read {path}: {e}"))?;
    let v: Value = serde_json::from_str(&text).map_err(|e| format!("manifest JSON: {e}"))?;
    parse_manifest_value(data, v)
}

fn roles_from_group(data: &Data, group: &[usize]) -> Vec<CombatRole> {
    let mut types = BTreeSet::new();
    let mut offensive_buff = false;
    let mut defensive_buff = false;
    for &i in group {
        let m = &data.moves[i];
        if m.is_attack() {
            types.insert(m.levels[0].ty);
        }
        match m.levels[0].buff {
            1 | 5 | 6 => offensive_buff = true,
            2 | 3 | 4 => defensive_buff = true,
            _ => {}
        }
    }
    let coverage = types.len() >= 2;
    let mut roles = vec![CombatRole::Base];
    if offensive_buff && !defensive_buff {
        roles.push(CombatRole::Aggro);
    }
    if coverage {
        roles.push(CombatRole::Coverage);
        if offensive_buff && !defensive_buff {
            roles.push(CombatRole::Both);
        }
    }
    roles
}
fn style_from_group(data: &Data, group: &[usize]) -> BuildStyle {
    if group.iter().any(|&i| data.moves[i].kind == Kind::Melee) {
        BuildStyle::Melee
    } else {
        BuildStyle::Ranged
    }
}
fn stratum(dex: u32, style: &BuildStyle, role: &CombatRole, branch: &str) -> Stratum {
    Stratum {
        dex,
        style: match style {
            BuildStyle::Melee => "melee",
            BuildStyle::Ranged => "ranged",
        }
        .into(),
        role: match role {
            CombatRole::Base => "base",
            CombatRole::Aggro => "aggro",
            CombatRole::Coverage => "coverage",
            CombatRole::Both => "both",
        }
        .into(),
        branch: branch.into(),
    }
}
fn config_proxy(data: &Data, base: &Mon, c: &Configuration) -> (f64, usize, usize) {
    let mon = data
        .configure(base, &c.nature, c.ability.as_deref(), &c.tms)
        .expect("generated legal configuration");
    let mut dps = 0.;
    let mut types = BTreeSet::new();
    let mut own = 0;
    for id in &c.moves {
        let ix = data.move_ix[id];
        let m = &data.moves[ix];
        if !m.is_attack() {
            continue;
        }
        let l = &m.levels[0];
        let cd = l.cd.max(0.05);
        let count = if l.count.is_finite() {
            l.count.max(1.)
        } else {
            1.
        };
        let fit = match l.cat {
            1 => {
                if mon.atk != 0. {
                    mon.pa / mon.atk
                } else {
                    1.
                }
            }
            2 => {
                if mon.atk != 0. {
                    mon.sa / mon.atk
                } else {
                    1.
                }
            }
            _ => 1.,
        };
        let mono = if mon.types.len() == 1 && mon.types[0] == l.ty {
            1.2
        } else {
            1.
        };
        let aid = c.ability.as_deref().unwrap_or("");
        let (offense, incoming) = ranking_prior(
            aid,
            PriorAttack {
                ty: l.ty,
                cat: l.cat,
                primary: mon.types.first().copied().unwrap_or(0),
                own: base.types.contains(&l.ty),
                melee: m.kind == Kind::Melee,
                dash: l.xk == 5,
                base_dmg: l.base_dmg,
                count,
                bounce: l.bounce.is_finite() && l.bounce > 0.,
                has_effect: l.status || (l.knock.is_finite() && l.knock > 0.),
                tags: l.tags,
            },
        );
        let taken = if matches!(c.role, CombatRole::Base | CombatRole::Coverage) {
            incoming
        } else {
            1.
        };
        dps += l.dmg.max(0.) * count / cd * mon.atk.max(0.) * fit * mono * offense / taken;
        types.insert(l.ty);
        if base.types.contains(&l.ty) {
            own += 1;
        }
    }
    let speed = if base.spd > 0. {
        (mon.spd / base.spd).clamp(0.5, 1.5)
    } else {
        1.
    };
    let aid = c.ability.as_deref().unwrap_or("");
    dps *= speed.powf(0.25) * ranking_speed(aid);
    (dps, types.len(), own)
}
fn candidate_order(a: &Candidate, b: &Candidate) -> Ordering {
    b.proxy_dps
        .total_cmp(&a.proxy_dps)
        .then_with(|| b.coverage_types.cmp(&a.coverage_types))
        .then_with(|| b.own_type_attacks.cmp(&a.own_type_attacks))
        .then_with(|| a.config.id.cmp(&b.config.id))
}

fn choose(
    items: &[usize],
    need: usize,
    from: usize,
    acc: &mut Vec<usize>,
    f: &mut impl FnMut(&[usize]),
) {
    if need == 0 {
        f(acc);
        return;
    }
    if items.len().saturating_sub(from) < need {
        return;
    }
    for i in from..=items.len() - need {
        acc.push(items[i]);
        choose(items, need - 1, i + 1, acc, f);
        acc.pop();
    }
}
fn move_proxy(data: &Data, base: &Mon, ix: usize) -> f64 {
    let m = &data.moves[ix];
    let l = &m.levels[0];
    let fit = match l.cat {
        1 => {
            if base.atk != 0. {
                base.pa / base.atk
            } else {
                1.
            }
        }
        2 => {
            if base.atk != 0. {
                base.sa / base.atk
            } else {
                1.
            }
        }
        _ => 1.,
    };
    let mono = if base.types.len() == 1 && base.types[0] == l.ty {
        1.2
    } else {
        1.
    };
    l.dmg.max(0.)
        * if l.count.is_finite() {
            l.count.max(1.)
        } else {
            1.
        }
        / l.cd.max(0.05)
        * base.atk.max(0.)
        * fit
        * mono
}
fn visit_groups(data: &Data, base: &Mon, mon: &Mon, f: &mut impl FnMut(Vec<usize>)) {
    // Bounded move beam: one best move per source feature bucket, then a fixed cap. It
    // preserves type, own/off-type, melee/ranged, and taught/natural coverage without walking
    // the cartesian set of every legal group. This is an explicit heuristic search frontier.
    let attacks = mon
        .pool
        .iter()
        .copied()
        .chain(std::iter::once(mon.start))
        .collect::<BTreeSet<_>>()
        .into_iter()
        .filter(|&i| data.moves[i].is_attack())
        .collect::<Vec<_>>();
    let mut buckets: BTreeMap<(u8, u8, bool, bool, bool), usize> = BTreeMap::new();
    for &ix in &attacks {
        let mv = &data.moves[ix];
        let key = (
            mv.levels[0].ty,
            mv.levels[0].cat,
            base.types.contains(&mv.levels[0].ty),
            mv.kind == Kind::Melee,
            !base.pool.contains(&ix) && ix != base.start,
        );
        let replace = buckets.get(&key).is_none_or(|&old| {
            move_proxy(data, base, ix).total_cmp(&move_proxy(data, base, old)) == Ordering::Greater
        });
        if replace {
            buckets.insert(key, ix);
        }
    }
    let mut by_type = BTreeMap::<u8, Vec<usize>>::new();
    for &ix in buckets.values() {
        by_type
            .entry(data.moves[ix].levels[0].ty)
            .or_default()
            .push(ix);
    }
    for xs in by_type.values_mut() {
        xs.sort_by(|&a, &b| {
            move_proxy(data, base, b)
                .total_cmp(&move_proxy(data, base, a))
                .then_with(|| data.moves[a].id.cmp(&data.moves[b].id))
        });
    }
    let mut beam = Vec::new();
    let mut depth = 0;
    while beam.len() < MOVE_BEAM_CAP {
        let mut added = false;
        for xs in by_type.values() {
            if let Some(&ix) = xs.get(depth) {
                if !beam.contains(&ix) {
                    beam.push(ix);
                    added = true;
                    if beam.len() == MOVE_BEAM_CAP {
                        break;
                    }
                }
            }
        }
        if !added {
            break;
        }
        depth += 1;
    }
    let mut rest = buckets
        .values()
        .copied()
        .filter(|i| !beam.contains(i))
        .collect::<Vec<_>>();
    rest.sort_by(|&a, &b| {
        move_proxy(data, base, b)
            .total_cmp(&move_proxy(data, base, a))
            .then_with(|| data.moves[a].id.cmp(&data.moves[b].id))
    });
    for i in rest {
        if beam.len() == MOVE_BEAM_CAP {
            break;
        }
        beam.push(i);
    }
    if beam.is_empty() {
        return;
    }
    let legal = mon
        .start_choices(&data.moves)
        .into_iter()
        .filter(|i| data.moves[*i].is_attack())
        .collect::<BTreeSet<_>>();
    let mut leads = beam
        .iter()
        .copied()
        .filter(|i| legal.contains(i))
        .collect::<Vec<_>>();
    if legal.contains(&base.start) && !leads.contains(&base.start) {
        leads.push(base.start);
    }
    let mut groups = BTreeSet::new();
    for &lead in &leads {
        groups.insert(vec![lead]);
        let partners = beam
            .iter()
            .copied()
            .filter(|&i| i != lead)
            .collect::<Vec<_>>();
        for &p in &partners {
            groups.insert(vec![lead, p]);
        }
        let top = partners.iter().take(6).copied().collect::<Vec<_>>();
        let mut pairs = Vec::new();
        choose(&top, 2, 0, &mut Vec::new(), &mut |xs| {
            if data.moves[xs[0]].levels[0].ty != data.moves[xs[1]].levels[0].ty {
                pairs.push(xs.to_vec());
            }
        });
        for pair in pairs {
            groups.insert(vec![lead, pair[0], pair[1]]);
        }
        let top4 = partners.iter().take(3).copied().collect::<Vec<_>>();
        if top4.len() == 3 {
            groups.insert(vec![lead, top4[0], top4[1], top4[2]]);
        }
    }
    let buffs = mon
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
                for j in i + 1..buffs.len() {
                    let a = buffs[i];
                    let b = buffs[j];
                    if !g.contains(&a) && !g.contains(&b) {
                        let mut x = g.clone();
                        x.extend([a, b]);
                        groups.insert(x);
                    }
                }
            }
        }
    }
    for g in groups {
        f(g);
    }
}

fn control(data: &Data, base: &Mon) -> Candidate {
    let nature = "hardy";
    let ability = base.abilities.iter().flatten().next().cloned();
    let group = vec![data.moves[base.start].id.clone()];
    let style = style_from_group(data, &[base.start]);
    let role = CombatRole::Base;
    let eq = selection::nature_equivalence(data, base, nature).expect("hardy nature");
    let aid = ability.as_deref().unwrap_or("default");
    let id = format!(
        "control_no_tm|dex{}|move:{}|nature:{eq}|ability:{aid}",
        base.dex, data.moves[base.start].id
    );
    let config = Configuration {
        id,
        dex: base.dex,
        moves: group,
        tms: vec![],
        second: None,
        nature: nature.into(),
        ability,
        nature_equivalence: eq,
        style: style.clone(),
        role: role.clone(),
    };
    Candidate {
        proxy_dps: config_proxy(data, base, &config).0,
        coverage_types: 1,
        own_type_attacks: usize::from(base.types.contains(&data.moves[base.start].levels[0].ty)),
        stratum: stratum(base.dex, &style, &role, "control_no_tm"),
        config,
        branch: "control_no_tm".into(),
    }
}

#[derive(Clone)]
struct GroupProposal {
    moves: Vec<usize>,
    proxy: f64,
    coverage: usize,
    own: usize,
}
fn group_order(a: &GroupProposal, b: &GroupProposal) -> Ordering {
    b.proxy
        .total_cmp(&a.proxy)
        .then_with(|| b.coverage.cmp(&a.coverage))
        .then_with(|| b.own.cmp(&a.own))
        .then_with(|| a.moves.cmp(&b.moves))
}
fn candidate_value(c: &Candidate) -> Value {
    json!({"id":c.config.id,"dex":c.config.dex,"group":c.config.moves,"tms":c.config.tms,"secondStart":c.config.second,"nature":c.config.nature,"ability":c.config.ability,"natureEquivalence":c.config.nature_equivalence,"build":c.stratum.style,"role":c.stratum.role,"branch":c.branch,"variantId":format!("{}:{}:{}",c.stratum.style,c.stratum.role,c.branch),"proxyDps":c.proxy_dps,"coverageTypes":c.coverage_types,"ownTypeAttacks":c.own_type_attacks})
}
fn parse_candidate(data: &Data, v: &Value) -> Result<Candidate, String> {
    let dex = v["dex"].as_u64().ok_or("candidate dex missing")? as u32;
    let base = data
        .dex
        .iter()
        .find(|m| m.dex == dex)
        .ok_or("candidate dex unavailable")?;
    let moves = v["group"]
        .as_array()
        .ok_or("candidate group missing")?
        .iter()
        .map(|x| {
            x.as_str()
                .map(str::to_owned)
                .ok_or("group move must be string".to_string())
        })
        .collect::<Result<Vec<_>, _>>()?;
    let tms = v["tms"]
        .as_array()
        .ok_or("candidate TMs missing")?
        .iter()
        .map(|x| {
            x.as_str()
                .map(str::to_owned)
                .ok_or("TM must be string".to_string())
        })
        .collect::<Result<Vec<_>, _>>()?;
    let nature = v["nature"]
        .as_str()
        .ok_or("candidate nature missing")?
        .to_string();
    let ability = v["ability"].as_str().map(str::to_owned);
    let branch = v["branch"]
        .as_str()
        .ok_or("candidate branch missing")?
        .to_string();
    if moves.is_empty()
        || moves.len() > 4
        || moves.iter().collect::<BTreeSet<_>>().len() != moves.len()
    {
        return Err("invalid candidate group".into());
    }
    let indices = moves
        .iter()
        .map(|id| {
            data.move_ix
                .get(id)
                .copied()
                .ok_or_else(|| format!("unknown candidate move {id}"))
        })
        .collect::<Result<Vec<_>, _>>()?;
    let mut mon = data.configure(base, &nature, ability.as_deref(), &tms)?;
    if !mon.start_choices(&data.moves).contains(&indices[0]) || !data.moves[indices[0]].is_attack()
    {
        return Err("illegal candidate lead".into());
    }
    if indices
        .iter()
        .any(|i| !mon.pool.contains(i) && *i != mon.start)
    {
        return Err("candidate contains unlearnable move".into());
    }
    let second = v["secondStart"].as_str().map(str::to_owned);
    let second_ix = second
        .as_ref()
        .map(|s| {
            data.move_ix
                .get(s)
                .copied()
                .ok_or_else(|| format!("unknown secondStart {s}"))
        })
        .transpose()?;
    if let Some(i) = second_ix {
        if i == indices[0] || !mon.start_choices(&data.moves).contains(&i) || !indices.contains(&i)
        {
            return Err("illegal secondStart".into());
        }
    }
    let style = if v["build"].as_str() == Some("melee") {
        BuildStyle::Melee
    } else if v["build"].as_str() == Some("ranged") {
        BuildStyle::Ranged
    } else {
        return Err("invalid build".into());
    };
    let role = match v["role"].as_str() {
        Some("base") => CombatRole::Base,
        Some("aggro") => CombatRole::Aggro,
        Some("coverage") => CombatRole::Coverage,
        Some("both") => CombatRole::Both,
        _ => return Err("invalid role".into()),
    };
    let eq = v["natureEquivalence"]
        .as_str()
        .ok_or("nature equivalence missing")?
        .to_string();
    let id = v["id"]
        .as_str()
        .ok_or("configuration ID missing")?
        .to_string();
    let config = Configuration {
        id,
        dex,
        moves,
        tms,
        second,
        nature,
        ability,
        nature_equivalence: eq,
        style: style.clone(),
        role: role.clone(),
    };
    let (proxy_dps, coverage_types, own_type_attacks) = config_proxy(data, base, &config);
    mon.tms.clear();
    Ok(Candidate {
        config,
        branch: branch.clone(),
        stratum: stratum(dex, &style, &role, &branch),
        proxy_dps,
        coverage_types,
        own_type_attacks,
    })
}

fn generate_candidates(
    data: &Data,
    m: &Manifest,
) -> Result<(Vec<Candidate>, Vec<Candidate>, Value), String> {
    let mut candidates = Vec::new();
    let mut controls = Vec::new();
    let mut per_dex = Vec::new();
    let mut total_proposals = 0u64;
    let mut expanded = 0u64;
    let mut unavailable = Vec::new();
    for &dex in &m.dex {
        let base = data.dex.iter().find(|x| x.dex == dex).unwrap();
        let control_candidate = control(data, base);
        controls.push(control_candidate);
        let taught = base
            .tms
            .iter()
            .map(|&ix| data.moves[ix].id.clone())
            .collect::<Vec<_>>();
        let all = base.abilities.iter().flatten().next().map(String::as_str);
        let mon = data.configure(base, "hardy", all, &taught)?;
        let mut proposals: BTreeMap<Stratum, Vec<GroupProposal>> = BTreeMap::new();
        let mut proposal_count = 0u64;
        visit_groups(data, base, &mon, &mut |group| {
            let attack_styles = group
                .iter()
                .filter(|&&i| data.moves[i].is_attack())
                .map(|&i| data.moves[i].kind == Kind::Melee)
                .collect::<BTreeSet<_>>();
            if attack_styles.len() > 1 {
                return;
            }
            proposal_count += 1;
            let style = style_from_group(data, &group);
            let roles = roles_from_group(data, &group);
            let branch = if group
                .iter()
                .all(|i| base.pool.contains(i) || *i == base.start)
            {
                "optimized_no_tm"
            } else {
                "optimized_tm"
            };
            let proxy = group
                .iter()
                .map(|&ix| move_proxy(data, base, ix))
                .sum::<f64>();
            let mut types = BTreeSet::new();
            let mut own = 0;
            for &ix in &group {
                if data.moves[ix].is_attack() {
                    let ty = data.moves[ix].levels[0].ty;
                    types.insert(ty);
                    if base.types.contains(&ty) {
                        own += 1;
                    }
                }
            }
            for role in roles {
                let st = stratum(dex, &style, &role, branch);
                let bucket = proposals.entry(st).or_default();
                bucket.push(GroupProposal {
                    moves: group.clone(),
                    proxy,
                    coverage: types.len(),
                    own,
                });
                bucket.sort_by(group_order);
                bucket.truncate(m.policy.group_quota);
            }
        });
        total_proposals += proposal_count;
        let mut profile_proposals = 0u64;
        let mut found_strata = BTreeSet::new();
        let mut top: BTreeMap<Stratum, Vec<Candidate>> = BTreeMap::new();
        for (st, groups) in proposals {
            found_strata.insert(st.clone());
            let mut raw = Vec::new();
            for g in groups {
                let ids = g
                    .moves
                    .iter()
                    .map(|&ix| data.moves[ix].id.clone())
                    .collect::<Vec<_>>();
                let cfgs = selection::configurations(
                    data,
                    dex,
                    &[ids],
                    if st.style == "melee" {
                        BuildStyle::Melee
                    } else {
                        BuildStyle::Ranged
                    },
                    match st.role.as_str() {
                        "aggro" => CombatRole::Aggro,
                        "coverage" => CombatRole::Coverage,
                        "both" => CombatRole::Both,
                        _ => CombatRole::Base,
                    },
                )?;
                profile_proposals += cfgs.len() as u64;
                for config in cfgs {
                    let (proxy_dps, coverage_types, own_type_attacks) =
                        config_proxy(data, base, &config);
                    raw.push(Candidate {
                        branch: st.branch.clone(),
                        stratum: st.clone(),
                        config,
                        proxy_dps,
                        coverage_types,
                        own_type_attacks,
                    });
                }
            }
            // One nature profile per ability, then the cap. Equal proxies keep the earlier nature.
            let mut by_ability: BTreeMap<String, Candidate> = BTreeMap::new();
            for c in raw {
                let key = c.config.ability.clone().unwrap_or_else(|| "default".into());
                let replace = by_ability
                    .get(&key)
                    .is_none_or(|old| candidate_order(old, &c) == Ordering::Greater);
                if replace {
                    by_ability.insert(key, c);
                }
            }
            let mut list = by_ability.into_values().collect::<Vec<_>>();
            list.sort_by(candidate_order);
            list.truncate(m.policy.shortlist_per_stratum);
            top.insert(st, list);
        }
        expanded += profile_proposals;
        for (_, mut xs) in top {
            candidates.append(&mut xs);
        }
        let mut missing = Vec::new();
        for build in ["melee", "ranged"] {
            for role in ["base", "aggro", "coverage", "both"] {
                for branch in ["optimized_no_tm", "optimized_tm"] {
                    let st = Stratum {
                        dex,
                        style: build.into(),
                        role: role.into(),
                        branch: branch.into(),
                    };
                    if !found_strata.contains(&st) {
                        missing.push(json!({"dex":dex,"variantId":format!("{build}:{role}:{branch}"),"reason":"no legal proposal in bounded source-feature beam"}));
                    }
                }
            }
        }
        unavailable.extend(missing);
        per_dex.push(json!({"dex":dex,"boundedMoveProposals":proposal_count,"jointProfilesExpanded":profile_proposals,"retainedConfigurations":candidates.iter().filter(|c|c.config.dex==dex).count()}));
    }
    candidates.sort_by(|a, b| {
        a.config
            .dex
            .cmp(&b.config.dex)
            .then_with(|| a.stratum.cmp(&b.stratum))
            .then_with(|| candidate_order(a, b))
    });
    if candidates.len() as u64 > m.limits.max_configurations {
        return Err(format!("shortlist retained {} configurations above maxConfigurations {}; reduce groupsPerStratum/shortlistPerStratum",candidates.len(),m.limits.max_configurations));
    }
    let ledger = json!({"species":m.dex.len(),"boundedMoveProposals":total_proposals,"jointProfilesExpandedWithinGroupBeam":expanded,"retainedConfigurations":candidates.len(),"controls":controls.len(),"byDex":per_dex,"unavailable":unavailable});
    Ok((candidates, controls, ledger))
}

fn paired_interval(xs: &[f64]) -> Value {
    if xs.is_empty() {
        return json!({"n":0,"mean":null,"lower":null,"upper":null});
    }
    let n = xs.len();
    let mean = xs.iter().sum::<f64>() / n as f64;
    if n < 2 {
        return json!({"n":n,"mean":mean,"lower":null,"upper":null});
    }
    let var = xs.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / (n - 1) as f64;
    let critical = match n - 1 {
        1 => 12.706,
        2 => 4.303,
        3 => 3.182,
        4 => 2.776,
        5 => 2.571,
        6 => 2.447,
        7 => 2.365,
        8 => 2.306,
        9 => 2.262,
        10 => 2.228,
        11 => 2.201,
        12 => 2.179,
        13 => 2.160,
        14 => 2.145,
        15 => 2.131,
        16 => 2.120,
        17 => 2.110,
        18 => 2.101,
        19 => 2.093,
        20 => 2.086,
        21 => 2.080,
        22 => 2.074,
        23 => 2.069,
        24 => 2.064,
        25 => 2.060,
        26 => 2.056,
        27 => 2.052,
        28 => 2.048,
        29 => 2.045,
        _ => 1.96,
    };
    let half = critical * (var / (n as f64)).sqrt();
    json!({"n":n,"mean":mean,"lower":mean-half,"upper":mean+half})
}

fn build_opts(
    data: &Data,
    c: &Candidate,
    seed: u32,
    seconds: f64,
) -> Result<(Mon, usize, Opts), String> {
    let base = data
        .dex
        .iter()
        .find(|m| m.dex == c.config.dex)
        .ok_or("unknown configuration dex")?;
    let mon = data.configure(
        base,
        &c.config.nature,
        c.config.ability.as_deref(),
        &c.config.tms,
    )?;
    let ids = c
        .config
        .moves
        .iter()
        .map(|id| {
            data.move_ix
                .get(id)
                .copied()
                .ok_or_else(|| format!("unknown move {id}"))
        })
        .collect::<Result<Vec<_>, _>>()?;
    if ids.is_empty() || !mon.start_choices(&data.moves).contains(&ids[0]) {
        return Err("configuration lead became illegal".into());
    }
    let buff_ids = ids
        .iter()
        .copied()
        .filter(|&i| data.moves[i].kind_name == "buff")
        .collect::<Vec<_>>();
    let second = c
        .config
        .second
        .as_ref()
        .map(|s| {
            data.move_ix
                .get(s)
                .copied()
                .ok_or_else(|| format!("unknown second start {s}"))
        })
        .transpose()?;
    let companions = ids
        .iter()
        .copied()
        .filter(|&i| data.moves[i].is_attack() && i != ids[0] && Some(i) != second)
        .collect::<Vec<_>>();
    let mut ext = Ext::with_planned_buffs(data, buff_ids)?;
    ext.companions = companions;
    ext.initial_second = second;
    ext.bonded = true;
    ext.bosses = true;
    ext.ability = c.config.ability.clone();
    let opts = Opts {
        seed,
        seconds,
        cards: true,
        bot: Bot::Play,
        terrain: true,
        trace: false,
        ext,
    };
    Ok((mon, ids[0], opts))
}

fn run_one(
    data: &Data,
    tables: &Tables,
    c: &Candidate,
    seed: u32,
    seconds: f64,
) -> Result<Value, String> {
    let (mon, start, opts) = build_opts(data, c, seed, seconds)?;
    let r = run_match(&Libm, data, tables, &mon, start, &opts);
    Ok(
        json!({"seed":seed,"metrics":{"damage":r.dealt,"contactDamage":r.risk.damage,"contactSeconds":r.risk.contact_seconds,"trappedSeconds":r.risk.surrounded_seconds,"kills":r.kills,"bosses":r.bosses,"survivalSeconds":r.time}}),
    )
}

fn task_id(plan_hash: &str, cfg: &str, stage: &str, seed: u32) -> String {
    format!("{}", hash_value(&json!([plan_hash, cfg, stage, seed])))
}
fn atomic_json(path: &Path, v: &Value) -> Result<(), String> {
    if let Some(p) = path.parent() {
        fs::create_dir_all(p).map_err(|e| e.to_string())?;
    }
    let tmp = path.with_extension(format!("tmp-{}", std::process::id()));
    let mut f = File::create(&tmp).map_err(|e| e.to_string())?;
    f.write_all(&serde_json::to_vec_pretty(v).map_err(|e| e.to_string())?)
        .and_then(|_| f.sync_all())
        .map_err(|e| e.to_string())?;
    fs::rename(&tmp, path).map_err(|e| e.to_string())?;
    Ok(())
}
struct CacheLock {
    path: PathBuf,
    _file: File,
}
impl CacheLock {
    fn acquire(path: PathBuf) -> Result<Self, String> {
        let file = OpenOptions::new().write(true).create_new(true).open(&path)
            .map_err(|_| "cache is locked by another run (remove a stale .production.lock after verifying no process owns it)".to_string())?;
        Ok(Self { path, _file: file })
    }
}
impl Drop for CacheLock {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.path);
    }
}
fn write_plan(data: &Data, manifest: &Manifest, out: &str) -> Result<(), String> {
    let (candidates, controls, summary) = generate_candidates(data, manifest)?;
    let mut roster = Vec::new();
    for c in &candidates {
        roster.push(candidate_value(c));
    }
    for c in &controls {
        roster.push(candidate_value(c));
    }
    let mut ledger = Vec::new();
    for c in &roster {
        let id = c["id"].as_str().ok_or("roster id missing")?;
        for &seed in &manifest.screen {
            ledger.push(json!({"taskId":task_id(&manifest.hash,id,"screening",seed),"configurationId":id,"stage":"screening","seed":seed}));
        }
    }
    let mut by_stratum = BTreeMap::<Stratum, Vec<String>>::new();
    for c in &candidates {
        by_stratum
            .entry(c.stratum.clone())
            .or_default()
            .push(c.config.id.clone());
    }
    let templates=by_stratum.into_iter().map(|(st,ids)|json!({"dex":st.dex,"build":st.style,"role":st.role,"branch":st.branch,"allowedConfigurationIds":ids,"quota":manifest.policy.confirm_per_stratum,"seeds":manifest.confirm})).collect::<Vec<_>>();
    let screening_tasks = ledger.len() as u64;
    let confirmation_tasks = (templates
        .iter()
        .map(|t| {
            t["allowedConfigurationIds"]
                .as_array()
                .map(Vec::len)
                .unwrap_or(0)
                .min(manifest.policy.confirm_per_stratum)
        })
        .sum::<usize>()
        + controls.len()) as u64
        * manifest.confirm.len() as u64;
    let matches = screening_tasks + confirmation_tasks;
    if matches > MAX_LEDGER_TASKS || matches > manifest.limits.max_matches {
        return Err(format!("ledger has {matches} tasks, above task ceiling"));
    }
    let simulated = matches as f64 * manifest.seconds;
    if simulated > manifest.limits.max_simulated_seconds {
        return Err(format!(
            "ledger simulated seconds {simulated} exceeds configured ceiling {}",
            manifest.limits.max_simulated_seconds
        ));
    }
    let mut plan = json!({"schema":1,"policyVersion":POLICY_VERSION,"manifest":manifest.raw,"manifestHash":manifest.hash,"policyHash":hash_value(&manifest.raw["searchPolicy"]),"gameCommit":research::GAME_COMMIT,"engineFingerprint":research::fingerprint(),"rustc":manifest.rustc,"candidateRoster":roster,"ledger":{"screeningTasks":ledger,"confirmationTemplates":templates,"maxTasks":matches},"counts":{"tasksUpperBound":matches,"screeningTasks":screening_tasks,"confirmationTasksUpperBound":confirmation_tasks,"candidateConfigurations":candidates.len(),"controlConfigurations":controls.len(),"screeningSeeds":manifest.screen.len(),"confirmationSeeds":manifest.confirm.len(),"simulatedSecondsUpperBound":simulated},"search":summary,"rankingReady":false});
    let ph = hash_value(&plan);
    plan["planHash"] = json!(ph);
    atomic_json(Path::new(out), &plan)
}

#[derive(Clone)]
struct ParsedTask {
    task_id: String,
    config_id: String,
    stage: String,
    seed: u32,
}
fn read_cached_rows(cache: &Path, tasks: &[ParsedTask]) -> Result<Vec<Value>, String> {
    let mut rows = Vec::new();
    for t in tasks {
        let p = cache.join(format!("{}.json", t.task_id));
        if p.exists() {
            rows.push(
                serde_json::from_slice(&fs::read(p).map_err(|e| e.to_string())?)
                    .map_err(|e| e.to_string())?,
            );
        }
    }
    Ok(rows)
}
fn nominate_confirmation(
    rows: &[Value],
    templates: &[Value],
    configs: &BTreeMap<String, Candidate>,
    m: &Manifest,
) -> BTreeMap<String, Vec<u32>> {
    // Index screening rows once. Lookups are then hash probes instead of scans over every row.
    let mut by_config: HashMap<&str, Vec<&Value>> = HashMap::new();
    let mut first_by_key: HashMap<(&str, u64), &Value> = HashMap::new();
    for row in rows {
        if row["stage"] != "screening" {
            continue;
        }
        let Some(id) = row["configurationId"].as_str() else {
            continue;
        };
        by_config.entry(id).or_default().push(row);
        if let Some(seed) = row["seed"].as_u64() {
            first_by_key.entry((id, seed)).or_insert(row);
        }
    }
    let mut out = BTreeMap::new();
    for t in templates {
        let dex = t["dex"].as_u64().unwrap_or(0) as u32;
        let control_id = configs
            .values()
            .find(|c| c.config.dex == dex && c.branch == "control_no_tm")
            .map(|c| c.config.id.as_str());
        let mut scores = Vec::new();
        for id in t["allowedConfigurationIds"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(Value::as_str)
        {
            let mut ds = [Vec::new(), Vec::new(), Vec::new(), Vec::new()];
            for row in by_config.get(id).into_iter().flatten() {
                let seed = row["seed"].as_u64().unwrap_or(u64::MAX);
                let Some(base) = control_id
                    .and_then(|cid| first_by_key.get(&(cid, seed)))
                    .and_then(|r| row_metrics(r))
                else {
                    continue;
                };
                let Some(a) = row_metrics(row) else { continue };
                let life = a["survivalSeconds"].as_f64().unwrap_or(0.);
                let base_life = base["survivalSeconds"].as_f64().unwrap_or(0.);
                let ae = normalized_exposure(a);
                let be = normalized_exposure(base);
                ds[0].push(life - base_life);
                ds[1].push(ae[0] - be[0]);
                ds[2].push(ae[1] - be[1]);
                ds[3].push(ae[2] - be[2]);
            }
            let mean = |v: &Vec<f64>| v.iter().sum::<f64>() / v.len().max(1) as f64;
            if ds[0].is_empty() {
                continue;
            }
            let safety = mean(&ds[1]) <= m.policy.exposure_margins[0]
                && mean(&ds[2]) <= m.policy.exposure_margins[1]
                && mean(&ds[3]) <= m.policy.exposure_margins[2];
            scores.push((id.to_owned(), safety, mean(&ds[0])));
        }
        scores.sort_by(|a, b| b.2.total_cmp(&a.2).then_with(|| a.0.cmp(&b.0)));
        let safe = scores
            .iter()
            .filter(|x| x.1)
            .map(|x| x.0.clone())
            .collect::<Vec<_>>();
        let chosen = if safe.is_empty() {
            scores
                .iter()
                .take(1)
                .map(|x| x.0.clone())
                .collect::<Vec<_>>()
        } else {
            safe.into_iter()
                .take(m.policy.confirm_per_stratum)
                .collect()
        };
        let seeds = t["seeds"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(Value::as_u64)
            .filter(|x| *x <= u32::MAX as u64)
            .map(|x| x as u32)
            .collect::<Vec<_>>();
        for id in chosen {
            out.insert(id, seeds.clone());
        }
    }
    for c in configs.values().filter(|c| c.branch == "control_no_tm") {
        out.insert(c.config.id.clone(), m.confirm.iter().copied().collect());
    }
    out
}
fn execute(data: &Data, plan_path: &str, cache_dir: &str, out: &str) -> Result<(), String> {
    let pv: Value = serde_json::from_slice(&fs::read(plan_path).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())?;
    if pv["schema"].as_u64() != Some(1) || pv["policyVersion"].as_str() != Some(POLICY_VERSION) {
        return Err("unsupported production plan".into());
    }
    if pv["gameCommit"].as_str() != Some(research::GAME_COMMIT)
        || pv["engineFingerprint"].as_str() != Some(research::fingerprint().as_str())
    {
        return Err("plan provenance does not match current game/engine".into());
    }
    let mut unsigned = pv.clone();
    unsigned
        .as_object_mut()
        .ok_or("plan must be object")?
        .remove("planHash");
    let ph = hash_value(&unsigned);
    if pv["planHash"].as_str() != Some(ph.as_str()) {
        return Err("plan hash mismatch".into());
    }
    let mv = pv["manifest"].clone();
    let manifest = parse_manifest_value(data, mv)?;
    if pv["rustc"].as_str() != Some(compiler_version().as_str()) {
        return Err("plan rustc version does not match current compiler".into());
    }
    if pv["manifestHash"].as_str() != Some(manifest.hash.as_str()) {
        return Err("manifest hash mismatch".into());
    }
    let mut configs = BTreeMap::new();
    for v in pv["candidateRoster"]
        .as_array()
        .ok_or("candidateRoster missing")?
    {
        let c = parse_candidate(data, v)?;
        if configs.insert(c.config.id.clone(), c).is_some() {
            return Err("duplicate configuration ID".into());
        }
    }
    let parse_task = |v: &Value| -> Result<ParsedTask, String> {
        Ok(ParsedTask {
            task_id: v["taskId"].as_str().ok_or("task id missing")?.into(),
            config_id: v["configurationId"]
                .as_str()
                .ok_or("config ID missing")?
                .into(),
            stage: v["stage"].as_str().ok_or("stage missing")?.into(),
            seed: v["seed"]
                .as_u64()
                .filter(|x| *x <= u32::MAX as u64)
                .ok_or("invalid seed")? as u32,
        })
    };
    let mut tasks = pv["ledger"]["screeningTasks"]
        .as_array()
        .ok_or("screeningTasks missing")?
        .iter()
        .map(parse_task)
        .collect::<Result<Vec<_>, _>>()?;
    let templates = pv["ledger"]["confirmationTemplates"]
        .as_array()
        .ok_or("confirmationTemplates missing")?;
    if configs.len() > manifest.limits.max_configurations as usize {
        return Err("candidate roster exceeds maxConfigurations".into());
    }
    for t in templates {
        let dex = t["dex"].as_u64().ok_or("template dex missing")? as u32;
        let build = t["build"].as_str().ok_or("template build missing")?;
        let role = t["role"].as_str().ok_or("template role missing")?;
        let branch = t["branch"].as_str().ok_or("template branch missing")?;
        if t["quota"].as_u64() != Some(manifest.policy.confirm_per_stratum as u64)
            || t["seeds"] != json!(manifest.confirm)
        {
            return Err("confirmation template policy differs from manifest".into());
        }
        for id in t["allowedConfigurationIds"]
            .as_array()
            .ok_or("template IDs missing")?
        {
            let id = id.as_str().ok_or("template ID must be string")?;
            if !configs.get(id).is_some_and(|c| {
                c.config.dex == dex
                    && c.stratum.style == build
                    && c.stratum.role == role
                    && c.branch == branch
                    && c.branch != "control_no_tm"
            }) {
                return Err("confirmation template contains an unplanned configuration".into());
            }
        }
    }
    if pv["ledger"]["maxTasks"].as_u64().unwrap_or(u64::MAX) > MAX_LEDGER_TASKS
        || pv["ledger"]["maxTasks"].as_u64().unwrap_or(u64::MAX) > manifest.limits.max_matches
    {
        return Err("ledger exceeds execution ceiling".into());
    }
    let mut seen = BTreeSet::new();
    for t in &tasks {
        if !seen.insert(t.task_id.clone())
            || !configs.contains_key(&t.config_id)
            || t.stage != "screening"
        {
            return Err("ledger contains duplicate or unplanned task".into());
        }
    }
    let cache = PathBuf::from(cache_dir);
    fs::create_dir_all(&cache).map_err(|e| e.to_string())?;
    let lock = cache.join(".production.lock");
    let _lock = CacheLock::acquire(lock)?;
    let began = Instant::now();
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(manifest.limits.threads)
        .build()
        .map_err(|e| e.to_string())?;
    let tables = Tables::new();
    let mut failures = 0u32;
    let mut failed_now = BTreeSet::new();
    let mut failure_rows = Vec::new();
    let mut run_stage = |stage_tasks: &[ParsedTask]| -> Result<(), String> {
        // Pending tasks are listed once per stage; the cursor only moves forward.
        let pending = stage_tasks
            .iter()
            .filter(|t| !cache.join(format!("{}.json", t.task_id)).exists())
            .collect::<Vec<_>>();
        let batch_size = manifest.limits.threads * 16;
        let mut cursor = 0;
        while cursor < pending.len() {
            if began.elapsed().as_secs_f64() >= manifest.limits.max_wall_seconds {
                break;
            }
            let mut batch = Vec::with_capacity(batch_size);
            while cursor < pending.len() && batch.len() < batch_size {
                let task = pending[cursor];
                cursor += 1;
                if !failed_now.contains(&task.task_id) {
                    batch.push(task);
                }
            }
            if batch.is_empty() {
                break;
            }
            // Each worker writes its own checkpoint, so writes overlap instead of queueing
            // behind the slowest match of the batch. Outer Err = I/O failure (hard stop);
            // inner Some = a match failure, counted against the failed-task budget.
            let outcomes = pool.install(|| {
                batch
                    .par_iter()
                    .map(|t| {
                        let c = &configs[&t.config_id];
                        match run_one(data, &tables, c, t.seed, manifest.seconds) {
                            Ok(row) => {
                                let v = json!({"taskId":t.task_id,"configurationId":t.config_id,"stage":t.stage,"seed":t.seed,"row":row});
                                atomic_json(&cache.join(format!("{}.json", t.task_id)), &v).map(|_| None)
                            }
                            Err(e) => Ok(Some(e)),
                        }
                    })
                    .collect::<Vec<Result<Option<String>, String>>>()
            });
            for (task, outcome) in batch.iter().zip(outcomes) {
                match outcome? {
                    None => {}
                    Some(e) => {
                        failures += 1;
                        failed_now.insert(task.task_id.clone());
                        failure_rows.push(json!({"taskId":task.task_id,"error":e}));
                        if failures > manifest.limits.max_failed_tasks {
                            return Err(format!("failed-task budget exceeded: {e}"));
                        }
                    }
                }
            }
        }
        Ok(())
    };
    run_stage(&tasks)?;
    let screen_rows = read_cached_rows(&cache, &tasks)?;
    let selected = if screen_rows.len() == tasks.len() {
        nominate_confirmation(&screen_rows, templates, &configs, &manifest)
    } else {
        BTreeMap::new()
    };
    for (id, seeds) in selected {
        for seed in seeds {
            let tid = task_id(&manifest.hash, &id, "confirmation", seed);
            if !seen.insert(tid.clone()) {
                return Err("duplicate confirmation task".into());
            }
            tasks.push(ParsedTask {
                task_id: tid,
                config_id: id.clone(),
                stage: "confirmation".into(),
                seed,
            });
        }
    }
    if tasks.len() as u64 > pv["ledger"]["maxTasks"].as_u64().unwrap_or(0) {
        return Err("dynamic confirmation exceeded plan upper bound".into());
    }
    run_stage(
        &tasks
            .iter()
            .filter(|t| t.stage == "confirmation")
            .cloned()
            .collect::<Vec<_>>(),
    )?;
    drop(run_stage);
    let mut rows = read_cached_rows(&cache, &tasks)?;
    let mut missing = Vec::new();
    for t in &tasks {
        if !cache.join(format!("{}.json", t.task_id)).exists() {
            missing.push(t.task_id.clone());
        }
    }
    rows.sort_by(|a, b| a["taskId"].as_str().cmp(&b["taskId"].as_str()));
    let winners = analyze_winners(&pv, &rows, &manifest);
    let result = json!({"schema":1,"planHash":ph,"manifestHash":manifest.hash,"policyHash":hash_value(&manifest.raw["searchPolicy"]),"gameCommit":research::GAME_COMMIT,"engineFingerprint":research::fingerprint(),"policyVersion":POLICY_VERSION,"selectionMethod":SELECTION_METHOD,"rankingReady":false,"winnerConfirmedMeans":"confirmation stage completed and exposure/survival noninferiority criteria passed; no statistical superiority claim","elapsedWallSeconds":began.elapsed().as_secs_f64(),"threads":manifest.limits.threads,"failureCount":failures,"failures":failure_rows,"completedTasks":rows.len(),"missingTasks":missing,"observations":rows,"winners":winners,"unavailable":pv["search"]["unavailable"]});
    atomic_json(Path::new(out), &result)?;
    Ok(())
}

fn row_metrics<'a>(row: &'a Value) -> Option<&'a Value> {
    Some(&row["row"]["metrics"])
}
fn normalized_exposure(m: &Value) -> [f64; 3] {
    let life = m["survivalSeconds"].as_f64().unwrap_or(0.).max(1.);
    [
        m["contactDamage"].as_f64().unwrap_or(0.) * 60. / life,
        m["contactSeconds"].as_f64().unwrap_or(0.) / life,
        m["trappedSeconds"].as_f64().unwrap_or(0.) / life,
    ]
}
fn analyze_winners(plan: &Value, rows: &[Value], m: &Manifest) -> Vec<Value> {
    let roster = plan["candidateRoster"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    let mut winners = Vec::new();
    let controls = roster
        .iter()
        .filter(|c| c["branch"] == "control_no_tm")
        .collect::<Vec<_>>();
    let mut strata = BTreeMap::<(u32, String, String, String), Vec<&Value>>::new();
    for c in &roster {
        if c["branch"] == "control_no_tm" {
            continue;
        }
        let key = (
            c["dex"].as_u64().unwrap_or(0) as u32,
            c["build"].as_str().unwrap_or("").into(),
            c["role"].as_str().unwrap_or("").into(),
            c["branch"].as_str().unwrap_or("").into(),
        );
        strata.entry(key).or_default().push(c);
    }
    let mut confirmed_rows: HashMap<&str, Vec<&Value>> = HashMap::new();
    for row in rows.iter().filter(|r| r["stage"] == "confirmation") {
        if let Some(id) = row["configurationId"].as_str() {
            confirmed_rows.entry(id).or_default().push(row);
        }
    }
    let confirmed = confirmed_rows.keys().copied().collect::<BTreeSet<&str>>();
    for ((dex, build, role, branch), cs) in strata {
        let cs = cs
            .into_iter()
            .filter(|c| confirmed.contains(c["id"].as_str().unwrap_or("")))
            .collect::<Vec<_>>();
        if cs.is_empty() {
            winners.push(json!({"dex":dex,"variantId":format!("{build}:{role}:{branch}"),"status":"inconclusive","winnerConfirmed":false,"confidenceUnresolved":true,"configuration":null,"reason":"No candidate completed independent confirmation; screening or wall-time budget was incomplete."}));
            continue;
        }
        let mut evaluated = Vec::new();
        let control = controls
            .iter()
            .find(|c| c["dex"].as_u64() == Some(dex as u64));
        for c in cs {
            let id = c["id"].as_str().unwrap_or("");
            let mut paired = BTreeMap::<u32, (Option<&Value>, Option<&Value>)>::new();
            for row in confirmed_rows.get(id).into_iter().flatten() {
                let seed = row["seed"].as_u64().unwrap_or(u64::MAX) as u32;
                paired.entry(seed).or_default().0 = row_metrics(row);
            }
            let control_id = control.and_then(|base| base["id"].as_str());
            for row in control_id
                .and_then(|cid| confirmed_rows.get(cid))
                .into_iter()
                .flatten()
            {
                let seed = row["seed"].as_u64().unwrap_or(u64::MAX) as u32;
                paired.entry(seed).or_default().1 = row_metrics(row);
            }
            let mut ds = [Vec::new(), Vec::new(), Vec::new(), Vec::new()];
            let mut seed_rows = Vec::new();
            for (seed, (a, b)) in paired {
                if let (Some(a), Some(b)) = (a, b) {
                    let ae = normalized_exposure(a);
                    let be = normalized_exposure(b);
                    let vals = [
                        a["survivalSeconds"].as_f64().unwrap_or(0.)
                            - b["survivalSeconds"].as_f64().unwrap_or(0.),
                        ae[0] - be[0],
                        ae[1] - be[1],
                        ae[2] - be[2],
                    ];
                    for j in 0..4 {
                        ds[j].push(vals[j]);
                    }
                    seed_rows.push(json!({"seed":seed,"candidate":a,"control":b,"delta":{"survivalSeconds":vals[0],"contactDamagePerMinute":vals[1],"contactFraction":vals[2],"trappedFraction":vals[3]}}));
                }
            }
            let intervals = ds.iter().map(|x| paired_interval(x)).collect::<Vec<_>>();
            let n = ds[0].len();
            let enough = n >= 2;
            let safety = enough
                && intervals[1]["upper"]
                    .as_f64()
                    .is_some_and(|x| x <= m.policy.exposure_margins[0])
                && intervals[2]["upper"]
                    .as_f64()
                    .is_some_and(|x| x <= m.policy.exposure_margins[1])
                && intervals[3]["upper"]
                    .as_f64()
                    .is_some_and(|x| x <= m.policy.exposure_margins[2])
                && intervals[0]["lower"]
                    .as_f64()
                    .is_some_and(|x| x >= -m.policy.survival_margin);
            evaluated.push((c.clone(), safety, enough, ds, intervals, seed_rows));
        }
        let safe = evaluated.iter().filter(|x| x.1).collect::<Vec<_>>();
        let best = safe.iter().max_by(|a, b| {
            a.3[0]
                .iter()
                .sum::<f64>()
                .total_cmp(&b.3[0].iter().sum::<f64>())
                .then_with(|| b.0["id"].as_str().cmp(&a.0["id"].as_str()))
        });
        let no_safe = safe.is_empty();
        let best_id = best.map(|b| b.0["id"].clone());
        let best_interval = best.map(|b| b.4[0].clone());
        for (c, is_safe, enough, ds, intervals, seed_rows) in evaluated {
            let status = if !enough {
                "inconclusive"
            } else if no_safe {
                "no_safe_candidate"
            } else if !is_safe {
                "unsafe"
            } else if let (Some(best_id), Some(best_iv)) = (&best_id, &best_interval) {
                if c["id"] == *best_id {
                    "best_observed"
                } else if intervals[0]["lower"]
                    .as_f64()
                    .zip(best_iv["upper"].as_f64())
                    .is_some_and(|(lo, hi)| lo <= hi)
                    && intervals[0]["upper"]
                        .as_f64()
                        .zip(best_iv["lower"].as_f64())
                        .is_some_and(|(hi, lo)| hi >= lo)
                {
                    "tied_best"
                } else {
                    "not_best_observed"
                }
            } else {
                "no_safe_candidate"
            };
            let delta = |i: usize| ds[i].iter().sum::<f64>() / (ds[i].len().max(1) as f64);
            winners.push(json!({"dex":dex,"variantId":format!("{build}:{role}:{branch}"),"status":status,"winnerConfirmed":enough&&is_safe,"confidenceUnresolved":!enough,"configuration":{"id":c["id"],"group":c["group"],"tms":c["tms"],"secondStart":c["secondStart"],"nature":c["nature"],"ability":c["ability"],"natureEquivalence":c["natureEquivalence"],"build":build,"role":role,"branch":branch},"pairedConfirmation":{"n":ds[0].len(),"survivalSeconds":intervals[0],"contactDamagePerMinute":intervals[1],"contactFraction":intervals[2],"trappedFraction":intervals[3],"meanDelta":{"survivalSeconds":delta(0),"contactDamagePerMinute":delta(1),"contactFraction":delta(2),"trappedFraction":delta(3)},"perSeed":seed_rows},"policyMargins":{"contactDamagePerMinute":m.policy.exposure_margins[0],"contactFraction":m.policy.exposure_margins[1],"trappedFraction":m.policy.exposure_margins[2],"survivalNoninferioritySeconds":m.policy.survival_margin}}));
        }
    }
    winners.sort_by(|a, b| {
        a["dex"]
            .as_u64()
            .cmp(&b["dex"].as_u64())
            .then_with(|| a["variantId"].as_str().cmp(&b["variantId"].as_str()))
    });
    winners
}

fn host_info() -> Value {
    let cpu = fs::read_to_string("/proc/cpuinfo")
        .ok()
        .and_then(|s| {
            s.lines()
                .find(|l| l.starts_with("model name"))
                .and_then(|l| l.split_once(':').map(|x| x.1.trim().to_string()))
        })
        .or_else(|| {
            Command::new("sysctl")
                .args(["-n", "machdep.cpu.brand_string"])
                .output()
                .ok()
                .filter(|o| o.status.success())
                .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        })
        .unwrap_or_else(|| "unknown".into());
    let quota = fs::read_to_string("/sys/fs/cgroup/cpu.max")
        .ok()
        .map(|s| s.trim().to_owned())
        .or_else(|| {
            fs::read_to_string("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
                .ok()
                .zip(fs::read_to_string("/sys/fs/cgroup/cpu/cpu.cfs_period_us").ok())
                .map(|(q, p)| format!("{}/{}", q.trim(), p.trim()))
        });
    json!({"architecture":std::env::consts::ARCH,"os":std::env::consts::OS,"cpuModel":cpu,"logicalCores":std::thread::available_parallelism().map(|n|n.get()).unwrap_or(1),"cgroupCpuQuota":quota})
}

fn benchmark(data: &Data, args: &[String]) -> Result<(), String> {
    if args.len() < 6 {
        return Err("usage: production benchmark <dex> <seed> <seconds<=15> <foes:10|20|30> <threads> <repetitions<=20> [mature]".into());
    }
    let dex = args[0].parse::<u32>().map_err(|_| "invalid dex")?;
    let seed = args[1].parse::<u32>().map_err(|_| "invalid seed")?;
    let seconds = args[2].parse::<f64>().map_err(|_| "invalid seconds")?;
    let foes = args[3].parse::<u8>().map_err(|_| "invalid foe count")?;
    let threads = args[4]
        .parse::<usize>()
        .map_err(|_| "invalid thread count")?;
    let reps = args[5]
        .parse::<usize>()
        .map_err(|_| "invalid repetitions")?;
    let mature = args.get(6).is_some_and(|s| s == "mature");
    if !seconds.is_finite()
        || seconds <= 0.
        || seconds > 15.
        || !matches!(foes, 10 | 20 | 30)
        || threads == 0
        || threads > 256
        || reps == 0
        || reps > 20
    {
        return Err(
            "benchmark bounds: seconds in (0,15], foes 10/20/30, threads 1..256, repetitions 1..20"
                .into(),
        );
    }
    let base = data
        .dex
        .iter()
        .find(|m| m.dex == dex)
        .ok_or_else(|| format!("unknown dex {dex}"))?;
    let nature = "hardy";
    let ability = base.abilities.iter().flatten().next().cloned();
    let mon = data.configure(base, nature, ability.as_deref(), &[])?;
    let start = base.start;
    let tables = Tables::new();
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(threads)
        .build()
        .map_err(|e| e.to_string())?;
    let wall = Instant::now();
    let samples = pool.install(|| {
        (0..reps)
            .into_par_iter()
            .map(|i| {
                let o = Opts {
                    seed: seed.wrapping_add(i as u32),
                    seconds,
                    cards: true,
                    bot: Bot::Play,
                    terrain: true,
                    trace: false,
                    ext: Ext::default(),
                };
                let begin = Instant::now();
                let result = crate::engine::benchmark_scene(
                    &Libm, data, &tables, &mon, start, &o, foes, mature,
                );
                (begin.elapsed().as_secs_f64(), result)
            })
            .collect::<Vec<_>>()
    });
    let elapsed = wall.elapsed().as_secs_f64();
    let mut times = Vec::new();
    let mut sims = Vec::new();
    for (sec, r) in samples {
        times.push(sec);
        sims.push(r?.seconds);
    }
    let total_sim = sims.iter().sum::<f64>();
    let mut sorted = times.clone();
    sorted.sort_by(f64::total_cmp);
    let mean_wall = times.iter().sum::<f64>() / times.len() as f64;
    println!("{}",serde_json::to_string_pretty(&json!({"benchmark":"mature_scene_cpu_only","rankingReady":false,"sceneSeconds":seconds,"foes":foes,"matureFixture":mature,"repetitions":reps,"threads":threads,"elapsedWallSeconds":elapsed,"meanScenarioWallSeconds":mean_wall,"p95ScenarioWallSeconds":sorted[((sorted.len()-1)*95)/100],"aggregateSimulatedSeconds":total_sim,"simulatedSecondsPerWallSecond":total_sim/elapsed,"host":host_info(),"provenance":{"engineFingerprint":research::fingerprint(),"gameCommit":research::GAME_COMMIT,"rustc":compiler_version()}})).map_err(|e|e.to_string())?);
    Ok(())
}

pub fn command(data: &Data, args: &[String]) {
    let result=match args.first().map(String::as_str){
        Some("plan") if args.len()==3=>parse_manifest(data,&args[1]).and_then(|m|write_plan(data,&m,&args[2])).map(|_|println!("plan written to {} (no matches executed)",args[2])),
        Some("run")|Some("resume") if args.len()==4=>execute(data,&args[1],&args[2],&args[3]),
        Some("benchmark")=>benchmark(data,&args[1..]),
        _=>Err("usage: production plan <manifest.json> <plan.json> | run|resume <plan.json> <cache-dir> <results.json> | benchmark <dex> <seed> <seconds<=15> <foes> <threads> <repetitions<=20> [mature]".into())
    };
    if let Err(e) = result {
        eprintln!("production: {e}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn data() -> Data {
        let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("../data/game.json");
        Data::load(path.to_str().unwrap())
    }

    #[test]
    fn normalized_exposure_does_not_penalize_longer_survival_by_itself() {
        let short = json!({"survivalSeconds":30.0,"contactDamage":30.0,"contactSeconds":3.0,"trappedSeconds":1.0});
        let long = json!({"survivalSeconds":300.0,"contactDamage":300.0,"contactSeconds":30.0,"trappedSeconds":10.0});
        let a = normalized_exposure(&short);
        let b = normalized_exposure(&long);
        for i in 0..3 {
            assert!((a[i] - b[i]).abs() < 1e-12);
        }
    }

    #[test]
    fn paired_interval_marks_single_seed_unresolved_and_is_symmetric() {
        let one = paired_interval(&[4.0]);
        assert!(one["lower"].is_null() && one["upper"].is_null());
        let ci = paired_interval(&[2.0, 4.0, 6.0]);
        assert_eq!(ci["mean"].as_f64(), Some(4.0));
        assert!(
            (ci["mean"].as_f64().unwrap()
                - ci["lower"].as_f64().unwrap()
                - (ci["upper"].as_f64().unwrap() - ci["mean"].as_f64().unwrap()))
            .abs()
                < 1e-12
        );
    }

    #[test]
    fn role_proposals_keep_base_aggro_coverage_and_both_semantics_distinct() {
        let data = data();
        let attacks = data
            .moves
            .iter()
            .enumerate()
            .filter(|(_, m)| m.is_attack())
            .map(|(i, _)| i)
            .collect::<Vec<_>>();
        let pair = (
            attacks
                .iter()
                .find(|&&a| {
                    attacks
                        .iter()
                        .any(|&b| data.moves[a].levels[0].ty != data.moves[b].levels[0].ty)
                })
                .copied()
                .unwrap(),
            *attacks
                .iter()
                .find(|&&b| data.moves[b].levels[0].ty != data.moves[attacks[0]].levels[0].ty)
                .unwrap(),
        );
        let offense = data
            .moves
            .iter()
            .position(|m| matches!(m.levels[0].buff, 1 | 5 | 6))
            .unwrap();
        let defense = data
            .moves
            .iter()
            .position(|m| matches!(m.levels[0].buff, 2 | 3 | 4))
            .unwrap();
        let with_offense = roles_from_group(&data, &[pair.0, pair.1, offense]);
        assert!(
            with_offense.contains(&CombatRole::Base)
                && with_offense.contains(&CombatRole::Aggro)
                && with_offense.contains(&CombatRole::Coverage)
                && with_offense.contains(&CombatRole::Both)
        );
        let with_defense = roles_from_group(&data, &[pair.0, pair.1, offense, defense]);
        assert!(
            with_defense.contains(&CombatRole::Base)
                && with_defense.contains(&CombatRole::Coverage)
        );
        assert!(
            !with_defense.contains(&CombatRole::Aggro) && !with_defense.contains(&CombatRole::Both)
        );
    }

    #[test]
    fn manifest_rejects_duplicate_and_overlapping_seed_blocks() {
        let data = data();
        let mut value = json!({"schema":1,"gameCommit":research::GAME_COMMIT,"engineFingerprint":research::fingerprint(),"policyVersion":POLICY_VERSION,"dex":[data.dex[0].dex],"screeningSeeds":[1,1],"confirmationSeeds":[2],"secondsPerMatch":15,"limits":{"maxConfigurations":1,"maxMatches":100,"maxSimulatedSeconds":1500,"maxWallSeconds":30,"maxFailedTasks":1,"threads":1},"searchPolicy":{"version":POLICY_VERSION,"groupsPerStratum":1,"shortlistPerStratum":1,"confirmPerStratum":1,"exposureMargins":{"contactDamagePerMinute":0,"contactFraction":0,"trappedFraction":0},"survivalNoninferioritySeconds":0}});
        assert!(parse_manifest_value(&data, value.clone())
            .unwrap_err()
            .contains("duplicate screeningSeeds"));
        value["screeningSeeds"] = json!([1]);
        value["confirmationSeeds"] = json!([1]);
        assert!(parse_manifest_value(&data, value)
            .unwrap_err()
            .contains("disjoint"));
    }

    #[test]
    fn aggro_prior_prefers_huge_power_over_the_alphabetically_earlier_ability() {
        let data = data();
        let base = data.dex.iter().find(|m| m.dex == 184).unwrap();
        let physical = base
            .pool
            .iter()
            .copied()
            .chain(std::iter::once(base.start))
            .find(|&i| data.moves[i].is_attack() && data.moves[i].levels[0].cat == 1)
            .unwrap();
        let cfgs = selection::configurations(
            &data,
            184,
            &[vec![data.moves[physical].id.clone()]],
            BuildStyle::Melee,
            CombatRole::Aggro,
        )
        .unwrap();
        let best = |ability: &str| {
            cfgs.iter()
                .filter(|c| c.ability.as_deref() == Some(ability))
                .map(|c| config_proxy(&data, base, c).0)
                .fold(f64::MIN, f64::max)
        };
        assert!(best("huge-power") > best("thick-fat"));
        assert!(best("huge-power") > best("sap-sipper"));
    }
}
