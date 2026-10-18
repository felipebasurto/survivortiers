/* Codifica una colección en el fragmento de la URL (#c=). Base64url sin relleno. Bit N = Pokémon N (el 0 no se usa).
   El nombre solo viaja en el enlace; no se guarda en localStorage.
   v1 (enlaces viejos, solo se leen): versión 1, longitud del nombre, nombre UTF-8, uint16 LE con los bytes de cada
   bitset, bitset de dex poseídos, bitset de shiny.
   v2: versión 2, banderas (bit 0: vista shiny; bit 1: hay bitset de gacha; bit 2: hay bitset de origen desconocido;
   bit 3: vista de legendarios), longitud del nombre, nombre UTF-8, uint16 LE con los bytes de cada bitset: dex, shiny y,
   según las banderas, gacha y desconocido. Los shiny que no están en ninguno de los dos son salvajes. La fecha de
   captura no viaja.
   Encodes a collection into the URL fragment (#c=). Version 2 adds flags (bit 0 shiny view, bit 1 gacha set, bit 2
   unknown-origin set, bit 3 legendary view); the shinies in neither set are wild. Version 1 links still decode. */
const ShareCodec = (() => {
  'use strict';
  const VERSION = 2;
  const VERSION_1 = 1;
  const FLAG_SHINY_VIEW = 1;
  const FLAG_ORIGIN = 2;
  const FLAG_UNKNOWN = 4;
  const FLAG_LEGEND_VIEW = 8;
  const MAX_CHARS = 24;
  const MAX_NAME_BYTES = 96;
  const MAX_BYTES = 512;

  function cleanName(name) {
    const flat = String(name == null ? '' : name).replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim();
    const chars = [...flat].slice(0, MAX_CHARS);
    while (chars.length && new TextEncoder().encode(chars.join('')).length > MAX_NAME_BYTES) chars.pop();
    return chars.join('');
  }

  function idsOf(list) {
    const set = new Set();
    const src = list || [];
    for (let i = 0; i < src.length; i++) {
      const n = Number(src[i]);
      if (Number.isInteger(n) && n > 0 && (n >> 3) < MAX_BYTES) set.add(n);
    }
    return [...set].sort((a, b) => a - b);
  }

  function b64urlEncode(bytes) {
    let bin = '';
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
  }

  function b64urlDecode(text) {
    if (typeof text !== 'string' || !/^[\w-]+$/.test(text)) return null;
    const pad = text.length % 4 === 0 ? '' : '='.repeat(4 - (text.length % 4));
    try {
      const bin = atob(text.replace(/-/g, '+').replace(/_/g, '/') + pad);
      const out = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
      return out;
    } catch (e) {
      return null;
    }
  }

  function writeBits(ids, nbytes) {
    const bytes = new Uint8Array(nbytes);
    for (let i = 0; i < ids.length; i++) {
      const id = ids[i];
      bytes[id >> 3] |= 1 << (id & 7);
    }
    return bytes;
  }

  function readBits(bytes) {
    const ids = [];
    for (let i = 0; i < bytes.length; i++) {
      const b = bytes[i];
      if (!b) continue;
      for (let bit = 0; bit < 8; bit++) if (b & (1 << bit)) ids.push((i << 3) | bit);
    }
    return ids.filter(n => n > 0);
  }

  function decodeName(bytes, start, len) {
    if (len > MAX_NAME_BYTES) return null;
    let name;
    try {
      name = new TextDecoder('utf-8', { fatal: true }).decode(bytes.subarray(start, start + len));
    } catch (e) {
      return null;
    }
    return [...name].length > MAX_CHARS ? null : name;
  }

  function viewFlag(view) {
    if (view === 'shiny') return FLAG_SHINY_VIEW;
    if (view === 'legend') return FLAG_LEGEND_VIEW;
    return 0;
  }

  /* dex: Pokémon poseídos. shiny: los que tienen shiny. gacha: los shiny que salieron de gacha, o null si el origen no
     viaja. unknown: shiny de origen desconocido; los que no están en gacha ni aquí son salvajes.
     view: 'normal', 'shiny' o 'legend'. */
  function encodeCollection({ dex, shiny, gacha = null, unknown = [], name = '', view = 'normal' } = {}) {
    const owned = idsOf(dex);
    const stars = idsOf(shiny);
    const originKnown = Array.isArray(gacha);
    const gachaIds = originKnown ? idsOf(gacha).filter(id => stars.includes(id)) : [];
    const gachaSet = new Set(gachaIds);
    const unknownIds = originKnown ? idsOf(unknown).filter(id => stars.includes(id) && !gachaSet.has(id)) : [];
    const label = cleanName(name);
    const labelBytes = new TextEncoder().encode(label);
    const maxId = Math.max(0, owned.length ? owned[owned.length - 1] : 0, stars.length ? stars[stars.length - 1] : 0);
    const nbytes = maxId === 0 ? 0 : (maxId >> 3) + 1;
    const sets = [owned, stars];
    if (originKnown) sets.push(gachaIds);
    if (unknownIds.length) sets.push(unknownIds);
    const flags = viewFlag(view) | (originKnown ? FLAG_ORIGIN : 0) | (unknownIds.length ? FLAG_UNKNOWN : 0);
    const out = new Uint8Array(3 + labelBytes.length + 2 + nbytes * sets.length);
    out[0] = VERSION;
    out[1] = flags;
    out[2] = labelBytes.length;
    out.set(labelBytes, 3);
    const at = 3 + labelBytes.length;
    out[at] = nbytes & 255;
    out[at + 1] = (nbytes >> 8) & 255;
    sets.forEach((ids, i) => out.set(writeBits(ids, nbytes), at + 2 + i * nbytes));
    return b64urlEncode(out);
  }

  function decodeV1(bytes) {
    if (bytes.length < 4) return null;
    const nameLen = bytes[1];
    if (nameLen > MAX_NAME_BYTES || bytes.length < 2 + nameLen + 2) return null;
    const name = decodeName(bytes, 2, nameLen);
    if (name === null) return null;
    const nameEnd = 2 + nameLen;
    const nbytes = bytes[nameEnd] | (bytes[nameEnd + 1] << 8);
    if (nbytes > MAX_BYTES) return null;
    const body = nameEnd + 2;
    if (bytes.length !== body + nbytes * 2) return null;
    return {
      version: VERSION_1,
      name,
      view: 'normal',
      dex: readBits(bytes.subarray(body, body + nbytes)),
      shiny: readBits(bytes.subarray(body + nbytes)),
      gacha: null,
      unknown: null,
      wild: null,
    };
  }

  function decodeV2(bytes) {
    if (bytes.length < 5) return null;
    const flags = bytes[1];
    if (flags & ~(FLAG_SHINY_VIEW | FLAG_ORIGIN | FLAG_UNKNOWN | FLAG_LEGEND_VIEW)) return null;
    if ((flags & FLAG_UNKNOWN) && !(flags & FLAG_ORIGIN)) return null;
    if ((flags & FLAG_SHINY_VIEW) && (flags & FLAG_LEGEND_VIEW)) return null;
    const nameLen = bytes[2];
    const name = decodeName(bytes, 3, nameLen);
    if (name === null) return null;
    const at = 3 + nameLen;
    if (bytes.length < at + 2) return null;
    const nbytes = bytes[at] | (bytes[at + 1] << 8);
    if (nbytes > MAX_BYTES) return null;
    const originKnown = !!(flags & FLAG_ORIGIN);
    const hasUnknown = !!(flags & FLAG_UNKNOWN);
    const count = 2 + (originKnown ? 1 : 0) + (hasUnknown ? 1 : 0);
    const body = at + 2;
    if (bytes.length !== body + nbytes * count) return null;
    const sets = [];
    for (let i = 0; i < count; i++) sets.push(readBits(bytes.subarray(body + i * nbytes, body + (i + 1) * nbytes)));
    const dex = sets[0];
    const shiny = sets[1];
    const gacha = originKnown ? sets[2] : null;
    const unknown = originKnown ? (hasUnknown ? sets[count - 1] : []) : null;
    const starSet = new Set(shiny);
    const gachaSet = new Set(gacha || []);
    const unknownSet = new Set(unknown || []);
    if (gacha && gacha.some(id => !starSet.has(id))) return null;
    if (unknown && unknown.some(id => !starSet.has(id) || gachaSet.has(id))) return null;
    return {
      version: VERSION,
      name,
      view: flags & FLAG_SHINY_VIEW ? 'shiny' : flags & FLAG_LEGEND_VIEW ? 'legend' : 'normal',
      dex,
      shiny,
      gacha,
      unknown,
      wild: gacha ? shiny.filter(id => !gachaSet.has(id) && !unknownSet.has(id)) : null,
    };
  }

  function decodeCollection(payload) {
    const bytes = b64urlDecode(payload);
    if (!bytes || bytes.length < 2) return null;
    if (bytes[0] === VERSION) return decodeV2(bytes);
    if (bytes[0] === VERSION_1) return decodeV1(bytes);
    return null;
  }

  return { encodeCollection, decodeCollection, cleanName, MAX_CHARS, VERSION };
})();
if (typeof module !== 'undefined' && module.exports) module.exports = ShareCodec;
