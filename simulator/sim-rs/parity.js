// Bit-exact parity check between sim/match.js and the Rust port.
// JS runs each case with Math.sin/cos/atan2/pow wrapped to record
// [fn, a, b, out]; Rust replays that trace (asserting identical inputs) and
// must return the same result bits.
//
//   node sim-rs/parity.js            (from the repo root, after cargo build --release)
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
const BIN = path.join(__dirname, 'target', 'release', 'pokesim');
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'pokesim-parity-'));

// `a ** b` cannot be intercepted, so load copies where it is Math.pow (same V8 routine).
const POW_EDITS = {
  'match.js': [['(t / 60) ** 1.6', 'Math.pow(t / 60, 1.6)'], ['0.0015 ** dt', 'Math.pow(0.0015, dt)']],
  'rules.js': [['(level ** 1.75)', 'Math.pow(level, 1.75)'], ['pow ** 0.35', 'Math.pow(pow, 0.35)']],
};
fs.mkdirSync(path.join(TMP, 'sim'));
for (const file of ['match.js', 'rules.js', 'rng.js', 'data.js']) {
  let src = fs.readFileSync(path.join(ROOT, 'sim', file), 'utf8');
  for (const [from, to] of POW_EDITS[file] || []) {
    if (!src.includes(from)) throw new Error(`${file}: pattern not found: ${from}`);
    src = src.replace(from, to);
  }
  fs.writeFileSync(path.join(TMP, 'sim', file), src);
}
fs.symlinkSync(path.join(ROOT, 'v3'), path.join(TMP, 'v3'));

const { runMatch } = require(path.join(TMP, 'sim', 'match.js'));
const { loadData } = require(path.join(TMP, 'sim', 'data.js'));
const data = loadData();

const real = { sin: Math.sin, cos: Math.cos, atan2: Math.atan2, pow: Math.pow };
let log = null;
Math.sin = (x) => { const r = real.sin(x); if (log) log.push(1, x, 0, r); return r; };
Math.cos = (x) => { const r = real.cos(x); if (log) log.push(2, x, 0, r); return r; };
Math.atan2 = (y, x) => { const r = real.atan2(y, x); if (log) log.push(3, y, x, r); return r; };
Math.pow = (x, y) => { const r = real.pow(x, y); if (log) log.push(4, x, y, r); return r; };

const tables = [];
for (let i = 0; i < 41; i++) tables.push(1.1 ** i);
for (let i = 0; i < 9; i++) tables.push(1.07 ** i);
for (let i = 0; i < 11; i++) tables.push(0.92 ** i);
const tablesFile = path.join(TMP, 'tables.bin');
fs.writeFileSync(tablesFile, Buffer.from(new Float64Array(tables).buffer));

// Every start kind, melee and ranged, status moves, healers late, both bots, cards off.
const CASES = [
  [791, 'psychic', 1], [791, 'psychic', 2], [1000, 'shadow-ball', 1], [1000, 'metal-claw', 3],
  [802, 'karate-chop', 1], [802, 'aura-sphere', 4], [395, 'water-gun', 5], [242, 'hyper-voice', 6],
  [16, 'gust', 7], [252, 'razor-leaf', 8], [4, 'ember', 9], [25, 'thunder-shock', 10],
  [594, 'water-gun', 11], [1007, 'aura-sphere', 12], [113, 'body-slam', 13], [150, 'confusion', 14],
];
const beamCase = data.dex.find((m) => data.moves[m.start].kind === 'beam');
CASES.push([beamCase.dex, beamCase.start, 15]);
const SIMULATED = new Set(['melee', 'beam', 'orbit', 'nova', 'projectile', 'boomerang']);
const randomCount = Number((process.argv.find((a) => a.startsWith('--random=')) || '--random=0').split('=')[1]);
let r = 0x5eed;
const roll = () => { r ^= r << 13; r >>>= 0; r ^= r >> 17; r ^= r << 5; r >>>= 0; return r / 4294967296; };
for (let k = 0; k < randomCount; k++) {
  const mon = data.dex[Math.floor(roll() * data.dex.length)];
  const cands = [...new Set([mon.start, ...mon.pool])].filter((id) => SIMULATED.has(data.moves[id].kind));
  CASES.push([mon.dex, cands[Math.floor(roll() * cands.length)], 1 + Math.floor(roll() * 200)]);
}
const EXTRA = [
  { args: ['--bot', 'line'], opts: { bot: 'line' }, c: [791, 'psychic', 3] },
  { args: ['--bot', 'line'], opts: { bot: 'line' }, c: [802, 'karate-chop', 2] },
  { args: ['--lvl1'], opts: { cards: false }, c: [1000, 'shadow-ball', 2] },
];

function bits(x) {
  const b = Buffer.alloc(8);
  b.writeDoubleLE(x);
  return b.toString('hex');
}

let pass = 0;
let fail = 0;
const all = CASES.map((c) => ({ args: [], opts: {}, c })).concat(EXTRA);
for (const { args, opts, c } of all) {
  const [dex, start, seed] = c;
  const mon = data.byDex.get(dex);
  if (!data.moves[start] || !(mon.pool.includes(start) || mon.start === start)) {
    throw new Error(`case ${dex} ${start}: not a candidate move`);
  }
  log = [];
  const js = runMatch({ mon: { ...mon, start }, seed, seconds: 900, cards: true, bot: 'repulse', data, ...opts });
  const trace = path.join(TMP, `trace_${dex}_${start}_${seed}.bin`);
  fs.writeFileSync(trace, Buffer.from(new Float64Array(log).buffer));
  const calls = log.length / 4;
  log = null;
  let rs;
  try {
    const out = execFileSync(BIN, ['replay', trace, tablesFile, String(dex), start, String(seed), ...args],
      { cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'] }).toString();
    rs = JSON.parse(out);
  } catch (err) {
    fail++;
    console.log(`FAIL ${dex} ${start} seed ${seed} ${args.join(' ')}: ${String(err.stderr || err.message).trim().split('\n').slice(-2).join(' | ')}`);
    continue;
  }
  const keys = ['time', 'kills', 'level', 'capped', 'statusIgnored', 'hp', 'maxHp', 'hpFrac'];
  const bad = keys.filter((k) => (typeof js[k] === 'number' ? bits(js[k]) !== bits(rs[k]) : js[k] !== rs[k]));
  if (bad.length) {
    fail++;
    console.log(`FAIL ${dex} ${start} seed ${seed}: ${bad.map((k) => `${k} js=${js[k]} rs=${rs[k]}`).join(', ')}`);
  } else {
    pass++;
    console.log(`ok   ${dex} ${start} seed ${seed} ${args.join(' ')}  t=${js.time.toFixed(2)} kills=${js.kills} lvl=${js.level} (${calls} math calls)`);
  }
}
if (process.env.KEEP_TRACES) console.log(`traces kept in ${TMP}`);
else fs.rmSync(TMP, { recursive: true, force: true });
console.log(`${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
