const STAT_OF = {
  atk: 'pow', spd: 'run', def: 'cor', hp: 'hp', cd: 'cd', rgn: 'rgn', mag: 'mag',
};
const CAPS = { pow: 40, run: 8, hp: 99, cor: 12, cd: 10, rgn: 10, mag: 6 };
const STATUS_SECONDS = 3;
const WX = {
  sun: { fire: 1.5, water: 0.5 },
  rain: { water: 1.5, electric: 1.2, fire: 0.5 },
  sand: { rock: 1.3, ground: 1.3, steel: 1.3 },
  snow: { ice: 1.5 },
  fog: { ghost: 1.3, fairy: 1.3, psychic: 1.3 },
};
const BIOMES = [
  [['rain', 3], ['fog', 2], ['sun', 1.5], ['snow', 0.5], ['sand', 0.5]],
  [['fog', 3], ['snow', 2.5], ['rain', 1], ['sand', 1]],
  [['sun', 3], ['sand', 3], ['fog', 1]],
];
const FILL = ['sd', 'hd', 'pow', 'run', 'hp', 'cor', 'cd', 'rgn', 'mag'];

function xpFor(level) {
  return Math.floor((8 + level * 6 + (level ** 1.75) * 1.6) * 4);
}

function typeMult(table, atk, defTypes) {
  const key = defTypes.join('/');
  const row = table[atk];
  if (!row || row[key] == null) {
    throw new Error('missing type ' + atk + ' vs ' + key);
  }
  return row[key];
}

function strikeDamage(dmg, atk, mult, weather) {
  return dmg * atk * mult * weather;
}

function weatherFactor(kind, type, strength) {
  if (!kind || strength <= 0) return 1;
  const table = WX[kind];
  const mult = (table && table[type]) || 1;
  return 1 + (mult - 1) * strength;
}

function weatherRamp(elapsed, dur) {
  return Math.min(1, elapsed / 3, Math.max(0, dur - elapsed) / 3);
}

function weightedKind(pairs, roll) {
  let sum = 0;
  for (const pair of pairs) sum += pair[1];
  let x = roll * sum;
  for (const pair of pairs) {
    x -= pair[1];
    if (x <= 0) return pair[0];
  }
  return pairs[0][0];
}

function reachOf(move) {
  if (move.kind === 'melee') return move.radius;
  if (move.kind === 'projectile' || move.kind === 'nova') return move.speed * move.life;
  if (move.kind === 'beam' || move.kind === 'orbit' || move.kind === 'boomerang') return move.radius;
  return 180;
}

function keepDistance(move) {
  if (move.kind === 'melee') return 0.55 * move.radius;
  return 0.75 * reachOf(move);
}

function len(dx, dy) {
  return Math.sqrt(dx * dx + dy * dy);
}

function inMelee(px, py, angle, arc, radius, ex, ey, er) {
  const dx = ex - px;
  const dy = ey - py;
  const dist = len(dx, dy);
  if (dist > radius + er) return false;
  if (arc >= Math.PI * 2 - 1e-3) return true;
  let turn = Math.atan2(dy, dx) - angle;
  while (turn > Math.PI) turn -= Math.PI * 2;
  while (turn < -Math.PI) turn += Math.PI * 2;
  return Math.abs(turn) <= arc / 2 + 1e-9;
}

function inBeam(px, py, angle, len, width, ex, ey, er) {
  const dx = ex - px;
  const dy = ey - py;
  const ca = Math.cos(angle);
  const sa = Math.sin(angle);
  const along = dx * ca + dy * sa;
  const perp = -dx * sa + dy * ca;
  return along >= -er && along <= len + er && Math.abs(perp) <= width / 2 + er;
}

function fanAngles(aim, count, spread) {
  const n = Math.max(1, count | 0);
  if (n === 1) return [aim];
  const width = (spread || 0) * n;
  const out = [];
  for (let i = 0; i < n; i++) out.push(aim + (i / (n - 1) - 0.5) * width);
  return out;
}

function healFraction(atk, baseAtk) {
  const pow = baseAtk > 0 ? atk / baseAtk : 1;
  return 0.07 * Math.min(2.5, pow ** 0.35);
}

// stats.js:17-43 at e868b5e. REF 75, EXP 0.35, clamp 0.78..1.25.
// `def || 75` treats a missing defense as the average. Math.pow is traced by parity.js.
const GUARD_REF = 75;
const GUARD_LO = 0.78;
const GUARD_HI = 1.25;
function guard(def) {
  const base = def || GUARD_REF;
  return Math.min(GUARD_HI, Math.max(GUARD_LO, Math.pow(GUARD_REF / Math.max(5, base), 0.35)));
}

function taken(mon, cat) {
  if (!mon || !cat) return 1;
  return guard(cat === 'special' ? mon.sd : mon.df);
}

function sideOf(mon) {
  if (!mon || mon.pa == null || mon.sa == null) return 'physical';
  return mon.sa > mon.pa ? 'special' : 'physical';
}

function fit(mon, cat) {
  if (!mon || !cat || mon.pa == null) return 1;
  return (cat === 'special' ? mon.sa : mon.pa) / mon.atk;
}

// enemy.js:42. Poison percent uses this effective HP; above 60_000 it grows with sqrt.
function pctHp(maxHp) {
  if (maxHp <= 60000) return maxHp;
  return 60000 * Math.sqrt(maxHp / 60000);
}

// judgment.js:46-48. Above 130, only a quarter of the extra speed counts.
function capSpd(s) {
  return s <= 130 ? s : 130 + (s - 130) * 0.25;
}

function judgmentTouchPct(arenaT) {
  return Math.min(1, 0.4 + Math.max(0, arenaT - 420) / 180 * 0.6);
}

function judgmentChaseK(arenaT) {
  return Math.min(1.22, 0.74 + arenaT * 0.013) + Math.max(0, arenaT - 300) * 0.0015;
}

function healAmount(maxHp, atk, baseAtk) {
  return maxHp * healFraction(atk, baseAtk);
}

function pulseHealer(hx, hy, enemies, atk, baseAtk) {
  for (const enemy of enemies) {
    if (enemy.hp >= enemy.max) continue;
    if (len(enemy.x - hx, enemy.y - hy) <= 150) {
      // enemy.js healAround: a boss heals at most 0.4 s of recent damage (RD_TAU 6).
      const heal = healAmount(enemy.max, atk, baseAtk);
      const add = enemy.boss ? Math.min(heal, (enemy.rd / 6) * 0.4) : heal;
      enemy.hp = Math.min(enemy.max, enemy.hp + add);
    }
  }
}

function pulseShield(sx, sy, enemies) {
  const near = [];
  for (const enemy of enemies) {
    const dist = len(enemy.x - sx, enemy.y - sy);
    if (dist <= 160) near.push([dist, enemy]);
  }
  near.sort((a, b) => a[0] - b[0]);
  // enemy.js castShields: the nearest 6, and a skipped boss still occupies a slot.
  // Only a boss with shieldT > 2 is skipped (one shield per ~6 s, scaled to 1.2 s
  // of recent damage). A normal enemy refreshes 35% even if a shield is already up.
  let given = 0;
  for (const pair of near) {
    if (given >= 6) break;
    given += 1;
    const enemy = pair[1];
    if (enemy.boss && enemy.shieldT > 2) continue;
    const s = enemy.boss
      ? Math.min(enemy.max * 0.35, (enemy.rd / 6) * 1.2)
      : enemy.max * 0.35;
    enemy.shield = Math.max(enemy.shield, s);
    enemy.shieldT = 8;
  }
}

// enemy.js applySlow / applyBurn / applyPoison, and the tick in Enemy.update.
// Slow is a speed factor for 1.2 s (the default duration). Burn stacks to 8 for 3 s
// and ticks every 0.5 s. Poison stacks to 8 for 4 s and ticks every 0.6 s.
const SLOW_SECS = 1.2;
const BURN_MAX = 8;
const BURN_SECS = 3;
const BURN_TICK = 0.5;
const POISON_MAX = 8;
const POISON_SECS = 4;
const POISON_TICK = 0.6;
// Kinds this engine actually fires. Chain is included so Infortunio can resolve;
// cone, meteor, aura, dash, mine, trail and turret stay in the Rust ranker.
const STATUS_KINDS = new Set(['melee', 'beam', 'orbit', 'nova', 'projectile', 'boomerang', 'chain']);

function readStatus(move, apply = false) {
  // Default (apply false) is the parity path: burn/poison/slow are recorded as
  // ignored and not turned into damage. opts.status passes apply so a fired hit
  // inflicts them. Values match data/moves.js; there is no hit-chance roll.
  const out = { burn: 0, poison: 0, slow: 0, ignored: false };
  const fires = apply && STATUS_KINDS.has(move.kind);
  for (const key of ['burn', 'poison', 'slow']) {
    if (move[key] != null) {
      if (fires) out[key] = move[key];
      else out.ignored = true;
    }
  }
  return out;
}

/** combat.js chain: `m.hex && (burn > 0 || poison > 0 || slow > 0) ? m.hex : 1`. */
function hexMultiplier(hex, enemy) {
  if (!(hex > 0) || !enemy) return 1;
  if (enemy.burn > 0 || enemy.poison > 0 || enemy.slow > 0) return hex;
  return 1;
}

function applyStatus(enemy, status) {
  if (!status) return;
  if (status.slow > 0) {
    enemy.slow = Math.max(enemy.slow || 0, status.slow);
    enemy.slowT = Math.max(enemy.slowT || 0, SLOW_SECS);
  }
  if (status.burn > 0) {
    enemy.burn = Math.min(BURN_MAX, (enemy.burn || 0) + status.burn);
    enemy.burnT = BURN_SECS;
  }
  if (status.poison > 0) {
    enemy.poison = Math.min(POISON_MAX, (enemy.poison || 0) + status.poison);
    enemy.poisonT = POISON_SECS;
  }
}

/** One Enemy.update status step. DoT uses hurt(): round, at least 1, shield first. */
function tickStatus(enemy, dt, level) {
  if (enemy.slowT > 0) {
    enemy.slowT -= dt;
    if (enemy.slowT <= 0) enemy.slow = 0;
  }
  if (enemy.burn > 0) {
    enemy.burnT -= dt;
    enemy.burnTick = (enemy.burnTick || 0) - dt;
    if (enemy.burnTick <= 0) {
      enemy.burnTick = BURN_TICK;
      hurtDot(enemy, 1.6 * enemy.burn * (1 + level * 0.06));
    }
    if (enemy.burnT <= 0) enemy.burn = 0;
  }
  if (enemy.poison > 0) {
    enemy.poisonT -= dt;
    enemy.poisonTick = (enemy.poisonTick || 0) - dt;
    if (enemy.poisonTick <= 0) {
      enemy.poisonTick = POISON_TICK;
      hurtDot(enemy, pctHp(enemy.max) * 0.012 * enemy.poison + 1);
    }
    if (enemy.poisonT <= 0) enemy.poison = 0;
  }
}

function hurtDot(enemy, amount) {
  if (!(enemy.hp > 0)) return;
  const d = Math.max(1, Math.round(amount));
  let left = d;
  const shield = enemy.shield || 0;
  if (shield > 0) {
    const used = Math.min(shield, d);
    enemy.shield = shield - used;
    left = d - used;
    if (left <= 0) return;
  }
  enemy.hp -= left;
}

function freshState() {
  return {
    cards: { pow: 0, run: 0, hp: 0, cor: 0, cd: 0, rgn: 0, mag: 0 },
    moveLvl: 1,
    evolved: false,
    sd: 0,
    hd: 0,
    sdStacks: 0,
    sdT: 0,
    sdCd: 0,
    hdStacks: 0,
    hdT: 0,
    hdCd: 0,
  };
}

function currentMove(moves, startId, state) {
  const move = moves[startId];
  if (state.evolved && move.evo) return move.evo;
  return move.levels[Math.min(state.moveLvl, move.maxLvl) - 1];
}

function buffLevel(moves, id, lvl) {
  const move = moves[id];
  const index = Math.max(1, Math.min(lvl, move.maxLvl)) - 1;
  return move.levels[index];
}

function legalCards(state, moveMeta, pool) {
  const out = [];
  const cards = state.cards;
  const need = moveMeta.needs ? STAT_OF[moveMeta.needs] : null;
  const atMax = !state.evolved && state.moveLvl >= moveMeta.maxLvl && moveMeta.evo;
  if (!state.evolved && state.moveLvl < moveMeta.maxLvl) out.push('up');
  if (atMax) {
    if (need && cards[need] < 1) out.push(need);
    else out.push('evo');
  }
  if (pool.includes('swords-dance') && state.sd < 5) out.push('sd');
  if (pool.includes('harden') && state.hd < 5) out.push('hd');
  for (const id of ['pow', 'run', 'hp', 'cor', 'cd', 'rgn', 'mag']) {
    if (out.includes(id)) continue;
    if (cards[id] < CAPS[id]) out.push(id);
  }
  return out;
}

function pickCard(offered, state, moveMeta) {
  const has = (id) => offered.includes(id);
  const need = moveMeta.needs ? STAT_OF[moveMeta.needs] : null;
  const atMax = !state.evolved && state.moveLvl >= moveMeta.maxLvl && moveMeta.evo;
  if (has('up') && !state.evolved && state.moveLvl < moveMeta.maxLvl) return 'up';
  if (atMax) {
    if (need && state.cards[need] < 1 && has(need)) return need;
    if ((!need || state.cards[need] >= 1) && has('evo')) return 'evo';
  }
  for (const id of FILL) {
    if (has(id)) return id;
  }
  return offered[0];
}

function offerCards(legal, roll) {
  const bag = legal.slice();
  for (let i = bag.length - 1; i > 0; i--) {
    const j = Math.floor(roll() * (i + 1));
    const swap = bag[i];
    bag[i] = bag[j];
    bag[j] = swap;
  }
  return bag.slice(0, Math.min(3, bag.length));
}

function applyCard(state, id) {
  if (id === 'up') {
    state.moveLvl += 1;
    return;
  }
  if (id === 'evo') {
    state.evolved = true;
    return;
  }
  if (id === 'sd') {
    state.sd = Math.min(5, state.sd + 1);
    return;
  }
  if (id === 'hd') {
    state.hd = Math.min(5, state.hd + 1);
    return;
  }
  if (state.cards[id] != null && state.cards[id] < CAPS[id]) state.cards[id] += 1;
}

const ATK_POW = new Float64Array(41);
const SPD_POW = new Float64Array(9);
const CD_POW = new Float64Array(11);
for (let i = 0; i < ATK_POW.length; i++) ATK_POW[i] = 1.1 ** i;
for (let i = 0; i < SPD_POW.length; i++) SPD_POW[i] = 1.07 ** i;
for (let i = 0; i < CD_POW.length; i++) CD_POW[i] = 0.92 ** i;

function deriveInto(out, mon, move, state, moves, snowOn) {
  let generic = 0;
  let patk = 1;
  let satk = 1;
  let defBuff = 0;
  // player.js atkFor (e868b5e): Swords Dance and Dragon Dance are patk, Nasty Plot is satk.
  // Fit and the side buff stay off this plain attack. A healer reads player.js `atk`,
  // and baking fit here changes the traced heal pow (rules.js healFraction).
  const cat = move.cat || null;
  if (state.sd > 0 && state.sdT > 0) {
    const inst = buffLevel(moves, 'swords-dance', state.sd);
    const bonus = state.sdStacks * inst.amount;
    if (inst.stat === 'patk') patk = 1 + bonus;
    else if (inst.stat === 'satk') satk = 1 + bonus;
    else generic = bonus;
  }
  if (state.hd > 0 && state.hdT > 0) {
    defBuff = state.hdStacks * buffLevel(moves, 'harden', state.hd).amount;
  }
  let spd = mon.spd * SPD_POW[state.cards.run];
  if (snowOn && !mon.types.includes('ice')) spd *= 0.9;
  out.maxHp = mon.hp + 20 * state.cards.hp;
  // Plain attack, as player.js `atk`. Fit and the patk/satk buff are applied per move
  // (atkFor). A healer scales off this, not off the move, so they must stay out.
  out.atk = mon.atk * ATK_POW[state.cards.pow] * (1 + generic);
  out.patk = patk;
  out.satk = satk;
  out.cat = cat;
  out.spd = spd;
  out.red = Math.min(0.8, Math.min(0.7, 0.06 * state.cards.cor) + defBuff);
  out.cdMul = CD_POW[state.cards.cd];
  out.regen = 0.9 * state.cards.rgn;
  // Incoming damage while the active move is melee. player.js:238, not the v4 exposure penalty.
  out.melee = move.kind === 'melee' ? 0.75 : 1;
  out.move = move;
  out.snow = snowOn;
  return out;
}

function derive(mon, move, state, moves, snowOn) {
  return deriveInto({}, mon, move, state, moves, snowOn);
}

function quantile(sorted, p) {
  if (!sorted.length) return 0;
  if (sorted.length === 1) return sorted[0];
  const x = (sorted.length - 1) * p;
  const i = Math.floor(x);
  const frac = x - i;
  if (i + 1 >= sorted.length) return sorted[i];
  return sorted[i] * (1 - frac) + sorted[i + 1] * frac;
}

module.exports = {
  STAT_OF,
  CAPS,
  STATUS_SECONDS,
  BIOMES,
  xpFor,
  typeMult,
  strikeDamage,
  weatherFactor,
  weatherRamp,
  weightedKind,
  reachOf,
  keepDistance,
  inMelee,
  inBeam,
  fanAngles,
  healFraction,
  healAmount,
  guard,
  taken,
  sideOf,
  fit,
  pctHp,
  capSpd,
  judgmentTouchPct,
  judgmentChaseK,
  pulseHealer,
  pulseShield,
  readStatus,
  hexMultiplier,
  applyStatus,
  tickStatus,
  SLOW_SECS,
  BURN_SECS,
  POISON_SECS,
  freshState,
  currentMove,
  buffLevel,
  legalCards,
  pickCard,
  offerCards,
  applyCard,
  derive,
  deriveInto,
  quantile,
};
