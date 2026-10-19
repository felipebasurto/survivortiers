"""Tier list de movimientos (data/move_tierlist_v4.csv), sacada del barrido en solitario de la simulación.

Cada fila de simulator/results/fixed_group/solo_sweep.csv es un Pokémon que abre la partida con un movimiento.
Para cada movimiento se mira, en todos los Pokémon que lo pueden llevar:

  score_rel   la puntuación de la simulación de cada Pokémon con ese movimiento, dividida por la mediana de
              su propio catálogo, y la mediana de esos cocientes. 1 es un movimiento normal, más es mejor.
              Un cuerpo a cuerpo lleva la penalización del dueño (data/owner_rules.json) y en Gengar no cuenta.
  dps         mediana del daño total entre los segundos que dura la partida.
  survive_s   mediana de los segundos que aguanta.
  kills       mediana de bajas.

Sustituto no es un ataque (data/owner_rules.json): se queda en el último puesto de su categoría con valor 0.
Los potenciadores no se miden con este barrido: sus filas se copian tal cual del CSV anterior (cifras del juego,
sin cambios en 5a23d49). Los nombres, evoluciones y cartas salen de js/data/moves.js del juego.

    python3 build/move_tierlist_v4.py --game /ruta/al/juego
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics as st
from pathlib import Path

import owner_rules
import picks

ROOT = Path(__file__).resolve().parent.parent
SWEEP = ROOT / "simulator" / "results" / "fixed_group" / "solo_sweep.csv"
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


def measure(rows: list[dict]) -> dict[str, dict]:
    """move id -> {species, score_rel, dps, survive_s, kills} over the solo sweep."""
    kinds = picks.kinds()
    by_dex: dict[int, list[dict]] = {}
    for row in rows:
        dex = int(row["dex"])
        move = row["start"]
        if move in owner_rules.NEVER_ATTACK or kinds.get(move) in (None, "buff"):
            continue
        if not owner_rules.allows_melee(dex) and kinds[move] == "melee":
            continue
        by_dex.setdefault(dex, []).append(row)
    per_move: dict[str, dict[str, list[float]]] = {}
    for dex, group in by_dex.items():
        scores = {r["start"]: picks.score(r, kinds[r["start"]] == "melee") for r in group}
        mid = st.median(scores.values())
        if mid <= 0:
            continue
        for r in group:
            m = per_move.setdefault(r["start"], {"rel": [], "dps": [], "s": [], "kills": []})
            m["rel"].append(scores[r["start"]] / mid)
            secs = float(r["median_s"])
            m["dps"].append(float(r["median_dealt"]) / secs if secs else 0.0)
            m["s"].append(secs)
            m["kills"].append(float(r["median_kills"]))
    return {mid: {"species": len(m["rel"]), "score_rel": st.median(m["rel"]), "dps": st.median(m["dps"]),
                  "survive_s": st.median(m["s"]), "kills": st.median(m["kills"])}
            for mid, m in per_move.items() if len(m["rel"]) >= MIN_SPECIES}


def assign_tiers(lst: list[dict]) -> list[dict]:
    lst = sorted(lst, key=lambda r: (-r["score_rel"], r["id"]))
    n = len(lst)
    for i, r in enumerate(lst):
        r["tier"] = ("S" if i < max(1, round(0.15 * n)) else "A" if i < round(0.40 * n)
                     else "B" if i < round(0.70 * n) else "C")
    return lst


def blurb(r: dict, med: dict, evo: tuple | None, need_name: dict) -> str:
    if r["id"] in owner_rules.NEVER_ATTACK:
        return (f"{TYPE_ES[r['type']]}, {KIND_ES[r['kind']]}: el simulador lo pone como torreta que hace daño, pero no "
                "cuenta como ataque. No se publica como mejor movimiento ni entra en un grupo.")
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
    missing = [m for m in attacks if m not in stats and m not in owner_rules.NEVER_ATTACK]
    if missing:
        raise SystemExit(f"movimientos sin medida en el barrido: {missing}")

    rows = []
    for mid in attacks:
        kind = game[mid]["kind"]
        base = stats.get(mid) or {"score_rel": 0.0, "dps": 0.0, "survive_s": 0.0, "kills": 0.0}
        rows.append({"id": mid, "kind": kind, "type": game[mid]["type"],
                     "cat": CAT_CLOSE if kind in CLOSE_KINDS else CAT_RANGED, **base})
    med = {k: st.median(r[k] for r in rows if r["id"] not in owner_rules.NEVER_ATTACK) for k in ("dps", "survive_s")}
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
