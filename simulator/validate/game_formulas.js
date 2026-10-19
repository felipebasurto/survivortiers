/**
 * Runs the vendored PokéSurvivor sources (commit e868b5e) on scripted cases and
 * compares them with `pokesim formulas`.
 *
 *   node simulator/validate/game_formulas.js [path-to-pokesim]
 */
"use strict";

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const ROOT = path.resolve(__dirname, "../..");
const GAME = path.join(ROOT, "simulator/vendor/pokesurvivor-e868b5e");

global.G = {
  U: {
    clamp(v, a, b) { return Math.min(b, Math.max(a, v)); },
    pickN(list, n) { return list.slice(0, n); },
    rand(a, b) { return a; },
    TYPE_COLOR: {},
    TYPE_NAME: {},
  },
  Weather: { mult() { return 1; }, speedFor() { return 1; } },
  Moves: { BY_ID: {}, poolFor() { return []; }, evoInfo() { return null; }, nextUpText() { return null; } },
  Audio: { sfx() {} },
  FX: { ring() {}, burst() {} },
  Progress: { event() {} },
  Sprites: { hasShiny() { return false; } },
  Judgment: null,
  World: { liquidEffect() { return {}; } },
};

function load(rel) {
  const src = fs.readFileSync(path.join(GAME, rel), "utf8");
  eval(src);
}

load("js/data/types.js");
load("js/systems/stats.js");
load("js/systems/levelup.js");
load("js/systems/spawner.js");
load("js/entities/player.js");

const judgmentSrc = fs.readFileSync(path.join(GAME, "js/systems/judgment.js"), "utf8").replace(/\r\n/g, "\n");
const at = eval(judgmentSrc.match(/const AT = ([^;]+);/)[1]);
const touchFn = new Function(
  "arenaT",
  judgmentSrc.match(/const TOUCH = [^;]+;/)[0] +
    "\n" +
    judgmentSrc.match(/const touchPct = \(\) => [^;]+;/)[0].replace("()", "(arenaT)") +
    "\nreturn touchPct(arenaT);"
);
const capSrc = judgmentSrc.match(/const SPD_SOFT = 130, SPD_OVER = 0\.25;\n  const capSpd = [^;]+;/)[0];
const capSpd = new Function("s", capSrc + "\nreturn capSpd(s);");

const combatSrc = fs.readFileSync(path.join(GAME, "js/systems/combat.js"), "utf8").replace(/\r\n/g, "\n");
const hitSrc = combatSrc.slice(combatSrc.indexOf("function hit("), combatSrc.indexOf("function segDist2"));
function gameHit(dmg, atkFor, type, defTypes, cat, df, sd, hp, shield) {
  const pl = { critChance: 0, onDealt() {}, dmgDealt: 0 };
  const e = {
    types: defTypes,
    mon: { df, sd },
    dead: false,
    shield,
    hp,
    boss: false,
    rd: 0,
    hurt(amount) {
      const d = Math.max(1, Math.round(amount));
      let left = d;
      if (this.shield > 0) {
        const used = Math.min(this.shield, left);
        this.shield -= used;
        left -= used;
      }
      this.hp -= left;
      this.lost = (hp - Math.max(0, this.hp)) + (shield - Math.max(0, this.shield));
    },
    applyBurn() {},
    applyPoison() {},
    applySlow() {},
  };
  const m = { type, cat, dealt: 0 };
  const typeK = (t, enemy) => G.Types.mult(t, enemy.types) * G.Weather.mult(t);
  const ghost = false;
  const CRIT_MUL = 1.5;
  const isCrit = () => false;
  const fn = new Function("G", "typeK", "ghost", "CRIT_MUL", "isCrit", "pl", "e", "dmg", "m", hitSrc + "\nhit(pl, e, dmg, '#fff', 1, 0, 0, m);");
  fn(G, typeK, ghost, CRIT_MUL, isCrit, pl, e, dmg * atkFor, m);
  return { mult: G.Types.mult(type, defTypes), taken: G.Stats.taken(e.mon, cat), dealt: e.lost };
}

function gameBuff() {
  const pl = Object.create(G.Player.prototype);
  pl.buffs = {
    atk: { n: 0, t: 0, amount: 0 },
    patk: { n: 0, t: 0, amount: 0 },
    satk: { n: 0, t: 0, amount: 0 },
    spd: { n: 0, t: 0, amount: 0 },
    def: { n: 0, t: 0, amount: 0 },
    regen: { n: 0, t: 0, amount: 0 },
  };
  pl.baseAtk = 100;
  pl.atkMul = 1;
  pl.dmgReduce = 0;
  pl.mon = { pa: 120, sa: 40, atk: 120, name: "x" };
  pl.addBuff("patk", 0.5, 7, 3);
  pl.addBuff("patk", 0.5, 7, 3);
  pl.addBuff("patk", 0.5, 7, 3);
  pl.addBuff("patk", 0.9, 7, 3);
  const physical = pl.atkFor({ cat: "physical" });
  const special = pl.atkFor({ cat: "special" });
  pl.addBuff("def", 0.2, 7, 6);
  pl.addBuff("def", 0.2, 7, 6);
  pl.addBuff("def", 0.2, 7, 6);
  pl.addBuff("def", 0.2, 7, 6);
  pl.addBuff("def", 0.2, 7, 6);
  const playerSrc = fs.readFileSync(path.join(GAME, "js/entities/player.js"), "utf8").replace(/\r\n/g, "\n");
  const loop = playerSrc.match(/for \(const k in this\.buffs\) \{[\s\S]*?\n    \}/)[0];
  pl.buffs.patk.t = 0.01;
  const tick = new Function("dt", loop);
  tick.call(pl, 0.02);
  const expired = pl.atkFor({ cat: "physical" });
  return { physical, special, expired, reduction: pl.reduction, stacks: pl.buffs.def.n };
}

function offerWeights() {
  const weights = [];
  const pl = {
    slots: [{}, {}],
    maxMoves: 4,
    moves: [
      { id: "ember", kind: "projectile", lvl: 1, name: "Ember", type: "fire" },
    ],
    mon: { pa: 40, sa: 120, atk: 120, name: "x" },
    hasMove(id) { return this.moves.some(m => m.id === id); },
    banned: new Set(),
    statsTaken: {},
  };
  G.Moves.BY_ID = {
    ember: { id: "ember", kind: "projectile", cat: "special", type: "fire", name: "Ember", desc: "" },
    "tackle": { id: "tackle", kind: "melee", cat: "physical", type: "normal", name: "Tackle", desc: "" },
    "shadow-ball": { id: "shadow-ball", kind: "projectile", cat: "special", type: "ghost", name: "Shadow Ball", desc: "" },
  };
  G.Moves.poolFor = () => ["tackle", "shadow-ball"];
  G.Moves.nextUpText = (m) => (m.id === "ember" ? "up" : null);
  G.Moves.evoInfo = () => ({ ready: true, name: "Evo", text: "" });
  const saved = Math.random;
  Math.random = () => 0;
  const cards = G.LevelUp.offer(pl, 8);
  Math.random = saved;
  for (const c of cards) weights.push({ type: c.type, w: c.w });
  const full = {
    slots: [{}, {}, {}, {}],
    maxMoves: 4,
    moves: pl.moves,
    mon: pl.mon,
    hasMove: pl.hasMove,
    banned: pl.banned,
    statsTaken: { hp: 0, atk: 0, spd: 0, cd: 0, def: 0, rgn: 0, mag: 0, xp: 0 },
  };
  G.Moves.evoInfo = () => null;
  G.Moves.nextUpText = () => null;
  const statCards = G.LevelUp.offer(full, 3);
  return { open: weights, fullStat: statCards.filter(c => c.type === "stat").map(c => c.w) };
}

function gameReport() {
  const hits = [
    ["ghost", ["psychic"], 40, 1.2, 80, 40, 30, 10, "special"],
    ["fire", ["grass", "steel"], 55, 1, 75, 75, 20, 0, "physical"],
    ["water", ["fire"], 12, 2.5, 200, 40, 100, 50, "special"],
    ["normal", ["ghost"], 80, 1, 50, 50, 5, 0, "physical"],
    ["dragon", ["fairy"], 90, 0.8, 10, 120, 8, 4, "physical"],
  ].map(([type, def, dmg, atk, df, sd, hp, shield, cat]) => {
    const h = gameHit(dmg, atk, type, def, cat, df, sd, hp, shield);
    return { atk: type, def: def.join("/"), mult: h.mult, taken: h.taken, dealt: h.dealt };
  });
  return {
    guard: [0, 5, 75, 150, 400].map(def => ({ def, v: G.Stats.taken({ df: def, sd: def }, "physical") })),
    spawn: [0, 32, 60, 105, 180, 600].map(t => ({ t, rate: G.Spawner.rate(t) })),
    capSpd: [100, 130, 180, 260].map(spd => ({ spd, v: capSpd(spd) })),
    touch: [0, 420, 600, 900].map(arena => ({ arena, v: touchFn(arena) })),
    hit: hits,
    judgmentAt: at,
    cap: G.Spawner.CAP,
    surge0: 32,
    buff: gameBuff(),
    offer: offerWeights(),
    fit: {
      on: G.Stats.fit({ pa: 40, sa: 120, atk: 120 }, "special"),
      off: G.Stats.fit({ pa: 40, sa: 120, atk: 120 }, "physical"),
    },
  };
}

function close(a, b) {
  return Math.abs(a - b) <= 1e-6 * Math.max(1, Math.abs(a));
}

function main() {
  const game = gameReport();
  const bin = process.argv[2] || path.join(ROOT, "simulator/sim-rs/target/release/pokesim");
  const rust = JSON.parse(execFileSync(bin, ["formulas"], { cwd: path.join(ROOT, "simulator"), encoding: "utf8" }));
  const fails = [];
  function check(label, a, b) {
    if (!close(a, b)) fails.push(`${label}: game ${a} sim ${b}`);
  }
  for (let i = 0; i < game.guard.length; i++) check(`guard ${game.guard[i].def}`, game.guard[i].v, rust.guard[i].v);
  for (let i = 0; i < game.spawn.length; i++) check(`spawn ${game.spawn[i].t}`, game.spawn[i].rate, rust.spawn[i].rate);
  for (let i = 0; i < game.capSpd.length; i++) check(`cap ${game.capSpd[i].spd}`, game.capSpd[i].v, rust.capSpd[i].v);
  for (let i = 0; i < game.touch.length; i++) check(`touch ${game.touch[i].arena}`, game.touch[i].v, rust.touch[i].v);
  for (let i = 0; i < game.hit.length; i++) {
    check(`mult ${game.hit[i].atk}`, game.hit[i].mult, rust.hit[i].mult);
    check(`taken ${game.hit[i].atk}`, game.hit[i].taken, rust.hit[i].taken);
    check(`dealt ${game.hit[i].atk}`, game.hit[i].dealt, rust.hit[i].dealt);
  }
  if (game.judgmentAt !== 1800) fails.push(`judgment AT ${game.judgmentAt}`);
  if (game.cap !== 64) fails.push(`cap ${game.cap}`);
  if (!(game.buff.physical > game.buff.special * 2)) fails.push(`patk ${game.buff.physical} vs special ${game.buff.special}`);
  if (game.buff.stacks !== 5) fails.push(`def stacks ${game.buff.stacks}`);
  if (Math.abs(game.buff.expired - 100) > 1e-6) fails.push(`expired physical ${game.buff.expired}`);
  if (Math.abs(game.buff.reduction - 0.8) > 1e-9) fails.push(`reduction ${game.buff.reduction}`);
  const types = game.offer.open.map(c => c.type);
  if (!types.includes("evo") || !types.includes("new")) fails.push(`offer ${JSON.stringify(game.offer.open)}`);
  const evo = game.offer.open.find(c => c.type === "evo");
  const neu = game.offer.open.find(c => c.type === "new");
  const up = game.offer.open.find(c => c.type === "up");
  if (!evo || evo.w !== 40) fails.push("evo weight");
  if (!neu || neu.w !== 10) fails.push("new weight");
  if (!up || up.w !== 8) fails.push("up weight " + JSON.stringify(game.offer.open));
  if (!game.offer.fullStat.length || game.offer.fullStat.some(w => w !== 7)) fails.push(`full stat weights ${game.offer.fullStat}`);
  const openStat = game.offer.open.filter(c => c.type === "stat").map(c => c.w);
  if (!openStat.length || openStat.some(w => w !== 4)) fails.push(`open stat weights ${openStat}`);
  if (game.fit.on !== 1 || !(game.fit.off < 1)) fails.push(`fit ${JSON.stringify(game.fit)}`);
  if (fails.length) {
    console.error(fails.join("\n"));
    process.exit(1);
  }
  console.log("game formulas match the sim");
}

main();
