/* SurvivorTiers · JS sin dependencias: buscador, orden, colección, progreso de gacha y las demos de la página Método.
   No hace peticiones salvo a los JSON y los sprites del propio sitio. Solo guarda en localStorage la colección que
   importas (clave survivortiers.coleccion), y se puede borrar desde la página. Compartir la pone en el fragmento
   de la URL (#c=); abrir ese enlace no escribe en localStorage ni llama al juego. No usa cookies.
   SurvivorTiers · dependency-free JS: search, sorting, collection, gacha progress and the Method page demos. It only
   requests this site's own JSON files and sprites, and stores only the collection you import, in localStorage (key
   survivortiers.coleccion), which you can delete from the page. Sharing puts it in the URL fragment (#c=); opening
   that link does not write localStorage or call the game. No cookies. */
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
      legY: 'Legendarios', legN: 'No legendarios',
      cardTitle: (name, dex, rank, tier) => name + ' · nº ' + dex + ' · puesto ' + rank + ' · tier ' + tier,
      pct: v => v + NBSP + '%',
      notJson: 'Eso no es JSON. Copia el resultado entero, de la { a la }.',
      notCollection: 'Eso no es una colección.',
      missingKeys: 'Faltan «dex» o «shiny». Copia el JSON que devuelve el comando de esta página.',
      badShinyInfo: 'El bloque «shinyInfo» no tiene el formato del comando. Vuelve a copiar el comando de esta página.',
      pasteFirst: 'Pega primero el resultado del comando.',
      tooBig: 'El archivo es demasiado grande.',
      copied: 'Copiado',
      copyFail: 'No se ha podido copiar. Selecciónalo a mano.',
      locale: 'es-ES',
      haveOf: (a, b) => a + ' de ' + b,
      shinyTitle: 'Tienes el shiny', shiny: '★',
      owned: n => String(n),
      missingSA: n => 'Te faltan de S y A (' + n + ')',
      allSA: 'Tienes todos los S y A.',
      collectionOf: n => 'Colección de ' + n, yourCollection: 'Tu colección',
      dexStat: () => 'en la Pokédex',
      shinyStat: 'shiny', lastSave: 'última partida',
      unknown: n => n + ' no están en el ranking.',
      byTier: 'Por tier', byRarity: 'Por rareza', breakBy: 'Agrupar por',
      legendWord: 'Legendarios', legendLabel: 'legendarios y singulares', legendShiny: n => n + ' shiny entre ellos',
      legendView: 'Legendarios', missingRar: n => 'Te faltan de 5★ (' + n + ')', allRar: 'Tienes todos los de 5★.',
      presume: 'Presumir', choiceCol: 'Colección', choiceLeg: 'Legendarios', choiceShiny: 'Shinies',
      choiceSub: (a, b) => a + ' de ' + b, closeDialog: 'Cerrar', previewLabel: 'Vista previa',
      copyLinkBtn: 'Copiar enlace', nativeShare: 'Compartir', nameField: 'Nombre',
      pause: 'Pausa', play: 'Seguir',
      repCount: (n, total) => grouped(n, '.') + ' / ' + grouped(total, '.'),
      stepOf: (i, n) => 'Paso ' + i + ' de ' + n,
      auto: 'Auto', stop: 'Parar',
      over: 'Fin',
      sep: '.',
      savedHere: 'Guardada en este navegador', reimport: 'Reimportar', forget: 'Borrar de este navegador',
      forgot: 'Borrada de este navegador. Pega el resultado otra vez cuando quieras.',
      storageOff: 'Este navegador no deja guardar la colección. Solo se verá mientras la página esté abierta.',
      ownedIn: (a, b) => 'Tienes ' + a + ' de ' + b,
      planH: 'Qué gacha tirar',
      planLede: 'Cada tirada da un Pokémon que te falta con la probabilidad de «Nuevo por tirada».',
      planNote: '«Tiradas para completarlo» es una estimación de 150 simulaciones de tiradas normales (×1).',
      planOdds: n => '1 de cada ' + n + ' tiradas da un Pokémon que te falta.',
      planSee: 'Ver todos los banners',
      planDone: 'Ya tienes todos los Pokémon de los banners.',
      colBanner: 'Banner', colMissing: 'Te faltan', colHave: 'Tienes', colNew: 'Por tirada', colPulls: 'Tiradas', pullsAvg: '≈ media de 150 simulaciones',
      pullHere: 'Tira aquí', complete: 'Completo',
      share: 'Compartir', download: 'Descargar imagen',
      otherCollection: 'Colección de otro jugador', backToMine: 'Volver a la mía',
      shareNamePh: 'Tu nombre', shareNameLabel: 'Nombre en el enlace y la imagen',
      copiedLink: 'Enlace copiado', shareFail: 'No se ha podido compartir.', copyLink: 'Copiar enlace', sendLink: 'Enviar enlace',
      imageFail: 'No se ha podido crear la imagen.', badLink: 'Ese enlace no se puede leer.',
      shareTitle: 'Mi colección', collectionWord: 'Colección',
      siteHost: 'survivortiers.pages.dev',
      viewLabel: 'Vista de la colección', viewNormal: 'Normal', viewShiny: 'Shiny',
      hunted: 'cazados en salvaje', shinyTotal: 'shiny en total', shinyHunter: 'Cazador de shiny',
      gachaCount: n => n + ' de gacha', unknownOrigin: n => n + ' sin origen',
      legacyNote: 'Este JSON no dice de dónde sale cada shiny. Pega otra vez el comando de esta página para verlo.',
      odds: () => '1 de cada ' + grouped(4096, '.') + ' Pokémon salvajes · 1 de cada 100 tiradas de gacha',
      shinydex: 'Shinydex', filterLabel: 'Filtro', sortLabel: 'Orden',
      filterAll: 'Todos', filterWild: 'Solo salvaje', sortNew: 'Recientes', sortDex: 'Pokédex',
      badgeWild: 'Salvaje', badgeGacha: 'Gacha',
      shEmpty: 'Todavía no tienes ningún shiny.', shEmptyWild: 'Ningún shiny cazado en salvaje todavía.',
    },
    en: {
      loadFail: n => 'Could not load ' + n,
      loadFailAll: m => 'Could not load the data: ' + m,
      count: (n, total) => n + ' of ' + total,
      legY: 'Legendary', legN: 'Not legendary',
      cardTitle: (name, dex, rank, tier) => name + ' · no. ' + dex + ' · rank ' + rank + ' · tier ' + tier,
      pct: v => v + '%',
      notJson: 'That is not JSON. Copy the whole result, from { to }.',
      notCollection: 'That is not a collection.',
      missingKeys: 'Missing "dex" or "shiny". Copy the JSON that this page\'s command returns.',
      badShinyInfo: '"shinyInfo" is not in the command\'s format. Copy this page\'s command again.',
      pasteFirst: 'Paste the command result first.',
      tooBig: 'The file is too large.',
      copied: 'Copied',
      copyFail: 'Could not copy. Select it by hand.',
      locale: 'en-US',
      haveOf: (a, b) => a + ' of ' + b,
      shinyTitle: 'You have the shiny', shiny: '★',
      owned: n => String(n),
      missingSA: n => 'Missing from S and A (' + n + ')',
      allSA: 'You have every S and A.',
      collectionOf: n => 'Collection of ' + n, yourCollection: 'Your collection',
      dexStat: () => 'in the Pokédex',
      shinyStat: 'shiny', lastSave: 'last save',
      unknown: n => n + ' not in the ranking.',
      byTier: 'By tier', byRarity: 'By rarity', breakBy: 'Group by',
      legendWord: 'Legendaries', legendLabel: 'legendaries and singulars', legendShiny: n => n + ' shiny among them',
      legendView: 'Legendaries', missingRar: n => 'Missing from 5★ (' + n + ')', allRar: 'You have every 5★.',
      presume: 'Show off', choiceCol: 'Collection', choiceLeg: 'Legendaries', choiceShiny: 'Shinies',
      choiceSub: (a, b) => a + ' of ' + b, closeDialog: 'Close', previewLabel: 'Preview',
      copyLinkBtn: 'Copy link', nativeShare: 'Share', nameField: 'Name',
      pause: 'Pause', play: 'Play',
      repCount: (n, total) => grouped(n, ',') + ' / ' + grouped(total, ','),
      stepOf: (i, n) => 'Step ' + i + ' of ' + n,
      auto: 'Auto', stop: 'Stop',
      over: 'Over',
      sep: ',',
      savedHere: 'Saved in this browser', reimport: 'Re-import', forget: 'Delete from this browser',
      forgot: 'Deleted from this browser. Paste the result again whenever you like.',
      storageOff: 'This browser does not let the collection be saved. It will only show while the page is open.',
      ownedIn: (a, b) => 'You have ' + a + ' of ' + b,
      planH: 'What to pull',
      planLede: 'Each pull gives a Pokémon you are missing, with the chance in "New per pull".',
      planNote: '"Pulls to complete" is an estimate from 150 simulations of single pulls (×1).',
      planOdds: n => '1 in ' + n + ' pulls gives a Pokémon you are missing.',
      planSee: 'See every banner',
      planDone: 'You already have every Pokémon in the banners.',
      colBanner: 'Banner', colMissing: 'Missing', colHave: 'You have', colNew: 'Per pull', colPulls: 'Pulls', pullsAvg: '≈ average of 150 simulations',
      pullHere: 'Pull here', complete: 'Complete',
      share: 'Share', download: 'Download image',
      otherCollection: 'Another player\'s collection', backToMine: 'Back to mine',
      shareNamePh: 'Your name', shareNameLabel: 'Name on the link and the image',
      copiedLink: 'Link copied', shareFail: 'Could not share.', copyLink: 'Copy link', sendLink: 'Send link',
      imageFail: 'Could not create the image.', badLink: 'That link could not be read.',
      shareTitle: 'My collection', collectionWord: 'Collection',
      siteHost: 'survivortiers.pages.dev',
      viewLabel: 'Collection view', viewNormal: 'Normal', viewShiny: 'Shiny',
      hunted: 'hunted in the wild', shinyTotal: 'shiny in total', shinyHunter: 'Shiny hunter',
      gachaCount: n => n + ' from gacha', unknownOrigin: n => n + ' unknown origin',
      legacyNote: 'This JSON does not say where each shiny came from. Paste this page\'s command again to see it.',
      odds: () => '1 in ' + grouped(4096, ',') + ' wild Pokémon · 1 in 100 gacha pulls',
      shinydex: 'Shinydex', filterLabel: 'Filter', sortLabel: 'Sort',
      filterAll: 'All', filterWild: 'Wild only', sortNew: 'Newest', sortDex: 'Pokédex',
      badgeWild: 'Wild', badgeGacha: 'Gacha',
      shEmpty: 'You have no shiny yet.', shEmptyWild: 'No shiny hunted in the wild yet.',
    },
  }[EN ? 'en' : 'es'];

  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const plain = s => String(s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const monName = p => (EN ? p.nameEn : p.name);
  // Misma regla que build/slugs.py: número de Pokédex, guion, nombre inglés en ASCII.
  function speciesSlug(name) {
    const s = String(name).replace(/♀/g, '-f').replace(/♂/g, '-m').normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase();
    return s.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  }
  globalThis.speciesSlug = speciesSlug;
  const monPath = p => home + 'pokemon/' + p.dex + '-' + speciesSlug(p.nameEn) + '/';
  const getJSON = name => fetch(assets + 'data/' + name).then(r => {
    if (!r.ok) throw new Error(TEXT.loadFail(name));
    return r.json();
  });

  const state = { mons: null, byDex: null, cards: [], groups: [], view: 'normal', breakBy: 'rarity', wildOnly: false, shinySort: 'new', shinyDex: null };

  // ---------------------------------------------------------------- tarjetas
  function card(p, extraClass, extraHtml) {
    const [rank, tier] = p.r;
    const cls = 'mon' + (extraClass ? ' ' + extraClass : '');
    const title = TEXT.cardTitle(monName(p), p.dex, rank, tier);
    return '<a class="' + cls + '" href="' + monPath(p) + '" data-dex="' + p.dex + '" title="' + esc(title) + '">' +
      '<span class="sp"><img class="px" src="' + sprites + p.dex + spriteExt + '" width="' + p.w * SCALE + '" height="' + p.h * SCALE +
      '" alt="" loading="lazy" decoding="async"></span><span class="nm">' + esc(monName(p)) + '</span><span class="rk">' + rank + '</span>' +
      (extraHtml || '') + '</a>';
  }

  // ---------------------------------------------------------------- tier list
  // Buscador (nombre, tipo o nº), orden y agrupación: por tier, tipo, rareza, región o legendarios, o sin agrupar.
  // Las cabeceras de los grupos las dibuja layout(); los textos de tipo y rareza llegan en #labels (render.py).
  const GROUP_OF = {
    tier: p => p.r[1],
    type: p => p.types[0],
    rar: p => p.rarity,
    region: p => p.bannerId,
    leg: p => (p.legendary ? 1 : 0),
    none: () => 'all',
  };
  let groupMode = 'tier';
  let labels = null;

  // Orden de los grupos: tiers de S a D, tipos como en el juego, rareza de la más rara a la común, región por generación.
  function orderedKeys(present) {
    if (groupMode === 'tier') return TIERS.filter(k => present.has(k));
    if (groupMode === 'type') return Object.keys(labels.type).filter(k => present.has(k));
    if (groupMode === 'rar') return [5, 4, 3, 2, 1].filter(k => present.has(k));
    if (groupMode === 'leg') return [1, 0].filter(k => present.has(k));
    if (groupMode === 'region') return [...present].sort((a, b) => a - b);
    return ['all'];
  }

  // Lo que se ve en la cabecera de un grupo (las cabeceras de tier son las de siempre, con la letra grande).
  function groupHead(k) {
    if (groupMode === 'tier') return '<b>' + k + '</b>' + (k === 'S' ? '<i class="ico ico-crown" aria-hidden="true"></i>' : '');
    if (groupMode === 'type') return '<b class="grp-name"><span class="type" style="--tc:' + labels.typeColor[k] +
      ';--tg:' + labels.typeText[k] + '">' + labels.typeGlyph[k] + '<span>' + esc(labels.type[k]) + '</span></span></b>';
    if (groupMode === 'rar') return '<b class="grp-name"><svg class="rball" viewBox="0 0 12 12" aria-hidden="true">' +
      '<use href="#rball-' + k + '"/></svg>' + esc(labels.rar[k]) + '</b>';
    if (groupMode === 'leg') return '<b class="grp-name">' + esc(k === 1 ? TEXT.legY : TEXT.legN) + '</b>';
    if (groupMode === 'region') return '<b class="grp-name">' + esc(labels.region[k]) + '</b>';
    return '';
  }

  // Reparte las tarjetas en grupos según el modo y el orden actual. Cada tarjeta enseña el valor del orden.
  function layout() {
    const root = $('#tierlist');
    const byKey = new Map();
    sortedCards().forEach(el => {
      const k = GROUP_OF[groupMode](state.byDex.get(+el.dataset.dex));
      if (!byKey.has(k)) byKey.set(k, []);
      byKey.get(k).push(el);
    });
    root.textContent = '';
    state.groups = orderedKeys(new Set(byKey.keys())).map(k => {
      const cards = byKey.get(k);
      const sec = document.createElement('section');
      sec.className = 'group tier' + (groupMode === 'tier' ? ' tier-' + k : '') + (groupMode === 'none' ? ' plain' : '');
      if (groupMode !== 'none') {
        const head = document.createElement('header');
        head.className = 'tier-head' + (groupMode === 'tier' ? '' : ' grp-head');
        const color = groupMode === 'type' ? labels.typeColor[k] : groupMode === 'rar' ? labels.rarColor[k] : '';
        if (color) head.style.setProperty('--tc', color);
        head.innerHTML = groupHead(k) + '<span class="n">' + cards.length + '</span>';
        sec.appendChild(head);
      }
      const grid = document.createElement('div');
      grid.className = 'grid';
      cards.forEach(el => grid.appendChild(el));
      sec.appendChild(grid);
      root.appendChild(sec);
      return { el: sec, cards };
    });
    state.cards.forEach(el => { el.querySelector('.rk').textContent = SORTS[sortKey].show(state.byDex.get(+el.dataset.dex)); });
    applySearch();
  }

  // Oculta las tarjetas que no coinciden, los grupos que quedan vacíos y enseña el recuento.
  function applySearch() {
    const raw = $('#q').value;
    const terms = plain(raw).trim().split(/\s+/).filter(Boolean);
    let shown = 0;
    state.cards.forEach(el => {
      const p = state.byDex.get(+el.dataset.dex);
      const ok = terms.every(term => p.q.includes(term));
      el.classList.toggle('dim', !ok);
      if (ok) shown++;
    });
    state.groups.forEach(g => g.el.classList.toggle('hidden', terms.length > 0 && g.cards.every(el => el.classList.contains('dim'))));
    $('#clear').hidden = !raw;
    $('#count').textContent = terms.length ? TEXT.count(shown, state.mons.length) : '';
    $('#nomatch').hidden = !(terms.length && shown === 0);
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

  function syncDir() {
    const b = $('#dir');
    const label = sortDesc ? b.dataset.desc : b.dataset.asc;
    b.setAttribute('aria-label', label);
    b.title = label;
    b.classList.toggle('desc', sortDesc);
  }

  function indexMons(mons) {
    state.byDex = new Map();
    mons.forEach(p => {
      p.q = plain([p.name, p.nameEn, p.dex, '#' + p.dex, ...p.types, ...p.types.map(t => TYPE_ES[t])].join(' '));
      state.byDex.set(p.dex, p);
    });
  }

  // Elige una tarjeta visible al azar, la lleva al centro y la hace latir un momento.
  function pickRandom() {
    const open = state.cards.filter(el => !el.classList.contains('dim'));
    if (!open.length) return;
    const el = open[Math.floor(Math.random() * open.length)];
    const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
    el.scrollIntoView({ block: 'center', behavior: calm ? 'auto' : 'smooth' });
    el.classList.remove('pick');
    void el.offsetWidth;
    el.classList.add('pick');
  }

  function initTierList() {
    labels = JSON.parse($('#labels').textContent);
    state.cards = $$('#tierlist .mon');
    // Las tiers que dibuja el servidor se rehacen aquí: las tarjetas se reparten de nuevo según el modo.
    $$('#tierlist > section').forEach(s => s.remove());
    const q = $('#q'), sort = $('#sort');
    q.addEventListener('input', applySearch);
    $('#clear').addEventListener('click', () => { q.value = ''; applySearch(); q.focus(); });
    $('#random').addEventListener('click', pickRandom);
    sort.addEventListener('change', () => {
      sortKey = sort.value;
      sortDesc = SORTS[sortKey].desc;
      syncDir();
      layout();
    });
    $('#dir').addEventListener('click', () => {
      sortDesc = !sortDesc;
      syncDir();
      layout();
    });
    $$('.seg[data-group]').forEach(b => b.addEventListener('click', () => {
      groupMode = b.dataset.group;
      $$('.seg[data-group]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
      layout();
    }));
    document.addEventListener('keydown', e => {
      if (e.key === '/' && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
        e.preventDefault();
        q.focus();
      } else if (e.key === 'Escape' && document.activeElement === q && q.value) {
        q.value = '';
        applySearch();
      }
    });
    layout();
  }

  // ---------------------------------------------------------------- colección
  // Desglose por rareza (por defecto) o por tier. Cada fila: cuántos tienes de un grupo.
  function breakKeys(by) {
    return by === 'tier' ? TIERS : [5, 4, 3, 2, 1];
  }

  function breakOf(by) {
    return by === 'tier' ? p => p.r[1] : p => p.rarity;
  }

  function breakRows(owned, by) {
    const of = breakOf(by);
    return breakKeys(by).map(key => {
      const all = state.mons.filter(p => of(p) === key);
      return { key: key, n: all.length, have: all.filter(p => owned.has(p.dex)).length };
    });
  }

  function breakBadge(by, key) {
    if (by === 'tier') return '<span class="tier-badge ' + key + '">' + key + '</span>';
    return '<span class="rar-badge r' + key + '"><svg class="rball" viewBox="0 0 12 12" aria-hidden="true"><use href="#rball-' + key +
      '"/></svg>' + key + '★</span>';
  }

  function breakList(by, rows) {
    return '<ol class="rows">' + rows.map(r => {
      const pct = r.n ? (100 * r.have / r.n).toFixed(1) : 0;
      const color = by === 'tier' ? 'var(--tier-' + r.key + ')' : 'var(--rar-' + r.key + ')';
      return '<li class="row"><span class="row-label">' + breakBadge(by, r.key) + '</span>' +
        '<span class="row-bar"><i style="width:' + pct + '%;--bf:' + color + '"></i></span>' +
        '<span class="row-num">' + esc(TEXT.haveOf(r.have, r.n)) + '</span></li>';
    }).join('') + '</ol>';
  }

  function breakTools() {
    const seg = (by, label) => '<button class="seg" type="button" data-break="' + by + '" aria-pressed="' + (state.breakBy === by) +
      '">' + esc(label) + '</button>';
    return '<div class="break-tools" role="group" aria-label="' + esc(TEXT.breakBy) + '">' + seg('rarity', TEXT.byRarity) +
      seg('tier', TEXT.byTier) + '</div>';
  }

  function ownedGroups(c, owned, by) {
    const shinySet = new Set(c.shiny);
    const of = breakOf(by);
    return breakKeys(by).map(key => {
      const mine = state.mons.filter(p => of(p) === key && owned.has(p.dex))
        .sort(by === 'tier' ? (a, b) => a.r[0] - b.r[0] : Collection.showOrder);
      if (!mine.length) return '';
      return '<h3>' + breakBadge(by, key) + ' ' + TEXT.owned(mine.length) + '</h3><div class="grid">' +
        mine.map(p => card(p, 'owned', shinySet.has(p.dex) ? '<span class="sh" title="' + TEXT.shinyTitle + '">' + TEXT.shiny + '</span>' : '')).join('') +
        '</div>';
    }).join('');
  }

  function missingHtml(owned, by) {
    if (by === 'rarity') {
      const missing = state.mons.filter(p => p.rarity === 5 && !owned.has(p.dex)).sort(Collection.showOrder);
      return missing.length
        ? '<h3>' + esc(TEXT.missingRar(missing.length)) + '</h3><div class="grid">' + missing.map(p => card(p, 'miss')).join('') + '</div>'
        : '<p><strong>' + esc(TEXT.allRar) + '</strong></p>';
    }
    const missing = state.mons.filter(p => ['S', 'A'].includes(p.r[1]) && !owned.has(p.dex)).sort((a, b) => a.r[0] - b.r[0]);
    return missing.length
      ? '<h3>' + TEXT.missingSA(missing.length) + '</h3><div class="grid">' + missing.map(p => card(p, 'miss')).join('') + '</div>'
      : '<p><strong>' + TEXT.allSA + '</strong></p>';
  }

  function legendView(c, owned) {
    const legends = state.mons.filter(p => p.legendary).sort(Collection.showOrder);
    const have = legends.filter(p => owned.has(p.dex));
    const shinySet = new Set(c.shiny);
    const shinies = have.filter(p => shinySet.has(p.dex)).length;
    const pct = legends.length ? (100 * have.length / legends.length).toFixed(1) : 0;
    const hero = '<div class="hero"><p class="hero-line"><b class="hero-n">' + have.length + '</b>' +
      '<span class="hero-of">/ ' + legends.length + '</span><span class="hero-what">' + esc(TEXT.legendLabel) + '</span>' +
      (shinies ? '<span class="badge-shiny">★ ' + shinies + '</span>' : '') + '</p>' +
      '<div class="meter" role="img" aria-label="' + esc(TEXT.haveOf(have.length, legends.length)) + '"><i style="width:' + pct + '%"></i></div></div>';
    return hero + '<div class="grid">' + legends.map(p => card(p, owned.has(p.dex) ? 'owned' : 'miss',
      owned.has(p.dex) && shinySet.has(p.dex) ? '<span class="sh" title="' + TEXT.shinyTitle + '">' + TEXT.shiny + '</span>' : '')).join('') +
      '</div>';
  }

  function collectionBody(c, owned, known, unknown, total, guest) {
    const shinyBadge = c.shiny.length
      ? '<span class="badge-shiny">★ ' + c.shiny.length + '<span class="sr"> ' + esc(TEXT.shinyStat) + '</span></span>' : '';
    const day = !guest && c.updated ? new Date(c.updated).toLocaleDateString(TEXT.locale, { day: 'numeric', month: 'short' }) : '';
    const hero = '<div class="hero"><p class="hero-line"><b class="hero-n">' + known.length + '</b>' +
      '<span class="hero-of">/ ' + total + '</span><span class="hero-what">' + TEXT.dexStat() + '</span>' + shinyBadge + '</p>' +
      '<div class="meter" role="img" aria-label="' + esc(TEXT.haveOf(known.length, total)) + '"><i style="width:' +
      (100 * known.length / total).toFixed(1) + '%"></i></div>' +
      (day ? '<p class="hero-sub">' + esc(TEXT.lastSave) + ': ' + esc(day) + '</p>' : '') + '</div>';
    const by = state.breakBy;
    return hero +
      (unknown ? '<p class="muted small">' + TEXT.unknown(unknown) + '</p>' : '') +
      planHtml(owned) +
      '<div class="break-head"><h3>' + esc(by === 'tier' ? TEXT.byTier : TEXT.byRarity) + '</h3>' + breakTools() + '</div>' +
      breakList(by, breakRows(owned, by)) + ownedGroups(c, owned, by) + missingHtml(owned, by);
  }

  function renderCollection(c, opts) {
    const guest = !!(opts && opts.guest);
    const shareName = (opts && opts.shareName) || '';
    const owned = new Set(c.dex);
    const known = state.mons.filter(p => owned.has(p.dex));
    const unknown = c.dex.length - known.length;
    const total = state.mons.length;
    const heading = guest
      ? (shareName ? '<h2>' + esc(shareName) + '</h2>' : '')
      : '<h2>' + (c.name ? TEXT.collectionOf(esc(c.name)) : TEXT.yourCollection) + '</h2>';
    const body = state.view === 'shiny' ? shinyView(c, guest)
      : state.view === 'legend' ? legendView(c, owned)
      : collectionBody(c, owned, known, unknown, total, guest);
    const result = $('#result');
    const pull = result.querySelector('.pull-more');
    const wasOpen = !!(pull && pull.open);
    result.innerHTML = viewTabs() + heading + body;
    if (wasOpen) { const again = result.querySelector('.pull-more'); if (again) again.open = true; }
    if (state.view === 'shiny') paintShinyGrid(c, guest);
  }

  // ---------------------------------------------------------------- vista shiny
  const dayDate = day => new Date(day * 864e5);
  const dayLabel = day => dayDate(day).toLocaleDateString(TEXT.locale, { day: 'numeric', month: 'short', timeZone: 'UTC' });
  const dayIso = day => dayDate(day).toISOString().slice(0, 10);

  // Cazados en salvaje y de gacha. Un JSON sin origen (antes de shinyInfo) cuenta todos como «shiny en total».
  function hunterCounts(c) {
    const k = Collection.shinyCounts(c);
    const legacy = k.wild === 0 && k.gacha === 0 && k.unknown > 0;
    return { hunted: legacy ? k.total : k.wild, legacy: legacy, gacha: k.gacha, unknown: k.unknown };
  }

  function hunterFacts(k) {
    return [k.gacha ? TEXT.gachaCount(k.gacha) : '', k.unknown && !k.legacy ? TEXT.unknownOrigin(k.unknown) : ''].filter(Boolean).join(' · ');
  }

  function shinyDexSet() {
    if (!state.shinyDex) state.shinyDex = new Set(state.mons.filter(p => p.sh).map(p => p.dex));
    return state.shinyDex;
  }

  function shinyDexCount(c) {
    const set = shinyDexSet();
    return { have: c.shiny.filter(d => set.has(d)).length, total: set.size };
  }

  function viewTabs() {
    const tab = (view, icon, label) => '<button class="view-btn" type="button" data-view="' + view + '" aria-pressed="' +
      (state.view === view) + '">' + icon + '<span>' + esc(label) + '</span></button>';
    return '<div class="views" role="group" aria-label="' + esc(TEXT.viewLabel) + '">' +
      tab('normal', '<i class="ico ico-ball" aria-hidden="true"></i>', TEXT.viewNormal) +
      tab('shiny', '<i class="ico ico-sparkle" aria-hidden="true"></i>', TEXT.viewShiny) +
      tab('legend', '<i class="ico ico-crown" aria-hidden="true"></i>', TEXT.legendView) + '</div>';
  }

  function shinyTools(guest) {
    const seg = (attr, val, label, on) => '<button class="seg" type="button" data-' + attr + '="' + val + '" aria-pressed="' + on + '">' +
      esc(label) + '</button>';
    return '<div class="sh-tools">' +
      '<div class="sh-group" role="group" aria-label="' + esc(TEXT.filterLabel) + '">' +
      seg('sh-filter', 'all', TEXT.filterAll, !state.wildOnly) + seg('sh-filter', 'wild', TEXT.filterWild, state.wildOnly) + '</div>' +
      (guest ? '' : '<div class="sh-group" role="group" aria-label="' + esc(TEXT.sortLabel) + '">' +
        seg('sh-sort', 'new', TEXT.sortNew, state.shinySort === 'new') + seg('sh-sort', 'dex', TEXT.sortDex, state.shinySort === 'dex') + '</div>') +
      '</div>';
  }

  function shinyView(c, guest) {
    const k = hunterCounts(c);
    const dex = shinyDexCount(c);
    const facts = hunterFacts(k);
    const pct = dex.total ? (100 * dex.have / dex.total).toFixed(1) : 0;
    return '<section class="sh-hero">' +
      '<div class="sh-count"><span class="sh-spk" aria-hidden="true"><i class="ico ico-sparkle"></i></span>' +
      '<b class="sh-n">' + k.hunted + '</b><span class="sh-what">' + esc(k.legacy ? TEXT.shinyTotal : TEXT.hunted) + '</span></div>' +
      (facts ? '<p class="sh-facts">' + esc(facts) + '</p>' : '') +
      (k.legacy ? '<p class="sh-note muted small">' + esc(TEXT.legacyNote) + '</p>' : '') +
      '<p class="sh-odds muted small">' + esc(TEXT.odds()) + '</p>' +
      '</section>' +
      '<div class="sh-dex"><div class="sh-dex-head"><span>' + esc(TEXT.shinydex) + '</span><b>' + dex.have + ' / ' + dex.total + '</b></div>' +
      '<div class="meter" role="img" aria-label="' + esc(TEXT.shinydex + ' ' + dex.have + ' / ' + dex.total) + '"><i style="width:' + pct + '%"></i></div></div>' +
      (k.legacy ? '' : shinyTools(guest)) +
      '<div class="sh-grid" id="sh-grid"></div>';
  }

  function shinyCard(p, row) {
    const badge = row.from === 'wild' || row.from === 'gacha'
      ? '<span class="sh-badge sh-' + row.from + '">' + esc(row.from === 'wild' ? TEXT.badgeWild : TEXT.badgeGacha) + '</span>' : '';
    return '<a class="sh-card" href="' + monPath(p) + '" title="' + esc(monName(p)) + '">' +
      '<span class="sh-spr"><img src="' + sprites + 'shiny/' + p.dex + spriteExt + '" width="' + p.w * SCALE + '" height="' + p.h * SCALE +
      '" alt="" loading="lazy" decoding="async"></span>' +
      '<span class="sh-nm">' + esc(monName(p)) + '</span>' +
      '<span class="sh-meta">' + badge + (row.day !== null ? '<time datetime="' + dayIso(row.day) + '">' + esc(dayLabel(row.day)) + '</time>' : '') +
      '</span></a>';
  }

  function paintShinyGrid(c, guest) {
    const k = hunterCounts(c);
    const rows = Collection.shinyRows(c, { sort: guest ? 'dex' : state.shinySort, wildOnly: state.wildOnly && !k.legacy })
      .filter(r => state.byDex.has(r.dex));
    $('#sh-grid').innerHTML = rows.length
      ? rows.map(r => shinyCard(state.byDex.get(r.dex), r)).join('')
      : '<p class="sh-empty">' + esc(c.shiny.length ? TEXT.shEmptyWild : TEXT.shEmpty) + '</p>';
  }

  // ---------------------------------------------------------------- gacha: qué tirar
  // Mismo modelo que systems/gacha.js del juego: 1★ 45 % · 2★ 30 % · 3★ 17 % · 4★ 6,5 % · 5★ 1,5 %. Cada tirada saca un
  // Pokémon al azar del pool de su rareza en el banner (o del más cercano si ese pool está vacío). A las 70 tiradas sin
  // 5★, la siguiente es 5★ (pity). Las garantías de la ×10 no se cuentan.
  const GACHA_RATES = [[1, 45], [2, 30], [3, 17], [4, 6.5], [5, 1.5]];
  const GACHA_NEAR = [0, -1, 1, -2, 2, -3, 3, -4, 4];
  const PITY = 70;
  const SIM_RUNS = 150;

  // gen -> { gen, all: [dex], byRarity: Map(rareza -> [dex]) }, a partir del índice de Pokémon.
  function bannerPools(mons) {
    const pools = new Map();
    mons.forEach(p => {
      let b = pools.get(p.bannerId);
      if (!b) pools.set(p.bannerId, b = { gen: p.bannerId, all: [], byRarity: new Map() });
      b.all.push(p.dex);
      if (!b.byRarity.has(p.rarity)) b.byRarity.set(p.rarity, []);
      b.byRarity.get(p.rarity).push(p.dex);
    });
    return pools;
  }

  // Pool de una rareza en el banner, o el no vacío más cercano (como poolNear() del juego).
  function nearPool(b, rarity) {
    for (const d of GACHA_NEAR) {
      const r = rarity + d;
      const list = r >= 1 && r <= 5 ? b.byRarity.get(r) : null;
      if (list && list.length) return { rarity: r, list };
    }
    return { rarity, list: b.all };
  }

  // Probabilidad de que una tirada dé un Pokémon que te falta (sin pity).
  function newPerPull(b, missing) {
    return GACHA_RATES.reduce((t, [r, pct]) => {
      const { list } = nearPool(b, r);
      return t + pct / 100 * list.filter(d => missing.has(d)).length / list.length;
    }, 0);
  }

  // Semilla fija: el número de tiradas no cambia al recargar la página.
  function rng(seed) {
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function rollRarity(x) {  // x en [0, 100)
    let acc = 0;
    for (const [r, pct] of GACHA_RATES) { acc += pct; if (x < acc) return r; }
    return 5;
  }

  // Tiradas esperadas (media de SIM_RUNS partidas) hasta tener todos los que te faltan del banner.
  function pullsToComplete(b, missing) {
    const near = [];
    for (let r = 1; r <= 5; r++) near[r] = nearPool(b, r);
    const rand = rng(b.gen * 7919 + 1);
    let total = 0;
    for (let run = 0; run < SIM_RUNS; run++) {
      const left = new Set(missing);
      let pity = 0, pulls = 0;
      while (left.size && pulls < 200000) {
        pulls++;
        pity++;
        const want = pity >= PITY ? 5 : rollRarity(rand() * 100);
        const { rarity, list } = near[want];
        if (rarity === 5) pity = 0;
        left.delete(list[Math.floor(rand() * list.length)]);
      }
      total += pulls;
    }
    return total / SIM_RUNS;
  }

  function bannerNames() {
    const el = $('#banners');
    return el ? JSON.parse(el.textContent) : [];
  }

  // La respuesta (en qué banner tirar) va arriba. La lista, con el mismo cálculo, queda plegada debajo.
  function planHtml(owned) {
    const pools = bannerPools(state.mons);
    const rows = bannerNames().map(bn => {
      const b = pools.get(bn.gen);
      const missing = new Set(b.all.filter(d => !owned.has(d)));
      return { name: bn.name, total: b.all.length, b, missing, n: missing.size, p: newPerPull(b, missing) };
    });
    const open = rows.filter(r => r.n).sort((a, b) => b.p - a.p);
    const done = rows.filter(r => !r.n);
    const top = open.find(r => r.p > 0);
    const line = r => {
      const have = r.total - r.n;
      const chip = r.n ? '<span class="pl-chip">' + esc(TEXT.pct(dec(100 * r.p, 1))) + '</span>' : '<span class="pl-chip is-empty">—</span>';
      const pulls = r.n ? grouped(Math.round(pullsToComplete(r.b, r.missing)), TEXT.sep) : esc(TEXT.complete);
      return '<li class="pl-row' + (r === top ? ' is-top' : '') + (r.n ? '' : ' is-done') + '">' +
        '<span class="pl-name">' + esc(r.name) + (r === top ? '<span class="pull-tag">' + esc(TEXT.pullHere) + '</span>' : '') + '</span>' +
        '<span class="pl-prog"><span class="pl-bar"><i style="width:' + (100 * have / r.total).toFixed(1) + '%"></i></span>' +
        '<span class="pl-num">' + esc(TEXT.haveOf(have, r.total)) + '</span></span>' +
        chip + '<span class="pl-pulls">' + pulls + '</span></li>';
    };
    const list = '<div class="pl-list"><div class="pl-head" aria-hidden="true"><span>' + esc(TEXT.colBanner) + '</span><span>' +
      esc(TEXT.colHave) + '</span><span>' + esc(TEXT.colNew) + '</span><span title="' + esc(TEXT.planNote) + '">' + esc(TEXT.colPulls) +
      '</span></div><ol class="pl-rows">' + open.map(line).join('') + done.map(line).join('') + '</ol>' +
      '<p class="pl-note">' + esc(TEXT.pullsAvg) + '</p></div>';
    const next = top ? open.filter(r => r !== top && r.p > 0).slice(0, 2) : [];
    return '<section class="pull" id="pull">' +
      '<h3 class="pull-h"><i class="ico ico-dice" aria-hidden="true"></i>' + esc(TEXT.planH) + '</h3>' +
      (top ? planBoard(top, next) : '<p class="pull-done"><i class="ico ico-trophy" aria-hidden="true"></i>' + esc(TEXT.planDone) + '</p>') +
      '<details class="pull-more"><summary>' + esc(TEXT.planSee) + '<i class="pull-chev" aria-hidden="true"></i></summary>' +
      '<div class="pull-body"><p class="pull-lede">' + esc(TEXT.planLede) + '</p>' + list + '</div></details></section>';
  }

  // Tarjeta del banner que más te acerca, y los dos siguientes en pequeño.
  function planBoard(top, next) {
    const odds = n => esc(TEXT.planOdds(n));
    const alts = next.map((r, i) => {
      const k = Math.round(1 / r.p);
      return '<li><span class="pull-n" aria-hidden="true">' + (i + 2) + '</span><b>' + esc(r.name) + '</b>' +
        '<span class="pull-k"><span class="sr">' + odds(k) + '</span><span aria-hidden="true">1/' + k + '</span></span>' +
        '<span class="pull-miss"><span class="sr">' + esc(TEXT.colMissing) + ' </span>' + r.n + '</span></li>';
    }).join('');
    const n = Math.round(1 / top.p);
    return '<div class="pull-board' + (alts ? ' with-alts' : '') + '"><article class="pull-hero">' +
      '<span class="pull-tag"><i class="ico ico-dice" aria-hidden="true"></i>' + esc(TEXT.pullHere) + '</span>' +
      '<p class="pull-name">' + esc(top.name) + '</p><p class="pull-odds">' + odds(n) + '</p>' +
      '<p class="pull-gap"><span>' + esc(TEXT.colMissing) + '</span><b>' + top.n + '</b></p></article>' +
      (alts ? '<ol class="pull-alts">' + alts + '</ol>' : '') + '</div>';
  }

  // ---------------------------------------------------------------- guardado en este navegador
  const STORE_KEY = 'survivortiers.coleccion';
  let viewing = null;
  let pendingOwn = null;

  function readSaved() {
    try {
      const o = JSON.parse(localStorage.getItem(STORE_KEY));
      if (!o || !o.data || !Array.isArray(o.data.dex) || !Array.isArray(o.data.shiny)) return null;
      return { c: { ...o.data, info: o.data.info || {} }, savedAt: +o.savedAt || 0 };
    } catch (e) { return null; }
  }

  function writeSaved(c) {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify({ savedAt: Date.now(), data: c }));
      return true;
    } catch (e) { return false; }  // sin almacenamiento (modo privado, cuota llena...)
  }

  function clearSaved() {
    try { localStorage.removeItem(STORE_KEY); } catch (e) { /* nada que borrar */ }
  }

  // Fila de acciones: una sola para la colección propia, la de otro jugador y los enlaces rotos.
  // mode: 'own' | 'failed' (sin almacenamiento) | 'guest' | 'broken' | 'forgot' | 'none'
  function renderSaved(mode) {
    const el = $('#saved');
    const guest = mode === 'guest';
    closePresume();
    const colBtn = (id, inner, label) => '<button class="col-btn" type="button" id="' + id + '"' +
      ' aria-label="' + esc(label) + '" title="' + esc(label) + '">' + inner + '</button>';
    const presume = '<button class="btn small col-presume" type="button" id="presume-open" aria-haspopup="dialog">' + ICO_SHARE +
      '<span>' + esc(TEXT.presume) + '</span></button>';
    const back = colBtn('back-own', ICO_BACK, TEXT.backToMine);
    const reimport = colBtn('reimport', '<i class="ico ico-import" aria-hidden="true"></i>', TEXT.reimport);
    const forget = colBtn('forget', '<i class="ico ico-trash" aria-hidden="true"></i>', TEXT.forget);
    const row = (meta, actions) => '<span class="col-meta' + (guest ? ' guest' : '') + '">' + meta + '</span>' +
      (actions.length ? '<span class="col-actions">' + actions.join('') + '</span>' : '');
    const html = {
      none: '',
      forgot: '<span class="col-meta">' + esc(TEXT.forgot) + '</span>',
      own: row(esc(TEXT.savedHere), [presume, reimport, forget]),
      failed: row(esc(TEXT.storageOff), [presume, reimport]),
      guest: row(ICO_USER + esc(TEXT.otherCollection), [presume, back]),
      broken: row('', [back]),
    };
    el.innerHTML = html[mode];
  }

  function closePresume() {
    const dlg = $('#presume');
    if (dlg && dlg.open) dlg.close();
  }

  // Progreso en cada tarjeta de gacha (página Gacha), si hay una colección guardada.
  function initGachaProgress() {
    const saved = readSaved();
    if (!saved) return;
    const owned = new Set(saved.c.dex);
    const pools = bannerPools(state.mons);
    $$('.gc-own').forEach(el => {
      const b = pools.get(+el.dataset.gen);
      el.textContent = TEXT.ownedIn(b.all.filter(d => owned.has(d)).length, b.all.length);
    });
  }

  function showError(msg) {
    $('#result').innerHTML = '<div class="err" role="alert">' + esc(msg) + '</div>';
  }

  // ---------------------------------------------------------------- compartir (enlace en el fragmento, imagen en el navegador)
  const ICO_SHARE = '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false" shape-rendering="crispEdges"><path fill="currentColor" d="M1 6h4v4H1zm10-5h4v4h-4zm0 10h4v4h-4z"/><path d="M5 8h6M9 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';
  const ICO_BACK = '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false" shape-rendering="crispEdges"><path fill="currentColor" d="M8 2 3 8l5 6V10h6V6H8z"/></svg>';
  const ICO_USER = '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false" shape-rendering="crispEdges"><path fill="currentColor" d="M6 1h4v4H6zM3 7h10v7H3z"/></svg>';
  const ICO_IMG = '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false" shape-rendering="crispEdges"><path fill="currentColor" fill-rule="evenodd" d="M1 1h14v14H1zM2 2v12h12V2z"/><path fill="currentColor" d="M4 12l3-4 2 2 1-1 2 3z"/></svg>';
  const ICO_COPY = '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false" shape-rendering="crispEdges"><path fill="none" stroke="currentColor" stroke-width="2" d="M6 1h9v9h-2M1 6h9v9H1z"/></svg>';
  const CARD_W = 1200, CARD_H = 630, CARD_LEFT = 48, CARD_BAR_W = 560;
  const CARD_UI = '"Zen Kaku Gothic New", sans-serif';
  const CARD_PIX = '"Pixelify Sans", monospace';
  const CARD_FONTS = ['400 20px "Zen Kaku Gothic New"', '700 20px "Zen Kaku Gothic New"', '700 52px "Pixelify Sans"'];
  let zenReady = null;

  function hashCollection() {
    let raw = location.hash.slice(3);
    if (!raw) return null;
    try { raw = decodeURIComponent(raw); } catch (e) { return null; }
    return ShareCodec.decodeCollection(raw);
  }

  function syncLangHash() {
    const hash = location.hash.startsWith('#c=') ? location.hash : '';
    $$('.lang a').forEach(a => {
      if (a.getAttribute('aria-current') === 'page') return;
      const href = a.getAttribute('href');
      if (!href || href === '#') return;
      if (!a.dataset.bare) a.dataset.bare = href.split('#')[0];
      a.setAttribute('href', a.dataset.bare + hash);
    });
  }

  const ICO_X = '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false" shape-rendering="crispEdges"><path fill="currentColor" d="M3 1h2v2h2v2h2V3h2V1h2v2h-2v2h-2v2h2v2h2v2h2v2h-2v-2h-2v-2H9v2H7v2H5v2H3v-2h2v-2h2v-2H5V7H3V5H1V3h2z"/></svg>';
  const FILE_NAME = { normal: 'survivortiers-collection.png', shiny: 'survivortiers-shiny.png', legend: 'survivortiers-legendarios.png' };
  const CHOICES = ['normal', 'legend', 'shiny'];
  let presumeView = 'normal';
  let shareNameOwn = '';
  let previewToken = 0;
  let previewTimer = 0;

  function shareUrl() {
    if (!viewing) return '';
    const name = $('#share-name') ? $('#share-name').value : '';
    return location.origin + location.pathname + location.search + '#c=' +
      ShareCodec.encodeCollection({ dex: viewing.c.dex, shiny: viewing.c.shiny, ...Collection.originForLink(viewing.c), name: name, view: presumeView });
  }

  function onMobileShare() {
    return !!(navigator.share && (matchMedia('(pointer: coarse)').matches ||
      (navigator.maxTouchPoints > 0 && matchMedia('(max-width: 820px)').matches)));
  }

  function shareLink() {
    const url = shareUrl();
    if (!url) return;
    const msg = $('#share-msg');
    if (onMobileShare()) {
      navigator.share({ title: TEXT.shareTitle, url }).then(() => {}, err => {
        if (err && err.name === 'AbortError') return;
        msg.textContent = TEXT.shareFail;
      });
      return;
    }
    const done = ok => { msg.textContent = ok ? TEXT.copiedLink : TEXT.copyFail; };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(() => done(true), () => done(false));
    else done(false);
  }

  function choiceLabel(view) {
    return view === 'shiny' ? TEXT.choiceShiny : view === 'legend' ? TEXT.choiceLeg : TEXT.choiceCol;
  }

  // Lo que dice cada opción de «Presumir» antes de abrirla: cuántos Pokémon o cazados entran en esa imagen.
  function choiceSub(view) {
    const c = viewing.c;
    const owned = new Set(c.dex);
    if (view === 'shiny') {
      const k = hunterCounts(c);
      return k.hunted + ' ' + (k.legacy ? TEXT.shinyTotal : TEXT.hunted);
    }
    if (view === 'legend') {
      const legends = state.mons.filter(p => p.legendary);
      return TEXT.choiceSub(legends.filter(p => owned.has(p.dex)).length, legends.length);
    }
    return TEXT.choiceSub(state.mons.filter(p => owned.has(p.dex)).length, state.mons.length);
  }

  function cardBlob() {
    return buildShareCanvas(viewing.c, $('#share-name').value, presumeView)
      .then(canvas => new Promise(resolve => canvas.toBlob(resolve, 'image/png')))
      .then(blob => { if (!blob) throw new Error('png'); return blob; });
  }

  function renderPreview() {
    if (!viewing) return;
    const token = ++previewToken;
    buildShareCanvas(viewing.c, $('#share-name').value, presumeView).then(canvas => {
      const pv = $('#ps-canvas');
      if (token !== previewToken || !pv) return;
      const ctx = pv.getContext('2d');
      ctx.clearRect(0, 0, pv.width, pv.height);
      ctx.drawImage(canvas, 0, 0);
    }).catch(() => { if (token === previewToken) $('#share-msg').textContent = TEXT.imageFail; });
  }

  function setChoice(view) {
    presumeView = view;
    $$('[data-choice]').forEach(b => {
      b.setAttribute('aria-pressed', String(b.dataset.choice === view));
      b.querySelector('b').textContent = choiceLabel(b.dataset.choice);
      b.querySelector('span').textContent = choiceSub(b.dataset.choice);
    });
    $('#share-link').querySelector('span').textContent = onMobileShare() ? TEXT.sendLink : TEXT.copyLinkBtn;
    renderPreview();
  }

  function shareImage() {
    if (!viewing) return;
    const btn = $('#share-img');
    const view = presumeView;
    btn.disabled = true;
    cardBlob().then(blob => {
      const a = document.createElement('a');
      const url = URL.createObjectURL(blob);
      a.href = url;
      a.download = FILE_NAME[view];
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1500);
    }).catch(() => { $('#share-msg').textContent = TEXT.imageFail; }).finally(() => { btn.disabled = false; });
  }

  // En el móvil, la imagen va como archivo a la hoja de compartir (si el navegador deja enviar archivos).
  function shareNativeImage() {
    const msg = $('#share-msg');
    const view = presumeView;
    cardBlob().then(blob => {
      const file = new File([blob], FILE_NAME[view], { type: 'image/png' });
      return navigator.share({ title: TEXT.shareTitle, files: [file] });
    }).catch(err => { if (err && err.name !== 'AbortError') msg.textContent = TEXT.shareFail; });
  }

  function canShareFiles() {
    try {
      return !!(navigator.canShare && navigator.canShare({ files: [new File([''], 'a.png', { type: 'image/png' })] }));
    } catch (e) { return false; }
  }

  function mountPresume() {
    if ($('#presume')) return;
    const mobile = onMobileShare();
    const dlg = document.createElement('dialog');
    dlg.id = 'presume';
    dlg.className = 'presume';
    dlg.setAttribute('aria-labelledby', 'presume-h');
    dlg.innerHTML =
      '<div class="ps-head"><h2 id="presume-h">' + esc(TEXT.presume) + '</h2>' +
      '<button class="col-btn" type="button" data-close aria-label="' + esc(TEXT.closeDialog) + '" title="' + esc(TEXT.closeDialog) + '">' +
      ICO_X + '</button></div>' +
      '<div class="ps-choices" role="group" aria-label="' + esc(TEXT.presume) + '">' +
      CHOICES.map(v => '<button class="ps-choice" type="button" data-choice="' + v + '" aria-pressed="false"><b></b><span></span></button>').join('') +
      '</div>' +
      '<div class="ps-body"><figure class="ps-preview"><canvas id="ps-canvas" width="1200" height="630" role="img" aria-label="' +
      esc(TEXT.previewLabel) + '"></canvas></figure>' +
      '<div class="ps-side"><label class="ps-field"><span>' + esc(TEXT.nameField) + '</span>' +
      '<input id="share-name" type="text" maxlength="' + ShareCodec.MAX_CHARS + '" autocomplete="off" spellcheck="false" placeholder="' +
      esc(TEXT.shareNamePh) + '"></label>' +
      '<button class="btn" type="button" id="share-link">' + (mobile ? ICO_SHARE : ICO_COPY) + '<span></span></button>' +
      (mobile && canShareFiles() ? '<button class="btn ghost" type="button" id="share-native">' + ICO_SHARE + '<span>' +
        esc(TEXT.nativeShare) + '</span></button>' : '') +
      '<button class="btn ghost" type="button" id="share-img">' + ICO_IMG + '<span>' + esc(TEXT.download) + '</span></button>' +
      '<p id="share-msg" class="muted small" role="status" aria-live="polite"></p></div></div>';
    document.body.appendChild(dlg);
    dlg.addEventListener('click', e => {
      if (e.target === dlg || e.target.closest('[data-close]')) { dlg.close(); return; }
      const choice = e.target.closest('[data-choice]');
      if (choice) setChoice(choice.dataset.choice);
    });
    $('#share-name', dlg).addEventListener('input', () => {
      shareNameOwn = $('#share-name').value;
      clearTimeout(previewTimer);
      previewTimer = setTimeout(renderPreview, 150);
    });
    $('#share-name', dlg).addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); $('#share-link').click(); }
    });
    $('#share-link', dlg).addEventListener('click', shareLink);
    $('#share-img', dlg).addEventListener('click', shareImage);
    const native = $('#share-native', dlg);
    if (native) native.addEventListener('click', shareNativeImage);
  }

  function openPresume() {
    if (!viewing) return;
    mountPresume();
    const dlg = $('#presume');
    const input = $('#share-name');
    input.readOnly = !!viewing.opts.guest;
    input.value = viewing.opts.guest ? (viewing.opts.shareName || '') : shareNameOwn;
    $('#share-msg').textContent = '';
    setChoice(state.view);
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
    $('[data-choice][aria-pressed="true"]', dlg).focus();
  }

  function themeColors() {
    const s = getComputedStyle(document.documentElement);
    const g = name => s.getPropertyValue(name).trim();
    const tier = {};
    TIERS.forEach(t => { tier[t] = g('--tier-' + t); });
    const rar = {};
    [1, 2, 3, 4, 5].forEach(r => { rar[r] = g('--rar-' + r); });
    return { bg: g('--bg'), ink: g('--ink'), ink2: g('--ink-2'), accent: g('--accent'), on: g('--on-accent'),
      soft: g('--rule-soft'), tierInk: g('--tier-ink'), tier, rar };
  }

  function fitText(ctx, text, max, size, weight, family) {
    let s = size;
    while (s > 18) {
      ctx.font = weight + ' ' + s + 'px ' + family;
      if (ctx.measureText(text).width <= max) return s;
      s -= 2;
    }
    return s;
  }

  function sparkle(ctx, x, y, color, px = 2) {
    ctx.fillStyle = color;
    const rows = ['000010000', '000111000', '001111100', '111111111', '011111110', '001111100', '011000110', '110000011'];
    rows.forEach((row, dy) => {
      for (let dx = 0; dx < row.length; dx++) if (row[dx] === '1') ctx.fillRect(x + dx * px, y + dy * px, px, px);
    });
  }

  // El canvas dibuja con la fuente que haya en ese momento y no avisa si falta: se espera a cada peso y se comprueba.
  function loadZen() {
    if (!zenReady) {
      zenReady = Promise.all(CARD_FONTS.map(f => document.fonts.load(f))).then(lists => {
        if (lists.some(list => !list.length) || !CARD_FONTS.every(f => document.fonts.check(f))) throw new Error('fonts');
      }).catch(e => {
        zenReady = null;
        throw e;
      });
    }
    return zenReady;
  }

  function loadSprite(dex, shiny) {
    return new Promise(resolve => {
      const img = new Image();
      const src = sprites + (shiny ? 'shiny/' : '') + dex + spriteExt;
      let absolute = null;
      try { absolute = new URL(src, location.href); } catch (e) { absolute = null; }
      if (absolute && absolute.origin !== location.origin) img.crossOrigin = 'anonymous';
      img.onload = () => resolve(img.naturalWidth ? img : null);
      img.onerror = () => resolve(null);
      img.src = src;
    });
  }

  function showcase(c) {
    const owned = new Set(c.dex);
    return state.mons.filter(p => owned.has(p.dex)).sort(Collection.showOrder).slice(0, 6);
  }

  function legendPicks(c) {
    const owned = new Set(c.dex);
    return state.mons.filter(p => p.legendary && owned.has(p.dex)).sort(Collection.showOrder).slice(0, 6);
  }

  function paintFrame(ctx, colors, kicker) {
    const W = CARD_W, H = CARD_H;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = colors.ink;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = colors.bg;
    ctx.fillRect(10, 10, W - 20, H - 20);
    ctx.fillStyle = colors.accent;
    ctx.fillRect(10, 10, W - 20, 8);
    ctx.save();
    ctx.beginPath();
    ctx.rect(18, 26, W - 36, H - 44);
    ctx.clip();
    ctx.globalAlpha = 0.055;
    ctx.strokeStyle = colors.ink;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = 24; x < W; x += 24) { ctx.moveTo(x + 0.5, 26); ctx.lineTo(x + 0.5, H); }
    for (let y = 32; y < H; y += 24) { ctx.moveTo(18, y + 0.5); ctx.lineTo(W, y + 0.5); }
    ctx.stroke();
    ctx.restore();

    ctx.textBaseline = 'top';
    ctx.textAlign = 'left';
    ctx.font = '700 52px ' + CARD_PIX;
    ctx.fillStyle = colors.accent;
    ctx.fillText('Survivor', CARD_LEFT, 40);
    ctx.fillStyle = colors.ink;
    ctx.fillText('Tiers', CARD_LEFT + ctx.measureText('Survivor').width, 40);
    ctx.font = '700 22px ' + CARD_UI;
    ctx.letterSpacing = '3px';
    ctx.fillStyle = colors.ink2;
    ctx.textAlign = 'right';
    ctx.fillText(kicker.toUpperCase(), W - 48, 52);
    ctx.letterSpacing = '0px';
    ctx.textAlign = 'left';
  }

  // Zen no trae cifras tabulares: cada dígito ocupa el ancho del más ancho, así el 1 no se pega al 8.
  function digitCell(ctx) {
    let w = 0;
    for (let d = 0; d <= 9; d++) w = Math.max(w, ctx.measureText(String(d)).width);
    return Math.ceil(w);
  }

  function numWidth(ctx, text) {
    const cell = digitCell(ctx);
    let w = 0;
    for (const ch of text) w += /\d/.test(ch) ? cell : ctx.measureText(ch).width;
    return w;
  }

  function drawNum(ctx, text, x, y) {
    const cell = digitCell(ctx);
    let cx = x;
    for (const ch of text) {
      const cw = ctx.measureText(ch).width;
      if (/\d/.test(ch)) {
        ctx.fillText(ch, Math.round(cx + (cell - cw) / 2), y);
        cx += cell;
      } else {
        ctx.fillText(ch, Math.round(cx), y);
        cx += cw;
      }
    }
  }

  function paintName(ctx, colors, name, y) {
    if (!name) return y;
    const size = fitText(ctx, name, 680, 34, '700', CARD_UI);
    ctx.font = '700 ' + size + 'px ' + CARD_UI;
    ctx.fillStyle = colors.ink;
    ctx.fillText(name, CARD_LEFT, y);
    return y + size + 14;
  }

  function paintCollectionStats(ctx, colors, info, y) {
    ctx.font = '700 84px ' + CARD_UI;
    ctx.fillStyle = colors.ink;
    const num = String(info.known);
    drawNum(ctx, num, CARD_LEFT, y);
    const totalX = Math.round(CARD_LEFT + numWidth(ctx, num) + 16);
    ctx.font = '400 30px ' + CARD_UI;
    ctx.fillStyle = colors.ink2;
    drawNum(ctx, '/ ' + info.total, totalX, y + 48);
    const labelY = y + 92;
    ctx.font = '400 20px ' + CARD_UI;
    ctx.fillStyle = colors.ink2;
    ctx.fillText(TEXT.dexStat(), CARD_LEFT, labelY);
    const hunterX = 500;
    sparkle(ctx, hunterX, y + 36, colors.accent);
    ctx.font = '700 42px ' + CARD_UI;
    ctx.fillStyle = colors.ink;
    drawNum(ctx, String(info.hunted), hunterX + 28, y + 26);
    ctx.font = '400 18px ' + CARD_UI;
    ctx.fillStyle = colors.ink2;
    ctx.fillText(info.hunterLabel, hunterX + 28, y + 78);
    if (info.sub) ctx.fillText(info.sub, hunterX + 28, y + 102);
    y = labelY + 44;
    info.rows.forEach(r => {
      ctx.fillStyle = r.color;
      ctx.fillRect(CARD_LEFT, y, 36, 36);
      ctx.fillStyle = colors.tierInk;
      ctx.font = (r.label.length > 1 ? '700 17px ' : '700 22px ') + CARD_UI;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(r.label, CARD_LEFT + 18, y + 19);
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      const barX = CARD_LEFT + 48, barW = 400, barY = y + 11;
      ctx.fillStyle = colors.soft;
      ctx.fillRect(barX, barY, barW, 14);
      const fill = r.n ? Math.round(barW * r.have / r.n) : 0;
      ctx.fillStyle = r.color;
      for (let i = 0; i < fill; i += 8) ctx.fillRect(barX + i, barY, Math.min(6, fill - i), 14);
      ctx.font = '700 20px ' + CARD_UI;
      ctx.fillStyle = colors.ink;
      drawNum(ctx, TEXT.haveOf(r.have, r.n), barX + barW + 14, y + 8);
      y += 46;
    });
  }

  function paintHunterStats(ctx, colors, info, y) {
    ctx.textBaseline = 'top';
    ctx.textAlign = 'left';
    ctx.font = '700 96px ' + CARD_UI;
    ctx.fillStyle = colors.ink;
    const num = String(info.hunted);
    drawNum(ctx, num, CARD_LEFT, y);
    sparkle(ctx, CARD_LEFT + numWidth(ctx, num) + 26, y + 14, colors.accent, 4);
    ctx.font = '400 22px ' + CARD_UI;
    ctx.fillStyle = colors.ink2;
    ctx.fillText(info.hunterLabel, CARD_LEFT, y + 116);
    if (info.facts) {
      ctx.fillStyle = colors.ink;
      ctx.fillText(info.facts, CARD_LEFT, y + 150);
    }
    const barY = y + 232, total = info.dex.total || 1;
    ctx.font = '700 20px ' + CARD_UI;
    ctx.letterSpacing = '2px';
    ctx.fillStyle = colors.ink2;
    ctx.fillText(TEXT.shinydex.toUpperCase(), CARD_LEFT, barY);
    ctx.letterSpacing = '0px';
    const count = info.dex.have + ' / ' + info.dex.total;
    ctx.font = '700 22px ' + CARD_UI;
    ctx.fillStyle = colors.ink;
    drawNum(ctx, count, Math.round(CARD_LEFT + CARD_BAR_W - numWidth(ctx, count)), barY);
    ctx.fillStyle = colors.soft;
    ctx.fillRect(CARD_LEFT, barY + 34, CARD_BAR_W, 16);
    ctx.fillStyle = colors.accent;
    ctx.fillRect(CARD_LEFT, barY + 34, Math.round(CARD_BAR_W * info.dex.have / total), 16);
  }

  function paintLegendStats(ctx, colors, info, y) {
    ctx.font = '700 84px ' + CARD_UI;
    ctx.fillStyle = colors.ink;
    const num = String(info.have);
    drawNum(ctx, num, CARD_LEFT, y);
    const totalX = Math.round(CARD_LEFT + numWidth(ctx, num) + 16);
    ctx.font = '400 30px ' + CARD_UI;
    ctx.fillStyle = colors.ink2;
    drawNum(ctx, '/ ' + info.total, totalX, y + 48);
    ctx.font = '400 20px ' + CARD_UI;
    ctx.fillText(info.label, CARD_LEFT, y + 92);
    ctx.fillStyle = colors.soft;
    ctx.fillRect(CARD_LEFT, y + 140, CARD_BAR_W, 16);
    ctx.fillStyle = colors.accent;
    ctx.fillRect(CARD_LEFT, y + 140, Math.round(CARD_BAR_W * info.have / info.total), 16);
    if (info.shinies) {
      ctx.font = '700 20px ' + CARD_UI;
      ctx.fillStyle = colors.ink;
      ctx.fillText(TEXT.legendShiny(info.shinies), CARD_LEFT, y + 176);
    }
  }

  // Todos los legendarios en rejilla: los que tienes a color, los que no, apagados; el shiny lleva un punto.
  function paintLegendGrid(ctx, colors, grid, y) {
    const cell = 42, gap = 6, cols = 22;
    grid.forEach((item, i) => {
      const x = CARD_LEFT + (i % cols) * (cell + gap);
      const cy = y + Math.floor(i / cols) * (cell + gap);
      if (item.owned) {
        ctx.fillStyle = colors.soft;
        ctx.fillRect(x, cy, cell, cell);
      }
      if (item.img) {
        const box = cell - 6;
        const scale = Math.min(box / item.img.width, box / item.img.height);
        const w = Math.max(1, Math.round(item.img.width * scale));
        const h = Math.max(1, Math.round(item.img.height * scale));
        ctx.globalAlpha = item.owned ? 1 : 0.16;
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(item.img, Math.round(x + (cell - w) / 2), Math.round(cy + (cell - h) / 2), w, h);
        ctx.imageSmoothingEnabled = true;
        ctx.globalAlpha = 1;
      }
      if (item.shiny) {
        ctx.fillStyle = colors.accent;
        ctx.fillRect(x + cell - 7, cy + 2, 5, 5);
      }
    });
  }

  function paintSprites(ctx, colors, images, big) {
    if (!images.length) return;
    const cell = big ? 150 : 116, gap = 14;
    const cols = images.length > 3 ? 3 : images.length;
    const gridW = cols * cell + (cols - 1) * gap;
    const originX = CARD_W - 48 - gridW;
    images.forEach((item, i) => {
      const x = originX + (i % cols) * (cell + gap);
      const sy = 128 + Math.floor(i / cols) * (cell + gap);
      ctx.fillStyle = item.color;
      ctx.fillRect(x, sy, cell, cell);
      ctx.fillStyle = colors.bg;
      ctx.fillRect(x + 5, sy + 5, cell - 10, cell - 10);
      if (!item.img) return;
      const box = cell - 20;
      const scale = Math.min(box / item.img.width, box / item.img.height);
      const w = Math.max(1, Math.round(item.img.width * scale));
      const h = Math.max(1, Math.round(item.img.height * scale));
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(item.img, Math.round(x + (cell - w) / 2), Math.round(sy + (cell - h) / 2), w, h);
      ctx.imageSmoothingEnabled = true;
    });
  }

  function paintCard(ctx, colors, info, images) {
    paintFrame(ctx, colors, info.kicker);
    const y = paintName(ctx, colors, info.name, 118);
    if (info.mode === 'shiny') paintHunterStats(ctx, colors, info, y);
    else if (info.mode === 'legend') paintLegendStats(ctx, colors, info, y);
    else paintCollectionStats(ctx, colors, info, y);
    paintSprites(ctx, colors, images, info.mode === 'shiny');
    if (info.grid) paintLegendGrid(ctx, colors, info.grid, 390);
    ctx.font = '400 16px "Zen Kaku Gothic New", sans-serif';
    ctx.fillStyle = colors.ink2;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';
    ctx.fillText(TEXT.siteHost, CARD_LEFT, CARD_H - 28);
  }

  function shinyPicks(c) {
    return Collection.shinyRows(c).map(r => state.byDex.get(r.dex)).filter(Boolean).slice(0, 6);
  }

  async function buildShareCanvas(c, shareName, view) {
    await loadZen();
    const colors = themeColors();
    const shiny = view === 'shiny';
    const legend = view === 'legend';
    const owned = new Set(c.dex);
    const picks = shiny ? shinyPicks(c) : legend ? legendPicks(c) : showcase(c);
    const loaded = await Promise.all(picks.map(p => loadSprite(p.dex, shiny)));
    const images = picks.map((p, i) => ({ color: shiny ? colors.accent : colors.rar[p.rarity], img: loaded[i] })).filter(item => item.img);
    const k = hunterCounts(c);
    const name = ShareCodec.cleanName(shareName);
    let info;
    if (shiny) {
      info = { mode: 'shiny', kicker: TEXT.shinyHunter, name: name, hunted: k.hunted,
        hunterLabel: k.legacy ? TEXT.shinyTotal : TEXT.hunted, facts: hunterFacts(k), dex: shinyDexCount(c) };
    } else if (legend) {
      const legends = state.mons.filter(p => p.legendary).sort(Collection.showOrder);
      const shinySet = new Set(c.shiny);
      const have = legends.filter(p => owned.has(p.dex));
      const imgs = await Promise.all(legends.map(p => loadSprite(p.dex, false)));
      info = { mode: 'legend', kicker: TEXT.legendWord, name: name, have: have.length, total: legends.length,
        shinies: have.filter(p => shinySet.has(p.dex)).length, label: TEXT.legendLabel,
        grid: legends.map((p, i) => ({ img: imgs[i], owned: owned.has(p.dex), shiny: shinySet.has(p.dex) })) };
    } else {
      const by = state.breakBy;
      info = { mode: 'collection', kicker: TEXT.collectionWord, name: name, known: state.mons.filter(p => owned.has(p.dex)).length,
        total: state.mons.length, hunted: k.hunted, hunterLabel: k.legacy ? TEXT.shinyStat : TEXT.hunted,
        sub: k.gacha ? TEXT.gachaCount(k.gacha) : '',
        rows: breakRows(owned, by).map(r => ({ label: by === 'tier' ? r.key : r.key + '★',
          color: by === 'tier' ? colors.tier[r.key] : colors.rar[r.key], have: r.have, n: r.n })) };
    }
    const canvas = document.createElement('canvas');
    canvas.width = CARD_W;
    canvas.height = CARD_H;
    paintCard(canvas.getContext('2d'), colors, info, images);
    return canvas;
  }

  function initCollection() {
    const area = $('#import-area'), drop = $('#drop'), fileIn = $('#file');
    // Con una colección importada, el paso a paso y el área de pegado se ocultan; «Reimportar» (en la fila guardada) los vuelve.
    const showImport = on => { area.hidden = !on; };
    const paintOwn = (c, stored) => {
      viewing = { c: c, opts: {} };
      renderCollection(c, viewing.opts);
      renderSaved(stored === false ? 'failed' : 'own');
      showImport(false);
    };
    const showView = () => {
      syncLangHash();
      if (pendingOwn && !location.hash.startsWith('#c=')) {
        const job = pendingOwn;
        pendingOwn = null;
        paintOwn(job.c, job.stored);
        return;
      }
      pendingOwn = null;
      if (location.hash.startsWith('#c=')) {
        const decoded = hashCollection();
        area.hidden = true;
        if (!decoded) {
          viewing = null;
          showError(TEXT.badLink);
          renderSaved('broken');
          return;
        }
        const c = Collection.fromLink(decoded);
        viewing = { c: c, opts: { guest: true, shareName: decoded.name } };
        state.view = decoded.view;
        renderCollection(c, viewing.opts);
        renderSaved('guest');
        return;
      }
      const saved = readSaved();
      if (saved) paintOwn(saved.c, true);
      else {
        viewing = null;
        $('#result').innerHTML = '';
        renderSaved('none');
        showImport(true);
      }
    };
    window.addEventListener('hashchange', showView);
    $('#result').addEventListener('click', e => {
      const t = e.target.closest('[data-view], [data-sh-filter], [data-sh-sort], [data-break]');
      if (!t || !viewing) return;
      if (t.dataset.break) {
        if (state.breakBy === t.dataset.break) return;
        state.breakBy = t.dataset.break;
        renderCollection(viewing.c, viewing.opts);
        $('[data-break="' + state.breakBy + '"]').focus();
        return;
      }
      if (t.dataset.view) {
        if (state.view === t.dataset.view) return;
        state.view = t.dataset.view;
        renderCollection(viewing.c, viewing.opts);
        $('[data-view="' + state.view + '"]').focus();
        return;
      }
      if (t.dataset.shFilter) {
        state.wildOnly = t.dataset.shFilter === 'wild';
        $$('[data-sh-filter]').forEach(b => b.setAttribute('aria-pressed', String(b === t)));
      } else {
        state.shinySort = t.dataset.shSort;
        $$('[data-sh-sort]').forEach(b => b.setAttribute('aria-pressed', String(b === t)));
      }
      paintShinyGrid(viewing.c, viewing.opts.guest);
    });
    $('#saved').addEventListener('click', e => {
      const btn = e.target.closest('button');
      if (!btn) return;
      if (btn.id === 'forget') {
        clearSaved();
        viewing = null;
        $('#result').innerHTML = '';
        renderSaved('forgot');
        showImport(true);
      } else if (btn.id === 'reimport') {
        showImport(true);
        area.scrollIntoView({ block: 'start' });
      } else if (btn.id === 'presume-open') {
        openPresume();
      } else if (btn.id === 'back-own') {
        location.hash = '';
      }
    });
    const run = text => {
      const r = Collection.parse(text);
      if (!r.ok) { showError(TEXT[r.reason]); return; }
      const stored = writeSaved(r.c);
      if (location.hash) {
        pendingOwn = { c: r.c, stored: stored };
        location.hash = '';
      } else paintOwn(r.c, stored);
    };
    const loadFile = f => {
      if (f.size > 2e6) { showError(TEXT.tooBig); return; }
      f.text().then(t => { $('#paste').value = t; run(t); });
    };
    $('#import').addEventListener('click', () => {
      const t = $('#paste').value;
      if (!t.trim()) { showError(TEXT.pasteFirst); return; }
      run(t);
    });
    fileIn.addEventListener('change', e => {
      const f = e.target.files[0];
      if (f) loadFile(f);
      fileIn.value = '';   // así se puede volver a elegir el mismo archivo
    });
    // Arrastrar el .json a la zona: la resaltamos mientras está encima.
    ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => {
      e.preventDefault();
      drop.classList.add('over');
    }));
    drop.addEventListener('dragleave', e => { if (!drop.contains(e.relatedTarget)) drop.classList.remove('over'); });
    drop.addEventListener('drop', e => {
      e.preventDefault();
      drop.classList.remove('over');
      const f = e.dataTransfer.files[0];
      if (f) loadFile(f);
    });
    $('#copy-snippet').addEventListener('click', () => {
      const text = $('#snippet').textContent;
      const msg = $('#copy-msg');
      const done = ok => { msg.textContent = ok ? TEXT.copied : TEXT.copyFail; };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(() => done(true), () => done(false));
      else done(false);
    });
    showView();
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
        ctx.fillStyle = color.ink; ctx.font = '600 15px "Zen Kaku Gothic New", system-ui, sans-serif'; ctx.textAlign = 'center';
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
    document.addEventListener('themechange', () => { readColors(); draw(); });
    document.fonts.ready.then(draw);
    reset();
    if (REDUCED) { for (let i = 0; i < 80; i++) update(0.05); draw(); } else draw();
    btn.addEventListener('click', () => set(!running));
    sprite.addEventListener('load', draw);
    new IntersectionObserver(es => { visible = es[0].isIntersecting; kick(); }, { threshold: 0.1 }).observe(cv);
    document.addEventListener('visibilitychange', kick);
    set(!REDUCED);
  }

  // ---------------------------------------------------------------- tema claro u oscuro
  // El script de <head> (build/theme.py) ya ha puesto data-theme si hay elección guardada. Aquí solo se muestra el botón,
  // se guarda la elección y se avisa a los gráficos con «themechange». Sin elección, manda el sistema.
  const THEME_KEY = 'survivortiers.tema';
  const darkQuery = matchMedia('(prefers-color-scheme: dark)');
  const isDark = () => (html.dataset.theme ? html.dataset.theme === 'dark' : darkQuery.matches);

  function syncTheme() {
    const meta = $('#theme-color');
    if (meta) meta.content = getComputedStyle(html).getPropertyValue('--bg').trim();
    const btn = $('#theme');
    if (!btn) return;
    const label = isDark() ? btn.dataset.toLight : btn.dataset.toDark;
    btn.setAttribute('aria-label', label);
    btn.title = label;
  }

  function applyTheme() {
    syncTheme();
    document.dispatchEvent(new CustomEvent('themechange'));
  }

  function initTheme() {
    const btn = $('#theme');
    if (!btn) return;
    btn.hidden = false;
    btn.addEventListener('click', () => {
      html.dataset.theme = isDark() ? 'light' : 'dark';
      try { localStorage.setItem(THEME_KEY, html.dataset.theme); } catch (e) { /* sin almacenamiento: vale para esta visita */ }
      applyTheme();
    });
    darkQuery.addEventListener('change', () => { if (!html.dataset.theme) applyTheme(); });
    syncTheme();
  }

  // En móvil el menú es una tira deslizable: se desplaza solo la tira para que la página activa quede centrada.
  function centerNav() {
    const nav = $('.nav');
    const cur = nav && $('a[aria-current="page"]', nav);
    if (!cur || nav.scrollWidth <= nav.clientWidth) return;
    const r = cur.getBoundingClientRect(), n = nav.getBoundingClientRect();
    nav.scrollLeft += r.left - n.left - (n.width - r.width) / 2;
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
  // Los enlaces antiguos /pokemon/25.html caen en la 404. Esta página los manda a ?id=, y ficha.js sigue hasta la URL estática.
  if (page === '404') {
    const old = location.pathname.match(/^(\/en)?\/pokemon\/(\d+)(?:\.html)?\/?$/);
    if (old) { location.replace((old[1] || '') + '/pokemon/?id=' + old[2]); return; }
  }
  initTheme();
  centerNav();
  initReveal();
  initDemo();
  initReps();
  initWalk();
  initArena();
  // Ataques: el buscador filtra las tarjetas por nombre o tipo y oculta los grupos y secciones que quedan vacíos.
  function initMoves() {
    const q = $('#mv-q');
    if (!q) return;
    const cards = $$('.mv-card');
    const none = $('#mv-none');
    const visible = el => $$('.mv-card', el).some(c => !c.hidden);
    q.addEventListener('input', () => {
      const s = q.value.trim().toLowerCase();
      cards.forEach(c => { c.hidden = !!s && !c.dataset.q.includes(s); });
      $$('.mv-tier').forEach(g => { g.hidden = !visible(g); });
      $$('.mv-section').forEach(sec => { sec.hidden = !visible(sec); });
      none.hidden = cards.some(c => !c.hidden);
    });
  }
  if (page === 'ataques') initMoves();

  if (page === 'index' || page === 'coleccion' || page === 'gachas') {
    getJSON('pokemon-index.json').then(mons => {
      state.mons = mons; indexMons(mons);
      if (page === 'index') initTierList();
      else if (page === 'coleccion') initCollection();
      else initGachaProgress();
    }).catch(err => {
      const el = $('#result') || $('#count');
      if (el) el.textContent = TEXT.loadFailAll(err.message);
    });
  }
})();
