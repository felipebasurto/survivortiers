const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const { openingValue, openingsFromSweep } = require('../repertorio');

const cases = require('./repertorio_cases.json');

test('opening value matches the shared cases', () => {
  for (const row of cases) {
    const got = openingValue(row.starter, row.candidates, row.bans);
    assert.deepEqual(got, row.expect, row.name);
  }
});

test('Marshadow bans the three worst and expects the mean of the rest', () => {
  const sweep = path.join(__dirname, '..', '..', 'results', 'fixed_group', 'g2p2', 'starter_sweep.csv');
  const row = openingsFromSweep(sweep).find((r) => r.dex === 802);
  assert.deepEqual(row.banned, ['body-slam', 'lick', 'tackle']);
  assert.equal(row.draws, 6);
  assert.equal(row.median, 96.875);
  assert.equal(row.meleeLocked, false);
});
