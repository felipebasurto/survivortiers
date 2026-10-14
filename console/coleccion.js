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
  const salida = { version: 1, name: String(s.name || ''), updated: +s.updated || 0, dex: claves(s.owned), shiny: claves(s.shiny) };
  const texto = JSON.stringify(salida);
  console.log(`Colección de «${salida.name}» (${tipo}): ${salida.dex.length} Pokémon, ${salida.shiny.length} shiny.`);
  const descargar = () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([texto], { type: 'application/json' }));
    a.download = 'coleccion-pokesurvivor.json';
    document.body.appendChild(a); a.click(); a.remove();
    console.log('Se ha descargado coleccion-pokesurvivor.json. Súbelo en la página «Mi colección».');
  };
  const copiado = navigator.clipboard && navigator.clipboard.writeText
    ? navigator.clipboard.writeText(texto).then(() => console.log('JSON copiado al portapapeles. Pégalo en la página «Mi colección».'), descargar)
    : Promise.resolve(descargar());
  copiado.catch(descargar);
  return salida;
})();
