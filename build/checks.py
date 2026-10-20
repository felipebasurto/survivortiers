"""Every check, in parallel lanes. Exits 1 if any check fails.

    python3 build/checks.py            # rust, game parity, python, data checks
    python3 build/checks.py --site     # then rebuild the site and run check_site.py against a local server

The lanes are independent, so they run at the same time. Each lane runs its commands one after the
other. Logs go to .cache/checks/ (git-ignored). The site lane runs after the python lane, because
the python tests render the site into site/.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "simulator" / "sim-rs" / "target" / "release" / "pokesim"
LOGS = ROOT / ".cache" / "checks"
PORT = 8765
PY = sys.executable

LANES: dict[str, list[list[str]]] = {
    "rust": [["cargo", "test", "--release", "--manifest-path", "simulator/sim-rs/Cargo.toml"]],
    "parity": [
        ["node", "simulator/validate/game_formulas.js", str(BIN)],
        ["node", "simulator/validate/game_scenarios.js", str(BIN)],
        ["node", "--test", "simulator/v3/game_update.test.js"],
    ],
    "python": [[PY, "-m", "unittest", "discover", "-s", "build", "-p", "test_*.py"]],
    "data": [
        [PY, "build/regen.py", "--check"],
        [PY, "build/facts_export.py", "--check"],
        [PY, "build/summary_pipeline.py", "check"],
    ],
}


def run(name: str, cmd: list[str]) -> tuple[bool, float]:
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{name}.log"
    t0 = time.perf_counter()
    with log.open("a", encoding="utf8") as f:
        f.write(f"$ {' '.join(cmd)}\n")
        f.flush()
        code = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
        f.write(f"[exit {code}]\n")
    return code == 0, time.perf_counter() - t0


def lane(name: str) -> tuple[str, bool, float]:
    ok, total = True, 0.0
    for cmd in LANES[name]:
        good, secs = run(name, cmd)
        total += secs
        if not good:
            ok = False
            break
    return name, ok, total


def site() -> tuple[str, bool, float]:
    env = {**os.environ, "SPRITE_BASE": f"http://127.0.0.1:{PORT}/_sprites/"}
    t0 = time.perf_counter()
    for cmd in ([PY, "build/catalog.py"], [PY, "build/render.py"]):
        code = subprocess.run(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT).returncode
        if code:
            return "site", False, time.perf_counter() - t0
    server = subprocess.Popen([PY, "build/serve.py"], cwd=ROOT, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        import urllib.request
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=2).read(1)
                break
            except OSError:
                time.sleep(1)
        ok, _ = run("site", [PY, "build/check_site.py", f"http://127.0.0.1:{PORT}/"])
    finally:
        server.terminate()
        server.wait(timeout=30)
    return "site", ok, time.perf_counter() - t0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", action="store_true", help="Also rebuild the site and run check_site.py.")
    args = parser.parse_args()
    if not BIN.exists():
        print(f"missing {BIN}: build the engine first (cargo build --release --manifest-path simulator/sim-rs/Cargo.toml)")
        return 2
    results: list[tuple[str, bool, float]] = []
    with ThreadPoolExecutor(max_workers=len(LANES)) as pool:
        futures = [pool.submit(lane, name) for name in LANES]
        results += [f.result() for f in futures]
    if args.site:
        results.append(site())
    width = max(len(name) for name, _, _ in results)
    for name, ok, secs in results:
        print(f"{name:<{width}}  {'PASS' if ok else 'FAIL'}  {secs:8.1f} s   log: {LOGS / (name + '.log')}")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
