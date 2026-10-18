/* Lectura del comando de la consola, filas de la vista shiny y comando de verdad (console/) ejecutado con un
   localStorage falso. node build/test_collection.js */
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const Collection = require('../src/collection.js');

const DAY = 864e5;
const ok = text => {
  const r = Collection.parse(text);
  assert.equal(r.ok, true, 'expected ok for ' + text.slice(0, 80) + ' got ' + JSON.stringify(r));
  return r.c;
};
const fail = (text, reason) => {
  const r = Collection.parse(text);
  assert.deepStrictEqual(r, { ok: false, reason }, text.slice(0, 80));
};

const legacy = ok('{"version":1,"name":"Ana","updated":5,"dex":[1,25,25,0,-3,1.5,"x"],"shiny":[25,151]}');
assert.deepStrictEqual(legacy.dex, [1, 25]);
assert.deepStrictEqual(legacy.shiny, [25, 151]);
assert.deepStrictEqual(legacy.info, {});
assert.equal(legacy.name, 'Ana');
assert.equal(legacy.updated, 5);
assert.deepStrictEqual(Collection.shinyCounts(legacy), { total: 2, wild: 0, gacha: 0, unknown: 2 });
assert.deepStrictEqual(Collection.shinyRows(legacy, { wildOnly: true }), []);

const day = Math.floor(Date.UTC(2026, 9, 1) / DAY);
const v2 = ok(JSON.stringify({ version: 2, name: 'Felipe', updated: 1, dex: [4, 25, 151, 300],
  shiny: [25], shinyInfo: { 25: [0, day], 151: [1, null], 4: [2, day - 3] } }));
assert.deepStrictEqual(v2.shiny, [4, 25, 151], 'shinyInfo keys join the shiny list');
assert.deepStrictEqual(Collection.originOf(v2, 25), 'wild');
assert.deepStrictEqual(Collection.originOf(v2, 151), 'gacha');
assert.deepStrictEqual(Collection.originOf(v2, 4), null);
assert.deepStrictEqual(Collection.originOf(v2, 300), null);
assert.deepStrictEqual(v2.info[151], { from: 'gacha', day: null });
assert.deepStrictEqual(Collection.shinyCounts(v2), { total: 3, wild: 1, gacha: 1, unknown: 1 });

const wrapped = ok(JSON.stringify(JSON.stringify({ version: 2, dex: [1], shiny: [1], shinyInfo: { 1: [1, day] } })));
assert.deepStrictEqual(wrapped.info, { 1: { from: 'gacha', day } });

fail('', 'notJson');
fail('{"dex":[1],', 'notJson');
fail('"hola"', 'notCollection');
fail('[]', 'missingKeys');
fail('{"dex":[1]}', 'missingKeys');
fail('{"shiny":[1]}', 'missingKeys');
fail('{"dex":"1","shiny":[]}', 'missingKeys');
fail('null', 'missingKeys');
for (const bad of [
  '[]', '"x"', '{"0":[0,1]}', '{"025":[0,1]}', '{"-1":[0,1]}', '{"25":[3,1]}', '{"25":[-1,1]}',
  '{"25":[0,1.5]}', '{"25":[0,-1]}', '{"25":[0,200000]}', '{"25":[0]}', '{"25":[0,1,2]}', '{"25":["wild",1]}',
  '{"25":"wild"}', '{"25":[0,"1"]}', '{"25":[0,null,null]}',
]) {
  fail(JSON.stringify({ dex: [25], shiny: [25], shinyInfo: JSON.parse(bad) }), 'badShinyInfo');
}
fail(JSON.stringify({ dex: [25], shiny: [25], shinyInfo: null }), 'badShinyInfo');
fail(JSON.stringify({ dex: [25], shiny: [25], shinyInfo: [] }), 'badShinyInfo');
fail(JSON.stringify({ dex: [25], shiny: [25], shinyInfo: '{}' }), 'badShinyInfo');
ok(JSON.stringify({ dex: [25], shiny: [25], shinyInfo: {} }));
ok(JSON.stringify({ dex: [25], shiny: [25], shinyInfo: { 25: [2, null] } }));
ok(JSON.stringify({ dex: [25], shiny: [25], shinyInfo: { 25: [1, 0] } }));

const rowsOf = c => Collection.shinyRows(c).map(r => r.dex);
const sample = ok(JSON.stringify({ version: 2, dex: [1, 4, 7, 25, 151], shiny: [7, 25, 151, 4, 1], shinyInfo: {
  25: [0, day - 10], 4: [0, day], 151: [1, day - 10], 7: [1, null] } }));
assert.deepStrictEqual(rowsOf(sample), [4, 25, 151, 1, 7], 'newest first, same day by dex, undated last by dex');
assert.deepStrictEqual(Collection.shinyRows(sample, { sort: 'dex' }).map(r => r.dex), [1, 4, 7, 25, 151]);
assert.deepStrictEqual(Collection.shinyRows(sample, { wildOnly: true }).map(r => r.dex), [4, 25]);
assert.deepStrictEqual(Collection.shinyRows(sample, { wildOnly: true, sort: 'dex' }).map(r => r.dex), [4, 25]);
assert.deepStrictEqual(Collection.shinyRows(sample)[0], { dex: 4, from: 'wild', day });

const snippetPath = name => path.join(__dirname, '..', 'console', name);
function runSnippet(file, saves) {
  const store = new Map(Object.entries(saves).map(([k, v]) => [k, JSON.stringify(v)]));
  const ctx = {
    localStorage: { length: store.size, key: i => [...store.keys()][i], getItem: k => (store.has(k) ? store.get(k) : null) },
    console: { log() {}, warn() {}, table() {} },
  };
  vm.createContext(ctx);
  return JSON.parse(JSON.stringify(vm.runInContext(fs.readFileSync(snippetPath(file), 'utf8'), ctx)));
}
const at = Date.UTC(2026, 9, 16, 20, 30);
const save = runSnippet('coleccion.js', {
  'ps.save.Felipe': {
    name: 'Felipe', updated: at, owned: { 1: {}, 4: {}, 25: {}, 151: {} },
    shiny: { 25: { at, from: 'wild' }, 151: { at: at - 5 * DAY, from: 'gacha' }, 4: { from: 'quest' } },
  },
});
assert.equal(save.version, 2);
assert.deepStrictEqual(save.dex, [1, 4, 25, 151]);
assert.deepStrictEqual(save.shiny, [4, 25, 151]);
assert.deepStrictEqual(save.shinyInfo, {
  4: [2, null], 25: [0, Math.floor(at / DAY)], 151: [1, Math.floor((at - 5 * DAY) / DAY)],
});
const imported = ok(JSON.stringify(save));
assert.deepStrictEqual(Collection.shinyCounts(imported), { total: 3, wild: 1, gacha: 1, unknown: 1 });
assert.equal(Collection.originOf(imported, 25), 'wild');

const enSave = runSnippet('coleccion.en.js', {
  'ps.cloud.uid1': { name: 'Ana', updated: 0, owned: { 6: {} }, shiny: { 6: { at, from: 'gacha' } } },
});
assert.deepStrictEqual(enSave.shinyInfo, { 6: [1, Math.floor(at / DAY)] });
assert.equal(ok(JSON.stringify(enSave)).info[6].from, 'gacha');

const linked = Collection.fromLink({ version: 2, name: 'Ana', dex: [1, 25, 151], shiny: [25, 151], gacha: [151] });
assert.deepStrictEqual(Collection.shinyCounts(linked), { total: 2, wild: 1, gacha: 1, unknown: 0 });
const mixedLink = Collection.fromLink({ version: 2, dex: [4, 25, 151], shiny: [4, 25, 151], gacha: [151], unknown: [4] });
assert.deepStrictEqual(Collection.shinyCounts(mixedLink), { total: 3, wild: 1, gacha: 1, unknown: 1 });
assert.deepStrictEqual(Collection.originForLink(imported), { gacha: [151], unknown: [4] });
assert.deepStrictEqual(Collection.originForLink(mixedLink), { gacha: [151], unknown: [4] });
const linkedOld = Collection.fromLink({ version: 1, name: '', dex: [25], shiny: [25], gacha: null });
assert.deepStrictEqual(Collection.originForLink(linkedOld), { gacha: [], unknown: [25] });
assert.deepStrictEqual(Collection.originForLink(sample), { gacha: [7, 151], unknown: [1] }, 'a shiny without origin is unknown');
assert.deepStrictEqual(Collection.originForLink(ok(JSON.stringify({ dex: [1], shiny: [1, 2], shinyInfo: { 1: [0, 1], 2: [1, 2] } }))), { gacha: [2], unknown: [] });
assert.deepStrictEqual(Collection.originForLink(ok('{"dex":[],"shiny":[]}')), { gacha: [], unknown: [] });

console.log('collection ok');
