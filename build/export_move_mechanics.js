/* Exporta cómo se comporta cada movimiento en el juego, a data/move_mechanics.json:
 *   kind     cómo se ejecuta (projectile, beam, chain, aura...), ver el encabezado de data/moves.js
 *   homing   > 0: el proyectil se curva hacia el enemigo más cercano (core/combat: homing)
 *   pierce   > 0: el proyectil atraviesa esos enemigos antes de parar (combat: pierce)
 *   count    en chain: cuántos enemigos golpea, saltando de uno a otro
 * y data/move_pool.json: los movimientos que ofrece cada tipo (G.Moves.POOL).
 * Se ejecuta cuando cambia el juego:
 *
 *   node build/export_move_mechanics.js /ruta/a/pokesurvivor/repo/js
 *
 * Sólo lee data/moves.js en un contexto vacío con G; no hace falta navegador. */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const GAME = path.resolve(process.argv[2] || '/Users/felipe/Downloads/pokesurvivor/repo/js');
const OUT = path.join(__dirname, '..', 'data', 'move_mechanics.json');
const POOL_OUT = path.join(__dirname, '..', 'data', 'move_pool.json');
const TYPES_OUT = path.join(__dirname, '..', 'data', 'type_matrix.json');

// G.U.clamp es la única utilidad de core/util.js que usa types.js; basta esta copia para exportar la tabla.
const G = { U: { clamp: (v, a, b) => Math.min(b, Math.max(a, v)) } };
const ctx = vm.createContext({ G, console });
vm.runInContext(fs.readFileSync(path.join(GAME, 'data', 'moves.js'), 'utf8'), ctx, { filename: 'moves.js' });
vm.runInContext(fs.readFileSync(path.join(GAME, 'data', 'types.js'), 'utf8'), ctx, { filename: 'types.js' });

const out = {};
for (const m of G.Moves.ALL) {
  out[m.id] = { kind: m.kind, homing: m.homing || 0, pierce: m.pierce || 0, count: m.count || 0 };
}
fs.writeFileSync(OUT, JSON.stringify(out, null, 1) + '\n', 'utf8');
console.log(`mecánicas de movimiento: ${Object.keys(out).length} → ${path.relative(process.cwd(), OUT)}`);

// Qué movimientos puede aprender cada tipo (G.Moves.POOL). Un Pokémon ofrece POOL.normal + los de sus tipos.
fs.writeFileSync(POOL_OUT, JSON.stringify(G.Moves.POOL, null, 1) + '\n', 'utf8');
console.log(`pool por tipo: ${Object.keys(G.Moves.POOL).length} tipos → ${path.relative(process.cwd(), POOL_OUT)}`);

// Multiplicador exacto del juego (G.Types.mult) de cada tipo de ataque contra cada tipo o pareja de tipos defensores.
// Clave del defensor: "fire" o "fire,flying" (tipos en orden alfabético). Así no hay que copiar la fórmula.
const ATK = ['normal','fire','water','electric','grass','ice','fighting','poison','ground','flying','psychic','bug','rock','ghost','dragon','dark','steel','fairy'];
const defs = [...ATK.map(t => [t]), ...ATK.flatMap((a, i) => ATK.slice(i + 1).map(b => [a, b]))];
const matrix = {};
for (const a of ATK) {
  matrix[a] = {};
  for (const d of defs) matrix[a][d.slice().sort().join(',')] = +G.Types.mult(a, d).toFixed(4);
}
fs.writeFileSync(TYPES_OUT, JSON.stringify(matrix) + '\n', 'utf8');
console.log(`matriz de tipos: ${ATK.length} ataques × ${defs.length} defensores → ${path.relative(process.cwd(), TYPES_OUT)}`);
