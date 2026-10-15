// SurvivorTiers · export your PokéSurvivor collection. Paste it in the game's console with your session open.
// It only reads localStorage (keys ps.save.<name> and ps.cloud.<uid>). It does not use G or make network requests.
(() => {
  const SOURCES = [['ps.save.', 'local save'], ['ps.cloud.', 'account (cloud)']];
  const keysOf = n => Object.keys(n || {}).map(Number).filter(Number.isInteger).sort((a, b) => a - b);
  const found = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      const f = SOURCES.find(([p]) => k.startsWith(p));
      if (!f) continue;
      try {
        const s = JSON.parse(localStorage.getItem(k));
        if (s && typeof s === 'object' && s.owned && typeof s.owned === 'object') found.push({ k, kind: f[1], s });
      } catch (e) { /* broken entry: ignored */ }
    }
  } catch (e) {
    console.warn('Cannot read localStorage on this page:', e.message);
    return null;
  }
  if (!found.length) {
    console.warn('There is no saved game in this browser. Guest mode saves nothing: ' +
      'log in with your account, play for a moment and paste the command again in the console of that same game tab.');
    return null;
  }
  found.sort((a, b) => (+b.s.updated || 0) - (+a.s.updated || 0));
  if (found.length > 1) {
    console.table(found.map(h => ({ source: h.kind, name: h.s.name, key: h.k, pokemon: keysOf(h.s.owned).length,
      modified: h.s.updated ? new Date(+h.s.updated).toLocaleString() : '-' })));
  }
  const { s, kind } = found[0];
  const out = { version: 1, name: String(s.name || ''), updated: +s.updated || 0, dex: keysOf(s.owned), shiny: keysOf(s.shiny) };
  const text = JSON.stringify(out);
  console.log(`Collection of "${out.name}" (${kind}): ${out.dex.length} Pokémon, ${out.shiny.length} shiny.`);
  // Straight to the clipboard with the console's copy(). If that function is missing, the JSON is printed to copy by hand.
  if (typeof copy === 'function') {
    copy(text);
    console.log('JSON copied to the clipboard. Paste it on the "My collection" page.');
  } else {
    console.log('Copy this JSON and paste it on the "My collection" page:\n' + text);
  }
  return out;
})();
