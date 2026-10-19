const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const { openingValue, openingsFromSweep, ownerView } = require('../repertorio');

const cases = require('./repertorio_cases.json');

test('opening value matches the shared cases', () => {
  for (const row of cases) {
    const got = openingValue(row.starter, row.candidates, row.bans);
    assert.deepEqual(got, row.expect, row.name);
  }
});

// Frozen rows (test/fixtures), so a new sim run never moves this test. By hand: the melee penalty puts the
// Karate Chop starter at 72.799 * 0.8 = 58.24; Sustituto scores 0 for the owner. Five moves tie at the starter's
// value, so the three bans go by id (Golpe Cuerpo, Lengüetazo, Ataque Rápido). The six draws left are worth
// (62.922 + 105.936 + 72.236 + 145.938 + 58.24 + 58.24) / 6 = 83.918 with Tackle and Sustituto not beating the starter.
test('Marshadow bans the three worst and expects the mean of the rest', () => {
  const sweep = path.join(__dirname, 'fixtures', 'solo_sweep_marshadow.csv');
  const row = openingsFromSweep(sweep, { dex: [{ dex: 802, start: 'karate-chop' }] })[0];
  assert.deepEqual(row.banned, ['body-slam', 'lick', 'quick-attack']);
  assert.equal(row.draws, 6);
  assert.equal(row.rank, 83.918);
  assert.equal(row.meleeLocked, false);
});

test('Gengar never plays a melee draw, Sustituto is never played, other melee takes the penalty', () => {
  const melee = { id: 'lick', kind: 'melee', median: 100, lo: 90, hi: 110, rank: 50, rankLo: 40, rankHi: 60 };
  assert.equal(ownerView({ dex: 94 }, melee).rank, 0);
  assert.equal(ownerView({ dex: 95 }, melee).rank, 40);
  const turret = { id: 'substitute', kind: 'turret', median: 100, lo: 90, hi: 110, rank: 50, rankLo: 40, rankHi: 60 };
  assert.equal(ownerView({ dex: 95 }, turret).rank, 0);
  const ranged = { id: 'shadow-ball', kind: 'projectile', median: 100, lo: 90, hi: 110, rank: 50, rankLo: 40, rankHi: 60 };
  assert.equal(ownerView({ dex: 94 }, ranged).rank, 50);
});
