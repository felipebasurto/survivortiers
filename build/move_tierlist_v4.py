"""Tier list de movimientos (data/move_tierlist_v4.csv), sacada del barrido en solitario de la simulación.

Cada fila de simulator/results/fixed_group/solo_screen.csv es un Pokémon que abre la partida con un movimiento;
el cribado mide todos los ataques del catálogo de cada Pokémon. Sin reglas del dueño: todos los ataques cuentan igual.

  score_rel   efecto del movimiento en un modelo de dos factores, log(puntuación) = Pokémon + movimiento,
              ajustado por mínimos cuadrados sobre todas las filas. Así un Pokémon fuerte o un catálogo bueno
              no infla ni hunde a sus movimientos. 1 es el movimiento mediano, 2 dobla la puntuación.
  dps         mediana del daño total entre los segundos que dura la partida.
  survive_s   mediana de los segundos que aguanta.
  kills       mediana de bajas.

Los potenciadores no se miden con este barrido: sus filas se copian tal cual del CSV anterior.
Los nombres, evoluciones y cartas salen de js/data/moves.js del juego.

    python3 build/move_tierlist_v4.py --game /ruta/al/juego
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics as st
from pathlib import Path

import picks

ROOT = Path(__file__).resolve().parent.parent
SWEEP = ROOT / "simulator" / "results" / "fixed_group" / "solo_screen.csv"
FIT_ROUNDS = 200
OUT = ROOT / "data" / "move_tierlist_v4.csv"
MIN_SPECIES = 5

CLOSE_KINDS = {"melee", "aura", "dash", "trail", "orbit", "spin", "shove"}
CAT_CLOSE, CAT_RANGED, CAT_STAT = "cuerpo a cuerpo", "distancia", "estadística"
TIER_SHARE = (("S", 0.15), ("A", 0.40), ("B", 0.70))
HEADER = ["category", "tier", "rank", "move_id", "name", "type", "kind", "score_rel", "dps", "survive_s", "kills",
          "evolves_to", "needs_card", "blurb"]

KIND_ES = {
    "melee": "golpe en arco", "aura": "aura continua", "dash": "carga que atraviesa", "trail": "estela de charcos",
    "orbit": "orbes que giran", "projectile": "proyectiles", "nova": "ráfaga radial", "beam": "rayo recto",
    "boomerang": "bumerán", "chain": "cadena de saltos", "mine": "minas", "meteor": "meteoros", "turret": "torreta",
    "cone": "abanico de disparos", "homing": "proyectiles que persiguen", "bounce": "proyectil que rebota",
    "charge": "rayo cargado", "spin": "giro", "quake": "onda por el suelo", "vortex": "remolino",
    "shove": "onda que empuja", "stun": "zona que aturde",
}
TYPE_ES = {
    "normal": "Normal", "fire": "Fuego", "water": "Agua", "grass": "Planta", "electric": "Eléctrico", "ice": "Hielo",
    "fighting": "Lucha", "poison": "Veneno", "ground": "Tierra", "flying": "Volador", "psychic": "Psíquico",
    "bug": "Bicho", "rock": "Roca", "ghost": "Fantasma", "dragon": "Dragón", "dark": "Siniestro", "steel": "Acero",
    "fairy": "Hada",
}


def game_names(game_dir: Path) -> dict:
    """Nombres españoles de js/data/moves.js: id -> nombre; y EVO: id -> (nombre evolucionado, carta)."""
    text = (game_dir / "js" / "data" / "moves.js").read_text(encoding="utf8")
    names = dict(re.findall(r"\{ id: '([^']+)', name: '([^']+)'", text))
    need = dict(re.findall(r"(\w+): '([^']+)'", text[text.index("const NEED_NAME"):text.index("const EVO")]))
    evo = {mid: (nm, nd) for mid, nm, nd in re.findall(r"'([^']+)': \['([^']+)', '(\w+)'\]", text)}
    return {"names": names, "need": need, "evo": evo}


def _fx(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def _rel(x: float) -> str:
    return "menos de 0,05" if x < 0.05 else _fx(x)


def move_effects(rows: list[dict]) -> dict[str, float]:
    """exp(move effect) of log(score) = species + move, centred so the median move is 1.

    Scores are floored at 1 before the log: a dash that never connects scores 0."""
    cells = [(r["dex"], r["start"], math.log(max(float(r["median_score"]), 1.0))) for r in rows]
    by_dex: dict[str, list[tuple[str, float]]] = {}
    by_move: dict[str, list[tuple[str, float]]] = {}
    for dex, move, y in cells:
        by_dex.setdefault(dex, []).append((move, y))
        by_move.setdefault(move, []).append((dex, y))
    species = dict.fromkeys(by_dex, 0.0)
    effect = dict.fromkeys(by_move, 0.0)
    for _ in range(FIT_ROUNDS):
        for move, obs in by_move.items():
            effect[move] = sum(y - species[d] for d, y in obs) / len(obs)
        for dex, obs in by_dex.items():
            species[dex] = sum(y - effect[m] for m, y in obs) / len(obs)
    centre = st.median(effect.values())
    return {move: math.exp(v - centre) for move, v in effect.items()}


def measure(rows: list[dict]) -> dict[str, dict]:
    """move id -> {species, score_rel, dps, survive_s, kills} over the solo screen."""
    kinds = picks.kinds()
    rows = [r for r in rows if kinds.get(r["start"]) not in (None, "buff")]
    per_move: dict[str, dict[str, list[float]]] = {}
    for r in rows:
        m = per_move.setdefault(r["start"], {"dps": [], "s": [], "kills": []})
        secs = float(r["median_s"])
        m["dps"].append(float(r["median_dealt"]) / secs if secs else 0.0)
        m["s"].append(secs)
        m["kills"].append(float(r["median_kills"]))
    rel = move_effects([r for r in rows if len(per_move[r["start"]]["s"]) >= MIN_SPECIES])
    return {mid: {"species": len(m["s"]), "score_rel": rel[mid], "dps": st.median(m["dps"]),
                  "survive_s": st.median(m["s"]), "kills": st.median(m["kills"])}
            for mid, m in per_move.items() if mid in rel}


def assign_tiers(lst: list[dict]) -> list[dict]:
    lst = sorted(lst, key=lambda r: (-r["score_rel"], r["id"]))
    n = len(lst)
    for i, r in enumerate(lst):
        r["tier"] = ("S" if i < max(1, round(0.15 * n)) else "A" if i < round(0.40 * n)
                     else "B" if i < round(0.70 * n) else "C")
    return lst


def blurb(r: dict, med: dict, evo: tuple | None, need_name: dict) -> str:
    dps_rel = r["dps"] / med["dps"]
    live_rel = r["survive_s"] / med["survive_s"]
    dps_txt = ("daño muy superior" if dps_rel >= 1.6 else "daño superior" if dps_rel >= 1.15 else
               "daño en la media" if dps_rel >= 0.85 else "daño inferior" if dps_rel >= 0.55 else "daño muy inferior")
    live_txt = ("te mantiene vivo mucho más" if live_rel >= 1.5 else "te mantiene vivo más" if live_rel >= 1.15 else
                "aguante en la media" if live_rel >= 0.85 else "te expone más" if live_rel >= 0.55 else "te expone mucho")
    why = ("Obliga a pelear dentro del enjambre, por eso el aguante pesa tanto." if r["cat"] == CAT_CLOSE
           else "Golpea desde lejos, así que el daño recibido depende menos del movimiento.")
    evo_txt = f" Evoluciona a {evo[0]} con la carta {need_name[evo[1]]}." if evo else ""
    return (f"{TYPE_ES[r['type']]}, {KIND_ES[r['kind']]}: {dps_txt} ({_rel(dps_rel)}× la mediana de los ataques) y "
            f"{live_txt} ({_rel(live_rel)}×). {why}{evo_txt}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", type=Path, required=True, help="copia local del repositorio del juego (solo lectura)")
    ap.add_argument("--sweep", type=Path, default=SWEEP)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    names = game_names(args.game)
    stats = measure(picks.load_rows(args.sweep))
    game = json.loads((ROOT / "data" / "game_stats.json").read_text(encoding="utf8"))["moves"]
    attacks = [mid for mid, m in game.items() if m["kind"] != "buff"]
    missing = [m for m in attacks if m not in stats]
    if missing:
        raise SystemExit(f"movimientos sin medida en el barrido: {missing}")

    rows = []
    for mid in attacks:
        kind = game[mid]["kind"]
        rows.append({"id": mid, "kind": kind, "type": game[mid]["type"],
                     "cat": CAT_CLOSE if kind in CLOSE_KINDS else CAT_RANGED, **stats[mid]})
    med = {k: st.median(r[k] for r in rows) for k in ("dps", "survive_s")}
    close = assign_tiers([r for r in rows if r["cat"] == CAT_CLOSE])
    ranged = assign_tiers([r for r in rows if r["cat"] == CAT_RANGED])

    with (ROOT / "data" / "move_tierlist_v4.csv").open(encoding="utf8", newline="") as f:
        stat_rows = [r for r in csv.DictReader(f) if r["category"] == CAT_STAT]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for lst in (close, ranged):
            for i, r in enumerate(lst, 1):
                evo = names["evo"].get(r["id"])
                w.writerow([r["cat"], r["tier"], i, r["id"], names["names"][r["id"]], r["type"], r["kind"],
                            round(r["score_rel"], 3), round(r["dps"]), round(r["survive_s"], 1), round(r["kills"], 1),
                            evo[0] if evo else "", names["need"][evo[1]] if evo else "",
                            blurb(r, med, evo, names["need"])])
        for r in stat_rows:
            w.writerow([r["category"], r["tier"], r["rank"], r["move_id"], r["name"], r["type"], "buff",
                        r["score_rel"], "", "", "", "", "", r["blurb"]])
    print(f"{args.out}: {len(close)} cuerpo a cuerpo, {len(ranged)} distancia, {len(stat_rows)} estadística")
    for lst in (close, ranged):
        print([(r["tier"], names["names"][r["id"]]) for r in lst[:6]])


if __name__ == "__main__":
    main()
