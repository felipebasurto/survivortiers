// Usage:
//   node sim/sweep_starters.js 1/4   (run part 1 of 4; repeat for 2/4, 3/4, 4/4)
//   node sim/sweep_starters.js merge (combine parts into the output CSVs)
const fs = require('fs');
const os = require('os');
const path = require('path');
const { Worker, isMainThread, parentPort, workerData } = require('worker_threads');
const { loadData } = require('./data');
const { runSpecies } = require('./rank');
const { DT } = require('./match');

// Only kinds that cast() in match.js actually fires. Other kinds (aura, cone,
// chain, dash, ...) would deal no damage and give misleading survival times.
const SIMULATED_KINDS = new Set(['melee', 'beam', 'orbit', 'nova', 'projectile', 'boomerang']);
const SEEDS = 200;
const SECONDS = 900;
const BOT = 'repulse';
const OUT_DIR = path.join(__dirname, 'out');
const PARTS_DIR = path.join(OUT_DIR, 'sweep_parts');
const OUT_LONG = path.join(OUT_DIR, 'starter_sweep.csv');
const OUT_BEST = path.join(OUT_DIR, 'rank_best_starter.csv');
const OLD_RANK = path.join(OUT_DIR, 'rank_200.csv');

function startCandidates(mon, data) {
  const ids = new Set([mon.start, ...(mon.pool || [])]);
  return [...ids].filter((id) => data.moves[id] && SIMULATED_KINDS.has(data.moves[id].kind));
}

function buildTasks(data) {
  const tasks = [];
  for (const mon of data.dex) {
    for (const start of startCandidates(mon, data)) tasks.push({ dex: mon.dex, start });
  }
  return tasks;
}

function workerMain() {
  const data = loadData();
  for (const task of workerData.tasks) {
    const mon = data.byDex.get(task.dex);
    const row = runSpecies({ ...mon, start: task.start }, {
      seeds: SEEDS, seconds: SECONDS, cards: true, bot: BOT, dt: DT, data,
    });
    parentPort.postMessage({
      ...row, start: task.start, kind: data.moves[task.start].kind,
    });
  }
}

async function runPart(part, nparts) {
  const data = loadData();
  const all = buildTasks(data);
  const tasks = all.filter((_, i) => i % nparts === part - 1);
  const workers = Math.max(1, os.availableParallelism() - 1);
  const chunks = Array.from({ length: workers }, () => []);
  tasks.forEach((task, i) => chunks[i % workers].push(task));
  console.log(`part ${part}/${nparts}: ${tasks.length} of ${all.length} candidates, ${workers} workers`);

  const rows = [];
  await Promise.all(chunks.map((chunk) => new Promise((resolve, reject) => {
    const worker = new Worker(__filename, { workerData: { tasks: chunk } });
    worker.on('message', (row) => {
      rows.push(row);
      if (rows.length % 200 === 0) console.log(`  ${rows.length}/${tasks.length}`);
    });
    worker.on('error', reject);
    worker.on('exit', (code) => (code === 0 ? resolve() : reject(new Error(`worker exit ${code}`))));
  })));

  fs.mkdirSync(PARTS_DIR, { recursive: true });
  const file = path.join(PARTS_DIR, `part_${part}_of_${nparts}.jsonl`);
  fs.writeFileSync(file, rows.map((row) => JSON.stringify(row)).join('\n') + '\n');
  console.log(`wrote ${file} (${rows.length} runs)`);
}

function csvEscape(value) {
  const text = String(value);
  if (/[",\n]/.test(text)) return '"' + text.replace(/"/g, '""') + '"';
  return text;
}

function num(value) {
  if (value === '' || value == null || Number.isNaN(value)) return '';
  return String(Math.round(value * 1000) / 1000);
}

function readOldRank() {
  const oldRank = new Map();
  if (!fs.existsSync(OLD_RANK)) return oldRank;
  const lines = fs.readFileSync(OLD_RANK, 'utf8').split('\n')
    .filter((line) => line && !line.startsWith('#') && !line.startsWith('dex,'));
  lines.forEach((line, i) => oldRank.set(Number(line.split(',')[0]), i + 1));
  return oldRank;
}

function mergeParts() {
  const files = fs.readdirSync(PARTS_DIR).filter((f) => f.endsWith('.jsonl'));
  const rows = files.flatMap((f) => fs.readFileSync(path.join(PARTS_DIR, f), 'utf8')
    .split('\n').filter(Boolean).map((line) => JSON.parse(line)));
  rows.sort((a, b) => a.dex - b.dex || a.start.localeCompare(b.start));
  console.log(`merged ${files.length} parts, ${rows.length} runs`);

  const longCols = 'dex,name,start,kind,n,median_s,mean_s,boot_lo,boot_hi,p10_s,p90_s,median_kills,median_lvl,status_ignored';
  const longLines = [
    `# barrido: todos los movimientos simulados del pool como inicial. seeds=1-${SEEDS} seconds=${SECONDS} bot=${BOT}`,
    longCols,
  ];
  for (const r of rows) {
    longLines.push([
      r.dex, csvEscape(r.name), r.start, r.kind, r.n,
      num(r.median_s), num(r.mean_s), num(r.boot_lo), num(r.boot_hi),
      num(r.p10_s), num(r.p90_s), num(r.median_kills), num(r.median_lvl), r.status_ignored,
    ].join(','));
  }
  fs.writeFileSync(OUT_LONG, longLines.join('\n') + '\n');

  const groups = new Map();
  for (const row of rows) {
    if (!groups.has(row.dex)) groups.set(row.dex, []);
    groups.get(row.dex).push(row);
  }
  const best = [];
  for (const group of groups.values()) {
    group.sort((a, b) => b.median_s - a.median_s || b.mean_s - a.mean_s || a.start.localeCompare(b.start));
    const top = group[0];
    const alt = group[1];
    best.push({
      ...top,
      n_candidates: group.length,
      alt_start: alt ? alt.start : '',
      alt_median_s: alt ? alt.median_s : '',
    });
  }
  best.sort((a, b) => b.median_s - a.median_s || b.mean_s - a.mean_s || a.dex - b.dex);

  const oldRank = readOldRank();
  const bestCols = 'rank,dex,name,best_start,best_kind,median_s,mean_s,boot_lo,boot_hi,p10_s,p90_s,median_kills,median_lvl,status_ignored,n_candidates,alt_start,alt_median_s,rank_old_200';
  const bestLines = [
    `# mejor movimiento inicial por especie. seeds=1-${SEEDS} seconds=${SECONDS} bot=${BOT}`,
    bestCols,
  ];
  best.forEach((r, i) => {
    bestLines.push([
      i + 1, r.dex, csvEscape(r.name), r.start, r.kind,
      num(r.median_s), num(r.mean_s), num(r.boot_lo), num(r.boot_hi),
      num(r.p10_s), num(r.p90_s), num(r.median_kills), num(r.median_lvl), r.status_ignored,
      r.n_candidates, r.alt_start, num(r.alt_median_s), oldRank.get(r.dex) || '',
    ].join(','));
  });
  fs.writeFileSync(OUT_BEST, bestLines.join('\n') + '\n');
  console.log(`wrote ${OUT_LONG}`);
  console.log(`wrote ${OUT_BEST} (${best.length} species)`);
}

async function cli() {
  const arg = process.argv[2] || '1/1';
  if (arg === 'merge') return mergeParts();
  const [part, nparts] = arg.split('/').map(Number);
  return runPart(part, nparts);
}

if (isMainThread) {
  cli().catch((err) => {
    console.error(err);
    process.exit(1);
  });
} else {
  workerMain();
}
