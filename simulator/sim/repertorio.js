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

function round3(x) {
  return Math.round(x * 1000) / 1000;
}

function byId(a, b) {
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
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
      const vw = Math.max(starter.median, pool[worst].median);
      const vi = Math.max(starter.median, pool[i].median);
      if (vi < vw || (vi === vw && pool[i].id < pool[worst].id)) worst = i;
    }
    banned.push(pool.splice(worst, 1)[0]);
  }
  banned.sort(byId);
  pool.sort(byId);

  let median = starter.median;
  let lo = starter.lo;
  let hi = starter.hi;
  const played = pool.filter((c) => c.median > starter.median);
  if (played.length > 0) {
    let sm = 0;
    let sl = 0;
    let sh = 0;
    for (const c of pool) {
      const useSecond = c.median > starter.median;
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
    && pool.every((c) => !(c.kind !== 'melee' && c.median > starter.median));

  return {
    median, lo, hi, banned: banned.map((c) => c.id), draws: pool.length, meleeLocked,
  };
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
    byDex.get(dex).set(p[ix.start], {
      id: p[ix.start],
      kind: p[ix.kind],
      median: Number(p[ix.median_s]),
      lo: Number(p[ix.boot_lo]),
      hi: Number(p[ix.boot_hi]),
    });
  }
  return byDex;
}

function openingsFromSweep(sweepFile, data = loadData()) {
  const sweep = loadSweep(sweepFile);
  const out = [];
  for (const mon of data.dex) {
    const rows = sweep.get(mon.dex);
    if (!rows || !rows.has(mon.start)) {
      throw new Error(`sweep has no starter for ${mon.dex} ${mon.start}`);
    }
    const starter = rows.get(mon.start);
    const candidates = [];
    for (const [id, row] of rows) {
      if (id === mon.start || row.kind === 'buff') continue;
      candidates.push(row);
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
