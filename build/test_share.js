/* Ida y vuelta del enlace de colección (v2), enlaces v1 de antes y rechazos. node build/test_share.js */
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const codec = require('../src/share.js');

const same = (got, exp) => assert.deepStrictEqual(got, exp);
const uniqSorted = list => [...new Set(list.filter(n => Number.isInteger(n) && n > 0))].sort((a, b) => a - b);

function round({ dex, shiny, gacha = null, unknown = [], name = '', view = 'normal' }) {
  const payload = codec.encodeCollection({ dex, shiny, gacha, unknown, name, view });
  assert.match(payload, /^[\w-]+$/);
  assert.ok(!payload.includes('+') && !payload.includes('/') && !payload.includes('='));
  const back = codec.decodeCollection(payload);
  assert.ok(back, 'decodes');
  same(back.version, 2);
  same(back.dex, uniqSorted(dex));
  same(back.shiny, uniqSorted(shiny));
  same(back.name, codec.cleanName(name));
  same(back.view, view);
  if (gacha === null) {
    same(back.gacha, null);
    same(back.unknown, null);
    same(back.wild, null);
  } else {
    const stars = uniqSorted(shiny);
    const g = uniqSorted(gacha).filter(id => stars.includes(id));
    const u = uniqSorted(unknown).filter(id => stars.includes(id) && !g.includes(id));
    same(back.gacha, g);
    same(back.unknown, u);
    same(back.wild, stars.filter(id => !g.includes(id) && !u.includes(id)));
  }
  same(codec.decodeCollection(payload), back);
  return payload;
}

round({ dex: [], shiny: [] });
round({ dex: [1], shiny: [] });
round({ dex: [1024], shiny: [1024], gacha: [] });
round({ dex: [3, 1, 3, 0, -4, 1.5], shiny: [3, 7], gacha: [7, 99], name: '  Ana  ' });
round({ dex: [25, 6, 150], shiny: [25], gacha: null, name: 'José', view: 'shiny' });
round({ dex: [4, 7, 1], shiny: [7], gacha: [7], name: 'Felipe', view: 'shiny' });
round({ dex: [386, 1, 151], shiny: [], gacha: [], name: 'a'.repeat(40) });
round({ dex: [5], shiny: [9], gacha: [], name: '' });
round({ dex: [4, 7, 9], shiny: [4, 7, 9], gacha: [7], unknown: [4, 9, 2], name: 'mix' });
round({ dex: [4, 7], shiny: [4, 7], gacha: [], unknown: [4, 7], view: 'shiny' });
assert.equal(codec.cleanName('a'.repeat(40)).length, 24);

const v1Ana = 'AQNBbmETABIAAAIAAAAAAAAAAAAAAAAAAIAQAAACAAAAAAAAAAAAAAAAAAAA';
const v1Empty = 'AQAAAA';
const v1Accent = 'AQhKb3PDqSDDkQIACAIAAg';

const legacy = codec.decodeCollection(v1Ana);
same(legacy, { version: 1, name: 'Ana', view: 'normal', dex: [1, 4, 25, 151], shiny: [4, 25], gacha: null, unknown: null, wild: null });
same(codec.decodeCollection(v1Empty), { version: 1, name: '', view: 'normal', dex: [], shiny: [], gacha: null, unknown: null, wild: null });
same(codec.decodeCollection(v1Accent).name, 'José Ñ');
same(codec.decodeCollection(v1Accent).dex, [3, 9]);

assert.equal(codec.decodeCollection(''), null);
assert.equal(codec.decodeCollection('!!!'), null);
assert.equal(codec.decodeCollection('AAAA'), null);
assert.equal(codec.decodeCollection(v1Ana.slice(0, -4) + '@@'), null);
assert.equal(codec.decodeCollection(v1Ana.slice(0, -4)), null);
assert.equal(codec.decodeCollection(Buffer.from([7, 0, 0, 0, 0]).toString('base64url')), null, 'unknown version');

const v2 = codec.encodeCollection({ dex: [1, 4, 25, 151], shiny: [4, 25], gacha: [25], name: 'Ana', view: 'shiny' });
const raw = Buffer.from(v2, 'base64url');
const flipped = Buffer.from(raw);
flipped[1] |= 0x80;
assert.equal(codec.decodeCollection(flipped.toString('base64url')), null, 'reserved flag bit');
const notSubset = Buffer.from(codec.encodeCollection({ dex: [4], shiny: [4], gacha: [4], name: '' }), 'base64url');
const bitsAt = notSubset.length - 1;
notSubset[bitsAt] = notSubset[bitsAt] | 0x08;
assert.equal(codec.decodeCollection(notSubset.toString('base64url')), null, 'gacha bit without shiny');
const crafted = bytes => Buffer.from(bytes).toString('base64url');
same(codec.decodeCollection(crafted([2, 6, 0, 1, 0, 0x10, 0x30, 0x10, 0x20])).unknown, [5]);
same(codec.decodeCollection(crafted([2, 6, 0, 1, 0, 0x10, 0x30, 0x10, 0x20])).wild, []);
assert.equal(codec.decodeCollection(crafted([2, 6, 0, 1, 0, 0x10, 0x10, 0x10, 0x10])), null, 'unknown overlaps gacha');
assert.equal(codec.decodeCollection(crafted([2, 6, 0, 1, 0, 0x10, 0x10, 0x10, 0x20])), null, 'unknown without shiny');
assert.equal(codec.decodeCollection(crafted([2, 4, 0, 1, 0, 0x10, 0x10, 0x10])), null, 'unknown bit without origin bit');
assert.equal(codec.decodeCollection(raw.subarray(0, raw.length - 1).toString('base64url')), null, 'truncated');
assert.equal(codec.decodeCollection(Buffer.concat([raw, Buffer.from([0])]).toString('base64url')), null, 'extra byte');

const pokedex = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'pokedex_export.json'), 'utf8'));
const shinyDoc = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'shiny_species.json'), 'utf8'));
const all = pokedex.map(p => p.dex).sort((a, b) => a - b);
const shinyable = shinyDoc.dex;
const gachaShinies = shinyable.filter((_, i) => i % 5 === 0);
const fullPayload = round({ dex: all, shiny: shinyable, gacha: gachaShinies, name: '' });
const typicalDex = all.filter(d => d <= 386);
const typicalShiny = typicalDex.filter(d => d % 20 === 1);
const typicalPayload = round({ dex: typicalDex, shiny: typicalShiny, gacha: typicalShiny.slice(0, 3), name: '', view: 'shiny' });
const unknownOrigin = round({ dex: typicalDex, shiny: typicalShiny, gacha: null, name: '' });

const es = 'https://survivortiers.pages.dev/coleccion#c=';
const en = 'https://survivortiers.pages.dev/en/coleccion#c=';
const fullEs = es.length + fullPayload.length;
const fullEn = en.length + fullPayload.length;
const typEs = es.length + typicalPayload.length;
assert.ok(fullEs < 700 && fullEn < 700, 'full link stays under 700 characters');
assert.ok(typEs < fullEs, 'a gen 1–3 save is shorter than a full dex');
assert.ok(unknownOrigin.length < typicalPayload.length, 'no origin bitset when the origin is unknown');
assert.equal(typicalDex.length > 300, true);

console.log('round-trip ok');
console.log('full collection: ' + all.length + ' owned, ' + shinyable.length + ' shiny, payload ' + fullPayload.length +
  '  es URL ' + fullEs + '  en URL ' + fullEn);
console.log('typical collection (dex <= 386, ' + typicalDex.length + ' owned, ' + typicalShiny.length +
  ' shiny): payload ' + typicalPayload.length + '  es URL ' + typEs);
