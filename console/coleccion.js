// SurvivorTiers · exporta tu colección de PokéSurvivor. Pégalo en la consola del juego, con la sesión abierta.
// Solo lee localStorage (claves ps.save.<nombre> y ps.cloud.<uid>). No usa G ni hace peticiones de red.
(() => {
  const FUENTES = [['ps.save.', 'partida local'], ['ps.cloud.', 'cuenta (nube)']];
  const claves = n => Object.keys(n || {}).map(Number).filter(Number.isInteger).sort((a, b) => a - b);
  const halladas = [];
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      const f = FUENTES.find(([p]) => k.startsWith(p));
      if (!f) continue;
      try {
        const s = JSON.parse(localStorage.getItem(k));
        if (s && typeof s === 'object' && s.owned && typeof s.owned === 'object') halladas.push({ k, tipo: f[1], s });
      } catch (e) { /* entrada rota: se ignora */ }
    }
  } catch (e) {
    console.warn('No puedo leer localStorage en esta página:', e.message);
    return null;
  }
  if (!halladas.length) {
    console.warn('No hay ninguna partida guardada en este navegador. Si juegas como invitado no se guarda nada: ' +
      'entra con tu cuenta, juega un momento y vuelve a pegar el comando en la consola de esa misma pestaña del juego.');
    return null;
  }
  halladas.sort((a, b) => (+b.s.updated || 0) - (+a.s.updated || 0));
  if (halladas.length > 1) {
    console.table(halladas.map(h => ({ origen: h.tipo, nombre: h.s.name, clave: h.k, pokemon: claves(h.s.owned).length,
      modificada: h.s.updated ? new Date(+h.s.updated).toLocaleString() : '-' })));
  }
  const { s, tipo } = halladas[0];
  // shinyInfo: { «nº»: [origen, día] }. Origen: 0 salvaje, 1 gacha, 2 otro. Día: días desde 1970 (UTC) en que lo consiguió.
  const ORIGEN = { wild: 0, gacha: 1 };
  const shinyInfo = {};
  claves(s.shiny).forEach(n => {
    const e = s.shiny[n];
    const at = +(e && e.at);
    shinyInfo[n] = [ORIGEN[e && e.from] ?? 2, at > 0 ? Math.floor(at / 864e5) : null];
  });
  const salida = { version: 2, name: String(s.name || ''), updated: +s.updated || 0, dex: claves(s.owned), shiny: claves(s.shiny), shinyInfo };
  const salvajes = Object.values(shinyInfo).filter(([o]) => o === 0).length;
  const texto = JSON.stringify(salida);
  console.log(`Colección de «${salida.name}» (${tipo}): ${salida.dex.length} Pokémon, ${salida.shiny.length} shiny (${salvajes} salvajes).`);
  // Al portapapeles con copy() de la consola. Si esa función no existe, el JSON queda impreso para copiarlo a mano.
  if (typeof copy === 'function') {
    copy(texto);
    console.log('JSON copiado al portapapeles. Pégalo en la página «Mi colección».');
  } else {
    console.log('Copia este JSON y pégalo en la página «Mi colección»:\n' + texto);
  }
  return salida;
})();
