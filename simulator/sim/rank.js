const fs = require('fs');
const { rng } = require('./rng');
const { quantile } = require('./rules');
const { runMatch } = require('./match');

function bootstrapMedian(times, reps) {
  const n = times.length;
  const roll = rng(0xB007);
  const meds = [];
  for (let i = 0; i < reps; i++) {
    const sample = [];
    for (let j = 0; j < n; j++) sample.push(times[(roll() * n) | 0]);
    sample.sort((a, b) => a - b);
    meds.push(quantile(sample, 0.5));
  }
  meds.sort((a, b) => a - b);
  return { lo: quantile(meds, 0.05), hi: quantile(meds, 0.95) };
}

function summarize(mon, runs) {
  const times = runs.map((run) => run.time).sort((a, b) => a - b);
  const kills = runs.map((run) => run.kills).sort((a, b) => a - b);
  const levels = runs.map((run) => run.level).sort((a, b) => a - b);
  const boot = bootstrapMedian(times, 400);
  const capped = runs.filter((run) => run.capped);
  const mean = times.reduce((sum, value) => sum + value, 0) / times.length;
  const hp = capped.length
    ? capped.reduce((sum, run) => sum + run.hpFrac, 0) / capped.length
    : null;
  return {
    dex: mon.dex,
    name: mon.name,
    n: runs.length,
    median_s: quantile(times, 0.5),
    mean_s: mean,
    boot_lo: boot.lo,
    boot_hi: boot.hi,
    p10_s: quantile(times, 0.1),
    p90_s: quantile(times, 0.9),
    median_kills: quantile(kills, 0.5),
    median_lvl: quantile(levels, 0.5),
    n_cap: capped.length,
    mean_hp_frac: hp,
    status_ignored: runs.some((run) => run.statusIgnored) ? 1 : 0,
  };
}

function runSpecies(mon, opts) {
  const runs = [];
  const seeds = opts.seeds;
  for (let seed = 1; seed <= seeds; seed++) {
    runs.push(runMatch({
      mon,
      seed,
      seconds: opts.seconds,
      cards: opts.cards,
      bot: opts.bot,
      dt: opts.dt,
      data: opts.data,
    }));
  }
  return summarize(mon, runs);
}

function csvEscape(value) {
  const text = String(value);
  if (/[",\n]/.test(text)) return '"' + text.replace(/"/g, '""') + '"';
  return text;
}

function num(value) {
  if (value == null || Number.isNaN(value)) return '';
  return String(Math.round(value * 1000) / 1000);
}

function formatRanking(rows, meta) {
  const head = [
    '# step=' + meta.step,
    'seeds=1-' + meta.seeds,
    'seconds=' + meta.seconds,
    'bot=' + meta.bot,
    'sin mejoras permanentes, un movimiento, sin grietas, sin jefes, controlador compartido',
  ].join(' ');
  const cols = 'dex,name,n,median_s,mean_s,boot_lo,boot_hi,p10_s,p90_s,median_kills,median_lvl,n_cap,mean_hp_frac,status_ignored';
  const sorted = rows.slice().sort((a, b) => b.median_s - a.median_s || b.mean_s - a.mean_s || (b.mean_hp_frac || 0) - (a.mean_hp_frac || 0) || a.dex - b.dex);
  const lines = [head, cols];
  for (const row of sorted) {
    lines.push([
      row.dex, csvEscape(row.name), row.n,
      num(row.median_s), num(row.mean_s), num(row.boot_lo), num(row.boot_hi),
      num(row.p10_s), num(row.p90_s), num(row.median_kills), num(row.median_lvl),
      row.n_cap, num(row.mean_hp_frac), row.status_ignored,
    ].join(','));
  }
  return lines.join('\n') + '\n';
}

function writeRanking(path, rows, meta) {
  fs.mkdirSync(require('path').dirname(path), { recursive: true });
  fs.writeFileSync(path, formatRanking(rows, meta));
}

module.exports = { bootstrapMedian, summarize, runSpecies, formatRanking, writeRanking };
