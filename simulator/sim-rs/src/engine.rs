//! Port of sim/match.js + sim/rules.js. Statement order and floating-point
//! operation order follow the JS exactly; `Replay` math proves it.

use crate::data::*;
use crate::math::MathFns;
use crate::rng::Rng;
use crate::terrain::{steer, Block, Liquid, Path, World, PATH_EVERY};
use std::f64::consts::PI;

pub const DT: f64 = 1.0 / 20.0;
/// Status values of repo/js/entities/enemy.js. Slow: factor per move, 1.2 s (applySlow default).
/// Burn: stacks up to 8, 3 s, one tick every 0.5 s. Poison: stacks up to 8, 4 s, one tick every 0.6 s.
const SLOW_SECS: f64 = 1.2;
const BURN_MAX: f64 = 8.0;
const BURN_SECS: f64 = 3.0;
const BURN_TICK: f64 = 0.5;
const POISON_MAX: f64 = 8.0;
const POISON_SECS: f64 = 4.0;
const POISON_TICK: f64 = 0.6;
const CAP: usize = 64;
const ELITE: f64 = 0.85;
const DMG_K: f64 = 2.4;
/// Math.hypot(768, 432) / 2 + 40, as V8 computes it.
const OUTER: f64 = 480.58143401645964;
const INV: f64 = 0.45;
const TOUCH: f64 = 0.55;

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Bot {
    Repulse,
    Line,
}

struct Terr {
    world: World,
    path: Path,
}

/// world.js collide() for a walking enemy, plus enemy.js's "stuck → walk around" rule.
fn collide_enemy(terrain: &mut Option<Box<Terr>>, e: &mut Enemy, ox: f64, oy: f64, vx: f64, vy: f64, dt: f64) {
    let Some(t) = terrain else { return };
    if e.fly || !t.world.collide(&mut e.x, &mut e.y, e.r) {
        return;
    }
    let want = vx.hypot(vy) * dt;
    let got = (e.x - ox).hypot(e.y - oy);
    if want > 0.5 && got < want * 0.35 {
        e.stuck_t += dt;
        if e.stuck_t > 0.35 && e.side_t <= 0.0 {
            e.side_t = 0.7;
            e.stuck_t = 0.0;
            e.side = if e.ai.next() < 0.5 { -1.0 } else { 1.0 };
        }
    } else {
        e.stuck_t = 0.0;
    }
}

pub struct Opts {
    pub seed: u32,
    pub seconds: f64,
    pub cards: bool,
    pub bot: Bot,
    /// play on the real map (src/terrain.rs); breaks parity with sim/match.js
    pub terrain: bool,
    /// record the run into TRACE (see take_trace)
    pub trace: bool,
    /// model slow, burn and poison with the game's values (see the consts above). Off by default:
    /// the default run is the JS-parity run, which ignores them.
    pub status: bool,
}

/// One trace sample: time, player x/y/hp, enemies, and both sides' shots.
pub struct Frame {
    pub t: f64,
    pub x: f64,
    pub y: f64,
    pub hp: f64,
    /// x, y, r, flying
    pub enemies: Vec<(f64, f64, f64, bool)>,
    /// id, dex of each entry in `enemies`
    pub ids: Vec<(u32, u16)>,
    /// x, y, vx, vy
    pub shots: Vec<(f64, f64, f64, f64)>,
    /// x, y, vx, vy, attack type
    pub e_shots: Vec<(f64, f64, f64, f64, u8)>,
}

thread_local! {
    static TRACE: std::cell::RefCell<Vec<Frame>> = const { std::cell::RefCell::new(Vec::new()) };
}

pub fn take_trace() -> Vec<Frame> {
    TRACE.with(|t| std::mem::take(&mut *t.borrow_mut()))
}

#[derive(Debug, Clone, Copy)]
pub struct RunResult {
    pub time: f64,
    pub kills: u32,
    pub level: u32,
    pub capped: bool,
    pub status_ignored: bool,
    pub hp: f64,
    pub max_hp: f64,
    pub hp_frac: f64,
}

// ---------------------------------------------------------------- weather

#[derive(Clone, Copy, PartialEq, Eq)]
enum Wx {
    Sun,
    Rain,
    Sand,
    Snow,
    Fog,
}

const BIOMES: [&[(Wx, f64)]; 3] = [
    &[(Wx::Rain, 3.0), (Wx::Fog, 2.0), (Wx::Sun, 1.5), (Wx::Snow, 0.5), (Wx::Sand, 0.5)],
    &[(Wx::Fog, 3.0), (Wx::Snow, 2.5), (Wx::Rain, 1.0), (Wx::Sand, 1.0)],
    &[(Wx::Sun, 3.0), (Wx::Sand, 3.0), (Wx::Fog, 1.0)],
];

fn wx_mult(kind: Wx, ty: u8) -> f64 {
    let t = TYPES[ty as usize];
    match (kind, t) {
        (Wx::Sun, "fire") => 1.5,
        (Wx::Sun, "water") => 0.5,
        (Wx::Rain, "water") => 1.5,
        (Wx::Rain, "electric") => 1.2,
        (Wx::Rain, "fire") => 0.5,
        (Wx::Sand, "rock" | "ground" | "steel") => 1.3,
        (Wx::Snow, "ice") => 1.5,
        (Wx::Fog, "ghost" | "fairy" | "psychic") => 1.3,
        _ => 1.0,
    }
}

#[derive(Clone, Copy)]
struct Weather {
    kind: Wx,
    elapsed: f64,
    dur: f64,
}

#[inline]
fn jmin(a: f64, b: f64) -> f64 {
    if a.is_nan() || b.is_nan() {
        f64::NAN
    } else if a < b {
        a
    } else {
        b
    }
}

#[inline]
fn jmax(a: f64, b: f64) -> f64 {
    if a.is_nan() || b.is_nan() {
        f64::NAN
    } else if a > b {
        a
    } else {
        b
    }
}

/// `x || d` for numbers: 0, NaN (undefined) fall back to d.
#[inline]
fn or(x: f64, d: f64) -> f64 {
    if x.is_nan() || x == 0.0 {
        d
    } else {
        x
    }
}

/// Math.round for the values this engine sees.
#[inline]
pub fn js_round(x: f64) -> f64 {
    let f = x.floor();
    if x - f >= 0.5 {
        f + 1.0
    } else {
        f
    }
}

#[inline]
fn len(dx: f64, dy: f64) -> f64 {
    (dx * dx + dy * dy).sqrt()
}

fn weather_ramp(elapsed: f64, dur: f64) -> f64 {
    jmin(jmin(1.0, elapsed / 3.0), jmax(0.0, dur - elapsed) / 3.0)
}

fn weather_factor(w: &Option<Weather>, ty: u8) -> f64 {
    match w {
        None => 1.0,
        Some(w) => {
            let strength = weather_ramp(w.elapsed, w.dur);
            if strength <= 0.0 {
                return 1.0;
            }
            let mult = wx_mult(w.kind, ty);
            1.0 + (mult - 1.0) * strength
        }
    }
}

fn weighted_kind(pairs: &[(Wx, f64)], roll: f64) -> Wx {
    let mut sum = 0.0;
    for p in pairs {
        sum += p.1;
    }
    let mut x = roll * sum;
    for p in pairs {
        x -= p.1;
        if x <= 0.0 {
            return p.0;
        }
    }
    pairs[0].0
}

// ---------------------------------------------------------------- rules

fn reach_of(m: &MoveLvl) -> f64 {
    match m.kind {
        Kind::Melee => m.radius,
        Kind::Projectile | Kind::Nova => m.speed * m.life,
        Kind::Beam | Kind::Orbit | Kind::Boomerang => m.radius,
        Kind::Inert => 180.0,
    }
}

fn keep_distance(m: &MoveLvl) -> f64 {
    if m.kind == Kind::Melee {
        0.55 * m.radius
    } else {
        0.75 * reach_of(m)
    }
}

fn in_melee<M: MathFns>(
    math: &M,
    px: f64,
    py: f64,
    angle: f64,
    arc: f64,
    radius: f64,
    ex: f64,
    ey: f64,
    er: f64,
) -> bool {
    let dx = ex - px;
    let dy = ey - py;
    let dist = len(dx, dy);
    if dist > radius + er {
        return false;
    }
    if arc >= PI * 2.0 - 1e-3 {
        return true;
    }
    let mut turn = math.atan2(dy, dx) - angle;
    while turn > PI {
        turn -= PI * 2.0;
    }
    while turn < -PI {
        turn += PI * 2.0;
    }
    turn.abs() <= arc / 2.0 + 1e-9
}

#[allow(clippy::too_many_arguments)]
fn in_beam<M: MathFns>(
    math: &M,
    px: f64,
    py: f64,
    angle: f64,
    length: f64,
    width: f64,
    ex: f64,
    ey: f64,
    er: f64,
) -> bool {
    let dx = ex - px;
    let dy = ey - py;
    let ca = math.cos(angle);
    let sa = math.sin(angle);
    let along = dx * ca + dy * sa;
    let perp = -dx * sa + dy * ca;
    along >= -er && along <= length + er && perp.abs() <= width / 2.0 + er
}

fn fan_angles(aim: f64, count: f64, spread: f64, out: &mut Vec<f64>) {
    out.clear();
    let n = jmax(1.0, (count as i64 as i32) as f64) as usize;
    if n == 1 {
        out.push(aim);
        return;
    }
    let width = or(spread, 0.0) * n as f64;
    for i in 0..n {
        out.push(aim + (i as f64 / (n - 1) as f64 - 0.5) * width);
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Card {
    Up,
    Evo,
    Sd,
    Hd,
    Stat(Stat),
}

const FILL: [Card; 9] = [
    Card::Sd,
    Card::Hd,
    Card::Stat(Stat::Pow),
    Card::Stat(Stat::Run),
    Card::Stat(Stat::Hp),
    Card::Stat(Stat::Cor),
    Card::Stat(Stat::Cd),
    Card::Stat(Stat::Rgn),
    Card::Stat(Stat::Mag),
];

#[derive(Default)]
struct State {
    cards: [u32; 7],
    move_lvl: usize,
    evolved: bool,
    sd: usize,
    hd: usize,
    sd_stacks: f64,
    sd_t: f64,
    sd_cd: f64,
    hd_stacks: f64,
    hd_t: f64,
    hd_cd: f64,
}

/// ATK_POW / SPD_POW / CD_POW from rules.js. V8 evaluates `1.1 ** i` with
/// integer exponents by repeated squaring, which no libm pow reproduces, so
/// the values are V8's own output (checked by sim-rs/parity.js).
pub struct Tables {
    atk: [f64; 41],
    spd: [f64; 9],
    cd: [f64; 11],
}

impl Tables {
    pub fn new() -> Tables {
        Tables {
            atk: [
                1.0, 1.1, 1.2100000000000002, 1.3310000000000004, 1.4641000000000006, 1.6105100000000006,
                1.7715610000000008, 1.9487171000000012, 2.1435888100000016, 2.357947691000002, 2.5937424601000023,
                2.8531167061100025, 3.138428376721003, 3.452271214393104, 3.7974983358324144, 4.177248169415656,
                4.594972986357222, 5.054470284992945, 5.55991731349224, 6.115909044841464, 6.727499949325611,
                7.400249944258173, 8.14027493868399, 8.95430243255239, 9.84973267580763, 10.834705943388393,
                11.918176537727234, 13.10999419149996, 14.420993610649957, 15.863092971714952, 17.44940226888645,
                19.194342495775096, 21.11377674535261, 23.225154419887872, 25.54766986187666, 28.10243684806433,
                30.912680532870763, 34.00394858615784, 37.40434344477363, 41.144777789250995, 45.2592555681761,
            ],
            spd: [
                1.0, 1.07, 1.1449, 1.2250430000000003, 1.3107960100000002, 1.4025517307000004, 1.5007303518490005,
                1.6057814764784306, 1.718186179831921,
            ],
            cd: [
                1.0, 0.92, 0.8464, 0.778688, 0.7163929600000001, 0.6590815232000001, 0.6063550013440002,
                0.5578466012364802, 0.5132188731375618, 0.47216136328655683, 0.4343884542236323,
            ],
        }
    }

    pub fn flat(&self) -> Vec<f64> {
        self.atk.iter().chain(&self.spd).chain(&self.cd).copied().collect()
    }
}

#[derive(Clone)]
struct Derived<'a> {
    mv: &'a MoveLvl,
    max_hp: f64,
    atk: f64,
    spd: f64,
    red: f64,
    cd_mul: f64,
    regen: f64,
    melee: f64,
}

// ---------------------------------------------------------------- entities

#[derive(Clone, Copy, PartialEq, Eq)]
enum Phase {
    Walk,
    Aim,
    Dash,
}

#[derive(Clone, Copy)]
struct Jump {
    tx: f64,
    ty: f64,
    t: f64,
    dur: f64,
}

struct Enemy {
    id: u32,
    dex: u16,
    x: f64,
    y: f64,
    r: f64,
    combo: u16,
    ty0: u8,
    xp: f64,
    beh: Beh,
    spd: f64,
    dmg: f64,
    hp: f64,
    max: f64,
    touch: f64,
    kx: f64,
    ky: f64,
    phase: Phase,
    pt: f64,
    shot_cd: f64,
    skill: f64,
    heal_cd: f64,
    shield_cd: f64,
    jump: Option<Jump>,
    fuse: f64,
    shield: f64,
    shield_t: f64,
    shot: f64,
    cx: f64,
    cy: f64,
    ai: Rng,
    def: Def,
    fly: bool,
    water: bool,
    fire: bool,
    los: (f64, bool),
    side_t: f64,
    side: f64,
    stuck_t: f64,
    lava_t: f64,
    slow: f64,
    slow_t: f64,
    burn: f64,
    burn_t: f64,
    burn_tick: f64,
    poison: f64,
    poison_t: f64,
    poison_tick: f64,
}

/// What one hit applies to an enemy: the move's slow, burn and poison values (applySlow,
/// applyBurn, applyPoison in the game).
#[derive(Clone, Copy, Default)]
struct Status {
    slow: f64,
    burn: f64,
    poison: f64,
}

struct Shot {
    x: f64,
    y: f64,
    vx: f64,
    vy: f64,
    speed: f64,
    r: f64,
    life: f64,
    left: f64,
    hit: Vec<u32>,
    dmg: f64,
    atk: f64,
    ty: u8,
    homing: f64,
    st: Status,
}

struct Boom {
    ox: f64,
    oy: f64,
    dx: f64,
    dy: f64,
    dist: f64,
    dir: f64,
    max: f64,
    speed: f64,
    r: f64,
    hit: Vec<u32>,
    dmg: f64,
    atk: f64,
    ty: u8,
    st: Status,
}

struct Orb {
    angle: f64,
    inside: Vec<u32>,
}

struct EShot {
    x: f64,
    y: f64,
    vx: f64,
    vy: f64,
    r: f64,
    life: f64,
    dmg: f64,
    ty: u8,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum HKind {
    Zone,
    Beam,
}

struct Hazard {
    kind: HKind,
    x: f64,
    y: f64,
    r: f64,
    angle: f64,
    len: f64,
    w: f64,
    delay: f64,
    t: f64,
    dmg: f64,
    ty: u8,
}

struct Player {
    x: f64,
    y: f64,
    r: f64,
    hp: f64,
    inv: f64,
    dirx: f64,
    diry: f64,
    react: f64,
    aim: f64,
}

#[inline]
fn type_mult(tm: &[Vec<f64>], atk: u8, combo: u16) -> f64 {
    tm[atk as usize][combo as usize]
}

#[inline]
fn has(ids: &[u32], id: u32) -> bool {
    ids.contains(&id)
}

fn nearest(enemies: &[Enemy], x: f64, y: f64) -> Option<usize> {
    let mut best = None;
    let mut best_d = f64::INFINITY;
    for (i, e) in enemies.iter().enumerate() {
        if e.hp <= 0.0 {
            continue;
        }
        let d = len(e.x - x, e.y - y);
        if d < best_d {
            best_d = d;
            best = Some(i);
        }
    }
    best
}

/// Applies one hit and what it inflicts (`st`, all zero unless `Opts::status`).
fn strike(e: &mut Enemy, dmg: f64, atk: f64, ty: u8, tm: &[Vec<f64>], w: &Option<Weather>, st: Status) {
    if e.hp <= 0.0 {
        return;
    }
    if st.slow > 0.0 {
        e.slow = e.slow.max(st.slow);
        e.slow_t = e.slow_t.max(SLOW_SECS);
    }
    if st.burn > 0.0 {
        e.burn = jmin(BURN_MAX, e.burn + st.burn);
        e.burn_t = BURN_SECS;
    }
    if st.poison > 0.0 {
        e.poison = jmin(POISON_MAX, e.poison + st.poison);
        e.poison_t = POISON_SECS;
    }
    let mult = type_mult(tm, ty, e.combo);
    let amount = dmg * atk * mult * weather_factor(w, ty);
    let mut left = amount;
    if e.shield > 0.0 {
        let used = jmin(e.shield, left);
        e.shield -= used;
        left -= used;
    }
    e.hp -= left;
}

/// Damage over time, as Enemy.hurt() in the game: rounded, at least 1, and the shield takes it first.
fn hurt_dot(e: &mut Enemy, amount: f64) {
    if e.hp <= 0.0 {
        return;
    }
    let d = jmax(1.0, js_round(amount));
    let mut left = d;
    if e.shield > 0.0 {
        let used = jmin(e.shield, d);
        e.shield -= used;
        left = d - used;
        if left <= 0.0 {
            return;
        }
    }
    e.hp -= left;
}

fn heal_fraction<M: MathFns>(math: &M, atk: f64, base_atk: f64) -> f64 {
    let p = if base_atk > 0.0 { atk / base_atk } else { 1.0 };
    0.07 * jmin(2.5, math.pow(p, 0.35))
}

fn pulse_healer<M: MathFns>(math: &M, hx: f64, hy: f64, enemies: &mut [Enemy], atk: f64, base_atk: f64) {
    for e in enemies.iter_mut() {
        if e.hp >= e.max {
            continue;
        }
        if len(e.x - hx, e.y - hy) <= 150.0 {
            e.hp = jmin(e.max, e.hp + e.max * heal_fraction(math, atk, base_atk));
        }
    }
}

fn pulse_shield(sx: f64, sy: f64, enemies: &mut [Enemy], near: &mut Vec<(f64, usize)>) {
    near.clear();
    for (i, e) in enemies.iter().enumerate() {
        let d = len(e.x - sx, e.y - sy);
        if d <= 160.0 {
            near.push((d, i));
        }
    }
    near.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    let mut given = 0;
    for &(_, i) in near.iter() {
        if given >= 6 {
            break;
        }
        let e = &mut enemies[i];
        if e.shield_t > 0.0 {
            continue;
        }
        e.shield = 0.35 * e.max;
        e.shield_t = 8.0;
        given += 1;
    }
}

/// Scratch space for `separate_enemies`, laid out SoA so the neighbour test vectorizes.
struct Sep {
    pos: Vec<[f64; 3]>,
    xs: [f64; 64],
    ys: [f64; 64],
    rs: [f64; 64],
    xs32: [f32; 64],
    ys32: [f32; 64],
    rs32: [f32; 64],
    hit: [u64; 64],
    near: [u64; 64],
}

impl Default for Sep {
    fn default() -> Self {
        Sep { pos: Vec::new(), xs: [0.0; 64], ys: [0.0; 64], rs: [0.0; 64], xs32: [0.0; 64], ys32: [0.0; 64], rs32: [0.0; 64], hit: [0; 64], near: [0; 64] }
    }
}

/// Enemy positions in SoA form for the shot collision prefilter.
struct ShotSoa {
    xs: [f64; 64],
    ys: [f64; 64],
    rs: [f64; 64],
}

impl Default for ShotSoa {
    fn default() -> Self {
        ShotSoa { xs: [0.0; 64], ys: [0.0; 64], rs: [0.0; 64] }
    }
}

impl ShotSoa {
    /// Returns the padded lane count.
    fn load(&mut self, enemies: &[Enemy]) -> usize {
        let n = enemies.len();
        assert!(n <= 64, "roll_spawn caps enemies at CAP = 64");
        let lanes = (n + 7) & !7;
        for (j, e) in enemies.iter().enumerate() {
            self.xs[j] = e.x;
            self.ys[j] = e.y;
            self.rs[j] = e.r;
        }
        for j in n..lanes {
            self.xs[j] = f64::INFINITY;
            self.ys[j] = f64::INFINITY;
            self.rs[j] = 0.0;
        }
        lanes
    }

    /// Bit j set unless enemy j fails the same axis-aligned box test the exact loop applies.
    fn box_mask(&self, lanes: usize, n: usize, x: f64, y: f64, r: f64) -> u64 {
        let mut mask = 0u64;
        for c in (0..lanes).step_by(8) {
            let mut bits = 0u64;
            for k in 0..8 {
                let j = c + k;
                let rad = r + self.rs[j];
                let dx = self.xs[j] - x;
                let dy = self.ys[j] - y;
                let keep = !((dx > rad) | (dx < -rad) | (dy > rad) | (dy < -rad));
                bits |= (keep as u64) << k;
            }
            mask |= bits << c;
        }
        if n < 64 {
            mask &= (1u64 << n) - 1;
        }
        mask
    }
}

/// Accumulates the push from neighbour `j` onto `i`; returns false when `j` is out of range.
#[inline(always)]
fn sep_term(pos: &[[f64; 3]], ix: f64, iy: f64, ir: f64, j: usize, px: &mut f64, py: &mut f64) -> bool {
    let min = (ir + pos[j][2]) * 0.82;
    let dx = ix - pos[j][0];
    if dx > min || dx < -min {
        return false;
    }
    let dy = iy - pos[j][1];
    if dy > min || dy < -min {
        return false;
    }
    let dd = dx * dx + dy * dy;
    if dd > min * min || dd < 1e-4 {
        return false;
    }
    let dist = dd.sqrt();
    let f = (min - dist) / min;
    let inv = 1.0 / dist;
    *px += dx * inv * f;
    *py += dy * inv * f;
    true
}

#[inline(always)]
fn bits_above(i: usize) -> u64 {
    if i >= 63 { 0 } else { u64::MAX << (i + 1) }
}

/// Same Gauss-Seidel pass as JS separateEnemies: enemies move in index order, later ones see
/// earlier moves, and each one stops after 7 neighbours taken in ascending index order.
///
/// The in-range test is exactly symmetric, so it runs once per unordered pair on the positions
/// at the start of the pass. Pairs involving an enemy that already moved this pass are re-tested
/// on current positions; `near` (the same box widened by the most an enemy can move) bounds them.
fn separate_enemies(enemies: &mut [Enemy], dt: f64, s: &mut Sep) {
    let n = enemies.len();
    let push = 42.0 * dt;
    let finite = enemies.iter().all(|e| e.x.is_finite() && e.y.is_finite() && e.r.is_finite());
    if n > 64 || !finite {
        s.pos.clear();
        s.pos.extend(enemies.iter().map(|e| [e.x, e.y, e.r]));
        sep_brute(enemies, push, &mut s.pos);
        return;
    }
    let lanes = (n + 7) & !7;
    for (j, e) in enemies.iter().enumerate() {
        s.xs[j] = e.x;
        s.ys[j] = e.y;
        s.rs[j] = e.r;
    }
    // Padding sits at +inf, so dx = -inf always fails the range test.
    for j in n..lanes {
        s.xs[j] = f64::INFINITY;
        s.ys[j] = f64::INFINITY;
        s.rs[j] = 0.0;
    }
    // 7 terms, each |dx/dist * f| <= 1 (plus rounding), scaled by push.
    let slack = 7.0 * push + 1.0;
    let mut extent = 0.0f64;
    for j in 0..n {
        extent = extent.max(s.xs[j].abs()).max(s.ys[j].abs()).max(s.rs[j].abs());
    }
    if extent > 1e5 {
        s.pos.clear();
        s.pos.extend(enemies.iter().map(|e| [e.x, e.y, e.r]));
        sep_brute(enemies, push, &mut s.pos);
        return;
    }
    for j in 0..lanes {
        s.xs32[j] = s.xs[j] as f32;
        s.ys32[j] = s.ys[j] as f32;
        s.rs32[j] = s.rs[j] as f32;
    }
    // Below 1e5 the f32 copies are within ~0.02 px, so `pad` keeps `near` a strict superset.
    let pad = (slack + 0.5) as f32;
    s.hit[..n].fill(0);
    s.near[..n].fill(0);
    for i in 0..n {
        let (ix, iy, ir) = (s.xs32[i], s.ys32[i], s.rs32[i]);
        let mut row = 0u64;
        for c in ((i + 1) & !7..lanes).step_by(8) {
            let mut nb = 0u64;
            for k in 0..8 {
                let j = c + k;
                let wide = (ir + s.rs32[j]) * 0.82 + pad;
                let near = ((ix - s.xs32[j]).abs() <= wide) & ((iy - s.ys32[j]).abs() <= wide);
                nb |= (near as u64) << k;
            }
            row |= nb << c;
        }
        row &= bits_above(i) & (u64::MAX >> (64 - n));
        s.near[i] |= row;
        let (fx, fy, fr) = (s.xs[i], s.ys[i], s.rs[i]);
        while row != 0 {
            let j = row.trailing_zeros() as usize;
            row &= row - 1;
            s.near[j] |= 1u64 << i;
            let min = (fr + s.rs[j]) * 0.82;
            let dx = fx - s.xs[j];
            let dy = fy - s.ys[j];
            let dd = dx * dx + dy * dy;
            let skip = dx > min || dx < -min || dy > min || dy < -min || dd > min * min || dd < 1e-4;
            if !skip {
                s.hit[i] |= 1u64 << j;
                s.hit[j] |= 1u64 << i;
            }
        }
    }
    let mut moved = 0u64;
    for i in 0..n {
        let (ix, iy, ir) = (s.xs[i], s.ys[i], s.rs[i]);
        let mut mask = s.hit[i] & !moved;
        let mut recheck = s.near[i] & moved;
        while recheck != 0 {
            let j = recheck.trailing_zeros() as usize;
            recheck &= recheck - 1;
            let min = (ir + s.rs[j]) * 0.82;
            let dx = ix - s.xs[j];
            let dy = iy - s.ys[j];
            let dd = dx * dx + dy * dy;
            let skip = dx > min || dx < -min || dy > min || dy < -min || dd > min * min || dd < 1e-4;
            if !skip {
                mask |= 1u64 << j;
            }
        }
        if mask == 0 {
            continue;
        }
        let mut px = 0.0;
        let mut py = 0.0;
        let mut count = 0;
        while mask != 0 {
            let j = mask.trailing_zeros() as usize;
            mask &= mask - 1;
            let min = (ir + s.rs[j]) * 0.82;
            let dx = ix - s.xs[j];
            let dy = iy - s.ys[j];
            let dist = (dx * dx + dy * dy).sqrt();
            let f = (min - dist) / min;
            let inv = 1.0 / dist;
            px += dx * inv * f;
            py += dy * inv * f;
            count += 1;
            if count > 6 {
                break;
            }
        }
        let e = &mut enemies[i];
        e.x += px * push;
        e.y += py * push;
        s.xs[i] = e.x;
        s.ys[i] = e.y;
        moved |= 1u64 << i;
    }
}

fn sep_brute(enemies: &mut [Enemy], push: f64, pos: &mut [[f64; 3]]) {
    let n = enemies.len();
    for i in 0..n {
        let [ix, iy, ir] = pos[i];
        let mut px = 0.0;
        let mut py = 0.0;
        let mut count = 0;
        for j in 0..n {
            if i != j && sep_term(pos, ix, iy, ir, j, &mut px, &mut py) {
                count += 1;
                if count > 6 {
                    break;
                }
            }
        }
        if count > 0 {
            let e = &mut enemies[i];
            e.x += px * push;
            e.y += py * push;
            pos[i][0] = e.x;
            pos[i][1] = e.y;
        }
    }
}

// ---------------------------------------------------------------- match

struct Match<'a, M: MathFns> {
    math: &'a M,
    data: &'a Data,
    tables: &'a Tables,
    mon: &'a Mon,
    start: &'a Move,
    opts: &'a Opts,
    dt: f64,
    knock_fade: f64,
    world: Rng,
    card_roll: Rng,
    state: State,
    has_sd: bool,
    has_hd: bool,
    status_ignored: bool,
    pl: Player,
    enemies: Vec<Enemy>,
    shots: Vec<Shot>,
    booms: Vec<Boom>,
    orbs: Vec<Orb>,
    e_shots: Vec<EShot>,
    hazards: Vec<Hazard>,
    spawn_n: u32,
    acc: f64,
    surge: f64,
    kills: u32,
    xp: f64,
    level: u32,
    need: f64,
    atk_cd: f64,
    t: f64,
    chip_t: f64,
    biome: usize,
    biome_t: f64,
    check_t: f64,
    weather: Option<Weather>,
    seq: u32,
    st: Derived<'a>,
    stat_dirty: bool,
    stat_snow: bool,
    angles: Vec<f64>,
    sep: Sep,
    shot_soa: ShotSoa,
    near_buf: Vec<(f64, usize)>,
    terrain: Option<Box<Terr>>,
    lava_t: f64,
}

fn xp_for<M: MathFns>(math: &M, level: u32) -> f64 {
    let l = level as f64;
    ((8.0 + l * 6.0 + math.pow(l, 1.75) * 1.6) * 4.0).floor()
}

fn spawn_rate<M: MathFns>(math: &M, t: f64) -> f64 {
    (1.6 + t * 0.028 + math.pow(t / 60.0, 1.6) * 0.5) * 0.24
}

/// Whether a move level carries a status the sim does not apply (the status_ignored flag). With
/// `Opts::status` every status is applied, but a move kind the sim never fires is not.
fn unmodelled(l: &MoveLvl, status_on: bool) -> bool {
    l.status && (!status_on || !l.kind.simulated())
}

fn move_has_status(m: &Move, status_on: bool) -> bool {
    m.levels.iter().any(|l| unmodelled(l, status_on)) || m.evo.as_ref().is_some_and(|e| unmodelled(e, status_on))
}

impl<'a, M: MathFns> Match<'a, M> {
    fn current_move(&self) -> &'a MoveLvl {
        let m = self.start;
        if self.state.evolved {
            if let Some(e) = &m.evo {
                return e;
            }
        }
        &m.levels[self.state.move_lvl.min(m.max_lvl) - 1]
    }

    fn buff_level(&self, id: usize, lvl: usize) -> &'a MoveLvl {
        let m = &self.data.moves[id];
        let index = lvl.clamp(1, m.max_lvl) - 1;
        &m.levels[index]
    }

    fn snow_now(&self) -> bool {
        matches!(self.weather, Some(w) if w.kind == Wx::Snow && weather_ramp(w.elapsed, w.dur) > 0.0)
    }

    /// stats() in match.js: recompute only when dirty or snow toggled.
    fn stats(&mut self) {
        let snow = self.snow_now();
        if !self.stat_dirty && snow == self.stat_snow {
            return;
        }
        self.stat_dirty = false;
        self.stat_snow = snow;
        let mv = self.current_move();
        let s = &self.state;
        let mut atk_buff = 0.0;
        let mut def_buff = 0.0;
        if s.sd > 0 && s.sd_t > 0.0 {
            atk_buff = s.sd_stacks * self.buff_level(self.data.swords_dance, s.sd).amount;
        }
        if s.hd > 0 && s.hd_t > 0.0 {
            def_buff = s.hd_stacks * self.buff_level(self.data.harden, s.hd).amount;
        }
        let mut spd = self.mon.spd * self.tables.spd[s.cards[Stat::Run as usize] as usize];
        if snow && !self.mon.types.contains(&T_ICE) {
            spd *= 0.9;
        }
        let st = &mut self.st;
        st.max_hp = self.mon.hp + 20.0 * s.cards[Stat::Hp as usize] as f64;
        st.atk = self.mon.atk * self.tables.atk[s.cards[Stat::Pow as usize] as usize] * (1.0 + atk_buff);
        st.spd = spd;
        st.red = jmin(0.8, jmin(0.7, 0.06 * s.cards[Stat::Cor as usize] as f64) + def_buff);
        st.cd_mul = self.tables.cd[s.cards[Stat::Cd as usize] as usize];
        st.regen = 0.9 * s.cards[Stat::Rgn as usize] as f64;
        st.melee = if mv.kind == Kind::Melee { 0.75 } else { 1.0 };
        st.mv = mv;
    }

    /// What a hit of this move applies (nothing unless `Opts::status`).
    fn status_of(&self, mv: &MoveLvl) -> Status {
        if !self.opts.status {
            return Status::default();
        }
        Status { slow: or(mv.slow, 0.0), burn: or(mv.burn, 0.0), poison: or(mv.poison, 0.0) }
    }

    fn wx(&self, ty: u8) -> f64 {
        weather_factor(&self.weather, ty)
    }

    fn hurt(&mut self, amount: f64, atk_ty: u8) {
        if self.pl.inv > 0.0 || self.pl.hp <= 0.0 {
            return;
        }
        let mult = type_mult(&self.data.tmult, atk_ty, self.mon.combo);
        let dmg = amount * mult * self.wx(atk_ty) * (1.0 - self.st.red) * self.st.melee;
        self.pl.hp -= dmg;
        self.pl.inv = INV;
    }

    // ------------------------------------------------ cards

    fn legal_cards(&self, out: &mut Vec<Card>) {
        out.clear();
        let s = &self.state;
        let meta = self.start;
        let need = meta.needs;
        let at_max = !s.evolved && s.move_lvl >= meta.max_lvl && meta.evo.is_some();
        if !s.evolved && s.move_lvl < meta.max_lvl {
            out.push(Card::Up);
        }
        if at_max {
            match need {
                Some(n) if s.cards[n as usize] < 1 => out.push(Card::Stat(n)),
                _ => out.push(Card::Evo),
            }
        }
        if self.has_sd && s.sd < 5 {
            out.push(Card::Sd);
        }
        if self.has_hd && s.hd < 5 {
            out.push(Card::Hd);
        }
        for st in STATS {
            if out.contains(&Card::Stat(st)) {
                continue;
            }
            if s.cards[st as usize] < CAPS[st as usize] {
                out.push(Card::Stat(st));
            }
        }
    }

    fn pick_card(&self, offered: &[Card]) -> Card {
        let s = &self.state;
        let meta = self.start;
        let need = meta.needs;
        let has = |c: Card| offered.contains(&c);
        let at_max = !s.evolved && s.move_lvl >= meta.max_lvl && meta.evo.is_some();
        if has(Card::Up) && !s.evolved && s.move_lvl < meta.max_lvl {
            return Card::Up;
        }
        if at_max {
            if let Some(n) = need {
                if s.cards[n as usize] < 1 && has(Card::Stat(n)) {
                    return Card::Stat(n);
                }
            }
            let gate_ok = match need {
                None => true,
                Some(n) => s.cards[n as usize] >= 1,
            };
            if gate_ok && has(Card::Evo) {
                return Card::Evo;
            }
        }
        for c in FILL {
            if has(c) {
                return c;
            }
        }
        offered[0]
    }

    fn apply_card(&mut self, c: Card) {
        let s = &mut self.state;
        match c {
            Card::Up => s.move_lvl += 1,
            Card::Evo => s.evolved = true,
            Card::Sd => s.sd = (s.sd + 1).min(5),
            Card::Hd => s.hd = (s.hd + 1).min(5),
            Card::Stat(st) => {
                if s.cards[st as usize] < CAPS[st as usize] {
                    s.cards[st as usize] += 1;
                }
            }
        }
    }

    fn level_up(&mut self) {
        let mut legal = Vec::with_capacity(12);
        self.legal_cards(&mut legal);
        if legal.is_empty() {
            return;
        }
        for i in (1..legal.len()).rev() {
            let j = (self.card_roll.next() * (i + 1) as f64).floor() as usize;
            legal.swap(i, j);
        }
        legal.truncate(3);
        let id = self.pick_card(&legal);
        let before = self.st.max_hp;
        self.apply_card(id);
        if id == Card::Sd {
            self.state.sd_cd = 0.0;
        }
        if id == Card::Hd {
            self.state.hd_cd = 0.0;
        }
        self.stat_dirty = true;
        self.stats();
        let after = self.st.max_hp;
        if after > before {
            self.pl.hp += after - before;
        }
    }

    fn grant_xp(&mut self, amount: f64) {
        self.xp += amount;
        while self.xp >= self.need {
            self.xp -= self.need;
            self.level += 1;
            self.need = xp_for(self.math, self.level);
            if self.opts.cards {
                self.level_up();
            }
        }
    }

    fn reap(&mut self) {
        let mut i = self.enemies.len();
        while i > 0 {
            i -= 1;
            if self.enemies[i].hp > 0.0 {
                continue;
            }
            let gained = or(self.enemies[i].xp, 1.0) * 5.6;
            self.enemies.remove(i);
            self.kills += 1;
            self.grant_xp(gained);
        }
    }

    // ------------------------------------------------ attacking

    fn cast(&mut self) {
        let mv = self.st.mv;
        if unmodelled(mv, self.opts.status) {
            self.status_ignored = true;
        }
        let st = self.status_of(mv);
        let math = self.math;
        let aim = match nearest(&self.enemies, self.pl.x, self.pl.y) {
            Some(i) => math.atan2(self.enemies[i].y - self.pl.y, self.enemies[i].x - self.pl.x),
            None => self.pl.aim,
        };
        self.pl.aim = aim;
        let tm = &self.data.tmult;
        let atk = self.st.atk;
        match mv.kind {
            Kind::Melee => {
                let (px, py) = (self.pl.x, self.pl.y);
                for e in self.enemies.iter_mut() {
                    if in_melee(math, px, py, aim, mv.arc, mv.radius, e.x, e.y, e.r) {
                        strike(e, mv.dmg, atk, mv.ty, tm, &self.weather, st);
                    }
                }
            }
            Kind::Beam => {
                let (px, py) = (self.pl.x, self.pl.y);
                for e in self.enemies.iter_mut() {
                    if in_beam(math, px, py, aim, mv.radius, mv.width, e.x, e.y, e.r) {
                        strike(e, mv.dmg, atk, mv.ty, tm, &self.weather, st);
                    }
                }
            }
            Kind::Orbit => {
                let count = or(mv.count, 1.0);
                while (self.orbs.len() as f64) < count {
                    let a = (self.orbs.len() as f64 / count) * PI * 2.0;
                    self.orbs.push(Orb { angle: a, inside: Vec::new() });
                }
                if self.orbs.len() as f64 > count {
                    self.orbs.truncate(count as usize);
                }
            }
            Kind::Nova => {
                let count = or(mv.count, 1.0);
                let mut i = 0.0;
                while i < count {
                    self.push_shot((i / count) * PI * 2.0, mv);
                    i += 1.0;
                }
            }
            Kind::Projectile => {
                let mut angles = std::mem::take(&mut self.angles);
                fan_angles(aim, or(mv.count, 1.0), or(mv.spread, 0.0), &mut angles);
                for &a in &angles {
                    self.push_shot(a, mv);
                }
                self.angles = angles;
            }
            Kind::Boomerang => {
                let mut angles = std::mem::take(&mut self.angles);
                fan_angles(aim, or(mv.count, 1.0), or(mv.spread, 0.0), &mut angles);
                for &a in &angles {
                    let dx = math.cos(a);
                    let dy = math.sin(a);
                    self.booms.push(Boom {
                        st,
                        ox: self.pl.x,
                        oy: self.pl.y,
                        dx,
                        dy,
                        dist: 0.0,
                        dir: 1.0,
                        max: mv.radius,
                        speed: mv.speed,
                        r: or(mv.size, 6.0),
                        hit: Vec::new(),
                        dmg: mv.dmg,
                        atk,
                        ty: mv.ty,
                    });
                }
                self.angles = angles;
            }
            Kind::Inert => {}
        }
    }

    fn push_shot(&mut self, angle: f64, mv: &MoveLvl) {
        let speed = mv.speed;
        let vx = self.math.cos(angle) * speed;
        let vy = self.math.sin(angle) * speed;
        let st = self.status_of(mv);
        self.shots.push(Shot {
            x: self.pl.x,
            y: self.pl.y,
            vx,
            vy,
            speed,
            r: or(mv.size, 7.0),
            life: mv.life,
            left: or(mv.pierce, 0.0) + 1.0,
            hit: Vec::new(),
            dmg: mv.dmg,
            atk: self.st.atk,
            ty: mv.ty,
            homing: or(mv.homing, 0.0),
            st,
        });
        if self.shots.len() > 80 {
            self.shots.remove(0);
        }
    }

    fn step_shots(&mut self) {
        let math = self.math;
        let dt = self.dt;
        let tm = &self.data.tmult;
        let weather = &self.weather;
        let enemies = &mut self.enemies;
        let shots = &mut self.shots;
        let terrain = &mut self.terrain;
        // strike() only touches hp/shield, so positions stay fixed for the whole shot pass.
        let soa = &mut self.shot_soa;
        let lanes = soa.load(enemies);
        let mut i = shots.len();
        while i > 0 {
            i -= 1;
            let shot = &mut shots[i];
            // steer(): nearest() is pure, so it only matters for homing shots.
            let turn = shot.homing;
            let near = if turn != 0.0 && !turn.is_nan() { nearest(enemies, shot.x, shot.y) } else { None };
            if let Some(n) = near {
                // js/entities/projectile.js: homing only locks onto enemies within 340 px.
                if len(enemies[n].x - shot.x, enemies[n].y - shot.y) <= 340.0 {
                    let desired = math.atan2(enemies[n].y - shot.y, enemies[n].x - shot.x);
                    let current = math.atan2(shot.vy, shot.vx);
                    let mut delta = desired - current;
                    while delta > PI {
                        delta -= PI * 2.0;
                    }
                    while delta < -PI {
                        delta += PI * 2.0;
                    }
                    let max = turn * dt;
                    if delta > max {
                        delta = max;
                    } else if delta < -max {
                        delta = -max;
                    }
                    let angle = current + delta;
                    shot.vx = math.cos(angle) * shot.speed;
                    shot.vy = math.sin(angle) * shot.speed;
                }
            }
            shot.x += shot.vx * dt;
            shot.y += shot.vy * dt;
            shot.life -= dt;
            if shot.life <= 0.0 {
                shots.remove(i);
                continue;
            }
            if let Some(t) = terrain {
                if let Some(b) = t.world.projectile_block(shot.x, shot.y, shot.r) {
                    if let Block::Prop { chunk, ix, destructible: true } = b {
                        t.world.damage_prop(chunk, ix, shot.dmg * shot.atk);
                    }
                    shots.remove(i);
                    continue;
                }
            }
            let mut mask = soa.box_mask(lanes, enemies.len(), shot.x, shot.y, shot.r);
            while mask != 0 {
                let k = mask.trailing_zeros() as usize;
                mask &= mask - 1;
                let e = &mut enemies[k];
                if e.hp <= 0.0 || has(&shot.hit, e.id) {
                    continue;
                }
                let rad = shot.r + e.r;
                let dx = e.x - shot.x;
                let dy = e.y - shot.y;
                if dx > rad || dx < -rad || dy > rad || dy < -rad {
                    continue;
                }
                if len(dx, dy) < rad {
                    shot.hit.push(e.id);
                    shot.left -= 1.0;
                    strike(e, shot.dmg, shot.atk, shot.ty, tm, weather, shot.st);
                    if shot.left <= 0.0 {
                        break;
                    }
                }
            }
            if shot.left <= 0.0 {
                shots.remove(i);
            }
        }

        let booms = &mut self.booms;
        let mut i = booms.len();
        while i > 0 {
            i -= 1;
            let b = &mut booms[i];
            b.dist += b.speed * dt * b.dir;
            if b.dir > 0.0 && b.dist >= b.max {
                b.dist = b.max;
                b.dir = -1.0;
                b.hit.clear();
            }
            if b.dir < 0.0 && b.dist <= 0.0 {
                booms.remove(i);
                continue;
            }
            let x = b.ox + b.dx * b.dist;
            let y = b.oy + b.dy * b.dist;
            for e in enemies.iter_mut() {
                if e.hp <= 0.0 || has(&b.hit, e.id) {
                    continue;
                }
                if len(e.x - x, e.y - y) < b.r + e.r {
                    b.hit.push(e.id);
                    strike(e, b.dmg, b.atk, b.ty, tm, weather, b.st);
                }
            }
        }
        self.step_orbs();
    }

    fn step_orbs(&mut self) {
        let mv = self.st.mv;
        if mv.kind != Kind::Orbit {
            self.orbs.clear();
            return;
        }
        let st = self.status_of(mv);
        let math = self.math;
        let count = or(mv.count, 1.0);
        while (self.orbs.len() as f64) < count {
            let a = (self.orbs.len() as f64 / count) * PI * 2.0;
            self.orbs.push(Orb { angle: a, inside: Vec::new() });
        }
        let tm = &self.data.tmult;
        let weather = &self.weather;
        let (plx, ply, atk, dt) = (self.pl.x, self.pl.y, self.st.atk, self.dt);
        for orb in self.orbs.iter_mut() {
            orb.angle += or(mv.speed, 1.0) * dt;
            let x = plx + math.cos(orb.angle) * mv.radius;
            let y = ply + math.sin(orb.angle) * mv.radius;
            for e in self.enemies.iter_mut() {
                if e.hp <= 0.0 {
                    continue;
                }
                let overlap = len(e.x - x, e.y - y) < or(mv.size, 8.0) + e.r;
                if overlap {
                    if !has(&orb.inside, e.id) {
                        orb.inside.push(e.id);
                        strike(e, mv.dmg, atk, mv.ty, tm, weather, st);
                    }
                } else if let Some(k) = orb.inside.iter().position(|&id| id == e.id) {
                    orb.inside.swap_remove(k);
                }
            }
        }
    }

    // ------------------------------------------------ bot

    fn decide(&mut self) {
        let pl = &mut self.pl;
        pl.react -= self.dt;
        if pl.react > 0.0 {
            return;
        }
        pl.react = 0.25;
        let mut fx = 0.0;
        let mut fy = 0.0;
        let mut near: Option<usize> = None;
        let mut near_d = f64::INFINITY;
        let keep = keep_distance(self.st.mv);
        for (i, e) in self.enemies.iter().enumerate() {
            if e.hp <= 0.0 {
                continue;
            }
            let dx = e.x - pl.x;
            let dy = e.y - pl.y;
            let dist = or(len(dx, dy), 1e-6);
            if dist < near_d {
                near_d = dist;
                near = Some(i);
            }
            if self.opts.bot == Bot::Repulse {
                let gap = dist - e.r - pl.r;
                if gap < 160.0 {
                    let w = 1.0 / jmax(8.0, gap);
                    fx -= (dx / dist) * w;
                    fy -= (dy / dist) * w;
                }
            }
        }
        let Some(n) = near else {
            pl.dirx = 0.0;
            pl.diry = 0.0;
            return;
        };
        let e = &self.enemies[n];
        let dx = e.x - pl.x;
        let dy = e.y - pl.y;
        let dist = or(len(dx, dy), 1e-6);
        let gap = dist - e.r - pl.r;
        if self.opts.bot == Bot::Line {
            if gap < keep {
                fx = -dx / dist;
                fy = -dy / dist;
            } else if gap > keep {
                fx = dx / dist;
                fy = dy / dist;
            } else {
                fx = 0.0;
                fy = 0.0;
            }
        } else if gap > keep {
            fx += dx / dist;
            fy += dy / dist;
        }
        let mag = len(fx, fy);
        if mag < 1e-6 {
            pl.dirx = 0.0;
            pl.diry = 0.0;
        } else {
            pl.dirx = fx / mag;
            pl.diry = fy / mag;
        }
        if let Some(t) = &mut self.terrain {
            if pl.dirx != 0.0 || pl.diry != 0.0 {
                let avoid = match t.world.liquid {
                    Liquid::Water => !self.mon.types.contains(&T_WATER),
                    Liquid::Lava => !self.mon.types.contains(&T_FIRE),
                };
                (pl.dirx, pl.diry) = steer(&mut t.world, pl.x, pl.y, pl.r, (pl.dirx, pl.diry), avoid);
            }
        }
    }

    // ------------------------------------------------ spawning

    fn sample_def(&mut self) -> Cand {
        let t = self.t;
        let tiers = &self.data.tiers;
        let mut total = 0.0;
        let mut bag: [(usize, f64); 8] = [(0, 0.0); 8];
        let mut nb = 0;
        for (i, tier) in tiers.iter().enumerate() {
            if t >= tier.from {
                bag[nb] = (i, if t - tier.from > 260.0 { 3.0 } else { 10.0 });
                nb += 1;
            }
        }
        for p in &bag[..nb] {
            total += p.1;
        }
        let mut x = self.world.next() * total;
        let mut tier = bag[0].0;
        for p in &bag[..nb] {
            x -= p.1;
            if x <= 0.0 {
                tier = p.0;
                break;
            }
        }
        let cands = &tiers[tier].cands;
        let picked = &cands[(self.world.next() * cands.len() as f64).floor() as usize];
        let mut c = picked.clone();
        if matches!(c.def.beh, Beh::Chase | Beh::Charger | Beh::Tank) && self.world.next() < 1.0 / 7.0 {
            c.def.beh = Beh::Runner;
            c.def.spd = js_round(c.def.spd * 1.6);
            c.def.hp = js_round(c.def.hp * 0.7);
        }
        c
    }

    fn roll_spawn(&mut self, angle: Option<f64>) {
        let cand = self.sample_def();
        let ai_seed = ((self.opts.seed as u64 + 1) * 1000003 + self.spawn_n as u64) as u32;
        let mut ai = Rng::new(ai_seed);
        self.spawn_n += 1;
        let aim = match angle {
            None => self.world.next() * PI * 2.0,
            Some(a) => a,
        };
        let dd = OUTER + 10.0 + self.world.next() * 60.0;
        if self.enemies.len() >= CAP {
            return;
        }
        let t = self.t;
        let sc_hp = 1.0 + t / 95.0;
        let sc_dmg = 1.0 + t / 420.0;
        let sc_spd = 1.0 + jmin(0.35, t / 1400.0);
        let elite = self.enemies.len() as f64 >= CAP as f64 * ELITE;
        let def = cand.def;
        let mut x = self.pl.x + self.math.cos(aim) * dd;
        let mut y = self.pl.y + self.math.sin(aim) * dd * 0.9;
        if let Some(t) = &mut self.terrain {
            if !cand.fly {
                let mut tries = 1;
                while !t.world.is_free(x, y, 14.0) {
                    if tries == 8 {
                        return;
                    }
                    tries += 1;
                    let a = aim + (ai.next() * 1.8 - 0.9);
                    x = self.pl.x + a.cos() * dd;
                    y = self.pl.y + a.sin() * dd * 0.9;
                }
            }
        }
        let hpk = 3.3 + jmin(1.7, t / 210.0);
        let shot_cd = or(def.shot_cd, 2.0) * ai.next();
        let skill = ai.next() * 3.0;
        let heal_cd = or(def.shot_cd, 3.5) * ai.next();
        let shield_cd = 6.0 * ai.next();
        let dmg = def.dmg * sc_dmg * DMG_K;
        let mut e = Enemy {
            id: self.seq,
            dex: cand.dex,
            x,
            y,
            r: cand.r,
            combo: cand.combo,
            ty0: cand.ty0,
            xp: or(def.xp, 1.0),
            beh: def.beh,
            spd: def.spd * sc_spd,
            dmg,
            hp: def.hp * sc_hp * hpk,
            max: 0.0,
            touch: 0.0,
            kx: 0.0,
            ky: 0.0,
            phase: Phase::Walk,
            pt: 0.0,
            shot_cd,
            skill,
            heal_cd,
            shield_cd,
            jump: None,
            fuse: -1.0,
            shield: 0.0,
            shield_t: 0.0,
            shot: 0.0,
            cx: 1.0,
            cy: 0.0,
            ai,
            def,
            fly: cand.fly,
            water: cand.water,
            fire: cand.fire,
            los: (f64::NEG_INFINITY, false),
            side_t: 0.0,
            side: 1.0,
            stuck_t: 0.0,
            lava_t: 0.0,
            slow: 0.0,
            slow_t: 0.0,
            burn: 0.0,
            burn_t: 0.0,
            burn_tick: 0.0,
            poison: 0.0,
            poison_t: 0.0,
            poison_tick: 0.0,
        };
        self.seq += 1;
        e.shot = or(e.def.shot_dmg, 10.0) * (e.dmg / or(e.def.dmg, 1.0));
        if elite {
            e.hp *= 1.6;
            e.dmg *= 1.25;
            e.shot *= 1.25;
        }
        e.max = e.hp;
        self.enemies.push(e);
    }

    fn tick_weather(&mut self) {
        let dt = self.dt;
        self.biome_t += dt;
        if self.biome_t >= 240.0 {
            self.biome = (self.biome + 1) % BIOMES.len();
            self.biome_t = 0.0;
        }
        if let Some(w) = &mut self.weather {
            w.elapsed += dt;
            if w.elapsed >= w.dur {
                self.weather = None;
            }
        } else {
            self.check_t -= dt;
            if self.check_t <= 0.0 {
                self.check_t = 60.0;
                if self.world.next() < 0.18 {
                    let kind = weighted_kind(BIOMES[self.biome], self.world.next());
                    let dur = 55.0 + self.world.next() * 20.0;
                    self.weather = Some(Weather { kind, elapsed: 0.0, dur });
                }
            }
        }
        if let Some(w) = self.weather {
            if w.kind == Wx::Sand || w.kind == Wx::Snow {
                self.chip_t += dt;
                if self.chip_t >= 2.0 {
                    self.chip_t -= 2.0;
                    let immune = if w.kind == Wx::Sand {
                        self.mon.types.iter().any(|&t| t == T_ROCK || t == T_GROUND || t == T_STEEL)
                    } else {
                        self.mon.types.contains(&T_ICE)
                    };
                    if !immune && weather_ramp(w.elapsed, w.dur) > 0.0 {
                        self.stats();
                        self.pl.hp -= 0.012 * self.st.max_hp;
                    }
                }
            }
        }
    }

    fn tick_buffs(&mut self) {
        for which in 0..2 {
            let (id, lvl) = if which == 0 {
                (self.data.swords_dance, self.state.sd)
            } else {
                (self.data.harden, self.state.hd)
            };
            if lvl == 0 {
                continue;
            }
            let inst = self.buff_level(id, lvl);
            let cd_mul = self.st.cd_mul;
            let dt = self.dt;
            let s = &mut self.state;
            let (time, stacks, cd) = if which == 0 {
                (&mut s.sd_t, &mut s.sd_stacks, &mut s.sd_cd)
            } else {
                (&mut s.hd_t, &mut s.hd_stacks, &mut s.hd_cd)
            };
            if *time > 0.0 {
                *time -= dt;
                if *time <= 0.0 {
                    self.stat_dirty = true;
                }
            }
            if *time <= 0.0 {
                *stacks = 0.0;
            }
            *cd -= dt;
            if *cd <= 0.0 {
                *stacks = jmin(inst.stacks, *stacks + 1.0);
                *time = inst.dur;
                *cd = inst.cd * cd_mul;
                self.stat_dirty = true;
            }
        }
    }

    // ------------------------------------------------ enemies

    fn step_enemies(&mut self) {
        let math = self.math;
        let dt = self.dt;
        let knock_fade = self.knock_fade;
        let lvl = self.level as f64;
        if let Some(t) = &mut self.terrain {
            let Terr { world, path } = &mut **t;
            path.timer -= dt;
            if path.timer <= 0.0 {
                path.timer = PATH_EVERY;
                path.build(world, self.pl.x, self.pl.y);
            }
        }
        let mut i = self.enemies.len();
        while i > 0 {
            i -= 1;
            let (plx, ply, pdirx, pdiry, plr) = (self.pl.x, self.pl.y, self.pl.dirx, self.pl.diry, self.pl.r);
            let e = &mut self.enemies[i];
            if e.hp <= 0.0 {
                continue;
            }
            if e.touch > 0.0 {
                e.touch -= dt;
            }
            if e.slow_t > 0.0 {
                e.slow_t -= dt;
                if e.slow_t <= 0.0 {
                    e.slow = 0.0;
                }
            }
            // Burn and poison: enemy.js update(). Burn scales with the player's level.
            if e.burn > 0.0 {
                e.burn_t -= dt;
                e.burn_tick -= dt;
                if e.burn_tick <= 0.0 {
                    e.burn_tick = BURN_TICK;
                    hurt_dot(e, 1.6 * e.burn * (1.0 + lvl * 0.06));
                }
                if e.burn_t <= 0.0 {
                    e.burn = 0.0;
                }
            }
            if e.poison > 0.0 {
                e.poison_t -= dt;
                e.poison_tick -= dt;
                if e.poison_tick <= 0.0 {
                    e.poison_tick = POISON_TICK;
                    hurt_dot(e, e.max * 0.012 * e.poison + 1.0);
                }
                if e.poison_t <= 0.0 {
                    e.poison = 0.0;
                }
            }
            if e.hp <= 0.0 {
                continue;
            }
            if e.shield_t > 0.0 {
                e.shield_t -= dt;
                if e.shield_t <= 0.0 {
                    e.shield = 0.0;
                }
            }
            let mut dx = plx - e.x;
            let mut dy = ply - e.y;
            let dist = or(len(dx, dy), 1e-3);
            dx /= dist;
            dy /= dist;
            if dist > OUTER + 250.0 {
                let a = math.atan2(pdiry, pdirx) + (e.ai.next() * 1.8 - 0.9);
                let dd = OUTER + 10.0 + e.ai.next() * 60.0;
                e.x = plx + math.cos(a) * dd;
                e.y = ply + math.sin(a) * dd * 0.9;
                e.phase = Phase::Walk;
                collide_enemy(&mut self.terrain, e, e.x, e.y, 0.0, 0.0, dt);
                continue;
            }
            if let Some(j) = &mut e.jump {
                j.t += dt;
                if j.t >= j.dur {
                    e.x = j.tx;
                    e.y = j.ty;
                    e.jump = None;
                    collide_enemy(&mut self.terrain, e, e.x, e.y, 0.0, 0.0, dt);
                }
                continue;
            }
            if e.fuse >= 0.0 {
                e.fuse -= dt;
                if e.fuse <= 0.0 {
                    e.hp = 0.0;
                }
                continue;
            }
            let (ox, oy) = (e.x, e.y);
            // const spd = this.spd * (1 - this.slow) * ... in repo/js/entities/enemy.js (dash uses it too)
            let mut spd = e.spd * (1.0 - e.slow);
            let mut steer_dir: Option<(f64, f64)> = None;
            if let Some(t) = &mut self.terrain {
                let Terr { world, path } = &mut **t;
                if !e.fly && world.is_liquid(e.x, e.y) {
                    match world.liquid {
                        Liquid::Water => {
                            if !e.water {
                                spd *= 0.55;
                            }
                        }
                        Liquid::Lava => {
                            if !e.fire {
                                e.lava_t -= dt;
                                if e.lava_t <= 0.0 {
                                    e.lava_t = 0.5;
                                    e.hp -= 6.0 + e.max * 0.04;
                                    if e.hp <= 0.0 {
                                        continue;
                                    }
                                }
                            }
                        }
                    }
                }
                if e.side_t > 0.0 {
                    e.side_t -= dt;
                    let a = dy.atan2(dx) + e.side * 1.25;
                    steer_dir = Some((a.cos(), a.sin()));
                }
                if !e.fly && e.phase != Phase::Dash && e.side_t <= 0.0 {
                    if let Some(pd) = path.dir_for(e.x, e.y, e.r, plx, ply, self.t, &mut e.los) {
                        if !(e.beh.keeps() && dist < or(e.def.range, 200.0) * 0.82) {
                            steer_dir = Some(pd);
                        }
                    }
                }
            }
            let (mdx, mdy) = steer_dir.unwrap_or((dx, dy));
            let mut vx = mdx * spd * 1.0;
            let mut vy = mdy * spd * 1.0;
            let beh = e.beh;
            if beh == Beh::Chase || beh == Beh::Tank {
                e.x += e.kx * dt;
                e.y += e.ky * dt;
                e.kx *= knock_fade;
                e.ky *= knock_fade;
                e.x += vx * dt;
                e.y += vy * dt;
                collide_enemy(&mut self.terrain, e, ox, oy, vx, vy, dt);
                let rad = e.r + plr;
                let gx = e.x - plx;
                let gy = e.y - ply;
                if (gx > rad || gx < -rad || gy > rad || gy < -rad) || e.touch > 0.0 {
                    continue;
                }
                let gap = len(gx, gy);
                if gap <= rad {
                    e.touch = TOUCH;
                    let (dmg, ty) = (e.dmg, e.ty0);
                    let nx = gx / or(gap, 1.0);
                    let ny = gy / or(gap, 1.0);
                    e.kx += nx * 150.0;
                    e.ky += ny * 150.0;
                    self.hurt(dmg, ty);
                }
                continue;
            }
            if beh == Beh::Runner && steer_dir.is_none() {
                let lead = jmin(1.4, jmax(0.0, dist / jmax(60.0, e.spd)));
                let tx = plx + pdirx * self.st.spd * lead - e.x;
                let ty = ply + pdiry * self.st.spd * lead - e.y;
                let mag = or(len(tx, ty), 1.0);
                vx = (tx / mag) * spd;
                vy = (ty / mag) * spd;
            }
            if beh == Beh::Bomber && dist < e.r + plr + 26.0 {
                e.fuse = 1.0;
                let hz = Hazard {
                    kind: HKind::Zone,
                    x: e.x,
                    y: e.y,
                    r: 62.0,
                    angle: 0.0,
                    len: 0.0,
                    w: 0.0,
                    delay: 1.0,
                    t: 0.0,
                    dmg: e.dmg * 1.4,
                    ty: e.ty0,
                };
                self.hazards.push(hz);
                continue;
            }
            if beh == Beh::Jumper {
                e.skill -= dt;
                if e.skill <= 0.0 {
                    if dist < 250.0 {
                        e.skill = 5.0 + e.ai.next() * 2.0;
                        e.jump = Some(Jump { tx: plx, ty: ply, t: -0.45, dur: 0.6 });
                        let hz = Hazard {
                            kind: HKind::Zone,
                            x: plx,
                            y: ply,
                            r: 50.0,
                            angle: 0.0,
                            len: 0.0,
                            w: 0.0,
                            delay: 1.05,
                            t: 0.0,
                            dmg: e.dmg * 1.2,
                            ty: e.ty0,
                        };
                        self.hazards.push(hz);
                        continue;
                    }
                    e.skill = 0.5;
                }
            }
            if beh == Beh::Charger {
                e.pt -= dt;
                match e.phase {
                    Phase::Walk => {
                        if dist < 200.0 && e.pt <= 0.0 {
                            e.phase = Phase::Aim;
                            e.pt = 0.55;
                        }
                    }
                    Phase::Aim => {
                        vx = 0.0;
                        vy = 0.0;
                        if e.pt <= 0.0 {
                            e.phase = Phase::Dash;
                            e.pt = 0.42;
                            e.cx = mdx;
                            e.cy = mdy;
                        }
                    }
                    Phase::Dash => {
                        vx = e.cx * spd * 3.4;
                        vy = e.cy * spd * 3.4;
                        if e.pt <= 0.0 {
                            e.phase = Phase::Walk;
                            e.pt = 1.1;
                        }
                    }
                }
            }
            if beh.keeps() {
                let range = or(e.def.range, 200.0);
                let hold = range * 0.82;
                if dist < hold * 0.75 {
                    vx = -dx * spd * 0.8;
                    vy = -dy * spd * 0.8;
                } else if dist < hold {
                    vx *= 0.1;
                    vy *= 0.1;
                }
                e.shot_cd -= dt;
                if e.shot_cd <= 0.0 && dist < range {
                    e.shot_cd = or(e.def.shot_cd, 2.0);
                    let (ex, ey, shot, ty) = (e.x, e.y, e.shot, e.ty0);
                    let shoot = |spread: f64, n: usize, k: f64, out: &mut Vec<EShot>| {
                        let base = math.atan2(dy, dx);
                        for j in 0..n {
                            let a = base + if n == 1 { 0.0 } else { (j as f64 / (n - 1) as f64 - 0.5) * spread };
                            out.push(EShot {
                                x: ex,
                                y: ey,
                                vx: math.cos(a) * 190.0,
                                vy: math.sin(a) * 190.0,
                                r: 7.0,
                                life: 2.4,
                                dmg: shot * k,
                                ty,
                            });
                        }
                    };
                    match beh {
                        Beh::Ranged => shoot(0.0, 1, 1.0, &mut self.e_shots),
                        Beh::Fan => {
                            let n = or(e.def.fan_n, 5.0);
                            shoot(if n == 3.0 { 0.6 } else { 0.9 }, n as usize, 0.65, &mut self.e_shots);
                        }
                        Beh::Beamer => {
                            let angle = math.atan2(dy, dx);
                            self.hazards.push(Hazard {
                                kind: HKind::Beam,
                                x: ex,
                                y: ey,
                                r: 0.0,
                                angle,
                                len: 360.0,
                                w: 22.0,
                                delay: 1.0,
                                t: 0.0,
                                dmg: shot * 1.05,
                                ty,
                            });
                        }
                        Beh::Zoner => {
                            let n = 1 + (e.ai.next() * or(e.def.zones, 3.0)).floor() as usize;
                            for j in 0..n {
                                let x = plx + if j > 0 { e.ai.next() * 140.0 - 70.0 } else { 0.0 };
                                let y = ply + if j > 0 { e.ai.next() * 110.0 - 55.0 } else { 0.0 };
                                self.hazards.push(Hazard {
                                    kind: HKind::Zone,
                                    x,
                                    y,
                                    r: 44.0,
                                    angle: 0.0,
                                    len: 0.0,
                                    w: 0.0,
                                    delay: 1.2,
                                    t: 0.0,
                                    dmg: shot * 0.95,
                                    ty,
                                });
                            }
                        }
                        _ => {}
                    }
                }
            }
            if beh == Beh::Healer {
                e.heal_cd -= dt;
                if e.heal_cd <= 0.0 {
                    e.heal_cd = or(e.def.shot_cd, 3.5);
                    let (hx, hy) = (e.x, e.y);
                    let (atk, base) = (self.st.atk, self.mon.atk);
                    pulse_healer(math, hx, hy, &mut self.enemies, atk, base);
                }
            }
            let e = &mut self.enemies[i];
            if beh == Beh::Shielder {
                e.shield_cd -= dt;
                if e.shield_cd <= 0.0 {
                    e.shield_cd = 6.0;
                    let (sx, sy) = (e.x, e.y);
                    pulse_shield(sx, sy, &mut self.enemies, &mut self.near_buf);
                }
            }
            let e = &mut self.enemies[i];
            e.x += e.kx * dt;
            e.y += e.ky * dt;
            e.kx *= knock_fade;
            e.ky *= knock_fade;
            e.x += vx * dt;
            e.y += vy * dt;
            collide_enemy(&mut self.terrain, e, ox, oy, vx, vy, dt);
            let rad = e.r + plr;
            let gx = e.x - plx;
            let gy = e.y - ply;
            if (gx > rad || gx < -rad || gy > rad || gy < -rad) || e.touch > 0.0 || beh.no_touch() {
                continue;
            }
            let gap = len(gx, gy);
            if gap <= rad {
                e.touch = TOUCH;
                let (dmg, ty) = (e.dmg, e.ty0);
                let nx = gx / or(gap, 1.0);
                let ny = gy / or(gap, 1.0);
                e.kx += nx * 150.0;
                e.ky += ny * 150.0;
                self.hurt(dmg, ty);
            }
        }
        if let Some(t) = &mut self.terrain {
            let before: Vec<(f64, f64)> = self.enemies.iter().map(|e| (e.x, e.y)).collect();
            separate_enemies(&mut self.enemies, dt, &mut self.sep);
            for (e, &(bx, by)) in self.enemies.iter_mut().zip(&before) {
                if !e.fly && e.hp > 0.0 && (e.x != bx || e.y != by) {
                    t.world.collide(&mut e.x, &mut e.y, e.r);
                }
            }
        } else {
            separate_enemies(&mut self.enemies, dt, &mut self.sep);
        }

        let mut i = self.e_shots.len();
        while i > 0 {
            i -= 1;
            let s = &mut self.e_shots[i];
            s.x += s.vx * dt;
            s.y += s.vy * dt;
            s.life -= dt;
            if s.life <= 0.0 {
                self.e_shots.remove(i);
                continue;
            }
            if let Some(t) = &mut self.terrain {
                if t.world.projectile_block(s.x, s.y, s.r).is_some() {
                    self.e_shots.remove(i);
                    continue;
                }
            }
            if len(s.x - self.pl.x, s.y - self.pl.y) < s.r + self.pl.r {
                let (dmg, ty) = (s.dmg, s.ty);
                self.hurt(dmg, ty);
                self.e_shots.remove(i);
            }
        }

        let mut i = self.hazards.len();
        while i > 0 {
            i -= 1;
            let h = &mut self.hazards[i];
            h.t += dt;
            if h.t < h.delay {
                continue;
            }
            let pl = &self.pl;
            let inside = if h.kind == HKind::Zone {
                len(pl.x - h.x, pl.y - h.y) < h.r + pl.r * 0.6
            } else {
                let ca = math.cos(h.angle);
                let sa = math.sin(h.angle);
                let px = pl.x - h.x;
                let py = pl.y - h.y;
                let along = px * ca + py * sa;
                along >= -pl.r && along <= h.len + pl.r && (-px * sa + py * ca).abs() <= h.w / 2.0 + pl.r * 0.6
            };
            let (dmg, ty) = (h.dmg, h.ty);
            if inside {
                self.hurt(dmg, ty);
            }
            self.hazards.remove(i);
        }
    }
}

/// One closed run. Same contract as runMatch in sim/match.js (no presets,
/// spawning and weather always on, recordHits/trace not supported).
pub fn run_match<M: MathFns>(
    math: &M,
    data: &Data,
    tables: &Tables,
    mon: &Mon,
    start: usize,
    opts: &Opts,
) -> RunResult {
    let dt = DT;
    let max_time = opts.seconds;
    let knock_fade = math.pow(0.0015, dt);
    let start_move = &data.moves[start];
    let mut world = Rng::new(opts.seed);
    let card_roll = Rng::new(opts.seed.wrapping_add(0xA5A5));
    let surge = world.next() * 20.0 + 10.0;
    let mut m = Match {
        math,
        data,
        tables,
        mon,
        start: start_move,
        opts,
        dt,
        knock_fade,
        world,
        card_roll,
        state: State { move_lvl: 1, ..State::default() },
        has_sd: mon.pool.contains(&data.swords_dance),
        has_hd: mon.pool.contains(&data.harden),
        status_ignored: move_has_status(start_move, opts.status),
        pl: Player { x: 0.0, y: 0.0, r: mon.r, hp: mon.hp, inv: 0.0, dirx: 1.0, diry: 0.0, react: 0.0, aim: 0.0 },
        enemies: Vec::with_capacity(72),
        shots: Vec::with_capacity(96),
        booms: Vec::new(),
        orbs: Vec::new(),
        e_shots: Vec::new(),
        hazards: Vec::new(),
        spawn_n: 0,
        acc: 0.0,
        surge,
        kills: 0,
        xp: 0.0,
        level: 1,
        need: 0.0,
        atk_cd: 0.0,
        t: 0.0,
        chip_t: 0.0,
        biome: 0,
        biome_t: 0.0,
        check_t: 60.0,
        weather: None,
        seq: 1,
        st: Derived {
            mv: &start_move.levels[0],
            max_hp: mon.hp,
            atk: mon.atk,
            spd: mon.spd,
            red: 0.0,
            cd_mul: 1.0,
            regen: 0.0,
            melee: 1.0,
        },
        stat_dirty: true,
        stat_snow: false,
        angles: Vec::with_capacity(8),
        sep: Sep::default(),
        shot_soa: ShotSoa::default(),
        near_buf: Vec::with_capacity(72),
        terrain: opts.terrain.then(|| {
            Box::new(Terr { world: World::new((opts.seed as i32).wrapping_mul(7919).wrapping_add(1)), path: Path::new() })
        }),
        lava_t: 0.0,
    };
    m.need = xp_for(math, 1);

    while m.t < max_time && m.pl.hp > 0.0 {
        let step = jmin(dt, max_time - m.t);
        m.t += step;
        m.tick_weather();
        m.stats();
        if m.st.regen != 0.0 {
            m.pl.hp = jmin(m.st.max_hp, m.pl.hp + m.st.regen * step);
        }
        if m.pl.inv > 0.0 {
            m.pl.inv -= step;
        }
        m.acc += spawn_rate(math, m.t) * step;
        let mut n = m.acc.floor();
        m.acc -= n;
        while n > 0.0 {
            n -= 1.0;
            m.roll_spawn(None);
        }
        m.surge -= step;
        if m.surge <= 0.0 {
            m.surge = 38.0 + m.world.next() * 18.0;
            let base = m.world.next() * PI * 2.0;
            let want = js_round((14.0 + (m.t / 22.0).floor()) * 0.4) as i64;
            for _ in 0..want {
                let a = base + (m.world.next() * 1.1 - 0.55);
                m.roll_spawn(Some(a));
            }
        }
        m.stats();
        if let Some(t) = &mut m.terrain {
            t.world.liquid = if m.biome == 2 { Liquid::Lava } else { Liquid::Water };
        }
        m.decide();
        let mut pspd = m.st.spd;
        if let Some(t) = &mut m.terrain {
            if t.world.is_liquid(m.pl.x, m.pl.y) {
                match t.world.liquid {
                    Liquid::Water => {
                        if !mon.types.contains(&T_WATER) {
                            pspd *= 0.6;
                        }
                    }
                    Liquid::Lava => {
                        if !mon.types.contains(&T_FIRE) {
                            m.lava_t -= step;
                            if m.lava_t <= 0.0 {
                                m.lava_t = 0.5;
                                m.pl.hp -= jmax(5.0, m.st.max_hp * 0.03);
                            }
                        }
                    }
                }
            }
        }
        m.pl.x += m.pl.dirx * pspd * step;
        m.pl.y += m.pl.diry * pspd * step;
        if let Some(t) = &mut m.terrain {
            t.world.collide(&mut m.pl.x, &mut m.pl.y, m.pl.r);
        }
        m.tick_buffs();
        m.stats();
        m.atk_cd -= step;
        if m.atk_cd <= 0.0 {
            m.cast();
            m.atk_cd = m.st.mv.cd * m.st.cd_mul;
        }
        m.step_shots();
        m.reap();
        m.stats();
        m.step_enemies();
        m.reap();
        if opts.trace && (m.t / 0.25).floor() != ((m.t - step) / 0.25).floor() {
            let f = Frame {
                t: m.t,
                x: m.pl.x,
                y: m.pl.y,
                hp: m.pl.hp,
                enemies: m.enemies.iter().filter(|e| e.hp > 0.0).map(|e| (e.x, e.y, e.r, e.fly)).collect(),
                ids: m.enemies.iter().filter(|e| e.hp > 0.0).map(|e| (e.id, e.dex)).collect(),
                shots: m.shots.iter().map(|s| (s.x, s.y, s.vx, s.vy)).collect(),
                e_shots: m.e_shots.iter().map(|s| (s.x, s.y, s.vx, s.vy, s.ty)).collect(),
            };
            TRACE.with(|t| t.borrow_mut().push(f));
        }
    }

    m.stats();
    let capped = m.pl.hp > 0.0;
    RunResult {
        time: if capped { max_time } else { m.t },
        kills: m.kills,
        level: m.level,
        capped,
        status_ignored: m.status_ignored,
        hp: m.pl.hp,
        max_hp: m.st.max_hp,
        hp_frac: if capped { m.pl.hp / m.st.max_hp } else { 0.0 },
    }
}