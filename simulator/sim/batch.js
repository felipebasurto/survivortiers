const fs = require('fs');
const path = require('path');
const os = require('os');
const { Worker } = require('worker_threads');
const { loadData } = require('./data');
const { runSpecies, formatRanking } = require('./rank');
const { DT } = require('./match');

function parseArgs(argv) {
  const opts = {
    seeds: 200,
    seconds: 900,
    cards: true,
    bot: 'repulse',
    out: path.join('sim', 'out', 'rank_fresh.csv'),
    dex: null,
    reset: false,
    workers: Math.max(1, os.availableParallelism() - 1),
    dt: DT,
  };
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--all') opts.dex = null;
    else if (arg === '--lvl1') opts.cards = false;
    else if (arg === '--reset') opts.reset = true;
    else if (arg === '--dex') opts.dex = argv[++i].split(',').map(Number);
    else if (arg === '--seeds') opts.seeds = Number(argv[++i]);
    else if (arg === '--seconds') opts.seconds = Number(argv[++i]);
    else if (arg === '--bot') opts.bot = argv[++i];
    else if (arg === '--out') opts.out = argv[++i];
    else if (arg === '--workers') opts.workers = Number(argv[++i]);
    else throw new Error('unknown arg ' + arg);
  }
  return opts;
}

function doneDexes(file) {
  if (!fs.existsSync(file)) return new Set();
  const found = new Set();
  for (const line of fs.readFileSync(file, 'utf8').split('\n')) {
    if (!line || line.startsWith('#') || line.startsWith('dex,')) continue;
    found.add(Number(line.split(',')[0]));
  }
  return found;
}

function runOne(mon, opts) {
  return runSpecies(mon, opts);
}

function runPool(dexes, opts, onRow) {
  const size = Math.min(opts.workers, dexes.length);
  const chunks = Array.from({ length: size }, () => []);
  dexes.forEach((dex, i) => chunks[i % size].push(dex));
  return Promise.all(chunks.map((chunk) => new Promise((resolve, reject) => {
    const worker = new Worker(path.join(__dirname, 'worker.js'), {
      workerData: {
        dexes: chunk,
        seeds: opts.seeds,
        seconds: opts.seconds,
        cards: opts.cards,
        bot: opts.bot,
        dt: opts.dt,
      },
    });
    const rows = [];
    worker.on('message', (msg) => {
      if (msg && msg.done) return;
      rows.push(msg);
      if (onRow) onRow(msg);
    });
    worker.on('error', reject);
    worker.on('exit', (code) => {
      if (code === 0) resolve(rows);
      else reject(new Error('worker exited ' + code));
    });
  }))).then((parts) => parts.flat());
}

async function main() {
  const opts = parseArgs(process.argv);
  const data = loadData();
  const all = opts.dex || data.dex.map((mon) => mon.dex);
  if (opts.reset && fs.existsSync(opts.out)) fs.unlinkSync(opts.out);
  const skip = doneDexes(opts.out);
  const todo = all.filter((dex) => !skip.has(dex));
  fs.mkdirSync(path.dirname(opts.out), { recursive: true });
  const fresh = !fs.existsSync(opts.out);
  if (fresh) {
    fs.writeFileSync(opts.out, formatRanking([], {
      step: opts.dt, seeds: opts.seeds, seconds: opts.seconds, bot: opts.bot,
    }));
  }
  let rows = [];
  if (!fresh) {
    rows = parseRows(opts.out);
  }
  const meta = {
    step: opts.dt, seeds: opts.seeds, seconds: opts.seconds, bot: opts.bot,
  };
  const flush = (row) => {
    rows.push(row);
    fs.writeFileSync(opts.out, formatRanking(rows, meta));
    process.stdout.write(row.dex + ' ' + row.median_s.toFixed(2) + 's ' + rows.length + '/' + all.length + '\n');
  };
  const useWorkers = todo.length > 1 && opts.workers > 1;
  process.stdout.write('todo ' + todo.length + ' workers ' + (useWorkers ? Math.min(opts.workers, todo.length) : 1) + '\n');
  if (!useWorkers) {
    for (const dex of todo) {
      flush(runOne(data.byDex.get(dex), Object.assign({ data }, opts)));
    }
  } else {
    await runPool(todo, opts, flush);
  }
}

function parseRows(file) {
  const lines = fs.readFileSync(file, 'utf8').trim().split('\n');
  const rows = [];
  for (const line of lines) {
    if (!line || line.startsWith('#') || line.startsWith('dex,')) continue;
    const c = line.split(',');
    rows.push({
      dex: Number(c[0]), name: c[1], n: Number(c[2]),
      median_s: Number(c[3]), mean_s: Number(c[4]),
      boot_lo: Number(c[5]), boot_hi: Number(c[6]),
      p10_s: Number(c[7]), p90_s: Number(c[8]),
      median_kills: Number(c[9]), median_lvl: Number(c[10]),
      n_cap: Number(c[11]),
      mean_hp_frac: c[12] === '' ? null : Number(c[12]),
      status_ignored: Number(c[13]),
    });
  }
  return rows;
}

if (require.main === module) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}

module.exports = { parseArgs, main };
