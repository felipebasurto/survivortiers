// Map digest from the game's own world.js, to compare with `pokesim mapcheck`.
//   node sim-rs/mapcheck.js <game repo> <seed> [half]
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const [GAME, SEED, HALF = '80'] = process.argv.slice(2);
const G = {};
const ctx = vm.createContext({ G, window: { G }, console, performance: { now: () => 0 }, Math });
G.Sprites = { PX: 2, hovers: () => false };
for (const f of ['core/util.js', 'world/tiles.js', 'world/world.js']) {
  vm.runInContext(fs.readFileSync(path.join(GAME, 'js', f), 'utf8'), ctx, { filename: f });
}
const W = G.World;
W.reset(Number(SEED));
const half = Number(HALF);
const counts = [0, 0, 0];
const kinds = { floor: 0, wall: 1, liquid: 2 };
let props = 0;
let sum = 0n;
const M = 1n << 64n;
for (let ty = -half; ty < half; ty++) {
  for (let tx = -half; tx < half; tx++) {
    const t = kinds[W.kindAt(tx * 32 + 1, ty * 32 + 1)];
    counts[t]++;
    sum = (sum * 31n + BigInt(t)) % M;
    // propAtTile is private: probe a solid prop through projectileBlock at its exact spot.
    const p = W.projectileBlock(tx * 32 + 16, ty * 32 + 28, 0.001);
    if (p && p !== 'wall' && p.tx === tx && p.ty === ty) {
      props++;
      sum = (sum * 31n + BigInt(p.r)) % M;
    }
  }
}
console.log(`floor=${counts[0]} wall=${counts[1]} liquid=${counts[2]} solid_props=${props} sum=${sum}`);
