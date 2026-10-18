/* Codifica una colección en el fragmento de la URL (#c=). Base64url sin relleno. Bit N = Pokémon N (el 0 no se usa).
   El nombre solo viaja en el enlace; no se guarda en localStorage.
   v1 (enlaces viejos, solo se leen): versión 1, longitud del nombre, nombre UTF-8, uint16 LE con los bytes de cada
   bitset, bitset de dex poseídos, bitset de shiny.
   v2: versión 2, banderas (bit 0: vista shiny; bit 1: se conoce el origen de todos los shiny), longitud del nombre,
   nombre UTF-8, uint16 LE con los bytes de cada bitset, bitset de dex, bitset de shiny y, solo si el origen se conoce,
   bitset de los shiny que vienen de gacha. Los shiny sin ese bit son salvajes: así viajan los contadores «cazados» y
   «gacha» sin campos extra. La fecha de captura no viaja.
   Encodes a collection into the URL fragment (#c=). Version 2 adds a flags byte (bit 0 shiny view, bit 1 origin known)
   and a bitset of the shinies that came from gacha; the rest of the shinies are wild. Version 1 links still decode. */
const ShareCodec = (() => {
  'use strict';
  const VERSION = 2;
  const VERSION_1 = 1;
  const FLAG_SHINY_VIEW = 1;
  const FLAG_ORIGIN = 2;
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

  /* dex: Pokémon poseídos. shiny: los que tienen shiny. gacha: los shiny que salieron de gacha, o null si no se sabe
     de dónde sale cada shiny. view: 'normal' o 'shiny' (la vista en la que se compartió). */
  function encodeCollection({ dex, shiny, gacha = null, name = '', view = 'normal' } = {}) {
    const owned = idsOf(dex);
    const stars = idsOf(shiny);
    const originKnown = Array.isArray(gacha);
    const gachaIds = originKnown ? idsOf(gacha).filter(id => stars.includes(id)) : [];
    const label = cleanName(name);
    const labelBytes = new TextEncoder().encode(label);
    const maxId = Math.max(0, owned.length ? owned[owned.length - 1] : 0, stars.length ? stars[stars.length - 1] : 0);
    const nbytes = maxId === 0 ? 0 : (maxId >> 3) + 1;
    const sets = [writeBits(owned, nbytes), writeBits(stars, nbytes)];
    if (originKnown) sets.push(writeBits(gachaIds, nbytes));
    const flags = (view === 'shiny' ? FLAG_SHINY_VIEW : 0) | (originKnown ? FLAG_ORIGIN : 0);
    const out = new Uint8Array(3 + labelBytes.length + 2 + nbytes * sets.length);
    out[0] = VERSION;
    out[1] = flags;
    out[2] = labelBytes.length;
    out.set(labelBytes, 3);
    const at = 3 + labelBytes.length;
    out[at] = nbytes & 255;
    out[at + 1] = (nbytes >> 8) & 255;
    sets.forEach((set, i) => out.set(set, at + 2 + i * nbytes));
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
      wild: null,
    };
  }

  function decodeV2(bytes) {
    const flags = bytes[1];
    if (flags & ~(FLAG_SHINY_VIEW | FLAG_ORIGIN)) return null;
    if (bytes.length < 5) return null;
    const nameLen = bytes[2];
    const name = decodeName(bytes, 3, nameLen);
    if (name === null) return null;
    const at = 3 + nameLen;
    if (bytes.length < at + 2) return null;
    const nbytes = bytes[at] | (bytes[at + 1] << 8);
    if (nbytes > MAX_BYTES) return null;
    const originKnown = !!(flags & FLAG_ORIGIN);
    const sets = originKnown ? 3 : 2;
    const body = at + 2;
    if (bytes.length !== body + nbytes * sets) return null;
    const dex = readBits(bytes.subarray(body, body + nbytes));
    const shiny = readBits(bytes.subarray(body + nbytes, body + 2 * nbytes));
    const gacha = originKnown ? readBits(bytes.subarray(body + 2 * nbytes)) : null;
    if (gacha && gacha.some(id => !new Set(shiny).has(id))) return null;
    return {
      version: VERSION,
      name,
      view: flags & FLAG_SHINY_VIEW ? 'shiny' : 'normal',
      dex,
      shiny,
      gacha,
      wild: gacha ? shiny.filter(id => !gacha.includes(id)) : null,
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
