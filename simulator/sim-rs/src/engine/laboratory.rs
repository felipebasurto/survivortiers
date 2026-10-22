//! Deterministic, bounded attack-laboratory scenes built on the real Match combat systems.
use super::*;

/// Runs a scripted stationary-player scene. `attacks[0]` is the lead and remaining entries are
/// bonded companions. `level` is the lead move level; companions and buffs clamp to their own
/// maximum levels. `scene` is `line`, `surround`, `approach`, or `boss`; `foes` is 1, 3 or 12.
/// Hostile contact is disabled by fixture policy.
pub fn laboratory_scene(
    data: &Data,
    attacks: &[usize],
    buffs: &[usize],
    scene: &str,
    foes: usize,
    level: usize,
    seconds: f64,
    seed: u32,
) -> Result<RunResult, String> {
    if attacks.is_empty() {
        return Err("laboratory scene requires at least one attack".into());
    }
    if attacks.len() > 4 {
        return Err("laboratory scene supports at most four bonded attacks".into());
    }
    if !matches!(scene, "line" | "surround" | "approach" | "boss") {
        return Err(format!("unknown laboratory scene {scene}"));
    }
    if !matches!(
        (scene, foes),
        ("boss", 1) | ("line" | "surround" | "approach", 3 | 12)
    ) {
        return Err("laboratory scene requires 3 or 12 foes; boss scene requires 1".into());
    }
    if !seconds.is_finite() || seconds <= 0.0 {
        return Err("laboratory scene duration must be finite and greater than zero".into());
    }
    for &ix in attacks {
        if data.moves.get(ix).is_none_or(|mv| !mv.is_attack()) {
            return Err(format!(
                "laboratory attack index {ix} is invalid or not an attack"
            ));
        }
    }
    let lead_max = data.moves[attacks[0]].max_lvl;
    if level == 0 || level > lead_max {
        return Err(format!("lead move level must be in 1..={lead_max}"));
    }
    if attacks.len() + buffs.len() > 4 {
        return Err("laboratory group supports at most four learned slots".into());
    }

    let neutral_data = neutral_data(data);
    let combo = neutral_data
        .combos
        .iter()
        .position(|types| types == &[0, 1])
        .unwrap_or(0) as u16;
    let mon = Mon {
        dex: 0,
        name: "Laboratory Mon".into(),
        // A dual type prevents the engine's single-type same-type attack bonus.
        types: vec![0, 1],
        combo,
        hp: 100_000.0,
        spd: 1.0,
        atk: 1.0,
        r: 12.0,
        pa: 1.0,
        sa: 1.0,
        df: 1.0,
        sd: 1.0,
        start: attacks[0],
        pool: Vec::new(),
        tms: Vec::new(),
        abilities: Vec::new(),
        leg: false,
        bst: 0.0,
    };
    let ext = Ext {
        planned_buffs: Some(buffs.to_vec()),
        companions: attacks[1..].to_vec(),
        bonded: true,
        ..Ext::default()
    };
    // Validate the same two-buff contract as assembled production groups.
    Ext::with_planned_buffs(&neutral_data, buffs.to_vec())?;
    let opts = Opts {
        seed,
        seconds,
        cards: false,
        bot: Bot::Repulse,
        terrain: false,
        trace: false,
        ext,
    };
    let math = Libm;
    let tables = Tables::new();
    let mut m = init_match(&math, &neutral_data, &tables, &mon, attacks[0], &opts);
    m.enemies.clear();
    // Only move levels vary: player cards, evolution, and game level remain at baseline.
    m.state.move_lvl = level;
    for (i, c) in m.comps.iter_mut().enumerate() {
        c.1 = level.min(m.data.moves[attacks[i + 1]].max_lvl);
    }
    m.state.sd = if m.has_sd {
        level.min(m.data.moves[m.atk_buff].max_lvl)
    } else {
        0
    };
    m.state.hd = if m.has_hd {
        level.min(m.data.moves[m.def_buff].max_lvl)
    } else {
        0
    };
    m.bonds = m.bond_order.len();
    m.learned.fill(true);
    m.stat_dirty = true;
    m.stats();
    m.pl.hp = m.st.max_hp;
    let target_hp = if scene == "boss" { 600.0 } else { 120.0 };
    let mut next_enemy = 0usize;
    for i in 0..foes {
        let e = lab_enemy(&m, scene, i, foes, next_enemy, target_hp);
        m.enemies.push(e);
        next_enemy += 1;
    }
    let max_time = seconds;
    while m.t < max_time {
        // Fixture policy: stationary and immune to hostile damage, status and knockback.
        m.pl.x = 0.0;
        m.pl.y = 0.0;
        m.pl.hp = m.st.max_hp.max(1.0);
        let step = DT.min(max_time - m.t);
        m.note_vel(step);
        m.t += step;
        m.ability_tick();
        m.stats();
        m.pl.inv = 0.0;
        m.decide();
        m.pl.dirx = 0.0;
        m.pl.diry = 0.0;
        m.step_enemies();
        m.tick_buffs();
        m.stats();
        if m.slot == 0 {
            m.atk_cd -= step;
            if m.atk_cd <= 0.0 {
                m.atk_cd = if m.cast() { m.cooled(m.st.mv.cd) } else { 0.05 };
            }
            m.cast_comps();
        }
        m.step_shots();
        if !m.fields.is_empty() {
            m.step_fields();
        }
        m.reap();
        reset_lab_progression(&mut m);
        while m.enemies.len() < foes {
            let e = lab_enemy(&m, scene, next_enemy % foes, foes, next_enemy, target_hp);
            m.enemies.push(e);
            next_enemy += 1;
        }
        m.stats();
        m.tick_stragglers();
        m.tick_specials();
        m.reap();
        reset_lab_progression(&mut m);
        while m.enemies.len() < foes {
            let e = lab_enemy(&m, scene, next_enemy % foes, foes, next_enemy, target_hp);
            m.enemies.push(e);
            next_enemy += 1;
        }
    }
    let damage = m.kills as f64 * target_hp
        + m.enemies
            .iter()
            .map(|e| (e.max - e.hp).max(0.0))
            .sum::<f64>();
    m.stats();
    Ok(RunResult {
        time: max_time,
        kills: m.kills,
        bosses: m.bosses,
        coins: 0.0,
        level: m.level,
        capped: true,
        status_ignored: false,
        hp: m.st.max_hp,
        max_hp: m.st.max_hp,
        hp_frac: 1.0,
        dealt: damage,
        risk: Exposure::default(),
    })
}

fn reset_lab_progression<M: MathFns>(m: &mut Match<'_, M>) {
    // The game assigns XP on enemy death. Laboratory fixtures hold player progression fixed.
    m.xp = 0.0;
    m.level = 1;
    m.need = xp_for(m.math, 1);
    m.orbs.clear();
}

fn neutral_data(data: &Data) -> Data {
    Data {
        commit: data.commit.clone(),
        natures: data.natures.clone(),
        combos: data.combos.clone(),
        moves: data.moves.clone(),
        move_ix: data.move_ix.clone(),
        dex: Vec::new(),
        tiers: Vec::new(),
        tmult: data.tmult.iter().map(|row| vec![1.0; row.len()]).collect(),
        swords_dance: data.swords_dance,
        harden: data.harden,
        dragon_dance: data.dragon_dance,
        agility: data.agility,
        nasty_plot: data.nasty_plot,
        tm_prices: data.tm_prices.clone(),
    }
}

fn lab_enemy(
    m: &Match<'_, Libm>,
    scene: &str,
    ix: usize,
    foes: usize,
    id: usize,
    hp: f64,
) -> Enemy {
    let mut e = blank_enemy(hp, 0.0, m.mon.combo, 0, 1.0);
    e.max = hp;
    e.xp = 0.0;
    e.beh = Beh::Chase;
    e.def.beh = Beh::Chase;
    e.def.hp = hp;
    e.def.spd = if scene == "approach" { 62.0 } else { 0.0 };
    e.spd = e.def.spd;
    e.dmg = 0.0;
    e.def.dmg = 0.0;
    e.touch = 0.0;
    // `blank_enemy` defaults fuse to zero for transient scripted hazards. Ordinary
    // benchmark enemies explicitly disable it; otherwise each fixture explodes
    // immediately and is counted as a kill on every engine tick.
    e.fuse = -1.0;
    e.boss = scene == "boss";
    e.g_phys = 1.0;
    e.g_spec = 1.0;
    if ix % foes == 0 {
        // One resistant target per scene: higher guard, while type chart remains neutral.
        e.g_phys = 0.35;
        e.g_spec = 0.35;
    }
    e.id = id as u32;
    let angle = std::f64::consts::TAU * (ix % foes) as f64 / foes as f64;
    match scene {
        "boss" => {
            e.x = 35.0;
            e.y = 0.0;
        }
        "line" => {
            e.x = 32.0 + (ix % foes) as f64 * 12.0;
            e.y = 0.0;
        }
        "surround" => {
            let radius = 35.0 + (ix % 3) as f64 * 17.0;
            e.x = angle.cos() * radius;
            e.y = angle.sin() * radius;
        }
        _ => {
            let radius = 260.0 + (ix % 3) as f64 * 36.0;
            e.x = angle.cos() * radius;
            e.y = angle.sin() * radius;
        }
    }
    e.ai = Rng::new((m.opts.seed ^ (id as u32).wrapping_mul(0x9E37_79B9)).max(1));
    e
}

#[cfg(test)]
mod tests {
    use super::*;

    fn data() -> Data {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../data/game.json");
        Data::load(path.to_str().expect("dataset path"))
    }

    #[test]
    fn neutral_fixture_disables_type_advantage_and_mono_boost() {
        let data = data();
        let neutral = neutral_data(&data);
        assert!(neutral.tmult.iter().flatten().all(|&m| m == 1.0));
        assert_eq!(mono_factor(&[0, 1], 0), 1.0);
        assert_eq!(mono_factor(&[0, 1], 1), 1.0);
    }

    #[test]
    fn laboratory_is_reproducible_immune_and_replenishes_finite_targets() {
        let data = data();
        let tackle = *data.move_ix.get("tackle").expect("tackle fixture");
        let first = laboratory_scene(&data, &[tackle], &[], "boss", 1, 1, 60.0, 177).unwrap();
        let again = laboratory_scene(&data, &[tackle], &[], "boss", 1, 1, 60.0, 177).unwrap();
        assert!(first.dealt > 0.0, "lab attack must deal damage");
        assert!(
            first.kills > 0,
            "finite boss target should replenish after a kill"
        );
        assert_eq!(first.dealt, again.dealt);
        assert_eq!(first.kills, again.kills);
        assert_eq!(first.hp, first.max_hp);
        assert_eq!(first.hp_frac, 1.0);
        assert_eq!(first.risk.damage, 0.0);
        assert_eq!(first.risk.hits, 0);
        assert_eq!(first.level, 1, "move level must not grant player levels");
    }

    #[test]
    fn melee_meteor_burn_and_move_max_levels_produce_measured_damage() {
        let data = data();
        let ix = |id: &str| {
            *data
                .move_ix
                .get(id)
                .unwrap_or_else(|| panic!("missing {id}"))
        };
        let tackle = ix("tackle");
        let ember = ix("ember");
        let meteor = ix("meteor-mash");
        let melee = laboratory_scene(&data, &[tackle], &[], "boss", 1, 1, 6.0, 82).unwrap();
        let meteor_hit = laboratory_scene(&data, &[meteor], &[], "boss", 1, 1, 6.0, 82).unwrap();
        assert!(
            melee.dealt > 0.0,
            "close boss fixture must admit melee hits"
        );
        assert!(meteor_hit.dealt > 0.0, "meteor fixture must deal damage");

        // Keep the target alive long enough for ticks to be visible beside direct damage.
        let mut burn_input = neutral_data(&data);
        for lvl in &mut burn_input.moves[ember].levels {
            lvl.dmg *= 0.001;
        }
        let burn = laboratory_scene(&burn_input, &[ember], &[], "boss", 1, 1, 6.0, 82).unwrap();
        let mut no_dot = neutral_data(&burn_input);
        for lvl in &mut no_dot.moves[ember].levels {
            lvl.burn = f64::NAN;
            lvl.poison = f64::NAN;
            lvl.status = false;
        }
        let no_dot = laboratory_scene(&no_dot, &[ember], &[], "boss", 1, 1, 6.0, 82).unwrap();
        assert!(
            burn.dealt > no_dot.dealt,
            "HP-based lab accounting must include burn ticks: burn={} kills={}, direct={} kills={}",
            burn.dealt,
            burn.kills,
            no_dot.dealt,
            no_dot.kills
        );

        let max = data.moves[tackle].max_lvl;
        assert!(max > 1);
        let at_max = laboratory_scene(&data, &[tackle], &[], "boss", 1, max, 6.0, 82).unwrap();
        assert!(
            at_max.dealt > melee.dealt,
            "move max level should affect damage without player cards/evolution"
        );
        assert_eq!(
            at_max.level, 1,
            "move level-up must not change player level"
        );
    }
}
