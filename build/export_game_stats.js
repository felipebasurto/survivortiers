/* Exporta a data/game_stats.json lo que las herramientas del sitio (buscador por tipos y planificador de build)
 * leen del juego en un commit concreto:
 *   moves   por movimiento: kind, type, cat ('physical' | 'special' | null para potenciadores), y stat del potenciador
 *   pool    G.Moves.POOL: los movimientos que ofrece cada tipo
 *   dex     por Pokémon: [pa, sa, df, sd] de js/data/pokedex.js (ver tools/fetch_stats.py en el juego)
 *
 *   node build/export_game_stats.js /ruta/al/repo/de/pokesurvivor
 *
 * Lee js/data/moves.js y js/data/pokedex.js en un contexto vacío con G; no hace falta navegador.
 * El commit que escribe es el HEAD del repo que se le pasa. */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { execFileSync } = require('child_process');

const REPO = path.resolve(process.argv[2] || '.');
const JS = path.join(REPO, 'js');
const OUT = path.join(__dirname, '..', 'data', 'game_stats.json');

const english = {};
const G = { U: { clamp: (v, a, b) => Math.min(b, Math.max(a, v)) }, I18n: { add: o => Object.assign(english, o) } };
const ctx = vm.createContext({ G, console });
vm.runInContext(fs.readFileSync(path.join(JS, 'data', 'moves.js'), 'utf8'), ctx, { filename: 'moves.js' });
vm.runInContext(fs.readFileSync(path.join(JS, 'data', 'pokedex.js'), 'utf8'), ctx, { filename: 'pokedex.js' });
vm.runInContext(fs.readFileSync(path.join(JS, 'data', 'lang-en.js'), 'utf8'), ctx, { filename: 'lang-en.js' });

const moves = {};
for (const m of G.Moves.ALL) {
  const entry = { name: m.name, en: english[m.name] || m.name, type: m.type, kind: m.kind, cat: m.cat ?? null };
  if (m.kind === 'buff') entry.buff = { stat: m.stat, amount: m.amount, cd: m.cd, dur: m.dur, stacks: m.stacks };
  moves[m.id] = entry;
}

const dex = {};
for (const p of G.DEX) {
  if (p.pa == null) continue;
  dex[p.dex] = [p.pa, p.sa, p.df, p.sd];
}

const commit = execFileSync('git', ['rev-parse', '--short', 'HEAD'], { cwd: REPO }).toString().trim();
const out = { commit, moves, pool: G.Moves.POOL, dex };
fs.writeFileSync(OUT, JSON.stringify(out, null, 1) + '\n', 'utf8');
console.log(`game_stats: ${Object.keys(moves).length} movimientos, ${Object.keys(dex).length} Pokémon, commit ${commit} -> ${OUT}`);
