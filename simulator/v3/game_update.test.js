'use strict';
// The PokéSurvivor update (66610d9, 5a23d49) against the vendored game sources: move stats in v3_data.json,
// the physical/special split, monotype, start choices and pool sizes.
//   node --test simulator/v3/game_update.test.js
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const GAME = path.resolve(__dirname, '../vendor/pokesurvivor-5a23d49');

global.window = global;
global.G = {
  Icons: new Proxy({}, { get: () => () => '' }),
  Weather: { mult: () => 1, speedFor: () => 1 },
};
for (const f of ['js/core/util.js', 'js/data/types.js', 'js/systems/stats.js', 'js/data/moves.js', 'js/data/starters.js', 'js/entities/player.js']) {
  (0, eval)(fs.readFileSync(path.join(GAME, f), 'utf8'));
}

const raw = JSON.parse(fs.readFileSync(path.join(__dirname, 'v3_data.json'), 'utf8'));
const data = { moves: raw.moves, dex: raw.dex, byDex: new Map(raw.dex.map((mon) => [mon.dex, mon])) };
const NEW = [
  'dragon-claw', 'play-rough', 'flame-charge', 'u-turn', 'dragon-breath', 'ancient-power', 'hyper-beam', 'solar-beam', 'rapid-spin',
  'rolling-kick', 'outrage', 'gyro-ball', 'night-slash', 'whirlpool', 'sand-tomb', 'ominous-wind', 'seed-bomb', 'electro-ball', 'acid-spray',
  'signal-beam', 'power-gem', 'mirror-shot', 'energy-ball', 'mist-ball', 'air-slash', 'ice-shard', 'shadow-sneak', 'draining-kiss',
  'sucker-punch', 'thunder-wave', 'rock-tomb', 'freeze-dry', 'dynamic-punch', 'extrasensory', 'whirlwind', 'vacuum-wave', 'disarming-voice',
  'magnitude',
];
const SHAPE = ['cd', 'dmg', 'radius', 'count', 'speed', 'life', 'size', 'spread', 'pierce', 'width', 'arc', 'homing', 'bounce', 'charge', 'knock', 'pull', 'stun', 'drain', 'dur', 'rate', 'range', 'burn', 'poison', 'slow'];

test('the 38 new moves exist in v3_data and in the game', () => {
  assert.equal(NEW.length, 38);
  for (const id of NEW) {
    assert.ok(data.moves[id], `${id} missing from v3_data`);
    assert.ok(G.Moves.BY_ID[id], `${id} missing from the game`);
  }
});

test('every level of every move matches G.Moves.instance (damage, cooldown, range, shape params)', () => {
  let checked = 0;
  for (const [id, mv] of Object.entries(data.moves)) {
    for (const lv of mv.levels) {
      const g = G.Moves.instance(id, lv.lvl);
      assert.equal(g.kind, lv.kind, `${id} L${lv.lvl} kind`);
      assert.equal(g.type, lv.type, `${id} L${lv.lvl} type`);
      assert.equal(g.cat, lv.cat, `${id} L${lv.lvl} cat`);
      for (const k of SHAPE) {
        const a = g[k] ?? undefined, b = lv[k] ?? undefined;
        if (a === undefined && b === undefined) continue;
        assert.ok(Math.abs((a ?? 0) - (b ?? 0)) < 1e-9, `${id} L${lv.lvl} ${k}: game ${a}, data ${b}`);
      }
      checked++;
    }
  }
  assert.ok(checked > 400);
});

test('the physical/special split follows the game, buffs buff their own side', () => {
  const phys = (id) => G.Moves.BY_ID[id].cat;
  for (const id of ['dragon-claw', 'play-rough', 'rapid-spin', 'seed-bomb', 'magnitude', 'dynamic-punch', 'sucker-punch']) assert.equal(phys(id), 'physical', id);
  for (const id of ['hyper-beam', 'whirlpool', 'thunder-wave', 'extrasensory', 'air-slash', 'draining-kiss', 'energy-ball']) assert.equal(phys(id), 'special', id);
  assert.equal(data.moves['swords-dance'].levels[0].stat, 'patk');
  assert.equal(data.moves['dragon-dance'].levels[0].stat, 'patk');
  assert.equal(data.moves['nasty-plot'].levels[0].stat, 'satk');
});

test('the new melee moves are melee in the data', () => {
  assert.equal(data.moves['dragon-claw'].levels[0].kind, 'melee');
  assert.equal(data.moves['play-rough'].levels[0].kind, 'melee');
});

test('monotype: +20 % with the own type only, never for dual types', () => {
  const pl = (types) => {
    const p = Object.create(G.Player.prototype);
    p.baseAtk = 100;
    p.atkMul = 1;
    p.buffs = { atk: { n: 0, amount: 0 }, patk: { n: 0, amount: 0 }, satk: { n: 0, amount: 0 } };
    p.mon = { pa: 100, sa: 100, atk: 100, types };
    return p;
  };
  assert.equal(G.Player.MONO_K, 1.2);
  assert.equal(pl(['psychic']).atkFor({ cat: 'special', type: 'psychic' }) / pl(['psychic']).atkFor({ cat: 'special', type: 'ghost' }), 1.2);
  assert.equal(pl(['grass', 'poison']).atkFor({ cat: 'special', type: 'grass' }), pl(['grass', 'poison']).atkFor({ cat: 'special', type: 'ghost' }));
});

test('starters.js startChoices keeps the stock attack, so Psyduck can go back to Confusión', () => {
  const psyduck = data.byDex.get(54);
  G.DEX_BY = { 54: { dex: 54, types: psyduck.types } };
  const choices = G.startChoices(54);
  assert.ok(choices.includes('confusion'), `choices ${choices}`);
  assert.ok(choices.every((id) => G.Moves.BY_ID[id].kind !== 'buff'));
  assert.notEqual(G.Moves.BY_ID.confusion.type, psyduck.types[0]);
  assert.equal(psyduck.start, 'confusion');
});

test('player.addMove keeps the move in use: learning does not switch to the new one', () => {
  const starter = G.Moves.instance('ember', 1);
  const pl = Object.create(G.Player.prototype);
  Object.assign(pl, {
    slots: [[starter]], moves: [starter], active: 0, maxMoves: 4,
    hasMove(id) { return this.moves.some((m) => m.id === id); },
    arrange() {},
  });
  G.Game = { st: { time: 0 } };
  assert.equal(pl.addMove('tackle'), true);
  assert.equal(pl.active, 0);
  assert.equal(pl.slots.length, 2);
});

test('pools match G.Moves.poolFor for every species, and the new moves widened them', () => {
  let widened = 0;
  for (const mon of data.dex) {
    const game = G.Moves.poolFor({ types: mon.types }).filter((id) => G.Moves.BY_ID[id].kind !== 'buff');
    const sim = mon.pool.filter((id) => data.moves[id].kind !== 'buff');
    assert.deepEqual([...sim].sort(), [...game].sort(), `${mon.name} pool`);
    if (sim.some((id) => NEW.includes(id))) widened++;
  }
  assert.ok(widened > data.dex.length * 0.9, `${widened} species got a new move`);
});
