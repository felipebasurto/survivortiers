"""Facts behind the ficha summaries: one record per species, from data/ and the simulator, no prose.

Standard library only, so build/catalog.py (which runs on the hosting with plain python3) can rebuild these
records and check every summary against today's data. The rank drivers need numpy and live in
build/facts_export.py, which adds them and writes data/facts.parquet.

Each record has the game stats as percentiles of the 966, the hitbox (game body radius), types and how they
match the enemy pool, the build the ficha shows first (its start move, bonded group, best item, priority
cards), the tier and rank, and (from facts_export.py) the rank drivers.

Game sources (JPTER78/pokesurvivor at legal.GAME_COMMIT, read only):
  hitbox   js/core/sprites.js playerRadius: collision radius is min(18, bodyRadius). bodyRadius is
           clamp(idle width * 0.22, 5, 26) * PX (PX = 2). Shots hit at p.r + pl.r and bodies at e.r + pl.r.
           The exported body_radius is the uncapped sprite size; the fact uses the collision cap.
  stats    js/data/pokedex.js:9 (G.DEX, one {dex, hp, spd, atk} per line); player.js:29 maxHp = mon.hp, :31 baseSpd = mon.spd, :32 baseAtk = mon.atk.
"""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import builds  # noqa: E402
import catalog  # noqa: E402
import combos  # noqa: E402
import objetos  # noqa: E402
import passives  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SIM = ROOT / "simulator" / "results" / "fixed_group"
N = 966
PILLARS = ("stats", "moves", "typedef", "size")
CARD_EN = {"hp": "Vigor", "atk": "Power", "spd": "Sprint", "cd": "Reflexes", "def": "Armor", "rgn": "Synthesis",
           "mag": "Magnet", "xp": "Learning"}


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def ranking_rows() -> list[dict]:
    rows = sorted(load_csv(DATA / "ranking_definitive.csv"), key=lambda r: int(r["dex"]))
    if len(rows) != N:
        raise SystemExit("ranking_definitive.csv no tiene 966 filas")
    return rows


def midpct(values: list[float]) -> list[float]:
    """Share of the 966 below each value, ties counted half (0 = lowest, 1 = highest)."""
    s = sorted(values)
    out = []
    for v in values:
        lo, hi = _bisect(s, v, False), _bisect(s, v, True)
        out.append((lo + 0.5 * (hi - lo)) / len(values))
    return out


def _bisect(s: list[float], v: float, right: bool) -> int:
    lo, hi = 0, len(s)
    while lo < hi:
        mid = (lo + hi) // 2
        if s[mid] < v or (right and s[mid] == v):
            lo = mid + 1
        else:
            hi = mid
    return lo


def r2(x: float) -> float:
    return round(float(x), 3)


def base_records() -> dict[str, dict]:
    """Every fact except the rank drivers, keyed by dex as a string."""
    rows = ranking_rows()
    dex_list = [int(r["dex"]) for r in rows]
    px = {p["dex"]: p for p in json.loads((DATA / "pokedex_export.json").read_text(encoding="utf8"))}
    moves = {m["id"]: m for m in catalog.load_moves()}
    # Boosts are in the game and in bonded groups, but the tier list only ranks attacks.
    for m in catalog.load_unranked():
        moves.setdefault(m["id"], m)
    cards_es = {k: v["title"] for k, v in json.loads((DATA / "card_icons.json").read_text(encoding="utf8")).items()}
    build_rows = builds.read_rows()
    lead = builds.lead_builds(build_rows)
    starts = builds.starts()
    types = {d: px[d]["types"] for d in dex_list}
    combo = combos.follow_builds(combos.compute_all(types, {int(r["dex"]): r["best_move"] for r in rows}), lead, types)
    psim = passives.load()
    items = objetos.recommended()

    # sprites.js playerRadius. A body larger than 18 collides at 18, so it is not a bigger target.
    radii = [min(18.0, float(px[d]["body_radius"])) for d in dex_list]
    game = {k: [float(px[d][k]) for d in dex_list] for k in ("hp", "spd", "atk")}
    game["body_radius"] = radii
    pct = {k: midpct(v) for k, v in game.items()}
    pct["body_radius"] = [1 - p for p in pct["body_radius"]]  # higher = smaller hitbox, like pct_size
    pct_super = midpct([float(combo[d]["super"]) for d in dex_list])
    med_r = float(statistics.median(game["body_radius"]))
    start_s = [float(r["start_median_s"]) for r in rows]
    med_start = float(statistics.median(start_s))

    def name(mid: str) -> dict:
        m = moves[mid]
        return {"id": mid, "es": m["name"], "en": m["en"]["name"], "type": m["type"], "kind": m["kind"]}

    out = {}
    for i, r in enumerate(rows):
        d = int(r["dex"])
        p = px[d]
        c = combo[d]
        ids = lead[d]["moves"]
        start = starts[d]
        card_ids, n_evo = passives.compute(d, ids, psim)
        out[str(d)] = {
            "dex": d, "name": p["name"], "nameEn": r["name"], "types": p["types"],
            "tier": r["tier"], "rank": int(r["rank"]), "p10": int(r["rank_p10"]), "p90": int(r["rank_p90"]),
            "stats": {k: {"v": p[k], "pct": r2(pct[k][i])} for k in ("hp", "spd", "atk")},
            "hitbox": {"r": radii[i], "pctSmaller": r2(pct["body_radius"][i]), "median": med_r},
            "pillars": {k: float(r["pct_" + k]) for k in PILLARS},
            "matchup": {"shotDmgTaken": float(r["shot_dmg_taken"]), "typedefPct": float(r["pct_typedef"]),
                        "superPct": c["super"], "neutralPct": c["neutral"], "superPctile": r2(pct_super[i]),
                        "attackTypes": int(r["attack_types"])},
            "build": {
                "start": name(start), "best": name(r["best_move"]),
                "group": [name(m) for m in ids if m != start], "attacks": len(ids) - lead[d]["nBoost"],
                "alts": [],
                "item": {"id": items[0]["id"], "es": items[0]["name"][0], "en": items[0]["name"][1]},
                "cards": [{"id": k, "es": cards_es[k], "en": CARD_EN[k]} for k in card_ids], "evoCards": n_evo,
            },
            "sim": {"startS": start_s[i], "noshopS": float(r["start_noshop_s"]),
                    "bestS": float(r["best_median_s"]), "medianStartS": med_start},
            "flags": {"melee": r["melee_locked"] == "1"},
        }
    return out


def fingerprint(rec: dict) -> str:
    """Hash of a facts record. On the full record (with drivers) it keys the summary cache; on the base record
    it lets catalog.py see that a summary was written for other build data."""
    return hashlib.sha1(json.dumps(rec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def base_of(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k != "drivers"}
