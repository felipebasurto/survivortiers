/* Exporta los iconos del juego tal y como los dibuja (ui/icons.js), a dos ficheros:
 *   data/move_icons.json  movimientos: emblema del tipo + insignia de la familia.
 *   data/item_icons.json  objetos equipables: el dibujo de G.Icons.UI con el id del objeto.
 *   data/ball_icons.json  las Poké Ball de rareza (G.Icons.RARITY_BALL): de Común a Master.
 * Se ejecuta una vez, cuando cambia el juego:
 *
 *   node build/export_move_icons.js /ruta/a/pokesurvivor/repo/js
 *
 * No hace falta navegador: el canvas es un mínimo que pinta píxeles y lee sus datos, lo que usa icons.js. */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const GAME = path.resolve(process.argv[2] || '/Users/felipe/Downloads/pokesurvivor/repo/js');
const OUT = path.join(__dirname, '..', 'data', 'move_icons.json');
const OUT_ITEMS = path.join(__dirname, '..', 'data', 'item_icons.json');
const OUT_BALLS = path.join(__dirname, '..', 'data', 'ball_icons.json');

// ---- canvas mínimo: fillRect con colores #rrggbb, getImageData y las propiedades que usa icons.js.
class Canvas {
  constructor() { this.width = 300; this.height = 150; this.buf = null; }
  getContext() {
    if (!this.buf) this.buf = new Uint8ClampedArray(this.width * this.height * 4);
    const cv = this;
    const ctx = {
      fillStyle: '#000000',
      fillRect(x, y, w, h) {
        const n = parseInt(this.fillStyle.slice(1), 16);
        const r = n >> 16 & 255, g = n >> 8 & 255, b = n & 255;
        for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
          const px = x + i, py = y + j;
          if (px < 0 || py < 0 || px >= cv.width || py >= cv.height) continue;
          const k = (py * cv.width + px) * 4;
          cv.buf[k] = r; cv.buf[k + 1] = g; cv.buf[k + 2] = b; cv.buf[k + 3] = 255;
        }
      },
      getImageData(x, y, w, h) { return { data: cv.buf, width: w, height: h }; },
    };
    return ctx;
  }
}
global.document = { createElement: tag => { if (tag !== 'canvas') throw new Error(tag); return new Canvas(); } };

// ---- TYPE_COLOR de core/util.js (sólo ese objeto; util.js arrastra más del juego).
const utilSrc = fs.readFileSync(path.join(GAME, 'core', 'util.js'), 'utf8');
const tc = utilSrc.match(/TYPE_COLOR:\s*(\{[\s\S]*?\n\s{2}\})/);
if (!tc) throw new Error('no encuentro TYPE_COLOR en core/util.js');
const TYPE_COLOR = vm.runInNewContext('(' + tc[1] + ')');

// ---- moves.js y icons.js del juego, en un contexto con G.
const G = { U: { TYPE_COLOR } };
const ctx = vm.createContext({ G, document: global.document, console });
vm.runInContext(fs.readFileSync(path.join(GAME, 'data', 'moves.js'), 'utf8'), ctx, { filename: 'moves.js' });
vm.runInContext(fs.readFileSync(path.join(GAME, 'ui', 'icons.js'), 'utf8'), ctx, { filename: 'icons.js' });
vm.runInContext(fs.readFileSync(path.join(GAME, 'data', 'items.js'), 'utf8'), ctx, { filename: 'items.js' });

// Cada icono como rejilla: rows[y][x] es '.' (transparente) o la letra de su color en pal (a, b, c…).
// El navegador lo pinta como SVG, así el JSON pesa unos pocos KB en vez de los ~10 KB de cada SVG codificado.
const LETTERS = 'abcdefghijklmnopqrstuvwxyz';
function grid(name) {
  let captured = null;
  G.Icons.draw({ imageSmoothingEnabled: true, drawImage(cv) { captured = cv; } }, name, 0, 0, 16);
  const { width: W, height: H, buf } = captured;
  const pal = [];
  const rows = [];
  for (let y = 0; y < H; y++) {
    let row = '';
    for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 4;
      if (!buf[i + 3]) { row += '.'; continue; }
      const hex = '#' + [buf[i], buf[i + 1], buf[i + 2]].map(v => v.toString(16).padStart(2, '0')).join('');
      let k = pal.indexOf(hex);
      if (k < 0) { pal.push(hex); k = pal.length - 1; }
      row += LETTERS[k];
    }
    rows.push(row);
  }
  return { size: [W, H], pal, rows };
}

const out = {};
for (const m of G.Moves.ALL) {
  out[m.id] = { type: m.type, kind: m.kind, ...grid('move:' + m.id) };
}
fs.writeFileSync(OUT, JSON.stringify(out) + '\n', 'utf8');
console.log(`iconos de movimiento: ${Object.keys(out).length} → ${path.relative(process.cwd(), OUT)}`);

// Objetos: G.Icons.draw usa el dibujo de UI con el mismo id; si falta, dibujaría la estrella, así que se exige.
const items = {};
for (const it of G.Items.LIST) {
  if (!G.Icons.UI[it.id]) throw new Error(`el juego no tiene icono para el objeto ${it.id}`);
  items[it.id] = grid(it.id);
}
fs.writeFileSync(OUT_ITEMS, JSON.stringify(items) + '\n', 'utf8');
console.log(`iconos de objeto: ${Object.keys(items).length} → ${path.relative(process.cwd(), OUT_ITEMS)}`);

// Poké Ball de rareza: las cinco que usa la rareza 1 a 5 (ui/icons.js, RARITY_BALL).
const balls = {};
for (const id of Object.values(G.Icons.RARITY_BALL)) {
  if (!G.Icons.UI[id]) throw new Error(`el juego no tiene el dibujo de la ${id}`);
  balls[id] = grid(id);
}
fs.writeFileSync(OUT_BALLS, JSON.stringify(balls) + '\n', 'utf8');
console.log(`poké balls: ${Object.keys(balls).length} → ${path.relative(process.cwd(), OUT_BALLS)}`);
