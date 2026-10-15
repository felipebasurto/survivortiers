/* SurvivorTiers · JS sin dependencias: buscador, importación de la colección y las demos de la página Método.
   No hace peticiones salvo a los JSON del propio sitio. No guarda nada (ni cookies ni localStorage).
   SurvivorTiers · dependency-free JS: search, collection import and the Method page demos. It only requests this
   site's own JSON files and stores nothing (no cookies, no localStorage). */
(() => {
  'use strict';
  const html = document.documentElement;
  const assets = html.dataset.assets || '';
  const home = html.dataset.home || '';
  const sprites = html.dataset.sprites || '';
  const spriteExt = html.dataset.spritesExt || '.png';
  const spritesAlt = html.dataset.spritesAlt || '';
  const page = html.dataset.page;
  const EN = html.lang === 'en';
  const TIERS = ['S', 'A', 'B', 'C', 'D'];
  const TYPE_ES = { normal: 'normal', fire: 'fuego', water: 'agua', grass: 'planta', electric: 'electrico', ice: 'hielo',
    fighting: 'lucha', poison: 'veneno', ground: 'tierra', flying: 'volador', psychic: 'psiquico', bug: 'bicho', rock: 'roca',
    ghost: 'fantasma', dragon: 'dragon', dark: 'siniestro', steel: 'acero', fairy: 'hada' };
  const SCALE = 2;
  const NBSP = '\u00a0';

  // 2.000 con punto o coma de miles, también a partir de 1.000 (toLocaleString en es no agrupa cuatro cifras).
  const grouped = (n, sep) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, sep);
  const TEXT = {
    es: {
      loadFail: n => 'No se pudo cargar ' + n,
      loadFailAll: m => 'No se pudieron cargar los datos: ' + m,
      count: (n, total) => n + ' de ' + total,
      cardTitle: (name, dex, rank, tier) => name + ' · nº ' + dex + ' · puesto ' + rank + ' · tier ' + tier,
      pct: v => v + NBSP + '%',
      notJson: 'Eso no es JSON. Copia el resultado entero, de la { a la }.',
      notCollection: 'Eso no es una colección.',
      missingKeys: 'Faltan «dex» o «shiny». Usa el JSON del comando de esta página.',
      pasteFirst: 'Pega primero el resultado del comando.',
      tooBig: 'El archivo es demasiado grande.',
      copied: 'Copiado',
      copyFail: 'No se ha podido copiar. Selecciónalo a mano.',
      noDate: 'sin fecha',
      locale: 'es-ES',
      tierWord: 'Tier', have: 'Tienes', progress: 'Progreso',
      haveOf: (a, b) => a + ' de ' + b,
      shinyTitle: 'Tienes el shiny', shiny: '★',
      owned: n => String(n),
      missingSA: n => 'Te faltan de S y A (' + n + ')',
      allSA: 'Tienes todos los S y A.',
      collectionOf: n => 'Colección de ' + n, yourCollection: 'Tu colección',
      dexStat: () => 'en la Pokédex',
      shinyStat: 'shiny', lastSave: 'última partida',
      unknown: n => n + ' no están en el ranking.',
      byTier: 'Por tier',
      pause: 'Pausa', play: 'Seguir',
      repCount: (n, total) => grouped(n, '.') + ' / ' + grouped(total, '.'),
      stepOf: (i, n) => 'Paso ' + i + ' de ' + n,
      auto: 'Auto', stop: 'Parar',
      over: 'Fin',
    },
    en: {
      loadFail: n => 'Could not load ' + n,
      loadFailAll: m => 'Could not load the data: ' + m,
      count: (n, total) => n + ' of ' + total,
      cardTitle: (name, dex, rank, tier) => name + ' · no. ' + dex + ' · rank ' + rank + ' · tier ' + tier,
      pct: v => v + '%',
      notJson: 'That is not JSON. Copy the whole result, from { to }.',
      notCollection: 'That is not a collection.',
      missingKeys: 'Missing "dex" or "shiny". Use the JSON from this page\'s command.',
      pasteFirst: 'Paste the command result first.',
      tooBig: 'The file is too large.',
      copied: 'Copied',
      copyFail: 'Could not copy. Select it by hand.',
      noDate: 'no date',
      locale: 'en-US',
      tierWord: 'Tier', have: 'You have', progress: 'Progress',
      haveOf: (a, b) => a + ' of ' + b,
      shinyTitle: 'You have the shiny', shiny: '★',
      owned: n => String(n),
      missingSA: n => 'Missing from S and A (' + n + ')',
      allSA: 'You have every S and A.',
      collectionOf: n => 'Collection of ' + n, yourCollection: 'Your collection',
      dexStat: () => 'in the Pokédex',
      shinyStat: 'shiny', lastSave: 'last save',
      unknown: n => n + ' not in the ranking.',
      byTier: 'By tier',
      pause: 'Pause', play: 'Play',
      repCount: (n, total) => grouped(n, ',') + ' / ' + grouped(total, ','),
      stepOf: (i, n) => 'Step ' + i + ' of ' + n,
      auto: 'Auto', stop: 'Stop',
      over: 'Over',
    },
  }[EN ? 'en' : 'es'];

  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const plain = s => String(s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const monName = p => (EN ? p.nameEn : p.name);
  const getJSON = name => fetch(assets + 'data/' + name).then(r => {
    if (!r.ok) throw new Error(TEXT.loadFail(name));
    return r.json();
  });

  const state = { mons: null, byDex: null, cards: [] };

  // ---------------------------------------------------------------- tarjetas
  function card(p, extraClass, extraHtml) {
    const [rank, tier] = p.r;
    const cls = 'mon' + (extraClass ? ' ' + extraClass : '');
    const title = TEXT.cardTitle(monName(p), p.dex, rank, tier);
    return '<a class="' + cls + '" href="' + home + 'pokemon/?id=' + p.dex + '" data-dex="' + p.dex + '" title="' + esc(title) + '">' +
      '<span class="sp"><img class="px" src="' + sprites + p.dex + spriteExt + '" width="' + p.w * SCALE + '" height="' + p.h * SCALE +
      '" alt="" loading="lazy" decoding="async"></span><span class="nm">' + esc(monName(p)) + '</span><span class="rk">' + rank + '</span>' +
      (extraHtml || '') + '</a>';
  }

  // ---------------------------------------------------------------- tier list
  function applySearch() {
    const q = plain(($('#q') || {}).value || '').trim();
    const terms = q.split(/\s+/).filter(Boolean);
    let shown = 0;
    state.cards.forEach(el => {
      const p = state.byDex.get(+el.dataset.dex);
      const ok = terms.every(term => p.q.includes(term));
      el.classList.toggle('dim', !ok);
      if (ok) shown++;
    });
    TIERS.forEach(t => {
      const sec = $('#tier-' + t);
      sec.classList.toggle('hidden', terms.length > 0 && $$('.mon:not(.dim)', sec).length === 0);
    });
    $('#count').textContent = terms.length ? TEXT.count(shown, state.mons.length) : '';
  }

  // ---------------------------------------------------------------- orden de la lista
  // Cómo se compara cada criterio, si de inicio va de mayor a menor, y qué se escribe en la tarjeta en su lugar del puesto.
  const dec = (v, n) => v.toFixed(n).replace('.', EN ? '.' : ',');
  const pct = v => v + (EN ? '%' : NBSP + '%');
  const SORTS = {
    rank: { val: p => p.r[0], desc: false, show: p => p.r[0] },
    name: { val: p => monName(p), desc: false, text: true, show: p => p.r[0] },
    dex: { val: p => p.dex, desc: false, show: p => p.r[0] },
    atk: { val: p => p.v.atk, desc: true, show: p => dec(p.v.atk, 2) },
    hp: { val: p => p.v.hp, desc: true, show: p => p.v.hp },
    spd: { val: p => p.v.spd, desc: true, show: p => p.v.spd },
    ehp: { val: p => p.v.ehp, desc: true, show: p => p.v.ehp },
    rad: { val: p => p.v.rad, desc: true, show: p => dec(p.v.rad, 1) },
    td: { val: p => p.v.td, desc: true, show: p => pct(p.v.td) },
    mv: { val: p => p.v.mv, desc: true, show: p => pct(p.v.mv) },
    st: { val: p => p.v.st, desc: true, show: p => pct(p.v.st) },
    rar: { val: p => p.rarity, desc: true, show: p => p.rarity },
  };
  let sortKey = 'rank', sortDesc = false;

  function sortedCards() {
    const spec = SORTS[sortKey], sign = sortDesc ? -1 : 1;
    return [...state.cards].sort((a, b) => {
      const pa = state.byDex.get(+a.dataset.dex), pb = state.byDex.get(+b.dataset.dex);
      const c = spec.text ? spec.val(pa).localeCompare(spec.val(pb), EN ? 'en' : 'es') : spec.val(pa) - spec.val(pb);
      return c * sign || pa.r[0] - pb.r[0];
    });
  }

  function applySort() {
    const flat = sortKey !== 'rank';
    $('#tierlist').classList.toggle('flat-mode', flat);
    if (flat) {
      // Una sola lista, ordenada por el criterio; cada tarjeta enseña ese valor en lugar del puesto.
      const grid = $('#flat');
      sortedCards().forEach(el => {
        grid.appendChild(el);
        el.querySelector('.rk').textContent = SORTS[sortKey].show(state.byDex.get(+el.dataset.dex));
      });
    } else {
      // Vuelve a las tiers, en orden de puesto.
      [...state.cards].sort((a, b) => state.byDex.get(+a.dataset.dex).r[0] - state.byDex.get(+b.dataset.dex).r[0])
        .forEach(el => {
          const p = state.byDex.get(+el.dataset.dex);
          $('#tier-' + p.r[1] + ' .grid').appendChild(el);
          el.querySelector('.rk').textContent = p.r[0];
        });
    }
    applySearch();
  }

  function syncDir() {
    const b = $('#dir');
    b.textContent = sortDesc ? b.dataset.desc : b.dataset.asc;
  }

  function indexMons(mons) {
    state.byDex = new Map();
    mons.forEach(p => {
      p.q = plain([p.name, p.nameEn, p.dex, '#' + p.dex, ...p.types, ...p.types.map(t => TYPE_ES[t])].join(' '));
      state.byDex.set(p.dex, p);
    });
  }

  function initTierList() {
    state.cards = $$('#tierlist .mon');
    $('#q').addEventListener('input', applySearch);
    $('#sort').addEventListener('change', () => {
      sortKey = $('#sort').value;
      sortDesc = SORTS[sortKey].desc;
      syncDir();
      applySort();
    });
    $('#dir').addEventListener('click', () => {
      sortDesc = !sortDesc;
      syncDir();
      applySort();
    });
  }

  // ---------------------------------------------------------------- colección
  class ImportError extends Error {}

  function parseCollection(text) {
    let o;
    try { o = JSON.parse(text.trim()); } catch (e) { throw new ImportError(TEXT.notJson); }
    if (typeof o === 'string') { try { o = JSON.parse(o); } catch (e) { throw new ImportError(TEXT.notCollection); } }
    if (!o || typeof o !== 'object' || !Array.isArray(o.dex) || !Array.isArray(o.shiny)) throw new ImportError(TEXT.missingKeys);
    const ints = a => [...new Set(a.map(Number).filter(n => Number.isInteger(n) && n > 0))];
    return { version: o.version, name: String(o.name || ''), updated: +o.updated || 0, dex: ints(o.dex), shiny: ints(o.shiny) };
  }

  function renderCollection(c) {
    const owned = new Set(c.dex);
    const known = state.mons.filter(p => owned.has(p.dex));
    const unknown = c.dex.length - known.length;
    const total = state.mons.length;
    const rows = TIERS.map(t => {
      const all = state.mons.filter(p => p.r[1] === t);
      return { t, have: all.filter(p => owned.has(p.dex)).length, n: all.length };
    });
    const when = c.updated ? new Date(c.updated).toLocaleString(TEXT.locale, { dateStyle: 'long', timeStyle: 'short' }) : TEXT.noDate;
    const table = '<div class="tablewrap"><table><thead><tr><th>' + TEXT.tierWord + '</th><th class="num">' + TEXT.have + '</th><th>' + TEXT.progress +
      '</th></tr></thead><tbody>' +
      rows.map(r => '<tr><th scope="row"><span class="tier-badge ' + r.t + '">' + r.t + '</span></th><td class="num">' + TEXT.haveOf(r.have, r.n) +
        '</td><td><span class="bar"><i style="width:' + (100 * r.have / r.n).toFixed(1) + '%"></i></span></td></tr>').join('') + '</tbody></table></div>';
    const shinySet = new Set(c.shiny);
    const groups = TIERS.map(t => {
      const mine = state.mons.filter(p => p.r[1] === t && owned.has(p.dex)).sort((a, b) => a.r[0] - b.r[0]);
      if (!mine.length) return '';
      return '<h3><span class="tier-badge ' + t + '">' + t + '</span> ' + TEXT.owned(mine.length) + '</h3><div class="grid">' +
        mine.map(p => card(p, 'owned', shinySet.has(p.dex) ? '<span class="sh" title="' + TEXT.shinyTitle + '">' + TEXT.shiny + '</span>' : '')).join('') + '</div>';
    }).join('');
    const missingTop = state.mons.filter(p => ['S', 'A'].includes(p.r[1]) && !owned.has(p.dex)).sort((a, b) => a.r[0] - b.r[0]);
    const missing = missingTop.length
      ? '<h3>' + TEXT.missingSA(missingTop.length) + '</h3><div class="grid">' + missingTop.map(p => card(p, 'miss')).join('') + '</div>'
      : '<p><strong>' + TEXT.allSA + '</strong></p>';
    $('#result').innerHTML =
      '<h2>' + (c.name ? TEXT.collectionOf(esc(c.name)) : TEXT.yourCollection) + '</h2>' +
      '<div class="stats"><div class="stat"><b>' + known.length + ' / ' + total + '</b><span>' +
      TEXT.dexStat(known.length, total, (100 * known.length / total).toFixed(1)) + '</span></div>' +
      '<div class="stat"><b>' + c.shiny.length + '</b><span>' + TEXT.shinyStat + '</span></div>' +
      '<div class="stat"><b class="stat-small">' + esc(when) + '</b><span>' + TEXT.lastSave + '</span></div></div>' +
      (unknown ? '<p class="muted small">' + TEXT.unknown(unknown) + '</p>' : '') +
      '<h3>' + TEXT.byTier + '</h3>' + table + groups + missing;
  }

  function showError(msg) {
    $('#result').innerHTML = '<div class="err" role="alert">' + esc(msg) + '</div>';
  }

  function initCollection() {
    const run = text => {
      try { renderCollection(parseCollection(text)); } catch (e) {
        if (e instanceof ImportError) showError(e.message); else throw e;
      }
    };
    $('#import').addEventListener('click', () => {
      const t = $('#paste').value;
      if (!t.trim()) { showError(TEXT.pasteFirst); return; }
      run(t);
    });
    $('#file').addEventListener('change', e => {
      const f = e.target.files[0];
      if (!f) return;
      if (f.size > 2e6) { showError(TEXT.tooBig); return; }
      f.text().then(t => { $('#paste').value = t; run(t); });
    });
    $('#copy-snippet').addEventListener('click', () => {
      const text = $('#snippet').textContent;
      const msg = $('#copy-msg');
      const done = ok => { msg.textContent = ok ? TEXT.copied : TEXT.copyFail; };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(() => done(true), () => done(false));
      else done(false);
    });
  }

  // ---------------------------------------------------------------- gráficos
  const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Cada gráfico (.anim) arranca su animación CSS cuando entra en pantalla.
  function initReveal() {
    html.classList.add('js');
    const figs = $$('.anim');
    if (!('IntersectionObserver' in window)) { figs.forEach(f => f.classList.add('in')); return; }
    const io = new IntersectionObserver(entries => entries.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
    }), { threshold: 0.2 });
    figs.forEach(f => io.observe(f));
  }

  // Media geométrica frente a aritmética con pesos por pieza.
  function initDemo() {
    const fig = $('[data-demo]');
    if (!fig) return;
    const sliders = $$('input[type=range]', fig);
    const weights = sliders.map(i => +i.dataset.w);
    const total = weights.reduce((a, b) => a + b, 0);
    const show = (kind, v) => {
      $('[data-out=' + kind + ']', fig).style.width = (v * 100).toFixed(1) + '%';
      const val = $('[data-out-val=' + kind + ']', fig);
      val.style.left = (v * 100).toFixed(1) + '%';
      val.textContent = TEXT.pct(Math.round(v * 100));
    };
    const update = () => {
      const v = sliders.map(i => +i.value / 100);
      sliders.forEach(i => { i.nextElementSibling.textContent = TEXT.pct(i.value); });
      show('geo', Math.exp(v.reduce((a, x, k) => a + weights[k] * Math.log(x), 0) / total));
      show('arith', v.reduce((a, x, k) => a + weights[k] * x, 0) / total);
    };
    sliders.forEach(i => i.addEventListener('input', () => {
      $$('.chip-btn', fig).forEach(b => b.setAttribute('aria-pressed', 'false'));
      update();
    }));
    $$('.chip-btn', fig).forEach(b => b.addEventListener('click', () => {
      b.dataset.v.split(',').forEach((x, k) => { sliders[k].value = x; });
      $$('.chip-btn', fig).forEach(o => o.setAttribute('aria-pressed', String(o === b)));
      update();
    }));
  }

  // Ilustración de las 2.000 repeticiones: cada punto salta dentro de su rango real.
  // Los puntos del recorrido paso a paso no tienen botón y solo saltan mientras se ven.
  function initReps() {
    const REPEATS = 2000;
    const PER_TICK = 40; // repeticiones por tic: 2.000 en unos 2,5 s
    const TICK_MS = 50;
    $$('[data-reps]').forEach(fig => {
      const dots = $$('.rp-dot', fig);
      const btn = $('[data-play]', fig);
      const count = $('[data-count]', fig);
      let n = 1;
      let timer = null;
      const step = () => {
        if (!fig.offsetParent) return;
        n = (n - 1 + PER_TICK) % REPEATS + 1;
        if (count) count.textContent = TEXT.repCount(n, REPEATS);
        dots.forEach(d => {
          const lo = +d.dataset.lo;
          const hi = +d.dataset.hi;
          d.style.left = ((lo + Math.random() * (hi - lo) - 1) / 965 * 100).toFixed(2) + '%';
        });
      };
      const set = on => {
        clearInterval(timer);
        timer = on ? setInterval(step, TICK_MS) : null;
        if (btn) btn.textContent = on ? TEXT.pause : TEXT.play;
      };
      if (btn) btn.addEventListener('click', () => set(!timer));
      set(!REDUCED);
    });
  }

  // Recorrido de un Pokémon en cinco pasos, con chips para cambiar de Pokémon.
  function initWalk() {
    const fig = $('[data-walk]');
    if (!fig) return;
    const STEPS = $$('[data-step]', $('[data-mon-panel]', fig)).length;
    const panels = $$('[data-mon-panel]', fig);
    const chips = $$('[data-mon]', fig);
    const dots = $$('[data-go]', fig);
    const prev = $('[data-prev]', fig);
    const next = $('[data-next]', fig);
    const auto = $('[data-auto]', fig);
    const pos = $('.walk-pos', fig);
    let mon = 0;
    let step = 0;
    let timer = null;
    fig.classList.add('stepper');
    const render = () => {
      panels.forEach((p, i) => { p.hidden = i !== mon; });
      $$('[data-step]', panels[mon]).forEach(s => { s.hidden = +s.dataset.step !== step; });
      chips.forEach((c, i) => c.setAttribute('aria-pressed', String(i === mon)));
      dots.forEach((d, k) => {
        d.setAttribute('aria-current', k === step ? 'step' : 'false');
        d.classList.toggle('past', k < step);
      });
      pos.textContent = TEXT.stepOf(step + 1, STEPS);
      prev.disabled = step === 0;
      next.disabled = step === STEPS - 1;
    };
    const stop = () => { clearInterval(timer); timer = null; auto.textContent = TEXT.auto; };
    const go = k => { step = Math.max(0, Math.min(STEPS - 1, k)); render(); };
    prev.addEventListener('click', () => { stop(); go(step - 1); });
    next.addEventListener('click', () => { stop(); go(step + 1); });
    dots.forEach((d, k) => d.addEventListener('click', () => { stop(); go(k); }));
    chips.forEach((c, i) => c.addEventListener('click', () => { mon = i; go(0); }));
    auto.addEventListener('click', () => {
      if (timer) { stop(); return; }
      auto.textContent = TEXT.stop;
      if (step === STEPS - 1) go(0);
      timer = setInterval(() => {
        if (step === STEPS - 1) { stop(); return; }
        go(step + 1);
      }, 3500);
    });
    stop();
    render();
  }

  // Ilustración de una partida simulada. No son datos del ranking: solo muestra qué se mide.
  function initArena() {
    const fig = $('[data-arena]');
    if (!fig) return;
    const cv = $('canvas', fig);
    const ctx = cv.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    const W = cv.width;
    const H = cv.height;
    const tEl = $('[data-t]', fig);
    const kEl = $('[data-k]', fig);
    const btn = $('[data-play]', fig);
    const sprite = new Image();
    sprite.addEventListener('error', () => { if (spritesAlt && sprite.src.startsWith(sprites)) sprite.src = spritesAlt + sprite.src.slice(sprites.length); });
    sprite.src = cv.dataset.sprite;
    const WALLS = [[58, 40, 8, 52], [206, 112, 52, 8], [146, 24, 44, 8]];
    const WATER = [[232, 28, 64, 38], [40, 130, 48, 30]];
    const SOLID = WALLS.concat(WATER);
    let color = {};
    let hero, enemies, shots, t, kills, spawn, shoot, over;
    let running = false;
    let visible = false;
    let last = 0;

    const readColors = () => {
      const cs = getComputedStyle(html);
      const v = n => cs.getPropertyValue(n).trim();
      color = { bg: v('--arena-bg'), wall: v('--arena-wall'), water: v('--arena-water'), enemy: v('--arena-enemy'),
        shot: v('--arena-shot'), hp: v('--arena-hp'), ink: v('--arena-ink') };
    };
    const reset = () => {
      hero = { x: W / 2, y: H / 2, hp: 100 };
      enemies = []; shots = []; t = 0; kills = 0; spawn = 0; shoot = 0; over = 0;
    };
    const blocked = (x, y, r) => SOLID.some(([a, b, w, h]) => x + r > a && x - r < a + w && y + r > b && y - r < b + h);
    const move = (o, dx, dy, r) => {
      if (!blocked(o.x + dx, o.y, r)) o.x += dx;
      if (!blocked(o.x, o.y + dy, r)) o.y += dy;
      o.x = Math.max(r, Math.min(W - r, o.x));
      o.y = Math.max(r, Math.min(H - r, o.y));
    };

    const update = dt => {
      if (over > 0) { over -= dt; if (over <= 0) reset(); return; }
      t += dt;
      spawn += dt * Math.min(5, 1.2 + t * 0.04);
      while (spawn >= 1 && enemies.length < 60) {
        spawn -= 1;
        const edge = Math.floor(Math.random() * 4);
        const x = edge === 0 ? 0 : edge === 1 ? W : Math.random() * W;
        const y = edge === 2 ? 0 : edge === 3 ? H : Math.random() * H;
        enemies.push({ x, y, hp: t > 25 ? 2 : 1, v: 20 + Math.random() * 12 + Math.min(10, t * 0.15) });
      }
      spawn = Math.min(spawn, 1);
      let vx = (W / 2 - hero.x) / W * 0.8 + Math.cos(t * 0.7) * 0.3;
      let vy = (H / 2 - hero.y) / H * 0.8 + Math.sin(t * 0.9) * 0.3;
      let near = null;
      let nearD = 1e9;
      enemies.forEach(e => {
        const dx = hero.x - e.x;
        const dy = hero.y - e.y;
        const d = Math.hypot(dx, dy) || 1;
        if (d < 80) { const w = (80 - d) / 80 * 2; vx += dx / d * w; vy += dy / d * w; }
        if (d < nearD) { nearD = d; near = e; }
      });
      const n = Math.hypot(vx, vy);
      if (n > 0.05) move(hero, vx / n * 58 * dt, vy / n * 58 * dt, 6);
      shoot += dt;
      if (shoot >= 0.45 && near && nearD < 140) {
        shoot = 0;
        const d = nearD || 1;
        shots.push({ x: hero.x, y: hero.y, vx: (near.x - hero.x) / d * 150, vy: (near.y - hero.y) / d * 150, life: 1.2 });
      }
      shots.forEach(s => {
        s.x += s.vx * dt; s.y += s.vy * dt; s.life -= dt;
        if (blocked(s.x, s.y, 1)) s.life = 0;
        enemies.forEach(e => {
          if (s.life > 0 && Math.hypot(e.x - s.x, e.y - s.y) < 6) { s.life = 0; e.hp -= 1; if (e.hp <= 0) kills += 1; }
        });
      });
      shots = shots.filter(s => s.life > 0);
      enemies = enemies.filter(e => e.hp > 0);
      enemies.forEach(e => {
        const dx = hero.x - e.x;
        const dy = hero.y - e.y;
        const d = Math.hypot(dx, dy) || 1;
        move(e, dx / d * e.v * dt, dy / d * e.v * dt, 4);
        if (d < 9) hero.hp -= 14 * dt;
      });
      if (hero.hp <= 0) over = 1.2;
    };

    const draw = () => {
      ctx.fillStyle = color.bg; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = color.water; WATER.forEach(r => ctx.fillRect(...r));
      ctx.fillStyle = color.wall; WALLS.forEach(r => ctx.fillRect(...r));
      enemies.forEach(e => {
        const x = Math.round(e.x) - 4;
        const y = Math.round(e.y) - 4;
        ctx.fillStyle = color.enemy; ctx.fillRect(x, y + 1, 8, 6); ctx.fillRect(x + 1, y, 6, 8);
        ctx.fillStyle = color.ink; ctx.fillRect(x + 2, y + 3, 1, 2); ctx.fillRect(x + 5, y + 3, 1, 2);
      });
      ctx.fillStyle = color.shot; shots.forEach(s => ctx.fillRect(Math.round(s.x) - 1, Math.round(s.y) - 1, 3, 3));
      if (sprite.complete && sprite.naturalWidth) {
        const k = Math.max(sprite.naturalWidth, sprite.naturalHeight) > 28 ? 0.5 : 1;
        const w = Math.round(sprite.naturalWidth * k);
        const h = Math.round(sprite.naturalHeight * k);
        ctx.drawImage(sprite, Math.round(hero.x - w / 2), Math.round(hero.y - h / 2), w, h);
      } else {
        ctx.fillStyle = color.shot; ctx.fillRect(Math.round(hero.x) - 5, Math.round(hero.y) - 5, 10, 10);
      }
      ctx.fillStyle = color.ink; ctx.fillRect(6, 6, 52, 6);
      ctx.fillStyle = color.hp; ctx.fillRect(7, 7, Math.max(0, Math.round(hero.hp / 100 * 50)), 4);
      if (over > 0) {
        ctx.fillStyle = color.ink; ctx.font = '14px "Pixelify Sans", monospace'; ctx.textAlign = 'center';
        ctx.fillText(TEXT.over, W / 2, H / 2);
      }
      tEl.textContent = Math.floor(t);
      kEl.textContent = kills;
    };

    let raf = 0;
    const kick = () => { if (!raf) raf = requestAnimationFrame(frame); };
    function frame(now) {
      raf = 0;
      if (!running || !visible || document.hidden) { last = 0; return; }
      update(Math.min(0.05, last ? (now - last) / 1000 : 0.016));
      last = now;
      draw();
      kick();
    }
    const set = on => {
      running = on;
      btn.textContent = on ? TEXT.pause : TEXT.play;
      if (on) kick();
    };

    readColors();
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { readColors(); draw(); });
    reset();
    if (REDUCED) { for (let i = 0; i < 80; i++) update(0.05); draw(); } else draw();
    btn.addEventListener('click', () => set(!running));
    sprite.addEventListener('load', draw);
    new IntersectionObserver(es => { visible = es[0].isIntersecting; kick(); }, { threshold: 0.1 }).observe(cv);
    document.addEventListener('visibilitychange', kick);
    set(!REDUCED);
  }

  // ---------------------------------------------------------------- arranque
  // Si el CDN de sprites falla, cada imagen prueba una vez el mismo archivo en la copia de respaldo.
  if (spritesAlt && sprites) {
    const retry = img => {
      if (!img.dataset.alt && img.src.startsWith(sprites)) { img.dataset.alt = '1'; img.src = spritesAlt + img.src.slice(sprites.length); }
    };
    document.addEventListener('error', e => { if (e.target.tagName === 'IMG') retry(e.target); }, true);
    $$('img').forEach(i => { if (i.complete && !i.naturalWidth) retry(i); });
  }
  // Los enlaces antiguos /pokemon/25.html caen en la página 404, que los reenvía a la ficha única.
  if (page === '404') {
    const old = location.pathname.match(/^(\/en)?\/pokemon\/(\d+)(?:\.html)?\/?$/);
    if (old) { location.replace((old[1] || '') + '/pokemon/?id=' + old[2]); return; }
  }
  initReveal();
  initDemo();
  initReps();
  initWalk();
  initArena();
  if (page === 'index' || page === 'coleccion') {
    getJSON('pokemon-index.json').then(mons => {
      state.mons = mons; indexMons(mons);
      if (page === 'index') initTierList(); else initCollection();
    }).catch(err => {
      const el = $('#result') || $('#count');
      if (el) el.textContent = TEXT.loadFailAll(err.message);
    });
  }
})();
