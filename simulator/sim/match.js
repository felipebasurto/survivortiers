const { rng } = require('./rng');
const { loadData } = require('./data');
const {
  BIOMES, xpFor, typeMult, strikeDamage, weatherFactor, weatherRamp, weightedKind,
  keepDistance, inMelee, inBeam, fanAngles, pulseHealer, pulseShield, readStatus,
  hexMultiplier, applyStatus, tickStatus,
  freshState, currentMove, buffLevel, legalCards, pickCard, offerCards, applyCard, deriveInto,
  guard, sideOf, fit,
} = require('./rules');

const DT = 1 / 20;
const CAP = 64;
const ELITE = 0.85;
const DMG_K = 2.4;
const OUTER = Math.hypot(768, 432) / 2 + 40;
const INV = 0.45;
const TOUCH = 0.55;
const KEEPS = {
  ranged: 1, fan: 1, beamer: 1, zoner: 1, healer: 1, summoner: 1, shielder: 1,
};
const NO_TOUCH = { healer: 1, summoner: 1 };
let SEP_X = new Float64Array(128);
let SEP_Y = new Float64Array(128);
let SEP_R = new Float64Array(128);

function len(dx, dy) {
  return Math.sqrt(dx * dx + dy * dy);
}

function separateEnemies(enemies, dt) {
  const n = enemies.length;
  if (n > SEP_X.length) {
    SEP_X = new Float64Array(n);
    SEP_Y = new Float64Array(n);
    SEP_R = new Float64Array(n);
  }
  const xs = SEP_X;
  const ys = SEP_Y;
  const rs = SEP_R;
  for (let i = 0; i < n; i++) {
    const enemy = enemies[i];
    xs[i] = enemy.x;
    ys[i] = enemy.y;
    rs[i] = enemy.r;
  }
  const push = 42 * dt;
  for (let i = 0; i < n; i++) {
    const ix = xs[i];
    const iy = ys[i];
    const ir = rs[i];
    let px = 0;
    let py = 0;
    let count = 0;
    for (let j = 0; j < n; j++) {
      if (i === j) continue;
      const min = (ir + rs[j]) * 0.82;
      const dx = ix - xs[j];
      if (dx > min || dx < -min) continue;
      const dy = iy - ys[j];
      if (dy > min || dy < -min) continue;
      const dd = dx * dx + dy * dy;
      if (dd > min * min || dd < 1e-4) continue;
      const dist = Math.sqrt(dd);
      const f = (min - dist) / min;
      const inv = 1 / dist;
      px += dx * inv * f;
      py += dy * inv * f;
      if (++count > 6) break;
    }
    if (count) {
      const enemy = enemies[i];
      enemy.x += px * push;
      enemy.y += py * push;
      xs[i] = enemy.x;
      ys[i] = enemy.y;
    }
  }
}

function scale(t) {
  return { hp: 1 + t / 95, dmg: 1 + t / 420, spd: 1 + Math.min(0.35, t / 1400) };
}
function hpK(t) {
  return 3.3 + Math.min(1.7, t / 210);
}
function spawnRate(t) {
  return (1.6 + t * 0.028 + (t / 60) ** 1.6 * 0.5) * 0.24;
}

function bagTiers(tiers, t) {
  const out = [];
  for (let i = 0; i < tiers.length; i++) {
    if (t >= tiers[i].from) out.push([i, t - tiers[i].from > 260 ? 3 : 10]);
  }
  return out;
}

// spawner.js:82. At most 3 alive of each support behavior. A full type is re-picked
// from the same tier, consuming one extra roll. An empty remainder spawns nothing.
const SUPPORT = new Set(['healer', 'shielder', 'summoner']);
const SUPPORT_MAX = 3;

function supportFull(enemies) {
  const n = Object.create(null);
  const full = new Set();
  for (const enemy of enemies) {
    if (enemy.hp <= 0 || !SUPPORT.has(enemy.beh)) continue;
    n[enemy.beh] = (n[enemy.beh] || 0) + 1;
    if (n[enemy.beh] >= SUPPORT_MAX) full.add(enemy.beh);
  }
  return full;
}

function sampleDef(tiers, t, roll, enemies) {
  const bag = bagTiers(tiers, t);
  let total = 0;
  for (const pair of bag) total += pair[1];
  let x = roll() * total;
  let tier = bag[0][0];
  for (const pair of bag) {
    x -= pair[1];
    if (x <= 0) {
      tier = pair[0];
      break;
    }
  }
  const cands = tiers[tier].cands;
  let picked = cands[Math.floor(roll() * cands.length)];
  if (SUPPORT.has(picked.def.behavior)) {
    const full = supportFull(enemies || []);
    if (full.has(picked.def.behavior)) {
      const rest = cands.filter((cand) => !full.has(cand.def.behavior));
      if (!rest.length) return null;
      picked = rest[Math.floor(roll() * rest.length)];
    }
  }
  const def = Object.assign({}, picked.def, {
    types: picked.types, r: picked.r, df: picked.df, sd: picked.sd, pa: picked.pa, sa: picked.sa,
  });
  if (['chase', 'charger', 'tank'].includes(def.behavior) && roll() < 1 / 7) {
    def.behavior = 'runner';
    def.spd = Math.round(def.spd * 1.6);
    def.hp = Math.round(def.hp * 0.7);
  }
  return def;
}

function moveHasStatus(moves, id, apply) {
  const move = moves[id];
  const sources = move.levels.slice();
  if (move.evo) sources.push(move.evo);
  for (const source of sources) {
    if (readStatus(source, apply).ignored) return true;
  }
  return false;
}

function nearest(enemies, x, y) {
  let best = null;
  let bestD = Infinity;
  for (const enemy of enemies) {
    if (enemy.hp <= 0) continue;
    const dist = len(enemy.x - x, enemy.y - y);
    if (dist < bestD) {
      bestD = dist;
      best = enemy;
    }
  }
  return best;
}

function runMatch(opts) {
  const data = opts.data || loadData();
  const mon = opts.mon;
  const dt = opts.dt || DT;
  const maxTime = opts.seconds == null ? 900 : opts.seconds;
  const cardsOn = opts.cards !== false;
  const spawnOn = opts.spawn !== false;
  const weatherOn = opts.weather !== false;
  const bot = opts.bot || 'repulse';
  // Off by default: the parity run ignores status. On, fired hits inflict burn,
  // poison and slow and Infortunio (chain) uses the ×hex bonus.
  const statusOn = !!opts.status;
  const chainOn = statusOn || !!opts.xkinds;
  const knockFade = 0.0015 ** dt;
  // stats.js guard, one pow per defense, before xpFor so the parity trace matches Rust.
  const gPhys = guard(mon.df);
  const gSpec = guard(mon.sd);
  const world = rng(opts.seed);
  const cardRoll = rng((opts.seed + 0xA5A5) >>> 0);
  const tiers = data.tiers;
  const state = freshState();
  const pool = mon.pool || [];
  let statusIgnored = moveHasStatus(data.moves, mon.start, statusOn);

  // sprites.js playerRadius: collision radius is at most PLAYER_R (18). The draw scale
  // below 18 needs Idle-frame heights this repo does not have, so it is not applied.
  const pl = { x: 0, y: 0, r: Math.min(18, mon.r), hp: mon.hp, inv: 0, dirx: 1, diry: 0, react: 0, aim: 0 };
  const enemies = [];
  const shots = [];
  const booms = [];
  const orbs = [];
  const eShots = [];
  const hazards = [];
  const hits = [];
  let spawnN = 0;
  let acc = 0;
  let surge = world() * 20 + 10;
  let kills = 0;
  let xp = 0;
  let level = 1;
  let need = xpFor(1);
  let atkCd = 0;
  let t = 0;
  let chipT = 0;
  let biome = 0;
  let biomeT = 0;
  let checkT = 60;
  let weather = null;
  let seq = 1;

  if (opts.enemies) {
    for (const preset of opts.enemies) enemies.push(presetEnemy(preset, seq++));
  }

  const st = {
    move: null, snow: false, maxHp: mon.hp, atk: mon.atk, spd: mon.spd,
    red: 0, cdMul: 1, regen: 0, melee: 1, patk: 1, satk: 1,
  };

  function hitAtk(st, cat) {
    const side = cat === 'physical' ? st.patk : cat === 'special' ? st.satk : 1;
    return st.atk * fit(mon, cat) * side;
  }
  let statDirty = true;
  let statSnow = false;
  function stats() {
    const snow = weatherOn && weather && weather.kind === 'snow' && weatherRamp(weather.elapsed, weather.dur) > 0;
    if (!statDirty && snow === statSnow) return st;
    statDirty = false;
    statSnow = snow;
    const move = currentMove(data.moves, mon.start, state);
    return deriveInto(st, mon, move, state, data.moves, snow);
  }

  function wx(type) {
    if (!weatherOn || !weather) return 1;
    return weatherFactor(weather.kind, type, weatherRamp(weather.elapsed, weather.dur));
  }

  function hurt(amount, atkType, st, cat) {
    if (pl.inv > 0 || pl.hp <= 0) return;
    // player.js incoming: taken(player, enemy cat) before the type chart. No cat → ×1.
    const g = cat === 'special' ? gSpec : cat === 'physical' ? gPhys : 1;
    const mult = typeMult(data.tmult, atkType, mon.types);
    const dmg = amount * g * mult * wx(atkType) * (1 - st.red) * st.melee;
    pl.hp -= dmg;
    pl.inv = INV;
  }

  function enemyGuard(enemy, cat) {
    if (!cat) return 1;
    const g = cat === 'special' ? enemy.gSpec : enemy.gPhys;
    return g == null ? 1 : g;
  }

  function strike(enemy, dmg, atk, moveType, status, cat) {
    if (enemy.hp <= 0) return;
    const mult = typeMult(data.tmult, moveType, enemy.types);
    // combat.js hit: typeK * Stats.taken(enemy, move cat). Crit is the ranking path only.
    const amount = strikeDamage(dmg, atk, mult, wx(moveType)) * enemyGuard(enemy, cat);
    // enemy.js hurt: bosses remember the rounded hit before the shield absorbs it.
    if (enemy.boss) enemy.rd = (enemy.rd || 0) + Math.max(1, Math.round(amount));
    let left = amount;
    if (enemy.shield > 0) {
      const used = Math.min(enemy.shield, left);
      enemy.shield -= used;
      left -= used;
    }
    enemy.hp -= left;
    if (opts.recordHits) hits.push({ amount, id: enemy.id });
    if (statusOn) applyStatus(enemy, status);
    else if (status && status.ignored) statusIgnored = true;
  }

  function levelUp(st) {
    const meta = data.moves[mon.start];
    const legal = legalCards(state, meta, pool);
    if (!legal.length) return;
    const offered = offerCards(legal, cardRoll);
    const id = pickCard(offered, state, meta);
    const before = st.maxHp;
    applyCard(state, id);
    if (id === 'sd') state.sdCd = 0;
    if (id === 'hd') state.hdCd = 0;
    statDirty = true;
    const after = stats().maxHp;
    if (after > before) pl.hp += after - before;
  }

  function grantXp(amount, st) {
    xp += amount;
    while (xp >= need) {
      xp -= need;
      level += 1;
      need = xpFor(level);
      if (cardsOn) levelUp(st);
    }
  }

  function reap(st) {
    for (let i = enemies.length - 1; i >= 0; i--) {
      if (enemies[i].hp > 0) continue;
      const gained = (enemies[i].xp || 1) * 5.6;
      enemies.splice(i, 1);
      kills += 1;
      grantXp(gained, st);
    }
  }

  function cast(st) {
    const move = st.move;
    const status = readStatus(move, statusOn);
    if (status.ignored) statusIgnored = true;
    if (move.kind === 'chain' && chainOn) {
      castChain(move, st, status);
      return;
    }
    const near = nearest(enemies, pl.x, pl.y);
    const aim = near ? Math.atan2(near.y - pl.y, near.x - pl.x) : pl.aim;
    pl.aim = aim;
    if (move.kind === 'melee') {
      for (const enemy of enemies) {
        if (inMelee(pl.x, pl.y, aim, move.arc, move.radius, enemy.x, enemy.y, enemy.r)) {
          strike(enemy, move.dmg, hitAtk(st, move.cat), move.type, status, move.cat);
        }
      }
      return;
    }
    if (move.kind === 'beam') {
      for (const enemy of enemies) {
        if (inBeam(pl.x, pl.y, aim, move.radius, move.width, enemy.x, enemy.y, enemy.r)) {
          strike(enemy, move.dmg, hitAtk(st, move.cat), move.type, status, move.cat);
        }
      }
      return;
    }
    if (move.kind === 'orbit') {
      const count = move.count || 1;
      while (orbs.length < count) {
        orbs.push({ angle: (orbs.length / count) * Math.PI * 2, inside: Object.create(null) });
      }
      if (orbs.length > count) orbs.length = count;
      return;
    }
    if (move.kind === 'nova') {
      const count = move.count || 1;
      for (let i = 0; i < count; i++) pushShot((i / count) * Math.PI * 2, move, st, status);
      return;
    }
    if (move.kind === 'projectile') {
      for (const angle of fanAngles(aim, move.count || 1, move.spread || 0)) pushShot(angle, move, st, status);
      return;
    }
    if (move.kind === 'boomerang') {
      for (const angle of fanAngles(aim, move.count || 1, move.spread || 0)) {
        booms.push({
          ox: pl.x, oy: pl.y,
          dx: Math.cos(angle), dy: Math.sin(angle),
          dist: 0, dir: 1, max: move.radius, speed: move.speed,
          r: move.size || 6, hit: Object.create(null),
          dmg: move.dmg, atk: hitAtk(st, move.cat), type: move.type, cat: move.cat, status,
        });
      }
    }
  }

  // combat.js chain(): first hop within 280 px, then the nearest unhit enemy inside
  // radius², 15 % less damage each jump. Hex is applied before hit(), so this hit's
  // own status does not boost itself.
  function castChain(move, st, status) {
    const near = nearest(enemies, pl.x, pl.y);
    if (!near || len(near.x - pl.x, near.y - pl.y) >= 280) return;
    let cur = near;
    const done = new Set();
    let k = 1;
    const n = Math.max(1, move.count || 1);
    for (let i = 0; i < n && cur; i++) {
      done.add(cur.id);
      const hex = hexMultiplier(move.hex, cur);
      strike(cur, move.dmg * k * hex, hitAtk(st, move.cat), move.type, status, move.cat);
      k *= 0.85;
      let best = null;
      let bd = (move.radius || 0) * (move.radius || 0);
      const cx = cur.x;
      const cy = cur.y;
      for (const enemy of enemies) {
        if (enemy.hp <= 0 || done.has(enemy.id)) continue;
        const dx = enemy.x - cx;
        const dy = enemy.y - cy;
        const d = dx * dx + dy * dy;
        if (d < bd) {
          bd = d;
          best = enemy;
        }
      }
      cur = best;
    }
  }

  function pushShot(angle, move, st, status) {
    const speed = move.speed;
    shots.push({
      x: pl.x, y: pl.y,
      vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
      speed, r: move.size || 7, life: move.life,
      left: (move.pierce || 0) + 1, hit: Object.create(null),
      dmg: move.dmg, atk: hitAtk(st, move.cat), type: move.type, cat: move.cat, status,
      homing: move.homing || 0,
    });
    if (shots.length > 80) shots.shift();
  }

  function steer(shot, turn) {
    const near = nearest(enemies, shot.x, shot.y);
    if (!near || !turn) return;
    // Matches js/entities/projectile.js: homing only locks onto enemies within 340 px.
    if (len(near.x - shot.x, near.y - shot.y) > 340) return;
    const desired = Math.atan2(near.y - shot.y, near.x - shot.x);
    let current = Math.atan2(shot.vy, shot.vx);
    let delta = desired - current;
    while (delta > Math.PI) delta -= Math.PI * 2;
    while (delta < -Math.PI) delta += Math.PI * 2;
    const max = turn * dt;
    if (delta > max) delta = max;
    else if (delta < -max) delta = -max;
    const angle = current + delta;
    shot.vx = Math.cos(angle) * shot.speed;
    shot.vy = Math.sin(angle) * shot.speed;
  }

  function decide(st) {
    pl.react -= dt;
    if (pl.react > 0) return;
    pl.react = 0.25;
    let fx = 0;
    let fy = 0;
    let near = null;
    let nearD = Infinity;
    const keep = keepDistance(st.move);
    for (const enemy of enemies) {
      if (enemy.hp <= 0) continue;
      const dx = enemy.x - pl.x;
      const dy = enemy.y - pl.y;
      const dist = len(dx, dy) || 1e-6;
      if (dist < nearD) {
        nearD = dist;
        near = enemy;
      }
      if (bot === 'repulse') {
        const gap = dist - enemy.r - pl.r;
        if (gap < 160) {
          const w = 1 / Math.max(8, gap);
          fx -= (dx / dist) * w;
          fy -= (dy / dist) * w;
        }
      }
    }
    if (!near) {
      pl.dirx = 0;
      pl.diry = 0;
      return;
    }
    const dx = near.x - pl.x;
    const dy = near.y - pl.y;
    const dist = len(dx, dy) || 1e-6;
    const gap = dist - near.r - pl.r;
    if (bot === 'line') {
      if (gap < keep) { fx = -dx / dist; fy = -dy / dist; }
      else if (gap > keep) { fx = dx / dist; fy = dy / dist; }
      else { fx = 0; fy = 0; }
    } else if (gap > keep) {
      fx += dx / dist;
      fy += dy / dist;
    }
    const mag = len(fx, fy);
    if (mag < 1e-6) { pl.dirx = 0; pl.diry = 0; }
    else { pl.dirx = fx / mag; pl.diry = fy / mag; }
  }

  function rollSpawn(angle) {
    const def = sampleDef(tiers, t, world, enemies);
    // An empty support re-pick consumes no further rolls and does not advance spawnN.
    if (!def) return;
    const ai = rng(((opts.seed + 1) * 1000003 + spawnN) >>> 0);
    spawnN += 1;
    const aim = angle == null ? world() * Math.PI * 2 : angle;
    const dd = OUTER + 10 + world() * 60;
    if (enemies.length >= CAP) return;
    const sc = scale(t);
    const elite = enemies.length >= CAP * ELITE;
    const enemy = {
      id: seq++,
      x: pl.x + Math.cos(aim) * dd,
      y: pl.y + Math.sin(aim) * dd * 0.9,
      // stats.js guard, after the position cos/sin and before the enemy is pushed.
      gPhys: guard(def.df),
      gSpec: guard(def.sd),
      cat: sideOf(def),
      r: def.r,
      types: def.types,
      xp: def.xp || 1,
      beh: def.behavior,
      spd: def.spd * sc.spd,
      dmg: def.dmg * sc.dmg * DMG_K,
      hp: def.hp * sc.hp * hpK(t),
      touch: 0, kx: 0, ky: 0, phase: 'walk', pt: 0,
      shotCd: (def.shotCd || 2) * ai(),
      skill: ai() * 3,
      healCd: (def.shotCd || 3.5) * ai(),
      shieldCd: 6 * ai(),
      jump: null, fuse: -1,
      shield: 0, shieldT: 0,
      shot: 0,
      cx: 1, cy: 0,
      ai, def,
      traceType: def.types.join('/'),
    };
    enemy.shot = (def.shotDmg || 10) * (enemy.dmg / (def.dmg || 1));
    if (elite) {
      enemy.hp *= 1.6;
      enemy.dmg *= 1.25;
      enemy.shot *= 1.25;
    }
    enemy.max = enemy.hp;
    enemies.push(enemy);
    if (opts.trace) spawnLog.push(enemy.traceType + '@' + Math.round(enemy.x) + ',' + Math.round(enemy.y));
  }

  const spawnLog = [];

  function tickWeather() {
    if (!weatherOn) return;
    biomeT += dt;
    if (biomeT >= 240) {
      biome = (biome + 1) % BIOMES.length;
      biomeT = 0;
    }
    if (weather) {
      weather.elapsed += dt;
      if (weather.elapsed >= weather.dur) weather = null;
    } else {
      checkT -= dt;
      if (checkT <= 0) {
        checkT = 60;
        if (world() < 0.18) {
          weather = {
            kind: weightedKind(BIOMES[biome], world()),
            elapsed: 0,
            dur: 55 + world() * 20,
          };
        }
      }
    }
    if (weather && (weather.kind === 'sand' || weather.kind === 'snow')) {
      chipT += dt;
      if (chipT >= 2) {
        chipT -= 2;
        const immune = weather.kind === 'sand'
          ? mon.types.some((tp) => tp === 'rock' || tp === 'ground' || tp === 'steel')
          : mon.types.includes('ice');
        if (!immune && weatherRamp(weather.elapsed, weather.dur) > 0) {
          pl.hp -= 0.012 * stats().maxHp;
        }
      }
    }
  }

  function tickBuffs(st) {
    for (const which of ['sd', 'hd']) {
      const id = which === 'sd' ? 'swords-dance' : 'harden';
      const lvl = state[which];
      if (lvl <= 0) continue;
      const inst = buffLevel(data.moves, id, lvl);
      const timeKey = which + 'T';
      const stackKey = which + 'Stacks';
      const cdKey = which + 'Cd';
      if (state[timeKey] > 0) {
        state[timeKey] -= dt;
        if (state[timeKey] <= 0) statDirty = true;
      }
      if (state[timeKey] <= 0) state[stackKey] = 0;
      state[cdKey] -= dt;
      if (state[cdKey] <= 0) {
        state[stackKey] = Math.min(inst.stacks, state[stackKey] + 1);
        state[timeKey] = inst.dur;
        state[cdKey] = inst.cd * st.cdMul;
        statDirty = true;
      }
    }
  }

  function stepOrbs(st) {
    const move = st.move;
    if (move.kind !== 'orbit') {
      orbs.length = 0;
      return;
    }
    const count = move.count || 1;
    while (orbs.length < count) {
      orbs.push({ angle: (orbs.length / count) * Math.PI * 2, inside: Object.create(null) });
    }
    const status = readStatus(move, statusOn);
    for (const orb of orbs) {
      orb.angle += (move.speed || 1) * dt;
      const x = pl.x + Math.cos(orb.angle) * move.radius;
      const y = pl.y + Math.sin(orb.angle) * move.radius;
      for (const enemy of enemies) {
        if (enemy.hp <= 0) continue;
        const overlap = len(enemy.x - x, enemy.y - y) < (move.size || 8) + enemy.r;
        if (overlap) {
          if (!orb.inside[enemy.id]) {
            orb.inside[enemy.id] = 1;
            strike(enemy, move.dmg, hitAtk(st, move.cat), move.type, status, move.cat);
          }
        } else if (orb.inside[enemy.id]) {
          delete orb.inside[enemy.id];
        }
      }
    }
  }

  function stepShots(st) {
    for (let i = shots.length - 1; i >= 0; i--) {
      const shot = shots[i];
      steer(shot, shot.homing);
      shot.x += shot.vx * dt;
      shot.y += shot.vy * dt;
      shot.life -= dt;
      if (shot.life <= 0) {
        shots.splice(i, 1);
        continue;
      }
      for (const enemy of enemies) {
        if (enemy.hp <= 0 || shot.hit[enemy.id]) continue;
        const rad = shot.r + enemy.r;
        const dx = enemy.x - shot.x;
        const dy = enemy.y - shot.y;
        if (dx > rad || dx < -rad || dy > rad || dy < -rad) continue;
        if (len(dx, dy) < rad) {
          shot.hit[enemy.id] = 1;
          shot.left -= 1;
          strike(enemy, shot.dmg, shot.atk, shot.type, shot.status, shot.cat);
          if (shot.left <= 0) {
            shots.splice(i, 1);
            break;
          }
        }
      }
    }
    for (let i = booms.length - 1; i >= 0; i--) {
      const boom = booms[i];
      boom.dist += boom.speed * dt * boom.dir;
      if (boom.dir > 0 && boom.dist >= boom.max) {
        boom.dist = boom.max;
        boom.dir = -1;
        boom.hit = Object.create(null);
      }
      if (boom.dir < 0 && boom.dist <= 0) {
        booms.splice(i, 1);
        continue;
      }
      const x = boom.ox + boom.dx * boom.dist;
      const y = boom.oy + boom.dy * boom.dist;
      for (const enemy of enemies) {
        if (enemy.hp <= 0 || boom.hit[enemy.id]) continue;
        if (len(enemy.x - x, enemy.y - y) < boom.r + enemy.r) {
          boom.hit[enemy.id] = 1;
          strike(enemy, boom.dmg, boom.atk, boom.type, boom.status, boom.cat);
        }
      }
    }
    stepOrbs(st);
  }

  function stepEnemies(st) {
    for (let i = enemies.length - 1; i >= 0; i--) {
      const enemy = enemies[i];
      if (enemy.hp <= 0) continue;
      if (enemy.touch > 0) enemy.touch -= dt;
      // enemy.js update: recent boss damage forgets with tau 6 s, before DoT ticks.
      if (enemy.boss && enemy.rd > 0) enemy.rd *= Math.exp(-dt / 6);
      if (statusOn) {
        tickStatus(enemy, dt, level);
        if (enemy.hp <= 0) continue;
      }
      if (enemy.shieldT > 0) {
        enemy.shieldT -= dt;
        if (enemy.shieldT <= 0) enemy.shield = 0;
      }
      let dx = pl.x - enemy.x;
      let dy = pl.y - enemy.y;
      const dist = len(dx, dy) || 1e-3;
      dx /= dist;
      dy /= dist;
      if (!enemy.preset && dist > OUTER + 250) {
        const a = Math.atan2(pl.diry, pl.dirx) + (enemy.ai() * 1.8 - 0.9);
        const dd = OUTER + 10 + enemy.ai() * 60;
        enemy.x = pl.x + Math.cos(a) * dd;
        enemy.y = pl.y + Math.sin(a) * dd * 0.9;
        enemy.phase = 'walk';
        continue;
      }
      if (enemy.jump) {
        enemy.jump.t += dt;
        if (enemy.jump.t >= enemy.jump.dur) {
          enemy.x = enemy.jump.tx;
          enemy.y = enemy.jump.ty;
          enemy.jump = null;
        }
        continue;
      }
      if (enemy.fuse >= 0) {
        enemy.fuse -= dt;
        if (enemy.fuse <= 0) enemy.hp = 0;
        continue;
      }
      const spd = statusOn ? enemy.spd * (1 - (enemy.slow || 0)) : enemy.spd;
      const slow = 1;
      let vx = dx * spd * slow;
      let vy = dy * spd * slow;
      const beh = enemy.beh;
      if (beh === 'chase' || beh === 'tank') {
        enemy.x += enemy.kx * dt;
        enemy.y += enemy.ky * dt;
        enemy.kx *= knockFade;
        enemy.ky *= knockFade;
        enemy.x += vx * dt;
        enemy.y += vy * dt;
        const rad = enemy.r + pl.r;
        const gx = enemy.x - pl.x;
        const gy = enemy.y - pl.y;
        if ((gx > rad || gx < -rad || gy > rad || gy < -rad) || enemy.touch > 0) continue;
        const gap = len(gx, gy);
        if (gap <= rad) {
          enemy.touch = TOUCH;
          hurt(enemy.dmg, enemy.types[0], st, enemy.cat);
          const nx = gx / (gap || 1);
          const ny = gy / (gap || 1);
          enemy.kx += nx * 150;
          enemy.ky += ny * 150;
        }
        continue;
      }
      if (beh === 'runner') {
        const lead = Math.min(1.4, Math.max(0, dist / Math.max(60, spd)));
        let tx = pl.x + pl.dirx * st.spd * lead - enemy.x;
        let ty = pl.y + pl.diry * st.spd * lead - enemy.y;
        const mag = len(tx, ty) || 1;
        vx = (tx / mag) * spd;
        vy = (ty / mag) * spd;
      }
      if (beh === 'bomber' && dist < enemy.r + pl.r + 26) {
        enemy.fuse = 1;
        hazards.push({ kind: 'zone', x: enemy.x, y: enemy.y, r: 62, delay: 1, t: 0, dmg: enemy.dmg * 1.4, atkType: enemy.types[0], cat: enemy.cat });
        continue;
      }
      if (beh === 'jumper') {
        enemy.skill -= dt;
        if (enemy.skill <= 0) {
          if (dist < 250) {
            enemy.skill = 5 + enemy.ai() * 2;
            enemy.jump = { tx: pl.x, ty: pl.y, t: -0.45, dur: 0.6 };
            hazards.push({ kind: 'zone', x: pl.x, y: pl.y, r: 50, delay: 1.05, t: 0, dmg: enemy.dmg * 1.2, atkType: enemy.types[0], cat: enemy.cat });
            continue;
          }
          enemy.skill = 0.5;
        }
      }
      if (beh === 'charger') {
        enemy.pt -= dt;
        if (enemy.phase === 'walk') {
          if (dist < 200 && enemy.pt <= 0) { enemy.phase = 'aim'; enemy.pt = 0.55; }
        } else if (enemy.phase === 'aim') {
          vx = 0; vy = 0;
          if (enemy.pt <= 0) { enemy.phase = 'dash'; enemy.pt = 0.42; enemy.cx = dx; enemy.cy = dy; }
        } else {
          vx = enemy.cx * spd * 3.4;
          vy = enemy.cy * spd * 3.4;
          if (enemy.pt <= 0) { enemy.phase = 'walk'; enemy.pt = 1.1; }
        }
      }
      const keeps = KEEPS[beh];
      if (keeps) {
        const range = (enemy.def && enemy.def.range) || 200;
        const hold = range * 0.82;
        if (dist < hold * 0.75) { vx = -dx * spd * 0.8; vy = -dy * spd * 0.8; }
        else if (dist < hold) { vx *= 0.1; vy *= 0.1; }
        enemy.shotCd -= dt;
        if (enemy.shotCd <= 0 && dist < range && enemy.def) {
          enemy.shotCd = enemy.def.shotCd || 2;
          const shoot = (spread, n, k) => {
            const base = Math.atan2(dy, dx);
            for (let j = 0; j < n; j++) {
              const a = base + (n === 1 ? 0 : (j / (n - 1) - 0.5) * spread);
              eShots.push({
                x: enemy.x, y: enemy.y, vx: Math.cos(a) * 190, vy: Math.sin(a) * 190,
                r: 7, life: 2.4, dmg: enemy.shot * k, atkType: enemy.types[0], cat: enemy.cat,
              });
            }
          };
          if (beh === 'ranged') shoot(0, 1, 1);
          else if (beh === 'fan') {
            const n = enemy.def.fanN || 5;
            shoot(n === 3 ? 0.6 : 0.9, n, 0.65);
          } else if (beh === 'beamer') {
            hazards.push({ kind: 'beam', x: enemy.x, y: enemy.y, angle: Math.atan2(dy, dx), len: 360, w: 22, delay: 1, t: 0, dmg: enemy.shot * 1.05, atkType: enemy.types[0], cat: enemy.cat });
          } else if (beh === 'zoner') {
            const n = 1 + Math.floor(enemy.ai() * (enemy.def.zones || 3));
            for (let j = 0; j < n; j++) {
              hazards.push({
                kind: 'zone',
                x: pl.x + (j ? enemy.ai() * 140 - 70 : 0),
                y: pl.y + (j ? enemy.ai() * 110 - 55 : 0),
                r: 44, delay: 1.2, t: 0, dmg: enemy.shot * 0.95, atkType: enemy.types[0], cat: enemy.cat,
              });
            }
          }
        }
      }
      if (beh === 'healer') {
        enemy.healCd -= dt;
        if (enemy.healCd <= 0) {
          enemy.healCd = (enemy.def && enemy.def.shotCd) || 3.5;
          pulseHealer(enemy.x, enemy.y, enemies, st.atk, mon.atk);
        }
      }
      if (beh === 'shielder') {
        enemy.shieldCd -= dt;
        if (enemy.shieldCd <= 0) {
          enemy.shieldCd = 6;
          pulseShield(enemy.x, enemy.y, enemies);
        }
      }
      enemy.x += enemy.kx * dt;
      enemy.y += enemy.ky * dt;
      enemy.kx *= knockFade;
      enemy.ky *= knockFade;
      enemy.x += vx * dt;
      enemy.y += vy * dt;
      const rad = enemy.r + pl.r;
      const gx = enemy.x - pl.x;
      const gy = enemy.y - pl.y;
      if ((gx > rad || gx < -rad || gy > rad || gy < -rad) || enemy.touch > 0 || NO_TOUCH[beh]) continue;
      const gap = len(gx, gy);
      if (gap <= rad) {
        enemy.touch = TOUCH;
        hurt(enemy.dmg, enemy.types[0], st, enemy.cat);
        const nx = gx / (gap || 1);
        const ny = gy / (gap || 1);
        enemy.kx += nx * 150;
        enemy.ky += ny * 150;
      }
    }
    separateEnemies(enemies, dt);
    for (let i = eShots.length - 1; i >= 0; i--) {
      const shot = eShots[i];
      shot.x += shot.vx * dt;
      shot.y += shot.vy * dt;
      shot.life -= dt;
      if (shot.life <= 0) { eShots.splice(i, 1); continue; }
      if (len(shot.x - pl.x, shot.y - pl.y) < shot.r + pl.r) {
        hurt(shot.dmg, shot.atkType, st, shot.cat);
        eShots.splice(i, 1);
      }
    }
    for (let i = hazards.length - 1; i >= 0; i--) {
      const hazard = hazards[i];
      hazard.t += dt;
      if (hazard.t < hazard.delay) continue;
      let inside;
      if (hazard.kind === 'zone') inside = len(pl.x - hazard.x, pl.y - hazard.y) < hazard.r + pl.r * 0.6;
      else {
        const ca = Math.cos(hazard.angle);
        const sa = Math.sin(hazard.angle);
        const px = pl.x - hazard.x;
        const py = pl.y - hazard.y;
        const along = px * ca + py * sa;
        inside = along >= -pl.r && along <= hazard.len + pl.r && Math.abs(-px * sa + py * ca) <= hazard.w / 2 + pl.r * 0.6;
      }
      if (inside) hurt(hazard.dmg, hazard.atkType, st, hazard.cat);
      hazards.splice(i, 1);
    }
  }

  while (t < maxTime && pl.hp > 0) {
    const step = Math.min(dt, maxTime - t);
    t += step;
    tickWeather();
    let st = stats();
    if (st.regen) pl.hp = Math.min(st.maxHp, pl.hp + st.regen * step);
    if (pl.inv > 0) pl.inv -= step;
    if (spawnOn) {
      acc += spawnRate(t) * step;
      let n = Math.floor(acc);
      acc -= n;
      while (n-- > 0) rollSpawn(null);
      surge -= step;
      if (surge <= 0) {
        surge = 38 + world() * 18;
        const base = world() * Math.PI * 2;
        const want = Math.round((14 + Math.floor(t / 22)) * 0.4);
        for (let i = 0; i < want; i++) rollSpawn(base + (world() * 1.1 - 0.55));
      }
    }
    st = stats();
    decide(st);
    pl.x += pl.dirx * st.spd * step;
    pl.y += pl.diry * st.spd * step;
    tickBuffs(st);
    st = stats();
    atkCd -= step;
    if (atkCd <= 0) {
      cast(st);
      atkCd = st.move.cd * st.cdMul;
    }
    stepShots(st);
    reap(st);
    st = stats();
    stepEnemies(st);
    reap(st);
  }

  const end = stats();
  const capped = pl.hp > 0;
  return {
    time: capped ? maxTime : t,
    kills,
    level,
    capped,
    statusIgnored,
    hp: pl.hp,
    maxHp: end.maxHp,
    hpFrac: capped ? pl.hp / end.maxHp : 0,
    hits: opts.recordHits ? hits : undefined,
    spawns: opts.trace ? spawnLog : undefined,
  };
}

function presetEnemy(p, id) {
  return {
    id,
    x: p.x, y: p.y, r: p.r,
    types: p.types || ['normal'],
    xp: p.xp || 1,
    beh: p.beh || 'chase',
    spd: p.spd || 0,
    dmg: p.dmg || 0,
    hp: p.hp,
    max: p.max || p.hp,
    touch: 0, kx: 0, ky: 0, phase: 'walk', pt: 0,
    shotCd: 999, skill: 999, healCd: 999, shieldCd: 999,
    jump: null, fuse: -1, shield: 0, shieldT: 0, shot: 0,
    cx: 1, cy: 0,
    ai: rng(1),
    def: { range: p.range || 200, shotCd: 999, behavior: p.beh || 'chase' },
    preset: true,
  };
}

module.exports = { runMatch, DT };
