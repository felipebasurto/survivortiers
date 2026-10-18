/* Colección importada: lectura del resultado del comando de la consola y lista de shiny. Sin DOM, lo usan app.js y
   build/test_collection.js. El comando exporta shinyInfo: { «dex»: [origen, día] }, origen 0 salvaje, 1 gacha, 2 otro
   (o desconocido), y día = días desde 1970 UTC de la captura, o null. Sin shinyInfo (JSON de antes), el origen
   de cada shiny es desconocido.
   Imported collection: parses the console command output and lists the shinies. No DOM. */
const Collection = (() => {
  'use strict';
  const FROM_CODE = ['wild', 'gacha', null];
  const MAX_DAY = 100000;
  const REASONS = ['notJson', 'notCollection', 'missingKeys', 'badShinyInfo'];

  function ids(list) {
    return [...new Set(list.map(Number).filter(n => Number.isInteger(n) && n > 0))].sort((a, b) => a - b);
  }

  function infoOf(raw) {
    if (raw === undefined) return { info: {}, ok: true };
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return { info: null, ok: false };
    const info = {};
    for (const key of Object.keys(raw)) {
      const dex = Number(key);
      const pair = raw[key];
      if (!/^[1-9]\d*$/.test(key) || !Array.isArray(pair) || pair.length !== 2) return { info: null, ok: false };
      const [from, day] = pair;
      if (!Number.isInteger(from) || from < 0 || from > 2) return { info: null, ok: false };
      if (day !== null && !(Number.isInteger(day) && day >= 0 && day <= MAX_DAY)) return { info: null, ok: false };
      info[dex] = { from: FROM_CODE[from], day };
    }
    return { info, ok: true };
  }

  /* Devuelve { ok: true, c } o { ok: false, reason }, con reason en REASONS (la página la traduce). */
  function parse(text) {
    let o;
    try { o = JSON.parse(String(text).trim()); } catch (e) { return { ok: false, reason: 'notJson' }; }
    if (typeof o === 'string') {
      try { o = JSON.parse(o); } catch (e) { return { ok: false, reason: 'notCollection' }; }
    }
    if (!o || typeof o !== 'object' || !Array.isArray(o.dex) || !Array.isArray(o.shiny)) return { ok: false, reason: 'missingKeys' };
    const parsed = infoOf(o.shinyInfo);
    if (!parsed.ok) return { ok: false, reason: 'badShinyInfo' };
    const shiny = ids([...o.shiny, ...Object.keys(parsed.info)]);
    return {
      ok: true,
      c: {
        version: o.version,
        name: String(o.name || ''),
        updated: +o.updated || 0,
        dex: ids(o.dex),
        shiny,
        info: parsed.info,
      },
    };
  }

  function originOf(c, dex) {
    const e = c.info[dex];
    return e ? e.from : null;
  }

  function shinyCounts(c) {
    const counts = { total: c.shiny.length, wild: 0, gacha: 0, unknown: 0 };
    c.shiny.forEach(dex => {
      const from = originOf(c, dex);
      if (from === 'wild') counts.wild++;
      else if (from === 'gacha') counts.gacha++;
      else counts.unknown++;
    });
    return counts;
  }

  /* Lo que el enlace #c= deja ver: sin origen (enlace v1) los shiny quedan «desconocidos». */
  function fromLink(link) {
    const info = {};
    if (link.gacha) {
      const gacha = new Set(link.gacha);
      link.shiny.forEach(dex => { info[dex] = { from: gacha.has(dex) ? 'gacha' : 'wild', day: null }; });
    }
    return { version: link.version, name: link.name, updated: 0, dex: link.dex, shiny: link.shiny, info };
  }

  /* Los shiny de gacha que viajan en el enlace, o null si algún shiny no tiene origen conocido. */
  function gachaForLink(c) {
    const known = c.shiny.every(dex => originOf(c, dex) === 'wild' || originOf(c, dex) === 'gacha');
    return known ? c.shiny.filter(dex => originOf(c, dex) === 'gacha') : null;
  }

  /* Filas de la vista shiny. sort: 'new' (más reciente primero; sin fecha al final, por nº) o 'dex'.
     wildOnly: solo los cazados en salvaje (los de origen desconocido no entran). */
  function shinyRows(c, { sort = 'new', wildOnly = false } = {}) {
    const rows = c.shiny
      .map(dex => ({ dex, from: originOf(c, dex), day: c.info[dex] ? c.info[dex].day : null }))
      .filter(r => !wildOnly || r.from === 'wild');
    if (sort === 'dex') return rows.sort((a, b) => a.dex - b.dex);
    return rows.sort((a, b) => {
      if (a.day === null && b.day === null) return a.dex - b.dex;
      if (a.day === null) return 1;
      if (b.day === null) return -1;
      return b.day - a.day || a.dex - b.dex;
    });
  }

  return { parse, shinyCounts, shinyRows, originOf, fromLink, gachaForLink, REASONS, MAX_DAY };
})();
if (typeof module !== 'undefined' && module.exports) module.exports = Collection;
