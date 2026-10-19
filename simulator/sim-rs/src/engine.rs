//! Port of sim/match.js + sim/rules.js. Statement order and floating-point
//! operation order follow the JS exactly; `Replay` math proves it.

use crate::data::*;
use crate::math::{Libm, MathFns};
use crate::rng::Rng;
use crate::terrain::{steer, tile_of, Block, Liquid, Path, World, PATH_EVERY};
use std::cell::RefCell;
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
    /// Orbit the nearest enemy at the move's keep distance. Not the parity bot.
    Kite,
    /// Kite, dodge telegraphs and collect orbs. Used for published ranks.
    /// The parity path stays on Repulse so `parity.js` does not move.
    Play,
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

/// player.js Player.MONO_K.
pub const MONO_K: f64 = 1.2;

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
    /// fixed main group (players' late-game setup): extra bonded attacks, buffs held from t=0, item
    pub ext: Ext,
}

#[derive(Clone, Default)]
pub struct Ext {
    /// extra bonded attacks cast alongside the primary (each with its own cooldown)
    pub companions: Vec<usize>,
    /// bitmask of buffs held in the group from t=0: 1 = atk buff (Swords/Dragon Dance), 2 = Harden (or Agility);
    /// 0 = old mode (SD/Harden only via cards)
    pub buffs: u8,
    /// use Dragon Dance instead of Swords Dance as the atk buff
    pub dd: bool,
    /// use Nasty Plot (Maquinación, satk) instead of Swords Dance. Set when the bonded attacks are special.
    pub np: bool,
    /// use Agility (speed) instead of Harden as the second buff
    pub agi: bool,
    /// held item (items.js): atk, spd, cd multipliers, flat reduction, regen frac/s, xp mult, life orb
    pub item: Item,
    /// card priority override for FILL stats (indices into Stat); empty = default
    pub fill: Vec<u8>,
    /// fire the kinds the parity engine leaves inert (cone, meteor, chain, aura, dash, mine, trail, turret; combat.js)
    pub xkinds: bool,
    /// bonds arrive with rift legendaries (rift.js), one group member per bond; false = whole group from t=0
    pub rift: bool,
    /// the five bosses of enemies.js BOSS_SLOTS (spawner.js), with waves at 25 % and no surges while one is alive
    pub bosses: bool,
    /// second slot for the swap bot (player.js setActive). None keeps the fixed group.
    pub alt: Option<usize>,
    /// crit chance from the permanent perk (upgrades.js crit, 0.03 per level). 0 in published ranks.
    pub crit: f64,
    /// offer Aprendizaje and Baya Zidra (levelup.js STATS). Off keeps the published card pool.
    pub full_cards: bool,
    /// fill priority applies only while that stat is below this count. 0 = no extra limit.
    pub stop: u32,
    /// take Baya Zidra only while hp/maxHp is at or below this. 0 = only when the fill list prefers it.
    /// Above 0, the berry is taken ahead of stat cards whenever the offer lands and HP is that low.
    pub heal_below: f64,
    /// Fraction of a combat hit ignored (contact and shots). 0 leaves `hurt` unchanged. Lava and weather
    /// chip are not dodged. A stand-in for a player who sidesteps, not a change to the parity bot.
    pub dodge: f64,
    /// (stat index, count): start the run with that many and do not take more. 7 = Aprendizaje.
    pub locks: Vec<(u8, u32)>,
}

#[derive(Clone, Copy)]
pub struct Item {
    pub atk: f64,
    pub spd: f64,
    pub cd: f64,
    pub red: f64,
    pub regen: f64,
    pub xp: f64,
    pub lifeorb: bool,
    /// choiceband: setActive returns without switching (player.js:141)
    pub lock: bool,
    /// focussash (player.js:248)
    pub sash: bool,
    /// shellbell (player.js:295)
    pub bell: bool,
    /// rockyhelmet (combat.js:668)
    pub helmet: bool,
}
impl Default for Item {
    fn default() -> Self {
        Item {
            atk: 1.0,
            spd: 1.0,
            cd: 1.0,
            red: 0.0,
            regen: 0.0,
            xp: 1.0,
            lifeorb: false,
            lock: false,
            sash: false,
            bell: false,
            helmet: false,
        }
    }
}
impl Item {
    pub fn by_id(id: &str) -> Item {
        let d = Item::default();
        match id {
            "none" => d,
            "choiceband" => Item { atk: 1.4, lock: true, ..d },
            "lifeorb" => Item { atk: 1.3, lifeorb: true, ..d },
            "quickclaw" => Item { cd: 0.8, ..d },
            "choicescarf" => Item { spd: 1.35, ..d },
            "assaultvest" => Item { red: 0.2, ..d },
            "leftovers" => Item { regen: 0.015, ..d },
            "luckyegg" => Item { xp: 1.3, ..d },
            "shellbell" => Item { bell: true, ..d },
            "rockyhelmet" => Item { helmet: true, ..d },
            "focussash" => Item { sash: true, ..d },
            _ => panic!("item {id} not modelled"),
        }
    }
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
    /// enemy.js:910, `e.boss && !e.judge`. Rift legends are bosses (rift.js spawnLegend passes boss=true).
    pub bosses: u32,
    /// game.js:301 with coinMul 1 (no Fortuna perk, upgrades.js:41).
    pub coins: f64,
    pub level: u32,
    pub capped: bool,
    pub status_ignored: bool,
    pub hp: f64,
    pub max_hp: f64,
    pub hp_frac: f64,
    /// HP and shield actually removed. Overkill is not counted. DoT is not included
    /// (combat.js adds the hit to `dmgDealt`, not the burn or poison ticks).
    pub dealt: f64,
}

/// End-of-run Pokémonedas. game.js:295-301.
/// `picked` is coins already on the player (boss shower 10×5, enemy.js:174; legend shower 10×8, enemy.js:191).
/// Golden, thieves, rescues and duplicate shinies are not in this sim, so they add nothing here.
pub fn run_coins(time: f64, kills: u32, bosses: u32, picked: f64) -> f64 {
    let tiempo = (time / 5.0).floor();
    let derrotados = (kills as f64 * 0.25).floor();
    let jefes = bosses as f64 * 80.0;
    js_round(tiempo + derrotados + jefes + picked)
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

mod kinds;

// ---------------------------------------------------------------- rules

fn reach_of(m: &MoveLvl) -> f64 {
    match m.kind {
        Kind::Melee => m.radius,
        Kind::Projectile | Kind::Nova => m.speed * m.life,
        Kind::Beam | Kind::Orbit | Kind::Boomerang => m.radius,
        // combat.js reach() of the 5a23d49 kinds. The other Inert kinds keep the old flat 180.
        Kind::Inert => match m.xk {
            9 | 10 => m.speed * m.life,
            11 | 12 | 15 => m.radius + 20.0,
            13 => or(m.count, 1.0).floor().max(1.0) * kinds::QSTEP + m.radius,
            14 | 16 => 300.0,
            _ => 180.0,
        },
    }
}

fn keep_distance(m: &MoveLvl) -> f64 {
    if m.kind == Kind::Melee || (m.kind == Kind::Inert && matches!(m.xk, 12 | 15)) {
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
    Up2(u8),
    Evo2(u8),
    Stat(Stat),
    /// Aprendizaje, levelup.js:24. Only offered with `Ext::full_cards`.
    Xp,
    /// Baya Zidra, levelup.js:26. Only offered with `Ext::full_cards`.
    Heal,
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
    /// 1 + stacks * amount for the physical and special buffs. 1 when that buff is down.
    patk: f64,
    satk: f64,
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
    sand_safe: bool,
    snow_safe: bool,
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
    boss: bool,
    /// rift legendary (rift.js spawnLegend). Also constructed with boss=true in the game.
    legend: bool,
    /// Spawned while the cap was already in the elite band (spawner.js:108). Faithful XP uses it.
    elite: bool,
    /// Seconds unseen and behind the player (enemy.js lagT, LAG_T 2.5).
    lag_t: f64,
    /// judgment.js legend. Gives XP and nothing else (no coins, no rift bond).
    judge: bool,
    /// Damage taken this second, for Sentencia's single-target DPS sample. Not read by combat.
    dps_acc: f64,
    /// stats.js guard of this enemy's Defense and Sp. Def. 1 when a path forgot to stamp them.
    g_phys: f64,
    g_spec: f64,
    /// 1 physical, 2 special. The side this enemy hits with (stats.js sideOf).
    cat: u8,
    /// Recent damage taken, bosses only (enemy.js RD_TAU = 6).
    rd: f64,
    /// Seconds of stun left (enemy.js applyStun / stunT). Frozen enemies skip movement, attacks and contact.
    stun_t: f64,
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
    knock: f64,
    /// Move category stamped at cast: 0 none, 1 physical, 2 special.
    cat: u8,
    /// Rebounds left (combat.js rebound). 0 on every pre-5a23d49 move.
    bounce: u32,
    /// HP the player gets back per hit (Beso Drenaje, combat.js resolve p.drain).
    drain: f64,
    /// Seconds since the cast (projectile.js p.t). Only the rebound reads it.
    age: f64,
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
    knock: f64,
    cat: u8,
}

struct Orb {
    angle: f64,
    inside: Vec<u32>,
    /// enemy id, last hit time (combat.js orbit rehit). Unused on the parity path.
    log: Vec<(u32, f64)>,
}

/// pickup.js orb. kind: 0 xp, 1 heal, 2 magnet, 3 bomb.
struct Pickup {
    kind: u8,
    x: f64,
    y: f64,
    vx: f64,
    vy: f64,
    value: f64,
    pulled: bool,
}

/// camera.js sees(), for the 768×432 view the spawn ring is built from.
fn sees_view(px: f64, py: f64, x: f64, y: f64, pad: f64) -> bool {
    (x - px).abs() < 384.0 + pad && (y - py).abs() < 216.0 + pad
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
    cat: u8,
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
    cat: u8,
    /// judgment.js hazards ignore guard, reduction and the melee cut (player.js hurt pure).
    pure: bool,
    /// Fraction of max HP. NaN when the hazard is a flat amount.
    pct: f64,
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

/// combat.js chain: `m.hex && (cur.burn > 0 || cur.poison > 0 || cur.slow > 0) ? m.hex : 1`.
/// `slow` is the speed factor (enemy.js applySlow), not the timer.
pub fn hex_multiplier(hex: f64, burn: f64, poison: f64, slow: f64) -> f64 {
    if hex.is_finite() && hex != 0.0 && (burn > 0.0 || poison > 0.0 || slow > 0.0) {
        hex
    } else {
        1.0
    }
}

/// stats.js:21. `def || 75`, then clamp((75 / max(5, def))^0.35, 0.78, 1.25).
pub fn defense_guard(def: f64) -> f64 {
    guard(&Libm, def)
}

fn guard<M: MathFns>(math: &M, def: f64) -> f64 {
    let base = if def.is_nan() || def == 0.0 { 75.0 } else { def };
    let d = base.max(5.0);
    math.pow(75.0 / d, 0.35).clamp(0.78, 1.25)
}

fn taken_of(e: &Enemy, cat: u8) -> f64 {
    match cat {
        1 => e.g_phys,
        2 => e.g_spec,
        _ => 1.0,
    }
}

/// levelup.js pickWeighted. `rest` is (item, weight) and shrinks as items are drawn.
fn pick_weighted(rng: &mut Rng, rest: &mut Vec<(usize, f64)>, n: usize) -> Vec<usize> {
    let mut out = Vec::new();
    while out.len() < n && !rest.is_empty() {
        let total: f64 = rest.iter().map(|(_, w)| *w).sum();
        let mut r = rng.next() * total;
        let mut i = 0;
        while i + 1 < rest.len() && {
            r -= rest[i].1;
            r > 0.0
        } {
            i += 1;
        }
        out.push(rest.remove(i).0);
    }
    out
}

/// judgment.js:46-48. While Sentencia is active, speed above 130 counts only 25%.
pub fn cap_spd(s: f64) -> f64 {
    if s <= 130.0 { s } else { 130.0 + (s - 130.0) * 0.25 }
}

/// judgment.js touchPct. The touch starts at 40% of max HP and reaches 100% at arena second 600 (minute 40).
pub fn judgment_touch_pct(arena_t: f64) -> f64 {
    (0.4 + (arena_t - 420.0).max(0.0) / 180.0 * 0.6).min(1.0)
}

/// judgment.js Arceus chase factor. After 300 s in the arena he speeds up without a cap.
pub fn judgment_chase_k(arena_t: f64) -> f64 {
    1.22_f64.min(0.74 + arena_t * 0.013) + (arena_t - 300.0).max(0.0) * 0.0015
}

/// Applies one hit and what it inflicts (`st`, all zero unless `Opts::status`).
fn strike(e: &mut Enemy, dmg: f64, atk: f64, ty: u8, tm: &[Vec<f64>], w: &Option<Weather>, st: Status, cat: u8) {
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
    // combat.js hit: typeK * Stats.taken(enemy, move cat).
    let amount = dmg * atk * mult * weather_factor(w, ty) * taken_of(e, cat);
    let mut left = amount;
    if e.shield > 0.0 {
        let used = jmin(e.shield, left);
        e.shield -= used;
        left -= used;
    }
    e.hp -= left;
}

/// Damage over time, as Enemy.hurt() in the game: rounded, at least 1, and the shield takes it first.
/// Returns the rounded tick (shield included) so a caller can record it. Combat is unchanged.
fn hurt_dot(e: &mut Enemy, amount: f64) -> f64 {
    if e.hp <= 0.0 {
        return 0.0;
    }
    let d = jmax(1.0, js_round(amount));
    // enemy.js hurt: bosses add the rounded hit before the shield takes it.
    if e.boss {
        e.rd += d;
    }
    let mut left = d;
    if e.shield > 0.0 {
        let used = jmin(e.shield, d);
        e.shield -= used;
        left = d - used;
        if left <= 0.0 {
            return d;
        }
    }
    e.hp -= left;
    d
}

/// Enemy.hurt (enemy.js:100) once the ranking path is on: round, min 1, shield first, knock only if the
/// shield did not absorb the whole hit and the enemy is not a boss. Returns the pre-round amount for Shell Bell.
fn raw_hurt(e: &mut Enemy, amount: f64, knock: f64, dx: f64, dy: f64) {
    let d = jmax(1.0, js_round(amount));
    if e.boss {
        e.rd += d;
    }
    let lost = if e.shield > 0.0 {
        let a = jmin(e.shield, d);
        e.shield -= a;
        if a >= d {
            return;
        }
        let lost = jmax(1.0, js_round(d - a));
        e.hp -= lost;
        lost
    } else {
        e.hp -= d;
        d
    };
    // judgment.js noteDmg: the HP actually lost, after the shield. Unused until minute 29.
    e.dps_acc += lost;
    if knock > 0.0 && !e.boss {
        let n = len(dx, dy);
        if n > 1e-6 {
            e.kx += dx / n * knock;
            e.ky += dy / n * knock;
        }
    }
}

/// Direct hit. The parity path calls `strike` and returns 0. The ranking path (status or extra kinds) rounds,
/// knocks and may crit (combat.js hit / projectile, upgrades.js crit). Crit uses its own rng so the fx stream stays put.
fn hit_one(
    faithful: bool,
    e: &mut Enemy,
    dmg: f64,
    atk: f64,
    ty: u8,
    tm: &[Vec<f64>],
    w: &Option<Weather>,
    st: Status,
    knock: f64,
    dx: f64,
    dy: f64,
    crit_chance: f64,
    crit_rng: &mut Rng,
    cat: u8,
) -> f64 {
    if !faithful {
        strike(e, dmg, atk, ty, tm, w, st, cat);
        return 0.0;
    }
    if e.hp <= 0.0 {
        return 0.0;
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
    let mut amount = dmg * atk * type_mult(tm, ty, e.combo) * weather_factor(w, ty) * taken_of(e, cat);
    if crit_chance > 0.0 && crit_rng.next() < crit_chance {
        amount *= 1.5;
    }
    let before_hp = e.hp;
    let before_sh = e.shield;
    raw_hurt(e, amount, knock, dx, dy);
    // Credit HP and shield actually removed. Overkill on a 1-HP swarm enemy is not damage.
    let hp_lost = (before_hp - e.hp.max(0.0)).max(0.0);
    let sh_lost = (before_sh - e.shield.max(0.0)).max(0.0);
    hp_lost + sh_lost
}

fn note_bell(bell: &mut f64, on: bool, dealt: f64) {
    if dealt > 0.0 && on {
        *bell = jmin(4.0, *bell + dealt * 0.04);
    }
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
            let heal = e.max * heal_fraction(math, atk, base_atk);
            // enemy.js healAround: a boss heals at most BOSS_HEAL_S * (rd / RD_TAU).
            let add = if e.boss { heal.min(e.rd / 6.0 * 0.4) } else { heal };
            e.hp = jmin(e.max, e.hp + add);
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
        // enemy.js castShields: the nearest 6, and a skipped boss still occupies a slot.
        // Only a boss with shield_t > 2 is skipped. A normal enemy refreshes 35%.
        given += 1;
        let e = &mut enemies[i];
        if e.boss && e.shield_t > 2.0 {
            continue;
        }
        let s = if e.boss { (e.max * 0.35).min(e.rd / 6.0 * 1.2) } else { 0.35 * e.max };
        e.shield = e.shield.max(s);
        e.shield_t = 8.0;
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

/// A ground or air effect of the extra kinds (combat.js `fields`): 2 meteor, 6 mine, 7 patch (trail), 8 turret,
/// and the 5a23d49 fields 11 charge, 12 spin, 13 quake, 14 vortex, 16 stun zone (see `kinds`).
struct Field<'a> {
    k: u8,
    x: f64,
    y: f64,
    t: f64,
    life: f64,
    r: f64,
    atk: f64,
    tick: f64,
    mv: &'a MoveLvl,
    /// Spare slots for the 5a23d49 fields: hits or waves left, wave counter, aim cos and sin.
    n: u32,
    i: u32,
    ca: f64,
    sa: f64,
}

const BOSS_SLOTS: [(f64, f64, f64, f64); 5] =
    [(180.0, 1400.0, 34.0, 220.0), (360.0, 3200.0, 42.0, 420.0), (540.0, 5600.0, 48.0, 680.0), (720.0, 9000.0, 56.0, 1000.0), (900.0, 16000.0, 68.0, 1800.0)];
/// enemies.js BOSS_SLOTS bst bands, inclusive. Fallback when a band is empty: bst >= 580 (rollRun).
const BOSS_BST: [(f64, f64); 5] = [(490.0, 545.0), (520.0, 580.0), (540.0, 600.0), (580.0, 700.0), (600.0, 700.0)];
/// enemies.js personality sets. Only the branches that return before 'ranged' matter for bosses.
const HEAL_DEX: [u32; 14] = [35, 36, 113, 173, 183, 184, 242, 301, 440, 531, 594, 700, 764, 858];
const SHIELD_DEX: [u32; 14] = [95, 122, 208, 213, 227, 306, 375, 410, 411, 436, 437, 439, 476, 703];
const BOMB_DEX: [u32; 12] = [74, 75, 76, 100, 101, 102, 109, 110, 337, 338, 343, 344];
const SUMMON_DEX: [u32; 32] = [
    15, 18, 24, 28, 31, 34, 42, 51, 53, 57, 59, 62, 68, 73, 78, 82, 85, 91, 117, 130, 168, 169, 199, 230, 262, 334, 405, 416, 462, 466, 553, 637,
];
/// judgment.js AT = 30*60; rifts stop 120 s earlier (rift.js update).
const RIFT_UNTIL: f64 = 1680.0;
/// Arena player-to-legend gap: (3 + 3.5) tiles * 32 px (rift.js begin / spawnLegend, tiles.js T=16, sprites PX=2).
const LEGEND_GAP: f64 = 208.0;
/// enemy.js bossScale is 1–2 from the idle sprite height (default anchor → 2). The sim has no frame heights, so bosses
/// and rift legendaries use ×2 on the species radius (sprites.js bodyRadius). Estimate; huge sprites would be closer to ×1.

#[derive(Clone, Copy)]
struct BossPick {
    ix: usize,
    beh: Beh,
    hp: f64,
    spd: f64,
    dmg: f64,
    xp: f64,
    shot: f64,
}

fn dex_in(dex: u32, set: &[u32]) -> bool {
    set.binary_search(&dex).is_ok()
}

fn has_ty(mon: &Mon, types: &[u8]) -> bool {
    mon.types.iter().any(|t| types.contains(t))
}

/// enemies.js behaviorOf, only the question bosses ask: did it return 'ranged'?
fn boss_is_ranged(mon: &Mon) -> bool {
    let h = crate::terrain::js_hash(mon.dex as i32, 7, 11);
    if dex_in(mon.dex, &HEAL_DEX) || dex_in(mon.dex, &SHIELD_DEX) || dex_in(mon.dex, &BOMB_DEX) || dex_in(mon.dex, &SUMMON_DEX) {
        return false;
    }
    if has_ty(mon, &[T_BUG]) && (0.6..0.78).contains(&h) {
        return false;
    }
    if has_ty(mon, &[T_ELECTRIC, T_PSYCHIC, T_DRAGON, T_ICE]) && h < 0.18 {
        return false;
    }
    if has_ty(mon, &[T_FIRE, T_GROUND, T_POISON]) && h < 0.18 {
        return false;
    }
    if has_ty(mon, &[T_WATER, T_GRASS, T_BUG, T_FAIRY]) && (0.18..0.32).contains(&h) {
        return false;
    }
    if has_ty(mon, &[T_FIGHTING, T_GROUND, T_NORMAL, T_ROCK]) && (0.42..0.56).contains(&h) {
        return false;
    }
    if has_ty(mon, &[T_PSYCHIC, T_ELECTRIC, T_GHOST, T_FAIRY]) && h < 0.4 {
        return true;
    }
    has_ty(mon, &[T_FIRE, T_WATER, T_POISON, T_ICE]) && h < 0.22
}

fn base_spd(mon: &Mon) -> f64 {
    (mon.spd - 78.0) / 0.42
}

#[allow(clippy::too_many_arguments)]
fn special_enemy(
    id: u32, dex: u16, x: f64, y: f64, r: f64, combo: u16, ty0: u8, xp: f64, beh: Beh, spd: f64, dmg: f64, hp: f64, shot_cd: f64, shot: f64, ai: Rng, def: Def, fly: bool, water: bool, fire: bool, boss: bool, legend: bool,
) -> Enemy {
    Enemy {
        id,
        dex,
        x,
        y,
        r,
        combo,
        ty0,
        xp,
        beh,
        spd,
        dmg,
        hp,
        max: hp,
        touch: 0.0,
        kx: 0.0,
        ky: 0.0,
        phase: Phase::Walk,
        pt: 0.0,
        shot_cd,
        skill: 0.0,
        heal_cd: 0.0,
        shield_cd: 0.0,
        jump: None,
        fuse: -1.0,
        shield: 0.0,
        shield_t: 0.0,
        shot,
        cx: 1.0,
        cy: 0.0,
        ai,
        def,
        fly,
        water,
        fire,
        sand_safe: false,
        snow_safe: false,
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
        boss,
        legend,
        elite: false,
        lag_t: 0.0,
        judge: false,
        dps_acc: 0.0,
        g_phys: 1.0,
        g_spec: 1.0,
        cat: 1,
        rd: 0.0,
        stun_t: 0.0,
    }
}

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
    atk_buff: usize,
    def_buff: usize,
    comps: Vec<(usize, usize, f64)>,
    any_melee: bool,
    fields: Vec<Field<'a>>,
    fx: Rng,
    /// group members bonded so far (index into bond_order) and their order: comps by index, 100 atk buff, 101 2nd buff
    bonds: usize,
    bond_order: Vec<u8>,
    rift_check: f64,
    rift_misses: f64,
    /// seconds left on an open rift; -1 when none (rift.js TTL 45)
    rift_ttl: f64,
    /// seconds of walking left before the bot enters; -1 if the rift is out of reach
    rift_walk: f64,
    /// 0 map, 1 fight, 2 won (endT 5), 3 lost (endT 1.2)
    arena_phase: u8,
    arena_t: f64,
    arena_end: f64,
    arena_down: f64,
    arena_back: (f64, f64),
    arena_dex: u32,
    stash: Vec<Enemy>,
    beaten: Vec<u32>,
    boss_picks: Vec<BossPick>,
    boss_idx: usize,
    patch_at: (f64, f64, f64),
    status_ignored: bool,
    pl: Player,
    enemies: Vec<Enemy>,
    shots: Vec<Shot>,
    booms: Vec<Boom>,
        orbs: Vec<Orb>,
        /// Learned attacks that were not in the planned group. (move index, cooldown).
        extras: Vec<(usize, f64)>,
        /// One orbit that is not the lead move: (move index, level index).
        side_orbit: Option<(usize, usize)>,
        side_orbs: Vec<Orb>,
        e_shots: Vec<EShot>,
    hazards: Vec<Hazard>,
    spawn_n: u32,
    acc: f64,
    surge: f64,
    kills: u32,
    /// bosses died this run (enemy.js:910). Includes rift legends, which spawn as bosses.
    bosses: u32,
    /// coins picked up. Boss shower and legend shower only.
    picked: f64,
    /// Post-type, post-guard, post-crit damage before the shield. Burn and poison are not included.
    dealt: f64,
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
    stat_snow: f64,
    angles: Vec<f64>,
    sep: Sep,
    shot_soa: ShotSoa,
    near_buf: Vec<(f64, usize)>,
    terrain: Option<Box<Terr>>,
    lava_t: f64,
    /// 0 fixed group, 1 the swap slot (player.js setActive). Stays 0 unless `Ext::alt` is set.
    slot: u8,
    alt_cd: f64,
    comp_evo: Vec<bool>,
    regen_n: f64,
    regen_amt: f64,
    regen_t: f64,
    /// altar power 0 Furia, 1 Rayo, 2 Imán, 3 Prisa (interact.js POWERS). 255 = none.
    power: u8,
    power_t: f64,
    altar_used: Vec<(i32, i32)>,
    bell: f64,
    /// player.js sashT starts at -999 ms, so the first lethal hit can proc
    sash_t: f64,
    crit_rng: RefCell<Rng>,
    /// enemies.js rollRun: seven species per tier, once per run. Empty on the parity path.
    roster: Vec<Vec<usize>>,
    /// Index into the tier's candidate list of the fastest plain, turned into the runner.
    runner_ix: Vec<Option<usize>>,
    pickups: Vec<Pickup>,
    /// Smoothed player velocity for the straggler test (enemy.js _vx/_vy).
    pvx: f64,
    pvy: f64,
    ppx: f64,
    ppy: f64,
    p_seen: bool,
    /// Aprendizaje stacks (levelup.js:25, max 8). Separate from `state.cards` so parity stays 7-wide.
    xp_n: u32,
    /// Baya Zidra taken this run (no max in levelup.js).
    heal_n: u32,
    /// Player's Defense and Sp. Def guards (stats.js), computed once at match start.
    g_phys: f64,
    g_spec: f64,
    /// bond_order members the level-up cards have already offered (levelup.js). Starter is not here.
    learned: Vec<bool>,
    /// Sentencia is running (judgment.js). The published window ends at 900 s, before minute 30.
    judging: bool,
    jd_t: f64,
    jd_boss_t: f64,
    jd_n: u32,
    jd_base: f64,
    jd_cx: f64,
    jd_cy: f64,
    jd_q: Vec<usize>,
    arceus_x: f64,
    arceus_y: f64,
    arceus_r: f64,
    arceus_cd: f64,
    arceus_touch: f64,
    /// Seconds into the current cast. Negative while he is chasing.
    arceus_cast: f64,
    arceus_wind: f64,
    /// 0 rain, 1 cross, 2 nova. Also the previous cast, so rain and cross alternate.
    arceus_kind: u8,
    /// One-second peaks of damage to a single enemy, last 30 s before Sentencia (judgment.js sampleDps).
    dps_samples: Vec<f64>,
    dps_clock: f64,
}

fn xp_for<M: MathFns>(math: &M, level: u32) -> f64 {
    let l = level as f64;
    ((8.0 + l * 6.0 + math.pow(l, 1.75) * 1.6) * 4.0).floor()
}

fn spawn_rate<M: MathFns>(math: &M, t: f64) -> f64 {
    (1.6 + t * 0.028 + math.pow(t / 60.0, 1.6) * 0.5) * 0.24
}

/// spawner.js rate(t). Enemies per second.
pub fn spawn_per_second(t: f64) -> f64 {
    spawn_rate(&Libm, t)
}

/// An enemy with nothing set but its HP, shield, type combo and the defence guard of one side. The base of
/// `faithful_hit_dealt` and of the scripted arenas in `scenario`.
fn blank_enemy(hp: f64, shield: f64, combo: u16, cat: u8, taken: f64) -> Enemy {
    Enemy {
        id: 0,
        dex: 0,
        x: 0.0,
        y: 0.0,
        r: 12.0,
        combo,
        ty0: 0,
        xp: 0.0,
        beh: crate::data::Beh::Chase,
        spd: 0.0,
        dmg: 0.0,
        hp,
        max: hp.max(1.0),
        touch: 0.0,
        kx: 0.0,
        ky: 0.0,
        phase: Phase::Walk,
        pt: 0.0,
        shot_cd: 0.0,
        skill: 0.0,
        heal_cd: 0.0,
        shield_cd: 0.0,
        jump: None,
        fuse: 0.0,
        shield,
        shield_t: 0.0,
        shot: 0.0,
        cx: 0.0,
        cy: 0.0,
        ai: Rng::new(1),
        def: crate::data::Def {
            beh: crate::data::Beh::Chase,
            hp: 1.0,
            spd: 1.0,
            dmg: 1.0,
            xp: 1.0,
            shot_dmg: 0.0,
            shot_cd: 1.0,
            range: 0.0,
            zones: 0.0,
            fan_n: 0.0,
        },
        fly: false,
        water: false,
        fire: false,
        sand_safe: false,
        snow_safe: false,
        los: (0.0, false),
        side_t: 0.0,
        side: 0.0,
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
        boss: false,
        legend: false,
        elite: false,
        lag_t: 0.0,
        judge: false,
        dps_acc: 0.0,
        g_phys: if cat == 1 { taken } else { 1.0 },
        g_spec: if cat == 2 { taken } else { 1.0 },
        cat,
        rd: 0.0,
        stun_t: 0.0,
    }
}

/// One faithful hit: the HP and shield `hit_one` actually removes.
/// One faithful hit: the HP and shield `hit_one` actually removes.
/// `taken` is stats.js `guard` for the defending side. Weather is clear. No crit.
pub fn faithful_hit_dealt(
    hp: f64,
    shield: f64,
    dmg: f64,
    atk: f64,
    ty: u8,
    combo: u16,
    tm: &[Vec<f64>],
    taken: f64,
    cat: u8,
) -> f64 {
    let mut e = blank_enemy(hp, shield, combo, cat, taken);
    hit_one(true, &mut e, dmg, atk, ty, tm, &None, Status { slow: 0.0, burn: 0.0, poison: 0.0 }, 0.0, 0.0, 0.0, 0.0, &mut Rng::new(1), cat)
}

/// Whether a move level carries a status the sim does not apply (the status_ignored flag). With
/// `Opts::status` every status is applied. Extra kinds count as applied when `xkinds` fires them.
fn unmodelled(l: &MoveLvl, status_on: bool, xkinds: bool) -> bool {
    l.status && (!status_on || !(l.kind.simulated() || (xkinds && l.xk != 0)))
}

fn move_has_status(m: &Move, status_on: bool, xkinds: bool) -> bool {
    m.levels.iter().any(|l| unmodelled(l, status_on, xkinds)) || m.evo.as_ref().is_some_and(|e| unmodelled(e, status_on, xkinds))
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

    /// Ranking path: status or extra kinds. Parity runs have both off, so the new combat math stays off.
    fn faith(&self) -> bool {
        self.opts.status || self.opts.ext.xkinds
    }

    /// weather.js speedFor. Parity keeps the flat ×0.9 whenever the ramp is above 0 (match.js).
    fn snow_mul(&self) -> f64 {
        let Some(w) = self.weather else { return 1.0 };
        if w.kind != Wx::Snow {
            return 1.0;
        }
        let ramp = weather_ramp(w.elapsed, w.dur);
        if self.faith() {
            if ramp > 0.0 { 1.0 - 0.1 * ramp } else { 1.0 }
        } else if ramp > 0.0 {
            0.9
        } else {
            1.0
        }
    }

    /// stats() in match.js: recompute only when dirty or the snow factor changed.
    fn stats(&mut self) {
        let snow = self.snow_mul();
        if !self.stat_dirty && snow == self.stat_snow {
            return;
        }
        self.stat_dirty = false;
        self.stat_snow = snow;
        let mv = self.current_move();
        let s = &self.state;
        let mut atk_buff = 0.0;
        let mut def_buff = 0.0;
        let mut patk = 1.0;
        let mut satk = 1.0;
        if s.sd > 0 && s.sd_t > 0.0 {
            let lvl = self.buff_level(self.atk_buff, s.sd);
            let bonus = s.sd_stacks * lvl.amount;
            // moves.js: Swords Dance and Dragon Dance are patk; Nasty Plot is satk.
            match lvl.buff {
                5 => patk = 1.0 + bonus,
                6 => satk = 1.0 + bonus,
                _ => atk_buff = bonus,
            }
        }
        if s.hd > 0 && s.hd_t > 0.0 {
            def_buff = s.hd_stacks * self.buff_level(self.def_buff, s.hd).amount;
        }
        let mut spd_buff = 1.0;
        if self.opts.ext.agi {
            spd_buff = 1.0 + def_buff;
            def_buff = 0.0;
        }
        let it = self.opts.ext.item;
        let faithful = self.faith();
        let judging = self.opts.ext.rift && self.t >= 1800.0;
        let mut spd = self.mon.spd * self.tables.spd[s.cards[Stat::Run as usize] as usize];
        if snow < 1.0 && !self.mon.types.contains(&T_ICE) {
            spd *= snow;
        }
        // player.js:254. The cut applies whenever a melee move is in the active group.
        // The starter always is. A companion counts once that bond has landed, not from t=0.
        let melee_cut = mv.kind == Kind::Melee || self.active_has_melee();
        let st = &mut self.st;
        st.max_hp = self.mon.hp + 20.0 * s.cards[Stat::Hp as usize] as f64;
        st.atk = self.mon.atk * self.tables.atk[s.cards[Stat::Pow as usize] as usize] * (1.0 + atk_buff) * it.atk;
        st.patk = patk;
        st.satk = satk;
        st.spd = spd * it.spd * spd_buff;
        // levelup.js:19 clamps each Coraza with Math.min(0.7, dmgReduce + 0.06). The vest is already
        // inside dmgReduce when it was equipped first (items.js:35). player.js:96 then caps at 0.8
        // after Harden. Parity has no item, so both branches agree until 12 cards.
        let cor = 0.06 * s.cards[Stat::Cor as usize] as f64;
        let (stacked, extra) = if faithful {
            (jmin(0.7, it.red + cor), 0.0)
        } else {
            (jmin(0.7, cor), it.red)
        };
        st.red = jmin(0.8, stacked + extra + def_buff);
        st.cd_mul = self.tables.cd[s.cards[Stat::Cd as usize] as usize] * it.cd;
        // items.js:14 snapshots leftovers at equip time. The sim equips at t=0, so that is base HP.
        // Parity never holds an item, so the scaling branch stays 0.
        let left = if faithful { it.regen * self.mon.hp } else { it.regen * st.max_hp };
        st.regen = 0.9 * s.cards[Stat::Rgn as usize] as f64 + left;
        if self.regen_n > 0.0 && self.regen_t > 0.0 {
            st.regen += self.regen_n * self.regen_amt;
        }
        st.melee = if melee_cut { 0.75 } else { 1.0 };
        st.mv = mv;
        // interact.js POWERS, 25 s. Imán only changes the magnet radius (magnet_r).
        if self.power_t > 0.0 {
            match self.power {
                0 => st.atk *= 2.0,
                1 => st.spd *= 1.45,
                3 => st.cd_mul *= 0.6,
                _ => {}
            }
        }
        if self.slot == 1 {
            if let Some(id) = self.opts.ext.alt {
                let alt = &self.data.moves[id].levels[0];
                st.melee = if alt.kind == Kind::Melee { 0.75 } else { 1.0 };
                st.mv = alt;
            }
        }
        // player.js spd getter: Judgment.capSpd only while Sentencia is active (judgment.js:46-48).
        if judging {
            st.spd = cap_spd(st.spd);
        }
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

    /// player.js atkFor. Fit and the side buff stay off `st.atk` so each companion uses its own cat.
    /// A single-type Pokémon hits 20 % harder with moves of its own type (player.js monoType, MONO_K).
    fn atk_for(&self, cat: u8, ty: u8) -> f64 {
        let fit = if cat == 0 || self.mon.pa.is_nan() {
            1.0
        } else if cat == 2 {
            self.mon.sa / self.mon.atk
        } else {
            self.mon.pa / self.mon.atk
        };
        let side = match cat {
            1 => self.st.patk,
            2 => self.st.satk,
            _ => 1.0,
        };
        let mono = if self.mon.types.len() == 1 && self.mon.types[0] == ty { MONO_K } else { 1.0 };
        self.st.atk * fit * side * mono
    }

    fn hurt(&mut self, amount: f64, atk_ty: u8, cat: u8) {
        if self.pl.inv > 0.0 || self.pl.hp <= 0.0 {
            return;
        }
        // player.js:245. taken(player, enemy cat) before the type chart. No cat → ×1.
        let g = match cat {
            1 => self.g_phys,
            2 => self.g_spec,
            _ => 1.0,
        };
        let mult = type_mult(&self.data.tmult, atk_ty, self.mon.combo);
        let dmg = amount * g * mult * self.wx(atk_ty) * (1.0 - self.st.red) * self.st.melee;
        // dodge 0 skips the multiply so the parity path stays bit-exact.
        let dmg = if self.opts.ext.dodge > 0.0 { dmg * (1.0 - self.opts.ext.dodge) } else { dmg };
        // player.js:255. At least 1. Parity hurt stays unclamped so the trace matches match.js.
        let dmg = if self.faith() { dmg.max(1.0) } else { dmg };
        self.pl.hp -= dmg;
        self.pl.inv = INV;
        self.sash();
    }

    /// player.js hurt with pure=true. No guard, no type chart, no reduction, no melee cut. At least 1.
    fn hurt_pure(&mut self, amount: f64) {
        if self.pl.hp <= 0.0 {
            return;
        }
        self.pl.hp -= amount.max(1.0);
        self.pl.inv = INV;
        self.sash();
    }

    /// player.js:248. Off unless the item is Focus Sash, so the parity hurt() is unchanged.
    fn sash(&mut self) {
        if self.opts.ext.item.sash && self.pl.hp <= 0.0 && self.t - self.sash_t > 60.0 {
            self.sash_t = self.t;
            self.pl.hp = 1.0;
            self.pl.inv = 1.2;
        }
    }

    /// combat.js:668. Contact only. 15+4*level, no type, no crit, no bell, knock 80. The 150 push stays separate.
    fn helmet_on(&mut self, i: usize) {
        if !self.opts.ext.item.helmet {
            return;
        }
        let (px, py) = (self.pl.x, self.pl.y);
        let dmg = 15.0 + 4.0 * self.level as f64;
        let e = &mut self.enemies[i];
        let (dx, dy) = (e.x - px, e.y - py);
        raw_hurt(e, dmg, 80.0, dx, dy);
    }

    /// Swap when the active timer is still above 35% of base cd (player.js:148). cdMul at or below
    /// 0.35 already waits less than the clamp, so swapping does not help. Choice Band never reaches this.
    fn maybe_swap(&mut self) {
        if self.opts.ext.alt.is_none() || self.opts.ext.item.lock || self.st.cd_mul <= 0.35 {
            return;
        }
        let (timer, base) = if self.slot == 0 {
            (self.atk_cd, self.current_move().cd)
        } else {
            let id = self.opts.ext.alt.unwrap();
            (self.alt_cd, self.data.moves[id].levels[0].cd)
        };
        if timer > base * 0.35 {
            self.enter_slot(1 - self.slot);
        }
    }

    fn enter_slot(&mut self, slot: u8) {
        self.slot = slot;
        self.orbs.clear();
        self.stat_dirty = true;
        if slot == 0 {
            let base = self.current_move().cd;
            self.atk_cd = jmin(self.atk_cd, base * 0.35);
            for i in 0..self.comps.len() {
                let cd = self.comp_lvl(i).cd;
                self.comps[i].2 = jmin(self.comps[i].2, cd * 0.35);
            }
        } else if let Some(id) = self.opts.ext.alt {
            let cd = self.data.moves[id].levels[0].cd;
            self.alt_cd = jmin(self.alt_cd, cd * 0.35);
        }
    }

    /// player.js:352. Clears invulnerability, then hurt() (defense, melee DR, min 1) and 0.45 s of invuln.
    fn player_lava(&mut self) {
        if self.faith() {
            self.pl.inv = 0.0;
            let raw = jmax(5.0, self.st.max_hp * 0.03);
            let d = jmax(1.0, raw * (1.0 - self.st.red) * self.st.melee);
            self.pl.hp -= d;
            self.pl.inv = 0.45;
            self.sash();
        } else {
            self.pl.hp -= jmax(5.0, self.st.max_hp * 0.03);
        }
    }

    /// Altars (interact.js POWERS, world.js:154). Contact within max(30, r+body+14), one use, 25 s.
    /// The bot does not path to them. Imán has no combat effect. Approximation.
    fn tick_altars(&mut self) {
        if !self.faith() || self.arena_phase != 0 || self.terrain.is_none() {
            return;
        }
        let (px, py, pr) = (self.pl.x, self.pl.y, self.pl.r);
        let (tx, ty) = (tile_of(px), tile_of(py));
        let used = self.altar_used.clone();
        let mut found: Option<(i32, i32, u8)> = None;
        if let Some(t) = &mut self.terrain {
            'scan: for dy in -3..=3 {
                for dx in -3..=3 {
                    let x = tx + dx;
                    let y = ty + dy;
                    if used.contains(&(x, y)) {
                        continue;
                    }
                    if let Some((ax, ay, r, kind)) = t.world.altar_at(x, y) {
                        if len(px - ax, py - ay) <= jmax(30.0, r + pr + 14.0) {
                            found = Some((x, y, kind));
                            break 'scan;
                        }
                    }
                }
            }
        }
        if let Some((x, y, kind)) = found {
            self.altar_used.push((x, y));
            self.power = kind;
            self.power_t = 25.0;
            self.stat_dirty = true;
        }
    }

    // ------------------------------------------------ cards

    /// levelup.js `max`. Vigor and Síntesis have none; the ranking path stops at 250, which a 900 s
    /// run cannot reach. Parity keeps the old caps (hp 99, rgn 10).
    fn stat_cap(&self, st: Stat) -> u32 {
        if let Some(&(_, n)) = self.opts.ext.locks.iter().find(|(k, _)| *k == st as u8) {
            return n;
        }
        if self.faith() && (st == Stat::Hp || st == Stat::Rgn) {
            return 250;
        }
        CAPS[st as usize]
    }

    fn xp_cap(&self) -> u32 {
        self.opts.ext.locks.iter().find(|(k, _)| *k == 7).map(|(_, n)| *n).unwrap_or(8)
    }

    fn card_count(&self, k: u8) -> u32 {
        match k {
            7 => self.xp_n,
            8 => self.heal_n,
            _ => self.state.cards[k as usize],
        }
    }

    fn fill_card(k: u8) -> Card {
        match k {
            7 => Card::Xp,
            8 => Card::Heal,
            _ => Card::Stat(STATS[k as usize]),
        }
    }

    /// Start with locked stacks already applied (Vigor also fills the new HP, as addMaxHp does at full life).
    fn apply_locks(&mut self) {
        let locks = self.opts.ext.locks.clone();
        for (k, n) in locks {
            match k {
                7 => self.xp_n = n,
                8 => self.heal_n = n,
                k if (k as usize) < STATS.len() => self.state.cards[k as usize] = n,
                _ => {}
            }
        }
        self.stat_dirty = true;
        self.stats();
        self.pl.hp = self.st.max_hp;
    }

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
        for (i, c) in self.comps.iter().enumerate() {
            if !self.bonded(i as u8) || self.comp_evo[i] {
                continue;
            }
            let m = &self.data.moves[c.0];
            if c.1 < m.max_lvl {
                out.push(Card::Up2(i as u8));
            } else if m.evo.is_some() {
                // moves.js evolve: at max level, after the needs card was taken once
                match m.needs {
                    Some(n) if self.state.cards[n as usize] < 1 => {}
                    _ => out.push(Card::Evo2(i as u8)),
                }
            }
        }
        // With rift bonds the bot only levels group members it has already bonded (an unbonded buff never fires).
        if self.has_sd && s.sd < 5 && (self.opts.ext.buffs == 0 || self.bonded(100)) {
            out.push(Card::Sd);
        }
        if self.has_hd && s.hd < 5 && (self.opts.ext.buffs == 0 || self.bonded(101)) {
            out.push(Card::Hd);
        }
        for st in STATS {
            if out.contains(&Card::Stat(st)) {
                continue;
            }
            if s.cards[st as usize] < self.stat_cap(st) {
                out.push(Card::Stat(st));
            }
        }
        // levelup.js:24-27. Imán is already in STATS; it does nothing here because XP is granted on kill.
        if self.opts.ext.full_cards && self.faith() {
            if self.xp_n < self.xp_cap() {
                out.push(Card::Xp);
            }
            out.push(Card::Heal);
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
        for i in 0..self.comps.len() {
            if has(Card::Up2(i as u8)) {
                return Card::Up2(i as u8);
            }
        }
        for i in 0..self.comps.len() {
            if has(Card::Evo2(i as u8)) {
                return Card::Evo2(i as u8);
            }
        }
        // Baya Zidra is a heal on the spot (levelup.js:27), not a stat. Take it only while missing HP.
        if self.opts.ext.heal_below > 0.0 && has(Card::Heal) {
            let frac = if self.st.max_hp > 0.0 { self.pl.hp / self.st.max_hp } else { 1.0 };
            if frac <= self.opts.ext.heal_below {
                return Card::Heal;
            }
        }
        if !self.opts.ext.fill.is_empty() {
            for c in [Card::Sd, Card::Hd] {
                if has(c) {
                    return c;
                }
            }
            for &k in &self.opts.ext.fill {
                if self.opts.ext.stop > 0 && self.card_count(k) >= self.opts.ext.stop {
                    continue;
                }
                let c = Self::fill_card(k);
                if c == Card::Heal && self.opts.ext.heal_below > 0.0 {
                    let frac = if self.st.max_hp > 0.0 { self.pl.hp / self.st.max_hp } else { 1.0 };
                    if frac > self.opts.ext.heal_below {
                        continue;
                    }
                }
                if has(c) {
                    return c;
                }
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
        match c {
            Card::Up => self.state.move_lvl += 1,
            Card::Evo => self.state.evolved = true,
            Card::Sd => self.state.sd = (self.state.sd + 1).min(5),
            Card::Hd => self.state.hd = (self.state.hd + 1).min(5),
            Card::Up2(i) => self.comps[i as usize].1 += 1,
            Card::Evo2(i) => {
                self.comp_evo[i as usize] = true;
                if self.comp_lvl(i as usize).kind == Kind::Melee {
                    self.any_melee = true;
                }
            }
            Card::Stat(st) => {
                if self.state.cards[st as usize] < self.stat_cap(st) {
                    self.state.cards[st as usize] += 1;
                }
            }
            Card::Xp => {
                if self.xp_n < self.xp_cap() {
                    self.xp_n += 1;
                }
            }
            // levelup.js:27 heals 45 % of max HP on the spot. No cap.
            Card::Heal => {
                self.heal_n += 1;
                self.pl.hp = jmin(self.st.max_hp, self.pl.hp + self.st.max_hp * 0.45);
            }
        }
    }

    fn comp_lvl(&self, i: usize) -> &'a MoveLvl {
        let (id, lvl, _) = self.comps[i];
        let m = &self.data.moves[id];
        if self.comp_evo[i] {
            if let Some(e) = &m.evo {
                return e;
            }
        }
        &m.levels[lvl.min(m.max_lvl) - 1]
    }

    fn level_up(&mut self) {
        // Group mode spends the level on a missing bond move when the offer shows it.
        // Parity and solo runs leave rift off, so this returns before touching card_roll.
        if self.try_learn() {
            return;
        }
        let mut legal = Vec::with_capacity(12);
        self.legal_cards(&mut legal);
        if legal.is_empty() {
            return;
        }
        if self.faith() {
            // levelup.js offer(): evolution first, upgrades at 8, five of the stat cards.
            legal = self.weighted_offer(legal);
        } else {
            for i in (1..legal.len()).rev() {
                let j = (self.card_roll.next() * (i + 1) as f64).floor() as usize;
                legal.swap(i, j);
            }
            legal.truncate(3);
        }
        if legal.is_empty() {
            return;
        }
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
        // player.js:273 xpMul. Lucky Egg is ×1.3 (items.js:27). Aprendizaje is ×1.12 per card (levelup.js:25).
        let mut mul = self.opts.ext.item.xp;
        if self.opts.ext.full_cards && self.faith() && self.xp_n > 0 {
            let mut x = 1.0;
            for _ in 0..self.xp_n {
                x *= 1.12;
            }
            mul *= x;
        }
        self.xp += amount * mul;
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
            // Wilds store pre-XP_K xp (spawner.js multiplies 5.6). Bosses and legendaries do not (spawnBoss / spawnLegend).
            let raw = or(self.enemies[i].xp, 1.0);
            let boss = self.enemies[i].boss;
            let legend = self.enemies[i].legend;
            let elite = self.enemies[i].elite;
            let judge = self.enemies[i].judge;
            let (ex, ey) = (self.enemies[i].x, self.enemies[i].y);
            // spawner.js:107-108. Wild XP is round(xp * 5.6); an elite then round(that * 1.6).
            // Parity keeps the unrounded product so the XP trace matches match.js.
            let gained = if boss || legend {
                raw
            } else if self.faith() {
                let v = js_round(raw * 5.6);
                if elite { js_round(v * 1.6) } else { v }
            } else {
                raw * 5.6
            };
            // pickup.js dropXp. Faithful path leaves orbs (magnet 78, collect at 15px).
            // Parity grants the XP and the heal on the spot, as match.js does.
            let boss_drop = (self.opts.ext.bosses && boss) || (self.opts.ext.rift && legend);
            if self.faith() {
                self.drop_xp(ex, ey, gained, boss_drop, legend, judge);
            } else if boss_drop || (self.opts.ext.bosses && self.fx.next() < 0.012) {
                self.pl.hp = jmin(self.st.max_hp, self.pl.hp + self.st.max_hp * 0.3);
            }
            // enemy.js die(): a boss that is not Judgment drops 10 coins of 5 (line 174).
            // A rift legend is constructed as a boss (rift.js spawnLegend) and also drops 10 of 8 (line 191).
            // The bot is assumed to pick them up, the same way it picks heal orbs.
            // judgment.js: a Sentencia legend gives XP and nothing else. A rift legend is a boss
            // and also drops the legend shower.
            if self.enemies[i].boss && !self.enemies[i].judge {
                self.bosses += 1;
                self.picked += 50.0;
            }
            if self.enemies[i].legend && !self.enemies[i].judge {
                self.picked += 80.0;
            }
            self.enemies.remove(i);
            self.kills += 1;
            if !self.faith() {
                self.grant_xp(gained);
            }
        }
    }

    /// combat.js:37. `m.t = max(0.05, cd * cdMul)` on the faithful path.
    fn cooled(&self, cd: f64) -> f64 {
        let t = cd * self.st.cd_mul;
        if self.faith() { t.max(0.05) } else { t }
    }

    /// player.js magnet starts at 78. Imán is ×1.30, six times (levelup.js:22). The altar ×4 (interact.js:22).
    fn magnet_r(&self) -> f64 {
        let n = self.state.cards[Stat::Mag as usize].min(6);
        let mut m = 78.0;
        for _ in 0..n {
            m *= 1.30;
        }
        if self.power_t > 0.0 && self.power == 2 {
            m *= 4.0;
        }
        m
    }

    fn push_pickup(&mut self, kind: u8, x: f64, y: f64, value: f64) {
        let a = self.fx.next() * PI * 2.0;
        let spx = 10.0 + self.fx.next() * 36.0;
        let spy = 10.0 + self.fx.next() * 36.0;
        self.pickups.push(Pickup {
            kind,
            x,
            y,
            vx: self.math.cos(a) * spx,
            vy: self.math.sin(a) * spy,
            value,
            pulled: false,
        });
    }

    /// pickup.js dropXp. Bosses burst into 14 orbs plus a heal and a magnet.
    /// A wild kill is one orb, then 1.2% heal, 0.8% magnet, 0.6% bomb.
    fn drop_xp(&mut self, x: f64, y: f64, value: f64, boss: bool, legend: bool, plain: bool) {
        if boss {
            let each = (value / 14.0).ceil();
            for _ in 0..14 {
                let a = self.fx.next() * PI * 2.0;
                let d = 10.0 + self.fx.next() * 60.0;
                let ox = x + self.math.cos(a) * d;
                let oy = y + self.math.sin(a) * d;
                self.push_pickup(0, ox, oy, each);
            }
            if plain {
                return;
            }
            self.push_pickup(1, x + 24.0, y, 0.0);
            self.push_pickup(2, x - 24.0, y, 0.0);
            let _ = legend;
            return;
        }
        self.push_pickup(0, x, y, value);
        let r = self.fx.next();
        if r < 0.012 {
            let ox = self.fx.next() * 16.0 - 8.0;
            self.push_pickup(1, x + ox, y, 0.0);
        } else if r < 0.020 {
            self.push_pickup(2, x, y, 0.0);
        } else if r < 0.026 {
            self.push_pickup(3, x, y, 0.0);
        }
    }

    fn collect_pickup(&mut self, kind: u8, value: f64) {
        match kind {
            0 => self.grant_xp(value),
            1 => self.pl.hp = jmin(self.st.max_hp, self.pl.hp + self.st.max_hp * 0.3),
            2 => {
                for p in &mut self.pickups {
                    p.pulled = true;
                }
            }
            3 => self.detonate(),
            _ => {}
        }
    }

    /// game.js:525. Everything on screen takes 60 + 14 * level.
    fn detonate(&mut self) {
        let dmg = 60.0 + self.level as f64 * 14.0;
        let (px, py) = (self.pl.x, self.pl.y);
        let mut dealt = 0.0;
        for e in &mut self.enemies {
            if e.hp <= 0.0 || !sees_view(px, py, e.x, e.y, 0.0) {
                continue;
            }
            dealt += js_round(dmg).max(1.0);
            raw_hurt(e, dmg, 160.0, e.x - px, e.y - py);
        }
        self.dealt += dealt;
    }

    /// pickup.js update. Pull inside the magnet, collect inside 15px.
    fn tick_pickups(&mut self) {
        if self.pl.hp <= 0.0 {
            return;
        }
        let mag2 = self.magnet_r().powi(2);
        let dt = self.dt;
        let (px, py) = (self.pl.x, self.pl.y);
        let mut i = self.pickups.len();
        while i > 0 {
            i -= 1;
            let p = &mut self.pickups[i];
            let dx = px - p.x;
            let dy = py - p.y;
            let d2 = dx * dx + dy * dy;
            if p.pulled || d2 < mag2 {
                p.pulled = true;
                let d = d2.sqrt().max(1.0);
                let pull = 240.0 + 1400.0 / d;
                let tx = dx / d * pull;
                let ty = dy / d * pull;
                let k = (-7.0 * dt).exp();
                p.vx = tx + (p.vx - tx) * k;
                p.vy = ty + (p.vy - ty) * k;
            } else {
                let drag = 0.02_f64.powf(dt);
                p.vx *= drag;
                p.vy *= drag;
            }
            p.x += p.vx * dt;
            p.y += p.vy * dt;
            if d2 < 225.0 {
                let kind = self.pickups[i].kind;
                let value = self.pickups[i].value;
                self.pickups.swap_remove(i);
                self.collect_pickup(kind, value);
            }
        }
    }

    fn note_vel(&mut self, step: f64) {
        if !self.faith() {
            return;
        }
        if self.p_seen {
            if (self.pl.x - self.ppx).abs() > 200.0 || (self.pl.y - self.ppy).abs() > 200.0 {
                self.pvx = 0.0;
                self.pvy = 0.0;
            } else if step > 0.0 {
                let k = (step * 5.0).min(1.0);
                self.pvx += ((self.pl.x - self.ppx) / step - self.pvx) * k;
                self.pvy += ((self.pl.y - self.ppy) / step - self.pvy) * k;
            }
        } else {
            self.p_seen = true;
        }
        self.ppx = self.pl.x;
        self.ppy = self.pl.y;
    }

    /// spawner.js ahead(): place a straggler in front of the player, outside the view.
    fn ahead_of(&mut self, i: usize) -> bool {
        let sp = self.pvx.hypot(self.pvy);
        let a0 = if sp > 20.0 { self.math.atan2(self.pvy, self.pvx) } else { self.fx.next() * PI * 2.0 };
        let fly = self.enemies[i].fly;
        for k in 0..8 {
            let a = a0 + if k == 0 { 0.0 } else { self.fx.next() * 1.8 - 0.9 };
            let d = OUTER + 10.0 + self.fx.next() * 60.0;
            let x = self.pl.x + self.math.cos(a) * d;
            let y = self.pl.y + self.math.sin(a) * d * 0.9;
            let free = fly || self.terrain.as_mut().map(|t| t.world.is_free(x, y, 14.0)).unwrap_or(true);
            if free {
                let e = &mut self.enemies[i];
                e.x = x;
                e.y = y;
                e.kx = 0.0;
                e.ky = 0.0;
                e.phase = Phase::Walk;
                e.pt = 0.0;
                e.jump = None;
                return true;
            }
        }
        false
    }

    /// enemy.js:964-978. Unseen and behind for 2.5s, or farther than 1400px, respawns ahead.
    fn tick_stragglers(&mut self) {
        if self.arena_phase != 0 || self.judging {
            return;
        }
        let step = self.dt;
        let (px, py) = (self.pl.x, self.pl.y);
        let (vx, vy) = (self.pvx, self.pvy);
        let sp = vx.hypot(vy);
        let far = (OUTER + 40.0).powi(2);
        let mut i = 0;
        while i < self.enemies.len() {
            if self.enemies[i].boss || self.enemies[i].legend || self.enemies[i].hp <= 0.0 {
                i += 1;
                continue;
            }
            let dx = self.enemies[i].x - px;
            let dy = self.enemies[i].y - py;
            let d2 = dx * dx + dy * dy;
            let unseen = d2 > far && !sees_view(px, py, self.enemies[i].x, self.enemies[i].y, 60.0);
            let behind = sp > 40.0 && dx * vx + dy * vy < -0.2 * d2.sqrt() * sp;
            if unseen && behind {
                self.enemies[i].lag_t += step;
            } else if !unseen {
                self.enemies[i].lag_t = 0.0;
            }
            if (unseen && self.enemies[i].lag_t > 2.5) || d2 > 1400.0 * 1400.0 {
                self.enemies[i].lag_t = 0.0;
                if !self.ahead_of(i) {
                    self.enemies.remove(i);
                    continue;
                }
            }
            i += 1;
        }
    }

    // ------------------------------------------------ attacking

    fn life_orb(&mut self) {
        if self.opts.ext.item.lifeorb {
            self.pl.hp = jmax(1.0, self.pl.hp - jmax(1.0, self.st.max_hp * 0.01));
        }
    }

    fn cast(&mut self) -> bool {
        let mv = self.st.mv;
        // player.js cast(): life orb skips orbit and trail, and only runs when combat.js actually calls pl.cast.
        // A needsTarget miss never calls cast. Default (parity) kinds keep the previous order: life orb before the cast.
        let extra = self.opts.ext.xkinds && mv.kind == Kind::Inert && mv.xk != 0;
        if mv.kind != Kind::Orbit && !extra {
            self.life_orb();
        }
        let ok = self.cast_mv(mv);
        if extra && ok && mv.xk != 7 {
            self.life_orb();
        }
        ok
    }

    fn bonded(&self, slot: u8) -> bool {
        if !self.opts.ext.rift {
            return true;
        }
        // A rift win is a charge. Charges are spent in bond_order, and only on a move the
        // level-up cards have already offered (levelup.js poolFor). An unlearned member
        // holds the queue: the player waits instead of fusing a later move.
        let mut charged = self.bonds;
        for (i, &b) in self.bond_order.iter().enumerate() {
            if !self.learned.get(i).copied().unwrap_or(false) {
                return false;
            }
            if charged == 0 {
                return false;
            }
            if b == slot {
                return true;
            }
            charged -= 1;
        }
        false
    }

    fn bond_move(&self, slot: u8) -> usize {
        if slot == 100 {
            self.atk_buff
        } else if slot == 101 {
            self.def_buff
        } else {
            self.comps[slot as usize].0
        }
    }

    /// levelup.js:72-120. Weight of everything that is not a new-move card, and how many
    /// evolutions are ready. The first ready evolution is shown unconditionally (offer, line 131).
    fn level_offer_parts(&self) -> (f64, usize) {
        let mut ups = 0.0;
        let mut evos = 0usize;
        let mut waiting = [false; 7];
        let note_move = |evos: &mut usize, waiting: &mut [bool; 7], lvl: usize, max_lvl: usize, evolved: bool, evo: bool, needs: Option<Stat>, cards: &[u32]| {
            if evolved {
                return;
            }
            if lvl >= max_lvl && evo {
                match needs {
                    Some(n) if cards[n as usize] < 1 => waiting[n as usize] = true,
                    _ => *evos += 1,
                }
            }
        };
        note_move(&mut evos, &mut waiting, self.state.move_lvl, self.start.max_lvl, self.state.evolved, self.start.evo.is_some(), self.start.needs, &self.state.cards);
        if !self.state.evolved && self.state.move_lvl < self.start.max_lvl {
            ups += 8.0;
        }
        for i in 0..self.comps.len() {
            if !self.bonded(i as u8) || self.comp_evo[i] {
                continue;
            }
            let m = &self.data.moves[self.comps[i].0];
            let lvl = self.comps[i].1;
            if lvl < m.max_lvl {
                ups += 8.0;
            }
            note_move(&mut evos, &mut waiting, lvl, m.max_lvl, self.comp_evo[i], m.evo.is_some(), m.needs, &self.state.cards);
        }
        if self.has_sd && self.state.sd < 5 && (self.opts.ext.buffs == 0 || self.bonded(100)) {
            ups += 8.0;
        }
        if self.has_hd && self.state.hd < 5 && (self.opts.ext.buffs == 0 || self.bonded(101)) {
            ups += 8.0;
        }
        let known = 1 + self.learned.iter().filter(|on| **on).count();
        let slots_open = !self.opts.ext.rift || known < 4;
        let per = if slots_open { 4.0 } else { 7.0 };
        let mut room = 0usize;
        for st in STATS {
            if waiting[st as usize] {
                continue;
            }
            if self.state.cards[st as usize] < self.stat_cap(st) {
                room += 1;
            }
        }
        if self.opts.ext.full_cards {
            if self.xp_n < self.xp_cap() {
                room += 1;
            }
            room += 1; // Baya Zidra has no cap
        }
        let wait_n = waiting.iter().filter(|w| **w).count();
        // Five of the non-waiting stat cards, plus every stat that unlocks an evolution.
        let stats = room.min(5) as f64 * per + wait_n as f64 * 14.0;
        let extra_evo = evos.saturating_sub(1) as f64 * 40.0;
        (ups + stats + extra_evo, evos)
    }

    /// The three cards levelup.js offer() would show, minus new moves (the bond draw handles those).
    /// Evolution first, then weight 40 / 8 / 4-or-7. Parity keeps the uniform shuffle.
    fn weighted_offer(&mut self, legal: Vec<Card>) -> Vec<Card> {
        let mut evo: Vec<Card> = Vec::new();
        let mut up: Vec<Card> = Vec::new();
        let mut stat: Vec<Card> = Vec::new();
        for c in legal {
            match c {
                Card::Evo | Card::Evo2(_) => evo.push(c),
                Card::Up | Card::Up2(_) | Card::Sd | Card::Hd => up.push(c),
                _ => stat.push(c),
            }
        }
        for i in (1..stat.len()).rev() {
            let j = (self.card_roll.next() * (i + 1) as f64).floor() as usize;
            stat.swap(i, j);
        }
        stat.truncate(5);
        let (_, evos) = self.level_offer_parts();
        let per = if evos > 0 && self.learned.iter().filter(|on| **on).count() + 1 >= 4 {
            7.0
        } else {
            let known = 1 + self.learned.iter().filter(|on| **on).count();
            if !self.opts.ext.rift || known < 4 { 4.0 } else { 7.0 }
        };
        let mut pool: Vec<(Card, f64)> = Vec::new();
        let mut picked: Vec<Card> = Vec::new();
        if !evo.is_empty() {
            picked.push(evo.remove(0));
        }
        for c in evo {
            pool.push((c, 40.0));
        }
        for c in up {
            pool.push((c, 8.0));
        }
        for c in stat {
            pool.push((c, per));
        }
        while picked.len() < 3 && !pool.is_empty() {
            let total: f64 = pool.iter().map(|(_, w)| *w).sum();
            let mut r = self.card_roll.next() * total;
            let mut i = 0;
            while i + 1 < pool.len() && {
                r -= pool[i].1;
                r > 0.0
            } {
                i += 1;
            }
            picked.push(pool.remove(i).0);
        }
        picked
    }

    /// levelup.js:58. On-side moves, ties and buffs (no category, fit 1) are twice as likely.
    fn offer_weight(&self, ix: usize) -> f64 {
        let cat = self.data.moves[ix].levels[0].cat;
        let fit = if cat == 0 || self.mon.atk <= 0.0 {
            1.0
        } else {
            (if cat == 2 { self.mon.sa } else { self.mon.pa }) / self.mon.atk
        };
        if fit >= 0.999 { 2.0 } else { 1.0 }
    }

    fn is_buff_move(&self, ix: usize) -> bool {
        self.data.moves[ix].levels[0].buff != 0 || self.data.moves[ix].kind_name == "buff"
    }

    /// Draw the next group move the way levelup.js offers it.
    /// poolFor is the species pool (moves.js:442-446). pickWeighted takes 6 (levelup.js:58-59).
    /// With 2 buffs already learned, further buffs are not offered (levelup.js:47-49).
    /// New moves weigh 10 against the upgrade (8) and five stat cards (4 each) for the 3 shown.
    /// The bot takes a missing group member when one of those 3 is it, and spends the level on it.
    fn try_learn(&mut self) -> bool {
        if !self.opts.ext.rift || self.learned.iter().all(|on| *on) {
            return false;
        }
        let known_n = 1 + self.learned.iter().filter(|on| **on).count();
        if known_n >= 4 {
            return false;
        }
        let buffs_known = self.learned.iter().enumerate().filter(|(i, on)| **on && self.bond_order[*i] >= 100).count();
        let mut known = vec![self.mon.start];
        for (i, on) in self.learned.iter().enumerate() {
            if *on {
                known.push(self.bond_move(self.bond_order[i]));
            }
        }
        let mut pool: Vec<(usize, f64)> = self.mon.pool.iter().copied().filter(|&ix| {
            if known.contains(&ix) {
                return false;
            }
            if buffs_known >= 2 && self.is_buff_move(ix) {
                return false;
            }
            true
        }).map(|ix| (ix, self.offer_weight(ix))).collect();
        if pool.is_empty() {
            return false;
        }
        let drawn = pick_weighted(&mut self.card_roll, &mut pool, 6);
        // levelup.js:59-143. A new move is weight 10. A ready evolution is weight 40 and
        // offer() shows it first, so it takes one of the three slots and is not in the lump.
        // Each upgradable move is 8. Five of the nine stat cards are 4 while a slot is open
        // (5 × 4 = 20) and 7 once the four slots are full. A stat that unlocks an evolution
        // is always offered at 14.
        let (lump, evos) = self.level_offer_parts();
        let mut cards: Vec<(Option<usize>, f64)> = drawn.into_iter().map(|ix| (Some(ix), 10.0)).collect();
        if lump > 0.0 {
            cards.push((None, lump));
        }
        let slots = if evos > 0 { 2 } else { 3 };
        let mut offered: Vec<usize> = Vec::new();
        for _ in 0..slots {
            if cards.is_empty() {
                break;
            }
            let total: f64 = cards.iter().map(|(_, w)| *w).sum();
            let mut r = self.card_roll.next() * total;
            let mut i = 0;
            while i + 1 < cards.len() && {
                r -= cards[i].1;
                r > 0.0
            } {
                i += 1;
            }
            if let Some(ix) = cards.remove(i).0 {
                offered.push(ix);
            }
        }
        let mut best: Option<usize> = None;
        for (i, on) in self.learned.iter().enumerate() {
            if *on {
                continue;
            }
            let ix = self.bond_move(self.bond_order[i]);
            if offered.contains(&ix) && best.is_none() {
                best = Some(i);
            }
        }
        if let Some(i) = best {
            self.learned[i] = true;
            return true;
        }
        // The bond member was not in the offer. A player still takes a new attack when a
        // slot is open (levelup.js new-move weight 10). One slot stays reserved for each
        // planned attack that has not been offered yet, so the group can still be finished.
        if self.extra_room() {
            if let Some(ix) = self.best_offered_attack(&offered) {
                self.extras.push((ix, 0.0));
                return true;
            }
        }
        false
    }

    /// Slots left after the starter, learned bonds, extras, and unlearned attack partners.
    fn extra_room(&self) -> bool {
        let known = 1 + self.learned.iter().filter(|on| **on).count() + self.extras.len();
        let reserved = self.bond_order.iter().enumerate().filter(|(i, b)| {
            **b < 100 && !self.learned.get(*i).copied().unwrap_or(false)
        }).count();
        known + reserved < 4
    }

    fn best_offered_attack(&self, offered: &[usize]) -> Option<usize> {
        let mut best: Option<(usize, f64)> = None;
        for &ix in offered {
            if self.extras.iter().any(|(e, _)| *e == ix) {
                continue;
            }
            let l = &self.data.moves[ix].levels[0];
            let dmg = if l.dmg.is_finite() { l.dmg } else { 0.0 };
            if dmg <= 0.0 || l.buff != 0 && dmg <= 0.0 {
                continue;
            }
            if self.data.moves[ix].kind_name == "buff" {
                continue;
            }
            let cd = if l.cd.is_finite() && l.cd > 0.0 { l.cd } else { 1.0 };
            let n = if l.count.is_finite() && l.count > 0.0 { l.count } else { 1.0 };
            // A single-target shot cannot hold the spawn rate. Prefer a swing, beam,
            // orbit or pierce that clears the arc in front of the bot.
            let mv = &self.data.moves[ix];
            let aoe = match mv.levels[0].kind {
                Kind::Melee | Kind::Orbit => 4.0,
                Kind::Beam | Kind::Nova => 5.0,
                Kind::Boomerang => n.max(1.0) * 2.0,
                Kind::Projectile => (l.pierce.max(0.0) + 1.0).min(4.0) * n.max(1.0),
                Kind::Inert => match l.xk {
                    1 | 2 | 3 | 4 | 11 | 12 => 4.0,
                    8 | 13 | 14 | 15 => 3.0,
                    5 | 16 => 2.0,
                    9 | 10 => n.max(1.0),
                    _ => 1.4,
                },
            };
            let score = dmg * aoe / cd;
            if best.map(|(_, s)| score > s).unwrap_or(true) {
                best = Some((ix, score));
            }
        }
        best.map(|(ix, _)| ix)
    }

    fn cast_extras(&mut self) {
        let n = self.extras.len();
        for i in 0..n {
            if self.extras[i].1 > 0.0 {
                self.extras[i].1 -= self.dt;
                continue;
            }
            let ix = self.extras[i].0;
            let mv = &self.data.moves[ix].levels[0];
            let (cd, kind) = (mv.cd, mv.kind);
            self.extras[i].1 = self.cooled(cd);
            if kind == Kind::Orbit {
                self.side_orbit = Some((ix, 0));
            } else if !self.cast_mv(mv) {
                self.extras[i].1 = 0.05;
            }
        }
    }

    /// Melee companion in the group that is actually firing. `any_melee` covers an evolution into melee.
    fn active_has_melee(&self) -> bool {
        if self.any_melee {
            return true;
        }
        self.comps.iter().enumerate().any(|(i, _)| self.bonded(i as u8) && self.comp_lvl(i).kind == Kind::Melee)
    }

    fn cast_comps(&mut self) {
        // Inactive slot timers freeze (combat.js only ticks the active group).
        if self.slot != 0 {
            return;
        }
        for i in 0..self.comps.len() {
            if !self.bonded(i as u8) {
                continue;
            }
            self.comps[i].2 -= self.dt;
            if self.comps[i].2 <= 0.0 {
                let mv = self.comp_lvl(i);
                let (cd, kind, xk) = (mv.cd, mv.kind, mv.xk);
                // combat.js:37. The floor is max(0.05, cd*cdMul). Parity keeps the raw product.
                self.comps[i].2 = self.cooled(cd);
                // player.js:203 life orb skips orbit and trail, companions included.
                let extra = self.opts.ext.xkinds && kind == Kind::Inert && xk != 0;
                if kind != Kind::Orbit && !extra {
                    self.life_orb();
                }
                // A companion orbit cannot share the lead's orb list (combat.js keeps one set per move).
                if kind == Kind::Orbit {
                    self.side_orbit = Some((self.comps[i].0, self.comps[i].1.saturating_sub(1)));
                    continue;
                }
                if !self.cast_mv(mv) {
                    self.comps[i].2 = 0.05;
                } else if extra && xk != 7 {
                    self.life_orb();
                }
            }
        }
    }

    fn cast_mv(&mut self, mv: &'a MoveLvl) -> bool {
        if unmodelled(mv, self.opts.status, self.opts.ext.xkinds) {
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
        let atk = self.atk_for(mv.cat, mv.ty);
        match mv.kind {
            Kind::Melee => {
                let (px, py) = (self.pl.x, self.pl.y);
                let knock = or(mv.knock, 0.0);
                let mut dealt = 0.0;
                {
                    let faithful = self.faith();
                    let chance = if faithful { self.opts.ext.crit } else { 0.0 };
                    let mut rng = self.crit_rng.borrow_mut();
                    let weather = &self.weather;
                    for e in self.enemies.iter_mut() {
                        if in_melee(math, px, py, aim, mv.arc, mv.radius, e.x, e.y, e.r) {
                            let (dx, dy) = (e.x - px, e.y - py);
                            dealt += hit_one(faithful, e, mv.dmg, atk, mv.ty, tm, weather, st, if faithful { knock } else { 0.0 }, dx, dy, chance, &mut rng, mv.cat);
                        }
                    }
                }
                self.dealt += dealt;
                note_bell(&mut self.bell, self.opts.ext.item.bell, dealt);
            }
            Kind::Beam => {
                let (px, py) = (self.pl.x, self.pl.y);
                let mut dealt = 0.0;
                {
                    let faithful = self.faith();
                    let chance = if faithful { self.opts.ext.crit } else { 0.0 };
                    let mut rng = self.crit_rng.borrow_mut();
                    let weather = &self.weather;
                    for e in self.enemies.iter_mut() {
                        if in_beam(math, px, py, aim, mv.radius, mv.width, e.x, e.y, e.r) {
                            dealt += hit_one(faithful, e, mv.dmg, atk, mv.ty, tm, weather, st, 0.0, aim.cos(), aim.sin(), chance, &mut rng, mv.cat);
                        }
                    }
                }
                self.dealt += dealt;
                note_bell(&mut self.bell, self.opts.ext.item.bell, dealt);
            }
            Kind::Orbit => {
                let count = or(mv.count, 1.0);
                while (self.orbs.len() as f64) < count {
                    let a = (self.orbs.len() as f64 / count) * PI * 2.0;
                    self.orbs.push(Orb { angle: a, inside: Vec::new(), log: Vec::new() });
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
                        knock: or(mv.knock, 0.0),
                        cat: mv.cat,
                    });
                }
                self.angles = angles;
            }
            Kind::Inert => {
                if self.opts.ext.xkinds && mv.xk != 0 {
                    return self.cast_x(mv, aim, st);
                }
                // moves.js aqua-ring: stat regen, 1.6/s, 4 stacks, 8 s. Only if this move is actually cast.
                if self.faith() && mv.buff == 4 {
                    self.regen_amt = mv.amount;
                    self.regen_n = jmin(or(mv.stacks, 1.0), self.regen_n + 1.0);
                    self.regen_t = or(mv.dur, 8.0);
                    self.stat_dirty = true;
                }
            }
        }
        true
    }

    fn push_shot(&mut self, angle: f64, mv: &MoveLvl) {
        let (x, y, atk) = (self.pl.x, self.pl.y, self.atk_for(mv.cat, mv.ty));
        self.push_shot_at(x, y, angle, mv, mv.speed, mv.life, atk);
    }

    #[allow(clippy::too_many_arguments)]
    fn push_shot_at(&mut self, x: f64, y: f64, angle: f64, mv: &MoveLvl, speed: f64, life: f64, atk: f64) {
        let vx = self.math.cos(angle) * speed;
        let vy = self.math.sin(angle) * speed;
        let st = self.status_of(mv);
        self.shots.push(Shot {
            x,
            y,
            vx,
            vy,
            speed,
            r: or(mv.size, 7.0),
            life,
            left: or(mv.pierce, 0.0) + 1.0,
            hit: Vec::new(),
            dmg: mv.dmg,
            atk,
            ty: mv.ty,
            homing: or(mv.homing, 0.0),
            st,
            knock: or(mv.knock, 0.0),
            cat: mv.cat,
            bounce: or(mv.bounce, 0.0) as u32,
            drain: or(mv.drain, 0.0),
            age: 0.0,
        });
        if self.shots.len() > 80 {
            self.shots.remove(0);
        }
    }

    // ------------------------------------------------ extra kinds (fixed-group mode, combat.js)

    fn any_within(&self, x: f64, y: f64, r: f64) -> bool {
        self.enemies.iter().any(|e| e.hp > 0.0 && len(e.x - x, e.y - y) <= r + e.r)
    }

    /// Hits every live enemy in the circle (combat.js blast / queryCircle: centre distance <= r + e.r).
    fn blast(&mut self, x: f64, y: f64, r: f64, dmg: f64, atk: f64, mv: &MoveLvl) {
        let knock = if self.faith() { or(mv.knock, 0.0) } else { 0.0 };
        self.blast_ex(x, y, r, dmg, atk, mv, knock, 0.0);
    }

    /// `blast` with the knock and stun of the call. A stun that is not 0 freezes what survives the hit for
    /// that many seconds, 0.35 of it on a boss or judgment legend (combat.js stunzone, enemy.js applyStun).
    #[allow(clippy::too_many_arguments)]
    fn blast_ex(&mut self, x: f64, y: f64, r: f64, dmg: f64, atk: f64, mv: &MoveLvl, knock: f64, stun: f64) {
        let st = self.status_of(mv);
        let faithful = self.faith();
        let chance = if faithful { self.opts.ext.crit } else { 0.0 };
        let mut dealt = 0.0;
        {
            let mut rng = self.crit_rng.borrow_mut();
            let weather = &self.weather;
            let tm = &self.data.tmult;
            for e in self.enemies.iter_mut() {
                if e.hp > 0.0 && len(e.x - x, e.y - y) <= r + e.r {
                    let (dx, dy) = (e.x - x, e.y - y);
                    dealt += hit_one(faithful, e, dmg, atk, mv.ty, tm, weather, st, knock, dx, dy, chance, &mut rng, mv.cat);
                    if stun > 0.0 && e.hp > 0.0 {
                        e.stun_t = jmax(e.stun_t, stun * if e.boss || e.judge { kinds::HEAVY_STUN } else { 1.0 });
                    }
                }
            }
        }
        self.dealt += dealt;
        note_bell(&mut self.bell, self.opts.ext.item.bell, dealt);
    }

    fn cast_x(&mut self, mv: &'a MoveLvl, aim: f64, st: Status) -> bool {
        let atk = self.atk_for(mv.cat, mv.ty);
        let (px, py) = (self.pl.x, self.pl.y);
        let count = or(mv.count, 1.0).floor().max(1.0);
        match mv.xk {
            // cone(): short fan of fast shots
            1 => {
                // combat.js needsTarget: centre distance < speed*life+30 (projectile.js nearest), not radius + e.r
                if !self.enemies.iter().any(|e| e.hp > 0.0 && len(e.x - px, e.y - py) < mv.speed * mv.life + 30.0) {
                    return false;
                }
                let n = count.max(2.0);
                let arc = or(mv.arc, 0.9);
                let mut i = 0.0;
                while i < n {
                    let a = aim + (i / (n - 1.0) - 0.5) * arc + (self.fx.next() * 0.1 - 0.05);
                    let sp = mv.speed * (0.85 + self.fx.next() * 0.25);
                    let life = mv.life * (0.85 + self.fx.next() * 0.2);
                    self.push_shot_at(px + a.cos() * 4.0, py + a.sin() * 4.0, a, mv, sp, life, atk);
                    i += 1.0;
                }
            }
            // meteors(): fall 0.5 s later on random enemies within reach 340
            2 => {
                // needsTarget is centre < 340; placement uses queryCircle(reach 340), which is centre <= 340 + e.r
                if !self.enemies.iter().any(|e| e.hp > 0.0 && len(e.x - px, e.y - py) < 340.0) {
                    return false;
                }
                let mut near: Vec<usize> =
                    (0..self.enemies.len()).filter(|&i| { let e = &self.enemies[i]; e.hp > 0.0 && len(e.x - px, e.y - py) <= 340.0 + e.r }).collect();
                for i in (1..near.len()).rev() {
                    let j = (self.fx.next() * (i + 1) as f64) as usize;
                    near.swap(i, j);
                }
                for i in 0..count as usize {
                    let (x, y) = match near.get(i) {
                        Some(&k) => (self.enemies[k].x + self.fx.next() * 16.0 - 8.0, self.enemies[k].y + self.fx.next() * 12.0 - 6.0),
                        None => (px + self.fx.next() * 280.0 - 140.0, py + self.fx.next() * 220.0 - 110.0),
                    };
                    self.fields.push(Field { k: 2, x, y, t: -(i as f64) * 0.09, life: 0.5, r: mv.radius, atk, tick: 0.0, mv, n: 0, i: 0, ca: 0.0, sa: 0.0 });
                }
            }
            // chain(): jumps to the nearest unhit enemy within radius, 15 % less each jump; hex x mv.hex on a status
            3 => {
                // chain() first hop: projectile.js nearest within reach 280 (centre). Later hops: centre < radius
                // (the radius^2 filter), not queryCircle's radius + e.r.
                let mut cur = match nearest(&self.enemies, px, py) {
                    Some(i) if len(self.enemies[i].x - px, self.enemies[i].y - py) < 280.0 => Some(i),
                    _ => return false,
                };
                let mut done: Vec<usize> = Vec::new();
                let mut k = 1.0;
                let faithful = self.faith();
                let chance = if faithful { self.opts.ext.crit } else { 0.0 };
                let knock = if faithful { or(mv.knock, 0.0) } else { 0.0 };
                let mut dealt = 0.0;
                for _ in 0..count as usize {
                    let Some(i) = cur else { break };
                    done.push(i);
                    let hex = {
                        let e = &self.enemies[i];
                        hex_multiplier(mv.hex, e.burn, e.poison, e.slow)
                    };
                    {
                        let mut rng = self.crit_rng.borrow_mut();
                        let weather = &self.weather;
                        let tm = &self.data.tmult;
                        let e = &mut self.enemies[i];
                        let (dx, dy) = (e.x - px, e.y - py);
                        dealt += hit_one(faithful, e, mv.dmg * k * hex, atk, mv.ty, tm, weather, st, knock, dx, dy, chance, &mut rng, mv.cat);
                    }
                    k *= 0.85;
                    let (cx, cy) = (self.enemies[i].x, self.enemies[i].y);
                    let mut best = None;
                    let mut bd = mv.radius * mv.radius;
                    for (j, o) in self.enemies.iter().enumerate() {
                        if o.hp <= 0.0 || done.contains(&j) {
                            continue;
                        }
                        let d = (o.x - cx) * (o.x - cx) + (o.y - cy) * (o.y - cy);
                        if d < bd {
                            bd = d;
                            best = Some(j);
                        }
                    }
                    cur = best;
                }
                self.dealt += dealt;
                note_bell(&mut self.bell, self.opts.ext.item.bell, dealt);
            }
            // aura(): everything in the circle; drain heals at most 6 per cast
            4 => {
                let mut healed = 0.0;
                let faithful = self.faith();
                let chance = if faithful { self.opts.ext.crit } else { 0.0 };
                let knock = if faithful { or(mv.knock, 0.0) } else { 0.0 };
                let mut dealt = 0.0;
                {
                    let mut rng = self.crit_rng.borrow_mut();
                    let weather = &self.weather;
                    let tm = &self.data.tmult;
                    for e in self.enemies.iter_mut() {
                        if e.hp > 0.0 && len(e.x - px, e.y - py) <= mv.radius + e.r {
                            let (dx, dy) = (e.x - px, e.y - py);
                            dealt += hit_one(faithful, e, mv.dmg, atk, mv.ty, tm, weather, st, knock, dx, dy, chance, &mut rng, mv.cat);
                            if mv.drain.is_finite() {
                                healed += mv.drain;
                            }
                        }
                    }
                }
                self.dealt += dealt;
                note_bell(&mut self.bell, self.opts.ext.item.bell, dealt);
                if healed > 0.0 {
                    self.pl.hp = jmin(self.st.max_hp, self.pl.hp + jmin(healed, 6.0));
                }
            }
            // dash(): lunge along the aim (stopped by walls), 0.3 s invulnerable, hits along the path
            5 => {
                if !self.enemies.iter().any(|e| e.hp > 0.0 && len(e.x - px, e.y - py) < mv.radius + 60.0) {
                    return false;
                }
                // A lunge at the nearest body lands inside the pack. Prefer the heading
                // whose landing spot is not already crowded; the hit test is unchanged.
                let open = self.open_heading(px, py);
                let mut best_a = aim;
                let mut best_s = f64::NEG_INFINITY;
                let options = [aim, open.1.atan2(open.0), self.pl.diry.atan2(self.pl.dirx)];
                for &a in &options {
                    if !a.is_finite() {
                        continue;
                    }
                    let (c, s) = (a.cos(), a.sin());
                    let lx = px + c * mv.radius;
                    let ly = py + s * mv.radius;
                    let mut crowd = 0.0;
                    let mut hits = 0.0;
                    for e in &self.enemies {
                        if e.hp <= 0.0 {
                            continue;
                        }
                        if len(e.x - lx, e.y - ly) < 64.0 {
                            crowd += 1.0;
                        }
                        let ex = e.x - px;
                        let ey = e.y - py;
                        let along = ex * c + ey * s;
                        if along > 0.0 && along < mv.radius + e.r && (-ex * s + ey * c).abs() < or(mv.width, 34.0) * 0.5 + e.r {
                            hits += 1.0;
                        }
                    }
                    let score = hits * 2.0 - crowd * 3.5;
                    if score > best_s {
                        best_s = score;
                        best_a = a;
                    }
                }
                let (ca, sa) = (best_a.cos(), best_a.sin());
                let mut l = 0.0;
                let mut d = 8.0;
                let pr = self.pl.r;
                while d <= mv.radius {
                    if let Some(t) = &mut self.terrain {
                        if !t.world.is_free_ex(px + ca * d, py + sa * d, pr * 0.8, true) {
                            break;
                        }
                    }
                    l = d;
                    d += 8.0;
                }
                let (ex, ey) = (px + ca * l, py + sa * l);
                self.pl.x = ex;
                self.pl.y = ey;
                // combat.js dash: invuln = max(invuln, 0.3). Lava clears it (player.js liquid).
                self.pl.inv = jmax(self.pl.inv, 0.3);
                let w = or(mv.width, 34.0);
                let faithful = self.faith();
                let chance = if faithful { self.opts.ext.crit } else { 0.0 };
                let knock = if faithful { or(mv.knock, 0.0) } else { 0.0 };
                let mut dealt = 0.0;
                {
                    let mut rng = self.crit_rng.borrow_mut();
                    let weather = &self.weather;
                    let tm = &self.data.tmult;
                    for e in self.enemies.iter_mut() {
                        if e.hp <= 0.0 {
                            continue;
                        }
                        let (vx, vy) = (ex - px, ey - py);
                        let ll = vx * vx + vy * vy;
                        let tt = if ll > 0.0 { (((e.x - px) * vx + (e.y - py) * vy) / ll).clamp(0.0, 1.0) } else { 0.0 };
                        let (qx, qy) = (px + vx * tt - e.x, py + vy * tt - e.y);
                        if qx * qx + qy * qy <= (w / 2.0 + e.r) * (w / 2.0 + e.r) {
                            let (dx, dy) = (e.x - px, e.y - py);
                            dealt += hit_one(faithful, e, mv.dmg, atk, mv.ty, tm, weather, st, knock, dx, dy, chance, &mut rng, mv.cat);
                        }
                    }
                }
                self.dealt += dealt;
                note_bell(&mut self.bell, self.opts.ext.item.bell, dealt);
            }
            // mines(): armed after 0.35 s, burst when stepped on (half damage when they expire); 4 + 2n at most
            6 => {
                for _ in 0..count as usize {
                    let a = self.fx.next() * 6.2832;
                    let d = if count <= 1.0 { 0.0 } else { 18.0 + self.fx.next() * 28.0 };
                    self.fields.push(Field { k: 6, x: px + a.cos() * d, y: py + a.sin() * d * 0.8, t: 0.0, life: or(mv.dur, 7.0), r: mv.radius, atk, tick: 0.0, mv, n: 0, i: 0, ca: 0.0, sa: 0.0 });
                }
                let max = 4 + 2 * count as usize;
                let n = self.fields.iter().filter(|f| f.k == 6).count();
                if n > max {
                    let mut drop = n - max;
                    self.fields.retain(|f| if f.k == 6 && drop > 0 { drop -= 1; false } else { true });
                }
            }
            // trailPatch(): a damaging puddle every so often, ticks every 0.5 s; 18 at most
            7 => {
                let (lx, ly, lt) = self.patch_at;
                if lx.is_finite() && len(lx - px, ly - py) < mv.radius * 0.9 && self.t - lt < 1.0 {
                    return true;
                }
                self.patch_at = (px, py, self.t);
                self.fields.push(Field { k: 7, x: px, y: py, t: 0.0, life: or(mv.dur, 3.0), r: mv.radius, atk, tick: 0.0, mv, n: 0, i: 0, ca: 0.0, sa: 0.0 });
                let n = self.fields.iter().filter(|f| f.k == 7).count();
                if n > 18 {
                    let mut drop = n - 18;
                    self.fields.retain(|f| if f.k == 7 && drop > 0 { drop -= 1; false } else { true });
                }
            }
            // turret(): left behind you, shoots the nearest enemy for a while; `count` at most
            8 => {
                let a = aim + PI + (self.fx.next() * 1.2 - 0.6);
                self.fields.push(Field { k: 8, x: px + a.cos() * 26.0, y: py + a.sin() * 20.0, t: 0.0, life: or(mv.dur, 6.0), r: 0.0, atk, tick: 0.3, mv, n: 0, i: 0, ca: 0.0, sa: 0.0 });
                let max = count as usize;
                let n = self.fields.iter().filter(|f| f.k == 8).count();
                if n > max {
                    let mut drop = n - max;
                    self.fields.retain(|f| if f.k == 8 && drop > 0 { drop -= 1; false } else { true });
                }
            }
            // homing, bounce, charge, spin, quake, vortex, shove, stun: engine/kinds.rs
            9..=16 => return self.cast_new(mv, aim),
            _ => {}
        }
        true
    }

    fn step_fields(&mut self) {
        let dt = self.dt;
        let mut i = self.fields.len();
        while i > 0 {
            i -= 1;
            self.fields[i].t += dt;
            let f = &self.fields[i];
            let (k, x, y, t, life, r, atk, mv) = (f.k, f.x, f.y, f.t, f.life, f.r, f.atk, f.mv);
            match k {
                2 => {
                    if t >= life {
                        self.blast(x, y, r, mv.dmg, atk, mv);
                        self.fields.remove(i);
                    }
                }
                6 => {
                    let trig = t >= 0.35 && self.any_within(x, y, 14.0);
                    if trig || t >= life {
                        self.blast(x, y, r, mv.dmg * if trig { 1.0 } else { 0.5 }, atk, mv);
                        self.fields.remove(i);
                    }
                }
                7 => {
                    if t >= life {
                        self.fields.remove(i);
                        continue;
                    }
                    self.fields[i].tick -= dt;
                    if self.fields[i].tick <= 0.0 {
                        self.fields[i].tick = 0.5;
                        self.blast(x, y, r, mv.dmg, atk, mv);
                    }
                }
                8 => {
                    if t >= life {
                        self.fields.remove(i);
                        continue;
                    }
                    self.fields[i].tick -= dt;
                    if self.fields[i].tick <= 0.0 {
                        let range = or(mv.range, 300.0);
                        let tg = nearest(&self.enemies, x, y).filter(|&j| len(self.enemies[j].x - x, self.enemies[j].y - y) <= range + self.enemies[j].r);
                        self.fields[i].tick = if tg.is_some() { or(mv.rate, 0.6) } else { 0.15 };
                        if let Some(j) = tg {
                            let a = (self.enemies[j].y - y).atan2(self.enemies[j].x - x);
                            self.push_shot_at(x, y, a, mv, or(mv.speed, 300.0), 1.4, atk);
                        }
                    }
                }
                11 | 12 | 13 | 14 | 16 => {
                    if self.step_new_field(i) {
                        self.fields.remove(i);
                    }
                }
                _ => {}
            }
        }
    }

    // ------------------------------------------------ rifts and bosses (fixed-group mode)

    /// rift.js update(): from t > 75 and t < Judgment.AT-120 a check every 30 s opens a rift with chance
    /// 0.2·(1+misses). A check with a boss alive resets the timer and does not count (rift.js:47). The rift lasts 45 s.
    /// Entering (dist < 30 of rift.y-10) starts the arena; the bond is granted only when the legendary dies (rift.js:199).
    fn tick_rift(&mut self, boss_alive: bool) {
        if !self.opts.ext.rift || self.arena_phase != 0 {
            return;
        }
        let dt = self.dt;
        if self.rift_ttl >= 0.0 {
            self.rift_ttl -= dt;
            if self.rift_walk >= 0.0 {
                self.rift_walk -= dt;
                if self.rift_walk < 0.0 && self.rift_ttl > 0.0 {
                    self.enter_arena();
                    return;
                }
            }
            if self.rift_ttl <= 0.0 {
                self.rift_ttl = -1.0;
                self.rift_walk = -1.0;
            }
            return;
        }
        if self.bonds >= self.bond_order.len() || self.t <= 75.0 || self.t >= RIFT_UNTIL {
            return;
        }
        self.rift_check -= dt;
        if self.rift_check > 0.0 {
            return;
        }
        self.rift_check = 30.0;
        if boss_alive {
            return;
        }
        if self.fx.next() < 0.2 * (1.0 + self.rift_misses) {
            self.rift_misses = 0.0;
            self.open_rift();
        } else {
            self.rift_misses += 1.0;
        }
    }

    /// rift.js open(): up to 24 placements, d in [380, 560], y scaled by 0.85, skipped when the tile isn't free.
    /// Walk time is (distance to the entrance − 30) / current speed. The bot does not path; this is an estimate.
    /// A rift farther than 45 s still occupies its TTL (checks stay frozen) but is not entered.
    fn open_rift(&mut self) {
        let (px, py) = (self.pl.x, self.pl.y);
        for _ in 0..24 {
            let a = self.fx.next() * 6.2832;
            let d = 380.0 + self.fx.next() * 180.0;
            let x = px + self.math.cos(a) * d;
            let y = py + self.math.sin(a) * d * 0.85;
            if let Some(t) = &mut self.terrain {
                if !t.world.is_free(x, y, 22.0) {
                    continue;
                }
            }
            let dx = x - px;
            let dy = (y - 10.0) - py;
            let walk = (dx.hypot(dy) - 30.0).max(0.0) / self.st.spd.max(1.0);
            if walk <= 45.0 {
                self.rift_ttl = 45.0;
                if walk <= 0.0 {
                    self.enter_arena();
                } else {
                    self.rift_walk = walk;
                }
            } else {
                self.rift_ttl = 45.0;
                self.rift_walk = -1.0;
            }
            return;
        }
    }

    /// rift.js begin(): stash map enemies, clear shots and fields, spawn the legendary ~208 px north.
    /// Arena columns and weather are not modelled; the fight is in open space (legend ignores map walls).
    fn enter_arena(&mut self) {
        self.arena_back = (self.pl.x, self.pl.y);
        self.arena_phase = 1;
        self.arena_t = 0.0;
        self.arena_end = 0.0;
        self.arena_down = 0.0;
        self.rift_ttl = -1.0;
        self.rift_walk = -1.0;
        self.stash = std::mem::take(&mut self.enemies);
        self.shots.clear();
        self.booms.clear();
        self.orbs.clear();
        self.fields.clear();
        self.e_shots.clear();
        self.hazards.clear();
        self.spawn_legend();
    }

    fn spawn_legend(&mut self) {
        let legs: Vec<usize> = self.data.dex.iter().enumerate().filter(|(_, m)| m.leg).map(|(i, _)| i).collect();
        if legs.is_empty() {
            return;
        }
        let weights: Vec<f64> = legs.iter().map(|&i| if self.beaten.contains(&self.data.dex[i].dex) { 1.0 } else { 4.0 }).collect();
        let total: f64 = weights.iter().sum();
        let mut r = self.fx.next() * total;
        let mut mi = 0;
        while mi + 1 < legs.len() {
            r -= weights[mi];
            if r <= 0.0 {
                break;
            }
            mi += 1;
        }
        let t = self.t;
        let (px, py) = (self.pl.x, self.pl.y);
        let shot_cd = 0.3 + self.fx.next() * 0.6;
        let ai = Rng::new((self.fx.next() * 4294967296.0) as u32);
        let mon = &self.data.dex[legs[mi]];
        let dex = mon.dex;
        let combo = mon.combo;
        let rad = self.boss_radius(mon);
        let spd_stat = mon.spd;
        let ty0 = mon.types.first().copied().unwrap_or(T_NORMAL);
        let water = mon.types.contains(&T_WATER);
        let fire = mon.types.contains(&T_FIRE);
        let ranged = has_ty(mon, &[T_PSYCHIC, T_ELECTRIC, T_GHOST, T_FAIRY, T_FIRE, T_WATER, T_ICE, T_DRAGON]);
        let hp = js_round(3200.0 + t * 9.0);
        let spd = js_round((48.0 + (spd_stat - 78.0) * 0.6).clamp(48.0, 105.0));
        let dmg = js_round(36.0 + t / 20.0);
        let shot = js_round(18.0 + t / 40.0);
        let xp = js_round(500.0 + t * 1.2);
        let beh = if ranged { Beh::Ranged } else { Beh::Charger };
        let def = Def { beh, hp, spd, dmg, xp, shot_dmg: shot, shot_cd: 0.9, range: 300.0, zones: f64::NAN, fan_n: f64::NAN };
        self.arena_dex = dex;
        // Hit radius is species r ×2 (bossScale for a default idle anchor; enemy.js:15–22, sprites.js:127–130).
        // The game sets flying=false so arena rocks block shots; here the fight is in open space, so the legend ignores map walls.
        let mut e = special_enemy(self.seq, dex as u16, px, py - LEGEND_GAP, rad, combo, ty0, xp, beh, spd, dmg, hp, shot_cd, shot, ai, def, true, water, fire, true, true);
        e.sand_safe = mon.types.iter().any(|&t| t == T_ROCK || t == T_GROUND || t == T_STEEL);
        e.snow_safe = mon.types.contains(&T_ICE);
        e.cat = if mon.sa > mon.pa { 2 } else { 1 };
        e.g_phys = guard(self.math, mon.df);
        e.g_spec = guard(self.math, mon.sd);
        self.seq += 1;
        self.enemies.push(e);
    }

    fn single_dps(&self) -> f64 {
        if self.dps_samples.is_empty() {
            return 0.0;
        }
        let mut top = self.dps_samples.clone();
        top.sort_by(|a, b| b.partial_cmp(a).unwrap_or(std::cmp::Ordering::Equal));
        top.truncate(6);
        top.iter().sum::<f64>() / top.len() as f64
    }

    /// judgment.js fight(). The map is stashed and nothing else spawns. Published runs stop at 900 s,
    /// so this only changes a match that is allowed to pass minute 30.
    fn begin_judgment(&mut self) {
        self.judging = true;
        self.jd_t = 0.0;
        self.jd_boss_t = 1.2;
        self.jd_n = 0;
        let t = self.t;
        let floor = (3200.0 + t * 9.0) * 0.35;
        self.jd_base = floor.max(self.single_dps() * 3.0);
        self.jd_cx = self.pl.x;
        self.jd_cy = self.pl.y;
        let legs: Vec<usize> = self
            .data
            .dex
            .iter()
            .enumerate()
            .filter(|(_, m)| m.leg && m.dex != 493)
            .map(|(i, _)| i)
            .collect();
        let mut q = Vec::new();
        if !legs.is_empty() {
            for _ in 0..40 {
                let i = ((self.fx.next() * legs.len() as f64).floor() as usize).min(legs.len() - 1);
                q.push(legs[i]);
            }
        }
        self.jd_q = q;
        self.stash = std::mem::take(&mut self.enemies);
        self.shots.clear();
        self.booms.clear();
        self.orbs.clear();
        self.fields.clear();
        self.e_shots.clear();
        self.hazards.clear();
        let ar = self.data.dex.iter().find(|m| m.dex == 493).map(|m| m.r * 1.5 * 0.9).unwrap_or(28.0);
        self.arceus_r = ar;
        self.arceus_x = self.jd_cx;
        self.arceus_y = self.jd_cy - 32.0 * 5.0;
        self.arceus_cd = 2.2;
        self.arceus_touch = 0.0;
        self.arceus_cast = -1.0;
        self.arceus_wind = 0.7;
        self.arceus_kind = 0;
        self.stat_dirty = true;
    }

    fn push_pure(&mut self, kind: HKind, x: f64, y: f64, r: f64, angle: f64, len: f64, w: f64, delay: f64, pct: f64) {
        self.hazards.push(Hazard {
            kind,
            x,
            y,
            r,
            angle,
            len,
            w,
            delay,
            t: 0.0,
            dmg: 1.0,
            ty: 0,
            cat: 0,
            pure: true,
            pct,
        });
    }

    fn cast_arceus(&mut self, kind: u8) {
        self.arceus_kind = kind;
        self.arceus_cast = 0.0;
        self.arceus_wind = if kind == 1 { 1.1 } else if kind == 2 { 0.85 } else { 0.7 };
        if kind == 0 {
            let n = 4 + (self.jd_t / 10.0).floor().min(6.0) as usize;
            for i in 0..n {
                let a = self.fx.next() * PI * 2.0;
                let d = if i == 0 { 0.0 } else { 40.0 + self.fx.next() * 110.0 };
                let x = self.pl.x + self.math.cos(a) * d;
                let y = self.pl.y + self.math.sin(a) * d * 0.8;
                let delay = 1.25 + i as f64 * 0.09;
                self.push_pure(HKind::Zone, x, y, 44.0, 0.0, 0.0, 0.0, delay, 0.3);
            }
        } else if kind == 1 {
            let a0 = self.math.atan2(self.pl.y - self.arceus_y, self.pl.x - self.arceus_x)
                + if self.fx.next() < 0.5 { 0.0 } else { PI / 4.0 };
            let n = if self.jd_t > 30.0 { 8 } else { 4 };
            for i in 0..n {
                let angle = a0 + i as f64 * PI * 2.0 / n as f64;
                self.push_pure(HKind::Beam, self.arceus_x, self.arceus_y, 0.0, angle, 1700.0, 34.0, 1.1, 0.35);
            }
        } else {
            self.push_pure(HKind::Zone, self.arceus_x, self.arceus_y, 170.0, 0.0, 0.0, 0.0, 0.85, 0.4);
        }
    }

    fn clamp_judgment(&mut self, x: &mut f64, y: &mut f64) {
        let max = (24.0 - 1.4) * 32.0;
        let dx = *x - self.jd_cx;
        let dy = *y - self.jd_cy;
        let d = len(dx, dy);
        if d > max {
            *x = self.jd_cx + dx / d * max;
            *y = self.jd_cy + dy / d * max;
        }
    }

    fn spawn_judge_legend(&mut self) {
        if self.jd_q.is_empty() {
            return;
        }
        let mi = self.jd_q[self.jd_n as usize % self.jd_q.len()];
        let k = 2.0_f64.powi(self.jd_n as i32);
        let t = self.t;
        let (cx, cy) = (self.jd_cx, self.jd_cy);
        let fast = self.st.spd;
        let mut placed = false;
        let mut x = cx;
        let mut y = cy;
        for _ in 0..16 {
            let a = self.fx.next() * PI * 2.0;
            let d = (24.0 - (3.0 + self.fx.next() * 3.0)) * 32.0;
            x = cx + self.math.cos(a) * d;
            y = cy + self.math.sin(a) * d;
            if len(self.pl.x - x, self.pl.y - y) > 280.0 {
                placed = true;
                break;
            }
        }
        if !placed {
            x = cx + 400.0;
            y = cy;
        }
        let mon = &self.data.dex[mi];
        let dex = mon.dex;
        let combo = mon.combo;
        let rad = self.boss_radius(mon);
        let spd_stat = mon.spd;
        let ty0 = mon.types.first().copied().unwrap_or(T_NORMAL);
        let water = mon.types.contains(&T_WATER);
        let fire = mon.types.contains(&T_FIRE);
        let ranged = has_ty(mon, &[T_PSYCHIC, T_ELECTRIC, T_GHOST, T_FAIRY, T_FIRE, T_WATER, T_ICE, T_DRAGON]);
        let hp = js_round(self.jd_base * k);
        let spd = js_round((48.0 + (spd_stat - 78.0) * 0.6).clamp(48.0, 105.0)).max(fast * 0.8);
        let spd = js_round(spd);
        let dmg = js_round((36.0 + t / 20.0) * k);
        let shot = js_round((18.0 + t / 40.0) * k);
        let xp = js_round(500.0 + t * 1.2);
        let beh = if ranged { Beh::Ranged } else { Beh::Charger };
        let sand = mon.types.iter().any(|&ty| ty == T_ROCK || ty == T_GROUND || ty == T_STEEL);
        let snow = mon.types.contains(&T_ICE);
        let cat = if mon.sa > mon.pa { 2 } else { 1 };
        let g_phys = guard(self.math, mon.df);
        let g_spec = guard(self.math, mon.sd);
        let shot_cd = 0.9;
        let ai = Rng::new((self.fx.next() * 4294967296.0) as u32);
        let def = Def { beh, hp, spd, dmg, xp, shot_dmg: shot, shot_cd, range: 300.0, zones: f64::NAN, fan_n: f64::NAN };
        let mut e = special_enemy(self.seq, dex as u16, x, y, rad, combo, ty0, xp, beh, spd, dmg, hp, shot_cd, shot, ai, def, false, water, fire, true, true);
        e.sand_safe = sand;
        e.snow_safe = snow;
        e.cat = cat;
        e.g_phys = g_phys;
        e.g_spec = g_spec;
        e.judge = true;
        self.seq += 1;
        self.jd_n += 1;
        self.enemies.push(e);
    }

    /// judgment.js update/arceusTick/touch/spawnBoss. Arceus is not an enemy: shots do not target him.
    fn tick_judgment(&mut self) {
        let dt = self.dt;
        self.jd_t += dt;
        let (px, py) = (self.pl.x, self.pl.y);
        let (mut ax, mut ay) = (self.arceus_x, self.arceus_y);
        let dx = px - ax;
        let dy = py - ay;
        let dist = len(dx, dy);
        if self.arceus_cast < 0.0 {
            let k = judgment_chase_k(self.jd_t);
            let spd = (self.st.spd * k).max(70.0);
            if dist > 1e-6 {
                ax += dx / dist * spd * dt;
                ay += dy / dist * spd * dt;
            }
            self.arceus_cd -= dt;
            if self.arceus_cd <= 0.0 {
                let kind = if dist < 210.0 && self.fx.next() < 0.6 {
                    2
                } else if self.arceus_kind == 0 {
                    1
                } else {
                    0
                };
                self.arceus_x = ax;
                self.arceus_y = ay;
                self.cast_arceus(kind);
                ax = self.arceus_x;
                ay = self.arceus_y;
            }
        } else {
            self.arceus_cast += dt;
            if self.arceus_cast >= self.arceus_wind + 0.35 {
                self.arceus_cast = -1.0;
                self.arceus_cd = 1.4_f64.max(3.2 - self.jd_t * 0.025);
            }
        }
        self.clamp_judgment(&mut ax, &mut ay);
        self.arceus_x = ax;
        self.arceus_y = ay;
        self.arceus_touch -= dt;
        let dist = len(self.pl.x - ax, self.pl.y - ay);
        let rr = self.arceus_r + self.pl.r;
        if self.arceus_touch <= 0.0 && self.pl.hp > 0.0 && dist * dist <= rr * rr {
            self.arceus_touch = 0.9;
            self.pl.inv = 0.0;
            let pct = judgment_touch_pct(self.jd_t);
            let hp = self.st.max_hp;
            self.hurt_pure(hp * pct);
        }
        self.jd_boss_t -= dt;
        if self.jd_boss_t <= 0.0 {
            self.jd_boss_t = 5.0;
            self.spawn_judge_legend();
        }
        let (mut x, mut y) = (self.pl.x, self.pl.y);
        self.clamp_judgment(&mut x, &mut y);
        self.pl.x = x;
        self.pl.y = y;
        let mut i = 0;
        while i < self.enemies.len() {
            let (mut x, mut y) = (self.enemies[i].x, self.enemies[i].y);
            self.clamp_judgment(&mut x, &mut y);
            self.enemies[i].x = x;
            self.enemies[i].y = y;
            i += 1;
        }
    }

    /// rift.js arenaTick / won / lost / finish. Map time keeps running. A death here does not end the run.
    fn tick_arena(&mut self) {
        let dt = self.dt;
        if self.arena_phase == 1 {
            self.arena_t += dt;
            let legend_alive = self.enemies.iter().any(|e| e.legend && e.hp > 0.0);
            if !legend_alive {
                let dex = self.arena_dex;
                if dex != 0 && !self.beaten.contains(&dex) {
                    self.beaten.push(dex);
                }
                self.bonds += 1;
                self.stat_dirty = true;
                self.arena_phase = 2;
                self.arena_end = 5.0;
                return;
            }
            if self.pl.hp <= 0.0 {
                self.arena_down += dt;
            } else {
                self.arena_down = 0.0;
            }
            if self.arena_down > 1.4 || self.arena_t > 120.0 {
                self.arena_phase = 3;
                self.arena_end = 1.2;
            }
            return;
        }
        self.arena_end -= dt;
        if self.arena_end <= 0.0 {
            self.finish_arena();
        }
    }

    fn finish_arena(&mut self) {
        self.stats();
        self.enemies.clear();
        self.shots.clear();
        self.booms.clear();
        self.orbs.clear();
        self.fields.clear();
        self.e_shots.clear();
        self.hazards.clear();
        self.enemies = std::mem::take(&mut self.stash);
        self.pl.x = self.arena_back.0;
        self.pl.y = self.arena_back.1;
        if self.pl.hp <= 0.0 {
            self.pl.hp = (self.st.max_hp * 0.3).max(1.0);
            self.pl.inv = 2.0;
        }
        self.arena_phase = 0;
    }

    /// enemies.js rollRun bakes the five bosses at the start of the run: a non-legendary in the BST band
    /// (fallback bst >= 580), unique per run. behavior is 'ranged' or charger/chase from base speed.
    fn roll_bosses(&mut self) {
        let mut used: Vec<u32> = Vec::new();
        for i in 0..BOSS_SLOTS.len() {
            let (lo, hi) = BOSS_BST[i];
            let (_, hp, dmg, xp) = BOSS_SLOTS[i];
            let mut pool: Vec<usize> = self
                .data
                .dex
                .iter()
                .enumerate()
                .filter(|(_, m)| !m.leg && !used.contains(&m.dex) && m.bst >= lo && m.bst <= hi)
                .map(|(ix, _)| ix)
                .collect();
            if pool.is_empty() {
                pool = self
                    .data
                    .dex
                    .iter()
                    .enumerate()
                    .filter(|(_, m)| !m.leg && !used.contains(&m.dex) && m.bst >= 580.0)
                    .map(|(ix, _)| ix)
                    .collect();
            }
            if pool.is_empty() {
                continue;
            }
            let k = ((self.fx.next() * pool.len() as f64).floor() as usize).min(pool.len() - 1);
            let ix = pool[k];
            let mon = &self.data.dex[ix];
            used.push(mon.dex);
            let bs = base_spd(mon);
            let beh = if boss_is_ranged(mon) { Beh::Ranged } else if bs > 90.0 { Beh::Charger } else { Beh::Chase };
            self.boss_picks.push(BossPick {
                ix,
                beh,
                hp: js_round(hp * 1.35),
                spd: js_round((40.0 + bs * 0.5).clamp(40.0, 100.0)),
                dmg: js_round(dmg * 1.2),
                xp,
                shot: js_round(dmg * 0.55),
            });
        }
    }

    /// spawner.js spawnBoss + enemy.js constructor with bossScale. Ignores the spawn cap (EnemyMgr.add).
    /// Personalities other than ranged/charger/chase are collapsed. Hit radius ×2 estimates bossScale for a default sprite.
    fn spawn_boss(&mut self) -> bool {
        let Some(pick) = self.boss_picks.get(self.boss_idx).copied() else {
            return false;
        };
        // The game's EnemyMgr.add ignores the cap. The sim's collision tables hold 64, so a non-boss
        // is dropped to make room (the boss still enters the fight).
        if self.enemies.len() >= CAP {
            let Some(i) = self.enemies.iter().position(|e| !e.boss) else {
                return false;
            };
            self.enemies.remove(i);
        }
        let sc = 1.0 + self.t / 600.0;
        let aim = self.fx.next() * PI * 2.0;
        let dd = OUTER + 10.0 + self.fx.next() * 60.0;
        let (px, py) = (self.pl.x, self.pl.y);
        let x = px + self.math.cos(aim) * dd;
        let y = py + self.math.sin(aim) * dd * 0.9;
        let hp = js_round(pick.hp * sc);
        let dmg = pick.dmg * sc;
        let shot = pick.shot * sc;
        let shot_cd = 0.3 + self.fx.next() * (1.1 - 0.3);
        let ai = Rng::new((self.fx.next() * 4294967296.0) as u32);
        let mon = &self.data.dex[pick.ix];
        let def = Def {
            beh: pick.beh,
            hp: pick.hp,
            spd: pick.spd,
            dmg: pick.dmg,
            xp: pick.xp,
            shot_dmg: pick.shot,
            shot_cd: 1.1,
            range: 260.0,
            zones: f64::NAN,
            fan_n: f64::NAN,
        };
        let water = mon.types.contains(&T_WATER);
        let fire = mon.types.contains(&T_FIRE);
        let ty0 = mon.types.first().copied().unwrap_or(T_NORMAL);
        let dex = mon.dex as u16;
        let rad = self.boss_radius(mon);
        let combo = mon.combo;
        let mut e = special_enemy(
            self.seq, dex, x, y, rad, combo, ty0, pick.xp, pick.beh, pick.spd, dmg, hp, shot_cd, shot, ai, def, true, water, fire, true, false,
        );
        e.sand_safe = mon.types.iter().any(|&t| t == T_ROCK || t == T_GROUND || t == T_STEEL);
        e.snow_safe = mon.types.contains(&T_ICE);
        e.cat = if mon.sa > mon.pa { 2 } else { 1 };
        e.g_phys = guard(self.math, mon.df);
        e.g_spec = guard(self.math, mon.sd);
        self.seq += 1;
        self.enemies.push(e);
        true
    }

    fn step_shots(&mut self) {
        let faithful = self.faith();
        let chance = if faithful { self.opts.ext.crit } else { 0.0 };
        let bell_on = self.opts.ext.item.bell;
        let math = self.math;
        let dt = self.dt;
        let tm = &self.data.tmult;
        let weather = &self.weather;
        let crit_rng = &self.crit_rng;
        let enemies = &mut self.enemies;
        let shots = &mut self.shots;
        let terrain = &mut self.terrain;
        let mut dealt = 0.0;
        let mut healed = 0.0;
        // strike() only touches hp/shield, so positions stay fixed for the whole shot pass.
        let soa = &mut self.shot_soa;
        let lanes = soa.load(enemies);
        let mut i = shots.len();
        while i > 0 {
            i -= 1;
            let shot = &mut shots[i];
            // steer(): nearest() is pure, so it only matters for homing shots.
            let turn = shot.homing;
            if faithful {
                // projectile.js: velocity damped toward the nearest enemy inside 340 px, speed kept.
                if turn > 0.0 {
                    let near = nearest(enemies, shot.x, shot.y).filter(|&n| len(enemies[n].x - shot.x, enemies[n].y - shot.y) < kinds::HOMING_LOCK);
                    if let Some(n) = near {
                        let (tx, ty) = (enemies[n].x - shot.x, enemies[n].y - shot.y);
                        let d = or(len(tx, ty), 1.0);
                        let sp = len(shot.vx, shot.vy);
                        shot.vx = kinds::damp(shot.vx, tx / d * sp, turn, dt);
                        shot.vy = kinds::damp(shot.vy, ty / d * sp, turn, dt);
                    }
                }
                shot.age += dt;
            } else {
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
            }
            shot.x += shot.vx * dt;
            shot.y += shot.vy * dt;
            shot.life -= dt;
            if shot.life <= 0.0 {
                shots.remove(i);
                continue;
            }
            // Arena columns are not modelled; shots are not blocked by the map while the rift fight is on.
            if self.arena_phase == 0 {
            if let Some(t) = terrain {
                if let Some(b) = t.world.projectile_block(shot.x, shot.y, shot.r) {
                    if let Block::Prop { chunk, ix, destructible: true } = b {
                        t.world.damage_prop(chunk, ix, shot.dmg * shot.atk);
                    }
                    shots.remove(i);
                    continue;
                }
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
                    let (sd, sa, sty, sst, sk, svx, svy, scat) = (shot.dmg, shot.atk, shot.ty, shot.st, if faithful { shot.knock } else { 0.0 }, shot.vx, shot.vy, shot.cat);
                    {
                        let mut rng = crit_rng.borrow_mut();
                        dealt += hit_one(faithful, e, sd, sa, sty, tm, weather, sst, sk, svx, svy, chance, &mut rng, scat);
                    }
                    healed += shot.drain;
                    if shot.bounce > 0 {
                        // combat.js rebound: jump to the nearest enemy not hit yet within 220 px of this one,
                        // a bounce is spent, 0.5 s of life comes back, and this shot is not consumed.
                        let (hx, hy) = (enemies[k].x, enemies[k].y);
                        let mut best = None;
                        let mut bd = kinds::REBOUND_REACH * kinds::REBOUND_REACH;
                        for o in enemies.iter() {
                            if o.hp <= 0.0 || has(&shot.hit, o.id) {
                                continue;
                            }
                            let d = (o.x - hx) * (o.x - hx) + (o.y - hy) * (o.y - hy);
                            if d < bd {
                                bd = d;
                                best = Some((o.x, o.y));
                            }
                        }
                        if let Some((bx, by)) = best {
                            shot.bounce -= 1;
                            let sp = or(len(shot.vx, shot.vy), 300.0);
                            let (nx, ny) = (bx - hx, by - hy);
                            let nn = or(len(nx, ny), 1.0);
                            shot.vx = nx / nn * sp;
                            shot.vy = ny / nn * sp;
                            shot.x = hx;
                            shot.y = hy;
                            let back = jmin(shot.age, kinds::REBOUND_LIFE);
                            shot.age -= back;
                            shot.life += back;
                            shot.left += 1.0;
                            break;
                        }
                    }
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
                    let (bd, ba, bt, bst, bk, bcat) = (b.dmg, b.atk, b.ty, b.st, if faithful { b.knock } else { 0.0 }, b.cat);
                    let (dx, dy) = (e.x - x, e.y - y);
                    {
                        let mut rng = crit_rng.borrow_mut();
                        dealt += hit_one(faithful, e, bd, ba, bt, tm, weather, bst, bk, dx, dy, chance, &mut rng, bcat);
                    }
                }
            }
        }
        self.dealt += dealt;
        note_bell(&mut self.bell, bell_on, dealt);
        if healed > 0.0 {
            self.pl.hp = jmin(self.st.max_hp, self.pl.hp + healed);
        }
        self.step_orbs();
    }

    fn step_orbs(&mut self) {
        // setActive clears orbs; a swapped-away orbit must not keep hitting.
        if self.slot == 1 {
            self.orbs.clear();
            self.step_side_orbs();
            return;
        }
        let mv = self.st.mv;
        if mv.kind != Kind::Orbit {
            self.orbs.clear();
            self.step_side_orbs();
            return;
        }
        let st = self.status_of(mv);
        let math = self.math;
        let count = or(mv.count, 1.0);
        while (self.orbs.len() as f64) < count {
            let a = (self.orbs.len() as f64 / count) * PI * 2.0;
            self.orbs.push(Orb { angle: a, inside: Vec::new(), log: Vec::new() });
        }
        let faithful = self.faith();
        let chance = if faithful { self.opts.ext.crit } else { 0.0 };
        let knock = if faithful { or(mv.knock, 0.0) } else { 0.0 };
        // combat.js:486 rehit is max(0.12, m.cd), with no cdMul. Parity hits once per overlap.
        let rehit = jmax(0.12, mv.cd);
        let now = self.t;
        let bell_on = self.opts.ext.item.bell;
        let (plx, ply, dt) = (self.pl.x, self.pl.y, self.dt);
        let atk = self.atk_for(mv.cat, mv.ty);
        let mut dealt = 0.0;
        {
            let mut rng = self.crit_rng.borrow_mut();
            let weather = &self.weather;
            let tm = &self.data.tmult;
            for orb in self.orbs.iter_mut() {
                orb.angle += or(mv.speed, 1.0) * dt;
                let x = plx + math.cos(orb.angle) * mv.radius;
                let y = ply + math.sin(orb.angle) * mv.radius;
                for e in self.enemies.iter_mut() {
                    if e.hp <= 0.0 {
                        continue;
                    }
                    let overlap = len(e.x - x, e.y - y) < or(mv.size, 8.0) + e.r;
                    if !faithful {
                        if overlap {
                            if !has(&orb.inside, e.id) {
                                orb.inside.push(e.id);
                                dealt += hit_one(false, e, mv.dmg, atk, mv.ty, tm, weather, st, 0.0, 0.0, 0.0, 0.0, &mut rng, mv.cat);
                            }
                        } else if let Some(k) = orb.inside.iter().position(|&id| id == e.id) {
                            orb.inside.swap_remove(k);
                        }
                    } else if overlap {
                        let last = orb.log.iter().find(|(id, _)| *id == e.id).map(|(_, t)| *t).unwrap_or(-99.0);
                        if now - last >= rehit {
                            if let Some(p) = orb.log.iter_mut().find(|(id, _)| *id == e.id) {
                                p.1 = now;
                            } else {
                                orb.log.push((e.id, now));
                            }
                            let (dx, dy) = (e.x - x, e.y - y);
                            dealt += hit_one(true, e, mv.dmg, atk, mv.ty, tm, weather, st, knock, dx, dy, chance, &mut rng, mv.cat);
                        }
                    }
                }
            }
        }
        self.dealt += dealt;
        note_bell(&mut self.bell, bell_on, dealt);
        self.step_side_orbs();
    }

    /// Orbit that is not the lead. combat.js allows an orbit in any slot; the lead keeps `orbs`.
    fn step_side_orbs(&mut self) {
        let Some((ix, lvl)) = self.side_orbit else {
            return;
        };
        let m = &self.data.moves[ix];
        let lv = lvl.min(m.max_lvl.saturating_sub(1));
        let mv = &m.levels[lv];
        let count = or(mv.count, 1.0);
        while (self.side_orbs.len() as f64) < count {
            let a = (self.side_orbs.len() as f64 / count) * PI * 2.0;
            self.side_orbs.push(Orb { angle: a, inside: Vec::new(), log: Vec::new() });
        }
        let math = self.math;
        let chance = self.opts.ext.crit;
        let knock = or(mv.knock, 0.0);
        let rehit = jmax(0.12, mv.cd);
        let now = self.t;
        let (plx, ply, dt) = (self.pl.x, self.pl.y, self.dt);
        let atk = self.atk_for(mv.cat, mv.ty);
        let st = self.status_of(mv);
        let radius = mv.radius;
        let speed = or(mv.speed, 1.0);
        let size = or(mv.size, 8.0);
        let (dmg, ty, cat) = (mv.dmg, mv.ty, mv.cat);
        let mut dealt = 0.0;
        {
            let mut rng = self.crit_rng.borrow_mut();
            let weather = &self.weather;
            let tm = &self.data.tmult;
            for orb in self.side_orbs.iter_mut() {
                orb.angle += speed * dt;
                let x = plx + math.cos(orb.angle) * radius;
                let y = ply + math.sin(orb.angle) * radius;
                for e in self.enemies.iter_mut() {
                    if e.hp <= 0.0 {
                        continue;
                    }
                    if len(e.x - x, e.y - y) >= size + e.r {
                        continue;
                    }
                    let last = orb.log.iter().find(|(id, _)| *id == e.id).map(|(_, t)| *t).unwrap_or(-99.0);
                    if now - last < rehit {
                        continue;
                    }
                    if let Some(p) = orb.log.iter_mut().find(|(id, _)| *id == e.id) {
                        p.1 = now;
                    } else {
                        orb.log.push((e.id, now));
                    }
                    let (dx, dy) = (e.x - x, e.y - y);
                    dealt += hit_one(true, e, dmg, atk, ty, tm, weather, st, knock, dx, dy, chance, &mut rng, cat);
                }
            }
        }
        self.dealt += dealt;
        note_bell(&mut self.bell, self.opts.ext.item.bell, dealt);
    }

    // ------------------------------------------------ bot

    /// Melee swing that is live in the bonded group. `None` off the ranking path, so parity is unchanged.
    /// `companions_only` is the ranged-lead case: the lead already keeps its own melee distance.
    fn bonded_melee_radius(&self, companions_only: bool) -> Option<f64> {
        if !self.opts.ext.rift {
            return None;
        }
        let mut rad = if !companions_only && self.current_move().kind == Kind::Melee {
            Some(self.current_move().radius)
        } else {
            None
        };
        for i in 0..self.comps.len() {
            if !self.bonded(i as u8) {
                continue;
            }
            let mv = self.comp_lvl(i);
            if mv.kind == Kind::Melee {
                rad = Some(rad.map_or(mv.radius, |r| r.max(mv.radius)));
            }
        }
        rad
    }

    fn nearest_gap(&self) -> Option<f64> {
        let (px, py, pr) = (self.pl.x, self.pl.y, self.pl.r);
        let mut best = f64::INFINITY;
        for e in &self.enemies {
            if e.hp <= 0.0 {
                continue;
            }
            let gap = len(e.x - px, e.y - py) - e.r - pr;
            if gap < best {
                best = gap;
            }
        }
        if best.is_finite() { Some(best) } else { None }
    }

    /// Gap the Play bot wants from the nearest enemy, in pixels of air (after both radii).
    /// Melee and orbit step inside the swing. A turret stays inside its range and out of contact.
    /// A buff has nothing to hit, so it holds a wide kite.
    fn attack_keep(mv: &MoveLvl, plr: f64) -> f64 {
        let pos = |x: f64, d: f64| if x.is_finite() && x > 0.0 { x } else { d };
        match mv.kind {
            Kind::Melee => (pos(mv.radius, 60.0) - plr - 8.0).clamp(12.0, 72.0),
            Kind::Projectile | Kind::Nova | Kind::Beam | Kind::Boomerang => {
                // pickup.js magnet starts at 78. A keep past that leaves the corpse's
                // orb on the ground, so the run never levels. Air gap so the body
                // (about 16px) plus the player still sits inside the magnet.
                (78.0 - plr - 16.0).clamp(34.0, 62.0)
            }
            Kind::Orbit => (pos(mv.radius, 62.0) - plr - 4.0).clamp(14.0, 80.0),
            Kind::Inert => match mv.xk {
                // chain / cone / mine / meteor still drop the orb on the body they hit
                1 | 2 | 3 | 6 | 7 | 8 => (78.0 - plr - 16.0).clamp(34.0, 62.0),
                4 => (pos(mv.radius, 80.0) - plr).clamp(16.0, 70.0),
                // spin and shove hit a circle around the player, like a melee swing
                12 | 15 => (pos(mv.radius, 60.0) - plr - 8.0).clamp(12.0, 72.0),
                5 => (pos(mv.radius, 110.0) * 0.45).clamp(22.0, 70.0),
                _ => (78.0 - plr - 16.0).clamp(34.0, 62.0),
            },
        }
    }

    fn play_keep(&self) -> f64 {
        let mut keep = Self::attack_keep(self.st.mv, self.pl.r);
        let crowd = self.near_crowd(36.0);
        if crowd <= 2 {
            if let Some(rad) = self.bonded_melee_radius(true) {
                keep = keep.min((rad - self.pl.r - 8.0).clamp(12.0, 72.0));
            }
            for i in 0..self.comps.len() {
                if !self.bonded(i as u8) {
                    continue;
                }
                let mv = self.comp_lvl(i);
                if mv.kind == Kind::Orbit {
                    keep = keep.min(Self::attack_keep(mv, self.pl.r));
                }
            }
        }
        keep
    }

    fn near_crowd(&self, gap_max: f64) -> usize {
        let (px, py, pr) = (self.pl.x, self.pl.y, self.pl.r);
        self.enemies
            .iter()
            .filter(|e| e.hp > 0.0 && len(e.x - px, e.y - py) - e.r - pr < gap_max)
            .count()
    }

    /// Escape a shot that will pass through the player in the next 0.7 s.
    /// The player is treated as standing still; the caller is about to step aside.
    fn shot_escape(px: f64, py: f64, pr: f64, sx: f64, sy: f64, vx: f64, vy: f64, sr: f64) -> Option<(f64, f64, f64)> {
        let sp2 = vx * vx + vy * vy;
        if sp2 < 1.0 {
            return None;
        }
        let t = ((px - sx) * vx + (py - sy) * vy) / sp2;
        if t < 0.0 || t > 0.7 {
            return None;
        }
        let cx = sx + vx * t;
        let cy = sy + vy * t;
        let dx = px - cx;
        let dy = py - cy;
        let dist = (dx * dx + dy * dy).sqrt();
        let hit = sr + pr + 10.0;
        if dist >= hit {
            return None;
        }
        let (ex, ey) = if dist > 1.0 {
            (dx / dist, dy / dist)
        } else {
            let sp = sp2.sqrt();
            (-vy / sp, vx / sp)
        };
        Some((ex, ey, (hit - dist) / t.max(0.05)))
    }

    /// True when enemies within 220px cover almost every direction. Steering away from
    /// the nearest body then points back into the ring, so the caller breaks out instead.
    fn flanked(&self, px: f64, py: f64) -> bool {
        let mut angs: Vec<f64> = Vec::new();
        for e in &self.enemies {
            if e.hp <= 0.0 {
                continue;
            }
            let dx = e.x - px;
            let dy = e.y - py;
            let d = len(dx, dy);
            if d > 1.0 && d < 260.0 {
                angs.push(dy.atan2(dx));
            }
        }
        if angs.len() < 6 {
            return false;
        }
        angs.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let mut biggest = 0.0_f64;
        for i in 0..angs.len() {
            let a = angs[i];
            let b = if i + 1 == angs.len() { angs[0] + PI * 2.0 } else { angs[i + 1] };
            biggest = biggest.max(b - a);
        }
        // Under ~80° of open arc the nearest-body flee points back into the pack.
        biggest < 1.4
    }

    /// Direction through the widest opening inside 280px. Used when the pack is a ring.
    fn widest_gap(&self, px: f64, py: f64) -> (f64, f64) {
        let math = self.math;
        let mut angs: Vec<f64> = Vec::new();
        for e in &self.enemies {
            if e.hp <= 0.0 {
                continue;
            }
            let dx = e.x - px;
            let dy = e.y - py;
            let d = len(dx, dy);
            if d > 1.0 && d < 280.0 {
                angs.push(dy.atan2(dx));
            }
        }
        if angs.is_empty() {
            return (1.0, 0.0);
        }
        angs.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let mut best = 0.0_f64;
        let mut mid = 0.0_f64;
        for i in 0..angs.len() {
            let a = angs[i];
            let b = if i + 1 == angs.len() { angs[0] + PI * 2.0 } else { angs[i + 1] };
            let gap = b - a;
            if gap > best {
                best = gap;
                mid = a + gap * 0.5;
            }
        }
        (math.cos(mid), math.sin(mid))
    }

    /// Unit aim: circle the pack. A straight flee runs into the spawn ring
    /// (spawner.js places the next wave just outside the view, and enemy.js
    /// puts stragglers ahead of the player's velocity).
    fn orbit_aim(&self, px: f64, py: f64, pr: f64, keep: f64) -> (f64, f64) {
        let mut cx = 0.0;
        let mut cy = 0.0;
        let mut wsum = 0.0;
        let mut near_dx = 0.0;
        let mut near_dy = 0.0;
        let mut near_gap = f64::INFINITY;
        let mut near_spd = 60.0;
        let mut n = 0usize;
        for e in &self.enemies {
            if e.hp <= 0.0 {
                continue;
            }
            let dx = e.x - px;
            let dy = e.y - py;
            let dist = len(dx, dy);
            if dist < 1.0 || dist > 460.0 {
                continue;
            }
            let gap = dist - e.r - pr;
            let w = 1.0 / dist;
            cx += dx * w;
            cy += dy * w;
            wsum += w;
            n += 1;
            if gap < near_gap {
                near_gap = gap;
                near_dx = dx;
                near_dy = dy;
                near_spd = if e.phase == Phase::Dash { e.spd * 3.4 } else { e.spd };
            }
        }
        if n == 0 || wsum <= 0.0 {
            return if self.pl.dirx == 0.0 && self.pl.diry == 0.0 {
                (1.0, 0.0)
            } else {
                (self.pl.dirx, self.pl.diry)
            };
        }
        let nd = or(len(near_dx, near_dy), 1e-6);
        let nux = near_dx / nd;
        let nuy = near_dy / nd;
        let cd = or(len(cx, cy), 1e-6);
        let cux = cx / cd;
        let cuy = cy / cd;
        let tx = -cuy;
        let ty = cux;
        let sign = if self.pl.dirx * tx + self.pl.diry * ty >= 0.0 { 1.0 } else { -1.0 };
        let mut fx = tx * sign;
        let mut fy = ty * sign;
        let ttc = if near_gap <= 0.0 { 0.0 } else { near_gap / near_spd.max(1.0) };
        if self.flanked(px, py) && self.pl.inv <= 0.08 {
            let (gx, gy) = self.widest_gap(px, py);
            fx = gx;
            fy = gy;
        } else if self.pl.inv > 0.08 {
            // Hurt i-frames (player.js 0.45s). Stay on the tangent.
        } else if ttc < 0.45 || near_gap < keep * 0.7 || near_gap < 20.0 {
            fx -= nux * 1.25;
            fy -= nuy * 1.25;
        } else if near_gap > keep * 1.35 && ttc > 0.9 {
            fx += cux * 0.65;
            fy += cuy * 0.65;
        }
        let mag = or(len(fx, fy), 1e-6);
        (fx / mag, fy / mag)
    }

    /// Heading with the fewest bodies in front. Hysteresis on the current direction
    /// stops the choice flipping every reaction tick.
    fn open_heading(&self, px: f64, py: f64) -> (f64, f64) {
        let math = self.math;
        let (dx0, dy0) = (self.pl.dirx, self.pl.diry);
        let mut best_s = f64::NEG_INFINITY;
        let mut best = if dx0 == 0.0 && dy0 == 0.0 { (1.0, 0.0) } else { (dx0, dy0) };
        for k in 0..16 {
            let a = k as f64 * (PI / 8.0);
            let c = math.cos(a);
            let s = math.sin(a);
            let mut score = (dx0 * c + dy0 * s) * 1.6;
            for e in &self.enemies {
                if e.hp <= 0.0 {
                    continue;
                }
                let dx = e.x - px;
                let dy = e.y - py;
                let d = len(dx, dy);
                if d < 1.0 || d > 340.0 {
                    continue;
                }
                let dot = (dx * c + dy * s) / d;
                if dot <= 0.15 {
                    continue;
                }
                let near = 1.0 - d / 340.0;
                score -= near * near * (0.3 + dot) * 4.2;
                if d - e.r - self.pl.r < 90.0 && dot > 0.4 {
                    score -= 4.0;
                }
            }
            if score > best_s {
                best_s = score;
                best = (c, s);
            }
        }
        best
    }

    /// Published bot. Orbits the pack at magnet range (pickup.js, 78px) so shots,
    /// melee and XP orbs all connect. A straight flee runs into the spawn ring
    /// (spawner.js) and into stragglers placed ahead of that velocity (enemy.js).
    /// The tangent is also what makes a runner's lead-aim miss. Threats it answers:
    /// charger aim then dash, ranged and fan shots, beamer and zoner telegraphs,
    /// bomber and jumper zones, and Sentencia's warned circles and beams (judgment.js).
    /// Orbs are pickup.js.
    fn decide_play(&mut self) {
        self.pl.react -= self.dt;
        if self.pl.react > 0.0 {
            return;
        }
        let (px, py, pr) = (self.pl.x, self.pl.y, self.pl.r);
        let keep = self.play_keep();
        let math = self.math;
        let mut ax = 0.0;
        let mut ay = 0.0;
        let mut urgent = false;
        let mut cx = 0.0;
        let mut cy = 0.0;
        let mut cn = 0.0;
        let mut near: Option<usize> = None;
        let mut near_d = f64::INFINITY;
        for (i, e) in self.enemies.iter().enumerate() {
            if e.hp <= 0.0 {
                continue;
            }
            let dx = e.x - px;
            let dy = e.y - py;
            let dist = or(len(dx, dy), 1e-6);
            if dist < 240.0 {
                cx += e.x;
                cy += e.y;
                cn += 1.0;
            }
            if dist < near_d {
                near_d = dist;
                near = Some(i);
            }
            let gap = dist - e.r - pr;
            let ux = dx / dist;
            let uy = dy / dist;
            // A ring of small repulses cancels and the player stands in the pack.
            // Separation is handled once, against the nearest body, below.
            if !e.beh.no_touch() && gap < 14.0 {
                let w = 1.4 + (14.0 - gap) * 0.2;
                ax -= ux * w;
                ay -= uy * w;
                urgent = true;
            }
            if e.phase == Phase::Aim || (e.phase == Phase::Dash && gap < 90.0) {
                // The dash goes along the line to the player. Step off that line.
                let tx = -uy;
                let ty = ux;
                let sign = if cn > 1.0 {
                    let mx = cx / cn - px;
                    let my = cy / cn - py;
                    if tx * mx + ty * my > 0.0 { -1.0 } else { 1.0 }
                } else {
                    1.0
                };
                let w = if e.phase == Phase::Aim { 2.6 } else { 2.0 };
                ax += tx * sign * w;
                ay += ty * sign * w;
                urgent = true;
            }
        }
        if self.judging {
            let dx = self.arceus_x - px;
            let dy = self.arceus_y - py;
            let dist = or(len(dx, dy), 1e-6);
            let gap = dist - self.arceus_r - pr;
            if gap < 90.0 {
                let w = ((90.0 - gap) / 12.0).max(0.4);
                ax -= dx / dist * w;
                ay -= dy / dist * w;
                if gap < 20.0 {
                    urgent = true;
                }
            }
        }
        for s in &self.e_shots {
            if let Some((ex, ey, w)) = Self::shot_escape(px, py, pr, s.x, s.y, s.vx, s.vy, s.r) {
                ax += ex * w;
                ay += ey * w;
                if w > 1.5 {
                    urgent = true;
                }
            }
        }
        for h in &self.hazards {
            let soon = h.delay - h.t;
            let live = h.t >= h.delay;
            let winding = !live && soon < 0.85;
            if !live && !winding {
                continue;
            }
            let w = if live { 4.0 } else if soon < 0.4 { 3.2 } else { 1.3 };
            if h.kind == HKind::Zone {
                let dx = px - h.x;
                let dy = py - h.y;
                let dist = or(len(dx, dy), 1e-6);
                let reach = h.r + pr * 0.6 + 12.0;
                if dist < reach {
                    ax += dx / dist * w;
                    ay += dy / dist * w;
                    urgent = true;
                }
            } else {
                let ca = math.cos(h.angle);
                let sa = math.sin(h.angle);
                let rdx = px - h.x;
                let rdy = py - h.y;
                let along = rdx * ca + rdy * sa;
                let perp = -rdx * sa + rdy * ca;
                let half = h.w / 2.0 + pr + 8.0;
                if along > -24.0 && along < h.len + 24.0 && perp.abs() < half {
                    let sign = if perp >= 0.0 { 1.0 } else { -1.0 };
                    ax += -sa * sign * w;
                    ay += ca * sign * w;
                    urgent = true;
                }
            }
        }
        let (hx, hy) = self.orbit_aim(px, py, pr, keep);
        let s = self.st.spd.max(40.0);
        let mut fx = hx * s;
        let mut fy = hy * s;
        let min_gap = near.map(|n| {
            let e = &self.enemies[n];
            near_d - e.r - pr
        });
        // Telegraph and shot dodges add to the orbit. They do not replace it,
        // or a warned beam turns the circle into a straight line into the next spawn.
        fx += ax * s * 0.85;
        fy += ay * s * 0.85;
        let safe = min_gap.map(|g| g > 24.0).unwrap_or(true) && !urgent;
        if safe && !self.pickups.is_empty() {
            let hurt = self.pl.hp < self.st.max_hp * 0.72;
            let mut best = f64::INFINITY;
            let mut bx = 0.0;
            let mut by = 0.0;
            for p in &self.pickups {
                let dx = p.x - px;
                let dy = p.y - py;
                let d = len(dx, dy);
                if d > 200.0 || d < 1.0 {
                    continue;
                }
                let pen = match p.kind {
                    3 => 0.45,
                    1 => if hurt { 0.28 } else { 1.6 },
                    2 => 0.55,
                    _ => 1.0,
                };
                let score = d * pen;
                if score < best {
                    best = score;
                    bx = dx / d;
                    by = dy / d;
                }
            }
            if best.is_finite() {
                // Orbs only pull inside 78px (pickup.js). Step toward one that is
                // already near the circle; don't abandon the orbit for a far gem.
                let align = bx * hx + by * hy;
                let mut w = if align > 0.15 { 0.85 } else { 0.28 };
                if hurt {
                    w += 0.45;
                }
                fx += bx * s * w;
                fy += by * s * w;
            }
        }
        if let Some(n) = near {
            let e = &self.enemies[n];
            let dx = e.x - px;
            let dy = e.y - py;
            let dist = or(len(dx, dy), 1e-6);
            let gap = dist - e.r - pr;
            let chase = if e.phase == Phase::Dash { e.spd * 3.4 } else { e.spd };
            let ttc = if gap <= 0.0 { 0.0 } else { gap / chase.max(1.0) };
            if self.pl.inv <= 0.08 && (gap < 28.0 || ttc < 0.4) {
                let ux = dx / dist;
                let uy = dy / dist;
                let mag = len(fx, fy).max(1.0);
                let away = -fx * ux - fy * uy;
                let need = (chase / s).clamp(0.55, 0.92);
                if away < mag * need {
                    fx -= ux * (mag * need - away + mag * 0.25);
                    fy -= uy * (mag * need - away + mag * 0.25);
                }
                urgent = true;
            }
        }
        let mag = len(fx, fy);
        if mag < 1e-6 {
            self.pl.dirx = 0.0;
            self.pl.diry = 0.0;
        } else {
            self.pl.dirx = fx / mag;
            self.pl.diry = fy / mag;
        }
        // steer() will turn 90° into the pack when the escape ray hits a wall.
        // Score clearance and bodies together so a corner doesn't become a dive.
        if self.pl.dirx != 0.0 || self.pl.diry != 0.0 {
            let (dx, dy) = (self.pl.dirx, self.pl.diry);
            (self.pl.dirx, self.pl.diry) = self.play_dir(px, py, pr, dx, dy);
        }
        self.pl.react = if urgent { 0.05 } else { 0.10 };
    }

    /// Wanted heading, deflected only as far as a clear ray requires, and never
    /// toward a body if some other clear ray exists.
    fn play_dir(&mut self, px: f64, py: f64, pr: f64, wantx: f64, wanty: f64) -> (f64, f64) {
        if self.terrain.is_none() {
            return (wantx, wanty);
        }
        let avoid = match self.terrain.as_ref().unwrap().world.liquid {
            Liquid::Water => !self.mon.types.contains(&T_WATER),
            Liquid::Lava => !self.mon.types.contains(&T_FIRE),
        };
        let foes: Vec<(f64, f64)> = self.enemies.iter().filter(|e| e.hp > 0.0).map(|e| (e.x, e.y)).collect();
        let t = self.terrain.as_mut().unwrap();
        let base = wanty.atan2(wantx);
        let mut best_s = f64::NEG_INFINITY;
        let mut best = (wantx, wanty);
        for k in 0..16 {
            let off = (k as f64 / 2.0).ceil() * (PI / 16.0) * if k % 2 == 0 { 1.0 } else { -1.0 };
            let a = base + off;
            let c = a.cos();
            let s = a.sin();
            let mut clear = 0.0;
            let mut d = 10.0;
            while d <= 100.0 {
                if !t.world.fits(px + c * d, py + s * d, pr * 0.9, avoid) {
                    break;
                }
                clear = d;
                d += 18.0;
            }
            let mut pen = 0.0;
            for (ex, ey) in &foes {
                let dx = ex - px;
                let dy = ey - py;
                let dist = len(dx, dy);
                if dist < 150.0 && dist > 1.0 && (dx * c + dy * s) / dist > 0.45 {
                    pen += (150.0 - dist) / 150.0;
                }
            }
            let align = c * wantx + s * wanty;
            let score = align * 1.4 + clear / 100.0 - pen * 2.8;
            if score > best_s {
                best_s = score;
                best = (c, s);
            }
        }
        best
    }

    fn decide(&mut self) {
        if self.opts.bot == Bot::Play {
            self.decide_play();
            return;
        }
        let mut keep = keep_distance(self.st.mv);
        // A bonded melee move is only useful inside its swing. Close to that keep instead of
        // holding the ranged lead's kite distance (which let the swing whiff and still grant DR).
        let closing = if let Some(rad) = self.bonded_melee_radius(true) {
            keep = keep.min(0.55 * rad);
            // Repulse stays off until the hold gap, so the swing can land. The hold itself
            // is the bot's policy; the game has no extra contact hit on the walk in.
            self.nearest_gap().map(|g| g > keep).unwrap_or(false)
        } else {
            false
        };
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
            if self.opts.bot == Bot::Repulse && !closing {
                let gap = dist - e.r - pl.r;
                if gap < 160.0 {
                    let w = 1.0 / jmax(8.0, gap);
                    fx -= (dx / dist) * w;
                    fy -= (dy / dist) * w;
                }
            } else if self.opts.bot == Bot::Kite {
                let gap = dist - e.r - pl.r;
                if gap < 240.0 {
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
        } else if self.opts.bot == Bot::Kite {
            // Hold the attack's range and strafe. Contact is no longer the way the bot plays.
            if gap < keep {
                fx -= dx / dist;
                fy -= dy / dist;
            } else if gap > keep + 28.0 {
                fx += dx / dist * 0.35;
                fy += dy / dist * 0.35;
            }
            fx += -dy / dist;
            fy += dx / dist;
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

    fn support_full(&self) -> [bool; 3] {
        let mut n = [0u8; 3];
        for e in &self.enemies {
            if e.hp <= 0.0 {
                continue;
            }
            let i = match e.beh {
                Beh::Healer => 0,
                Beh::Shielder => 1,
                Beh::Summoner => 2,
                _ => continue,
            };
            n[i] = n[i].saturating_add(1);
        }
        [n[0] >= 3, n[1] >= 3, n[2] >= 3]
    }

    fn support_ix(beh: Beh) -> Option<usize> {
        match beh {
            Beh::Healer => Some(0),
            Beh::Shielder => Some(1),
            Beh::Summoner => Some(2),
            _ => None,
        }
    }

    /// enemy.js bossScale. Parity keeps the old ×2 estimate so boss traces stay put.
    fn boss_radius(&self, mon: &Mon) -> f64 {
        let scale = if self.faith() { crate::radii::boss_scale(mon.dex).unwrap_or(2.0) } else { 2.0 };
        mon.r * scale
    }

    fn plain_beh(b: Beh) -> bool {
        matches!(b, Beh::Chase | Beh::Charger | Beh::Ranged | Beh::Tank)
    }

    fn support_beh(b: Beh) -> bool {
        matches!(b, Beh::Healer | Beh::Shielder | Beh::Summoner)
    }

    /// enemies.js castFor + rollRun. Seven species per tier, once: one support, one warning
    /// attacker from tier 2 on, and the fastest plain turned into the runner.
    fn roll_roster(&mut self) {
        if !self.faith() {
            return;
        }
        let n = self.data.tiers.len();
        self.roster = vec![Vec::new(); n];
        self.runner_ix = vec![None; n];
        for ti in 0..n {
            let from = self.data.tiers[ti].from;
            let behs: Vec<Beh> = self.data.tiers[ti].cands.iter().map(|c| c.def.beh).collect();
            let spds: Vec<f64> = self.data.tiers[ti].cands.iter().map(|c| c.def.spd).collect();
            let len = behs.len();
            let mut pick: Vec<usize> = Vec::new();
            let mut kinds = Vec::new();
            for beh in [Beh::Healer, Beh::Shielder, Beh::Summoner] {
                if behs.iter().any(|b| *b == beh) {
                    kinds.push(beh);
                }
            }
            if !kinds.is_empty() {
                let sk = kinds[(self.world.next() * kinds.len() as f64).floor() as usize];
                let pool: Vec<usize> = (0..len).filter(|&i| behs[i] == sk).collect();
                pick.push(pool[(self.world.next() * pool.len() as f64).floor() as usize]);
            }
            if from > 0.0 {
                let pool: Vec<usize> = (0..len)
                    .filter(|&i| !Self::plain_beh(behs[i]) && !Self::support_beh(behs[i]) && !pick.contains(&i))
                    .collect();
                if !pool.is_empty() {
                    pick.push(pool[(self.world.next() * pool.len() as f64).floor() as usize]);
                }
            }
            let mut rest: Vec<usize> = (0..len)
                .filter(|&i| !pick.contains(&i) && (from > 0.0 || Self::plain_beh(behs[i])))
                .collect();
            while pick.len() < 7 && !rest.is_empty() {
                let j = (self.world.next() * rest.len() as f64).floor() as usize;
                pick.push(rest.remove(j));
            }
            let mut best: Option<(usize, f64)> = None;
            for &i in &pick {
                if matches!(behs[i], Beh::Chase | Beh::Charger | Beh::Tank) && best.map_or(true, |(_, s)| spds[i] > s) {
                    best = Some((i, spds[i]));
                }
            }
            self.runner_ix[ti] = best.map(|(i, _)| i);
            self.roster[ti] = pick;
        }
    }

    fn sample_cast(&mut self) -> Option<Cand> {
        let t = self.t;
        let tiers = &self.data.tiers;
        let mut total = 0.0;
        let mut bag: [(usize, f64); 8] = [(0, 0.0); 8];
        let mut nb = 0;
        for (i, tier) in tiers.iter().enumerate() {
            if t >= tier.from && !self.roster[i].is_empty() {
                bag[nb] = (i, if t - tier.from > 260.0 { 3.0 } else { 10.0 });
                nb += 1;
            }
        }
        if nb == 0 {
            return None;
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
        let list = self.roster[tier].clone();
        let cands = &self.data.tiers[tier].cands;
        let mut idx = list[(self.world.next() * list.len() as f64).floor() as usize];
        if let Some(slot) = Self::support_ix(cands[idx].def.beh) {
            let full = self.support_full();
            if full[slot] {
                let rest: Vec<usize> = list
                    .iter()
                    .copied()
                    .filter(|&i| Self::support_ix(cands[i].def.beh).map(|s| full[s]).unwrap_or(false) == false)
                    .collect();
                if rest.is_empty() {
                    return None;
                }
                idx = rest[(self.world.next() * rest.len() as f64).floor() as usize];
            }
        }
        let mut c = cands[idx].clone();
        if self.runner_ix.get(tier).and_then(|o| *o) == Some(idx) {
            c.def.beh = Beh::Runner;
            c.def.spd = js_round(c.def.spd * 1.6);
            c.def.hp = js_round(c.def.hp * 0.7);
        }
        Some(c)
    }

    // spawner.js:82. Re-pick from the same tier when that support type is full.
    // None means the remainder was empty: the caller returns before spawn_n advances.
    fn sample_def(&mut self) -> Option<Cand> {
        if self.faith() && !self.roster.is_empty() {
            return self.sample_cast();
        }
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
        let mut idx = (self.world.next() * cands.len() as f64).floor() as usize;
        if let Some(slot) = Self::support_ix(cands[idx].def.beh) {
            let full = self.support_full();
            if full[slot] {
                let rest: Vec<usize> = (0..cands.len()).filter(|&i| Self::support_ix(cands[i].def.beh).map(|s| full[s]).unwrap_or(false) == false).collect();
                if rest.is_empty() {
                    return None;
                }
                idx = rest[(self.world.next() * rest.len() as f64).floor() as usize];
            }
        }
        let mut c = cands[idx].clone();
        if matches!(c.def.beh, Beh::Chase | Beh::Charger | Beh::Tank) && self.world.next() < 1.0 / 7.0 {
            c.def.beh = Beh::Runner;
            c.def.spd = js_round(c.def.spd * 1.6);
            c.def.hp = js_round(c.def.hp * 0.7);
        }
        Some(c)
    }

    fn roll_spawn(&mut self, angle: Option<f64>) {
        let Some(cand) = self.sample_def() else { return };
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
        // stats.js guard, after the position cos/sin. Parity does not use terrain, so these
        // two pows sit here even if a later terrain retry abandons the spawn.
        let g_phys = guard(self.math, cand.df);
        let g_spec = guard(self.math, cand.sd);
        let cat = if cand.sa > cand.pa { 2 } else { 1 };
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
            sand_safe: cand.sand_safe,
            snow_safe: cand.snow_safe,
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
            boss: false,
            legend: false,
            elite,
            lag_t: 0.0,
            judge: false,
            dps_acc: 0.0,
            g_phys,
            g_spec,
            cat,
            rd: 0.0,
            stun_t: 0.0,
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
                    let ramp = weather_ramp(w.elapsed, w.dur);
                    if self.faith() {
                        // weather.js:111-124. level() is the ramp. Never KOs the player. Enemies lose HP directly.
                        if ramp > 0.5 {
                            if !immune {
                                self.stats();
                                let d = jmax(1.0, self.st.max_hp * 0.012);
                                if self.pl.hp > d + 1.0 {
                                    self.pl.hp -= d;
                                }
                            }
                            let sand = w.kind == Wx::Sand;
                            for e in self.enemies.iter_mut() {
                                if e.hp <= 0.0 || e.boss {
                                    continue;
                                }
                                if if sand { e.sand_safe } else { e.snow_safe } {
                                    continue;
                                }
                                e.hp -= e.max * 0.02 + 1.0;
                            }
                        }
                    } else if !immune && ramp > 0.0 {
                        self.stats();
                        self.pl.hp -= 0.012 * self.st.max_hp;
                    }
                }
            }
        }
    }

    fn tick_buffs(&mut self) {
        for which in 0..2 {
            if self.opts.ext.rift && self.opts.ext.buffs != 0 && !self.bonded(100 + which as u8) {
                continue;
            }
            let (id, lvl) = if which == 0 {
                (self.atk_buff, self.state.sd)
            } else {
                (self.def_buff, self.state.hd)
            };
            if lvl == 0 {
                continue;
            }
            let inst = self.buff_level(id, lvl);
            let cd_mul = self.st.cd_mul;
            let dt = self.dt;
            let frozen = self.slot != 0;
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
            // Recast cooldown freezes on the inactive slot. The buff's own duration still ticks.
            if frozen {
                continue;
            }
            *cd -= dt;
            if *cd <= 0.0 {
                *stacks = jmin(inst.stacks, *stacks + 1.0);
                *time = inst.dur;
                *cd = inst.cd * cd_mul;
                self.stat_dirty = true;
                if self.opts.ext.item.lifeorb {
                    self.pl.hp = jmax(1.0, self.pl.hp - jmax(1.0, self.st.max_hp * 0.01));
                }
            }
        }
    }

    // ------------------------------------------------ enemies

    fn step_enemies(&mut self) {
        let faithful = self.faith();
        let snow_mul = if faithful { self.snow_mul() } else { 1.0 };
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
            // enemy.js update: recent boss damage decays before DoT. libm, not the traced pow.
            if e.boss && e.rd > 0.0 {
                e.rd *= libm::exp(-dt / 6.0);
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
                    // enemy.js pctHp (lines 42-43): above 60_000 the percent base grows with sqrt.
                    let base = if e.max <= 60000.0 { e.max } else { 60000.0 * (e.max / 60000.0).sqrt() };
                    hurt_dot(e, base * 0.012 * e.poison + 1.0);
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
            // enemy.js update: a stunned enemy stays put after its status ticks. No movement, knock decay,
            // contact, shot, jump or fuse, and combat.js resolve skips its touch damage too.
            if e.stun_t > 0.0 {
                e.stun_t -= dt;
                continue;
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
            // const spd = this.spd * (1 - this.slow) * terrain * weather.speedFor (enemy.js:279)
            let mut spd = e.spd * (1.0 - e.slow);
            if snow_mul < 1.0 && !e.snow_safe {
                spd *= snow_mul;
            }
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
                                    // enemy.js:274 hurt() rounds and hits the shield. Legends are skipped (enemy.js:270).
                                    if faithful {
                                        if !e.legend {
                                            raw_hurt(e, 6.0 + e.max * 0.04, 0.0, 0.0, 0.0);
                                        }
                                    } else {
                                        e.hp -= 6.0 + e.max * 0.04;
                                    }
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
                    let (dmg, ty, cat) = (e.dmg, e.ty0, e.cat);
                    let nx = gx / or(gap, 1.0);
                    let ny = gy / or(gap, 1.0);
                    e.kx += nx * 150.0;
                    e.ky += ny * 150.0;
                    self.hurt(dmg, ty, cat);
                    self.helmet_on(i);
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
                    cat: e.cat,
                    pure: false,
                    pct: f64::NAN,
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
                    cat: e.cat,
                    pure: false,
                    pct: f64::NAN,
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
                    let (ex, ey, shot, ty, ecat) = (e.x, e.y, e.shot, e.ty0, e.cat);
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
                                cat: ecat,
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
                                cat: ecat,
                                pure: false,
                                pct: f64::NAN,
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
                                    cat: ecat,
                                    pure: false,
                                    pct: f64::NAN,
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
                let (dmg, ty, cat) = (e.dmg, e.ty0, e.cat);
                let nx = gx / or(gap, 1.0);
                let ny = gy / or(gap, 1.0);
                e.kx += nx * 150.0;
                e.ky += ny * 150.0;
                self.hurt(dmg, ty, cat);
                self.helmet_on(i);
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
                let (dmg, ty, cat) = (s.dmg, s.ty, s.cat);
                self.hurt(dmg, ty, cat);
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
            let (dmg, ty, cat, pure, pct) = (h.dmg, h.ty, h.cat, h.pure, h.pct);
            if inside {
                if pure {
                    // hazards.js: invuln is cleared, then hurt(..., pure=true).
                    self.pl.inv = 0.0;
                    let amt = if pct.is_finite() { dmg.max(self.st.max_hp * pct) } else { dmg };
                    self.hurt_pure(amt);
                } else {
                    self.hurt(dmg, ty, cat);
                }
            }
            self.hazards.remove(i);
        }
    }
}

/// One closed run. Same contract as runMatch in sim/match.js (no presets,
/// spawning and weather always on, recordHits/trace not supported).
/// Everything `run_match` sets up before its first step. Split out so a test can build a match and
/// drive single systems (cast, fields, shots, enemies) against scripted enemies.
fn init_match<'a, M: MathFns>(
    math: &'a M,
    data: &'a Data,
    tables: &'a Tables,
    mon: &'a Mon,
    start: usize,
    opts: &'a Opts,
) -> Match<'a, M> {
    let dt = DT;
    let knock_fade = math.pow(0.0015, dt);
    // stats.js guard of the player's defenses, before xp_for, so the parity pow order matches match.js.
    let g_phys = guard(math, mon.df);
    let g_spec = guard(math, mon.sd);
    let start_move = &data.moves[start];
    let mut world = Rng::new(opts.seed);
    let card_roll = Rng::new(opts.seed.wrapping_add(0xA5A5));
    // spawner.js:25. The first surge is at 32s. The roll is still consumed so the parity
    // stream is unchanged; only the faithful path uses 32.
    let rolled_surge = world.next() * 20.0 + 10.0;
    let faithful = opts.status || opts.ext.xkinds;
    let surge = if faithful { 32.0 } else { rolled_surge };
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
        state: State { move_lvl: 1, sd: (opts.ext.buffs & 1) as usize, hd: ((opts.ext.buffs >> 1) & 1) as usize, ..State::default() },
        has_sd: if opts.ext.buffs > 0 { opts.ext.buffs & 1 != 0 } else { mon.pool.contains(&data.swords_dance) },
        has_hd: if opts.ext.buffs > 0 { opts.ext.buffs & 2 != 0 } else { mon.pool.contains(&data.harden) },
        def_buff: if opts.ext.agi { data.agility } else { data.harden },
        atk_buff: if opts.ext.np { data.nasty_plot } else if opts.ext.dd { data.dragon_dance } else { data.swords_dance },
        comps: opts.ext.companions.iter().map(|&c| (c, 1usize, 0.0)).collect(),
        // Seeded false. player.js applies the melee cut to activeGroup() only, and a companion
        // is not in that group until the rift bond lands. Evolving a bonded move into melee sets it.
        any_melee: false,
        fields: Vec::new(),
        fx: Rng::new(opts.seed.wrapping_mul(2654435761).wrapping_add(0x51F7)),
        bonds: 0,
        bond_order: {
            let mut o: Vec<u8> = (0..opts.ext.companions.len() as u8).collect();
            if opts.ext.buffs & 1 != 0 {
                o.push(100);
            }
            if opts.ext.buffs & 2 != 0 {
                o.push(101);
            }
            o.truncate(3);
            o
        },
        rift_check: 30.0,
        rift_misses: 0.0,
        rift_ttl: -1.0,
        rift_walk: -1.0,
        arena_phase: 0,
        arena_t: 0.0,
        arena_end: 0.0,
        arena_down: 0.0,
        arena_back: (0.0, 0.0),
        arena_dex: 0,
        stash: Vec::new(),
        beaten: Vec::new(),
        boss_picks: Vec::new(),
        boss_idx: 0,
        patch_at: (f64::NAN, f64::NAN, 9.0),
        status_ignored: move_has_status(start_move, opts.status, opts.ext.xkinds),
        // sprites.js:151 playerRadius = min(18, bodyRadius(dex, playerScale)).
        // Parity keeps min(18, exported body radius); the faithful path uses the shrunk radius.
        pl: Player {
            x: 0.0,
            y: 0.0,
            r: if faithful { crate::radii::player_radius(mon.dex).unwrap_or(mon.r.min(18.0)) } else { mon.r.min(18.0) },
            hp: mon.hp,
            inv: 0.0,
            dirx: 1.0,
            diry: 0.0,
            react: 0.0,
            aim: 0.0,
        },
        enemies: Vec::with_capacity(72),
        shots: Vec::with_capacity(96),
        booms: Vec::new(),
        orbs: Vec::new(),
        extras: Vec::new(),
        side_orbit: None,
        side_orbs: Vec::new(),
        e_shots: Vec::new(),
        hazards: Vec::new(),
        spawn_n: 0,
        acc: 0.0,
        surge,
        kills: 0,
        bosses: 0,
        picked: 0.0,
        dealt: 0.0,
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
            patk: 1.0,
            satk: 1.0,
        },
        stat_dirty: true,
        stat_snow: 1.0,
        angles: Vec::with_capacity(8),
        sep: Sep::default(),
        shot_soa: ShotSoa::default(),
        near_buf: Vec::with_capacity(72),
        terrain: opts.terrain.then(|| {
            Box::new(Terr { world: World::new((opts.seed as i32).wrapping_mul(7919).wrapping_add(1)), path: Path::new() })
        }),
        lava_t: 0.0,
        slot: 0,
        alt_cd: 0.0,
        comp_evo: vec![false; opts.ext.companions.len()],
        regen_n: 0.0,
        regen_amt: 0.0,
        regen_t: 0.0,
        power: 255,
        power_t: 0.0,
        altar_used: Vec::new(),
        bell: 0.0,
        sash_t: -1.0e9,
        crit_rng: RefCell::new(Rng::new(opts.seed.wrapping_add(0xC217))),
        roster: Vec::new(),
        runner_ix: Vec::new(),
        pickups: Vec::new(),
        pvx: 0.0,
        pvy: 0.0,
        ppx: 0.0,
        ppy: 0.0,
        p_seen: false,
        xp_n: 0,
        heal_n: 0,
        g_phys,
        g_spec,
        learned: Vec::new(),
        judging: false,
        jd_t: 0.0,
        jd_boss_t: 0.0,
        jd_n: 0,
        jd_base: 0.0,
        jd_cx: 0.0,
        jd_cy: 0.0,
        jd_q: Vec::new(),
        arceus_x: 0.0,
        arceus_y: 0.0,
        arceus_r: 0.0,
        arceus_cd: 0.0,
        arceus_touch: 0.0,
        arceus_cast: -1.0,
        arceus_wind: 0.0,
        arceus_kind: 0,
        dps_samples: Vec::new(),
        dps_clock: 0.0,
    };
    // A bond move the species cannot be offered (not in poolFor) must not block the queue.
    // The starter is already known.
    m.learned = m.bond_order.iter().map(|&slot| {
        let ix = if slot == 100 {
            m.atk_buff
        } else if slot == 101 {
            m.def_buff
        } else {
            m.comps[slot as usize].0
        };
        ix == mon.start || !mon.pool.contains(&ix)
    }).collect();
    m.need = xp_for(math, 1);
    m.roll_roster();
    if !opts.ext.locks.is_empty() {
        m.apply_locks();
    }
    if opts.ext.bosses {
        m.roll_bosses();
    }
    m
}

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
    let mut m = init_match(math, data, tables, mon, start, opts);

    while m.t < max_time && (m.pl.hp > 0.0 || m.arena_phase != 0) {
        let step = jmin(dt, max_time - m.t);
        m.note_vel(step);
        let prev_t = m.t;
        m.t += step;
        if opts.ext.rift && prev_t < 1800.0 && m.t >= 1800.0 {
            m.stat_dirty = true;
        }
        m.tick_weather();
        m.stats();
        if opts.ext.rift && !m.judging {
            m.dps_clock += step;
            if m.dps_clock >= 1.0 {
                if m.t > 1770.0 {
                    let best = m.enemies.iter().map(|e| e.dps_acc).fold(0.0, f64::max);
                    m.dps_samples.push(best / m.dps_clock);
                    if m.dps_samples.len() > 30 {
                        m.dps_samples.remove(0);
                    }
                }
                for e in &mut m.enemies {
                    e.dps_acc = 0.0;
                }
                m.dps_clock = 0.0;
            }
        }
        if m.regen_t > 0.0 {
            m.regen_t -= step;
            if m.regen_t <= 0.0 {
                m.regen_n = 0.0;
                m.stat_dirty = true;
                m.stats();
            }
        }
        if m.power_t > 0.0 {
            m.power_t -= step;
            if m.power_t <= 0.0 {
                m.stat_dirty = true;
                m.stats();
            }
        }
        // player.js:327 Shell Bell, cap 4 per second.
        if m.bell > 0.0 && m.pl.hp > 0.0 {
            let h = jmin(m.bell, 4.0 * step);
            m.bell -= h;
            m.pl.hp = jmin(m.st.max_hp, m.pl.hp + h);
        }
        if m.pl.hp > 0.0 && m.st.regen != 0.0 {
            m.pl.hp = jmin(m.st.max_hp, m.pl.hp + m.st.regen * step);
        }
        if m.pl.inv > 0.0 {
            m.pl.inv -= step;
        }
        let mut boss_alive = false;
        if m.arena_phase == 0 && !m.judging {
            if opts.ext.bosses {
                if m.boss_idx < BOSS_SLOTS.len() && m.t >= BOSS_SLOTS[m.boss_idx].0 && m.spawn_boss() {
                    m.boss_idx += 1;
                }
                boss_alive = m.enemies.iter().any(|e| e.boss && !e.legend && e.hp > 0.0);
            }
            m.acc += spawn_rate(math, m.t) * step * if boss_alive { 0.25 } else { 1.0 };
            let mut n = m.acc.floor();
            m.acc -= n;
            while n > 0.0 {
                n -= 1.0;
                m.roll_spawn(None);
            }
            if !boss_alive {
                m.surge -= step;
            }
        }
        if m.arena_phase == 0 && !m.judging && m.surge <= 0.0 {
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
        // End phase of an arena (won/lost) waits out endT with the map paused. A dead player only
        // reaches this loop while the arena is still going (rift.js: death there does not end the run).
        if m.pl.hp > 0.0 && m.arena_phase < 2 {
            m.decide();
            let mut pspd = m.st.spd;
            if m.arena_phase == 0 && !m.judging {
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
                                        m.player_lava();
                                    }
                                }
                            }
                        }
                    }
                }
            }
            m.pl.x += m.pl.dirx * pspd * step;
            m.pl.y += m.pl.diry * pspd * step;
            if m.arena_phase == 0 && !m.judging {
                if let Some(t) = &mut m.terrain {
                    t.world.collide(&mut m.pl.x, &mut m.pl.y, m.pl.r);
                }
                m.tick_altars();
            }
            m.tick_buffs();
            m.stats();
            m.maybe_swap();
            m.stats();
            if m.slot == 0 {
                m.atk_cd -= step;
                if m.atk_cd <= 0.0 {
                    m.atk_cd = if m.cast() { m.cooled(m.st.mv.cd) } else { 0.05 };
                }
                if !m.comps.is_empty() {
                    m.cast_comps();
                }
                if !m.extras.is_empty() {
                    m.cast_extras();
                }
            } else {
                m.alt_cd -= step;
                if m.alt_cd <= 0.0 {
                    m.alt_cd = if m.cast() { m.cooled(m.st.mv.cd) } else { 0.05 };
                }
            }
            if !m.fields.is_empty() {
                m.step_fields();
            }
            m.step_shots();
            m.reap();
            m.stats();
            m.step_enemies();
            m.reap();
            if m.faith() {
                m.tick_stragglers();
                m.tick_pickups();
            }
        }
        if m.judging {
            m.tick_judgment();
        } else if m.arena_phase != 0 {
            m.tick_arena();
        } else if opts.ext.rift {
            if m.t >= 1800.0 {
                m.begin_judgment();
            } else {
                let alive = opts.ext.bosses && m.enemies.iter().any(|e| e.boss && !e.legend && e.hp > 0.0);
                m.tick_rift(alive);
            }
        }
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
    let time = if capped { max_time } else { m.t };
    RunResult {
        time,
        kills: m.kills,
        bosses: m.bosses,
        coins: run_coins(time, m.kills, m.bosses, m.picked),
        level: m.level,
        capped,
        status_ignored: m.status_ignored,
        hp: m.pl.hp,
        max_hp: m.st.max_hp,
        hp_frac: if capped { m.pl.hp / m.st.max_hp } else { 0.0 },
        dealt: m.dealt,
    }
}

#[cfg(test)]
mod coin_tests {
    use super::run_coins;

    #[test]
    fn coins_follow_game_js_end_run() {
        // 100.4 s, 10 kills, 1 boss, 50 picked: floor(100.4/5)=20, floor(2.5)=2, 80, +50.
        assert_eq!(run_coins(100.4, 10, 1, 50.0), 152.0);
        // A rift legend is a boss and also drops the legend shower: 50 + 80 picked.
        assert_eq!(run_coins(180.0, 40, 1, 130.0), 36.0 + 10.0 + 80.0 + 130.0);
    }
}

#[cfg(test)]
mod hex_tests {
    use super::hex_multiplier;

    #[test]
    fn hex_is_1_7_only_while_burn_poison_or_slow_is_up() {
        assert_eq!(hex_multiplier(1.7, 0.0, 0.0, 0.0), 1.0);
        assert_eq!(hex_multiplier(1.7, 1.0, 0.0, 0.0), 1.7);
        assert_eq!(hex_multiplier(1.7, 0.0, 2.0, 0.0), 1.7);
        assert_eq!(hex_multiplier(1.7, 0.0, 0.0, 0.4), 1.7);
        assert_eq!(hex_multiplier(f64::NAN, 1.0, 0.0, 0.0), 1.0);
        // A leftover timer with factor 0 does not count (combat.js checks cur.slow).
        assert_eq!(hex_multiplier(1.7, 0.0, 0.0, 0.0), 1.0);
    }
}

#[cfg(test)]
mod judgment_tests {
    use super::{cap_spd, judgment_chase_k, judgment_touch_pct};

    #[test]
    fn cap_touch_and_chase_match_judgment_js() {
        assert_eq!(cap_spd(130.0), 130.0);
        assert_eq!(cap_spd(100.0), 100.0);
        assert_eq!(cap_spd(290.0), 170.0);
        assert!((judgment_touch_pct(0.0) - 0.4).abs() < 1e-12);
        assert!((judgment_touch_pct(420.0) - 0.4).abs() < 1e-12);
        assert!((judgment_touch_pct(600.0) - 1.0).abs() < 1e-12);
        assert!((judgment_touch_pct(900.0) - 1.0).abs() < 1e-12);
        assert!((judgment_chase_k(0.0) - 0.74).abs() < 1e-12);
        // 35 s: min(1.22, 0.74+0.455) = 1.195, still under the 300 s ramp.
        assert!((judgment_chase_k(35.0) - 1.195).abs() < 1e-12);
    }
}