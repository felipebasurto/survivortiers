const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { loadData } = require('../data');
const { runMatch } = require('../match');
const { summarize, formatRanking } = require('../rank');

const data = loadData();

test('three species write three rows and each median sits inside its own runs', () => {
  const rows = [];
  for (const dex of [1, 4, 7]) {
    const mon = data.byDex.get(dex);
    const runs = [];
    for (let seed = 1; seed <= 4; seed++) {
      runs.push(runMatch({ mon, seed, seconds: 1.5, cards: false, bot: 'line', data }));
    }
    const row = summarize(mon, runs);
    const times = runs.map((run) => run.time);
    assert.ok(row.median_s >= Math.min(...times) - 1e-9);
    assert.ok(row.median_s <= Math.max(...times) + 1e-9);
    assert.ok(row.boot_lo <= row.median_s + 1e-9);
    assert.ok(row.boot_hi >= row.median_s - 1e-9);
    rows.push(row);
  }
  const csv = formatRanking(rows, { step: 0.05, seeds: 4, seconds: 1.5, bot: 'line' });
  const file = path.join(os.tmpdir(), 'pokesurvivor-rank-test.csv');
  fs.writeFileSync(file, csv);
  const text = fs.readFileSync(file, 'utf8');
  assert.match(text, /sin mejoras permanentes, un movimiento, sin grietas, sin jefes, controlador compartido/);
  const dataRows = text.trim().split('\n').filter((line) => line && !line.startsWith('#') && !line.startsWith('dex,'));
  assert.equal(dataRows.length, 3);
});
