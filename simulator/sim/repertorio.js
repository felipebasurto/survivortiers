// Repertorio + Veto opening, as an expected value over the starter sweep.
//
// Game (JPTER78/pokesurvivor @ 5bbc3b2):
//   js/data/upgrades.js:15  Repertorio, max 1, base 1500, "Empiezas con 2 movimientos"
//   js/data/upgrades.js:18  Veto, max 3, "Bloquea 1 movimiento"
//   js/data/upgrades.js:42  startMoves: 1 + L('moves')
//   js/data/upgrades.js:45  bans: L('ban')
//   js/game.js:120-128      starter, then bans, then one random non-buff attack, active slot stays 0
//   js/game.js:554          number keys call pl.setActive(i); only the active slot fires (player.js:193)
//   js/entities/player.js:148  switching clamps that slot's cooldown to 35% of base
//   js/entities/player.js:238  the melee damage-taken factor (0.75) applies only while a melee move is active
//
// A player who bought both upgrades bans up to 3 eligible attacks and, once the random
// second attack is dealt, switches to whichever of the two lasts longer. The second attack
// is uniform over the non-buff pool (every row of the starter sweep except the starter).
// The value of a draw is the better move's solo median, not a fresh two-move sim and not
// the best move in the pool. One switch at the start is a single 35% cooldown clamp, so
// the rest of the run is that move's solo survival.
//
// Keep this file in lockstep with sim-rs/src/repertorio.rs. Shared cases:
// sim/test/repertorio_cases.json.
const fs = require('fs');
const path = require('path');
const { loadData } = require('./data');

const BANS = 3;

const OWNER = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'data', 'owner_rules.json'), 'utf8'));

function round3(x) {
  return Math.round(x * 1000) / 1000;
}

function byId(a, b) {
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
}

// When the sweep carries median_score, bans and the switch follow that score.
// The returned median/lo/hi stay the seconds of the moves that score picked.
function valueOf(move) {
  return move.rank != null ? move.rank : move.median;
}

/**
 * @param {{id:string, kind:string, median:number, lo:number, hi:number}} starter
 * @param {{id:string, kind:string, median:number, lo:number, hi:number}[]} candidates
 *        non-buff pool attacks other than the starter
 * @param {number} bans  Veto levels, 0..3
 * @returns {{median:number, lo:number, hi:number, banned:string[], draws:number, meleeLocked:boolean}}
 */
function openingValue(starter, candidates, bans = BANS) {
  const pool = candidates.filter((c) => c.id !== starter.id).slice().sort(byId);
  const nBan = Math.min(Math.max(0, bans), Math.max(0, pool.length - 1));
  const banned = [];
  for (let n = 0; n < nBan; n++) {
    let worst = 0;
    for (let i = 1; i < pool.length; i++) {
      const vw = Math.max(valueOf(starter), valueOf(pool[worst]));
      const vi = Math.max(valueOf(starter), valueOf(pool[i]));
      if (vi < vw || (vi === vw && pool[i].id < pool[worst].id)) worst = i;
    }
    banned.push(pool.splice(worst, 1)[0]);
  }
  banned.sort(byId);
  pool.sort(byId);

  let median = starter.median;
  let lo = starter.lo;
  let hi = starter.hi;
  const played = pool.filter((c) => valueOf(c) > valueOf(starter));
  if (played.length > 0) {
    let sm = 0;
    let sl = 0;
    let sh = 0;
    for (const c of pool) {
      const useSecond = valueOf(c) > valueOf(starter);
      sm += useSecond ? c.median : starter.median;
      sl += useSecond ? c.lo : starter.lo;
      sh += useSecond ? c.hi : starter.hi;
    }
    median = round3(sm / pool.length);
    lo = round3(sl / pool.length);
    hi = round3(sh / pool.length);
    if (lo > median) lo = median;
    if (hi < median) hi = median;
  }

  // Stuck on melee when no remaining draw is a strictly better non-melee attack.
  // The S-tier gate uses this. The solo melee penalty is already inside the expectation.
  const meleeLocked = starter.kind === 'melee'
    && pool.every((c) => !(c.kind !== 'melee' && valueOf(c) > valueOf(starter)));

  const out = {
    median, lo, hi, banned: banned.map((c) => c.id), draws: pool.length, meleeLocked,
  };
  if (starter.rank != null) {
    let rank = starter.rank;
    let rankLo = starter.rankLo;
    let rankHi = starter.rankHi;
    if (played.length > 0) {
      let sm = 0;
      let sl = 0;
      let sh = 0;
      for (const c of pool) {
        const useSecond = valueOf(c) > valueOf(starter);
        sm += useSecond ? c.rank : starter.rank;
        sl += useSecond ? c.rankLo : starter.rankLo;
        sh += useSecond ? c.rankHi : starter.rankHi;
      }
      rank = round3(sm / pool.length);
      rankLo = round3(sl / pool.length);
      rankHi = round3(sh / pool.length);
      if (rankLo > rank) rankLo = rank;
      if (rankHi < rank) rankHi = rank;
    }
    out.rank = rank;
    out.rankLo = rankLo;
    out.rankHi = rankHi;
  }
  return out;
}

function loadSweep(file) {
  const byDex = new Map();
  const lines = fs.readFileSync(file, 'utf8').split('\n');
  const header = lines.find((line) => line && !line.startsWith('#'));
  const cols = header.split(',');
  const ix = Object.fromEntries(cols.map((name, i) => [name, i]));
  for (const line of lines) {
    if (!line || line.startsWith('#') || line === header) continue;
    const p = line.split(',');
    const dex = Number(p[ix.dex]);
    if (!byDex.has(dex)) byDex.set(dex, new Map());
    const row = {
      id: p[ix.start],
      kind: p[ix.kind],
      median: Number(p[ix.median_s]),
      lo: Number(p[ix.boot_lo]),
      hi: Number(p[ix.boot_hi]),
    };
    if (ix.median_score != null && p[ix.median_score] !== '') {
      row.rank = Number(p[ix.median_score]);
      row.rankLo = Number(p[ix.score_lo]);
      row.rankHi = Number(p[ix.score_hi]);
    }
    byDex.get(dex).set(p[ix.start], row);
  }
  return byDex;
}

// The owner's rules on one sweep row. A move that is never an attack (Sustituto), and a
// melee move on Gengar, can be dealt but are never played: they score 0. Any other melee
// row takes the melee penalty on its score. The seconds it reports stay as measured.
function ownerView(mon, row) {
  const never = OWNER.never_attack.includes(row.id) || (mon.dex === OWNER.gengar_dex && row.kind === 'melee');
  const factor = row.kind === 'melee' ? OWNER.melee_score_factor : 1;
  const out = { ...row };
  if (never) {
    if (out.rank != null) { out.rank = 0; out.rankLo = 0; out.rankHi = 0; }
    else { out.median = 0; out.lo = 0; out.hi = 0; }
    return out;
  }
  if (out.rank != null) { out.rank *= factor; out.rankLo *= factor; out.rankHi *= factor; }
  return out;
}

function openingsFromSweep(sweepFile, data = loadData()) {
  const sweep = loadSweep(sweepFile);
  const out = [];
  for (const mon of data.dex) {
    const rows = sweep.get(mon.dex);
    if (!rows || !rows.has(mon.start)) {
      throw new Error(`sweep has no starter for ${mon.dex} ${mon.start}`);
    }
    const starter = ownerView(mon, rows.get(mon.start));
    const candidates = [];
    for (const [id, row] of rows) {
      if (id === mon.start || row.kind === 'buff') continue;
      candidates.push(ownerView(mon, row));
    }
    out.push({ dex: mon.dex, ...openingValue(starter, candidates, BANS) });
  }
  out.sort((a, b) => a.dex - b.dex);
  return out;
}

function main() {
  const args = process.argv.slice(2);
  let sweep = path.join(__dirname, '..', 'results', 'fixed_group', 'g2p2', 'starter_sweep.csv');
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--sweep') sweep = args[++i];
    else throw new Error(`unknown argument ${args[i]}`);
  }
  process.stdout.write(JSON.stringify(openingsFromSweep(sweep)));
}

module.exports = { BANS, openingValue, openingsFromSweep, round3 };

if (require.main === module) main();
