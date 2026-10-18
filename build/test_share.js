/* Ida y vuelta del enlace de colección. node build/test_share.js */
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const codec = require('../src/share.js');

const same = (got, exp) => assert.deepStrictEqual(got, exp);

function round(dex, shiny, name) {
  const payload = codec.encodeCollection(dex, shiny, name);
  assert.match(payload, /^[\w-]+$/);
  assert.ok(!payload.includes('+') && !payload.includes('/') && !payload.includes('='));
  const back = codec.decodeCollection(payload);
  assert.ok(back);
  const wantDex = [...new Set(dex.filter(n => Number.isInteger(n) && n > 0))].sort((a, b) => a - b);
  const wantShiny = [...new Set(shiny.filter(n => Number.isInteger(n) && n > 0))].sort((a, b) => a - b);
  same(back.dex, wantDex);
  same(back.shiny, wantShiny);
  same(back.name, codec.cleanName(name));
  same(codec.decodeCollection(codec.encodeCollection(dex, shiny, name)), back);
  return payload;
}

round([], [], '');
round([1], [], '');
round([1024], [1024], '');
round([3, 1, 3, 0, -4, 1.5], [3, 7], '  Ana  ');
round([25, 6, 150], [25], 'José');
round([4, 7, 1], [7], 'Felipe');
round([386, 1, 151], [], 'a'.repeat(40));
assert.equal(codec.cleanName('a'.repeat(40)).length, 24);
assert.equal(codec.decodeCollection(''), null);
assert.equal(codec.decodeCollection('!!!'), null);
assert.equal(codec.decodeCollection('AAAA'), null);
assert.equal(codec.decodeCollection(codec.encodeCollection([5], [9], 'x').slice(0, -2) + '@@'), null);

const pokedex = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'pokedex_export.json'), 'utf8'));
const all = pokedex.map(p => p.dex).sort((a, b) => a - b);
const fullPayload = round(all, all.slice(), '');
const typicalDex = all.filter(d => d <= 386);
const typicalShiny = typicalDex.filter(d => d % 20 === 1);
const typicalPayload = round(typicalDex, typicalShiny, '');

const es = 'https://survivortiers.pages.dev/coleccion#c=';
const en = 'https://survivortiers.pages.dev/en/coleccion#c=';
const fullEs = es.length + fullPayload.length;
const fullEn = en.length + fullPayload.length;
const typEs = es.length + typicalPayload.length;
const typEn = en.length + typicalPayload.length;
assert.ok(fullEs < 500 && fullEn < 500, 'full link should stay short');
assert.ok(typEs < fullEs && typEn < fullEn, 'a gen 1–3 save is shorter than a full dex');
assert.equal(typicalDex.length > 300, true);

console.log('round-trip ok');
console.log('full collection: ' + all.length + ' owned, payload ' + fullPayload.length +
  '  es URL ' + fullEs + '  en URL ' + fullEn);
console.log('typical collection (dex <= 386, ' + typicalDex.length + ' owned, ' + typicalShiny.length +
  ' shiny): payload ' + typicalPayload.length + '  es URL ' + typEs + '  en URL ' + typEn);
