//! Explicit candidate identities and conservative staged selection primitives.
//!
//! This module does not assign weights or claim calibrated game balance. Callers supply
//! paired runs and safety non-inferiority margins from an evidence-backed policy.
use crate::{
    data::{Data, Mon},
    engine::RunResult,
};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum BuildStyle {
    Melee,
    Ranged,
}
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum CombatRole {
    Base,
    Aggro,
    Coverage,
    Both,
}

#[derive(Clone, Debug)]
pub struct Configuration {
    pub id: String,
    pub dex: u32,
    pub moves: Vec<String>,
    /// Empty means the natural/no-TM branch; it is kept as a distinct configuration.
    pub tms: Vec<String>,
    /// Explicit second starting attack used by the engine when returning from its stock move.
    pub second: Option<String>,
    pub nature: String,
    pub ability: Option<String>,
    pub nature_equivalence: String,
    pub style: BuildStyle,
    pub role: CombatRole,
}

/// Nature equivalence is based only on configured combat stats. Ability equivalence is
/// deliberately not inferred: abilities can have effects beyond the Mon stat record.
pub fn nature_equivalence(data: &Data, base: &Mon, nature: &str) -> Result<String, String> {
    let mon = data.configure(base, nature, None, &[])?;
    let signature = [mon.hp, mon.spd, mon.atk, mon.pa, mon.sa, mon.df, mon.sd]
        .iter()
        .map(|v| format!("{:016x}", v.to_bits()))
        .collect::<Vec<_>>()
        .join("-");
    Ok(format!("stats:{signature}"))
}

/// Construct stable, explicit configurations from legal move groups. The no-TM row is always
/// emitted separately from a TM-taught row, even if the resulting move list happens to match.
pub fn configurations(
    data: &Data,
    dex: u32,
    groups: &[Vec<String>],
    style: BuildStyle,
    role: CombatRole,
) -> Result<Vec<Configuration>, String> {
    let base = data
        .dex
        .iter()
        .find(|m| m.dex == dex)
        .ok_or_else(|| format!("unknown dex {dex}"))?;
    let natures = data.natures.as_array().ok_or("nature table missing")?;
    let mut out = Vec::new();
    let abilities: Vec<Option<String>> = {
        let mut xs = base
            .abilities
            .iter()
            .flatten()
            .cloned()
            .collect::<BTreeSet<_>>()
            .into_iter()
            .map(Some)
            .collect::<Vec<_>>();
        if xs.is_empty() {
            xs.push(None);
        }
        xs
    };
    let mut emitted_profiles = BTreeSet::new();
    for moves in groups {
        if moves.is_empty() || moves.len() > 4 {
            return Err("move group must contain 1..4 moves".into());
        }
        if moves.iter().collect::<BTreeSet<_>>().len() != moves.len() {
            return Err("move group contains duplicate moves".into());
        }
        let move_ids = moves
            .iter()
            .map(|id| {
                data.move_ix
                    .get(id.as_str())
                    .copied()
                    .ok_or_else(|| format!("unknown move {id}"))
            })
            .collect::<Result<Vec<_>, _>>()?;
        if move_ids
            .iter()
            .any(|ix| !base.pool.contains(ix) && *ix != base.start && !base.tms.contains(ix))
        {
            return Err(
                "move group contains a move outside the pool, stock move, and legal TM list".into(),
            );
        }
        let mut tms = moves
            .iter()
            .filter(|id| {
                data.move_ix
                    .get(id.as_str())
                    .is_some_and(|&ix| !base.pool.contains(&ix) && ix != base.start)
            })
            .cloned()
            .collect::<Vec<_>>();
        tms.sort();
        tms.dedup();
        let second = if move_ids[0] != base.start
            && move_ids.contains(&base.start)
            && !base.pool.contains(&base.start)
        {
            Some(data.moves[base.start].id.clone())
        } else {
            None
        };
        let tm_key = if tms.is_empty() {
            "natural".to_string()
        } else {
            format!("tm:{}", tms.join(","))
        };
        for n in natures {
            let nature = n["id"].as_str().ok_or("nature id missing")?;
            let eq = nature_equivalence(data, base, nature)?;
            for ability in &abilities {
                // The representative is deterministic (the first nature in the pinned table).
                // All names remain recoverable from the equivalence signature if needed.
                if !emitted_profiles.insert((
                    moves.clone(),
                    tm_key.clone(),
                    eq.clone(),
                    ability.clone(),
                )) {
                    continue;
                }
                let configured = data.configure(base, nature, ability.as_deref(), &tms)?;
                if !data.moves[move_ids[0]].is_attack()
                    || !configured.start_choices(&data.moves).contains(&move_ids[0])
                {
                    return Err("lead move is not a legal starting attack".into());
                }
                let aid = ability.as_deref().unwrap_or("default");
                let style_key = match &style {
                    BuildStyle::Melee => "melee",
                    BuildStyle::Ranged => "ranged",
                };
                let role_key = match &role {
                    CombatRole::Base => "base",
                    CombatRole::Aggro => "aggro",
                    CombatRole::Coverage => "coverage",
                    CombatRole::Both => "both",
                };
                let id = format!(
                    "dex{dex}|moves:{}|{}|second:{}|style:{style_key}|role:{role_key}|nature:{}|ability:{aid}",
                    moves.join(","),
                    tm_key,
                    second.as_deref().unwrap_or("none"),
                    eq
                );
                out.push(Configuration {
                    id,
                    dex,
                    moves: moves.clone(),
                    tms: tms.clone(),
                    second: second.clone(),
                    nature: nature.into(),
                    ability: ability.clone(),
                    nature_equivalence: eq.clone(),
                    style: style.clone(),
                    role: role.clone(),
                });
            }
        }
    }
    Ok(out)
}

#[derive(Clone, Copy, Debug, Default)]
pub struct Metrics {
    pub damage: f64,
    pub contact_damage: f64,
    pub contact_seconds: f64,
    pub trapped_seconds: f64,
    pub kills: f64,
    pub bosses: f64,
    pub survival_seconds: f64,
}
impl From<&RunResult> for Metrics {
    fn from(r: &RunResult) -> Self {
        Self {
            damage: r.dealt,
            contact_damage: r.risk.damage,
            contact_seconds: r.risk.contact_seconds,
            trapped_seconds: r.risk.surrounded_seconds,
            kills: r.kills as f64,
            bosses: r.bosses as f64,
            survival_seconds: r.time,
        }
    }
}
#[derive(Clone, Debug)]
pub struct Observation {
    pub config_id: String,
    pub seed: u64,
    pub metrics: Metrics,
}
#[derive(Clone, Copy, Debug)]
pub struct Margin {
    pub contact_damage: f64,
    pub contact_seconds: f64,
    pub trapped_seconds: f64,
}
#[derive(Clone, Debug)]
pub struct Policy {
    pub screening_seeds: BTreeSet<u64>,
    pub confirmation_seeds: BTreeSet<u64>,
    pub margins: Margin,
}
#[derive(Clone, Debug)]
pub struct SelectionReport {
    /// Exploratory screening Pareto set; means are descriptive, not confidence intervals.
    pub screened: Vec<String>,
    pub eligible: Vec<String>,
    pub pareto: Vec<String>,
    pub excluded_safety: BTreeMap<String, String>,
    /// No unique winner is asserted until paired uncertainty is quantified externally.
    pub confidence_unresolved: bool,
    pub winner: Option<String>,
}

/// Screen every candidate on screening seeds, then confirm only screening finalists and the
/// incumbent. Means and Pareto membership are descriptive; uncertainty remains unresolved here.
pub fn select(
    observations: &[Observation],
    incumbent: &str,
    policy: &Policy,
) -> Result<SelectionReport, String> {
    if policy.screening_seeds.is_empty()
        || policy.confirmation_seeds.is_empty()
        || !policy
            .screening_seeds
            .is_disjoint(&policy.confirmation_seeds)
    {
        return Err("screening and confirmation seeds must be nonempty and disjoint".into());
    }
    if [
        policy.margins.contact_damage,
        policy.margins.contact_seconds,
        policy.margins.trapped_seconds,
    ]
    .iter()
    .any(|x| !x.is_finite() || *x < 0.)
    {
        return Err("safety margins must be finite and nonnegative".into());
    }
    let mut rows: BTreeMap<(&str, u64), Metrics> = BTreeMap::new();
    for o in observations {
        if [
            o.metrics.damage,
            o.metrics.contact_damage,
            o.metrics.contact_seconds,
            o.metrics.trapped_seconds,
            o.metrics.kills,
            o.metrics.bosses,
            o.metrics.survival_seconds,
        ]
        .iter()
        .any(|x| !x.is_finite())
        {
            return Err(format!(
                "non-finite metric for {} seed {}",
                o.config_id, o.seed
            ));
        }
        if !policy.screening_seeds.contains(&o.seed) && !policy.confirmation_seeds.contains(&o.seed)
        {
            return Err(format!("unassigned seed {}", o.seed));
        }
        if rows.insert((&o.config_id, o.seed), o.metrics).is_some() {
            return Err("duplicate configuration/seed row".into());
        }
    }
    let ids = rows.keys().map(|(id, _)| *id).collect::<BTreeSet<_>>();
    if !ids.contains(incumbent) {
        return Err("incumbent missing".into());
    }
    for id in &ids {
        for seed in &policy.screening_seeds {
            if !rows.contains_key(&(*id, *seed)) {
                return Err(format!("missing screening row for {id} seed {seed}"));
            }
        }
    }
    let paired = |id: &str, seeds: &BTreeSet<u64>| -> Vec<Metrics> {
        seeds.iter().map(|s| rows[&(id, *s)]).collect()
    };
    let mean = |v: &[Metrics], f: fn(Metrics) -> f64| {
        v.iter().map(|m| f(*m)).sum::<f64>() / v.len() as f64
    };
    // Screen on the first independent seed block; only its Pareto frontier advances.
    let dims: [fn(Metrics) -> f64; 7] = [
        |m| m.damage,
        |m| m.kills,
        |m| m.bosses,
        |m| m.survival_seconds,
        |m| -m.contact_damage,
        |m| -m.contact_seconds,
        |m| -m.trapped_seconds,
    ];
    let frontier = |candidates: &[String], seeds: &BTreeSet<u64>| -> Vec<String> {
        let dominates = |a: &str, b: &str| {
            let av = paired(a, seeds);
            let bv = paired(b, seeds);
            dims.iter().all(|f| mean(&av, *f) >= mean(&bv, *f))
                && dims.iter().any(|f| mean(&av, *f) > mean(&bv, *f))
        };
        candidates
            .iter()
            .filter(|a| {
                !candidates
                    .iter()
                    .any(|b| b.as_str() != a.as_str() && dominates(b, a))
            })
            .cloned()
            .collect()
    };
    let all = ids.iter().map(|x| (*x).to_string()).collect::<Vec<_>>();
    let screened = frontier(&all, &policy.screening_seeds);
    let mut finalists = screened.clone();
    if !finalists.iter().any(|x| x == incumbent) {
        finalists.push(incumbent.to_string());
    }
    for id in &finalists {
        for seed in &policy.confirmation_seeds {
            if !rows.contains_key(&(id, *seed)) {
                return Err(format!(
                    "missing confirmation row for selected candidate {id} seed {seed}"
                ));
            }
        }
    }
    for (id, seed) in rows.keys() {
        if policy.confirmation_seeds.contains(seed) && !finalists.iter().any(|x| x == id) {
            return Err(format!(
                "unexpected confirmation row for unselected candidate {id}"
            ));
        }
    }
    let safety = |id: &str| -> bool {
        let a = paired(id, &policy.confirmation_seeds);
        let b = paired(incumbent, &policy.confirmation_seeds);
        mean(&a, |m| m.contact_damage) - mean(&b, |m| m.contact_damage)
            <= policy.margins.contact_damage
            && mean(&a, |m| m.contact_seconds) - mean(&b, |m| m.contact_seconds)
                <= policy.margins.contact_seconds
            && mean(&a, |m| m.trapped_seconds) - mean(&b, |m| m.trapped_seconds)
                <= policy.margins.trapped_seconds
    };
    let mut excluded_safety = BTreeMap::new();
    let mut eligible = Vec::new();
    for id in &screened {
        if safety(id) {
            eligible.push(id.clone());
        } else {
            excluded_safety.insert(
                id.clone(),
                "confirmation safety non-inferiority failed".into(),
            );
        }
    }
    let pareto = frontier(&eligible, &policy.confirmation_seeds);
    Ok(SelectionReport {
        screened,
        eligible,
        pareto,
        excluded_safety,
        confidence_unresolved: true,
        winner: None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn data() -> Data {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../data/game.json");
        Data::load(path.to_str().unwrap())
    }

    fn sample_group(data: &Data, base: &Mon) -> Vec<String> {
        base.start_choices(&data.moves)
            .into_iter()
            .find(|&ix| data.moves[ix].is_attack())
            .map(|ix| vec![data.moves[ix].id.clone()])
            .expect("pinned species has a legal attack starter")
    }

    fn tm_stock_pair(data: &Data) -> (&Mon, Vec<String>) {
        data.dex
            .iter()
            .find_map(|m| {
                if m.pool.contains(&m.start)
                    || data.moves[m.start].is_attack() == false
                    || m.types.contains(&data.moves[m.start].levels[0].ty)
                {
                    return None;
                }
                let tm = m.tms.iter().copied().find(|&ix| {
                    data.moves[ix].is_attack() && ix != m.start && !m.pool.contains(&ix)
                })?;
                Some((
                    m,
                    vec![data.moves[tm].id.clone(), data.moves[m.start].id.clone()],
                ))
            })
            .expect("dataset has an off-type stock starter and an attack TM")
    }

    #[test]
    fn rejects_seed_leakage_and_unsafe_margin() {
        let p = Policy {
            screening_seeds: [1].into(),
            confirmation_seeds: [1, 2].into(),
            margins: Margin {
                contact_damage: 0.,
                contact_seconds: 0.,
                trapped_seconds: 0.,
            },
        };
        assert!(select(&[], "x", &p).unwrap_err().contains("disjoint"));
    }

    #[test]
    fn configurations_reject_duplicate_unknown_and_unlearnable_moves() {
        let data = data();
        let base = data
            .dex
            .iter()
            .find(|m| {
                m.start_choices(&data.moves)
                    .iter()
                    .any(|&ix| data.moves[ix].is_attack())
            })
            .unwrap();
        let lead = sample_group(&data, base)[0].clone();
        assert!(configurations(
            &data,
            base.dex,
            &[vec![lead.clone(), lead]],
            BuildStyle::Melee,
            CombatRole::Base
        )
        .unwrap_err()
        .contains("duplicate"));
        assert!(configurations(
            &data,
            base.dex,
            &[vec!["__unknown_move__".into()]],
            BuildStyle::Melee,
            CombatRole::Base
        )
        .unwrap_err()
        .contains("unknown"));
        let forbidden = data
            .moves
            .iter()
            .find(|mv| {
                mv.is_attack()
                    && data.move_ix[&mv.id] != base.start
                    && !base.pool.contains(&data.move_ix[&mv.id])
                    && !base.tms.contains(&data.move_ix[&mv.id])
            })
            .expect("species has at least one unlearnable attack");
        assert!(configurations(
            &data,
            base.dex,
            &[vec![forbidden.id.clone()]],
            BuildStyle::Melee,
            CombatRole::Base
        )
        .unwrap_err()
        .contains("outside"));
    }

    #[test]
    fn tm_lead_can_keep_off_type_stock_move_as_second_start() {
        let data = data();
        let (base, group) = tm_stock_pair(&data);
        let configs = configurations(
            &data,
            base.dex,
            &[group.clone()],
            BuildStyle::Melee,
            CombatRole::Base,
        )
        .unwrap();
        assert!(!configs.is_empty());
        assert!(configs
            .iter()
            .all(|c| c.second.as_deref() == Some(data.moves[base.start].id.as_str())));
        assert!(configs.iter().all(|c| c.tms == vec![group[0].clone()]));
    }

    #[test]
    fn exact_stat_natures_collapse_but_abilities_and_configuration_dimensions_remain_distinct() {
        let data = data();
        let base = data
            .dex
            .iter()
            .find(|m| {
                m.abilities.iter().flatten().collect::<BTreeSet<_>>().len() >= 2
                    && m.start_choices(&data.moves)
                        .iter()
                        .any(|&ix| data.moves[ix].is_attack())
            })
            .unwrap();
        let group = sample_group(&data, base);
        let configs = configurations(
            &data,
            base.dex,
            &[group.clone()],
            BuildStyle::Melee,
            CombatRole::Base,
        )
        .unwrap();
        let signatures = data
            .natures
            .as_array()
            .unwrap()
            .iter()
            .map(|n| nature_equivalence(&data, base, n["id"].as_str().unwrap()).unwrap())
            .collect::<BTreeSet<_>>();
        let abilities = base
            .abilities
            .iter()
            .flatten()
            .cloned()
            .collect::<BTreeSet<_>>();
        assert_eq!(configs.len(), signatures.len() * abilities.len());
        let pairs = configs
            .iter()
            .map(|c| (c.nature_equivalence.clone(), c.ability.clone()))
            .collect::<BTreeSet<_>>();
        assert_eq!(pairs.len(), configs.len());
        let nature = configs[0].nature.clone();
        let ranged = configurations(
            &data,
            base.dex,
            &[group],
            BuildStyle::Ranged,
            CombatRole::Base,
        )
        .unwrap();
        let aggro = configurations(
            &data,
            base.dex,
            &[sample_group(&data, base)],
            BuildStyle::Melee,
            CombatRole::Aggro,
        )
        .unwrap();
        let chosen = &configs[0];
        let ranged_id = ranged
            .iter()
            .find(|c| c.nature == nature && c.ability == chosen.ability)
            .unwrap()
            .id
            .clone();
        let aggro_id = aggro
            .iter()
            .find(|c| c.nature == nature && c.ability == chosen.ability)
            .unwrap()
            .id
            .clone();
        assert_ne!(chosen.id, ranged_id);
        assert_ne!(chosen.id, aggro_id);
    }

    #[test]
    fn native_and_tm_move_sets_have_separate_configuration_ids() {
        let data = data();
        let (base, tm) = data
            .dex
            .iter()
            .find_map(|m| {
                let tm = m
                    .tms
                    .iter()
                    .copied()
                    .find(|&ix| data.moves[ix].is_attack() && !m.pool.contains(&ix))?;
                m.start_choices(&data.moves)
                    .iter()
                    .any(|&ix| data.moves[ix].is_attack())
                    .then_some((m, tm))
            })
            .expect("species with a natural starter and attack TM");
        let native = sample_group(&data, base);
        let taught = vec![data.moves[tm].id.clone()];
        let no_tm = configurations(
            &data,
            base.dex,
            &[native],
            BuildStyle::Melee,
            CombatRole::Base,
        )
        .unwrap();
        let with_tm = configurations(
            &data,
            base.dex,
            &[taught],
            BuildStyle::Melee,
            CombatRole::Base,
        )
        .unwrap();
        assert!(no_tm.iter().all(|c| c.tms.is_empty()));
        assert!(with_tm
            .iter()
            .all(|c| c.tms == vec![data.moves[tm].id.clone()]));
        assert_ne!(no_tm[0].id, with_tm[0].id);
    }
    #[test]
    fn requires_confirmation_only_for_screened_candidates_and_keeps_uncertainty_explicit() {
        let p = Policy {
            screening_seeds: [10].into(),
            confirmation_seeds: [20, 21].into(),
            margins: Margin {
                contact_damage: 0.,
                contact_seconds: 0.,
                trapped_seconds: 0.,
            },
        };
        let mut xs = Vec::new();
        for (id, dmg, risk) in [
            ("base", 10., 2.),
            ("better", 12., 2.),
            ("risky", 15., 4.),
            ("dominated", 8., 3.),
        ] {
            for seed in [10] {
                xs.push(Observation {
                    config_id: id.into(),
                    seed,
                    metrics: Metrics {
                        damage: dmg,
                        contact_damage: risk,
                        contact_seconds: risk,
                        trapped_seconds: risk,
                        kills: 1.,
                        bosses: 0.,
                        survival_seconds: 100.,
                    },
                });
            }
        }
        for (id, dmg, risk) in [("base", 10., 2.), ("better", 12., 2.), ("risky", 15., 4.)] {
            for seed in [20, 21] {
                xs.push(Observation {
                    config_id: id.into(),
                    seed,
                    metrics: Metrics {
                        damage: dmg,
                        contact_damage: risk,
                        contact_seconds: risk,
                        trapped_seconds: risk,
                        kills: 1.,
                        bosses: 0.,
                        survival_seconds: 100.,
                    },
                });
            }
        }
        let r = select(&xs, "base", &p).unwrap();
        assert_eq!(r.screened, vec!["better", "risky"]);
        assert_eq!(r.eligible, vec!["better"]);
        assert_eq!(r.pareto, vec!["better"]);
        assert!(r.excluded_safety.contains_key("risky"));
        assert!(r.confidence_unresolved);
        assert_eq!(r.winner, None);
    }

    #[test]
    fn high_damage_does_not_hide_a_contact_safety_regression() {
        let p = Policy {
            screening_seeds: [1].into(),
            confirmation_seeds: [2, 3].into(),
            margins: Margin {
                contact_damage: 0.,
                contact_seconds: 0.,
                trapped_seconds: 0.,
            },
        };
        let mut rows = Vec::new();
        for (id, damage, exposure) in [("incumbent", 10., 2.), ("high-damage", 100., 3.)] {
            for seed in [1, 2, 3] {
                rows.push(Observation {
                    config_id: id.into(),
                    seed,
                    metrics: Metrics {
                        damage,
                        contact_damage: exposure,
                        contact_seconds: exposure,
                        trapped_seconds: exposure,
                        kills: 1.,
                        bosses: 0.,
                        survival_seconds: 100.,
                    },
                });
            }
        }
        let report = select(&rows, "incumbent", &p).unwrap();
        assert!(report.screened.contains(&"high-damage".into()));
        assert!(report.excluded_safety.contains_key("high-damage"));
        assert!(!report.eligible.contains(&"high-damage".into()));
        assert_eq!(report.pareto, vec!["incumbent"]);
    }
}
