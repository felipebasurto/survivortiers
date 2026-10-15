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
  const FLAGS = [[1, 'potion', 'flag_status'], [2, 'sword', 'flag_melee'], [4, 'trophy', 'flag_capped']];
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

  function rankBand(p, name) {
    const [rank, tier, lo, hi] = p.r;
    const [w0, w1] = zoomWindow(lo, hi);
    const at = n => (n - w0) / (w1 - w0) * 100;
    const x = at(rank);
    const sd = x < 14 ? 'l' : x > 86 ? 'r' : 'c';
    const noteStyle = sd !== 'r' ? 'left:' + f2(x) + '%' : 'right:' + f2(100 - x) + '%';
    const visible = CUTS.map(c => [c, Math.max(c[1], w0), Math.min(c[2], w1)]).filter(v => v[2] >= v[1]);
    const segs = visible.map(([c, a, b]) => '<i class="rb-seg' + (c[0] === tier ? ' on' : '') + '" style="flex:' + (b - a + 1) + '"></i>').join('');
    const letters = visible.map(([c, a, b]) => '<i style="flex:' + (b - a + 1) + '">' + c[0] + '</i>').join('');
    const marks = [...new Set([w0, w1, ...RANK_TICKS.filter(n => n >= w0 && n <= w1)])].sort((a, b) => a - b);
    const kept = [];
    marks.forEach(n => {
      if (kept.length && at(n) - at(kept[kept.length - 1]) < 7) {
        if (n !== w1) return;
        kept.pop();
      }
      kept.push(n);
    });
    const ticks = kept.map(n => '<span style="left:' + f2(at(n)) + '%">' + n + '</span>').join('');
    const span = Math.max(at(hi) - at(lo), 0.5);
    const zoomed = w0 !== 1 || w1 !== TOTAL;
    const zoomNote = zoomed ? '<p class="zoom-note">' + esc(t('band_zoom', { lo: w0, hi: w1 })) + '</p>' : '';
    const body = '<div class="rb-note rb-' + sd + '" style="' + noteStyle + '"><b>' + esc(t('band_rank', { rank })) + '</b>' +
      '<span>' + esc(t('band_range', { lo, hi })) + '</span></div>' +
      '<div class="rb-track">' + segs + '<b class="rb-range" style="left:' + f2(at(lo)) + '%;width:' + f2(span) + '%"></b>' +
      '<b class="rb-dot" style="left:' + f2(x) + '%"></b></div>' +
      '<div class="rb-tiers" aria-hidden="true">' + letters + '</div><div class="rb-ticks" aria-hidden="true">' + ticks + '</div>' +
      zoomNote;
    return fig('band', t('t_band'), body, t('band_alt', { name, rank, total: TOTAL, tier, lo, hi }));
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
    const body = dotplot({ text: t('methods_final', { rank: final }), x: xf, side: side(xf) }, rows, [String(w0), String(w1)]) + zoomNote;
    const alt = t('methods_alt', { name, rank: final }) + rows.map(r => t('methods_alt_item', { label: r.label, v: r.v })).join('; ') + '.';
    return fig('methods', t('t_methods'), body, alt);
  }

  function sim(d, range, moveName) {
    const [lo, hi, median] = range;
    const items = [{ label: t('sim_start', { name: moveName(d[2]) }), s: d[3] }];
    if (d[4] !== d[2]) items.push({ label: t('sim_best', { name: moveName(d[4]) }), s: d[5] });
    const xOf = s => (s - lo) / (hi - lo) * 100;
    const xm = xOf(median);
    const secs = s => rnd(s) + ' s';
    const body = dotplot({ text: t('sim_median', { s: rnd(median) }), x: xm, side: side(xm) },
      items.map(i => ({ label: i.label, x: xOf(i.s), text: secs(i.s) })), [rnd(lo) + ' s', rnd(hi) + ' s']);
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

  function render(p, d, range, moveName, prev, next, moves) {
    const name = EN ? p.nameEn : p.name;
    const scale = Math.max(1, Math.min(5, Math.floor(FICHA_BOX / Math.max(p.w, p.h))));
    const [rank, tier] = p.r;
    const otherName = !EN && p.nameEn !== p.name ? '<small>' + esc(p.nameEn) + '</small>' : '';
    const pills = '<span class="types">' + p.types.map(ty => tpl('tpl-types', 'data-t', ty)).join('') + '</span>';
    const stars = '<span class="stars" role="img" aria-label="' + esc(t('stars_alt', { n: p.rarity })) + '">' +
      '★'.repeat(p.rarity) + '☆'.repeat(5 - p.rarity) + '</span>';
    const legendary = p.legendary ? '<span class="chip">' + esc(t('legendary')) + '</span>' : '';
    const link = (q, left) => {
      const label = esc(EN ? q.nameEn : q.name) + '<span> ' + esc(t('dex_no', { dex: q.dex })) + '</span>';
      return '<a href="?id=' + q.dex + '">' + (left ? '← ' + label : label + ' →') + '</a>';
    };
    const pager = (prev ? link(prev, true) : '<span></span>') + (next ? link(next, false) : '<span></span>');
    root.innerHTML =
      '<p class="crumbs"><a href="' + home + 'index.html">' + esc(t('crumb_home')) + '</a> › ' + esc(name) + '</p>' +
      '<div class="ficha-head"><div class="ficha-sprite"><img class="px" src="' + sprites + p.dex + spriteExt + '" width="' + p.w * scale +
      '" height="' + p.h * scale + '" alt="' + esc(t('sprite_alt', { name })) + '"></div><div>' +
      '<h1>' + esc(name) + ' ' + otherName + '<small>' + esc(t('dex_no', { dex: p.dex })) + '</small></h1>' +
      '<div class="facts">' + pills + ' ' + stars + ' ' + legendary + ' ' + tpl('tpl-regions', 'data-gen', p.bannerId) + '</div>' +
      '<div class="rankline"><span class="tier-badge ' + tier + '" title="' + esc(t('tier', { t: tier })) + '">' + tier + '</span>' +
      '<strong>' + rank + '</strong><span>/ ' + TOTAL + '</span>' + flagsHtml(d[7]) + '</div></div></div>' +
      rankBand(p, name) + pillars(d, name) + methods(p, d, name) + sim(d, range, moveName) + learn(p, d, moves) +
      '<nav class="pager" aria-label="' + esc(t('pager_aria')) + '">' + pager + '</nav>';
    const label = EN || p.nameEn === p.name ? name : p.name + ' (' + p.nameEn + ')';
    document.title = t('ficha_title', { name, tier });
    const desc = document.querySelector('meta[name=description]');
    if (desc) desc.setAttribute('content', t('ficha_desc', { label, tier, rank }));
    document.querySelectorAll('.lang a[hreflang]:not([aria-current])').forEach(a => { a.href = a.getAttribute('href').split('?')[0] + location.search; });
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
    render(index[i], d, species.sim, moveName, index[i - 1], index[i + 1], moves);
  }).catch(err => { root.textContent = err.message; });
})();
