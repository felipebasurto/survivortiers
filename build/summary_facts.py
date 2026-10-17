"""Facts behind the ficha summaries: one record per species, from data/ and the simulator, no prose.

    python3 build/summary_facts.py            # writes data/summary_facts.json
    python3 build/summary_facts.py --check    # fails if data/summary_facts.json is stale

Each record has the game stats as percentiles of the 966, the hitbox (game body radius), types and how they
match the enemy pool, the build shown on the ficha (start move, bonded group, alternatives, best item, priority
cards), the tier and rank, and the rank drivers.

Game sources (JPTER78/pokesurvivor at legal.GAME_COMMIT, read only):
  hitbox   js/core/sprites.js:127-131 bodyRadius = clamp(idle width * 0.22, 5, 26) * PX (PX = 2, sprites.js:14);
           js/entities/player.js:17 this.r = bodyRadius(dex); enemy shots hit at p.r + pl.r (js/systems/combat.js:565)
           and bodies touch at e.r + pl.r (combat.js:663). Exported as body_radius in data/pokedex_export.json.
  stats    js/data/pokedex.js (G.DEX hp/spd/atk); player.js:29 maxHp = mon.hp, :31 baseSpd = mon.spd, :32 baseAtk = mon.atk.

Drivers. The published order is a weighted geometric mean of percentiles: sheet 45 (pillars stats 45, moves 25,
type defence 15, size 15), early sim 30 (start move 10, best move 45) and late game 25 (build/make_definitive.py).
For each factor the record holds how many places the species would move if only that factor were at the
population median, everything else fixed, on that same point score:
  hitbox, speed, hp, attack  re-simulated with that stat at the median (simulator/counterfactual_bench.py,
                             results/fixed_group/counterfactuals_g2p2.csv, same seeds and flags as the rank).
                             hitbox also sets the size pillar to the median radius.
  start_move, best_move      that sim median replaced by the median over every start the species can learn
                             (results/fixed_group/g2p2/starter_sweep.csv).
  stats, moves, typedef      that sheet pillar at 0.5.
  late                       both late-game ranks at the middle (483.5).
  gate                       published rank minus the ungated rank, for the species a tier gate held back.
Positive `places` means the factor lifts the species (without it, it would sit lower). Sim figures are estimates.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402
import combos  # noqa: E402
import make_definitive as md  # noqa: E402
import objetos  # noqa: E402
import passives  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SIM = ROOT / "simulator" / "results" / "fixed_group"
OUT = DATA / "summary_facts.json"
CF_CSV = SIM / "counterfactuals_g2p2.csv"
SWEEP_CSV = SIM / "g2p2" / "starter_sweep.csv"
N = 966
PILLAR_W = {"stats": 45, "moves": 25, "typedef": 15, "size": 15}
SIM_STATS = {"r": "hitbox", "spd": "speed", "hp": "hp", "atk": "attack"}
CARD_EN = {"hp": "Vigor", "atk": "Power", "spd": "Sprint", "cd": "Reflexes", "def": "Armor", "rgn": "Synthesis",
           "mag": "Magnet", "xp": "Learning"}


def midpct(values: np.ndarray) -> np.ndarray:
    """Share of the 966 below each value, ties counted half (0 = lowest, 1 = highest)."""
    v = np.asarray(values, dtype=float)
    less = (v[None, :] < v[:, None]).sum(1)
    eq = (v[None, :] == v[:, None]).sum(1)
    return (less + 0.5 * eq) / len(v)


def rank_among(value: float, others: np.ndarray) -> int:
    """1 + how many of the other species score higher."""
    return 1 + int((others > value).sum())


class Model:
    """The published point score (make_definitive.draw without the noise) and single-species counterfactuals."""

    def __init__(self, rows: list[dict], start_s: np.ndarray, best_s: np.ndarray):
        self.rows = rows
        self.start_s, self.best_s = start_s, best_s
        self.pil = np.array([[float(r["pct_" + k]) for k in PILLAR_W] for r in rows])
        self.w = np.array(list(PILLAR_W.values()), dtype=float)
        self.sheet_score = self._sheet(self.pil)
        self.sheet_rank = np.array([int(r["rank_sheet"]) for r in rows], dtype=float)
        self.v4m = np.array([int(r["rank_v4_max"]) for r in rows], dtype=float)
        self.v4f = np.array([int(r["rank_v4_fresh"]) for r in rows], dtype=float)
        self.early_score = self._early_score(md.ranks_of(start_s), md.ranks_of(best_s))
        self.early_rank = md.ranks_of(self.early_score)
        self.late_score = np.exp((2 / 3) * np.log(md.pct(self.v4m)) + (1 / 3) * np.log(md.pct(self.v4f)))
        self.late_rank = md.ranks_of(self.late_score)
        self.point = self._point(self.sheet_rank, self.early_rank, self.late_rank)
        self.point_rank = md.ranks_of(self.point)

    def _sheet(self, pil: np.ndarray) -> np.ndarray:
        return np.exp((np.log(np.maximum(pil, 1e-9)) * self.w).sum(-1) / self.w.sum())

    @staticmethod
    def _early_score(rs, rb):
        return np.exp((10 * np.log(md.pct(rs)) + 45 * np.log(md.pct(rb))) / 55)

    @staticmethod
    def _point(sheet, early, late):
        return np.exp((45 * np.log(md.pct(sheet)) + 30 * np.log(md.pct(early)) + 25 * np.log(md.pct(late))) / 100)

    def counterfactual(self, i: int, start_s=None, best_s=None, pillars: dict | None = None, late=False) -> int:
        """Point rank of species i with only the given pieces changed."""
        others = np.arange(N) != i
        sheet = self.sheet_rank[i]
        if pillars:
            pil = self.pil[i].copy()
            for k, v in pillars.items():
                pil[list(PILLAR_W).index(k)] = v
            mine = rank_among(float(self._sheet(pil)), self.sheet_score[others])
            sheet = sheet + mine - rank_among(float(self.sheet_score[i]), self.sheet_score[others])
        early = self.early_rank[i]
        if start_s is not None or best_s is not None:
            s = self.start_s[i] if start_s is None else start_s
            b = self.best_s[i] if best_s is None else best_s
            rs = rank_among(s, self.start_s[others])
            rb = rank_among(b, self.best_s[others])
            early = rank_among(float(self._early_score(rs, rb)), self.early_score[others])
        lr = self.late_rank[i]
        if late:
            lr = rank_among(float(np.exp(np.log(md.pct(483.5)))), self.late_score[others])
        score = float(self._point(sheet, early, lr))
        return rank_among(score, self.point[others])


def ungated_ranks(rows: list[dict]) -> dict[int, int]:
    """Position of each species before the tier gates, as make_definitive.main orders it."""
    starts = {int(r["dex"]): r for r in md.load_csv(SIM / "g2p2" / "rank_200.csv")}
    sweep = md.load_csv(SWEEP_CSV)
    winners = md.winner_by_dex(sweep)
    sweep_moves = {(int(r["dex"]), r["start"]): r for r in sweep}
    arrays = md.sim_arrays(rows, starts, winners, sweep_moves, False)
    start_s, slo, shi, best_s, blo, bhi, same = arrays[:7]
    sheet = np.array([int(r["rank_sheet"]) for r in rows], dtype=float)
    v4m = np.array([int(r["rank_v4_max"]) for r in rows], dtype=float)
    v4f = np.array([int(r["rank_v4_fresh"]) for r in rows], dtype=float)
    _, _, point, fr = md.draw(start_s, slo, shi, best_s, blo, bhi, same, sheet, v4m, v4f)
    med = np.median(fr, axis=0)
    order = sorted(range(N), key=lambda i: (med[i], -point[i], int(rows[i]["dex"])))
    return {int(rows[i]["dex"]): pos for pos, i in enumerate(order, start=1)}


def load_cf() -> dict[tuple[int, str, str], float]:
    """(dex, move, mod key or '') -> median seconds."""
    if not CF_CSV.exists():
        raise SystemExit(f"falta {CF_CSV.relative_to(ROOT)}; córrelo con simulator/counterfactual_bench.py")
    out = {}
    for r in csv.DictReader(CF_CSV.open(encoding="utf8")):
        key = r["mods"].split("=")[0] if r["mods"] else ""
        out[(int(r["dex"]), r["move"], key)] = float(r["median_s"])
    return out


def r2(x: float) -> float:
    return round(float(x), 3)


def build() -> dict:
    rows = md.load_csv(DATA / "ranking_definitive.csv")
    rows.sort(key=lambda r: int(r["dex"]))
    if len(rows) != N:
        raise SystemExit("ranking_definitive.csv no tiene 966 filas")
    dex_list = [int(r["dex"]) for r in rows]
    px = {p["dex"]: p for p in json.loads((DATA / "pokedex_export.json").read_text(encoding="utf8"))}
    moves = {m["id"]: m for m in catalog.load_moves()}
    cards_es = {k: v["title"] for k, v in json.loads((DATA / "card_icons.json").read_text(encoding="utf8")).items()}
    combo = combos.compute_all({d: px[d]["types"] for d in dex_list}, {int(r["dex"]): r["best_move"] for r in rows})
    psim = passives.load()
    items = objetos.recommended()
    cf = load_cf()
    sweep: dict[int, list[float]] = {}
    for r in md.load_csv(SWEEP_CSV):
        sweep.setdefault(int(r["dex"]), []).append(float(r["median_s"]))

    start_s = np.array([float(r["start_median_s"]) for r in rows])
    best_s = np.array([float(r["best_median_s"]) for r in rows])
    model = Model(rows, start_s, best_s)
    ungated = ungated_ranks(rows)

    game = {k: np.array([px[d][k] for d in dex_list], dtype=float) for k in ("hp", "spd", "atk", "body_radius")}
    pct = {k: midpct(v) for k, v in game.items()}
    pct["body_radius"] = 1 - pct["body_radius"]  # higher = smaller hitbox, like pct_size
    supers = np.array([combo[d]["super"] for d in dex_list], dtype=float)
    pct_super = midpct(supers)
    med = {k: float(statistics.median(v)) for k, v in game.items()}
    med_size = float(np.median([float(r["pct_size"]) for r in rows if px[int(r["dex"])]["body_radius"] == med["body_radius"]]))

    def name(mid: str) -> dict:
        m = moves[mid]
        return {"id": mid, "es": m["name"], "en": m["en"]["name"], "type": m["type"], "kind": m["kind"]}

    records = {}
    for i, r in enumerate(rows):
        d = int(r["dex"])
        p = px[d]
        c = combo[d]
        ids = c["moves"]
        n_boost = c["nBoost"]
        card_ids, n_evo = passives.compute(d, ids, psim)
        start_mv, best_mv = r["start_move"], r["best_move"]
        # Sim counterfactuals: start and best move re-run with one stat at the median.
        drivers = {}
        base_start = cf[(d, start_mv, "")]
        base_best = cf[(d, best_mv, "")]
        if abs(base_start - start_s[i]) > 1e-9 or abs(base_best - best_s[i]) > 1e-9:
            raise SystemExit(f"{d}: la sim de contrafactuales no reproduce el ranking ({base_start} / {start_s[i]}, "
                             f"{base_best} / {best_s[i]})")
        here = model.counterfactual(i)
        for key, factor in SIM_STATS.items():
            s2 = cf.get((d, start_mv, key))
            b2 = cf.get((d, best_mv, key))
            if s2 is None:  # already at the median
                drivers[factor] = {"places": 0, "startS": 0.0, "bestS": 0.0}
                continue
            pil = {"size": med_size} if key == "r" else None
            cfr = model.counterfactual(i, start_s=s2, best_s=b2, pillars=pil)
            drivers[factor] = {"places": int(cfr - here), "startS": r2(base_start - s2), "bestS": r2(base_best - b2)}
        cand = statistics.median(sweep[d])
        drivers["start_move"] = {"places": int(model.counterfactual(i, start_s=cand) - here), "startS": r2(base_start - cand)}
        drivers["best_move"] = {"places": int(model.counterfactual(i, best_s=cand) - here), "bestS": r2(base_best - cand)}
        for k in ("stats", "moves", "typedef"):
            drivers[k] = {"places": int(model.counterfactual(i, pillars={k: 0.5}) - here)}
        drivers["late"] = {"places": int(model.counterfactual(i, late=True) - here)}
        gated = r["stats_capped"] == "1" or r["types_capped"] == "1" or (r["melee_start"] == "1" and ungated[d] <= 30)
        drivers["gate"] = {"places": -(int(r["rank"]) - ungated[d]) if gated else 0}

        records[str(d)] = {
            "dex": d, "name": p["name"], "nameEn": r["name"], "types": p["types"],
            "tier": r["tier"], "rank": int(r["rank"]), "p10": int(r["rank_p10"]), "p90": int(r["rank_p90"]),
            "ungated": ungated[d],
            "stats": {k: {"v": p[k], "pct": r2(pct[k][i])} for k in ("hp", "spd", "atk")},
            "hitbox": {"r": p["body_radius"], "pctSmaller": r2(pct["body_radius"][i]), "median": med["body_radius"]},
            "pillars": {k: float(r["pct_" + k]) for k in PILLAR_W},
            "matchup": {"shotDmgTaken": float(r["shot_dmg_taken"]), "typedefPct": float(r["pct_typedef"]),
                        "superPct": c["super"], "neutralPct": c["neutral"], "superPctile": r2(pct_super[i]),
                        "attackTypes": int(r["attack_types"])},
            "build": {
                "start": name(start_mv), "best": name(best_mv),
                "group": [name(m) for m in ids], "attacks": len(ids) - n_boost,
                "alts": [name(m) for m in c["alts"]],
                "item": {"id": items[0]["id"], "es": items[0]["name"][0], "en": items[0]["name"][1]},
                "cards": [{"id": k, "es": cards_es[k], "en": CARD_EN[k]} for k in card_ids], "evoCards": n_evo,
            },
            "sim": {"startS": float(start_s[i]), "bestS": float(best_s[i]), "medianStartS": float(np.median(start_s))},
            "flags": {"statsCapped": r["stats_capped"] == "1", "typesCapped": r["types_capped"] == "1",
                      "melee": r["melee_start"] == "1"},
            "drivers": drivers,
        }
    return {"note": "Generado por build/summary_facts.py. Sin prosa; build/summaries.py escribe y valida los textos.",
            "medians": {"hp": med["hp"], "spd": med["spd"], "atk": med["atk"], "r": med["body_radius"]},
            "species": records}


def fingerprint(rec: dict) -> str:
    """Hash of the fields a summary can cite, so a stale summary is caught when the build or rank changes."""
    return hashlib.sha1(json.dumps(rec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def dump(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = dump(build())
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf8") != text:
            print(f"{OUT.relative_to(ROOT)} está desactualizado: python3 build/summary_facts.py", file=sys.stderr)
            return 1
        print("summary_facts.json al día")
        return 0
    OUT.write_text(text, encoding="utf8")
    print(f"escrito {OUT.relative_to(ROOT)} ({N} especies)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
