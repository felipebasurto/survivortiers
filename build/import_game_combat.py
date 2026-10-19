#!/usr/bin/env python3
"""Añade a data/pokedex_export.json los valores de combate de cada Pokémon del juego:
pa y sa (multiplicador del daño de sus ataques físicos y especiales; atk es el mayor de los dos),
df y sd (Defensa y Defensa Especial base).

Fuente: js/data/pokedex.js de JPTER78/pokesurvivor en el commit de --commit (5a23d49 por defecto), una línea
por Pokémon. El script solo añade esas cuatro claves. Antes comprueba que el commit del checkout es el pedido y
que hp, spd, atk, nombre, tipos, rareza y generación coinciden con el export que ya hay; si no coinciden, el juego
cambió y el export hay que regenerarlo entero.

    git clone https://github.com/JPTER78/pokesurvivor /ruta/pokesurvivor
    git -C /ruta/pokesurvivor checkout 5a23d49
    python3 build/import_game_combat.py --game /ruta/pokesurvivor
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPORT = ROOT / "data" / "pokedex_export.json"
GAME_FILE = Path("js") / "data" / "pokedex.js"
DEFAULT_COMMIT = "5a23d49"
NEW_KEYS = ("pa", "sa", "df", "sd")
LINE = re.compile(r'^\s*(\{"dex":.*\}),?\s*$')
SAME = ("hp", "spd", "atk", "name", "types", "rarity", "gen")


class ImportFailure(RuntimeError):
    pass


def game_commit(game: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(game), "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ImportFailure(f"{game} no es un checkout git del juego") from exc
    return out.stdout.strip()


def read_game(game: Path) -> list[dict]:
    text = (game / GAME_FILE).read_text(encoding="utf8")
    rows = [m.group(1) for m in map(LINE.match, text.splitlines()) if m]
    if len(rows) != 966:
        raise ImportFailure(f"{GAME_FILE}: {len(rows)} Pokémon, se esperaban 966")
    return [json.loads(r) for r in rows]


def merge(export: list[dict], game: list[dict]) -> list[dict]:
    by_dex = {g["dex"]: g for g in game}
    if set(by_dex) != {p["dex"] for p in export}:
        raise ImportFailure("los números de Pokédex del juego no son los de pokedex_export.json")
    out = []
    for p in export:
        g = by_dex[p["dex"]]
        for k in SAME:
            if g[k] != p[k]:
                raise ImportFailure(f"{p['dex']}: {k} es {g[k]!r} en el juego y {p[k]!r} en el export")
        if abs(g["atk"] - max(g["pa"], g["sa"])) > 0.005:
            raise ImportFailure(f"{p['dex']}: atk {g['atk']} no es el mayor de pa {g['pa']} y sa {g['sa']}")
        row = {k: v for k, v in p.items() if k not in NEW_KEYS}
        head = list(row.keys()).index("atk") + 1
        ordered = list(row.items())
        ordered[head:head] = [(k, g[k]) for k in NEW_KEYS]
        out.append(dict(ordered))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--game", required=True, type=Path, help="checkout de JPTER78/pokesurvivor")
    ap.add_argument("--commit", default=DEFAULT_COMMIT, help="commit que debe tener el checkout")
    args = ap.parse_args()
    try:
        head = game_commit(args.game)
        if not head.startswith(args.commit):
            raise ImportFailure(f"el checkout está en {head[:7]}, se pidió {args.commit}")
        export = json.loads(EXPORT.read_text(encoding="utf8"))
        merged = merge(export, read_game(args.game))
    except (ImportFailure, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    EXPORT.write_text(json.dumps(merged, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    print(f"{EXPORT.relative_to(ROOT)}: pa, sa, df, sd de {len(merged)} Pokémon desde {GAME_FILE} @ {args.commit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
