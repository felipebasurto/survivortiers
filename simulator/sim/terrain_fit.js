// Measures how much of the real game map a body of radius r can reach.
// Loads the game's own terrain generator (world.js) read-only from a clone of the game repo.
//   node sim/terrain_fit.js /path/to/pokesurvivor-game [seeds] > sim/out/terrain_fit.csv
// For each radius: fraction of the sampled area reachable from the start clearing, relative to
// the smallest body (r = 10.56). Liquids count as walkable except lava/poison/spark.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const GAME = process.argv[2];
const SEEDS = Number(process.argv[3] || 6);
if (!GAME) throw new Error('usage: node sim/terrain_fit.js <game repo> [seeds]');

const G = {};
const ctx = vm.createContext({ G, window: { G }, console, performance: { now: () => 0 }, Math });
G.Sprites = { PX: 2, hovers: () => false };
for (const f of ['core/util.js', 'world/tiles.js', 'world/world.js']) {
  vm.runInContext(fs.readFileSync(path.join(GAME, 'js', f), 'utf8'), ctx, { filename: f });
}
const W = G.World;

const RADII = [10.56, 14.08, 15.84, 17.6, 19.36, 21.12, 24.64, 28.16, 31.68, 35.2, 42.24, 52];
const HALF = 1600;   // sample a 3200 x 3200 px square (100 x 100 tiles) around the start
const STEP = 4;      // px between sample points
const SIDE = (2 * HALF) / STEP;

function reachable(r) {
  const seen = new Uint8Array(SIDE * SIDE);
  const free = (i, j) => W.isFree(-HALF + i * STEP, -HALF + j * STEP, r, true) && W.walkable(
    Math.floor((-HALF + i * STEP) / 32), Math.floor((-HALF + j * STEP) / 32));
  const start = SIDE / 2;
  const stack = [start * SIDE + start];
  seen[stack[0]] = 1;
  let count = 0;
  while (stack.length) {
    const k = stack.pop();
    count++;
    const i = k % SIDE, j = (k - i) / SIDE;
    for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const a = i + di, b = j + dj;
      if (a < 0 || b < 0 || a >= SIDE || b >= SIDE) continue;
      const q = b * SIDE + a;
      if (seen[q]) continue;
      seen[q] = 1;
      if (free(a, b)) stack.push(q);
    }
  }
  return count;
}

const totals = RADII.map(() => 0);
for (let s = 1; s <= SEEDS; s++) {
  W.reset(s * 7919);
  RADII.forEach((r, k) => { totals[k] += reachable(r); });
}
console.log('radius,reach_rel');
RADII.forEach((r, k) => console.log(`${r},${(totals[k] / totals[0]).toFixed(4)}`));
