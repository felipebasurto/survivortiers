/* Codifica una colección en el fragmento de la URL (#c=).
   Bytes: versión (1), longitud del nombre, nombre en UTF-8, uint16 LE con los bytes de cada bitset,
   bitset de dex poseídos, bitset de shiny. El bit N es el dex N (el 0 no se usa). Base64url sin relleno.
   El nombre solo viaja en el enlace; no se guarda en localStorage.
   Encodes a collection into the URL fragment (#c=).
   Bytes: version (1), name length, UTF-8 name, uint16 LE bitset size, owned dex bitset, shiny bitset.
   Bit N is dex N (bit 0 is unused). Unpadded base64url. The name lives only in the link. */
const ShareCodec = (() => {
  'use strict';
  const VERSION = 1;
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

  function encodeCollection(dex, shiny, name) {
    const owned = idsOf(dex);
    const stars = idsOf(shiny);
    const label = cleanName(name);
    const labelBytes = new TextEncoder().encode(label);
    const maxId = Math.max(0, owned.length ? owned[owned.length - 1] : 0, stars.length ? stars[stars.length - 1] : 0);
    const nbytes = maxId === 0 ? 0 : (maxId >> 3) + 1;
    const out = new Uint8Array(2 + labelBytes.length + 2 + nbytes * 2);
    out[0] = VERSION;
    out[1] = labelBytes.length;
    out.set(labelBytes, 2);
    const at = 2 + labelBytes.length;
    out[at] = nbytes & 255;
    out[at + 1] = (nbytes >> 8) & 255;
    out.set(writeBits(owned, nbytes), at + 2);
    out.set(writeBits(stars, nbytes), at + 2 + nbytes);
    return b64urlEncode(out);
  }

  function decodeCollection(payload) {
    const bytes = b64urlDecode(payload);
    if (!bytes || bytes.length < 4 || bytes[0] !== VERSION) return null;
    const nameLen = bytes[1];
    if (nameLen > MAX_NAME_BYTES || bytes.length < 2 + nameLen + 2) return null;
    const nameEnd = 2 + nameLen;
    let name;
    try {
      name = new TextDecoder('utf-8', { fatal: true }).decode(bytes.subarray(2, nameEnd));
    } catch (e) {
      return null;
    }
    if ([...name].length > MAX_CHARS) return null;
    const nbytes = bytes[nameEnd] | (bytes[nameEnd + 1] << 8);
    if (nbytes > MAX_BYTES) return null;
    const body = nameEnd + 2;
    if (bytes.length !== body + nbytes * 2) return null;
    return {
      dex: readBits(bytes.subarray(body, body + nbytes)),
      shiny: readBits(bytes.subarray(body + nbytes)),
      name,
    };
  }

  return { encodeCollection, decodeCollection, cleanName, MAX_CHARS };
})();
if (typeof module !== 'undefined' && module.exports) module.exports = ShareCodec;
