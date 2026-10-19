//! Map terrain, ported from the game (repo/js/world/world.js, systems/pathing.js).
//!
//! Only used with `--terrain`; the default engine stays bit-exact with sim/match.js.
//! Arena (rift) terrain, non-solid props (grass, springs, traps) and the ice
//! slide are not modelled.

use std::collections::HashMap;
use std::hash::{BuildHasherDefault, Hasher};
use std::sync::{Arc, OnceLock, RwLock};

pub const TS: f64 = 32.0;
const N: i32 = 16;
pub const FLOOR: u8 = 0;
pub const WALL: u8 = 1;
pub const LIQUID: u8 = 2;

/// util.js hash(): 32-bit Math.imul arithmetic. enemies.js behaviorOf calls hash(dex, 7, 11).
pub(crate) fn js_hash(x: i32, y: i32, seed: i32) -> f64 {
    hash(x, y, seed)
}

/// util.js hash(): 32-bit Math.imul arithmetic.
fn hash(x: i32, y: i32, seed: i32) -> f64 {
    let mut h = x.wrapping_mul(374761393) ^ y.wrapping_mul(668265263) ^ seed.wrapping_mul(2246822519u32 as i32);
    h = (h ^ ((h as u32 >> 13) as i32)).wrapping_mul(1274126177);
    h ^= (h as u32 >> 16) as i32;
    (h as u32) as f64 / 4294967296.0
}

fn vnoise(x: f64, y: f64, s: i32) -> f64 {
    let xi = x.floor();
    let yi = y.floor();
    let xf = x - xi;
    let yf = y - yi;
    let u = xf * xf * (3.0 - 2.0 * xf);
    let v = yf * yf * (3.0 - 2.0 * yf);
    let (xi, yi) = (xi as i32, yi as i32);
    let a = hash(xi, yi, s);
    let b = hash(xi + 1, yi, s);
    let c = hash(xi, yi + 1, s);
    let d = hash(xi + 1, yi + 1, s);
    (a + (b - a) * u) * (1.0 - v) + (c + (d - c) * u) * v
}

fn fbm(x: f64, y: f64, s: i32) -> f64 {
    vnoise(x, y, s) * 0.65 + vnoise(x * 2.13 + 17.0, y * 2.13 - 9.0, s + 1) * 0.35
}

fn terrain_raw(tx: i32, ty: i32, seed: i32) -> u8 {
    let (fx, fy) = (tx as f64, ty as f64);
    let d = fx.hypot(fy);
    if d < 9.0 {
        return FLOOR;
    }
    let ramp = ((d - 9.0) / 8.0).clamp(0.0, 1.0);
    if fbm(fx / 13.0, fy / 13.0, seed.wrapping_add(101)) < 0.04 + 0.23 * ramp {
        return LIQUID;
    }
    if fbm(fx / 8.0, fy / 8.0, seed.wrapping_add(202)) > 1.0 - 0.27 * ramp {
        return WALL;
    }
    FLOOR
}

#[derive(Clone, Copy)]
pub struct Prop {
    pub x: f64,
    pub y: f64,
    pub r: f64,
    /// INFINITY for indestructible props
    pub hp: f64,
    pub solid: bool,
}

/// Generated chunk, shared by every match on the same map seed.
struct Base {
    terr: [u8; (N * N) as usize],
    /// solid prop per tile (index into `props`), -1 if none
    prop_at: [i16; (N * N) as usize],
    props: Vec<Prop>,
}

/// A match's view of a chunk: the shared base plus its own prop damage.
struct Chunk {
    base: Arc<Base>,
    /// per-prop hp, allocated on first damage
    hp: Vec<f64>,
}

impl Chunk {
    fn solid(&self, ix: usize) -> bool {
        self.base.props[ix].solid && (self.hp.is_empty() || self.hp[ix] > 0.0)
    }
}

type ChunkKey = (i32, i32, i32);
static SHARED: OnceLock<RwLock<HashMap<ChunkKey, Arc<Base>, BuildHasherDefault<KeyHasher>>>> = OnceLock::new();

fn shared_chunk(seed: i32, cx: i32, cy: i32) -> Arc<Base> {
    let map = SHARED.get_or_init(|| RwLock::new(HashMap::default()));
    if let Some(b) = map.read().unwrap().get(&(seed, cx, cy)) {
        return b.clone();
    }
    let b = Arc::new(gen_chunk(seed, cx, cy));
    map.write().unwrap().entry((seed, cx, cy)).or_insert(b).clone()
}

fn gen_chunk(seed: i32, cx: i32, cy: i32) -> Base {
    // terrain with a one-tile border, so placeProps' 3×3 "open" test needs no extra noise
    const B: i32 = N + 2;
    let mut ring = [FLOOR; (B * B) as usize];
    for j in 0..B {
        for i in 0..B {
            ring[(j * B + i) as usize] = terrain_raw(cx * N + i - 1, cy * N + j - 1, seed);
        }
    }
    let mut c = Base { terr: [FLOOR; (N * N) as usize], prop_at: [-1; (N * N) as usize], props: Vec::new() };
    for j in 0..N {
        for i in 0..N {
            c.terr[(j * N + i) as usize] = ring[((j + 1) * B + i + 1) as usize];
        }
    }
    // placeProps (open-world branch). Only solid props matter to the sim.
    for j in 0..N {
        for i in 0..N {
            if c.terr[(j * N + i) as usize] != FLOOR {
                continue;
            }
            let (tx, ty) = (cx * N + i, cy * N + j);
            let d0 = (tx as f64).hypot(ty as f64);
            if d0 < 7.0 {
                continue;
            }
            let open = (0..3).all(|b| (0..3).all(|a| ring[((j + b) * B + i + a) as usize] == FLOOR));
            let h = hash(tx, ty, seed.wrapping_add(404));
            let grove = fbm(tx as f64 / 10.0, ty as f64 / 10.0, seed.wrapping_add(505)) > 0.6;
            let hs = hash(tx, ty, seed.wrapping_add(909));
            // (r, hp): tree 13/inf, rock 12/34, chest 12/22, altar 9/inf, bigchest 14/inf
            let prop = if open && d0 > 12.0 && hs < 0.0032 {
                if hs < 0.0004 {
                    Some((9.0, f64::INFINITY))
                } else if hs < 0.0008 {
                    None // spring
                } else if hs < 0.0011 {
                    Some((14.0, f64::INFINITY))
                } else {
                    None // trap
                }
            } else if open && h < (if grove { 0.07 } else { 0.006 }) {
                Some((13.0, f64::INFINITY))
            } else if open && h > 0.992 {
                Some((12.0, 34.0))
            } else if open && h > 0.985 && h <= 0.992 && hash(tx, ty, seed.wrapping_add(606)) < 0.07 {
                Some((12.0, 22.0))
            } else {
                None
            };
            if let Some((r, hp)) = prop {
                c.prop_at[(j * N + i) as usize] = c.props.len() as i16;
                c.props.push(Prop { x: tx as f64 * TS + TS / 2.0, y: ty as f64 * TS + TS - 4.0, r, hp, solid: true });
            }
        }
    }
    c
}

#[derive(Default)]
struct KeyHasher(u64);
impl Hasher for KeyHasher {
    fn finish(&self) -> u64 {
        self.0
    }
    fn write(&mut self, _: &[u8]) {
        unreachable!()
    }
    fn write_i32(&mut self, v: i32) {
        self.0 = (self.0.rotate_left(32) ^ v as u32 as u64).wrapping_mul(0x9E37_79B9_7F4A_7C15);
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Liquid {
    Water,
    Lava,
}

#[derive(Clone, Copy)]
pub enum Block {
    Wall,
    Prop { chunk: u32, ix: u16, destructible: bool },
}

pub struct World {
    seed: i32,
    chunks: Vec<Chunk>,
    index: HashMap<(i32, i32), u32, BuildHasherDefault<KeyHasher>>,
    /// direct-mapped cache in front of `index`
    recent: [(i32, i32, u32); 64],
    pub liquid: Liquid,
    /// bumped whenever a prop breaks (invalidates path fields)
    version: u32,
}

impl World {
    pub fn new(seed: i32) -> World {
        let mut w = World { seed, chunks: Vec::new(), index: HashMap::default(), recent: [(i32::MIN, 0, 0); 64], liquid: Liquid::Water, version: 0 };
        w.chunk(0, 0);
        w
    }

    #[inline(always)]
    fn chunk(&mut self, cx: i32, cy: i32) -> u32 {
        let slot = ((cx & 7) * 8 + (cy & 7)) as usize;
        let r = self.recent[slot];
        if r.0 == cx && r.1 == cy {
            return r.2;
        }
        self.chunk_miss(cx, cy, slot)
    }

    #[cold]
    #[inline(never)]
    fn chunk_miss(&mut self, cx: i32, cy: i32, slot: usize) -> u32 {
        let ix = match self.index.get(&(cx, cy)) {
            Some(&ix) => ix,
            None => {
                let ix = self.chunks.len() as u32;
                self.chunks.push(Chunk { base: shared_chunk(self.seed, cx, cy), hp: Vec::new() });
                self.index.insert((cx, cy), ix);
                ix
            }
        };
        self.recent[slot] = (cx, cy, ix);
        ix
    }

    /// Terrain and solid prop of one tile, with a single chunk lookup.
    #[inline(always)]
    fn tile(&mut self, tx: i32, ty: i32) -> (u8, Option<Prop>) {
        let (cx, cy) = (tx.div_euclid(N), ty.div_euclid(N));
        let ix = self.chunk(cx, cy) as usize;
        let c = &self.chunks[ix];
        let k = ((ty - cy * N) * N + (tx - cx * N)) as usize;
        let p = c.base.prop_at[k];
        let prop = if p >= 0 && c.solid(p as usize) { Some(c.base.props[p as usize]) } else { None };
        (c.base.terr[k], prop)
    }

    pub fn terrain_at(&mut self, tx: i32, ty: i32) -> u8 {
        let (cx, cy) = (tx.div_euclid(N), ty.div_euclid(N));
        let c = self.chunk(cx, cy);
        self.chunks[c as usize].base.terr[((ty - cy * N) * N + (tx - cx * N)) as usize]
    }

    fn prop_ref(&mut self, tx: i32, ty: i32) -> Option<(u32, u16)> {
        let (cx, cy) = (tx.div_euclid(N), ty.div_euclid(N));
        let c = self.chunk(cx, cy);
        let ix = self.chunks[c as usize].base.prop_at[((ty - cy * N) * N + (tx - cx * N)) as usize];
        if ix < 0 || !self.chunks[c as usize].solid(ix as usize) {
            return None;
        }
        Some((c, ix as u16))
    }

    pub fn solid_prop(&mut self, tx: i32, ty: i32) -> Option<Prop> {
        self.prop_ref(tx, ty).map(|(c, ix)| self.chunks[c as usize].base.props[ix as usize])
    }

    /// An altar on this tile (world.js placeProps: r=9, hp inf, hs<0.0004). Kind is
    /// floor(hash(tx, ty, seed+910)*4) (world.js:154): 0 Furia, 1 Rayo, 2 Imán, 3 Prisa.
    pub fn altar_at(&mut self, tx: i32, ty: i32) -> Option<(f64, f64, f64, u8)> {
        let prop = self.solid_prop(tx, ty)?;
        if prop.r != 9.0 || !prop.hp.is_infinite() {
            return None;
        }
        let kind = (hash(tx, ty, self.seed.wrapping_add(910)) * 4.0).floor() as u8;
        Some((prop.x, prop.y, prop.r, kind))
    }

    pub fn is_liquid(&mut self, x: f64, y: f64) -> bool {
        self.terrain_at(tile_of(x), tile_of(y)) == LIQUID
    }

    /// pathing.js walkable() (water can be crossed, lava cannot) over a w×h tile
    /// window starting at (ox, oy), one chunk at a time, as one bit row per tile
    /// row (rows[0] and rows[h + 1] stay empty).
    fn fill_walkable(&mut self, ox: i32, oy: i32, w: i32, h: i32, rows: &mut [u64]) {
        rows.fill(0);
        let lava = self.liquid == Liquid::Lava;
        for cy in oy.div_euclid(N)..=(oy + h - 1).div_euclid(N) {
            for cx in ox.div_euclid(N)..=(ox + w - 1).div_euclid(N) {
                let ix = self.chunk(cx, cy) as usize;
                let c = &self.chunks[ix];
                let (x0, x1) = ((cx * N).max(ox), (cx * N + N).min(ox + w));
                let (y0, y1) = ((cy * N).max(oy), (cy * N + N).min(oy + h));
                for ty in y0..y1 {
                    for tx in x0..x1 {
                        let k = ((ty - cy * N) * N + (tx - cx * N)) as usize;
                        let t = c.base.terr[k];
                        let p = c.base.prop_at[k];
                        let open = t != WALL && !(t == LIQUID && lava) && (p < 0 || !c.solid(p as usize));
                        rows[(ty - oy + 1) as usize] |= (open as u64) << (tx - ox);
                    }
                }
            }
        }
    }

    /// Does a circle of radius r fit here? Exact circle tests (unlike the game's
    /// tile-box isFree), so the bot can slide along a wall it is touching.
    pub fn fits(&mut self, x: f64, y: f64, r: f64, avoid_liquid: bool) -> bool {
        let (t0x, t1x, t0y, t1y) = (tile_of(x - r), tile_of(x + r), tile_of(y - r), tile_of(y + r));
        for ty in t0y..=t1y {
            for tx in t0x..=t1x {
                let (t, prop) = self.tile(tx, ty);
                if t == WALL || (avoid_liquid && t == LIQUID) {
                    let (bx0, by0) = (tx as f64 * TS, ty as f64 * TS);
                    let qx = x.clamp(bx0, bx0 + TS);
                    let qy = y.clamp(by0, by0 + TS);
                    if (x - qx) * (x - qx) + (y - qy) * (y - qy) < r * r {
                        return false;
                    }
                }
                if let Some(p) = prop {
                    let min = r + p.r;
                    if (x - p.x) * (x - p.x) + (y - p.y) * (y - p.y) < min * min {
                        return false;
                    }
                }
            }
        }
        true
    }

    /// world.js isFree() (spawner uses it with r = 14). Liquid blocks.
    pub fn is_free(&mut self, x: f64, y: f64, r: f64) -> bool {
        self.is_free_ex(x, y, r, false)
    }

    /// world.js isFree(x, y, r, allowLiquid). Dash passes allowLiquid so it can cross water
    /// (systems/combat.js dash, the fourth argument `true`).
    pub fn is_free_ex(&mut self, x: f64, y: f64, r: f64, allow_liquid: bool) -> bool {
        let (t0x, t1x, t0y, t1y) = (tile_of(x - r), tile_of(x + r), tile_of(y - r), tile_of(y + r));
        for ty in t0y..=t1y {
            for tx in t0x..=t1x {
                let (t, prop) = self.tile(tx, ty);
                if t == WALL || (!allow_liquid && t != FLOOR) {
                    return false;
                }
                if let Some(p) = prop {
                    let min = r + p.r;
                    if (x - p.x) * (x - p.x) + (y - p.y) * (y - p.y) < min * min {
                        return false;
                    }
                }
            }
        }
        true
    }

    /// world.js collide(): push a circle out of walls and solid props.
    pub fn collide(&mut self, x: &mut f64, y: &mut f64, r: f64) -> bool {
        let mut hit = false;
        for _ in 0..2 {
            let (t0x, t1x, t0y, t1y) = (tile_of(*x - r), tile_of(*x + r), tile_of(*y - r), tile_of(*y + r));
            for ty in t0y..=t1y {
                for tx in t0x..=t1x {
                    let (t, prop) = self.tile(tx, ty);
                    if t == WALL {
                        let (bx0, by0) = (tx as f64 * TS, ty as f64 * TS);
                        let (bx1, by1) = (bx0 + TS, by0 + TS);
                        let qx = x.clamp(bx0, bx1);
                        let qy = y.clamp(by0, by1);
                        let (dx, dy) = (*x - qx, *y - qy);
                        let d2 = dx * dx + dy * dy;
                        if d2 < r * r {
                            hit = true;
                            if d2 > 1e-6 {
                                let d = d2.sqrt();
                                *x += dx / d * (r - d);
                                *y += dy / d * (r - d);
                            } else {
                                let (l, rr, u, b) = (*x - bx0, bx1 - *x, *y - by0, by1 - *y);
                                let m = l.min(rr).min(u).min(b);
                                if m == l {
                                    *x = bx0 - r;
                                } else if m == rr {
                                    *x = bx1 + r;
                                } else if m == u {
                                    *y = by0 - r;
                                } else {
                                    *y = by1 + r;
                                }
                            }
                        }
                    }
                    if let Some(p) = prop {
                        let (dx, dy) = (*x - p.x, *y - p.y);
                        let min = r + p.r;
                        let d2 = dx * dx + dy * dy;
                        if d2 < min * min {
                            hit = true;
                            let d = if d2 > 0.0 { d2.sqrt() } else { 0.01 };
                            *x = p.x + dx / d * min;
                            *y = p.y + dy / d * min;
                        }
                    }
                }
            }
        }
        hit
    }

    /// world.js isWall(): the tile under the point is a wall.
    pub fn is_wall(&mut self, x: f64, y: f64) -> bool {
        self.terrain_at(tile_of(x), tile_of(y)) == WALL
    }

    /// world.js projectileBlock()
    pub fn projectile_block(&mut self, x: f64, y: f64, r: f64) -> Option<Block> {
        let (tx, ty) = (tile_of(x), tile_of(y));
        if self.terrain_at(tx, ty) == WALL {
            return Some(Block::Wall);
        }
        for b in -1..=1 {
            for a in -1..=1 {
                if let Some((c, ix)) = self.prop_ref(tx + a, ty + b) {
                    let p = self.chunks[c as usize].base.props[ix as usize];
                    let min = r + p.r;
                    if (x - p.x) * (x - p.x) + (y - p.y) * (y - p.y) < min * min {
                        return Some(Block::Prop { chunk: c, ix, destructible: p.hp.is_finite() });
                    }
                }
            }
        }
        None
    }

    pub fn damage_prop(&mut self, chunk: u32, ix: u16, amount: f64) {
        let c = &mut self.chunks[chunk as usize];
        if c.hp.is_empty() {
            c.hp = c.base.props.iter().map(|p| p.hp).collect();
        }
        c.hp[ix as usize] -= amount;
        if c.hp[ix as usize] <= 0.0 {
            self.version += 1;
        }
    }
}

pub fn tile_of(v: f64) -> i32 {
    (v / TS).floor() as i32
}

const R: i32 = 28;
const PN: i32 = R * 2 + 1;
/// field arrays carry a one-cell closed border, so the BFS needs no bounds checks
const PW: i32 = PN + 2;

fn pix(x: i32, y: i32) -> usize {
    ((y + 1) * PW + x + 1) as usize
}
const UNSEEN: i16 = 0x7fff;
const D8: [(i32, i32); 8] = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)];
pub const PATH_EVERY: f64 = 0.35;
pub const LOS_EVERY: f64 = 0.2;

/// pathing.js: BFS distance field around the player.
pub struct Path {
    ox: i32,
    oy: i32,
    dist: Vec<i16>,
    /// walkable tiles, one bit row per tile row, padded with an empty row on each side
    ob: [u64; PW as usize],
    pub timer: f64,
    built: bool,
    /// (player tile, liquid, world version) of the last build
    key: (i32, i32, bool, u32),
}

impl Path {
    pub fn new() -> Path {
        let n = (PW * PW) as usize;
        Path { ox: 0, oy: 0, dist: vec![UNSEEN; n], ob: [0; PW as usize], timer: 0.0, built: false, key: (0, 0, false, u32::MAX) }
    }

    pub fn build(&mut self, world: &mut World, plx: f64, ply: f64) {
        let (px, py) = (tile_of(plx), tile_of(ply));
        let key = (px, py, world.liquid == Liquid::Lava, world.version);
        if self.built && key == self.key {
            return;
        }
        self.key = key;
        self.ox = px - R;
        self.oy = py - R;
        self.built = true;
        self.dist.fill(UNSEEN);
        world.fill_walkable(self.ox, self.oy, PN, PN, &mut self.ob);
        self.ob[(R + 1) as usize] |= 1 << R;
        self.dist[pix(R, R)] = 0;
        // Bit-parallel BFS: one u64 per row (bit i = column i). Distances are the
        // same as the game's queue BFS, which does not depend on visit order.
        const ROWS: usize = PW as usize;
        let ob = self.ob;
        let mut seen = [0u64; ROWS];
        let mut front = [0u64; ROWS];
        let mut next = [0u64; ROWS];
        let (mut lo, mut hi) = ((R + 1) as usize, (R + 1) as usize);
        front[lo] = 1 << R;
        seen[lo] = 1 << R;
        let mut d: i16 = 0;
        loop {
            d += 1;
            let (a, b) = (lo.saturating_sub(1).max(1), (hi + 1).min(PN as usize));
            let (mut nlo, mut nhi) = (usize::MAX, 0);
            for j in a..=b {
                let (up, me, dn) = (front[j - 1], front[j], front[j + 1]);
                let o = ob[j];
                let n = (me << 1 | me >> 1 | up | dn)
                    | ((up << 1) & ob[j - 1] & (o << 1))
                    | ((up >> 1) & ob[j - 1] & (o >> 1))
                    | ((dn << 1) & ob[j + 1] & (o << 1))
                    | ((dn >> 1) & ob[j + 1] & (o >> 1));
                let n = n & o & !seen[j];
                next[j] = n;
                if n != 0 {
                    nlo = nlo.min(j);
                    nhi = nhi.max(j);
                    seen[j] |= n;
                    let mut bits = n;
                    let base = j * ROWS + 1;
                    while bits != 0 {
                        self.dist[base + bits.trailing_zeros() as usize] = d;
                        bits &= bits - 1;
                    }
                }
            }
            for j in a..=b {
                front[j] = next[j];
                next[j] = 0;
            }
            if nlo == usize::MAX {
                break;
            }
            front[..a].fill(0);
            (lo, hi) = (nlo, nhi);
        }
    }

    /// pathing.js dirFor(). `los` is the enemy's cached line-of-sight state
    /// (checked at most every LOS_EVERY seconds).
    pub fn dir_for(&self, ex: f64, ey: f64, er: f64, plx: f64, ply: f64, now: f64, los: &mut (f64, bool)) -> Option<(f64, f64)> {
        if !self.built {
            return None;
        }
        let (tx, ty) = (tile_of(ex) - self.ox, tile_of(ey) - self.oy);
        if tx < 0 || ty < 0 || tx >= PN || ty >= PN {
            return None;
        }
        let here = self.dist[pix(tx, ty)];
        if here <= 1 || here == UNSEEN {
            return None;
        }
        if now - los.0 > LOS_EVERY {
            *los = (now, self.clear_line(ex, ey, plx, ply, er));
        }
        if los.1 {
            return None;
        }
        let (mut bx, mut by, mut best) = (tx, ty, here);
        for (k, &(ax, ay)) in D8.iter().enumerate() {
            let (x, y) = (tx + ax, ty + ay);
            if x < 0 || y < 0 || x >= PN || y >= PN {
                continue;
            }
            let v = self.dist[pix(x, y)];
            if v >= best {
                continue;
            }
            if k >= 4 && (!self.open(x, ty) || !self.open(tx, y)) {
                continue;
            }
            best = v;
            bx = x;
            by = y;
        }
        if bx == tx && by == ty {
            return None;
        }
        let mut gx = (self.ox + bx) as f64 * TS + TS / 2.0;
        let mut gy = (self.oy + by) as f64 * TS + TS / 2.0;
        if !self.clear_line(ex, ey, gx, gy, er) {
            gx = (self.ox + tx) as f64 * TS + TS / 2.0;
            gy = (self.oy + ty) as f64 * TS + TS / 2.0;
        }
        let (dx, dy) = (gx - ex, gy - ey);
        let l = dx.hypot(dy);
        if l == 0.0 {
            return Some((0.0, 0.0));
        }
        Some((dx / l, dy / l))
    }

    fn open(&self, x: i32, y: i32) -> bool {
        self.ob[(y + 1) as usize] >> x & 1 != 0
    }

    fn clear_line(&self, ax: f64, ay: f64, bx: f64, by: f64, r: f64) -> bool {
        let len = (bx - ax).hypot(by - ay);
        if len < 1.0 {
            return true;
        }
        let (ux, uy) = ((bx - ax) / len, (by - ay) / len);
        let w = (r * 0.9).min(TS * 0.45);
        let mut d = 0.0;
        while d <= len {
            let (cx, cy) = (ax + ux * d, ay + uy * d);
            for s in [-w, 0.0, w] {
                let x = tile_of(cx - uy * s) - self.ox;
                let y = tile_of(cy + ux * s) - self.oy;
                if x < 0 || y < 0 || x >= PN || y >= PN || !self.open(x, y) {
                    return false;
                }
            }
            d += TS * 0.4;
        }
        true
    }
}

/// Steering for the bot: the free direction closest to `want`, scored by
/// alignment plus how far the body can travel that way before touching a
/// wall, prop or (when `avoid_liquid`) liquid.
pub fn steer(world: &mut World, x: f64, y: f64, r: f64, want: (f64, f64), avoid_liquid: bool) -> (f64, f64) {
    const LOOK: f64 = 128.0;
    const STEP: f64 = 8.0;
    const CLEAR_W: f64 = 1.2;
    let base = want.1.atan2(want.0);
    let probe_r = r * 0.95;
    let mut best = (f64::NEG_INFINITY, want);
    for k in 0..24 {
        let off = ((k + 1) / 2) as f64 * (PI_12) * if k % 2 == 0 { 1.0 } else { -1.0 };
        let a = base + off;
        let (c, s) = (a.cos(), a.sin());
        let align = c * want.0 + s * want.1;
        if align + CLEAR_W <= best.0 {
            continue;
        }
        let mut clear = 0.0;
        let mut d = STEP;
        while d <= LOOK {
            if !world.fits(x + c * d, y + s * d, probe_r, avoid_liquid) {
                break;
            }
            clear = d;
            d += STEP;
        }
        let score = align + CLEAR_W * clear / LOOK;
        if score > best.0 {
            best = (score, (c, s));
        }
    }
    best.1
}

const PI_12: f64 = std::f64::consts::PI / 12.0;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hash_matches_js() {
        assert_eq!(hash(3, -7, 12345), 0.6179683092050254);
        assert_eq!(hash(-100, 250, 987654321 + 404), 0.9162725156638771);
        assert_eq!(hash(0, 0, 1), 0.4915040940977633);
    }
}

/// Tile grid (0 floor, 1 wall, 2 liquid, 3 solid prop) of a square around the start.
pub fn dump(seed: i32, half: i32) -> String {
    let mut w = World::new(seed);
    let mut out = String::new();
    for ty in -half..half {
        for tx in -half..half {
            let (t, p) = w.tile(tx, ty);
            out.push(char::from(b'0' + if p.is_some() { 3 } else { t }));
        }
        out.push('\n');
    }
    out
}

/// Map digest over a square of tiles, for checking against world.js.
pub fn digest(seed: i32, half: i32) -> String {
    let mut w = World::new(seed);
    let mut counts = [0u32; 3];
    let mut props = 0u32;
    let mut sum = 0u64;
    for ty in -half..half {
        for tx in -half..half {
            let t = w.terrain_at(tx, ty);
            counts[t as usize] += 1;
            sum = sum.wrapping_mul(31).wrapping_add(t as u64);
            if let Some(p) = w.solid_prop(tx, ty) {
                props += 1;
                sum = sum.wrapping_mul(31).wrapping_add(p.r as u64);
            }
        }
    }
    format!("floor={} wall={} liquid={} solid_props={} sum={}", counts[0], counts[1], counts[2], props, sum)
}
