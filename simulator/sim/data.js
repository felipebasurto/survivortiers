const fs = require('fs');
const path = require('path');

let cached = null;

function loadData() {
  if (cached) return cached;
  const file = path.join(__dirname, '..', 'v3', 'v3_data.json');
  const raw = JSON.parse(fs.readFileSync(file, 'utf8'));
  const byDex = new Map();
  for (const mon of raw.dex) byDex.set(mon.dex, mon);
  cached = {
    raw,
    moves: raw.moves,
    tmult: raw.tmult,
    tiers: raw.tiers,
    dex: raw.dex,
    byDex,
  };
  return cached;
}

module.exports = { loadData };
