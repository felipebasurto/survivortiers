const test = require('node:test');
const assert = require('node:assert/strict');
const { loadData } = require('../data');
const { runMatch } = require('../match');
const { typeMult } = require('../rules');

const data = loadData();

function dummy(over) {
  return Object.assign({
    dex: 0, name: 'Dummy', types: ['normal'], hp: 500, spd: 0, atk: 1, r: 10,
    start: 'ember', pool: ['ember', 'swords-dance', 'harden'],
  }, over);
}

test('the same seed replays the same death', () => {
  const mon = data.byDex.get(1);
  const a = runMatch({ mon, seed: 1, seconds: 2, bot: 'repulse', data });
  const b = runMatch({ mon, seed: 1, seconds: 2, bot: 'repulse', data });
  assert.deepEqual(a, b);
});

test('a still dummy takes ember damage of dmg times attack times type', () => {
  const ember = data.moves.ember.levels[0];
  const result = runMatch({
    mon: dummy(),
    seed: 1,
    seconds: 0.4,
    cards: false,
    spawn: false,
    weather: false,
    bot: 'line',
    recordHits: true,
    enemies: [{ x: 90, y: 0, r: 10, hp: 200, spd: 0, dmg: 0, types: ['normal'], beh: 'chase' }],
    data,
  });
  const expected = ember.dmg * 1 * typeMult(data.tmult, 'fire', ['normal']);
  assert.equal(result.hits.length, 1);
  assert.ok(Math.abs(result.hits[0].amount - expected) < 1e-6);
});

test('melee hits the enemy in the arc and misses the one behind', () => {
  const tackle = data.moves.tackle.levels[0];
  const result = runMatch({
    mon: dummy({ start: 'tackle', pool: ['tackle'], atk: 1 }),
    seed: 1,
    seconds: 0.2,
    cards: false,
    spawn: false,
    weather: false,
    bot: 'line',
    enemies: [
      { x: 40, y: 0, r: 10, hp: 100, spd: 0, dmg: 0, types: ['normal'], beh: 'chase' },
      { x: -40, y: 0, r: 10, hp: 100, spd: 0, dmg: 0, types: ['normal'], beh: 'chase' },
    ],
    data,
  });
  assert.ok(Math.abs(result.kills) === 0);
  const again = runMatch({
    mon: dummy({ start: 'tackle', pool: ['tackle'], atk: 1, hp: 500 }),
    seed: 1,
    seconds: 0.2,
    cards: false,
    spawn: false,
    weather: false,
    bot: 'line',
    recordHits: true,
    enemies: [
      { x: 40, y: 0, r: 10, hp: 100, spd: 0, dmg: 0, types: ['normal'], beh: 'chase' },
      { x: -40, y: 0, r: 10, hp: 100, spd: 0, dmg: 0, types: ['normal'], beh: 'chase' },
    ],
    data,
  });
  const dealt = again.hits.reduce((sum, hit) => sum + hit.amount, 0);
  assert.ok(Math.abs(dealt - tackle.dmg) < 1e-6);
  assert.equal(again.hits.length, 1);
});

test('one hp dies on the first contact', () => {
  const result = runMatch({
    mon: dummy({ hp: 1, atk: 0, spd: 0, r: 10 }),
    seed: 1,
    seconds: 1,
    cards: false,
    spawn: false,
    weather: false,
    bot: 'line',
    enemies: [{ x: 0, y: 0, r: 10, hp: 50, spd: 0, dmg: 40, types: ['normal'], beh: 'chase' }],
    data,
  });
  assert.equal(result.capped, false);
  assert.ok(result.time > 0 && result.time <= 0.1);
});

test('the same seed spawns the same enemy types for two different pokemon', () => {
  const slow = dummy({ atk: 0, spd: 0, hp: 99999, start: 'ember' });
  const other = dummy({ atk: 0, spd: 0, hp: 99999, start: 'tackle', name: 'Other' });
  const a = runMatch({ mon: slow, seed: 17, seconds: 4, cards: false, weather: false, bot: 'line', trace: true, data });
  const b = runMatch({ mon: other, seed: 17, seconds: 4, cards: false, weather: false, bot: 'line', trace: true, data });
  assert.deepEqual(a.spawns, b.spawns);
  assert.ok(a.spawns.length > 0);
});

test('each starter kind can run a short match', () => {
  const seen = new Set();
  for (const mon of data.dex) {
    const kind = data.moves[mon.start].kind;
    if (seen.has(kind)) continue;
    seen.add(kind);
    const result = runMatch({ mon, seed: 2, seconds: 0.5, cards: false, bot: 'repulse', data });
    assert.equal(result.capped, true);
    assert.ok(result.time === 0.5);
  }
  assert.equal(seen.size, 6);
});
