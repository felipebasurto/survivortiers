/* SurvivorTiers · herramientas: buscador por tipos (page data-page="buscador") y planificador de build
   (data-page="planificador"). Los datos vienen de data/game-stats.json (build/gamestats.py), data/pokemon-index.json y
   data/species.json; los textos, de #i18n (build/toolpages.py). La parte pura (tabla de tipos, cobertura, avisos de
   potenciadores, enlaces) se exporta a Node para test_tools.js; el DOM solo se toca en las dos páginas.
   Reglas del juego: js/data/types.js (SOFT, MIN, MAX), js/systems/levelup.js:46-56 (tope de dos potenciadores),
   js/entities/player.js:42-50 y 99-102 (físico con patk, especial con satk), js/game.js:140-145 (Repertorio) y
   js/data/moves.js:620-630 (lista de movimientos físicos). */
(() => {
  'use strict';

  const SUPER = 1.05;
  const NEUTRAL = 0.95;
  const MIN_MULT = 0.3;
  const MAX_MULT = 2.4;
  const BOOST_CAP = 2;
  const PLAN_SLOTS = 4;
  const LETTERS = 'abcdefghijklmnopqrstuvwxyz';

  // Python redondea a par cuando está justo en medio (round); igual que rnd de ficha.js.
  const rnd = x => {
    const f = Math.floor(x);
    const d = x - f;
    return d < 0.5 ? f : d > 0.5 ? f + 1 : (f % 2 ? f + 1 : f);
  };

  const slugOf = name => String(name).replace(/♀/g, '-f').replace(/♂/g, '-m').normalize('NFKD')
    .replace(/\p{M}/gu, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

  // Producto de los multiplicadores de cada tipo defensor, acotado como G.Types.mult.
  function comboMult(chart, atk, defs) {
    let m = 1;
    for (const d of defs) m *= chart[atk][d];
    return clamp(m, MIN_MULT, MAX_MULT);
  }

  function weaknessMap(chart, defs) {
    const out = {};
    for (const atk of Object.keys(chart)) out[atk] = comboMult(chart, atk, defs);
    return out;
  }

  // Agrupa los multiplicadores de un Pokémon: doble debilidad (×2,4), débil (×1,6 y más), resiste (menos de ×1) e inmune.
  function groupWeak(map) {
    const g = { double: [], weak: [], res: [], imm: [] };
    for (const [atk, m] of Object.entries(map)) {
      if (m >= MAX_MULT - 1e-9) g.double.push([atk, m]);
      else if (m > 1 + 1e-9) g.weak.push([atk, m]);
      else if (m <= MIN_MULT + 1e-9) g.imm.push([atk, m]);
      else if (m < 1 - 1e-9) g.res.push([atk, m]);
    }
    return g;
  }

  function sideOf(pa, sa) {
    return sa > pa ? 'special' : 'physical';
  }

  function poolOf(types, pool) {
    const ids = new Set(pool.normal);
    for (const t of types) for (const id of (pool[t] || [])) ids.add(id);
    return ids;
  }

  // Cobertura sobre todos los Pokémon, con la regla de build/combos.py (SUPER y NEUTRAL de ahí).
  function coverage(defenders, attackTypes, chart) {
    if (!attackTypes.length) return { super: 0, neutral: 0 };
    let superHits = 0;
    let neutralHits = 0;
    for (const defs of defenders) {
      let best = 0;
      for (const atk of attackTypes) best = Math.max(best, comboMult(chart, atk, defs));
      if (best > SUPER) superHits += 1;
      if (best >= NEUTRAL) neutralHits += 1;
    }
    const n = defenders.length;
    return { super: rnd(100 * superHits / n), neutral: rnd(100 * neutralHits / n) };
  }

  const isBuff = (moves, id) => moves[id] && moves[id].b != null;
  const isAttack = (moves, id) => moves[id] && moves[id].c != null;
  const boostsOf = (moves, group) => group.filter(id => id && isBuff(moves, id));
  const attacksOf = (moves, group) => group.filter(id => id && isAttack(moves, id));

  function attackTypesOf(moves, group) {
    return [...new Set(attacksOf(moves, group).map(id => moves[id].t))];
  }

  // Avisos de los potenciadores de ataque (patk = físico, satk = especial): no suman entre sí en la misma casilla
  // y un potenciador que no coincide con ningún ataque del grupo no sube nada.
  function boostWarnings(moves, group) {
    const out = [];
    const boosts = boostsOf(moves, group);
    const dances = boosts.filter(id => moves[id].b.stat === 'patk');
    if (dances.length >= 2) out.push({ k: 'both' });
    const attacks = attacksOf(moves, group);
    for (const id of boosts) {
      const stat = moves[id].b.stat;
      if (stat !== 'patk' && stat !== 'satk') continue;
      if (!attacks.length) continue;
      const cat = stat === 'patk' ? 'physical' : 'special';
      const n = attacks.filter(a => moves[a].c === cat).length;
      if (n === 0) out.push({ k: 'none', boost: id, cat });
      else if (n < attacks.length) out.push({ k: 'some', boost: id, cat, n, total: attacks.length });
    }
    return out;
  }

  // Cuatro cartas del planificador: las primeras de la lista por prioridad (d[10][0]), y la que evoluciona el ataque
  // principal (d[10][1]) siempre dentro, en su sitio de la lista.
  function plannerCards(prio) {
    const [order, gate] = prio;
    const top = order.slice(0, PLAN_SLOTS);
    const picks = gate && !top.includes(gate) ? order.slice(0, PLAN_SLOTS - 1).concat(gate) : top;
    return order.filter(id => picks.includes(id));
  }

  // Build recomendada de build/combos.py. El potenciador sigue al ataque que abre el grupo (los ids salen de
  // data/owner_rules.json, el mismo archivo que lee el publicador): especial → Maquinación, físico → Danza Espada. Un grupo mixto no vota por mayoría.
  function leadSide(attacks, game, dex) {
    for (const id of attacks) {
      const cat = game.moves[id] && game.moves[id].c;
      if (cat === 'physical' || cat === 'special') return cat;
    }
    const [pa, sa] = game.dex[String(dex)];
    return sideOf(pa, sa);
  }

  function recommended(dex, species, game, rules) {
    const d = species.d[String(dex)];
    const ids = d[9][2];
    const nBoost = d[9][5];
    const attacks = ids.slice(0, ids.length - nBoost);
    const boosts = ids.slice(ids.length - nBoost);
    const lead = leadSide(attacks, game, dex);
    let swap = null;
    const fixed = boosts.map(id => {
      const stat = game.moves[id].b && game.moves[id].b.stat;
      if (stat === 'patk' && lead === 'special') {
        swap = { from: id, to: rules.special_buff };
        return rules.special_buff;
      }
      if (stat === 'satk' && lead === 'physical') {
        swap = { from: id, to: rules.physical_buff };
        return rules.physical_buff;
      }
      return id;
    });
    const group = [...attacks, ...fixed].slice(0, PLAN_SLOTS);
    return {
      group: group.concat(Array(PLAN_SLOTS - group.length).fill(null)),
      item: species.items[0] ? species.items[0].id : null,
      cards: plannerCards(d[10]).concat(Array(PLAN_SLOTS).fill(null)).slice(0, PLAN_SLOTS),
      swap,
    };
  }

  const PARAM = { dex: 'p', group: 'g', item: 'o', cards: 'c' };

  function encodeState(st) {
    const q = new URLSearchParams();
    q.set(PARAM.dex, String(st.dex));
    q.set(PARAM.group, st.group.map(x => x || '-').join(','));
    q.set(PARAM.item, st.item || '-');
    q.set(PARAM.cards, st.cards.map(x => x || '-').join(','));
    return q.toString();
  }

  // Lee el estado de la URL y descarta lo que no existe o no cabe (un enlace editado a mano no rompe la página).
  function decodeState(search, game, species, index, fallbackDex) {
    const q = new URLSearchParams(search);
    const dex = Number(q.get(PARAM.dex));
    const known = index.some(p => p.dex === dex);
    const start = known ? dex : fallbackDex;
    const mon = index.find(p => p.dex === start);
    const pool = poolOf(mon.types, game.pool);
    // The published build can include this species' own start move, which is not always in the type pool.
    const built = (species.d[String(start)] && species.d[String(start)][9][2]) || [];
    for (const id of built) pool.add(id);
    const seen = new Set();
    const group = (q.get(PARAM.group) || '').split(',').slice(0, PLAN_SLOTS).map(id => {
      if (!id || id === '-' || seen.has(id) || !pool.has(id) || !game.moves[id]) return null;
      seen.add(id);
      return id;
    });
    let boosts = 0;
    for (let i = 0; i < group.length; i += 1) {
      if (group[i] && isBuff(game.moves, group[i])) {
        boosts += 1;
        if (boosts > BOOST_CAP) group[i] = null;
      }
    }
    const itemId = q.get(PARAM.item);
    const itemOk = itemId && itemId !== '-' && species.items.some(i => i.id === itemId);
    const cardIds = Object.keys(species.cards);
    const cards = (q.get(PARAM.cards) || '').split(',').slice(0, PLAN_SLOTS).map(id => (id && id !== '-' && cardIds.includes(id) ? id : null));
    const fill = (arr) => arr.concat(Array(PLAN_SLOTS).fill(null)).slice(0, PLAN_SLOTS);
    return { dex: start, group: fill(group), item: itemOk ? itemId : null, cards: fill(cards), fromUrl: known };
  }

  const toolsApi = {
    slugOf, comboMult, weaknessMap, groupWeak, sideOf, poolOf, coverage, boostWarnings, recommended, plannerCards,
    encodeState, decodeState, attackTypesOf, boostsOf, attacksOf, rnd, SUPER, NEUTRAL, PLAN_SLOTS, BOOST_CAP,
  };

  const html = typeof document !== 'undefined' ? document.documentElement : null;
  if (!html) {
    if (typeof module !== 'undefined' && module.exports) module.exports = toolsApi;
    return;
  }
  const page = html.dataset.page;
  if (page !== 'buscador' && page !== 'planificador') return;

  const home = html.dataset.home || '';
  const sprites = html.dataset.sprites || '';
  const spriteExt = html.dataset.spritesExt || '.png';
  const assets = html.dataset.assets || '';
  const T = JSON.parse(document.getElementById('i18n').textContent);
  const EN = T.en;
  const S = T.s;
  const TY = T.types;

  const t = (k, v) => String(S[k]).replace(/\{(\w+)\}/g, (m, n) => (v && n in v ? v[n] : m));
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = (v, d) => (EN ? v.toFixed(d) : v.toFixed(d).replace('.', ','));
  const pillOf = ty => '<span class="type" style="--tc:' + TY[ty].c + ';--tg:' + TY[ty].tc + '">' + TY[ty].g +
    '<span>' + esc(TY[ty].n) + '</span></span>';
  const tagOf = (ty, extra) => '<span class="tt' + (extra || '') + '" style="--tc:' + TY[ty].c + ';--tg:' + TY[ty].tc + '">' +
    esc(TY[ty].n) + '</span>';
  const monPath = p => home + 'pokemon/' + p.dex + '-' + slugOf(p.nameEn) + '/';
  const monName = p => (EN ? p.nameEn : p.name);
  const spriteImg = (p, scale, cls) => '<img class="' + (cls || 'px') + '" src="' + sprites + p.dex + spriteExt +
    '" width="' + p.w * scale + '" height="' + p.h * scale + '" alt="" loading="lazy" decoding="async">';
  const iconSvg = (ic, cls) => {
    const [w, h] = ic.size;
    let rects = '';
    ic.rows.forEach((row, y) => {
      let x = 0;
      while (x < w) {
        const ch = row[x];
        let n = 1;
        while (x + n < w && row[x + n] === ch) n += 1;
        if (ch !== '.') rects += '<rect x="' + x + '" y="' + y + '" width="' + n + '" height="1" fill="' + ic.pal[LETTERS.indexOf(ch)] + '"/>';
        x += n;
      }
    });
    return '<svg class="' + cls + '" viewBox="0 0 ' + w + ' ' + h + '" width="' + w * 3 + '" height="' + h * 3 +
      '" aria-hidden="true" focusable="false" shape-rendering="crispEdges">' + rects + '</svg>';
  };
  const getJSON = name => fetch(assets + 'data/' + name).then(r => {
    if (!r.ok) throw new Error(t('tool_fail'));
    return r.json();
  });
  const moveName = (game, id) => (EN ? game.moves[id].n[1] : game.moves[id].n[0]);
  const catLabel = (game, id) => {
    if (isBuff(game.moves, id)) return t('bp_cat_boost');
    return game.moves[id].c === 'physical' ? t('bp_cat_phys') : t('bp_cat_spec');
  };

  function finder(game, index) {
    const names = Object.keys(game.chart);
    const root = document.getElementById('tf-app');
    const chips = [...root.querySelectorAll('.tf-chip')];
    const weakBox = document.getElementById('tf-weak');
    const list = document.getElementById('tf-list');
    const count = document.getElementById('tf-count');
    const empty = document.getElementById('tf-empty');
    const clear = document.getElementById('tf-clear');
    const status = document.getElementById('tf-status');
    const selected = [];

    const readParam = () => {
      const q = new URLSearchParams(location.search).get('t');
      return q ? q.split(',').filter(x => names.includes(x)).slice(0, 2) : [];
    };
    const writeParam = () => {
      const u = new URL(location.href);
      if (selected.length) u.searchParams.set('t', selected.join(','));
      else u.searchParams.delete('t');
      history.replaceState(null, '', u.pathname + (u.search || '') + u.hash);
    };

    function weakHtml(groups) {
      const row = (title, items, cls) => items.length
        ? '<div class="tf-wgroup ' + cls + '"><h3>' + esc(title) + '</h3><ul>' +
          items.map(([a, m]) => '<li>' + tagOf(a) + '<span class="tf-mult">×' + num(m, 2) + '</span></li>').join('') + '</ul></div>'
        : '';
      const body = row(t('tf_g_x24'), groups.double, 'is-double') + row(t('tf_g_weak'), groups.weak, 'is-weak') +
        row(t('tf_g_res'), groups.res, 'is-res') + row(t('tf_g_imm'), groups.imm, 'is-imm');
      return body || '<p class="muted">' + esc(t('tf_none')) + '</p>';
    }

    function render() {
      chips.forEach(c => {
        const on = selected.includes(c.dataset.t);
        c.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      clear.hidden = selected.length === 0;
      if (!selected.length) {
        weakBox.innerHTML = '<p class="muted">' + esc(t('tf_start')) + '</p>';
        list.innerHTML = '';
        count.textContent = '';
        empty.hidden = true;
        return;
      }
      weakBox.innerHTML = weakHtml(groupWeak(weaknessMap(game.chart, selected)));
      const hits = index.filter(p => (selected.length === 1
        ? p.types.includes(selected[0])
        : p.types.length === 2 && selected.every(s => p.types.includes(s))))
        .sort((a, b) => a.r[0] - b.r[0]);
      count.textContent = t('tf_count', { n: hits.length });
      empty.hidden = hits.length > 0;
      list.innerHTML = hits.map(p => {
        const map = weaknessMap(game.chart, p.types);
        const g = groupWeak(map);
        const weak = [...g.double.map(x => [x, true]), ...g.weak.map(x => [x, false])];
        const [pa, sa] = game.dex[String(p.dex)];
        const doubles = g.double.map(([a]) => TY[a].n).join(', ');
        return '<li class="tf-card"><a href="' + monPath(p) + '">' +
          '<span class="tf-sp">' + spriteImg(p, 2) + '</span>' +
          '<span class="tf-nm">' + esc(monName(p)) + '<small>#' + p.dex + '</small></span>' +
          '<span class="tf-types">' + p.types.map(pillOf).join('') + '</span>' +
          '<span class="tf-rank">' + esc(p.r[0]) + '</span>' +
          '<span class="tf-atk"><span class="tf-pa">' + esc(t('tf_card_pa', { v: num(pa, 2) })) + '</span>' +
          '<span class="tf-sa">' + esc(t('tf_card_sa', { v: num(sa, 2) })) + '</span></span>' +
          '<span class="tf-weak">' + weak.map(([[a, m], dbl]) => '<span class="tf-w' + (dbl ? ' is-double' : '') + '">' +
            esc(TY[a].n) + ' ×' + num(m, 2) + '</span>').join('') + '</span>' +
          (doubles ? '<span class="sr">' + esc(t('tf_card_double', { types: doubles })) + '</span>' : '') +
          '</a></li>';
      }).join('');
    }

    chips.forEach(chip => chip.addEventListener('click', () => {
      const ty = chip.dataset.t;
      const i = selected.indexOf(ty);
      if (i >= 0) selected.splice(i, 1);
      else {
        if (selected.length === 2) selected.shift();
        selected.push(ty);
      }
      writeParam();
      render();
    }));
    clear.addEventListener('click', () => {
      selected.length = 0;
      writeParam();
      render();
    });

    selected.push(...readParam());
    render();
    status.textContent = '';
  }

  function planner(game, species, index, rules) {
    const root = document.getElementById('bp-app');
    const input = document.getElementById('bp-q');
    const datalist = document.getElementById('bp-list');
    const monBox = document.getElementById('bp-mon');
    const slotsBox = document.getElementById('bp-slots');
    const itemSel = document.getElementById('bp-item');
    const cardsBox = document.getElementById('bp-cards');
    const warnBox = document.getElementById('bp-warn');
    const result = document.getElementById('bp-result');
    const byDex = new Map(index.map(p => [p.dex, p]));
    const sorted = [...index].sort((a, b) => a.r[0] - b.r[0]);
    const firstDex = sorted[0].dex;
    const parsed = decodeState(location.search, game, species, index, firstDex);
    let st = parsed.fromUrl && new URLSearchParams(location.search).has(PARAM.group) ? parsed : recommendedState(parsed.dex);

    datalist.innerHTML = index.slice().sort((a, b) => a.dex - b.dex)
      .map(p => '<option value="' + esc(monName(p)) + ' (#' + p.dex + ')"></option>').join('');

    function resolve(text) {
      const v = String(text).trim();
      const m = v.match(/#(\d+)\)?$/) || v.match(/^#?(\d+)$/);
      if (m) return byDex.has(Number(m[1])) ? Number(m[1]) : null;
      const low = v.toLowerCase();
      const hit = index.find(p => p.name.toLowerCase() === low || p.nameEn.toLowerCase() === low);
      return hit ? hit.dex : null;
    }

    function writeUrl() {
      const u = new URL(location.href);
      u.search = '?' + encodeState(st);
      history.replaceState(null, '', u.pathname + u.search);
    }

    function poolIds() {
      return poolOf(byDex.get(st.dex).types, game.pool);
    }

    function boostCount(exclude) {
      return st.group.filter((id, i) => i !== exclude && id && isBuff(game.moves, id)).length;
    }

    function optionsFor(slot) {
      const pool = poolIds();
      const used = new Set(st.group.filter((id, i) => i !== slot && id));
      const groups = { phys: [], spec: [], boost: [] };
      for (const id of pool) {
        const m = game.moves[id];
        const k = isBuff(game.moves, id) ? 'boost' : m.c === 'physical' ? 'phys' : 'spec';
        const disabled = used.has(id) || (k === 'boost' && boostCount(slot) >= BOOST_CAP);
        groups[k].push({ id, disabled });
      }
      const opt = o => '<option value="' + o.id + '"' + (o.disabled ? ' disabled' : '') +
        (st.group[slot] === o.id ? ' selected' : '') + '>' + esc(moveName(game, o.id)) + '</option>';
      const grp = (label, arr) => arr.length
        ? '<optgroup label="' + esc(label) + '">' + arr.sort((a, b) => moveName(game, a.id).localeCompare(moveName(game, b.id), EN ? 'en' : 'es')).map(opt).join('') + '</optgroup>' : '';
      return '<option value="">' + esc(t('bp_pick_move')) + '</option>' +
        grp(t('bp_cat_phys'), groups.phys) + grp(t('bp_cat_spec'), groups.spec) + grp(t('bp_cat_boost'), groups.boost);
    }

    function renderSlots() {
      slotsBox.innerHTML = st.group.map((id, i) => {
        const tag = id ? (isBuff(game.moves, id) ? t('bp_cat_boost') : (game.moves[id].c === 'physical' ? t('bp_cat_phys') : t('bp_cat_spec'))) : '';
        const cls = id && isBuff(game.moves, id) ? ' is-boost' : '';
        return '<div class="bp-slot' + cls + '"><label><span class="bp-slot-n">' + esc(t('bp_slot', { n: i + 1 })) + '</span>' +
          '<select class="bp-select" data-slot="' + i + '">' + optionsFor(i) + '</select></label>' +
          '<span class="bp-cat" data-cat="' + i + '">' + esc(tag) + '</span></div>';
      }).join('');
    }

    function refreshSlots() {
      [...slotsBox.querySelectorAll('select')].forEach((sel, i) => {
        sel.innerHTML = optionsFor(i);
      });
      [...slotsBox.querySelectorAll('.bp-cat')].forEach((el, i) => {
        const id = st.group[i];
        el.textContent = id ? catLabel(game, id) : '';
      });
      [...slotsBox.querySelectorAll('.bp-slot')].forEach((el, i) => {
        el.classList.toggle('is-boost', !!st.group[i] && isBuff(game.moves, st.group[i]));
      });
    }

    function renderItems() {
      const items = species.items;
      itemSel.innerHTML = '<option value="">' + esc(t('bp_item_none')) + '</option>' + items.map((it, i) =>
        '<option value="' + it.id + '"' + (st.item === it.id ? ' selected' : '') + '>' +
        esc(EN ? it.en.name : it.name) + (i === 0 ? ' · ' + esc(t('bp_item_best')) : '') + '</option>').join('');
    }

    function renderCards() {
      const cardList = Object.values(species.cards);
      const [order, gate] = species.d[String(st.dex)][10];
      const cardName = id => EN ? species.cards[id].en.name : species.cards[id].name;
      cardsBox.innerHTML = st.cards.map((id, i) =>
        '<label class="bp-card"><span class="bp-slot-n">' + esc(t('bp_card_n', { n: i + 1 })) + '</span>' +
        '<select class="bp-select" data-card="' + i + '"><option value="">' + esc(t('bp_card_none')) + '</option>' +
        cardList.map(c => '<option value="' + c.id.replace('card:', '') + '"' +
          (id === c.id.replace('card:', '') ? ' selected' : '') + '>' + esc(EN ? c.en.name : c.name) + '</option>').join('') +
        '</select></label>').join('') +
        '<p class="tool-rule bp-cardorder">' + esc(t('bp_cards_all')) + ': ' +
        order.map((id, i) => (i + 1) + '. ' + esc(cardName(id)) + (id === gate ? ' 1×' : '')).join(' · ') + '</p>' +
        '<p class="tool-rule">' + esc(t('build_card_hint')) + (gate ? ' ' + esc(t('build_card_once')) : '') + '</p>';
    }

    function renderMon() {
      const p = byDex.get(st.dex);
      const [pa, sa] = game.dex[String(p.dex)];
      const side = sideOf(pa, sa);
      const stats = '<span class="bp-mon-atk">' + esc(t('tf_card_pa', { v: num(pa, 2) })) + '<span aria-hidden="true"> · </span>' +
        esc(t('tf_card_sa', { v: num(sa, 2) })) + '</span>';
      monBox.innerHTML = '<a class="bp-mon-link" href="' + monPath(p) + '"><span class="bp-sprite" style="--tc:' + TY[p.types[0]].c + '">' +
        spriteImg(p, 2) + '</span><span class="bp-mon-txt"><strong>' + esc(monName(p)) + '</strong><small>#' + p.dex + '</small>' +
        '<span class="bp-mon-types">' + p.types.map(pillOf).join('') + '</span>' +
        '<span class="bp-mon-rank">' + esc(t('bp_rank', { rank: p.r[0], total: index.length, tier: p.r[1] })) + '</span>' +
        '<span class="bp-mon-side">' + esc(t('bp_side', { side: side === 'special' ? t('bp_cat_spec_adj') : t('bp_cat_phys_adj') })) + '</span>' +
        stats +
        '</span></a>';
      input.value = monName(p) + ' (#' + p.dex + ')';
    }

    function renderWarnings() {
      const ws = boostWarnings(game.moves, st.group);
      const msgs = ws.map(w => {
        if (w.k === 'both') return ['bad', t('bp_both')];
        if (w.k === 'none') return ['bad', t('bp_mismatch_none', { boost: moveName(game, w.boost), cat: t(w.cat === 'physical' ? 'bp_cat_phys_adj' : 'bp_cat_spec_adj') })];
        return ['note', t('bp_mismatch_some', { boost: moveName(game, w.boost), n: w.n, total: w.total })];
      });
      const rec = recommended(st.dex, species, game, rules);
      if (rec.swap && st.group.includes(rec.swap.to)) msgs.push(['note', t('bp_swapped', { from: moveName(game, rec.swap.from), to: moveName(game, rec.swap.to) })]);
      warnBox.innerHTML = msgs.map(([cls, text]) => '<p class="bp-warn is-' + cls + '">' + esc(text) + '</p>').join('');
      const n = boostCount(-1);
      document.getElementById('bp-boostcount').textContent = t('bp_boost_count', { n }) + (n >= BOOST_CAP ? ' · ' + t('bp_boost_max') : '');
    }

    function renderResult() {
      const p = byDex.get(st.dex);
      const attacks = attacksOf(game.moves, st.group);
      const boosts = boostsOf(game.moves, st.group);
      const cov = coverage(index.map(q => q.types), attackTypesOf(game.moves, st.group), game.chart);
      const chipOf = id => '<li class="bp-chip' + (isBuff(game.moves, id) ? ' is-boost' : '') + '">' +
        '<span class="bp-chip-ico">' + (game.moves[id].i ? iconSvg(game.moves[id].i, 'tl-ico') : '') + '</span>' +
        '<span class="bp-chip-txt">' + esc(moveName(game, id)) + '<small>' + esc(catLabel(game, id)) + '</small></span></li>';
      const itemObj = species.items.find(i => i.id === st.item);
      const cards = st.cards.filter(Boolean).map(id => species.cards[id]).filter(Boolean);
      const link = location.href;
      const coverLine = attacks.length
        ? t('bp_cover', { super: cov.super + '%', neutral: cov.neutral + '%' })
        : t('bp_none_attack');
      result.innerHTML = '<h2>' + esc(t('bp_result_h')) + '</h2>' +
        '<p class="bp-result-who">' + esc(monName(p)) + ' <small>#' + p.dex + '</small></p>' +
        '<p class="bp-sub">' + esc(t('bp_group_h')) + '</p><ul class="bp-chips">' + attacks.map(chipOf).join('') + boosts.map(chipOf).join('') + '</ul>' +
        '<p class="bp-sub">' + esc(t('bp_item_h')) + '</p><p class="bp-line">' + (itemObj ? esc(EN ? itemObj.en.name : itemObj.name) : esc(t('bp_item_none'))) + '</p>' +
        '<p class="bp-sub">' + esc(t('bp_cards_h')) + '</p><ol class="bp-cardlist">' + cards.map(c => '<li>' + esc(EN ? c.en.name : c.name) + '</li>').join('') + '</ol>' +
        '<p class="bp-line">' + esc(coverLine) + '</p>' +
        '<div class="bp-share"><label class="sr" for="bp-link">' + esc(t('bp_link')) + '</label>' +
        '<input id="bp-link" class="bp-link" readonly value="' + esc(link) + '">' +
        '<button type="button" class="btn" id="bp-copy">' + esc(t('bp_copy')) + '</button>' +
        '<span id="bp-copied" class="muted small" role="status" aria-live="polite"></span></div>' +
        '<div class="bp-actions"><button type="button" class="btn ghost" id="bp-reset">' + esc(t('bp_reset')) + '</button>' +
        '<a class="btn ghost" href="' + monPath(p) + '">' + esc(t('bp_open_sheet')) + '</a></div>';
      document.getElementById('bp-copy').addEventListener('click', () => {
        const box = document.getElementById('bp-link');
        const done = () => { document.getElementById('bp-copied').textContent = t('bp_copied'); };
        if (navigator.clipboard) navigator.clipboard.writeText(box.value).then(done, () => { box.select(); document.execCommand('copy'); done(); });
        else { box.select(); document.execCommand('copy'); done(); }
      });
      document.getElementById('bp-reset').addEventListener('click', () => {
        st = recommendedState(st.dex);
        writeUrl();
        renderAll();
      });
    }

    function recommendedState(dex) {
      const rec = recommended(dex, species, game, rules);
      return { dex, group: rec.group, item: rec.item, cards: rec.cards };
    }

    function renderAll() {
      renderMon();
      renderSlots();
      renderItems();
      renderCards();
      renderWarnings();
      renderResult();
      itemSel.value = st.item || '';
    }

    function changeDex(dex) {
      st = recommendedState(dex);
      writeUrl();
      renderAll();
    }

    input.addEventListener('change', () => {
      const dex = resolve(input.value);
      if (dex == null) {
        input.value = monName(byDex.get(st.dex)) + ' (#' + st.dex + ')';
        return;
      }
      if (dex !== st.dex) changeDex(dex);
    });

    slotsBox.addEventListener('change', e => {
      const i = Number(e.target.dataset.slot);
      st.group[i] = e.target.value || null;
      writeUrl();
      refreshSlots();
      renderWarnings();
      renderResult();
    });
    itemSel.addEventListener('change', () => {
      st.item = itemSel.value || null;
      writeUrl();
      renderResult();
    });
    cardsBox.addEventListener('change', e => {
      const i = Number(e.target.dataset.card);
      st.cards[i] = e.target.value || null;
      writeUrl();
      renderResult();
    });

    writeUrl();
    renderAll();
    root.hidden = false;
  }

  Promise.all([getJSON('game-stats.json'), getJSON('species.json'), getJSON('pokemon-index.json'), getJSON('owner_rules.json')])
    .then(([game, species, index, rules]) => {
      if (page === 'buscador') finder(game, index);
      else planner(game, species, index, rules);
    })
    .catch(err => {
      const box = document.getElementById(page === 'buscador' ? 'tf-status' : 'bp-warn');
      if (box) box.textContent = err.message;
    });

  if (typeof module !== 'undefined' && module.exports) module.exports = toolsApi;
})();
