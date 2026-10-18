"""Compare status+Hex groups with the group the site recommends.

Protocol of the published rank: seeds 1-200, 900 s, bot repulse, --group 2+2,
--terrain --status. Every printed median is simulated. The bot does not dodge,
so sustain looks stronger than it is for a player who moves out of hits.

Hex (Infortunio) deals ×1.7 while the target's burn, poison or slow factor is
above 0. Burn lasts 3 s, poison 4 s, slow 1.2 s. A hit that carries the status
always applies it; the move data has no chance roll.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
BIN = ROOT / "sim-rs" / "target" / "release" / "pokesim"
SYNERGY_CSV = ROOT / "results" / "fixed_group" / "synergy_groups.csv"
BASE_CSV = ROOT / "results" / "fixed_group" / "synergy_baselines.csv"
BEST = ROOT / "results" / "fixed_group" / "g2p2" / "rank_best_starter.csv"
RANKING = REPO / "data" / "ranking_definitive.csv"


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def site_groups() -> dict[int, dict]:
    sys.path.insert(0, str(REPO / "build"))
    import combos

    dex = {p["dex"]: p["types"] for p in __import__("json").loads((REPO / "data" / "pokedex_export.json").read_text())}
    with RANKING.open(encoding="utf8") as f:
        best = {int(r["dex"]): r["best_move"] for r in csv.DictReader(line for line in f if not line.startswith("#"))}
    return combos.compute_all(dex, best)


def buff_token(moves: list[str]) -> str:
    buffs = [m for m in moves if m in ("swords-dance", "dragon-dance", "harden", "agility")]
    token = {"swords-dance": "sd", "dragon-dance": "dd", "harden": "hd", "agility": "agi"}
    return ";".join(token[b] for b in buffs)


def attack_lead(moves: list[str]) -> str:
    attacks = [m for m in moves if m not in ("swords-dance", "dragon-dance", "harden", "agility")]
    return "+".join(attacks)


def run_tasks(lines: list[str], out: Path, seeds: int) -> None:
    task = ROOT / "sim" / "out" / "synergy_tasks.txt"
    task.parent.mkdir(parents=True, exist_ok=True)
    task.write_text("\n".join(lines) + "\n", encoding="utf8")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(BIN), "tasks", str(task),
        "--group", "2+2", "--terrain", "--status",
        "--partners", str(ROOT / "results" / "fixed_group" / "solo_sweep.csv"),
        "--seeds", str(seeds), "--seconds", "900", "--out", str(out),
    ]
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> None:
    seeds = 200
    if len(sys.argv) > 1:
        seeds = int(sys.argv[1])
    if not BIN.exists():
        raise SystemExit(f"missing {BIN}")
    groups = site_groups()
    # Species that can pair a status move with Hex are exactly the rows the
    # engine's synergy command emits. Run that first, then the site group for
    # each of those species (the ficha's 2 attacks + 2 buffs).
    subprocess.check_call(
        [str(BIN), "synergy", "--seeds", str(seeds), "--seconds", "900", "--out", str(SYNERGY_CSV)],
        cwd=ROOT,
    )
    syn = load_csv(SYNERGY_CSV)
    species = sorted({int(r["dex"]) for r in syn})
    lines = []
    for dex in species:
        moves = groups[dex]["moves"]
        lines.append(f"{dex},{attack_lead(moves)},none,,{buff_token(moves)}")
    run_tasks(lines, BASE_CSV, seeds)
    base = {int(r["dex"]): r for r in load_csv(BASE_CSV)}
    published = {}
    for r in load_csv(BEST):
        published[int(r["dex"])] = r
    tiers = {}
    for r in load_csv(RANKING):
        tiers[int(r["dex"])] = r

    gains = []
    for dex in species:
        rows = [r for r in syn if int(r["dex"]) == dex]
        best_row = max(rows, key=lambda r: float(r["median_s"]))
        site = base[dex]
        site_med = float(site["median_s"])
        pub = published.get(dex)
        pub_med = float(pub["median_s"]) if pub else None
        gain = float(best_row["median_s"]) - site_med
        gains.append((gain, dex, best_row, site, site_med, pub_med, tiers.get(dex, {}).get("tier", ""), tiers.get(dex, {}).get("name", best_row["name"])))
    gains.sort(key=lambda g: -g[0])
    print(f"species {len(species)}  seeds {seeds}  simulated medians, bot does not dodge")
    print(f"{'dex':>5} {'name':<16} {'tier':<4} {'site_s':>8} {'syn_s':>8} {'gain':>7} {'pub_s':>8}  site group -> synergy group")
    for gain, dex, best_row, site, site_med, pub_med, tier, name in gains[:15]:
        site_g = site["move"].replace("+", " + ")
        print(f"{dex:5} {name:<16} {tier:<4} {site_med:8.3f} {float(best_row['median_s']):8.3f} {gain:+7.3f} {pub_med or 0:8.3f}  {site_g} -> {best_row['group'].replace('+', ' + ')}")
    # Ceruledge detail
    ceru = [r for r in syn if int(r["dex"]) == 937]
    ceru.sort(key=lambda r: -float(r["median_s"]))
    print("\nCeruledge simulated groups (median seconds):")
    site = base[937]
    print(f"  site {site['move']} +{site['buffs']}  {float(site['median_s']):.3f}")
    for r in ceru:
        print(f"  {r['group']}  {float(r['median_s']):.3f}")


if __name__ == "__main__":
    main()
