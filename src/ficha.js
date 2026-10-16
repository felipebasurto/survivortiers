/* SurvivorTiers · ficha de cada Pokémon, dibujada en el navegador con data/pokemon-index.json, data/species.json y
   data/moves.json. Es la única plantilla pokemon/index.html de cada idioma: el número sale de ?id=. Los textos llegan
   en un bloque JSON de la propia página (build/render.py), para que ES y EN salgan de build/i18n.py.
   Mismos gráficos que build/charts.py. */
(() => {
  'use strict';
  const html = document.documentElement;
  if (html.dataset.page !== 'ficha') return;
  const home = html.dataset.home || '';
  const sprites = html.dataset.sprites || '';
  const spriteExt = html.dataset.spritesExt || '.png';
  const T = JSON.parse(document.getElementById('i18n').textContent);
  const EN = T.en;
  const TOTAL = 966;
  const FICHA_BOX = 170;
  const CUTS = [['S', 1, 30], ['A', 31, 120], ['B', 121, 320], ['C', 321, 620], ['D', 621, 966]];
  const PILLARS = ['stats', 'moves', 'typedef', 'size'];
  const METHODS = ['sheet', 'simStart', 'simBest', 'lateMax', 'lateFresh'];
  const FLAGS = [[1, 'potion', 'flag_status'], [2, 'sword', 'flag_melee'], [4, 'trophy', 'flag_capped'], [8, 'sparkle', 'flag_types']];
  // Mismos colores que build/typedata.py (TYPE_COLOR): tiñen el fondo del sprite.
  const TYPE_COLOR = {
    normal: '#b0a99f', fire: '#ff7b3d', water: '#4b9bff', grass: '#5fcb6a', electric: '#ffd33d', ice: '#7fe0e0',
    fighting: '#e0533d', poison: '#b45ec4', ground: '#d6b25c', flying: '#9bb8ff', psychic: '#ff5f9e', bug: '#a3c43d',
    rock: '#bfa96b', ghost: '#7a6bc4', dragon: '#6b58ff', dark: '#6b5c52', steel: '#a8b8c4', fairy: '#ff9ed8',
  };
  const root = document.getElementById('ficha');

  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const t = (k, v) => String(T.s[k]).replace(/\{(\w+)\}/g, (m, n) => (v && n in v ? v[n] : m));
  // Python redondea a par cuando está justo en medio y Math.round no: se iguala para que ES y EN coincidan con el generador.
  const rnd = x => {
    const f = Math.floor(x);
    const d = x - f;
    return d < 0.5 ? f : d > 0.5 ? f + 1 : (f % 2 ? f + 1 : f);
  };
  const pct = v => rnd(v * 100) + (EN ? '%' : '\u00a0%');
  const f2 = x => x.toFixed(2);

  const fig = (kind, title, body, alt) =>
    '<figure class="fig anim fig-' + kind + '"><figcaption><h3>' + esc(title) + '</h3></figcaption>' +
    '<div class="fig-body" role="img" aria-label="' + esc(alt) + '">' + body + '</div></figure>';

  const side = x => (x < 12 ? 's-l' : x > 88 ? 's-r' : '');

  function dotplot(ref, rows, axis) {
    let out = '';
    if (ref) out += '<div class="mt-ref"><span class="' + ref.side + '" style="left:' + f2(ref.x) + '%">' + esc(ref.text) + '</span></div>';
    rows.forEach((r, i) => {
      const flip = r.x > 85;
      const where = flip ? 'right:' + f2(100 - r.x) + '%' : 'left:' + f2(r.x) + '%';
      const line = ref ? '<i class="mt-final" style="left:' + f2(ref.x) + '%"></i>' : '';
      out += '<div class="mt-row" style="--i:' + i + '"><span class="mt-name">' + esc(r.label) + '</span>' +
        '<span class="mt-track">' + line + '<b class="mt-dot" style="left:' + f2(r.x) + '%"></b>' +
        '<em class="mt-val' + (flip ? ' flip' : '') + '" style="' + where + '">' + esc(r.text) + '</em></span></div>';
    });
    return out + '<div class="mt-axis" aria-hidden="true"><span>' + esc(axis[0]) + '</span><span>' + esc(axis[1]) + '</span></div>';
  }

  // Vista ampliada: entre 1 y 966 el margen de un Pokémon ocupa pocos píxeles. La barra enseña solo una ventana
  // alrededor de su margen, con al menos 20 puestos a cada lado (o lo ancho que sea el margen).
  const RANK_TICKS = [1, 30, 120, 320, 620, 966];
  function zoomWindow(lo, hi) {
    const pad = Math.max(20, hi - lo);
    return [Math.max(1, lo - pad), Math.min(TOTAL, hi + pad)];
  }

  // Números redondos para la escala (1, 10, 20...), con un paso que dé unas 5 marcas en la ventana.
  function niceTicks(w0, w1) {
    const raw = (w1 - w0) / 5, pow = Math.pow(10, Math.floor(Math.log10(raw)));
    const m = raw / pow, step = (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * pow;
    const out = [];
    for (let n = Math.ceil(w0 / step) * step; n <= w1; n += step) out.push(n);
    return out;
  }

  // Mini-barra con los 966: el tramo ampliado queda marcado con un recuadro, y el Pokémon, con un punto.
  function overview(rank, tier, w0, w1) {
    const pos = n => (n - 1) / (TOTAL - 1) * 100;
    const segs = CUTS.map(c => '<i class="t-' + c[0] + (c[0] === tier ? ' on' : '') + '" style="flex:' + (c[2] - c[1] + 1) + '"></i>').join('');
    return '<div class="rb-over">' +
      '<div class="rb-ov">' + segs +
      '<b class="rb-ov-win" style="left:' + f2(pos(w0)) + '%;width:' + f2(Math.max(pos(w1) - pos(w0), 1.2)) + '%"></b>' +
      '<b class="rb-ov-dot" style="left:' + f2(pos(rank)) + '%"></b></div></div>';
  }

  function rankBand(p, name) {
    const [rank, tier, lo, hi] = p.r;
    const [w0, w1] = zoomWindow(lo, hi);
    const zoomed = w0 !== 1 || w1 !== TOTAL;
    const at = n => (n - w0) / (w1 - w0) * 100;
    const x = at(rank);
    const sd = x < 14 ? 'l' : x > 86 ? 'r' : 'c';
    const noteStyle = sd !== 'r' ? 'left:' + f2(x) + '%' : 'right:' + f2(100 - x) + '%';
    const visible = CUTS.map(c => [c, Math.max(c[1], w0), Math.min(c[2], w1)]).filter(v => v[2] >= v[1]);
    const segs = visible.map(([c, a, b]) => '<i class="rb-seg t-' + c[0] + (c[0] === tier ? ' on' : '') + '" style="flex:' + (b - a + 1) + '"></i>').join('');
    const letters = visible.map(([c, a, b]) => '<i class="t-' + c[0] + '" style="flex:' + (b - a + 1) + '">' + c[0] + '</i>').join('');
    // Escala: los extremos y los cortes de tier mandan; los números redondos se quitan si se pegan a ellos.
    const fixed = [...new Set([w0, w1, ...RANK_TICKS.filter(n => n > w0 && n < w1)])];
    const cand = [...new Set([...fixed, ...niceTicks(w0, w1)])].sort((a, b) => a - b);
    const kept = [];
    cand.forEach(n => {
      const last = kept[kept.length - 1];
      if (kept.length === 0 || at(n) - at(last) >= 9) kept.push(n);
      else if (fixed.includes(n) && !fixed.includes(last)) kept[kept.length - 1] = n;
    });
    const ticks = kept.map(n => '<span style="left:' + f2(at(n)) + '%">' + n + '</span>').join('');
    const span = Math.max(at(hi) - at(lo), 0.5);
    const legend = zoomed ? t('band_zoom', { lo: w0, hi: w1, total: TOTAL }) : t('band_all', { total: TOTAL });
    const view = '<div class="rb-view"><span class="rb-legend">' + esc(legend) + '</span>' +
      '<div class="rb-note rb-' + sd + '" style="' + noteStyle + '"><b>' + esc(t('band_rank', { rank })) + '</b>' +
      '<span>' + esc(t('band_range', { lo, hi })) + '</span></div>' +
      '<div class="rb-track">' + segs + '<b class="rb-range" style="left:' + f2(at(lo)) + '%;width:' + f2(span) + '%"></b>' +
      '<b class="rb-dot" style="left:' + f2(x) + '%"></b></div>' +
      '<div class="rb-tiers" aria-hidden="true">' + letters + '</div><div class="rb-ticks" aria-hidden="true">' + ticks + '</div></div>';
    const body = (zoomed ? overview(rank, tier, w0, w1) : '') + view;
    return fig('band', t('t_band'), body, t('band_alt', { name, rank, total: TOTAL, tier, lo, hi }));
  }

  // Estadísticas base oficiales (PokéAPI): un hexágono con los seis valores, como el radar de los juegos, y al lado la
  // barra de cada uno. El hexágono discontinuo y la línea de cada barra marcan la mediana de los 966.
  const BASE_KEYS = ['bs_hp', 'bs_atk', 'bs_def', 'bs_spa', 'bs_spd', 'bs_spe'];
  const SHORT_KEYS = ['bs_s_hp', 'bs_s_atk', 'bs_s_def', 'bs_s_spa', 'bs_s_spd', 'bs_s_spe'];
  const bandOf = v => (v < 50 ? 0 : v < 80 ? 1 : v < 100 ? 2 : v < 120 ? 3 : 4);
  const RADAR = { cx: 150, cy: 128, r: 84, max: 255 };
  // Vértice i: el primero arriba y los demás en sentido horario, en el mismo orden que BASE_KEYS.
  const angle = i => (-90 + i * 60) * Math.PI / 180;
  const vertex = (i, v) => [RADAR.cx + v / RADAR.max * RADAR.r * Math.cos(angle(i)), RADAR.cy + v / RADAR.max * RADAR.r * Math.sin(angle(i))];
  const polyOf = fn => [0, 1, 2, 3, 4, 5].map(i => fn(i).map(f2).join(',')).join(' ');
  const hexAt = (x, y, r) => [0, 1, 2, 3, 4, 5].map(k => f2(x + r * Math.cos(k * Math.PI / 3)) + ',' + f2(y + r * Math.sin(k * Math.PI / 3))).join(' ');
  function radar(vals, meds) {
    const { cx, cy, r, max } = RADAR;
    const grid = [0.25, 0.5, 0.75, 1].map(f => '<polygon class="rd-grid" points="' + polyOf(i => vertex(i, max * f)) + '"/>').join('');
    const axes = [0, 1, 2, 3, 4, 5].map(i => {
      const [x, y] = vertex(i, max);
      return '<line class="rd-axis" x1="' + cx + '" y1="' + cy + '" x2="' + f2(x) + '" y2="' + f2(y) + '"/>';
    }).join('');
    const med = '<polygon class="rd-med" points="' + polyOf(i => vertex(i, meds[i])) + '"/>';
    const shape = '<polygon class="rd-shape" points="' + polyOf(i => vertex(i, vals[i])) + '"/>';
    const verts = [0, 1, 2, 3, 4, 5].map(i => {
      const [x, y] = vertex(i, vals[i]);
      return '<polygon class="rd-vert b' + bandOf(vals[i]) + '" points="' + hexAt(x, y, 4.5) + '"/>';
    }).join('');
    const labels = [0, 1, 2, 3, 4, 5].map(i => {
      const c = Math.cos(angle(i)), s = Math.sin(angle(i));
      const x = cx + (r + 16) * c, y = cy + (r + 16) * s + (s > 0.5 ? 14 : s < -0.5 ? -4 : 4);
      const anchor = c > 0.3 ? 'start' : c < -0.3 ? 'end' : 'middle';
      return '<text class="rd-lab" x="' + f2(x) + '" y="' + f2(y) + '" text-anchor="' + anchor + '"><tspan class="rd-n">' +
        esc(t(SHORT_KEYS[i])) + '</tspan><tspan class="rd-v" x="' + f2(x) + '" dy="13">' + vals[i] + '</tspan></text>';
    }).join('');
    return '<svg class="rd" viewBox="0 0 300 268" aria-hidden="true" focusable="false">' + grid + axes + med + shape + verts + labels + '</svg>';
  }
  function baseStats(d, medians, name) {
    const s = d[8];
    const total = s.reduce((a, b) => a + b, 0);
    const rows = BASE_KEYS.map((k, i) => ({ label: t(k), v: s[i], med: medians[i] }));
    let out = '<div class="bs-list">';
    rows.forEach((r, i) => {
      out += '<div class="bs-row" style="--i:' + i + '"><span class="bs-name">' + esc(r.label) + '</span>' +
        '<span class="bs-track"><i class="bs-fill b' + bandOf(r.v) + '" style="width:' + f2(r.v / 255 * 100) + '%"></i>' +
        '<b class="bs-med" style="left:' + f2(r.med / 255 * 100) + '%"></b></span>' +
        '<output class="bs-val">' + r.v + '</output></div>';
    });
    out += '<div class="bs-total"><span>' + esc(t('bs_total')) + '</span><b>' + total + '</b></div></div>';
    const body = '<div class="bs-wrap"><div class="bs-radar">' + radar(s, medians) + '</div>' + out + '</div>';
    const alt = name + ': ' + rows.map(r => t('bs_alt_item', { label: r.label, v: r.v })).join('; ') + '; ' + t('bs_total') + ' ' + total + '.';
    return fig('bases', t('t_base'), body, alt);
  }

  function pillars(d, name) {
    const rows = PILLARS.map((k, i) => ({ label: t('pill_' + k), v: d[0][i] })).sort((a, b) => b.v - a.v);
    let out = '<div class="lp-ref"><span style="left:50%">' + esc(t('median')) + '</span></div>';
    rows.forEach((r, i) => {
      const x = r.v * 100;
      const hot = i === 0 ? ' hot' : '';
      out += '<div class="lp-row" style="--i:' + i + '"><span class="lp-name">' + esc(r.label) + '</span>' +
        '<span class="lp-track"><i class="lp-line" style="width:' + x.toFixed(1) + '%"></i>' +
        '<b class="lp-dot' + hot + '" style="left:' + x.toFixed(1) + '%"></b>' +
        '<em class="lp-val' + hot + '" style="left:' + x.toFixed(1) + '%">' + pct(r.v) + '</em></span></div>';
    });
    const alt = name + ': ' + rows.map(r => t('pillars_alt_item', { label: r.label, v: rnd(r.v * 100) })).join('; ') + '.';
    return fig('pillars', t('t_pillars'), out, alt);
  }

  function methods(p, d, name) {
    const final = p.r[0];
    const vals = [final, ...d[1]];
    const [w0, w1] = zoomWindow(Math.min(...vals), Math.max(...vals));
    const at = n => (n - w0) / (w1 - w0) * 100;
    const xf = at(final);
    const rows = METHODS.map((k, i) => ({ label: t('m_' + k), x: at(d[1][i]), text: String(d[1][i]), v: d[1][i] }));
    const zoomed = w0 !== 1 || w1 !== TOTAL;
    const zoomNote = zoomed ? '<p class="zoom-note">' + esc(t('band_zoom', { lo: w0, hi: w1 })) + '</p>' : '';
    const body = '<p class="fig-lede">' + esc(t('methods_lede')) + '</p>' +
      dotplot({ text: t('methods_final', { rank: final }), x: xf, side: side(xf) }, rows, [String(w0), String(w1)]) + zoomNote;
    const alt = t('methods_alt', { name, rank: final }) + rows.map(r => t('methods_alt_item', { label: r.label, v: r.v })).join('; ') + '.';
    return fig('methods', t('t_methods'), body, alt);
  }

  // Marcas redondas (20, 40, 60...) con a lo sumo unas seis en la escala: sin ellas no se lee la distancia.
  function simTicks(lo, hi) {
    const step = [5, 10, 20, 25, 50, 100].find(s => (hi - lo) / s <= 6) || 100;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(v);
    return out;
  }

  function sim(d, range, moveName) {
    const [lo, hi, median] = range;
    const items = [{ label: t('sim_start', { name: moveName(d[2]) }), s: d[3] }];
    if (d[4] !== d[2]) items.push({ label: t('sim_best', { name: moveName(d[4]) }), s: d[5] });
    const xOf = s => (s - lo) / (hi - lo) * 100;
    const xm = xOf(median);
    const secs = s => rnd(s) + ' s';
    const grid = simTicks(lo, hi).map(v => '<i class="mt-grid" style="left:' + f2(xOf(v)) + '%"></i>').join('');
    const rows = items.map((it, i) => {
      const x = xOf(it.s);
      const gain = i === 1 ? '<i class="mt-gain" style="left:' + f2(xOf(items[0].s)) + '%;width:' + f2(x - xOf(items[0].s)) + '%"></i>' : '';
      const side = x < 10 ? ' s-l' : x > 90 ? ' s-r' : '';
      return '<div class="mt-row" style="--i:' + i + '"><span class="mt-name">' + esc(it.label) + '</span>' +
        '<span class="mt-track">' + grid + gain + '<i class="mt-final" style="left:' + f2(xm) + '%"></i>' +
        '<b class="mt-dot" style="left:' + f2(x) + '%"></b>' +
        '<em class="mt-val' + side + '" style="left:' + f2(x) + '%">' + esc(secs(it.s)) + '</em></span></div>';
    }).join('');
    const axis = simTicks(lo, hi).map(v => '<span style="left:' + f2(xOf(v)) + '%">' + v + ' s</span>').join('');
    const ref = '<div class="mt-ref"><span class="' + side(xm) + '" style="left:' + f2(xm) + '%">' + esc(t('sim_median', { s: rnd(median) })) + '</span></div>';
    const gainNote = items.length === 2 && items[1].s > items[0].s
      ? '<p class="fig-note sim-gain">' + esc(t('sim_gain', { d: rnd(items[1].s - items[0].s) })) + '</p>' : '';
    const body = '<p class="fig-lede">' + esc(t('sim_lede')) + '</p>' +
      '<div class="sim-chart">' + ref + rows + '<div class="mt-axis sim-axis" aria-hidden="true">' + axis + '</div></div>' +
      gainNote +
      '<p class="fig-note">' + esc(t('sim_scale', { lo: rnd(lo), hi: rnd(hi) })) + '</p>';
    const alt = t('sim_alt') + items.map(i => i.label + ', ' + secs(i.s)).join('; ') + '.';
    return fig('sim', t('t_sim'), body, alt);
  }

  // Ataques que puede aprender: el mismo grupo que el juego (normal y los de sus tipos), agrupado por tier general.
  const LEARN_TIERS = ['S', 'A', 'B', 'C', 'D'];
  const LETTERS = 'abcdefghijklmnopqrstuvwxyz';
  const iconCache = new Map();
  // El icono del juego (ui/icons.js) como SVG: moves.json trae la rejilla de píxeles de cada uno.
  function iconUrl(m) {
    if (iconCache.has(m.id)) return iconCache.get(m.id);
    const [W, H] = m.icon.size;
    let rects = '';
    m.icon.rows.forEach((row, y) => {
      let x = 0;
      while (x < W) {
        const ch = row[x];
        let n = 1;
        while (x + n < W && row[x + n] === ch) n++;
        if (ch !== '.') rects += '<rect x="' + x + '" y="' + y + '" width="' + n + '" height="1" fill="' + m.icon.pal[LETTERS.indexOf(ch)] + '"/>';
        x += n;
      }
    });
    const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H +
      '" shape-rendering="crispEdges">' + rects + '</svg>';
    const u = 'data:image/svg+xml,' + encodeURIComponent(svg);
    iconCache.set(m.id, u);
    return u;
  }

  function learn(p, d, moves) {
    const pool = moves.filter(m => m.type === 'normal' || p.types.includes(m.type));
    const rows = LEARN_TIERS.map(tier => {
      const ms = pool.filter(m => m.tier === tier).sort((a, b) => b.score - a.score);
      if (!ms.length) return '';
      const chips = ms.map(m => '<li class="lt-move' + (m.id === d[2] ? ' start' : '') + '"><img class="lt-ico" src="' + iconUrl(m) +
        '" alt="" width="32" height="32">' + esc(EN ? m.en.name : m.name) +
        (m.id === d[2] ? ' <em>' + esc(t('learn_start')) + '</em>' : '') + '</li>').join('');
      return '<div class="lt-row"><span class="tier-badge ' + tier + '">' + tier + '</span><ul class="lt-moves">' + chips + '</ul></div>';
    }).join('');
    return '<section class="fig anim fig-learn"><figcaption><h3>' + esc(t('t_learn')) + '</h3></figcaption>' +
      '<p class="learn-lede">' + esc(t('learn_lede', { n: pool.length })) + '</p>' + rows + '</section>';
  }

  // Build recomendada (build/combos.py): inicio, tres ataques (el primero, el mejor de la simulación) y un potenciador,
  // opcionales para los huecos que se abren más tarde y los objetos de la tier list. Una tarjeta oscura que se lee sola
  // en una captura: lleva el sprite, el nombre y la marca del sitio.
  const ITEM_COLOR = '#f2ecd8';
  function tile(m, cls, badge, i) {
    const color = TYPE_COLOR[m.type] || ITEM_COLOR;
    const nm = EN ? m.en.name : m.name;
    return '<li class="bd-tile' + cls + '" style="--tc:' + color + ';--i:' + i + '">' + (badge || '') +
      '<span class="bd-ico"><img src="' + iconUrl(m) + '" alt="" width="48" height="48"></span><span class="bd-nm">' + esc(nm) + '</span></li>';
  }
  const badgeOf = (kind, label) => '<b class="bd-badge" title="' + esc(label) + '" aria-label="' + esc(label) + '">' +
    (kind === 'crown' || kind === 'sparkle' ? '<i class="ico ico-' + kind + '" aria-hidden="true"></i>' : kind) + '</b>';
  const meter = (label, v, cls) => '<div class="bd-meter ' + cls + '"><span>' + esc(label) + '</span>' +
    '<i class="bd-track" role="img" aria-label="' + v + ' %"><b style="width:' + v + '%"></b></i><strong>' + v + '&nbsp;%</strong></div>';

  function build(p, d, moves, items, name, scale) {
    const [superPct, neutralPct, ids, , altIds] = d[9];
    const find = id => moves.find(m => m.id === id);
    const slots = ids.map(find).filter(Boolean);
    const attacks = slots.slice(0, -1), boost = slots[slots.length - 1];
    const start = find(d[2]);
    const alts = altIds.map(find).filter(Boolean);
    const attackTiles = attacks.map((m, i) => tile(m, '', badgeOf(i === 0 ? 'crown' : String(i + 1), i === 0 ? t('build_best') : t('build_slot', { n: i + 1 })), i)).join('');
    const boostTile = tile(boost, ' bd-boost', badgeOf('sparkle', t('build_boost')), attacks.length);
    const sprite = '<span class="bd-sprite" style="--tc:' + (TYPE_COLOR[p.types[0]] || '#888') + ';--tc2:' + (TYPE_COLOR[p.types[1] || p.types[0]] || '#888') +
      '"><img class="px" src="' + sprites + p.dex + spriteExt + '" width="' + p.w * scale + '" height="' + p.h * scale + '" alt=""></span>';
    const group = (key, list, cls) => list.length ? '<div class="bd-group"><span class="bd-cap">' + esc(t(key)) + '</span><ul class="bd-small ' + cls + '">' + list + '</ul></div>' : '';
    const altTiles = alts.map((m, i) => tile(m, ' sm', '', i)).join('');
    const itemTiles = items.map((m, i) => tile(m, ' sm item', '', i)).join('');
    return '<section class="fig anim fig-build" id="build" aria-labelledby="bd-h"><div class="bd-card" style="--p1:' + (TYPE_COLOR[p.types[0]] || '#888') + ';--p2:' + (TYPE_COLOR[p.types[1] || p.types[0]] || '#888') + '">' +
      '<header class="bd-head">' + sprite + '<div><h2 id="bd-h">' + esc(t('t_build')) + '</h2><span class="bd-who">' + esc(name) + '</span></div>' +
      '<button class="bd-share" type="button" aria-label="' + esc(t('build_share')) + '" title="' + esc(t('build_share')) + '"><svg viewBox="0 0 12 12" width="20" height="20" aria-hidden="true" focusable="false" shape-rendering="crispEdges">' +
      '<path d="M4 6l4-4M4 6l4 4" stroke="currentColor" stroke-width="1.4" fill="none"/>' +
      '<path fill="currentColor" d="M8 0h4v4H8zM0 4h4v4H0zM8 8h4v4H8z"/></svg></button>' +
      '<span class="bd-toast" role="status" aria-live="polite"></span></header>' +
      '<div class="bd-flow"><div class="bd-start"><span class="bd-cap">' + esc(t('build_start')) + '</span><ul>' +
      (start ? tile(start, ' bd-startmove', '', 0) : '') + '</ul></div><i class="ico ico-arrow bd-arrow" aria-hidden="true"></i>' +
      '<ol class="bd-slots">' + attackTiles + boostTile + '</ol></div>' +
      '<div class="bd-more">' + group('build_alt', altTiles, 'bd-alts') + group('build_items', itemTiles, 'bd-items') + '</div>' +
      '<div class="bd-meters">' + meter(t('build_super'), superPct, 'bd-super') + meter(t('build_neutral'), neutralPct, 'bd-neutral') + '</div>' +
      '<p class="bd-brand">' + esc(t('build_brand')) + '</p></div></section>';
  }

  function wireShare(p) {
    const btn = document.querySelector('.bd-share');
    if (!btn) return;
    const toast = document.querySelector('.bd-toast');
    btn.addEventListener('click', () => {
      const url = location.origin + location.pathname + '?id=' + p.dex + '#build';
      const done = () => { toast.textContent = t('build_copied'); setTimeout(() => { toast.textContent = ''; }, 1800); };
      if (navigator.share) {
        navigator.share({ title: document.title, url }).catch(() => {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(done, () => {});
      }
    });
  }

  const tpl = (id, attr, val) => {
    const el = document.querySelector('#' + id).content.querySelector('[' + attr + '="' + val + '"]');
    return el ? el.innerHTML : '';
  };

  function flagsHtml(flags) {
    return FLAGS.filter(f => flags & f[0]).map(f => {
      const text = esc(t(f[2]));
      return '<span class="flag" role="img" tabindex="0" aria-label="' + text + '" data-tip="' + text + '" title="' + text + '"><i class="ico ico-' + f[1] + '" aria-hidden="true"></i></span>';
    }).join('');
  }

  function render(p, d, range, moveName, prev, next, moves, medians, items) {
    const name = EN ? p.nameEn : p.name;
    const scale = Math.max(1, Math.min(5, Math.floor(FICHA_BOX / Math.max(p.w, p.h))));
    const [rank, tier] = p.r;
    const otherName = !EN && p.nameEn !== p.name ? '<small>' + esc(p.nameEn) + '</small>' : '';
    const pills = '<span class="types">' + p.types.map(ty => tpl('tpl-types', 'data-t', ty)).join('') + '</span>';
    // La rareza se ve como la Poké Ball del juego, con su nombre al lado (Común... Legendaria).
    const rarityName = t('rar_' + p.rarity);
    const rarity = '<span class="rarity r' + p.rarity + '"><svg class="rball" viewBox="0 0 12 12" aria-hidden="true">' +
      '<use href="#rball-' + p.rarity + '"/></svg>' + esc(rarityName) + '</span>';
    const legendary = p.legendary ? '<span class="chip">' + esc(t('legendary')) + '</span>' : '';
    const link = (q, left) => {
      const label = esc(EN ? q.nameEn : q.name) + '<span> ' + esc(t('dex_no', { dex: q.dex })) + '</span>';
      return '<a href="?id=' + q.dex + '">' + (left ? '← ' + label : label + ' →') + '</a>';
    };
    const pager = (prev ? link(prev, true) : '<span></span>') + (next ? link(next, false) : '<span></span>');
    root.innerHTML =
      '<p class="crumbs"><a href="' + home + 'index.html">' + esc(t('crumb_home')) + '</a> › ' + esc(name) + '</p>' +
      '<div class="ficha-head"><div class="ficha-sprite" style="--tc:' + (TYPE_COLOR[p.types[0]] || '#888') +
      ';--tc2:' + (TYPE_COLOR[p.types[1] || p.types[0]] || '#888') + '"><img class="px" src="' + sprites + p.dex + spriteExt + '" width="' + p.w * scale +
      '" height="' + p.h * scale + '" alt="' + esc(t('sprite_alt', { name })) + '"></div><div>' +
      '<h1>' + esc(name) + ' ' + otherName + '<small>' + esc(t('dex_no', { dex: p.dex })) + '</small></h1>' +
      '<div class="facts">' + pills + ' ' + rarity + ' ' + legendary + ' ' + tpl('tpl-regions', 'data-gen', p.bannerId) + '</div>' +
      '<div class="rankline"><span class="tier-badge ' + tier + '" title="' + esc(t('tier', { t: tier })) + '">' + tier + '</span>' +
      '<strong>' + rank + '</strong><span>/ ' + TOTAL + '</span>' + flagsHtml(d[7]) + '</div></div></div>' +
      build(p, d, moves, items, name, Math.max(1, Math.min(4, Math.floor(72 / Math.max(p.w, p.h))))) +
      baseStats(d, medians, name) + rankBand(p, name) + pillars(d, name) + sim(d, range, moveName) + learn(p, d, moves) + methods(p, d, name) +
      '<nav class="pager" aria-label="' + esc(t('pager_aria')) + '">' + pager + '</nav>';
    const label = EN || p.nameEn === p.name ? name : p.name + ' (' + p.nameEn + ')';
    document.title = t('ficha_title', { name, tier });
    const desc = document.querySelector('meta[name=description]');
    if (desc) desc.setAttribute('content', t('ficha_desc', { label, tier, rank }));
    document.querySelectorAll('.lang a[hreflang]:not([aria-current])').forEach(a => { a.href = a.getAttribute('href').split('?')[0] + location.search + location.hash; });
    wireShare(p);
    if (location.hash === '#build') document.getElementById('build').scrollIntoView();
    const figs = [...root.querySelectorAll('.anim')];
    if (!('IntersectionObserver' in window)) { figs.forEach(f => f.classList.add('in')); return; }
    const io = new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
    }), { threshold: 0.2 });
    figs.forEach(f => io.observe(f));
  }

  function missing() {
    root.innerHTML = '<h1>' + esc(t('f_missing')) + '</h1><p><a href="' + home + 'index.html">' + esc(t('crumb_home')) + '</a></p>';
  }

  const getJSON = name => fetch(html.dataset.assets + 'data/' + name).then(r => {
    if (!r.ok) throw new Error(name + ' ' + r.status);
    return r.json();
  });
  const id = Number(new URLSearchParams(location.search).get('id'));
  Promise.all([getJSON('pokemon-index.json'), getJSON('species.json'), getJSON('moves.json')]).then(([index, species, moves]) => {
    const i = index.findIndex(p => p.dex === id);
    const d = species.d[id];
    if (i < 0 || !d) { missing(); return; }
    const byId = new Map(moves.map(m => [m.id, m]));
    const moveName = mid => { const m = byId.get(mid); return m ? (EN ? m.en.name : m.name) : mid; };
    render(index[i], d, species.sim, moveName, index[i - 1], index[i + 1], moves, species.statMedian, species.items);
  }).catch(err => { root.textContent = err.message; });
})();
