import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { chromium } from "playwright";

const frames = 3600;
const gameDir = process.env.POKESURVIVOR_DIR;
if (!gameDir) {
  console.error("Set POKESURVIVOR_DIR to the pinned game checkout.");
  process.exit(2);
}

const clock = `(() => {
  window.IntersectionObserver = class {
    constructor(callback) { this.callback = callback; }
    observe(target) { this.callback([{ target, isIntersecting: true }]); }
    unobserve() {}
    disconnect() {}
    takeRecords() { return []; }
  };
  const NativeAudio = window.AudioContext || window.webkitAudioContext;
  let now = 0;
  if (NativeAudio) {
    const SteppedAudio = function (...args) {
      const ctx = new NativeAudio(...args);
      const born = now;
      return new Proxy(ctx, {
        get(target, key) {
          if (key === "currentTime") return Math.max(0, (now - born) / 1000);
          if (key === "state") return "running";
          const value = Reflect.get(target, key, target);
          return typeof value === "function" ? value.bind(target) : value;
        },
        set(target, key, value) {
          target[key] = value;
          return true;
        },
      });
    };
    SteppedAudio.prototype = NativeAudio.prototype;
    window.AudioContext = SteppedAudio;
    window.webkitAudioContext = SteppedAudio;
  }
  const params = new URLSearchParams(location.search);
  let state = Number(params.get("seed") || "1") >>> 0;
  let draws = 0;
  Math.random = () => {
    draws += 1;
    state = (Math.imul(1664525, state) + 1013904223) >>> 0;
    return state / 4294967296;
  };
  const stepMs = 1000 / 60;
  const epoch = 1700000000000;
  const clockNow = () => now;
  Object.defineProperty(performance, "now", { configurable: true, value: clockNow });
  performance.timeOrigin = epoch;
  const RealDate = Date;
  function FixedDate(...args) {
    if (args.length === 0) return new RealDate(epoch + Math.floor(now));
    return new RealDate(...args);
  }
  FixedDate.now = () => epoch + Math.floor(now);
  FixedDate.parse = RealDate.parse;
  FixedDate.UTC = RealDate.UTC;
  FixedDate.prototype = RealDate.prototype;
  window.Date = FixedDate;
  window.__randomDraws = () => draws;
  const queue = [];
  let timer = 1;
  const add = (fn, ms, interval) => {
    const id = timer++;
    queue.push({ id, at: now + Number(ms || 0), fn, interval, ms: Number(ms || 0) });
    return id;
  };
  window.setTimeout = (fn, ms) => add(fn, ms, false);
  window.setInterval = (fn, ms) => add(fn, ms, true);
  const clear = (id) => {
    const index = queue.findIndex((item) => item.id === id);
    if (index >= 0) queue.splice(index, 1);
  };
  window.clearTimeout = clear;
  window.clearInterval = clear;
  let raf = 1;
  const pending = [];
  window.requestAnimationFrame = (fn) => {
    const id = raf++;
    pending.push({ id, fn });
    return id;
  };
  window.cancelAnimationFrame = (id) => {
    const index = pending.findIndex((item) => item.id === id);
    if (index >= 0) pending.splice(index, 1);
  };
  const fire = () => {
    const due = queue.filter((item) => item.at <= now);
    for (const item of due) {
      if (item.interval) item.at = now + item.ms;
      else {
        const index = queue.indexOf(item);
        if (index >= 0) queue.splice(index, 1);
      }
      item.fn();
    }
    const batch = pending.splice(0, pending.length);
    for (const item of batch) item.fn(now);
  };
  window.__stepFrames = (count) => {
    for (let i = 0; i < count; i += 1) {
      now += stepMs;
      fire();
    }
  };
  window.__clockNow = () => now;
})();`;

function contentType(file) {
  if (file.endsWith(".js")) return "text/javascript";
  if (file.endsWith(".css")) return "text/css";
  if (file.endsWith(".html")) return "text/html";
  if (file.endsWith(".json")) return "application/json";
  if (file.endsWith(".png")) return "image/png";
  if (file.endsWith(".webp")) return "image/webp";
  if (file.endsWith(".svg")) return "image/svg+xml";
  if (file.endsWith(".ttf")) return "font/ttf";
  return "application/octet-stream";
}

function serve(root) {
  const base = path.resolve(root);
  const server = http.createServer((req, res) => {
    const url = new URL(req.url || "/", "http://127.0.0.1");
    const rel = decodeURIComponent(url.pathname);
    const file = path.join(base, rel);
    if (file !== base && !file.startsWith(base + path.sep)) {
      res.writeHead(403);
      res.end();
      return;
    }
    fs.readFile(file, (err, buf) => {
      if (err) {
        res.writeHead(404);
        res.end();
        return;
      }
      res.writeHead(200, { "content-type": contentType(file) });
      res.end(buf);
    });
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

async function run(origin, seed) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  await page.addInitScript(clock);
  await page.route("**/*", (route) => {
    const url = route.request().url();
    if (url.startsWith(origin)) route.continue();
    else route.abort();
  });
  const pageErrors = [];
  page.on("pageerror", (err) => pageErrors.push(err.message));
  await page.goto(`${origin}/dev.html?seed=${seed}`, { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForFunction(() => document.getElementById("game") && window.__stepFrames, null, { timeout: 60000 });
  await page.evaluate(async () => {
    const pending = [...document.images].filter((img) => !img.complete);
    await Promise.all(pending.map((img) => img.decode().catch(() => undefined)));
  });
  await page.evaluate((count) => window.__stepFrames(count), frames);
  const png = await page.locator("#game").screenshot();
  const state = await page.evaluate(() => {
    const cam = window.G && window.G.Camera;
    if (!cam) throw new Error("game camera is missing");
    const canvas = document.getElementById("game");
    const data = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
    let hash = 2166136261;
    for (let i = 0; i < data.length; i += 1) {
      hash ^= data[i];
      hash = Math.imul(hash, 16777619);
    }
    return {
      camera: [cam.x, cam.y],
      randomDraws: window.__randomDraws(),
      clock: window.__clockNow(),
      pixels: (hash >>> 0).toString(16),
    };
  });
  await browser.close();
  return {
    screenshotSha256: createHash("sha256").update(png).digest("hex"),
    pageErrors,
    ...state,
  };
}

const gameCommit = execFileSync("git", ["-C", gameDir, "rev-parse", "HEAD"], { encoding: "utf8" }).trim();
const server = await serve(path.resolve(gameDir));
const address = server.address();
const origin = `http://127.0.0.1:${address.port}`;
const first = await run(origin, 1);
const second = await run(origin, 1);
const other = await run(origin, 2);
server.close();
function stateOf(row) {
  return {
    camera: row.camera,
    randomDraws: row.randomDraws,
    clock: row.clock,
    pixels: row.pixels,
  };
}
const sameSeedMatches = JSON.stringify(stateOf(first)) === JSON.stringify(stateOf(second));
const differentSeedDiffers = JSON.stringify(stateOf(first)) !== JSON.stringify(stateOf(other));
const report = {
  gameCommit,
  frames,
  seed1: first,
  seed1Repeat: second,
  seed2: other,
  sameSeedMatches,
  differentSeedDiffers,
  screenshotStable: first.screenshotSha256 === second.screenshotSha256,
};
const pageErrors = [...first.pageErrors, ...second.pageErrors, ...other.pageErrors];
console.log(JSON.stringify(report, null, 2));
if (!sameSeedMatches || !differentSeedDiffers || pageErrors.length) process.exit(1);
