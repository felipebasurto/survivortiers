/* SurvivorTiers · ficha. La página de cada Pokémon es estática (build/static_ficha.py). En /pokemon/?id=N no hay
   data-dex: redirige a /pokemon/<n>-<nombre>/ con el mapa #slugs (build/render.py). */
(() => {
  'use strict';
  const html = document.documentElement;
  if (html.dataset.page !== 'ficha') return;
  const root = document.getElementById('ficha');
  if (!root) return;
  if (!Number(root.dataset.dex)) {
    const qid = new URLSearchParams(location.search).get('id');
    const mapEl = document.getElementById('slugs');
    if (!qid || !mapEl) return;
    let slug = '';
    try { slug = JSON.parse(mapEl.textContent)[String(Number(qid))] || ''; } catch (e) { slug = ''; }
    if (slug) location.replace((html.dataset.home || '') + 'pokemon/' + slug + '/' + location.hash);
    return;
  }
  // El cambio de idioma conserva la sección a la que apunta el enlace (#build, #faq...).
  document.querySelectorAll('.lang a[hreflang]:not([aria-current])').forEach(a => {
    a.href = a.getAttribute('href').split('?')[0].split('#')[0] + location.hash;
  });
})();
