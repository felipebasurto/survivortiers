#!/usr/bin/env python3
"""Baja las seis estadísticas base oficiales (PS, ataque, defensa, ataque especial, defensa especial, velocidad)
de PokéAPI para los 966 Pokémon de la lista y las deja en data/base_stats.json. Se ejecuta una vez; el resto del
build lee ese fichero y no toca internet.

    python3 build/fetch_base_stats.py
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://pokeapi.co/api/v2/pokemon/{}"
ROOT = Path(__file__).resolve().parent.parent
DEX_FILE = ROOT / "data" / "pokedex_export.json"
OUT = ROOT / "data" / "base_stats.json"
# Orden fijo que usa species.json: el mismo que aparece en la ficha.
ORDER = ["hp", "attack", "defense", "special-attack", "special-defense", "speed"]


def get(dex: int, retries: int = 3) -> list[int] | None:
    for _ in range(retries):
        try:
            req = urllib.request.Request(API.format(dex), headers={"User-Agent": "survivortiers/1.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                body = json.load(r)
            base = {s["stat"]["name"]: s["base_stat"] for s in body["stats"]}
            return [base[k] for k in ORDER]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            pass
    return None


def main() -> None:
    dexes = sorted(p["dex"] for p in json.loads(DEX_FILE.read_text(encoding="utf8")))
    print(f"Bajando {len(dexes)} Pokémon de PokéAPI…")
    out, missing = {}, []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for dex, stats in zip(dexes, ex.map(get, dexes)):
            if stats is None:
                missing.append(dex)
            else:
                out[str(dex)] = stats
    if missing:
        raise SystemExit(f"sin datos para {len(missing)} Pokémon: {missing[:10]}")
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf8")
    print(f"{len(out)} Pokémon → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
