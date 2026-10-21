//! The eight kinds of PokéSurvivor 66610d9 and the monotype bonus, checked against the numbers and the
//! frame order of js/systems/combat.js, projectile.js, enemy.js and player.js at 5a23d49. The scenes run
//! the same per-frame calls as `run_match` (cast, fields, shots, enemies) with the player standing still.
//! `simulator/validate/game_formulas.js` runs the game's own functions against `pokesim formulas`.

use super::*;
use crate::math::Libm;
use std::sync::OnceLock;

static LIBM: Libm = Libm;
static DATA: OnceLock<Data> = OnceLock::new();
static TABLES: OnceLock<Tables> = OnceLock::new();

fn dat() -> &'static Data {
    DATA.get_or_init(|| Data::load("../data/game.json"))
}

fn tables() -> &'static Tables {
    TABLES.get_or_init(Tables::new)
}

fn mon(dex: u32) -> &'static Mon {
    dat().dex.iter().find(|m| m.dex == dex).expect("dex")
}

fn mv(id: &str) -> usize {
    *dat().move_ix.get(id).unwrap_or_else(|| panic!("move {id}"))
}

fn lvl1(id: &str) -> &'static MoveLvl {
    &dat().moves[mv(id)].levels[0]
}

fn scene(dex: u32, move_id: &str) -> Match<'static, Libm> {
    scene_with_ext(dex, move_id, Ext::default())
}

fn scene_with_ext(dex: u32, move_id: &str, ext: Ext) -> Match<'static, Libm> {
    let opts: &'static Opts = Box::leak(Box::new(Opts {
        seed: 1,
        seconds: 15.0,
        cards: false,
        bot: Bot::Kite,
        terrain: false,
        trace: false,

        ext,
    }));
    let mut m = init_match(&LIBM, dat(), tables(), mon(dex), mv(move_id), opts);
    m.ability = Ability { id: "none" };
    m.pl.x = 0.0;
    m.pl.y = 0.0;
    m.stat_dirty = true;
    m.stats();
    m.pl.hp = m.st.max_hp;
    m
}

/// A combo the move's type hits for exactly x1, so expected damage is dmg * atk.
fn neutral_combo(ty: u8) -> u16 {
    dat()
        .dex
        .iter()
        .find(|d| dat().tmult[ty as usize][d.combo as usize] == 1.0)
        .expect("neutral combo")
        .combo
}

fn foe(m: &mut Match<'static, Libm>, ty: u8, x: f64, y: f64, boss: bool, spd: f64) -> usize {
    let mut e = blank_enemy(1e9, 0.0, neutral_combo(ty), 1, 1.0);
    e.x = x;
    e.y = y;
    e.spd = spd;
    e.boss = boss;
    e.fuse = -1.0;
    e.id = m.enemies.len() as _;
    e.max = 1e9;
    m.enemies.push(e);
    m.enemies.len() - 1
}

fn tick(m: &mut Match<'static, Libm>) {
    m.t += DT;
    m.stats();
    m.atk_cd -= DT;
    if m.atk_cd <= 0.0 {
        m.atk_cd = if m.cast() { m.cooled(m.st.mv.cd) } else { 0.05 };
    }
    if !m.fields.is_empty() {
        m.step_fields();
    }
    m.step_shots();
    m.stats();
    m.step_enemies();
    m.resolve_contact();
    m.resolve_enemy_shots();
    m.resolve_hazards();
}

fn lost(m: &Match<'static, Libm>, i: usize) -> f64 {
    1e9 - m.enemies[i].hp
}

fn per_hit(m: &Match<'static, Libm>, mvl: &MoveLvl, combo: u16) -> f64 {
    js_round(mvl.dmg * m.atk_for(mvl.cat, mvl.ty) * dat().tmult[mvl.ty as usize][combo as usize])
}

#[test]
fn data_has_the_38_new_moves_with_game_numbers() {
    let new = [
        "dragon-claw",
        "play-rough",
        "flame-charge",
        "u-turn",
        "dragon-breath",
        "ancient-power",
        "hyper-beam",
        "solar-beam",
        "rapid-spin",
        "rolling-kick",
        "outrage",
        "gyro-ball",
        "night-slash",
        "whirlpool",
        "sand-tomb",
        "ominous-wind",
        "seed-bomb",
        "electro-ball",
        "acid-spray",
        "signal-beam",
        "power-gem",
        "mirror-shot",
        "energy-ball",
        "mist-ball",
        "air-slash",
        "ice-shard",
        "shadow-sneak",
        "draining-kiss",
        "sucker-punch",
        "thunder-wave",
        "rock-tomb",
        "freeze-dry",
        "dynamic-punch",
        "extrasensory",
        "whirlwind",
        "vacuum-wave",
        "disarming-voice",
        "magnitude",
    ];
    assert_eq!(new.len(), 38);
    for id in new {
        assert!(dat().move_ix.contains_key(id), "{id} missing");
    }
    let spin = lvl1("rapid-spin");
    assert_eq!(
        (spin.xk, spin.dmg, spin.count, spin.radius, spin.cd),
        (12, 9.0, 3.0, 62.0, 1.0)
    );
    let quake = lvl1("magnitude");
    assert_eq!(
        (quake.xk, quake.dmg, quake.count, quake.radius, quake.cd),
        (13, 18.0, 6.0, 30.0, 1.15)
    );
    let vortex = lvl1("whirlpool");
    assert_eq!(
        (
            vortex.xk,
            vortex.dmg,
            vortex.radius,
            vortex.dur,
            vortex.pull
        ),
        (14, 8.0, 72.0, 2.6, 150.0)
    );
    let stun = lvl1("thunder-wave");
    assert_eq!(
        (stun.xk, stun.dmg, stun.radius, stun.stun),
        (16, 22.0, 58.0, 1.0)
    );
    let shove = lvl1("extrasensory");
    assert_eq!(
        (shove.xk, shove.dmg, shove.radius, shove.knock),
        (15, 16.0, 92.0, 320.0)
    );
    let charge = lvl1("hyper-beam");
    assert_eq!(
        (
            charge.xk,
            charge.dmg,
            charge.charge,
            charge.radius,
            charge.width
        ),
        (11, 58.0, 0.75, 300.0, 44.0)
    );
}

#[test]
fn every_type_has_five_attacks_except_dragon_which_has_four_in_the_game() {
    let mut per_type = [0usize; 18];
    for mvd in &dat().moves {
        let l = &mvd.levels[0];
        if l.buff == 0 {
            per_type[l.ty as usize] += 1;
        }
    }
    for (t, n) in per_type.iter().enumerate() {
        let want = if crate::data::TYPES[t] == "dragon" {
            4
        } else {
            5
        };
        assert!(*n >= want, "type {} has {n} attacks", crate::data::TYPES[t]);
    }
}

#[test]
fn monotype_hits_20_percent_harder_with_its_own_type_only() {
    let psychic = crate::data::TYPES
        .iter()
        .position(|t| *t == "psychic")
        .unwrap() as u8;
    let ghost = crate::data::TYPES
        .iter()
        .position(|t| *t == "ghost")
        .unwrap() as u8;
    let grass = crate::data::TYPES
        .iter()
        .position(|t| *t == "grass")
        .unwrap() as u8;
    let mewtwo = scene(150, "extrasensory");
    let own = mewtwo.atk_for(2, psychic);
    assert!((own / mewtwo.atk_for(2, ghost) - 1.2).abs() < 1e-12);
    let bulbasaur = scene(1, "seed-bomb");
    assert_eq!(bulbasaur.atk_for(1, grass), bulbasaur.atk_for(1, ghost));
}

#[test]
fn planned_buff_ids_support_mixed_scaling_and_aqua_ring_regen() {
    let sd = mv("swords-dance");
    let np = mv("nasty-plot");
    let aqua = mv("aqua-ring");
    let mut ext = Ext::with_planned_buffs(dat(), vec![sd, np]).expect("two scaling buffs");
    ext.item = Item::default();
    let mut m = scene_with_ext(25, "tackle", ext);
    m.tick_buffs();
    m.stat_dirty = true;
    m.stats();
    let expected_p = 1.0 + m.state.buff_effects[5].stacks * m.state.buff_effects[5].amount;
    let expected_s = 1.0 + m.state.buff_effects[6].stacks * m.state.buff_effects[6].amount;
    assert!((m.st.patk - expected_p).abs() < 1e-12);
    assert!((m.st.satk - expected_s).abs() < 1e-12);

    let ext = Ext::with_planned_buffs(dat(), vec![aqua, sd]).expect("Aqua Ring plus attack buff");
    let mut m = scene_with_ext(25, "tackle", ext);
    m.tick_buffs();
    m.stat_dirty = true;
    m.stats();
    assert!(m.st.regen >= lvl1("aqua-ring").amount);
}

#[test]
fn buffs_writing_the_same_stat_share_the_game_stack_cap_and_last_amount() {
    // player.js:addBuff writes one shared state per stat, so the later Dragon Dance
    // overwrites amount, adds to the existing stack count and sets the shared timer.
    let ext = Ext::with_planned_buffs(dat(), vec![mv("swords-dance"), mv("dragon-dance")])
        .expect("same-stat pair");
    let mut m = scene_with_ext(25, "tackle", ext);
    m.state.buff_effects[5] = BuffEffect {
        stacks: 4.0,
        time: 2.0,
        amount: lvl1("swords-dance").amount,
    };
    m.state.sd_cd = 10.0;
    m.state.hd_cd = 0.0;
    m.tick_buffs();
    assert_eq!(m.state.buff_effects[5].stacks, 5.0);
    assert_eq!(m.state.buff_effects[5].amount, lvl1("dragon-dance").amount);
    assert_eq!(m.state.buff_effects[5].time, lvl1("dragon-dance").dur);
    m.stat_dirty = true;
    m.stats();
    assert!((m.st.patk - (1.0 + 5.0 * lvl1("dragon-dance").amount)).abs() < 1e-12);
}

#[test]
fn planned_buff_constructor_rejects_nonbuff_duplicate_and_third_move() {
    let attack = mv("tackle");
    let buff = mv("swords-dance");
    assert!(Ext::with_planned_buffs(dat(), vec![attack]).is_err());
    assert!(Ext::with_planned_buffs(dat(), vec![buff, buff]).is_err());
    assert!(Ext::with_planned_buffs(dat(), vec![buff, mv("harden"), mv("aqua-ring")]).is_err());
    for id in [
        "swords-dance",
        "dragon-dance",
        "nasty-plot",
        "harden",
        "agility",
        "aqua-ring",
    ] {
        assert!(Ext::with_planned_buffs(dat(), vec![mv(id)]).is_ok(), "{id}");
    }
    let no_buffs = Ext::with_planned_buffs(dat(), vec![]).expect("explicitly empty plan");
    assert_eq!(no_buffs.planned_buffs, Some(vec![]));
}

#[test]
fn planned_buffs_are_acquired_in_opening_but_present_in_assembled_state() {
    let planned = vec![mv("swords-dance"), mv("aqua-ring")];
    let opening_ext = Ext {
        planned_buffs: Some(planned.clone()),
        rift: true,
        ..Ext::default()
    };
    let opts: &'static Opts = Box::leak(Box::new(Opts {
        seed: 2,
        seconds: 0.5,
        cards: true,
        bot: Bot::Kite,
        terrain: false,
        trace: false,
        ext: opening_ext,
    }));
    let mut opening = init_match(&LIBM, dat(), tables(), mon(25), mv("tackle"), opts);
    assert_eq!(opening.bond_order, vec![100, 101]);
    assert_eq!(opening.learned, vec![false, false]);
    assert_eq!((opening.state.sd, opening.state.hd), (0, 0));
    for seed in 1..=512 {
        opening.card_roll = crate::rng::Rng::new(seed);
        opening.try_learn();
        if opening.learned[0] {
            break;
        }
    }
    assert!(
        opening.learned[0],
        "level-up offer eventually learns the planned first buff"
    );
    assert_eq!(
        opening.state.sd, 1,
        "acquisition initializes its upgrade level"
    );
    opening.bonds = 1;
    assert!(opening.bonded(100));
    opening.tick_buffs();
    assert!(opening.state.buff_effects[5].stacks > 0.0);

    let assembled_ext = Ext::with_planned_buffs(dat(), planned).unwrap();
    let assembled = scene_with_ext(25, "tackle", assembled_ext);
    assert_eq!(assembled.learned, vec![true, true]);
    assert_eq!((assembled.state.sd, assembled.state.hd), (1, 1));
}

#[test]
fn official_inventory_oracle_and_bonded_slot_dilution() {
    let oracle: serde_json::Value = serde_json::from_str(include_str!(
        "../../../tests/oracles/official-core-ce57853.json"
    ))
    .unwrap();
    assert_eq!(
        oracle["gameCommit"],
        "ce5785313b0205af8b9477423f64b0a7b7039dcd"
    );
    assert_eq!(oracle["observations"]["inventory"]["before"]["slots"], 4);
    assert_eq!(oracle["observations"]["inventory"]["after"]["slots"], 1);
    assert_eq!(
        oracle["observations"]["inventory"]["after"]["offers"][0]["w"],
        10
    );

    // Four moves in one assembled group consume one slot, so levelup may still offer new moves.
    let mut m = scene_with_ext(
        7,
        "water-gun",
        Ext {
            companions: vec![mv("whirlpool"), mv("nasty-plot"), mv("tackle")],
            ..Ext::default()
        },
    );
    assert_eq!(m.known_count(), 4);
    assert_eq!(m.slot_count(), 1);
    assert!(m.extra_room());
    let mut offered_new_move = false;
    for seed in 1..128 {
        let mut candidate = scene_with_ext(
            7,
            "water-gun",
            Ext {
                companions: vec![mv("whirlpool"), mv("nasty-plot"), mv("tackle")],
                ..Ext::default()
            },
        );
        candidate.card_roll = Rng::new(seed);
        if candidate.try_learn() && !candidate.extras.is_empty() {
            offered_new_move = true;
            break;
        }
    }
    assert!(
        offered_new_move,
        "a bonded four-move group should still acquire an offered standalone move"
    );

    // A learned off-group attack occupies a standalone slot and gets upgrade cards,
    // but it is inventory only: active-group casting never emits it autonomously.
    let extra = mv("quick-attack");
    m.extras.push((extra, 0.0));
    m.extra_levels.push(1);
    m.extra_evolved.push(false);
    assert_eq!(m.slot_count(), 2);
    let mut legal = Vec::new();
    m.legal_cards(&mut legal);
    assert!(legal.contains(&Card::UpExtra(0)));
    let hit = foe(
        &mut m,
        dat().moves[extra].levels[0].ty,
        1000.0,
        1000.0,
        false,
        0.0,
    );
    m.atk_cd = 1.0;
    tick(&mut m);
    assert_eq!(m.enemies[hit].hp, 1e9);
    m.apply_card(Card::UpExtra(0));
    assert_eq!(m.extra_levels[0], 2);
}

#[test]
fn schooling_rounds_the_transformed_max_hp_like_the_official_start_hook() {
    let mon = dat()
        .dex
        .iter()
        .find(|m| m.hp % 4.0 != 0.0)
        .expect("non-quarter HP");
    let mut m = scene(mon.dex, "tackle");
    m.ability = Ability { id: "schooling" };
    m.state.cards[Stat::Hp as usize] = 1;
    m.stat_dirty = true;
    m.stats();
    assert_eq!(m.st.max_hp, js_round(mon.hp * 1.25) + 20.0);
}

#[test]
fn mature_benchmark_fixture_is_labelled_and_enforces_short_scene_bounds() {
    let opts: &'static Opts = Box::leak(Box::new(Opts {
        seed: 7,
        seconds: 0.1,
        cards: false,
        bot: Bot::Kite,
        terrain: false,
        trace: false,
        ext: Ext::default(),
    }));
    let run = benchmark_scene(
        &LIBM,
        dat(),
        tables(),
        mon(150),
        mv("psybeam"),
        opts,
        10,
        true,
    )
    .expect("bounded mature fixture");
    assert_eq!(
        (run.seconds, run.foes, run.level, run.mature_fixture),
        (0.1, 10, 25, true)
    );
    assert_eq!(run.result.time, 0.1);
    assert!(
        run.hostile_projectiles > 0,
        "fixture should exercise ranged shot simulation"
    );
    assert!(benchmark_scene(
        &LIBM,
        dat(),
        tables(),
        mon(150),
        mv("psybeam"),
        opts,
        9,
        true
    )
    .is_err());
    let too_long: &'static Opts = Box::leak(Box::new(Opts {
        seed: 7,
        seconds: 15.01,
        cards: false,
        bot: Bot::Kite,
        terrain: false,
        trace: false,
        ext: Ext::default(),
    }));
    assert!(benchmark_scene(
        &LIBM,
        dat(),
        tables(),
        mon(150),
        mv("psybeam"),
        too_long,
        10,
        true
    )
    .is_err());
}

#[test]
fn start_choices_keep_the_off_type_stock_attack() {
    let psyduck = mon(54);
    let confusion = mv("confusion");
    assert_eq!(psyduck.start, confusion);
    assert!(psyduck.start_choices(&dat().moves).contains(&confusion));
    assert_ne!(dat().moves[confusion].levels[0].ty, psyduck.types[0]);
}

#[test]
fn damp_matches_util_js() {
    let v = damp(0.0, 100.0, 6.0, 0.05);
    assert!((v - 100.0 * (1.0 - (-0.3f64).exp())).abs() < 1e-9);
    assert_eq!(damp(7.0, 7.0, 3.0, 1.0), 7.0);
}

#[test]
fn spin_hits_count_times_and_waits_for_a_target() {
    let spin = lvl1("rapid-spin");
    let mut m = scene(133, "rapid-spin");
    let a = foe(&mut m, spin.ty, 20.0, 0.0, false, 0.0);
    let mut hits_at = Vec::new();
    let mut seen = 0.0;
    for step in 1..=18 {
        tick(&mut m);
        let l = lost(&m, a);
        if l > seen {
            hits_at.push(step);
            seen = l;
        }
    }
    // First hit on the cast frame (next: 0), then every 0.13 s on the 0.05 s grid: 0.05, 0.20, 0.35.
    assert_eq!(hits_at, vec![1, 4, 7]);
    let each = per_hit(&m, spin, m.enemies[a].combo);
    assert_eq!(seen, each * 3.0);

    let mut far = scene(133, "rapid-spin");
    let b = foe(
        &mut far,
        spin.ty,
        spin.radius + 20.0 + 40.0,
        0.0,
        false,
        0.0,
    );
    for _ in 0..30 {
        tick(&mut far);
    }
    assert_eq!(lost(&far, b), 0.0);
    assert!(far.fields.is_empty());
}

#[test]
fn quake_waves_advance_34_px_and_neighbours_get_hit_by_overlapping_waves() {
    let q = lvl1("magnitude");
    let mut m = scene(27, "magnitude");
    let ids: Vec<usize> = (1..=6)
        .map(|k| foe(&mut m, q.ty, 34.0 * k as f64, 0.0, false, 0.0))
        .collect();
    tick(&mut m);
    m.atk_cd = 1e9;
    for _ in 0..30 {
        tick(&mut m);
    }
    let each = per_hit(&m, q, m.enemies[ids[0]].combo);
    let hits: Vec<f64> = ids.iter().map(|&i| lost(&m, i) / each).collect();
    // Waves at 34 k with radius 30 + 12 reach the foes at 34 (k-1), 34 k, 34 (k+1): ends 2, middle 3.
    assert_eq!(hits, vec![2.0, 3.0, 3.0, 3.0, 3.0, 2.0]);
}

#[test]
fn vortex_pulls_a_boss_a_quarter_as_hard_and_keeps_two() {
    let v = lvl1("whirlpool");
    let mut m = scene(7, "whirlpool");
    let centre = foe(&mut m, v.ty, 150.0, 0.0, false, 0.0);
    let small = foe(&mut m, v.ty, 150.0, 80.0, false, 0.0);
    let boss = foe(&mut m, v.ty, 150.0 + 60.0, 0.0, true, 0.0);
    tick(&mut m);
    m.atk_cd = 1e9;
    let (b0, s0) = (
        len(m.enemies[boss].x - 150.0, m.enemies[boss].y),
        len(m.enemies[small].x - 150.0, m.enemies[small].y - 0.0),
    );
    let steps = 6;
    for _ in 0..steps {
        tick(&mut m);
    }
    let b1 = len(m.enemies[boss].x - 150.0, m.enemies[boss].y);
    let s1 = len(m.enemies[small].x - 150.0, m.enemies[small].y);
    assert!(
        ((b0 - b1) - 150.0 * DT * 0.25 * steps as f64).abs() < 0.5,
        "boss pulled {}",
        b0 - b1
    );
    assert!(
        ((s0 - s1) - 150.0 * DT * steps as f64).abs() < 0.5,
        "enemy pulled {}",
        s0 - s1
    );
    assert_eq!(m.enemies[centre].x, 150.0);
    assert!(lost(&m, centre) > 0.0);

    let mut cap = scene(7, "whirlpool");
    foe(&mut cap, v.ty, 150.0, 0.0, false, 0.0);
    for _ in 0..3 {
        cap.cast_new(v, 0.0);
    }
    assert_eq!(cap.fields.iter().filter(|f| f.k == 14).count(), 2);
}

#[test]
fn stun_freezes_for_a_second_and_a_boss_for_035_of_it() {
    let s = lvl1("thunder-wave");
    let mut m = scene(25, "thunder-wave");
    let a = foe(&mut m, s.ty, 40.0, 0.0, false, 60.0);
    let boss = foe(&mut m, s.ty, 40.0, 30.0, true, 60.0);
    let mut hit_step = 0;
    for step in 1..=40 {
        tick(&mut m);
        if m.enemies[a].stun_t > 0.0 && hit_step == 0 {
            hit_step = step;
            m.atk_cd = 1e9;
            assert!((m.enemies[a].stun_t - (1.0 - DT)).abs() < 1e-9);
            assert!((m.enemies[boss].stun_t - (0.35 - DT)).abs() < 1e-9);
            break;
        }
    }
    // 0.45 s warning: the zone lands on the tenth frame (0.50 s).
    assert!((9..=11).contains(&hit_step), "hit at step {hit_step}");
    let (ax, bx, by) = (m.enemies[a].x, m.enemies[boss].x, m.enemies[boss].y);
    for _ in 0..5 {
        tick(&mut m);
    }
    assert_eq!(m.enemies[a].x, ax);
    assert_eq!(
        (m.enemies[boss].x, m.enemies[boss].y),
        (bx, by),
        "boss still frozen 0.25 s in"
    );
    for _ in 0..3 {
        tick(&mut m);
    }
    assert_ne!(
        (m.enemies[boss].x, m.enemies[boss].y),
        (bx, by),
        "boss moves again after 0.35 s"
    );
    assert!(lost(&m, a) > 0.0);
}

#[test]
fn shove_knocks_back_everything_but_a_boss() {
    let s = lvl1("extrasensory");
    let mut m = scene(63, "extrasensory");
    let a = foe(&mut m, s.ty, 40.0, 0.0, false, 0.0);
    let boss = foe(&mut m, s.ty, 40.0, 20.0, true, 0.0);
    tick(&mut m);
    m.atk_cd = 1e9;
    for _ in 0..10 {
        tick(&mut m);
    }
    assert!(m.enemies[a].x > 40.0 + 20.0, "pushed to {}", m.enemies[a].x);
    assert_eq!(m.enemies[boss].x, 40.0);
    assert!(lost(&m, boss) > 0.0);
}

#[test]
fn homing_shots_turn_toward_a_target_inside_340_only() {
    let h = lvl1("air-slash");
    let run = |dest: (f64, f64)| {
        let mut m = scene(16, "air-slash");
        let a = foe(&mut m, h.ty, 200.0, 0.0, false, 0.0);
        tick(&mut m);
        m.atk_cd = 1e9;
        m.enemies[a].x = dest.0;
        m.enemies[a].y = dest.1;
        for _ in 0..40 {
            tick(&mut m);
        }
        lost(&m, a)
    };
    assert!(
        run((200.0, 110.0)) > 0.0,
        "homing shot should curve into the foe"
    );
    assert_eq!(run((0.0, -1500.0)), 0.0);
}

#[test]
fn bounce_chains_through_one_more_enemy_than_its_bounces() {
    let b = lvl1("seed-bomb");
    assert_eq!(b.bounce, 3.0);
    let mut m = scene(1, "seed-bomb");
    let ids: Vec<usize> = [0.0, 120.0, 240.0, 400.0, 620.0]
        .iter()
        .map(|&y| foe(&mut m, b.ty, 100.0, y, false, 0.0))
        .collect();
    tick(&mut m);
    m.atk_cd = 1e9;
    for _ in 0..60 {
        tick(&mut m);
    }
    let each = per_hit(&m, b, m.enemies[ids[0]].combo);
    let hits: Vec<f64> = ids.iter().map(|&i| lost(&m, i) / each).collect();
    assert_eq!(hits, vec![1.0, 1.0, 1.0, 1.0, 0.0]);
}

#[test]
fn drain_heals_one_per_hit() {
    let d = lvl1("draining-kiss");
    let mut m = scene(35, "draining-kiss");
    let a = foe(&mut m, d.ty, 80.0, 0.0, false, 0.0);
    tick(&mut m);
    m.atk_cd = 1e9;
    m.pl.hp = m.st.max_hp - 10.0;
    let before = m.pl.hp;
    for _ in 0..30 {
        tick(&mut m);
    }
    assert!(lost(&m, a) > 0.0);
    assert!(
        (m.pl.hp - (before + d.drain)).abs() < 1e-9,
        "hp {} -> {}",
        before,
        m.pl.hp
    );
}

#[test]
fn charge_holds_still_then_fires_the_beam_on_the_line() {
    let c = lvl1("hyper-beam");
    let mut m = scene(133, "hyper-beam");
    let on = foe(&mut m, c.ty, 100.0, 0.0, false, 0.0);
    let off = foe(&mut m, c.ty, 100.0, 100.0, false, 0.0);
    let mut first = 0;
    for step in 1..=20 {
        tick(&mut m);
        if first == 0 && lost(&m, on) > 0.0 {
            first = step;
            m.atk_cd = 1e9;
        }
    }
    assert!((15..=16).contains(&first), "fired at step {first}");
    assert_eq!(lost(&m, on), per_hit(&m, c, m.enemies[on].combo));
    assert_eq!(lost(&m, off), 0.0);
}

#[test]
fn dash_cannot_choose_a_special_uncrowded_direction() {
    let mut m = scene(150, "quick-attack");
    foe(&mut m, T_NORMAL, 30., 0., false, 0.);
    for i in 0..30 {
        foe(
            &mut m,
            T_NORMAL,
            100. + (i % 5) as f64,
            (i / 5) as f64 - 3.,
            false,
            0.,
        );
    }
    assert!(m.cast());
    assert_eq!((m.pl.x, m.pl.y), (104., 0.));
    assert_eq!(m.pl.inv, 0.3);
    assert_eq!(m.risk.dash_casts, 1);
}
#[test]
fn thirty_contacts_cannot_extend_dash_invulnerability() {
    let mut m = scene(150, "quick-attack");
    for i in 0..30 {
        let a = i as f64 * PI / 15.;
        let n = foe(&mut m, T_NORMAL, a.cos() * 10., a.sin() * 10., false, 0.);
        m.enemies[n].dmg = 10.;
    }
    m.pl.inv = 0.3;
    let hp = m.pl.hp;
    m.resolve_contact();
    assert_eq!(m.pl.hp, hp);
    assert_eq!(m.risk.contact_attempts, 30);
    m.pl.inv = 0.;
    for e in &mut m.enemies {
        e.touch = 0.;
    }
    m.resolve_contact();
    assert!(m.pl.hp < hp);
    assert_eq!(m.risk.hits, 1);
    m.note_exposure(DT);
    assert_eq!(m.risk.surrounded_seconds, DT);
    assert!(m.risk.contact_seconds > 0.);
}

#[test]
fn contact_scenes_scale_attempts_without_scaling_hits_during_global_immunity() {
    for count in [10, 20, 30] {
        let mut m = scene(150, "quick-attack");
        for i in 0..count {
            let a = i as f64 * PI * 2. / count as f64;
            let n = foe(&mut m, T_NORMAL, a.cos() * 10., a.sin() * 10., false, 0.);
            m.enemies[n].dmg = 10.;
        }
        m.pl.inv = 0.3;
        let hp = m.pl.hp;
        m.resolve_contact();
        assert_eq!(m.pl.hp, hp, "{count} contacts bypassed active immunity");
        assert_eq!(m.risk.contact_attempts, count as u32);
        assert_eq!(m.risk.hits, 0);
        assert_eq!(m.risk.damage, 0.);
    }
}

#[test]
fn kill_abilities_update_damage_live_and_stop_at_fifteen_percent() {
    let mut m = scene(150, "shadow-ball");
    m.ability = Ability::of("moxie");
    let attack = lvl1("shadow-ball");
    let target = foe(&mut m, T_NORMAL, 500., 0., false, 0.);
    let mut rng = crate::rng::Rng::new(7);
    let base = m.ability_frame().outgoing(
        m.status_of(attack),
        attack.ty,
        attack.cat,
        &m.enemies[target],
        &dat().tmult,
        &mut rng,
    );
    for kill in 1..=40 {
        let n = foe(&mut m, T_NORMAL, 500., kill as f64, false, 0.);
        m.enemies[n].hp = 0.;
        m.reap();
        let next = m.ability_frame().outgoing(
            m.status_of(attack),
            attack.ty,
            attack.cat,
            &m.enemies[target],
            &dat().tmult,
            &mut rng,
        );
        let expected = 1. + (kill as f64 * 0.005).min(0.15);
        assert!((next / base - expected).abs() < 1e-12, "after {kill} kills");
    }
}

#[test]
fn initially_learned_second_attack_is_a_separate_swappable_slot() {
    let start = mv("water-gun");
    let second = mv("quick-attack");
    let mut m = scene_with_ext(
        54,
        "water-gun",
        Ext {
            initial_second: Some(second),
            alt: Some(second),
            ..Ext::default()
        },
    );
    assert_eq!(
        m.known_count(),
        2,
        "start and chosen second are both learned"
    );
    assert_eq!(m.current_move().ty, dat().moves[start].levels[0].ty);
    m.atk_cd = 10.;
    m.maybe_swap();
    assert_eq!(m.slot, 1);
    assert_eq!(
        m.alt_cd, 0.,
        "new slot is immediately available when its timer was ready"
    );
    m.maybe_swap();
    assert_eq!(
        m.slot, 1,
        "entering an available slot does not immediately bounce back"
    );
    m.alt_cd = 10.;
    m.maybe_swap();
    assert_eq!(m.slot, 0);
    assert!(m.atk_cd <= dat().moves[start].levels[0].cd * 0.35);
}

#[test]
fn bonded_second_attack_is_not_retained_as_a_duplicate_alt_slot() {
    let start = mv("water-gun");
    let second = mv("quick-attack");
    let mut m = scene_with_ext(
        54,
        "water-gun",
        Ext {
            initial_second: Some(second),
            alt: Some(second),
            companions: vec![second],
            bonded: true,
            ..Ext::default()
        },
    );
    m.atk_cd = 10.;
    m.maybe_swap();
    assert_eq!(
        m.slot, 0,
        "an active-group member has no duplicate standalone slot"
    );
    assert_eq!(m.current_move().ty, dat().moves[start].levels[0].ty);
    m.slot = 1;
    m.st.cd_mul = 0.3;
    m.maybe_swap();
    assert_eq!(
        m.slot, 0,
        "group membership normalizes even when swapping is unnecessary"
    );
}

#[test]
fn failed_target_gated_cast_does_not_charge_life_orb() {
    let mut m = scene_with_ext(
        150,
        "quick-attack",
        Ext {
            item: Item::by_id("lifeorb"),
            ..Ext::default()
        },
    );
    let hp = m.pl.hp;
    assert!(!m.cast(), "quick attack waits until a target is in reach");
    assert_eq!(
        m.pl.hp, hp,
        "a failed cast is not an attack and costs no HP"
    );
}

#[test]
fn failed_companion_target_gate_does_not_charge_life_orb() {
    let second = mv("quick-attack");
    let mut m = scene_with_ext(
        150,
        "water-gun",
        Ext {
            item: Item::by_id("lifeorb"),
            companions: vec![second],
            bonded: true,
            ..Ext::default()
        },
    );
    let hp = m.pl.hp;
    m.cast_comps();
    assert_eq!(m.pl.hp, hp);
    assert_eq!(
        m.comps[0].2, 0.05,
        "failed companion waits for the next target check"
    );
}

#[test]
fn life_orb_cost_precedes_blaze_threshold_damage_calculation() {
    let mut m = scene_with_ext(
        150,
        "ember",
        Ext {
            item: Item::by_id("lifeorb"),
            ..Ext::default()
        },
    );
    let attack = lvl1("ember");
    let target = foe(&mut m, T_NORMAL, 20., 0., false, 0.);
    m.ability = Ability::of("blaze");
    m.pl.hp = m.st.max_hp * 0.34;
    let before = m.pl.hp;
    assert!(m.cast_player_move(attack));
    assert!(m.pl.hp < before && m.pl.hp / m.st.max_hp < 1. / 3.);
    let mut rng = crate::rng::Rng::new(9);
    let factor = m.ability_frame().outgoing(
        m.status_of(attack),
        attack.ty,
        attack.cat,
        &m.enemies[target],
        &dat().tmult,
        &mut rng,
    );
    assert_eq!(factor, 1.35, "Blaze sees HP after the pre-cast item cost");
}

#[test]
fn dash_invulnerability_expires_before_the_next_contact_resolution() {
    let mut m = scene(150, "quick-attack");
    let n = foe(&mut m, T_NORMAL, 100., 0., false, 0.);
    m.enemies[n].dmg = 10.;
    assert!(m.cast());
    assert!(m.pl.inv >= 0.3);
    m.enemies[n].x = m.pl.x;
    m.enemies[n].y = m.pl.y;
    m.enemies[n].kx = 0.;
    m.enemies[n].ky = 0.;
    for _ in 0..7 {
        m.pl.inv -= DT;
        m.enemies[n].touch = 0.;
        m.resolve_contact();
    }
    assert_eq!(m.risk.contact_attempts, 7);
    assert_eq!(
        m.risk.hits, 1,
        "contact hurts after dash protection expires"
    );
    assert!(m.pl.hp < m.st.max_hp);
}

#[test]
fn dash_stops_at_the_first_wall_on_its_aim_line() {
    let mut m = scene(150, "quick-attack");
    let mut world = crate::terrain::World::new(7920);
    let radius = lvl1("quick-attack").radius;
    let mut start = None;
    'search: for y in (-512..=512).step_by(32) {
        for x in (-512..=512).step_by(32) {
            if !world.is_free_ex(x as f64, y as f64, m.pl.r * 0.8, true) {
                continue;
            }
            for d in (8..=radius as i32).step_by(8) {
                if !world.is_free_ex(x as f64 + d as f64, y as f64, m.pl.r * 0.8, true) {
                    start = Some((x as f64, y as f64, d as f64));
                    break 'search;
                }
            }
        }
    }
    let (x, y, wall_at) = start.expect("seed has a wall within one dash of a free tile");
    m.terrain = Some(Box::new(Terr {
        world,
        path: Path::new(),
    }));
    m.pl.x = x;
    m.pl.y = y;
    m.pl.aim = 0.;
    foe(&mut m, T_NORMAL, x + 12., y, false, 0.);
    assert!(m.cast());
    assert!((m.pl.x - x - (wall_at - 8.)).abs() < 1e-9);
    assert_eq!(m.pl.y, y);
}
#[test]
fn ranged_combat_does_not_force_the_player_inside_the_magnet() {
    assert!(Match::<Libm>::attack_keep(lvl1("water-gun"), 14.) > 78.);
    assert!(
        Match::<Libm>::attack_keep(lvl1("water-gun"), 14.)
            > Match::<Libm>::attack_keep(lvl1("tackle"), 14.)
    );
}
#[test]
fn hazards_cancel_dash_protection_but_damp_blocks_bombers() {
    let mut m = scene(54, "water-gun");
    m.ability = Ability::of("damp");
    let h = |boom| Hazard {
        boom,
        kind: HKind::Zone,
        x: 0.,
        y: 0.,
        r: 50.,
        angle: 0.,
        len: 0.,
        w: 0.,
        delay: 0.,
        t: 0.,
        dmg: 10.,
        ty: T_NORMAL,
        cat: 1,
        pure: false,
        pct: f64::NAN,
    };
    m.pl.inv = 0.3;
    let hp = m.pl.hp;
    m.hazards.push(h(true));
    m.resolve_hazards();
    assert_eq!(m.pl.hp, hp);
    m.hazards.push(h(false));
    m.resolve_hazards();
    assert!(m.pl.hp < hp);
}
#[test]
fn shot_collision_accepts_more_than_sixty_four_bodies() {
    let mut m = scene(150, "water-gun");
    for i in 0..80 {
        foe(&mut m, T_WATER, 20. + i as f64, 0., i == 79, 0.);
    }
    m.cast();
    m.step_shots();
    assert_eq!(m.enemies.len(), 80);
}
#[test]
fn nature_tm_and_ability_configuration_enforces_game_rules() {
    let base = mon(150);
    let n = dat()
        .configure(base, "modest", Some("pressure"), &["shadow-ball".into()])
        .unwrap();
    assert_eq!(n.pa, base.pa * 0.9);
    assert_eq!(n.sa, base.sa * 1.1);
    assert_eq!(n.atk, n.pa.max(n.sa));
    assert_eq!(n.hp, base.hp);
    assert!(n.pool.contains(&mv("shadow-ball")));
    assert!(!base.pool.contains(&mv("shadow-ball")));
    assert!(dat()
        .configure(mon(54), "hardy", None, &["flamethrower".into()])
        .is_err());
    assert!(dat()
        .configure(base, "hardy", Some("huge-power"), &[])
        .is_err());
    assert!(dat().configure(base, "made-up", None, &[]).is_err());
}
#[test]
fn huge_power_boosts_physical_damage() {
    let mut m = scene(184, "tackle");
    let n = foe(&mut m, T_NORMAL, 20., 0., false, 0.);
    m.ability = Ability::of("huge-power");
    m.cast();
    let boosted = lost(&m, n);
    let attack = lvl1("tackle");
    assert_eq!(
        boosted,
        js_round(attack.dmg * m.atk_for(attack.cat, attack.ty) * 1.5)
    );
}
#[test]
fn sheer_force_removes_status_and_serene_grace_doubles_it() {
    let mut m = scene(150, "sludge");
    let n = foe(&mut m, T_POISON, 0., 0., false, 0.);
    m.ability = Ability::of("sheer-force");
    m.cast();
    for _ in 0..5 {
        m.step_shots();
    }
    assert_eq!(m.enemies[n].poison, 0.);
    assert_eq!((m.enemies[n].kx, m.enemies[n].ky), (0., 0.));
    let mut m = scene(150, "lick");
    let n = foe(&mut m, T_GHOST, 20., 0., false, 0.);
    m.ability = Ability::of("serene-grace");
    m.cast();
    assert_eq!(m.enemies[n].slow, (or(lvl1("lick").slow, 0.) * 2.).min(0.8));
}
#[test]
fn absorption_heals_and_sturdy_has_a_cooldown() {
    let mut m = scene(25, "thunder-shock");
    m.ability = Ability::of("lightning-rod");
    m.pl.hp = m.st.max_hp * 0.5;
    let hp = m.pl.hp;
    m.hurt(100., T_ELECTRIC, 2);
    assert!(m.pl.hp > hp);
    assert_eq!(m.pl.inv, 0.3);
    m.ability = Ability::of("sturdy");
    m.pl.inv = 0.;
    m.hurt(1e6, T_NORMAL, 1);
    assert_eq!(m.pl.hp, 1.);
    m.pl.inv = 0.;
    m.t = 1.;
    m.hurt(1e6, T_NORMAL, 1);
    assert!(m.pl.hp <= 0.);
}
#[test]
fn levitation_ignores_a_sticky_trap() {
    let mut m = scene(150, "confusion");
    m.trap_effect(0., 0., 1);
    assert_eq!(m.pl.slow_t, 3.5);
    m.stat_dirty = true;
    m.stats();
    let slow = m.st.spd;
    m.ability = Ability::of("levitate");
    m.pl.slow_t = 0.;
    m.trap_effect(0., 0., 1);
    assert_eq!(m.pl.slow_t, 0.);
    m.stat_dirty = true;
    m.stats();
    assert!(m.st.spd > slow);
}
#[test]
fn projectile_upgrades_add_real_projectiles() {
    let m = &dat().moves[mv("energy-ball")];
    assert_eq!(m.levels[0].count, 1.);
    assert_eq!(m.levels[1].count, 2.);
    assert!((m.levels[1].spread - 0.156).abs() < 1e-12);
}
