const { parentPort, workerData } = require('worker_threads');
const { loadData } = require('./data');
const { runSpecies } = require('./rank');

const data = loadData();
for (const dex of workerData.dexes) {
  const mon = data.byDex.get(dex);
  const row = runSpecies(mon, {
    seeds: workerData.seeds,
    seconds: workerData.seconds,
    cards: workerData.cards,
    bot: workerData.bot,
    dt: workerData.dt,
    data,
  });
  parentPort.postMessage(row);
}
parentPort.postMessage({ done: true });
