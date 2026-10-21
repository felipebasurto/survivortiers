"""Qué Pokémon pueden salir shiny en el juego, y sus sprites shiny para la colección.

Fuente: JPTER78/pokesurvivor @ 5bbc3b2, solo lectura. js/data/sprites-meta.js (generado por tools/fetch_sprites.py de
SpriteCollab) pone sh=1 en los Pokémon con versión shiny, y js/core/sprites.js (hasShiny) y js/systems/spawner.js
(rollShiny) solo sortean shiny en esos. El fotograma de cada sprite es la fila 0 (abajo), columna 0 de Idle.png,
recortada al píxel opaco; con esa regla salen exactamente los 966 sprites de sprites/ (--fetch lo comprueba). El shiny
usa assets/pokemon/<n>/s/Idle.png, con la geometría shiny de sprites-meta cuando la hay (campo sa).

    python3 build/shiny_sprites.py --fetch   # descarga del juego: reescribe data/shiny_species.json y sprites/shiny/
    python3 build/shiny_sprites.py           # comprueba lo que está en el repositorio, sin red

Después, python3 build/webp.py genera sprites/shiny/*.webp, que es lo que sirve la página.
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # optional: only --fetch and frame writes need it; CI installs Pillow
    Image = None  # type: ignore[misc, assignment]

ROOT = Path(__file__).resolve().parent.parent
REPO = "JPTER78/pokesurvivor"
COMMIT = "5bbc3b2"
META_PATH = "js/data/sprites-meta.js"
ASSETS = "assets/pokemon/"
RAW = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/"
CACHE = ROOT / ".cache" / "game"
POKEDEX = ROOT / "data" / "pokedex_export.json"
OUT_JSON = ROOT / "data" / "shiny_species.json"
SPRITES = ROOT / "sprites"
SHINY_DIR = SPRITES / "shiny"
ENTRY = re.compile(r"^\s*(\d+):\s*(\{.*\}),?\s*$")


class ShinyError(RuntimeError):
    pass


def parse_meta(text: str) -> dict[int, dict]:
    """sprites-meta.js tiene una entrada por línea: «  1: {...},». Devuelve {dex: entrada}."""
    out: dict[int, dict] = {}
    for line in text.splitlines():
        m = ENTRY.match(line)
        if m:
            out[int(m.group(1))] = json.loads(m.group(2))
    if not out:
        raise ShinyError(f"{META_PATH}: no encuentro entradas de SPRITE_META")
    return out


def shiny_dex(meta: dict[int, dict]) -> list[int]:
    return sorted(d for d, v in meta.items() if v.get("sh"))


def crop_frame(sheet: Path, size: dict):
    """Fotograma 0 de la fila 0 (abajo) recortado a sus píxeles opacos."""
    if Image is None:
        raise ShinyError("Pillow is required to crop sprite frames (pip install Pillow)")
    img = Image.open(sheet).convert("RGBA")
    frame = img.crop((0, 0, size["w"], size["h"]))
    box = frame.getbbox()
    if box is None:
        raise ShinyError(f"{sheet}: el fotograma está vacío")
    return frame.crop(box)


def idle_size(entry: dict, shiny: bool) -> dict:
    if shiny and entry.get("sa") and "Idle" in entry["sa"]:
        return entry["sa"]["Idle"]
    return entry["a"]["Idle"]


def fetch(url: str, dest: Path) -> None:
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as r:
        dest.write_bytes(r.read())


def download(meta: dict[int, dict], dexes: list[int], shiny: list[int]) -> None:
    jobs = [(f"{RAW}{ASSETS}{d}/Idle.png", CACHE / str(d) / "Idle.png") for d in dexes]
    jobs += [(f"{RAW}{ASSETS}{d}/s/Idle.png", CACHE / str(d) / "s" / "Idle.png") for d in shiny]
    with futures.ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda j: fetch(*j), jobs))


def write_frames(meta: dict[int, dict], dexes: list[int], shiny: list[int]) -> None:
    """Comprueba que el sprite normal sale igual que el de sprites/ y escribe los shiny en sprites/shiny/."""
    if Image is None:
        raise ShinyError("Pillow is required to write shiny frames (pip install Pillow)")
    SHINY_DIR.mkdir(parents=True, exist_ok=True)
    bad = []
    for d in dexes:
        ref = Image.open(SPRITES / f"{d}.png").convert("RGBA")
        got = crop_frame(CACHE / str(d) / "Idle.png", idle_size(meta[d], shiny=False))
        if got.size != ref.size or got.tobytes() != ref.tobytes():
            bad.append(d)
    if bad:
        raise ShinyError(f"el fotograma normal no coincide con sprites/ en {bad[:10]}: revisa la regla de recorte")
    for d in shiny:
        frame = crop_frame(CACHE / str(d) / "s" / "Idle.png", idle_size(meta[d], shiny=True))
        frame.save(SHINY_DIR / f"{d}.png", optimize=True)


def vendored(dexes: list[int], shiny: list[int], meta_sha: str) -> dict:
    without = sorted(set(dexes) - set(shiny))
    return {
        "source": {"repo": REPO, "commit": COMMIT, "file": META_PATH, "sha256": meta_sha,
                   "sheets": ASSETS + "<dex>/s/Idle.png"},
        "rule": "sh=1 en sprites-meta.js: el Pokémon tiene sprite shiny (hasShiny del juego)",
        "count": len(shiny),
        "dex": shiny,
        "withoutShiny": without,
    }


def check_repo(dexes: list[int]) -> None:
    doc = json.loads(OUT_JSON.read_text(encoding="utf8"))
    if doc["source"]["commit"] != COMMIT:
        raise ShinyError(f"{OUT_JSON.name} viene de {doc['source']['commit']}, no de {COMMIT}")
    shiny = doc["dex"]
    if doc["count"] != len(shiny) or shiny != sorted(set(shiny)):
        raise ShinyError(f"{OUT_JSON.name}: la lista no está ordenada sin repetir o no cuadra con count")
    if sorted(set(shiny) | set(doc["withoutShiny"])) != dexes:
        raise ShinyError(f"{OUT_JSON.name}: no cubre exactamente los Pokémon de pokedex_export.json")
    missing = [d for d in shiny if not (SHINY_DIR / f"{d}.png").exists()]
    if missing:
        raise ShinyError(f"faltan sprites shiny: {missing[:10]} (ejecuta con --fetch)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fetch", action="store_true", help="descarga del juego @ " + COMMIT + " y rehace los datos")
    args = ap.parse_args(argv)
    dexes = sorted(p["dex"] for p in json.loads(POKEDEX.read_text(encoding="utf8")))
    try:
        if args.fetch:
            CACHE.mkdir(parents=True, exist_ok=True)
            meta_file = CACHE / "sprites-meta.js"
            fetch(RAW + META_PATH, meta_file)
            meta = parse_meta(meta_file.read_text(encoding="utf8"))
            if sorted(meta) != dexes:
                raise ShinyError("sprites-meta.js no tiene los 966 Pokémon de pokedex_export.json")
            shiny = shiny_dex(meta)
            download(meta, dexes, shiny)
            write_frames(meta, dexes, shiny)
            sha = hashlib.sha256(meta_file.read_bytes()).hexdigest()
            OUT_JSON.write_text(json.dumps(vendored(dexes, shiny, sha), ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf8")
            print(f"shiny: {len(shiny)} de {len(dexes)} Pokémon con sprite shiny → {OUT_JSON.relative_to(ROOT)}")
        else:
            check_repo(dexes)
            print(f"shiny: {json.loads(OUT_JSON.read_text(encoding='utf8'))['count']} de {len(dexes)} con sprite, en {SHINY_DIR.relative_to(ROOT)}")
    except (ShinyError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
