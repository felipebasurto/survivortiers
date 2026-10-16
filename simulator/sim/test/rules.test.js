const test = require('node:test');
const assert = require('node:assert/strict');
const { loadData } = require('../data');
const {
  xpFor, typeMult, strikeDamage, inMelee, keepDistance, pickCard, legalCards,
  healAmount, pulseHealer, pulseShield, quantile, freshState, derive, applyCard,
} = require('../rules');

const data = loadData();

test('xp to leave level 1 is 62', () => {
  assert.equal(xpFor(1), 62);
});

test('ember strike is dmg times attack times type', () => {
  const ember = data.moves.ember.levels[0];
  const mult = typeMult(data.tmult, ember.type, ['normal']);
  const dealt = strikeDamage(ember.dmg, 1, mult, 1);
  assert.equal(mult, 1);
  assert.equal(dealt, ember.dmg * 1 * mult);
});

test('melee arc hits in front and misses behind', () => {
  const arc = 1.63;
  const radius = 85;
  assert.equal(inMelee(0, 0, 0, arc, radius, 40, 0, 10), true);
  assert.equal(inMelee(0, 0, 0, arc, radius, -40, 0, 10), false);
});

test('a level-5 arc above two pi is a full circle', () => {
  assert.equal(inMelee(0, 0, 0, 14.67, 75, -40, 0, 10), true);
});

test('keep distance follows the move kind', () => {
  const ember = data.moves.ember.levels[0];
  const whip = data.moves['vine-whip'].levels[0];
  assert.equal(keepDistance(ember), 0.75 * ember.speed * ember.life);
  assert.equal(keepDistance(whip), 0.55 * whip.radius);
});

test('card priority upgrades the attack, then the evolution gate, then the evolution', () => {
  const ember = data.moves.ember;
  const fresh = freshState();
  assert.equal(pickCard(['up', 'sd', 'pow'], fresh, ember), 'up');
  assert.equal(pickCard(['pow', 'cor', 'run'], fresh, ember), 'pow');
  assert.equal(pickCard(['hd', 'evo', 'sd'], fresh, ember), 'sd');
  const maxed = freshState();
  maxed.moveLvl = 5;
  assert.equal(pickCard(['sd', 'pow', 'hd'], maxed, ember), 'pow');
  maxed.cards.pow = 1;
  assert.equal(pickCard(['sd', 'evo', 'hd'], maxed, ember), 'evo');
  assert.equal(legalCards(fresh, ember, ember && data.dex[0].pool).includes('evo'), false);
});

test('one power card multiplies attack by 1.1 and coraza stops at 70 percent', () => {
  const mon = { hp: 100, atk: 1, spd: 100, types: ['normal'] };
  const move = { kind: 'projectile' };
  const state = freshState();
  applyCard(state, 'pow');
  const powered = derive(mon, move, state, data.moves, false);
  assert.ok(Math.abs(powered.atk - 1.1) < 1e-9);
  state.cards.cor = 12;
  const armored = derive(mon, move, state, data.moves, false);
  assert.equal(armored.red, 0.7);
  state.hd = 1;
  state.hdT = 1;
  state.hdStacks = 1;
  const cap = derive(mon, { kind: 'melee' }, state, data.moves, false);
  assert.equal(cap.melee, 0.75);
  assert.ok(cap.red <= 0.8);
});

test('a healer restores 7 percent inside 150px and a second shield does not stack', () => {
  assert.ok(Math.abs(healAmount(100, 1, 1) - 7) < 1e-9);
  const near = { x: 100, y: 0, hp: 50, max: 100, shield: 0, shieldT: 0 };
  const far = { x: 200, y: 0, hp: 50, max: 100, shield: 0, shieldT: 0 };
  pulseHealer(0, 0, [near, far], 1, 1);
  assert.equal(near.hp, 57);
  assert.equal(far.hp, 50);
  const ally = { x: 10, y: 0, hp: 80, max: 100, shield: 0, shieldT: 0 };
  pulseShield(0, 0, [ally]);
  assert.equal(ally.shield, 35);
  pulseShield(0, 0, [ally]);
  assert.equal(ally.shield, 35);
});

test('burn 1 is a flag and does not become damage', () => {
  const ember = data.moves.ember.levels[0];
  const status = require('../rules').readStatus(ember);
  assert.equal(ember.burn, 1);
  assert.equal(status.burn, 0);
  assert.equal(status.ignored, true);
});

test('median of four sorted values is the average of the middle pair', () => {
  assert.equal(quantile([1, 2, 3, 4], 0.5), 2.5);
  assert.equal(quantile([1, 2, 3, 4], 0.1), 1.3);
});
