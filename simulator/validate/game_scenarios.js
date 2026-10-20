/**
 * Runs the vendored PokéSurvivor combat.js and projectile.js (commit 5a23d49) on scripted scenes and checks
 * the behaviours that sim-rs/src/engine/kind_tests.rs asserts for the same scenes: spin, quake, vortex,
 * stun, shove, homing, bounce, drain and charge. The game's own modules run for real (util, types, stats,
 * moves, player.atkFor, projectile, combat); only rendering, the map and the enemy manager are stubbed.
 *
 *   node simulator/validate/game_scenarios.js
 *
 * Frame order is main.js's: Combat.tick, Projectiles.update, Combat.resolve, Combat.updateFields, enemies.
 */
"use strict";

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "../..");
const GAME = path.join(ROOT, "simulator/vendor/pokesurvivor-11fe868");

function sink() {
  const fn = () => undefined;
  return new Proxy(fn, { get: (_, k) => (k === Symbol.toPrimitive ? () => 0 : sink()), apply: () => undefined });
}

let enemies = [];

global.window = global;
global.G = {
  LIFT: 0,
  Icons: sink(),
  FX: sink(),
  Audio: sink(),
  Camera: { sees: () => true, kick() {} },
  Coop: { active: false, cast() {} },
  Weather: { mult: () => 1, speedFor: () => 1 },
  VFX: { forMove: () => new Proxy({}, { get: () => undefined }), spins: () => false, isDir: () => false, draw() {} },
  World: { propsInCircle: () => [], damageProp() {}, isWall: () => false, projectileBlock: () => null },
  EnemyMgr: {
    all: () => enemies,
    queryCircle: (x, y, r) => enemies.filter(e => !e.dead && Math.hypot(e.x - x, e.y - y) <= r + e.r),
  },
};

function load(rel) {
  (0, eval)(fs.readFileSync(path.join(GAME, rel), "utf8"));
}
for (const f of ["js/core/util.js", "js/data/types.js", "js/systems/stats.js", "js/data/moves.js", "js/entities/player.js", "js/entities/projectile.js", "js/systems/combat.js"]) load(f);

const HP = 1e9;

function enemy(types, x, y, opts = {}) {
  const e = {
    id: enemies.length + 1, types, x, y, r: 12, hp: HP, dead: false, boss: !!opts.boss, judge: false,
    mon: { df: 75, sd: 75 }, stunT: 0, touchCd: 99, knocked: 0, spd: opts.spd || 0, moved: 0,
    cy() { return this.y; },
    hurt(amount, _c, _dx, _dy, knock) {
      this.hp -= Math.max(1, Math.round(amount));
      if (!this.boss) this.knocked += knock || 0;
    },
    applyStun(s) { this.stunT = Math.max(this.stunT, s); },
    applyBurn() {}, applySlow() {}, applyPoison() {},
    update(dt, pl) {
      if (this.stunT > 0) { this.stunT -= dt; return; }
      if (!this.spd) return;
      const d = Math.hypot(pl.x - this.x, pl.y - this.y) || 1;
      this.x += (pl.x - this.x) / d * this.spd * dt;
      this.y += (pl.y - this.y) / d * this.spd * dt;
    },
  };
  enemies.push(e);
  return e;
}

function player(dexTypes, pa = 100, sa = 100) {
  return {
    x: 0, y: 0, r: 12, aim: 0, dead: false, hp: 100, maxHp: 100, cdMul: 1, manualAim: false, critChance: 0,
    dmgDealt: 0, target: null, atk: 100, buffs: { patk: { n: 0, amount: 0 }, satk: { n: 0, amount: 0 } },
    mon: { pa, sa, atk: Math.max(pa, sa), types: dexTypes },
    atkFor: G.Player.prototype.atkFor, monoType: G.Player.prototype.monoType,
    onDealt() {}, cast() {}, heal(h) { this.hp = Math.min(this.maxHp, this.hp + h); },
    activeGroup() { return this.moves; },
    moves: [],
  };
}

/** One scene: the player at the origin casting `moveId`; `foes` is filled by the caller. */
function scene(moveId, types, dt, build) {
  G.Combat.clearFields();
  G.Projectiles.clear();
  enemies = [];
  const pl = player(types);
  const m = G.Moves.instance(moveId, 1);
  m.t = 0;
  pl.moves = [m];
  const foes = build(pl);
  const log = [];
  let t = 0;
  const frame = () => {
    t += dt;
    const near = enemies.filter(e => !e.dead).sort((a, b) => Math.hypot(a.x, a.y) - Math.hypot(b.x, b.y))[0];
    pl.target = near || null;
    if (near) pl.aim = Math.atan2(near.y - pl.y, near.x - pl.x);
    G.Combat.tick(dt, pl, t);
    G.Projectiles.update(dt, pl, enemies);
    G.Combat.resolve(dt, pl, t);
    G.Combat.updateFields(dt);
    for (const e of enemies) e.update(dt, pl);
  };
  return { pl, m, foes, frame, time: () => t, log };
}

const fails = [];
function expect(label, got, want) {
  const same = Array.isArray(want) ? JSON.stringify(got) === JSON.stringify(want) : got === want;
  if (!same) fails.push(`${label}: game ${JSON.stringify(got)}, expected ${JSON.stringify(want)}`);
}
function near(label, got, want, tol) {
  if (!(Math.abs(got - want) <= tol)) fails.push(`${label}: game ${got}, expected ${want} +- ${tol}`);
}

const lost = e => HP - e.hp;

for (const dt of [0.05, 1 / 60]) {
  const tag = `dt=${dt.toFixed(4)}`;

  {
    const s = scene("rapid-spin", ["normal"], dt, () => [enemy(["ghost"], 20, 0)]);
    const hits = [];
    let seen = 0;
    const one = Math.round(9 * s.pl.atkFor(s.m) * G.Types.mult("normal", ["ghost"]));
    for (let i = 0; i < 0.9 / dt; i++) {
      s.frame();
      const l = lost(enemies[0]);
      if (l > seen) { hits.push(+s.time().toFixed(3)); seen = l; }
    }
    expect(`spin hit count ${tag}`, hits.length, 3);
    expect(`spin damage ${tag}`, seen, one * 3);
    expect(`spin first hit on the cast frame ${tag}`, hits[0] <= dt + 1e-3, true);
    if (dt === 0.05) expect("spin hit times at 0.05 s", hits, [0.05, 0.2, 0.35]);
    const gaps = hits.slice(1).map((t, i) => t - hits[i]);
    for (const g of gaps) near(`spin gap ${tag}`, g, 0.13, dt + 1e-9);
  }

  {
    const s = scene("magnitude", ["ground"], dt, () => [1, 2, 3, 4, 5, 6].map(k => enemy(["normal"], 34 * k, 0)));
    s.frame();
    s.m.t = 1e9;
    for (let i = 0; i < 1.5 / dt; i++) s.frame();
    const each = Math.round(18 * s.pl.atkFor(s.m) * G.Types.mult("ground", ["normal"]));
    expect(`quake hits per enemy ${tag}`, enemies.map(e => lost(e) / each), [2, 3, 3, 3, 3, 2]);
  }

  {
    const s = scene("whirlpool", ["water"], dt, () => [enemy(["normal"], 150, 0), enemy(["normal"], 150, 80), enemy(["normal"], 210, 0, { boss: true })]);
    s.frame();
    const [c, small, boss] = enemies;
    s.m.t = 1e9;
    const b0 = Math.hypot(boss.x - 150, boss.y), s0 = Math.hypot(small.x - 150, small.y - 0);
    const n = Math.round(0.3 / dt);
    for (let i = 0; i < n; i++) s.frame();
    const T = n * dt;
    near(`vortex boss pull ${tag}`, b0 - Math.hypot(boss.x - 150, boss.y), 150 * T * 0.25, 0.5);
    near(`vortex enemy pull ${tag}`, s0 - Math.hypot(small.x - 150, small.y), 150 * T, 0.5);
    expect(`vortex damaged the centre enemy ${tag}`, lost(c) > 0, true);
  }

  {
    const s = scene("thunder-wave", ["electric"], dt, () => [enemy(["normal"], 40, 0, { spd: 60 }), enemy(["normal"], 40, 30, { boss: true, spd: 60 })]);
    const [a, boss] = enemies;
    let at = 0;
    for (let i = 0; i < 2 / dt && !at; i++) {
      s.frame();
      if (a.stunT > 0) at = s.time();
    }
    near(`stun lands after the 0.45 s warning ${tag}`, at, 0.45, dt + 1e-9);
    near(`stun length ${tag}`, a.stunT, 1 - 0, dt + 1e-9);
    near(`boss stun length ${tag}`, boss.stunT, 0.35, dt + 1e-9);
    expect(`stun damage ${tag}`, lost(a) > 0 && lost(boss) > 0, true);
  }

  {
    const s = scene("extrasensory", ["psychic"], dt, () => [enemy(["normal"], 40, 0), enemy(["normal"], 40, 20, { boss: true })]);
    s.frame();
    s.m.t = 1e9;
    expect(`shove knocks the enemy ${tag}`, enemies[0].knocked, 320);
    expect(`shove does not knock a boss ${tag}`, enemies[1].knocked, 0);
    expect(`shove damages the boss ${tag}`, lost(enemies[1]) > 0, true);
  }

  {
    const run = dest => {
      const s = scene("air-slash", ["normal", "flying"], dt, () => [enemy(["normal"], 200, 0)]);
      s.frame();
      s.m.t = 1e9;
      enemies[0].x = dest[0];
      enemies[0].y = dest[1];
      for (let i = 0; i < 2 / dt; i++) s.frame();
      return lost(enemies[0]);
    };
    expect(`homing curves into a foe off the line ${tag}`, run([200, 110]) > 0, true);
    expect(`homing ignores a foe beyond 340 ${tag}`, run([0, -1500]), 0);
  }

  {
    const s = scene("seed-bomb", ["grass", "poison"], dt, () => [0, 120, 240, 400, 620].map(y => enemy(["normal"], 100, y)));
    s.frame();
    s.m.t = 1e9;
    for (let i = 0; i < 3 / dt; i++) s.frame();
    const each = Math.round(10 * s.pl.atkFor(s.m) * G.Types.mult("grass", ["normal"]));
    expect(`bounce chain ${tag}`, enemies.map(e => lost(e) / each), [1, 1, 1, 1, 0]);
  }

  {
    const s = scene("draining-kiss", ["fairy"], dt, () => [enemy(["normal"], 80, 0)]);
    s.pl.hp = 90;
    s.frame();
    s.m.t = 1e9;
    for (let i = 0; i < 2 / dt; i++) s.frame();
    expect(`drain heals one per hit ${tag}`, s.pl.hp, 91);
  }

  {
    const s = scene("hyper-beam", ["normal"], dt, () => [enemy(["normal"], 100, 0), enemy(["normal"], 100, 100)]);
    let first = 0;
    for (let i = 0; i < 1.2 / dt; i++) {
      s.frame();
      if (!first && lost(enemies[0]) > 0) { first = s.time(); s.m.t = 1e9; }
    }
    near(`charge fires after 0.75 s ${tag}`, first, 0.75, dt + 1e-9);
    expect(`charge beam damage ${tag}`, lost(enemies[0]), Math.round(58 * s.pl.atkFor(s.m) * G.Types.mult("normal", ["normal"])));
    expect(`charge beam misses off the line ${tag}`, lost(enemies[1]), 0);
  }
}

if (fails.length) {
  console.error(fails.join("\n"));
  process.exit(1);
}
console.log("game scenarios match the engine tests");
