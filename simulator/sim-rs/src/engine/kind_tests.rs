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
    DATA.get_or_init(|| Data::load("../v3/v3_data.json"))
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
        seconds: 60.0,
        cards: false,
        bot: Bot::Play,
        terrain: false,
        trace: false,
        status: true,
        ext: Ext { xkinds: true, ..Ext::default() },
    }));
    let mut m = init_match(&LIBM, dat(), tables(), mon(dex), mv(move_id), opts);
    m.pl.x = 0.0;
    m.pl.y = 0.0;
    m.stat_dirty = true;
    m.stats();
    m.pl.hp = m.st.max_hp;
    m
}

/// A combo the move's type hits for exactly x1, so expected damage is dmg * atk.
fn neutral_combo(ty: u8) -> u16 {
    dat().dex.iter().find(|d| dat().tmult[ty as usize][d.combo as usize] == 1.0).expect("neutral combo").combo
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
        "dragon-claw", "play-rough", "flame-charge", "u-turn", "dragon-breath", "ancient-power", "hyper-beam", "solar-beam", "rapid-spin",
        "rolling-kick", "outrage", "gyro-ball", "night-slash", "whirlpool", "sand-tomb", "ominous-wind", "seed-bomb", "electro-ball", "acid-spray",
        "signal-beam", "power-gem", "mirror-shot", "energy-ball", "mist-ball", "air-slash", "ice-shard", "shadow-sneak", "draining-kiss",
        "sucker-punch", "thunder-wave", "rock-tomb", "freeze-dry", "dynamic-punch", "extrasensory", "whirlwind", "vacuum-wave", "disarming-voice",
        "magnitude",
    ];
    assert_eq!(new.len(), 38);
    for id in new {
        assert!(dat().move_ix.contains_key(id), "{id} missing");
    }
    let spin = lvl1("rapid-spin");
    assert_eq!((spin.xk, spin.dmg, spin.count, spin.radius, spin.cd), (12, 9.0, 3.0, 62.0, 1.0));
    let quake = lvl1("magnitude");
    assert_eq!((quake.xk, quake.dmg, quake.count, quake.radius, quake.cd), (13, 18.0, 6.0, 30.0, 1.15));
    let vortex = lvl1("whirlpool");
    assert_eq!((vortex.xk, vortex.dmg, vortex.radius, vortex.dur, vortex.pull), (14, 8.0, 72.0, 2.6, 150.0));
    let stun = lvl1("thunder-wave");
    assert_eq!((stun.xk, stun.dmg, stun.radius, stun.stun), (16, 22.0, 58.0, 1.0));
    let shove = lvl1("extrasensory");
    assert_eq!((shove.xk, shove.dmg, shove.radius, shove.knock), (15, 16.0, 92.0, 320.0));
    let charge = lvl1("hyper-beam");
    assert_eq!((charge.xk, charge.dmg, charge.charge, charge.radius, charge.width), (11, 58.0, 0.75, 300.0, 44.0));
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
        let want = if crate::data::TYPES[t] == "dragon" { 4 } else { 5 };
        assert!(*n >= want, "type {} has {n} attacks", crate::data::TYPES[t]);
    }
}

#[test]
fn monotype_hits_20_percent_harder_with_its_own_type_only() {
    let psychic = crate::data::TYPES.iter().position(|t| *t == "psychic").unwrap() as u8;
    let ghost = crate::data::TYPES.iter().position(|t| *t == "ghost").unwrap() as u8;
    let grass = crate::data::TYPES.iter().position(|t| *t == "grass").unwrap() as u8;
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
    let b = foe(&mut far, spin.ty, spin.radius + 20.0 + 40.0, 0.0, false, 0.0);
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
    let ids: Vec<usize> = (1..=6).map(|k| foe(&mut m, q.ty, 34.0 * k as f64, 0.0, false, 0.0)).collect();
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
    let (b0, s0) = (len(m.enemies[boss].x - 150.0, m.enemies[boss].y), len(m.enemies[small].x - 150.0, m.enemies[small].y - 0.0));
    let steps = 6;
    for _ in 0..steps {
        tick(&mut m);
    }
    let b1 = len(m.enemies[boss].x - 150.0, m.enemies[boss].y);
    let s1 = len(m.enemies[small].x - 150.0, m.enemies[small].y);
    assert!(((b0 - b1) - 150.0 * DT * 0.25 * steps as f64).abs() < 0.5, "boss pulled {}", b0 - b1);
    assert!(((s0 - s1) - 150.0 * DT * steps as f64).abs() < 0.5, "enemy pulled {}", s0 - s1);
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
    assert_eq!((m.enemies[boss].x, m.enemies[boss].y), (bx, by), "boss still frozen 0.25 s in");
    for _ in 0..3 {
        tick(&mut m);
    }
    assert_ne!((m.enemies[boss].x, m.enemies[boss].y), (bx, by), "boss moves again after 0.35 s");
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
    assert!(run((200.0, 110.0)) > 0.0, "homing shot should curve into the foe");
    assert_eq!(run((0.0, -1500.0)), 0.0);
}

#[test]
fn bounce_chains_through_one_more_enemy_than_its_bounces() {
    let b = lvl1("seed-bomb");
    assert_eq!(b.bounce, 3.0);
    let mut m = scene(1, "seed-bomb");
    let ids: Vec<usize> = [0.0, 120.0, 240.0, 400.0, 620.0].iter().map(|&y| foe(&mut m, b.ty, 100.0, y, false, 0.0)).collect();
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
    assert!((m.pl.hp - (before + d.drain)).abs() < 1e-9, "hp {} -> {}", before, m.pl.hp);
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
fn a_boss_past_boss_far_respawns_ahead_after_four_seconds() {
    // enemy.js:984-988: a boss farther than BOSS_FAR for more than 4 s is placed ahead of the player.
    // The boss is held at BOSS_FAR + 200 so only the rule moves it.
    let mut m = scene(133, "rapid-spin");
    let b = foe(&mut m, 0, BOSS_FAR + 200.0, 0.0, true, 0.0);
    let mut respawned_at = None;
    for call in 1..=100 {
        m.enemies[b].x = BOSS_FAR + 200.0;
        m.enemies[b].y = 0.0;
        m.tick_stragglers();
        if m.enemies[b].x.hypot(m.enemies[b].y) < BOSS_FAR {
            respawned_at = Some(call);
            break;
        }
    }
    // Each call adds DT = 0.05 s, so the 4 s mark is passed on call 81 (call 80 may land on it exactly).
    let call = respawned_at.expect("the boss never respawned");
    assert!((80..=81).contains(&call), "respawned on call {call}");
}

#[test]
fn a_boss_within_boss_far_is_never_moved_by_stragglers() {
    let mut m = scene(133, "rapid-spin");
    let b = foe(&mut m, 0, BOSS_FAR - 200.0, 0.0, true, 0.0);
    for _ in 0..200 {
        m.tick_stragglers();
    }
    assert_eq!(m.enemies[b].x, BOSS_FAR - 200.0);
}

#[test]
fn damage_is_credited_to_the_move_that_dealt_it() {
    let mut m = scene(1, "vine-whip");
    let ty = m.st.mv.ty;
    foe(&mut m, ty, 30.0, 0.0, false, 0.0);
    for _ in 0..600 {
        tick(&mut m);
    }
    assert!(m.dealt > 0.0);
    let total: f64 = m.dealt_by.iter().sum();
    assert!((total - m.dealt).abs() < 1e-6, "{total} vs {}", m.dealt);
    assert!((m.dealt_by[mv("vine-whip")] - m.dealt).abs() < 1e-6);
}

/// A fixed group of `comps` bonded through the rift, run from `start` (not the species default).
fn rift_scene(dex: u32, start: usize, comps: Vec<usize>) -> Match<'static, Libm> {
    let opts: &'static Opts = Box::leak(Box::new(Opts {
        seed: 1,
        seconds: 60.0,
        cards: false,
        bot: Bot::Play,
        terrain: false,
        trace: false,
        status: true,
        ext: Ext { xkinds: true, rift: true, companions: comps, ..Ext::default() },
    }));
    init_match(&LIBM, dat(), tables(), mon(dex), start, opts)
}

/// A species with enough attacks to draw from, and the attacks that are not its default start.
fn pool_species() -> (&'static Mon, usize, Vec<usize>) {
    let mon = dat().dex.iter().find(|m| m.pool.iter().filter(|&&ix| ix != m.start).count() >= 5).expect("pool");
    let start = *mon.pool.iter().find(|&&ix| ix != mon.start).expect("start");
    let others: Vec<usize> = mon.pool.iter().copied().filter(|&ix| ix != start && ix != mon.start).collect();
    (mon, start, others)
}

#[test]
fn the_run_starter_and_companions_are_never_drawn_as_extras() {
    let (mon, start, others) = pool_species();
    let comps = vec![others[0]];
    let mut drawn = 0;
    for seed in 1..=200u32 {
        let mut m = rift_scene(mon.dex, start, comps.clone());
        m.card_roll = Rng::new(seed);
        for _ in 0..3 {
            m.try_learn();
        }
        drawn += m.extras.len();
        assert!(!m.extras.iter().any(|e| e.0 == start), "run starter drawn as an extra (seed {seed})");
        assert!(!m.extras.iter().any(|e| comps.contains(&e.0)), "companion drawn as an extra (seed {seed})");
    }
    assert!(drawn > 0, "no extra was ever drawn, the check is vacuous");
}

#[test]
fn a_bonded_pair_of_companions_is_one_hole_with_the_starter() {
    let (mon, start, others) = pool_species();
    let mut m = rift_scene(mon.dex, start, others[..2].to_vec());
    m.learned = vec![true, true];
    m.bonds = 2;
    assert_eq!(m.holes_used(), 1);
    assert!(m.extra_room());
    m.bonds = 0;
    assert_eq!(m.holes_used(), 3);
}

/// A boss built like spawn_boss: ranged personality, a 1000 HP bar, `hp` left, 60 speed, 300 px away.
fn boss_at(m: &mut Match<'static, Libm>, hp: f64) -> usize {
    let mon = mon(1);
    let mut e = blank_enemy(hp, 0.0, neutral_combo(mon.types[0]), 1, 1.0);
    e.max = 1000.0;
    e.x = 300.0;
    e.y = 0.0;
    e.spd = 60.0;
    e.dmg = 10.0;
    e.beh = crate::data::Beh::Ranged;
    e.boss = true;
    e.fuse = -1.0;
    e.id = m.enemies.len() as _;
    e.bai = Some(BossAi::new(mon.dex, &mon.types, true, &mut Rng::new(7)));
    m.enemies.push(e);
    m.enemies.len() - 1
}

/// enemy.js:460 and :492: a boss under half HP enrages once, at ×1.15 speed, and the speed does not compound.
#[test]
fn boss_enrages_once_below_half_hp_at_15_percent_speed() {
    let mut m = scene(1, "seed-bomb");
    let hurt = boss_at(&mut m, 400.0);
    let healthy = boss_at(&mut m, 600.0);
    m.step_enemies();
    assert!(m.enemies[hurt].bai.as_ref().unwrap().fury);
    assert!((m.enemies[hurt].spd - 69.0).abs() < 1e-9, "spd {}", m.enemies[hurt].spd);
    assert!(!m.enemies[healthy].bai.as_ref().unwrap().fury);
    assert_eq!(m.enemies[healthy].spd, 60.0);
    m.step_enemies();
    assert!((m.enemies[hurt].spd - 69.0).abs() < 1e-9, "spd after a second frame {}", m.enemies[hurt].spd);
}

/// enemy.js:505-507: the slam warns a ring of 96 + boss radius that lands after 0.85 s, at the boss's damage ×1.3.
#[test]
fn boss_slam_warns_a_ring_for_0_85_s_at_1_3_times_dmg() {
    let env = BossEnv {
        x: 0.0,
        y: 0.0,
        r: 20.0,
        dmg: 10.0,
        shot: 5.0,
        ty: 0,
        cat: 1,
        px: 50.0,
        py: 0.0,
        dist: 50.0,
        nd: (1.0, 0.0),
        dir: (1.0, 0.0),
        spd: 60.0,
        dt: DT,
        hp: 1000.0,
        max: 1000.0,
    };
    let mut b = BossAi::new(1, &[0], false, &mut Rng::new(3));
    let mut hz = Vec::new();
    boss_start(&LIBM, &mut b, &mut Rng::new(3), BAtk::Slam, &env, &mut hz);
    assert_eq!(hz.len(), 1);
    assert_eq!(hz[0].r, 116.0);
    assert!((hz[0].delay - 0.85).abs() < 1e-12);
    assert!((hz[0].dmg - 13.0).abs() < 1e-9);
}

/// One frame on the ranking path, without the player's attacks: enemies move, then the straggler rules run
/// (engine step order, enemy.js update() then EnemyMgr.update()).
fn frame(m: &mut Match<'static, Libm>) {
    m.t += DT;
    m.stats();
    m.step_enemies();
    m.tick_stragglers();
}

/// A summoner 150 px from the player, with the game's values for a 100-HP, 10-dmg, 8-xp species.
fn summoner(m: &mut Match<'static, Libm>) -> usize {
    let s = foe(m, 0, 150.0, 0.0, false, 0.0);
    let e = &mut m.enemies[s];
    e.beh = crate::data::Beh::Summoner;
    e.def.hp = 100.0;
    e.def.dmg = 10.0;
    e.def.xp = 8.0;
    e.def.spd = 60.0;
    e.def.shot_cd = 2.0;
    e.shot_cd = 2.0;
    s
}

#[test]
fn a_summoner_calls_two_minions_per_cooldown_up_to_four_alive() {
    // enemy.js:665-682: two chasers at 0.35 x hp, 0.6 x dmg and max(1, 0.25 x xp), no DMG_K or XP_K.
    let mut m = scene(133, "rapid-spin");
    let s = summoner(&mut m);
    let id = m.enemies[s].id;
    m.pl.hp = 1e12;
    let mine = |m: &Match<'static, Libm>| m.enemies.iter().filter(|e| e.owner == Some(id) && e.hp > 0.0).count();
    for _ in 0..45 {
        frame(&mut m);
        m.pl.hp = 1e12;
    }
    assert_eq!(mine(&m), 2);
    for e in m.enemies.iter().filter(|e| e.owner == Some(id)) {
        assert_eq!(e.beh, crate::data::Beh::Chase);
        assert_eq!(e.max, 35.0);
        assert_eq!(e.dmg, 6.0);
        assert_eq!(e.xp, 2.0);
    }
    for _ in 0..90 {
        frame(&mut m);
        m.pl.hp = 1e12;
    }
    // Second cooldown: 4 alive. The third one finds 4 of its own and summons nothing.
    assert_eq!(mine(&m), 4);
}

#[test]
fn a_summoner_stays_quiet_while_more_than_cap_plus_15_enemies_live() {
    // enemy.js:668: no summon while EnemyMgr.count > CAP + 15 (79). 81 enemies live here.
    let mut m = scene(133, "rapid-spin");
    let s = summoner(&mut m);
    let id = m.enemies[s].id;
    for _ in 0..80 {
        foe(&mut m, 0, 5000.0, 5000.0, false, 0.0);
    }
    for _ in 0..60 {
        m.step_enemies();
    }
    assert_eq!(m.enemies.iter().filter(|e| e.owner == Some(id)).count(), 0);
}

#[test]
fn a_shielder_walks_in_instead_of_holding_range() {
    // enemy.js:578: keepsDistance() has no shielder, so it chases like a plain walker.
    let mut m = scene(133, "rapid-spin");
    let s = foe(&mut m, 0, 140.0, 0.0, false, 60.0);
    m.enemies[s].beh = crate::data::Beh::Shielder;
    for _ in 0..40 {
        m.step_enemies();
        m.pl.hp = 1e12;
    }
    assert!(m.enemies[s].x < 100.0, "x = {}", m.enemies[s].x);
}

#[test]
fn a_healer_heals_only_inside_its_range() {
    // enemy.js:403: it fires only when dist < range. Its cooldown runs meanwhile and fires on entry.
    let mut m = scene(133, "rapid-spin");
    let h = foe(&mut m, 0, 300.0, 0.0, false, 0.0);
    let t = foe(&mut m, 0, 300.0, 20.0, false, 0.0);
    m.enemies[h].beh = crate::data::Beh::Healer;
    m.enemies[t].hp = 5e8;
    for _ in 0..200 {
        m.step_enemies();
    }
    assert_eq!(m.enemies[t].hp, 5e8);
    m.enemies[h].x = 100.0;
    m.enemies[t].x = 100.0;
    m.step_enemies();
    assert!(m.enemies[t].hp > 5e8, "hp = {}", m.enemies[t].hp);
}

#[test]
fn healer_power_never_drops_below_one() {
    // enemy.js:633-634: pow = Math.max(1, atk / baseAtk). Being weaker than base does not weaken the heal.
    assert!((heal_fraction(&LIBM, 0.5, 1.0) - 0.07).abs() < 1e-12);
    assert!((heal_fraction(&LIBM, 4.0, 1.0) - 0.07 * 4f64.powf(0.35)).abs() < 1e-9);
}

#[test]
fn damage_over_time_takes_the_shield_first_then_rounds_and_costs_at_least_one() {
    // enemy.js:137-144: the shield takes it first, then Math.max(1, Math.round(amount)), and noteDmg.
    let mut e = blank_enemy(100.0, 4.6, 0, 1, 1.0);
    hurt_dot(&mut e, 5.0); // 4.6 absorbed, 0.4 left: costs 1
    assert!((e.hp - 99.0).abs() < 1e-9);
    assert_eq!(e.shield, 0.0);
    hurt_dot(&mut e, 0.3); // costs 1
    assert!((e.hp - 98.0).abs() < 1e-9);
    e.shield = 2.0;
    hurt_dot(&mut e, 5.2); // 2 absorbed, round(3) = 3 lost
    assert!((e.hp - 95.0).abs() < 1e-9);
    assert!((e.dps_acc - 5.0).abs() < 1e-9);
}

#[test]
fn a_wild_enemy_past_1400_px_is_placed_ahead_in_the_same_frame() {
    // enemy.js:999: more than 1400 px away respawns ahead. The frame runs the rule after the movement.
    let mut m = scene(133, "rapid-spin");
    let w = foe(&mut m, 0, 1500.0, 0.0, false, 0.0);
    frame(&mut m);
    let d = m.enemies[w].x.hypot(m.enemies[w].y);
    assert!(d < 1400.0, "d = {d}");
}

#[test]
fn a_wild_enemy_1000_px_away_is_left_alone_when_not_unseen_and_behind() {
    // enemy.js:989-1002: 1000 px is inside the 1400 px rule and the player is standing still, so no
    // straggler rule applies. The old teleport at OUTER + 250 (730 px) moved it on the first frame.
    let mut m = scene(133, "rapid-spin");
    let w = foe(&mut m, 0, 1000.0, 0.0, false, 0.0);
    for _ in 0..100 {
        frame(&mut m);
    }
    assert_eq!(m.enemies[w].x, 1000.0);
}

#[test]
fn a_boss_2600_px_away_is_moved_only_after_four_seconds() {
    // enemy.js:984-987: a boss farther than 2500 px for 4 s respawns ahead. It must not be teleported first.
    let mut m = scene(133, "rapid-spin");
    let b = foe(&mut m, 0, BOSS_FAR + 100.0, 0.0, true, 0.0);
    let mut moved_at = None;
    for call in 1..=100 {
        frame(&mut m);
        if m.enemies[b].x < BOSS_FAR {
            moved_at = Some(call);
            break;
        }
    }
    let call = moved_at.expect("the boss never respawned");
    assert!((80..=82).contains(&call), "moved on frame {call}");
}

#[test]
fn an_orb_sits_on_an_ellipse_0_7_high_at_the_top_of_its_orbit() {
    // projectile.js:52: p.y = o.y + sin(oa) * orad * 0.7. The top point is 0.7 of the radius above the player.
    let top = std::f64::consts::FRAC_PI_2 * 3.0;
    let (x, y) = kinds::orb_point(&LIBM, 10.0, 20.0, top, 100.0);
    assert!((x - 10.0).abs() < 1e-9, "x {x}");
    assert!((y - (20.0 - 70.0)).abs() < 1e-9, "y {y}");
    let (rx, ry) = kinds::orb_point(&LIBM, 0.0, 0.0, 0.0, 100.0);
    assert!((rx - 100.0).abs() < 1e-9 && ry.abs() < 1e-9);
}

#[test]
fn boomerang_fan_widens_by_spread_per_blade_up_to_three_gaps() {
    // combat.js:230 spread = m.spread || 0.5, combat.js:233 the fan is spread * min(n, 3) wide.
    let mut out = Vec::new();
    kinds::boom_angles(0.0, 3.0, 0.0, &mut out);
    assert_eq!(out.len(), 3);
    assert!((out[2] - out[0] - 1.5).abs() < 1e-9, "3 blades with the default spread: {out:?}");
    kinds::boom_angles(0.0, 5.0, 0.0, &mut out);
    assert_eq!(out.len(), 5);
    assert!((out[4] - out[0] - 1.5).abs() < 1e-9, "5 blades are capped at 3 gaps: {out:?}");
    kinds::boom_angles(0.0, 2.0, 0.3, &mut out);
    assert!((out[1] - out[0] - 0.6).abs() < 1e-9, "2 blades use 2 gaps: {out:?}");
    kinds::boom_angles(0.7, 1.0, 0.5, &mut out);
    assert_eq!(out, vec![0.7]);
}
