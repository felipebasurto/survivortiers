//! The eight attack kinds PokéSurvivor added in 66610d9 (homing, bounce, charge, spin, quake, vortex,
//! shove, stun), cast on the fixed-group path (`Ext::xkinds`) like cone, meteor and the rest.
//! Source: js/systems/combat.js at 5a23d49 (`run`, `reach`, `chargeUp`, `spin`, `quake`, `vortex`,
//! `shove`, `stunZone`, `rebound`, `tickNewField`) and js/entities/enemy.js `applyStun`.
//!
//! The parity path never fires them (they are `Kind::Inert` there).

use super::*;

/// combat.js QSTEP: distance between two quake waves.
pub(super) const QSTEP: f64 = 34.0;
/// combat.js tickNewField: spin hits every 0.13 s.
const SPIN_EVERY: f64 = 0.13;
/// combat.js tickNewField: a quake wave every 0.07 s.
const QUAKE_EVERY: f64 = 0.07;
/// combat.js stunZone: the zone warns this long before it hits.
const STUN_DELAY: f64 = 0.45;
/// combat.js vortex: first blast after 0.15 s, then every 0.4 s.
const VORTEX_FIRST: f64 = 0.15;
const VORTEX_EVERY: f64 = 0.4;
/// combat.js vortex: at most this many per player.
const VORTEX_MAX: usize = 2;
/// combat.js tickNewField: a boss or judgment legend is pulled and stunned this fraction as hard.
const HEAVY: f64 = 0.25;
pub(super) const HEAVY_STUN: f64 = 0.35;
/// combat.js rebound: search radius from the enemy that was hit, and the life it gives back.
pub(super) const REBOUND_REACH: f64 = 220.0;
pub(super) const REBOUND_LIFE: f64 = 0.5;
/// projectile.js: a homing shot only locks onto something this close.
pub(super) const HOMING_LOCK: f64 = 340.0;

/// util.js damp(a, b, rate, dt).
pub fn damp(a: f64, b: f64, rate: f64, dt: f64) -> f64 {
    b + (a - b) * libm::exp(-rate * dt)
}

/// projectile.js:52: an orb's height is 0.7 of its orbit radius (an ellipse, not a circle).
pub(super) const ORBIT_Y: f64 = 0.7;

/// Where an orb sits at `angle` around the player (projectile.js orbit update).
pub(super) fn orb_point<M: MathFns>(math: &M, px: f64, py: f64, angle: f64, radius: f64) -> (f64, f64) {
    (px + math.cos(angle) * radius, py + math.sin(angle) * radius * ORBIT_Y)
}

/// combat.js boomerang: `spread = m.spread || 0.5`, and the fan is `spread * min(n, 3)` wide, so
/// blades past the third do not widen it (combat.js:233). Writes the blade angles into `out`.
pub(super) fn boom_angles(aim: f64, count: f64, spread: f64, out: &mut Vec<f64>) {
    out.clear();
    let n = or(count, 1.0).trunc().max(1.0) as usize;
    if n == 1 {
        out.push(aim);
        return;
    }
    let width = or(spread, 0.5) * n.min(3) as f64;
    for i in 0..n {
        out.push(aim + (i as f64 / (n - 1) as f64 - 0.5) * width);
    }
}

/// combat.js reach(m) for a kind that needs a target (TARGETED). `None` for kinds that fire without one.
pub(super) fn reach(mv: &MoveLvl) -> Option<f64> {
    Some(match mv.kind {
        Kind::Melee => mv.radius + 30.0,
        Kind::Beam => mv.radius + 20.0,
        Kind::Boomerang => mv.radius + 40.0,
        Kind::Projectile => 520.0,
        Kind::Nova | Kind::Orbit => return None,
        Kind::Inert => match mv.xk {
            1 => mv.speed * mv.life + 30.0,                      // cone
            2 => 340.0,                                          // meteor
            3 => 280.0,                                          // chain
            5 => mv.radius + 60.0,                               // dash
            9 | 10 => 520.0,                                     // homing, bounce: projectiles
            11 | 12 | 15 => mv.radius + 20.0,                    // charge, spin, shove
            13 => or(mv.count, 0.0).trunc() * QSTEP + mv.radius, // quake
            14 | 16 => 300.0,                                    // vortex, stun
            _ => return None,                                    // aura, mine, trail, turret
        },
    })
}

impl<'a, M: MathFns> Match<'a, M> {
    /// Cast of xk 9..=16. `false` when combat.js needsTarget would wait for a target (the caller retries in
    /// 0.05 s). The reach is `reach(m)`: spin, shove and charge radius + 20, quake count * 34 + radius,
    /// vortex and stun 300. Homing and bounce are projectiles: no gate, like `Kind::Projectile`.
    pub(super) fn cast_new(&mut self, mv: &'a MoveLvl, aim: f64) -> bool {
        let (px, py) = (self.pl.x, self.pl.y);
        let atk = self.atk_for(mv.cat, mv.ty);
        let count = or(mv.count, 1.0).floor().max(1.0);
        let near = nearest(&self.enemies, px, py).map(|i| (self.enemies[i].x, self.enemies[i].y, len(self.enemies[i].x - px, self.enemies[i].y - py)));
        let within = |reach: f64| near.filter(|n| n.2 <= reach);
        match mv.xk {
            // fireProjectiles with m.homing / m.bounce on the shot
            9 | 10 => {
                let mut angles = std::mem::take(&mut self.angles);
                fan_angles(aim, or(mv.count, 1.0), or(mv.spread, 0.0), &mut angles);
                for &a in &angles {
                    self.push_shot(a, mv);
                }
                self.angles = angles;
            }
            11 => {
                if within(mv.radius + 20.0).is_none() {
                    return false;
                }
                let at = if mv.charge.is_finite() && mv.charge > 0.0 { mv.charge } else { 0.75 };
                self.fields.push(Field { k: 11, x: px, y: py, t: 0.0, life: at, r: mv.radius, atk, tick: 0.0, mv, n: 0, i: 0, ca: 0.0, sa: 0.0 });
            }
            12 => {
                if within(mv.radius + 20.0).is_none() {
                    return false;
                }
                self.fields.push(Field { k: 12, x: px, y: py, t: 0.0, life: 0.0, r: mv.radius, atk, tick: 0.0, mv, n: count as u32, i: 0, ca: 0.0, sa: 0.0 });
            }
            13 => {
                if within(count * QSTEP + mv.radius).is_none() {
                    return false;
                }
                self.fields.push(Field {
                    k: 13,
                    x: px,
                    y: py,
                    t: 0.0,
                    life: 0.0,
                    r: mv.radius,
                    atk,
                    tick: 0.0,
                    mv,
                    n: count as u32,
                    i: 0,
                    ca: aim.cos(),
                    sa: aim.sin(),
                });
            }
            14 => {
                let Some((x, y, _)) = within(300.0) else { return false };
                let life = if mv.dur.is_finite() && mv.dur > 0.0 { mv.dur } else { 2.6 };
                self.fields.push(Field { k: 14, x, y, t: 0.0, life, r: mv.radius, atk, tick: VORTEX_FIRST, mv, n: 0, i: 0, ca: 0.0, sa: 0.0 });
                let mut extra = self.fields.iter().filter(|f| f.k == 14).count().saturating_sub(VORTEX_MAX);
                self.fields.retain(|f| {
                    if f.k == 14 && extra > 0 {
                        extra -= 1;
                        false
                    } else {
                        true
                    }
                });
            }
            15 => {
                if within(mv.radius + 20.0).is_none() {
                    return false;
                }
                let knock = if mv.knock.is_finite() && mv.knock > 0.0 { mv.knock } else { 300.0 };
                self.blast_ex(px, py, mv.radius, mv.dmg, atk, mv, knock, 0.0);
            }
            16 => {
                let Some((x, y, _)) = within(300.0) else { return false };
                self.fields.push(Field { k: 16, x, y, t: 0.0, life: STUN_DELAY, r: mv.radius, atk, tick: 0.0, mv, n: 0, i: 0, ca: 0.0, sa: 0.0 });
            }
            _ => {}
        }
        true
    }

    /// One frame of a charge, spin, quake, vortex or stun field (combat.js tickNewField). `true` removes it.
    /// `t` was already advanced by `step_fields`.
    pub(super) fn step_new_field(&mut self, i: usize) -> bool {
        let dt = self.dt;
        let (k, x, y, t, life, r, fatk, mv) = {
            let f = &self.fields[i];
            (f.k, f.x, f.y, f.t, f.life, f.r, f.atk, f.mv)
        };
        match k {
            // Hold still `charge` seconds, then the beam of combat.js beam() at the aim of that moment.
            11 => {
                if t < life {
                    return false;
                }
                self.charge_beam(mv);
                true
            }
            // Spin: every 0.13 s hit everything around the player, `count` times. Damage uses the live atkFor.
            // `tick` carries the remainder (the game's 60 fps frame hides the 1/20 s step; a plain reset
            // would stretch 0.13 s to 0.15 s). Only the first hit starts clean.
            12 => {
                self.fields[i].tick -= dt;
                if self.fields[i].tick > 0.0 {
                    return false;
                }
                // The game's field starts with `next: 0` and resets it, so the first hit carries no remainder.
                self.fields[i].tick = if self.fields[i].i == 0 { SPIN_EVERY } else { self.fields[i].tick + SPIN_EVERY };
                self.fields[i].i += 1;
                let atk = self.atk_for(mv.cat, mv.ty);
                let (px, py) = (self.pl.x, self.pl.y);
                self.blast_ex(px, py, r, mv.dmg, atk, mv, 40.0, 0.0);
                self.fields[i].n -= 1;
                self.fields[i].n == 0
            }
            // Quake: one blast per 0.07 s, each 34 px further along the aim of the cast; a wall ends it.
            13 => {
                self.fields[i].tick -= dt;
                let (ca, sa) = (self.fields[i].ca, self.fields[i].sa);
                let knock = or(mv.knock, 0.0);
                while self.fields[i].tick <= 0.0 && self.fields[i].i < self.fields[i].n {
                    self.fields[i].tick += QUAKE_EVERY;
                    self.fields[i].i += 1;
                    let step = self.fields[i].i as f64 * QSTEP;
                    let (wx, wy) = (x + ca * step, y + sa * step);
                    if let Some(tr) = &mut self.terrain {
                        if tr.world.is_wall(wx, wy) {
                            self.fields[i].i = self.fields[i].n;
                            break;
                        }
                    }
                    self.blast_ex(wx, wy, r, mv.dmg, fatk, mv, knock, 0.0);
                }
                self.fields[i].i >= self.fields[i].n
            }
            // Vortex: ends at `dur` (before it acts); drags everything within 1.4 r toward the centre, 0.25 as
            // hard on a boss or judgment legend; blasts at 0.15 s and then every 0.4 s.
            14 => {
                if t >= life {
                    return true;
                }
                let pull = if mv.pull.is_finite() && mv.pull > 0.0 { mv.pull } else { 140.0 };
                for e in self.enemies.iter_mut() {
                    if e.hp <= 0.0 || len(e.x - x, e.y - y) > r * 1.4 + e.r {
                        continue;
                    }
                    let (dx, dy) = (x - e.x, y - e.y);
                    let d = len(dx, dy);
                    if d < 4.0 {
                        continue;
                    }
                    let step = jmin(d, pull * dt * if e.boss || e.judge { HEAVY } else { 1.0 });
                    e.x += dx / d * step;
                    e.y += dy / d * step;
                }
                self.fields[i].tick -= dt;
                if self.fields[i].tick <= 0.0 {
                    self.fields[i].tick += VORTEX_EVERY;
                    self.blast_ex(x, y, r, mv.dmg, fatk, mv, or(mv.knock, 0.0), 0.0);
                }
                false
            }
            // Stun zone: after the 0.45 s warning, damage and a stun on everything inside.
            16 => {
                if t < life {
                    return false;
                }
                let stun = if mv.stun.is_finite() && mv.stun > 0.0 { mv.stun } else { 1.0 };
                self.blast_ex(x, y, r, mv.dmg, fatk, mv, 0.0, stun);
                true
            }
            _ => false,
        }
    }

    /// combat.js beam() for a charge move: the beam is cut at the first wall (8 px probes), then hits
    /// everything on it with the aim and attack of this frame.
    fn charge_beam(&mut self, mv: &'a MoveLvl) {
        let math = self.math;
        let (px, py) = (self.pl.x, self.pl.y);
        // The beam takes the aim of this frame (player.js sets pl.aim from the lead move each frame).
        let aim = match self.aim_target() {
            Some(i) => math.atan2(self.enemies[i].y - py, self.enemies[i].x - px),
            None => self.pl.aim,
        };
        self.pl.aim = aim;
        let (ca, sa) = (aim.cos(), aim.sin());
        let mut length = mv.radius;
        if let Some(tr) = &mut self.terrain {
            let mut d = 8.0;
            while d < mv.radius {
                if tr.world.is_wall(px + ca * d, py + sa * d) {
                    length = d;
                    break;
                }
                d += 8.0;
            }
        }
        let atk = self.atk_for(mv.cat, mv.ty);
        let st = self.status_of(mv);
        let faithful = self.faith();
        let chance = if faithful { self.opts.ext.crit } else { 0.0 };
        let mut dealt = 0.0;
        {
            let mut rng = self.crit_rng.borrow_mut();
            let weather = &self.weather;
            let tm = &self.data.tmult;
            for e in self.enemies.iter_mut() {
                if e.hp > 0.0 && in_beam(math, px, py, aim, length, mv.width, e.x, e.y, e.r) {
                    dealt += hit_one(faithful, e, mv.dmg, atk, mv.ty, tm, weather, st, 0.0, ca, sa, chance, &mut rng, mv.cat);
                }
            }
        }
        self.add_dealt(mv.ix, dealt);
    }
}
