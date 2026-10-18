// Pruebas de src/tools.js (buscador por tipos y planificador) con los datos reales. No se ejecuta sola: la llama
// build/test_tools.py con un paquete JSON que ese archivo arma desde data/ y build/out/. Sale con código 1 si algo falla.
//   node build/test_tools.js /ruta/bundle.json
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const tools = require(path.join(__dirname, '..', 'src', 'tools.js'));
const bundle = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const { game, species, index, slugs, matrix } = bundle;

const failures = [];
const check = (name, fn) => {
  try {
    fn();
  } catch (err) {
    failures.push(name + ': ' + err.message.split('\n')[0]);
  }
};

const TYPES = Object.keys(game.chart);
const byDex = new Map(index.map(p => [p.dex, p]));

check('la tabla suavizada coincide con js/data/types.js', () => {
  for (const a of TYPES) for (const d of TYPES) assert.equal(game.chart[a][d], matrix[a][d], a + '→' + d);
});

check('combos dobles: producto acotado a [0,3, 2,4]', () => {
  for (const a of TYPES) for (const d1 of TYPES) for (const d2 of TYPES) {
    const raw = matrix[a][d1] * matrix[a][d2];
    const want = Math.min(2.4, Math.max(0.3, raw));
    assert.ok(Math.abs(tools.comboMult(game.chart, a, [d1, d2]) - want) < 1e-9, [a, d1, d2].join('/'));
  }
});

check('doble debilidad aparece como ×2,4 y no más', () => {
  const pair = TYPES.flatMap(d1 => TYPES.map(d2 => [d1, d2]))
    .find(([d1, d2]) => TYPES.some(a => matrix[a][d1] * matrix[a][d2] > 2.4));
  assert.ok(pair, 'ningún par de tipos llega a doble debilidad');
  const g = tools.groupWeak(tools.weaknessMap(game.chart, pair));
  assert.ok(g.double.length > 0);
  for (const [, m] of g.double) assert.equal(m, 2.4);
});

check('slugs de las fichas iguales a build/slugs.py', () => {
  for (const p of index) assert.equal(p.dex + '-' + tools.slugOf(p.nameEn), slugs[String(p.dex)], p.nameEn);
});

check('lado físico o especial igual que G.Stats.sideOf', () => {
  for (const p of index) {
    const [pa, sa] = game.dex[String(p.dex)];
    assert.equal(tools.sideOf(pa, sa), sa > pa ? 'special' : 'physical', String(p.dex));
  }
});

const coverageMismatch = [];
check('la cobertura reproduce d[9][0] y d[9][1] de cada build fija', () => {
  const defenders = index.map(p => p.types);
  for (const p of index) {
    const d9 = species.d[String(p.dex)][9];
    const nBoost = d9[5];
    const attacks = d9[2].slice(0, d9[2].length - nBoost);
    const cov = tools.coverage(defenders, tools.attackTypesOf(game.moves, attacks), game.chart);
    if (cov.super !== d9[0] || cov.neutral !== d9[1]) coverageMismatch.push(p.dex);
  }
  assert.equal(coverageMismatch.length, 0, 'dex con cobertura distinta: ' + coverageMismatch.slice(0, 10).join(', '));
});

const swaps = [];
check('cada build recomendada: sin repetidos, máximo 2 potenciadores, ids en el grupo del Pokémon', () => {
  for (const p of index) {
    const rec = tools.recommended(p.dex, species, game);
    const pool = tools.poolOf(p.types, game.pool);
    const ids = rec.group.filter(Boolean);
    assert.equal(new Set(ids).size, ids.length, 'repetido en ' + p.dex);
    assert.ok(ids.length <= tools.PLAN_SLOTS, 'más de cuatro en ' + p.dex);
    assert.ok(tools.boostsOf(game.moves, ids).length <= tools.BOOST_CAP, 'más de dos potenciadores en ' + p.dex);
    for (const id of ids) assert.ok(pool.has(id), id + ' fuera del grupo de ' + p.dex);
    if (rec.swap) swaps.push(p.dex);
  }
});

check('el cambio de danza solo ocurre si la mayoría de ataques es especial', () => {
  for (const dex of swaps) {
    const rec = tools.recommended(dex, species, game);
    const d9 = species.d[String(dex)][9];
    const attacks = d9[2].slice(0, d9[2].length - d9[5]);
    const spec = attacks.filter(id => game.moves[id].c === 'special').length;
    const phys = attacks.length - spec;
    assert.ok(spec > phys || (spec === phys && tools.sideOf(...game.dex[String(dex)]) === 'special'), 'cambio sin motivo en ' + dex);
    assert.equal(rec.swap.to, 'nasty-plot');
    assert.ok(rec.group.includes('nasty-plot') && !rec.group.includes(rec.swap.from), 'el cambio no llegó al grupo ' + dex);
  }
});

check('la URL de una build recomendada se lee igual', () => {
  for (const p of index) {
    const rec = tools.recommended(p.dex, species, game);
    const st = { dex: p.dex, group: rec.group, item: rec.item, cards: rec.cards };
    const search = '?' + tools.encodeState(st);
    const back = tools.decodeState(search, game, species, index, p.dex);
    assert.equal(back.fromUrl, true, String(p.dex));
    assert.deepEqual(back.group, st.group, String(p.dex));
    assert.equal(back.item, st.item, String(p.dex));
    assert.deepEqual(back.cards, st.cards, String(p.dex));
  }
});

check('una URL editada a mano no rompe el estado', () => {
  const back = tools.decodeState('?p=999999&g=nope,tackle,tackle,swords-dance,harden&o=zzz&c=zz', game, species, index, 1);
  assert.equal(back.fromUrl, false);
  assert.equal(back.dex, 1);
  assert.equal(back.item, null);
  assert.equal(back.group.filter(Boolean).length <= tools.PLAN_SLOTS, true);
  const boosts = tools.boostsOf(game.moves, back.group.filter(Boolean));
  assert.ok(boosts.length <= tools.BOOST_CAP);
  assert.deepEqual(back.cards, [null, null, null, null]);
});

check('el tercer potenciador se descarta en la URL', () => {
  const ids = ['swords-dance', 'harden', 'agility'].filter(id => game.moves[id]);
  const dex = [...byDex.keys()].find(d => ids.every(id => tools.poolOf(byDex.get(d).types, game.pool).has(id)));
  assert.ok(dex != null, 'ningún Pokémon tiene los tres potenciadores');
  const back = tools.decodeState('?p=' + dex + '&g=' + ids.join(',') + '&o=-&c=-,-,-,-', game, species, index, dex);
  assert.equal(tools.boostsOf(game.moves, back.group.filter(Boolean)).length, 2);
});

check('avisos de potenciadores: dos danzas, y danza sin ataque de su categoría', () => {
  const both = tools.boostWarnings(game.moves, ['swords-dance', 'dragon-dance', 'tackle', 'ember']);
  assert.ok(both.some(w => w.k === 'both'));
  const noneSpec = tools.boostWarnings(game.moves, ['swords-dance', 'tackle', 'quick-attack', 'ember'].filter(id => game.moves[id]));
  assert.ok(noneSpec.some(w => w.k === 'some' && w.cat === 'physical'), JSON.stringify(noneSpec));
  const none = tools.boostWarnings(game.moves, ['nasty-plot', 'tackle', 'quick-attack']);
  assert.ok(none.some(w => w.k === 'none' && w.cat === 'special'), JSON.stringify(none));
  const fine = tools.boostWarnings(game.moves, ['swords-dance', 'tackle', 'quick-attack']);
  assert.deepEqual(fine, []);
});

check('la categoría de cada movimiento viene del juego (físico o especial)', () => {
  for (const [id, m] of Object.entries(game.moves)) {
    if (m.b) assert.equal(m.c, null, id);
    else assert.ok(m.c === 'physical' || m.c === 'special', id);
  }
  assert.equal(game.moves['tackle'].c, 'physical');
  assert.equal(game.moves['ember'].c, 'special');
});

check('cartas del planificador: cuatro, en orden de prioridad, y con la que evoluciona el ataque dentro', () => {
  for (const p of index) {
    const [order, gate] = species.d[String(p.dex)][10];
    const picks = tools.plannerCards([order, gate]);
    assert.equal(picks.length, tools.PLAN_SLOTS, String(p.dex));
    assert.equal(new Set(picks).size, picks.length, 'repetida en ' + p.dex);
    const pos = picks.map(id => order.indexOf(id));
    assert.deepEqual(pos, [...pos].sort((a, b) => a - b), 'fuera de orden en ' + p.dex);
    if (gate) assert.ok(picks.includes(gate), 'falta la carta que evoluciona en ' + p.dex);
    assert.deepEqual(tools.recommended(p.dex, species, game).cards, picks, String(p.dex));
  }
});

check('la danza de la build recomendada se elige por categoría, sin Danza Espada fija', () => {
  for (const p of index) {
    const rec = tools.recommended(p.dex, species, game);
    const boosts = tools.boostsOf(game.moves, rec.group.filter(Boolean));
    for (const b of boosts) if (b === 'swords-dance') {
      const attacks = tools.attacksOf(game.moves, rec.group.filter(Boolean));
      assert.ok(attacks.some(a => game.moves[a].c === 'physical'), 'Danza Espada sin ataque físico en ' + p.dex);
    }
  }
});

const report = {
  pokemon: index.length,
  coverageMismatch: coverageMismatch.length,
  swapped: swaps.length,
};
if (failures.length) {
  console.error(failures.join('\n'));
  console.error(JSON.stringify(report));
  process.exit(1);
}
console.log('test_tools.js: ' + JSON.stringify(report));
