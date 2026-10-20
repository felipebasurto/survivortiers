/* SurvivorTiers · ficha interactiva. La página estática ya trae el texto (build/static_ficha.py); este script
   sustituye #ficha por los gráficos. En /pokemon/?id=N no hay data-dex: redirige a /pokemon/<n>-<nombre>/.
   Los textos llegan en #i18n (build/render.py). Mismos gráficos que build/charts.py. */
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
  let CUTS = [];
  const PILLARS = ['stats', 'moves', 'typedef', 'size'];
  const METHODS = ['sheet', 'simStart', 'simBest', 'lateMax', 'lateFresh'];
  const FLAGS = [[1, 'potion', 'flag_status'], [2, 'sword', 'flag_melee']];
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
  let RANK_TICKS = [];
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

  function rankBand(p, name) {
    const [rank, tier, lo, hi] = p.r;
    const [w0, w1] = zoomWindow(Math.min(lo, rank), Math.max(hi, rank));
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
    const body = '<div class="rb-view">' +
      '<div class="rb-note rb-' + sd + '" style="' + noteStyle + '"><b>' + esc(t('band_rank', { rank })) + '</b>' +
      '<span>' + esc(t('band_range', { lo, hi })) + '</span></div>' +
      '<div class="rb-track">' + segs + '<b class="rb-range" style="left:' + f2(at(lo)) + '%;width:' + f2(span) + '%"></b>' +
      '<b class="rb-dot" style="left:' + f2(x) + '%"></b></div>' +
      '<div class="rb-tiers" aria-hidden="true">' + letters + '</div><div class="rb-ticks" aria-hidden="true">' + ticks + '</div></div>';
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
    const body = dotplot({ text: t('methods_final', { rank: final }), x: xf, side: side(xf) }, rows, [String(w0), String(w1)]);
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
    const noshop = d[11];
    const shopNote = noshop != null && Math.abs(noshop - items[0].s) >= 0.5
      ? '<p class="fig-note sim-noshop">' + esc(t('sim_noshop', { name: moveName(d[2]), s: rnd(noshop) })) + '</p>' : '';
    const body = '<div class="sim-chart">' + ref + rows + '<div class="mt-axis sim-axis" aria-hidden="true">' + axis + '</div></div>' + gainNote + shopNote;
    const alt = t('sim_alt') + items.map(i => i.label + ', ' + secs(i.s)).join('; ') + '.'
      + (shopNote ? ' ' + t('sim_noshop', { name: moveName(d[2]), s: rnd(noshop) }) : '');
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

  // Físico, especial o estado (build/game_moves.py). Solo los movimientos lo llevan: objetos y cartas no.
  const dmgTag = m => m.damage ? '<span class="cat-tag is-' + m.damage + '" title="' + esc(t('dmg_tip_' + m.damage)) + '">' +
    esc(t('dmg_' + m.damage)) + '</span>' : '';
  // Misma clave que game_moves.shape_key y que la etiqueta de ataques.html (mv_kind_*).
  const shapeKey = m => {
    const mech = m.mech || {};
    if (m.kind === 'projectile' && mech.homing > 0) return 'homing';
    if (m.kind === 'projectile' && mech.pierce > 0) return 'pierce';
    return m.kind;
  };
  const shapeTag = m => {
    if (!m || !m.kind) return '';
    const mark = m.nuevo ? '<span class="mv-new">' + esc(t('mv_new')) + '</span>' : '';
    return '<span class="mv-shape">' + esc(t('mv_kind_' + shapeKey(m))) + '</span>' + mark;
  };
  const moveTags = (m, withShape) => {
    const bits = dmgTag(m) + (withShape ? shapeTag(m) : '');
    return bits ? '<span class="bd-tags">' + bits + '</span>' : '';
  };
  const learnPool = (p, moves) => moves.filter(m => m.type === 'normal' || p.types.includes(m.type));
  function learn(p, pair, moves) {
    const pool = learnPool(p, moves);
    const inBuild = new Set(BUILD_KINDS.flatMap(k => pair[k] ? pair[k].moves : []));
    const chips = ms => ms.map(m => '<li class="lt-move' + (inBuild.has(m.id) ? ' in-build' : '') +
      '" style="--tc:' + (TYPE_COLOR[m.type] || ITEM_COLOR) + '"><img class="lt-ico" src="' + iconUrl(m) +
      '" alt="" width="32" height="32">' + esc(EN ? m.en.name : m.name) + moveTags(m, inBuild.has(m.id)) + '</li>').join('');
    const rows = LEARN_TIERS.map(tier => {
      const ms = pool.filter(m => m.tier === tier).sort((a, b) => b.score - a.score);
      if (!ms.length) return '';
      return '<div class="lt-row"><span class="tier-badge ' + tier + '">' + tier + '</span><ul class="lt-moves">' + chips(ms) + '</ul></div>';
    });
    // Boosts have no tier (the tier list ranks attacks): one row of their own, in the game's order.
    const boosts = pool.filter(m => !m.tier);
    if (boosts.length) rows.push('<div class="lt-row boosts"><span class="lt-label">' + esc(t('learn_boosts')) +
      '</span><ul class="lt-moves">' + chips(boosts) + '</ul></div>');
    return rows.join('');
  }

  const ITEM_COLOR = '#f2ecd8';
  const SHARE_SVG = '<svg viewBox="0 0 12 12" width="20" height="20" aria-hidden="true" focusable="false" shape-rendering="crispEdges">' +
    '<path d="M4 6l4-4M4 6l4 4" stroke="currentColor" stroke-width="1.4" fill="none"/>' +
    '<path fill="currentColor" d="M8 0h4v4H8zM0 4h4v4H0zM8 8h4v4H8z"/></svg>';
  const typeVars = p => '--p1:' + (TYPE_COLOR[p.types[0]] || '#888') + ';--p2:' + (TYPE_COLOR[p.types[1] || p.types[0]] || '#888');
  const capOf = key => '<h3 class="bd-cap">' + esc(t(key)) + '</h3>';
  const meter = (label, v, cls) => '<div class="bd-meter ' + cls + '"><span>' + esc(label) + '</span>' +
    '<i class="bd-track" role="img" aria-label="' + v + ' %"><b style="width:' + v + '%"></b></i><strong>' + v + '&nbsp;%</strong></div>';

  // Dos builds de la simulación, la mejor de cuerpo a cuerpo y la mejor a distancia (species.builds, build/builds.py).
  // Una build sin ataques que le valgan no sale. La de mayor puntuación lleva la marca; la otra dice cuánto le falta.
  const BUILD_KINDS = ['melee', 'ranged'];
  const BUILD_NAME = { melee: 'bd_melee', ranged: 'bd_ranged' };
  const BUILD_OTHER = { melee: 'bd_other_ranged', ranged: 'bd_other_melee' };
  const GAP_SMALL_PCT = 5;
  const numText = n => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, EN ? ',' : '.');
  const decText = (x, d) => { const s = x.toFixed(d); return EN ? s : s.replace('.', ','); };
  const pctText = v => Math.round(v) + (EN ? '%' : '\u00a0%');
  const gapPct = (high, low) => high > 0 ? Math.round((high - low) / high * 100) : 0;
  const winnerOf = pair => {
    const have = BUILD_KINDS.filter(k => pair[k]);
    if (have.length < 2) return have[0] || null;
    if (pair.melee.score === pair.ranged.score) return null;
    return pair.melee.score > pair.ranged.score ? 'melee' : 'ranged';
  };

  function verdict(kind, b, other, win) {
    if (!other) return '';
    if (win === kind) return '<p class="bd-verdict is-best">' + esc(t('bd_best')) + '</p>';
    const gap = win === null ? 0 : gapPct(other.score, b.score);
    if (gap === 0) return '<p class="bd-verdict">' + esc(t('bd_tie')) + '</p>';
    const key = gap < GAP_SMALL_PCT ? 'bd_gap_small' : 'bd_gap';
    return '<p class="bd-verdict">' + esc(t(key, { pct: pctText(gap), other: t(BUILD_OTHER[kind]) })) + '</p>';
  }

  // Una fila: número (vacío en el inicio y en los objetos), icono, nombre y etiquetas; una marca opcional a la derecha.
  // Los potenciadores van marcados.
  function moveRow(m, n, pill, buff) {
    const nm = EN ? m.en.name : m.name;
    return '<li class="bd-row' + (buff ? ' is-buff' : '') + '" style="--tc:' + (TYPE_COLOR[m.type] || ITEM_COLOR) + '">' +
      '<span class="bd-n">' + n + '</span>' +
      '<span class="bd-ico"><img src="' + iconUrl(m) + '" alt="" width="32" height="32"></span>' +
      '<span class="bd-info"><span class="bd-nm">' + esc(nm) + '</span>' + moveTags(m, true) + '</span>' +
      (pill ? '<span class="bd-pill' + (pill.gold ? ' is-gold' : '') + '">' + esc(pill.text) + '</span>' : '') + '</li>';
  }

  function buildOption(kind, b, other, moves, cards, win) {
    if (!b) return '';
    const head = '<h3 class="bd-kind">' + esc(t(BUILD_NAME[kind])) + '</h3>';
    const ids = b.moves, nb = b.nBoost;
    const rows = ids.map((id, i) => {
      const m = moves.find(x => x.id === id);
      return m ? moveRow(m, i + 1, null, i >= ids.length - nb) : '';
    }).join('');
    const stats = '<dl class="bd-stats">' +
      '<div><dt>' + esc(t('bd_time')) + '</dt><dd>' + decText(b.time, 1) + ' s</dd></div>' +
      '<div><dt>' + esc(t('bd_dealt')) + '</dt><dd>' + numText(b.dealt) + '</dd></div>' +
      '<div><dt>' + esc(t('bd_kills')) + '</dt><dd>' + decText(b.kills, 1) + '</dd></div>' +
      '<div><dt>' + esc(t('bd_score')) + '</dt><dd>' + decText(b.score, 1) + '</dd></div></dl>';
    const [cardIds, gateId] = b.cards;
    const cardItems = cardIds.map((id, i) => {
      const m = cards[id];
      if (!m) return '';
      const gate = id === gateId;
      return '<li class="' + (gate ? 'is-gate' : '') + '"><span class="bd-n">' + (i + 1) + '</span>' +
        '<span class="bd-nm">' + esc(EN ? m.en.name : m.name) + '</span>' +
        (gate ? '<b class="bd-gate" title="' + esc(t('build_card_once')) + '">1×</b>' : '') + '</li>';
    }).join('');
    const cardsHtml = '<p class="bd-cap">' + esc(t('build_cards')) + '</p><ol class="bd-cardlist">' + cardItems + '</ol>' +
      (gateId ? '<p class="bd-legend">' + esc(t('build_card_once')) + '</p>' : '');
    const note = kind === 'melee' ? '<p class="bd-note">' + esc(t('bd_melee_note')) + '</p>' : '';
    return '<article class="bd-opt' + (win === kind && other ? ' is-best' : '') + '" data-build="' + kind + '">' + head +
      verdict(kind, b, other, win) + '<ol class="bd-rows">' + rows + '</ol>' + stats + cardsHtml + note + '</article>';
  }

  function build(p, d, moves, items, name, scale, cards, pair) {
    const [superPct, neutralPct] = d[9];
    const win = winnerOf(pair);
    const sprite = '<span class="bd-sprite" style="--tc:' + (TYPE_COLOR[p.types[0]] || '#888') +
      '"><img class="px" src="' + sprites + p.dex + spriteExt + '" width="' + p.w * scale + '" height="' + p.h * scale + '" alt=""></span>';
    const start = moves.find(m => m.id === d[2]);
    const startRow = start ? moveRow(start, '', null) : '';
    const options = BUILD_KINDS.map(kind => buildOption(kind, pair[kind], pair[BUILD_KINDS.find(k => k !== kind)], moves, cards, win)).filter(Boolean);
    const itemRows = items.map((m, i) => moveRow(m, '', i === 0 ? { text: t('build_best_item'), gold: true } : null)).join('');
    return '<section class="fig anim fig-build" id="build" aria-labelledby="bd-h"><div class="bd-card" style="' + typeVars(p) + '">' +
      '<header class="bd-head">' + sprite + '<div><h2 id="bd-h">' + esc(t('t_build')) + '</h2><span class="bd-who">' + esc(name) + '</span></div>' +
      '<button class="bd-share" type="button" aria-label="' + esc(t('build_share')) + '" title="' + esc(t('build_share')) + '">' + SHARE_SVG + '</button>' +
      '<span class="bd-toast" role="status" aria-live="polite"></span></header>' +
      '<div class="bd-block bd-start">' + capOf('build_start') + '<ul class="bd-rows">' + startRow + '</ul></div>' +
      (options.length > 1 ? '<p class="bd-cap">' + esc(t('bd_pair_cap')) + '</p>' : '') +
      '<div class="bd-pair' + (options.length > 1 ? '' : ' is-single') + '">' + options.join('') + '</div>' +
      '<div class="bd-gear">' + capOf('build_items') + '<ul class="bd-rows">' + itemRows + '</ul></div>' +
      '<div class="bd-cover">' + meter(t('build_super'), superPct, 'bd-super') + meter(t('build_neutral'), neutralPct, 'bd-neutral') + '</div>' +
      '<p class="bd-brand">' + esc(t('build_brand')) + '</p></div></section>';
  }

  // Bloques plegables bajo la build: un icono, un título y un adelanto a la derecha; el detalle, al abrirlo.
  const panel = (id, icon, title, aside, body) =>
    '<details class="fx" id="' + id + '"><summary><i class="ico ico-' + icon + '" aria-hidden="true"></i>' +
    '<span class="fx-t">' + esc(title) + '</span>' + (aside ? '<span class="fx-aside">' + aside + '</span>' : '') +
    '<i class="fx-chev" aria-hidden="true"></i></summary><div class="fx-body">' + body + '</div></details>';

  // Adelanto de las estadísticas: seis barritas con el color de su tramo, sin números.
  const statSpark = s => '<span class="fx-spark" aria-hidden="true">' +
    s.map(v => '<i class="b' + bandOf(v) + '" style="height:' + f2(Math.min(100, Math.max(12, v / 160 * 100))) + '%"></i>').join('') + '</span>';

  function wireShare(p) {
    const btn = document.querySelector('.bd-share');
    if (!btn) return;
    const toast = document.querySelector('.bd-toast');
    btn.addEventListener('click', () => {
      const path = location.pathname.replace(/index\.html$/, '');
      const url = location.origin + (path.endsWith('/') ? path : path + '/') + '#build';
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

  // Avisos de la simulación (estado sin reproducir, apertura que sigue en cuerpo a cuerpo...): un icono y una frase, dentro de Ranking.
  const flagList = flags => FLAGS.filter(f => flags & f[0]);
  const flagsHtml = flags => {
    const fs = flagList(flags);
    return fs.length ? '<ul class="fx-flags">' + fs.map(f => '<li><i class="ico ico-' + f[1] + '" aria-hidden="true"></i>' + esc(t(f[2])) + '</li>').join('') + '</ul>' : '';
  };
  const flagIcons = flags => flagList(flags).map(f => '<i class="ico ico-' + f[1] + '" aria-hidden="true"></i>').join('');

  // Resumen (build/summaries.py, data/summaries-<idioma>.json): tres frases con marcas [clave|texto]. Cada marca dice
  // qué dato la respalda; aquí solo se le pone su icono. Una línea por frase: perfil, build y por qué ese puesto.
  const SM_MARK = /\[([^\[\]|]+)\|([^\[\]]+)\]/g;
  const SM_LEAD = ['heart', 'sword', 'trophy'];
  const pixSvg = (cls, d) => '<svg class="sm-px ' + cls + '" viewBox="0 0 12 12" aria-hidden="true" focusable="false" shape-rendering="crispEdges"><path fill="currentColor" fill-rule="evenodd" d="' + d + '"/></svg>';
  // Hitbox: un anillo de píxeles con el cuerpo en medio. Tipos: un escudo.
  const HITBOX_SVG = pixSvg('sm-hb', 'M4 0h4v1H4zM2 1h2v1H2zM8 1h2v1H8zM1 2h1v2H1zM10 2h1v2h-1zM0 4h1v4H0zM11 4h1v4h-1zM1 8h1v2H1zM10 8h1v2h-1zM2 10h2v1H2zM8 10h2v1H8zM4 11h4v1H4zM5 5h2v2H5z');
  const SHIELD_SVG = pixSvg('sm-td', 'M1 1h10v5h-1v2H9v1H8v1H7v1H5v-1H4V9H3V8H2V6H1zM3 3v3h1v2h1v1h2V8h1V6h1V3z');
  const SM_STAT_CARD = { spd: 'spd', hp: 'hp', atk: 'atk' };
  function summary(text, moves, items, cards, bestId) {
    const byId = new Map(moves.map(m => [m.id, m]));
    const item = new Map(items.map(m => [m.id, m]));
    const img = m => '<img class="sm-ico" src="' + iconUrl(m) + '" alt="" width="18" height="18">';
    const mark = (key, inner) => {
      const label = esc(inner);
      const trait = /^(spd|hp|atk|hb|td)(\+|-|--|0)$/.exec(key);
      if (trait) {
        const [, stat, sign] = trait;
        const card = cards[SM_STAT_CARD[stat]];
        const icon = stat === 'hb' ? HITBOX_SVG : stat === 'td' ? SHIELD_SVG : card ? img(card) : '';
        const tone = sign === '+' ? ' good' : sign === '0' ? '' : ' bad';
        return '<b class="sm-t' + tone + '">' + icon + label + '</b>';
      }
      const [role, id] = key.split(':');
      if (role.startsWith('m.') && byId.has(id)) return '<span class="sm-m">' + img(byId.get(id)) + label + '</span>';
      if (role === 'i.best' && item.has(id)) return '<span class="sm-m">' + img(item.get(id)) + label + '</span>';
      if (role === 'c.first' && cards[id]) return '<span class="sm-m">' + img(cards[id]) + label + '</span>';
      if (role === 'up' || role === 'down') {
        const icon = id === 'best_move' && byId.has(bestId) ? img(byId.get(bestId)) : '';
        return '<b class="sm-d ' + role + '"><i aria-hidden="true"></i>' + icon + label + '</b>';
      }
      return '<b class="sm-n">' + label + '</b>';
    };
    const line = s => {
      let out = '', at = 0;
      s.replace(SM_MARK, (all, key, inner, i) => { out += esc(s.slice(at, i)) + mark(key, inner); at = i + all.length; return all; });
      return out + esc(s.slice(at));
    };
    const sentences = text.split(/(?<=\.)\s+/).filter(Boolean);
    return '<div class="sm">' + sentences.map((s, i) => '<p class="sm-l"><i class="ico ico-' + (SM_LEAD[i] || 'sparkle') +
      ' sm-lead" aria-hidden="true"></i><span>' + line(s) + '</span></p>').join('') + '</div>';
  }

  function hero(p, name, rank, tier, sum) {
    const scale = Math.max(1, Math.min(5, Math.floor(FICHA_BOX / Math.max(p.w, p.h))));
    const otherName = !EN && p.nameEn !== p.name ? '<small>' + esc(p.nameEn) + '</small>' : '';
    const pills = '<span class="types">' + p.types.map(ty => tpl('tpl-types', 'data-t', ty)).join('') + '</span>';
    // La rareza se ve como la Poké Ball del juego; el nombre (Común... Legendaria) queda en el texto alternativo.
    const rarityName = esc(t('rar_' + p.rarity));
    const rarity = '<span class="rarity r' + p.rarity + '" role="img" aria-label="' + rarityName + '" title="' + rarityName + '">' +
      '<svg class="rball" viewBox="0 0 12 12" aria-hidden="true"><use href="#rball-' + p.rarity + '"/></svg></span>';
    const legendary = p.legendary ? '<span class="chip">' + esc(t('legendary')) + '</span>' : '';
    const lo = p.r[2], hi = p.r[3];
    const rankTitle = esc(t('ficha_rank', { rank, total: TOTAL }));
    return '<header class="ficha-head">' +
      '<div class="ficha-sprite" style="--tc:' + (TYPE_COLOR[p.types[0]] || '#888') + ';--tc2:' + (TYPE_COLOR[p.types[1] || p.types[0]] || '#888') + '">' +
      '<img class="px" src="' + sprites + p.dex + spriteExt + '" width="' + p.w * scale + '" height="' + p.h * scale + '" alt="' + esc(t('sprite_alt', { name })) + '">' +
      '<span class="tier-badge medal ' + tier + '" title="' + esc(t('tier', { t: tier })) + '">' + tier + '</span></div>' +
      '<div class="fh-main"><h1>' + esc(name) + ' <span class="fh-game">' + esc(t('fh_game')) + '</span> ' + otherName + '<small class="fh-dex">' + esc(t('dex_no', { dex: p.dex })) + '</small></h1>' +
      '<div class="facts">' + pills + rarity + legendary + tpl('tpl-regions', 'data-gen', p.bannerId) + '</div>' +
      '<p class="rankline" title="' + rankTitle + '" aria-label="' + rankTitle + '"><i class="ico ico-trophy" aria-hidden="true"></i><strong>' + rank + '</strong><span>/ ' + TOTAL + '</span>' +
      (lo != null && hi != null ? '<span class="rankband">' + esc(t('band_range', { lo, hi })) + '</span>' : '') + '</p>' +
      '</div>' + (sum || '') + '</header>';
  }

  // Ataque y defensa del juego (js/systems/stats.js): el mismo bloque que build/static_ficha.py. Las barras de ataque
  // van hasta ×1,8 con la línea en ×1,00; las de defensa, hasta 255 con la línea en 75 (daño normal).
  const COMBAT_LO = 0.78, COMBAT_HI = 1.25, COMBAT_REF_DEF = 75, ATK_BAR_MAX = 1.8, DEF_BAR_MAX = 255;
  const KIND_KEY = { phys: 'cb_kind_phys', spec: 'cb_kind_spec', mix: 'cb_kind_mix' };
  const dec2 = x => x.toFixed(2).replace('.', EN ? '.' : ',');
  const combatBar = (cls, label, shown, fill, mark) =>
    '<div class="cb-row ' + cls + '"><span class="cb-name">' + esc(label) + '</span>' +
    '<span class="cb-track"><i class="cb-fill" style="width:' + f2(fill * 100) + '%"></i>' +
    '<b class="cb-mark" style="left:' + f2(mark * 100) + '%"></b></span>' +
    '<output class="cb-val">' + esc(shown) + '</output></div>';
  function combat(p) {
    const v = p.v;
    const atk = combatBar('cb-atk-phys', t('cb_pa'), '×' + dec2(v.pa), v.pa / ATK_BAR_MAX, 1 / ATK_BAR_MAX) +
      combatBar('cb-atk-spec', t('cb_sa'), '×' + dec2(v.sa), v.sa / ATK_BAR_MAX, 1 / ATK_BAR_MAX);
    const dfn = combatBar('cb-def', t('cb_df'), String(v.df), v.df / DEF_BAR_MAX, COMBAT_REF_DEF / DEF_BAR_MAX) +
      combatBar('cb-def', t('cb_sd'), String(v.sd), v.sd / DEF_BAR_MAX, COMBAT_REF_DEF / DEF_BAR_MAX);
    const note = t('cb_note', { less: Math.round((1 - COMBAT_LO) * 100), more: Math.round((COMBAT_HI - 1) * 100) });
    return '<section class="combat" id="combate" aria-labelledby="cb-h" data-kind="' + v.ak + '">' +
      '<header class="cb-head"><h3 id="cb-h">' + esc(t('t_combat')) + '</h3>' +
      '<span class="cb-kind cb-k-' + v.ak + '">' + esc(t(KIND_KEY[v.ak])) + '</span></header>' +
      '<div class="cb-list">' + atk + '</div><div class="cb-list">' + dfn + '</div>' +
      '<p class="cb-note">' + esc(note) + '</p></section>';
  }

  function pager(prev, next) {
    const link = (q, dir) => {
      const k = Math.max(1, Math.min(2, Math.floor(40 / Math.max(q.w, q.h))));
      const slug = q.dex + '-' + globalThis.speciesSlug(q.nameEn);
      return '<a class="pg pg-' + dir + '" href="' + home + 'pokemon/' + slug + '/"><b aria-hidden="true">' + (dir === 'prev' ? '‹' : '›') + '</b>' +
        '<img class="px" src="' + sprites + q.dex + spriteExt + '" width="' + q.w * k + '" height="' + q.h * k + '" alt="" loading="lazy">' +
        '<span>' + esc(EN ? q.nameEn : q.name) + '<small>' + esc(t('dex_no', { dex: q.dex })) + '</small></span></a>';
    };
    return '<nav class="pager" aria-label="' + esc(t('pager_aria')) + '">' + (prev ? link(prev, 'prev') : '<span></span>') + (next ? link(next, 'next') : '<span></span>') + '</nav>';
  }

  function render(p, d, range, moveName, prev, next, moves, medians, items, cards, pair, text) {
    const name = EN ? p.nameEn : p.name;
    const [rank, tier, lo, hi] = p.r;
    const back = '<a class="back" href="' + home + 'index.html"><b aria-hidden="true">‹</b>' + esc(t('crumb_home')) + '</a>';
    const stats = panel('stats', 'heart', t('t_base'), statSpark(d[8]), baseStats(d, medians, name));
    const learnable = panel('moves', 'sword', t('t_learn'), '<b class="fx-n">' + learnPool(p, moves).length + '</b>', learn(p, pair, moves));
    const ranking = panel('ranking', 'trophy', t('t_rank'), flagIcons(d[7]),
      flagsHtml(d[7]) + rankBand(p, name) + pillars(d, name) + sim(d, range, moveName) + methods(p, d, name) +
      '<p class="fx-more"><a href="' + home + 'metodo.html">' + esc(t('rank_how')) + '</a></p>');
    root.innerHTML = back + hero(p, name, rank, tier, text ? summary(text, moves, items, cards, d[4]) : '') +
      build(p, d, moves, items, name, Math.max(1, Math.min(4, Math.floor(56 / Math.max(p.w, p.h)))), cards, pair) +
      combat(p) +
      '<div class="fx-list">' + stats + learnable + ranking + '</div>' + pager(prev, next);
    if (!baked) {
      document.title = t('sheet_title', { name, tier, rank });
      const desc = document.querySelector('meta[name=description]');
      if (desc) desc.setAttribute('content', t('sheet_desc', { name, tier, rank }));
    }
    document.querySelectorAll('.lang a[hreflang]:not([aria-current])').forEach(a => {
      const base = a.getAttribute('href').split('?')[0].split('#')[0];
      a.href = base + location.hash;
    });
    wireShare(p);
    const target = location.hash && document.getElementById(location.hash.slice(1));
    if (target) {
      if (target.tagName === 'DETAILS') target.open = true;
      target.scrollIntoView();
    }
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
  const baked = Number(root.dataset.dex);
  if (!baked) {
    const qid = Number(new URLSearchParams(location.search).get('id'));
    if (!qid) return;
    const mapEl = document.getElementById('slugs');
    if (qid && mapEl) {
      let slug = '';
      try { slug = JSON.parse(mapEl.textContent)[String(qid)] || ''; } catch (e) { slug = ''; }
      if (slug) { location.replace(home + 'pokemon/' + slug + '/' + location.hash); return; }
    }
  }
  const id = baked || Number(new URLSearchParams(location.search).get('id'));
  // Sin resúmenes la ficha se dibuja igual: el bloque es un extra.
  const summaries = getJSON('summaries-' + (EN ? 'en' : 'es') + '.json').catch(() => ({}));
  Promise.all([getJSON('pokemon-index.json'), getJSON('species.json'), getJSON('moves.json'), getJSON('moves_unranked.json'), summaries, getJSON('tiers.json')]).then(([index, species, moves, unranked, texts, tierFile]) => {
    CUTS = tierFile.cuts;
    RANK_TICKS = [1, ...CUTS.map(c => c[2])];
    const i = index.findIndex(p => p.dex === id);
    const d = species.d[id];
    if (i < 0 || !d) { missing(); return; }
    // Boosts are not in the tier list, but a bonded group can still use one.
    moves = moves.concat(unranked);
    const byId = new Map(moves.map(m => [m.id, m]));
    const moveName = mid => { const m = byId.get(mid); return m ? (EN ? m.en.name : m.name) : mid; };
    const pairOf = (species.builds || {})[id] || {};
    render(index[i], d, species.sim, moveName, index[i - 1], index[i + 1], moves, species.statMedian, species.items, species.cards || {}, { melee: pairOf.melee || null, ranged: pairOf.ranged || null }, texts[id]);
  }).catch(err => { root.textContent = err.message; });
})();
