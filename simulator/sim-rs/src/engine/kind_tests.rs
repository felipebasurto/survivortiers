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
    let opts: &'static Opts = Box::leak(Box::new(Opts {
        seed: 1,
        seconds: 15.0,
        cards: false,
        bot: Bot::Kite,
        terrain: false,
        trace: false,

        ext: Ext { ..Ext::default() },
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
