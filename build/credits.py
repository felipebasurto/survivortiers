"""Lee data/CREDITS.md (copia de CREDITS.md del juego, commit a9b21f0) y devuelve
quién dibujó el sprite de cada Pokémon.

Solo se publica el nombre del artista y, si tiene, un enlace http(s). Los correos
y los identificadores de Discord del fichero original no se copian a la web:
CC BY 4.0 pide crédito adecuado (nombre y, opcionalmente, un enlace), no contacto.
"""
from __future__ import annotations

import re
from pathlib import Path

ROW = re.compile(r"^\|\s*(?P<artist>.+?)\s*\|\s*(?P<contact>.*?)\s*\|\s*(?P<dex>\d[\d,\s]*)\s*\|\s*$")
URL = re.compile(r"^https?://[^\s<>]+$")

SPRITE_LICENSE = {
    "name": "CC BY-NC 4.0",
    "url": "https://creativecommons.org/licenses/by-nc/4.0/",
}
SPRITE_SOURCE = {
    "name": "SpriteCollab",
    "url": "https://github.com/PMDCollab/SpriteCollab",
}


# Enlaces de CREDITS.md que dan 404 (comprobado con build/check_site.py --external, oct 2026).
# Se publica igualmente el nombre del artista; solo se omite el enlace muerto.
DEAD_URLS = {
    "https://twitter.com/Pi_y_ranitas",
    "https://twitter.com/Sea_of_Pencils",
}


class CreditsError(RuntimeError):
    pass


def _clean_name(raw: str) -> str:
    name = raw.replace("\\_", "_").replace("\\", "").strip()
    return name


def _clean_url(raw: str) -> str | None:
    value = raw.strip().strip("<>").strip()
    return value if URL.match(value) and value not in DEAD_URLS else None


def parse_credits(path: Path) -> dict:
    """Devuelve {'artists': [{name, url, dex[]}], 'by_dex': {dex: [artist_index]}}."""
    text = path.read_text(encoding="utf8")
    start = text.index("## Sprites")
    end = text.index("## Datos")
    artists: list[dict] = []
    skipped: list[str] = []
    for line in text[start:end].splitlines():
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| Artista"):
            continue
        m = ROW.match(line)
        if not m:
            skipped.append(line[:80])
            continue
        dex = sorted({int(x) for x in re.findall(r"\d+", m.group("dex"))})
        artists.append({"name": _clean_name(m.group("artist")), "url": _clean_url(m.group("contact")), "dex": dex})
    if skipped:
        raise CreditsError(f"{len(skipped)} filas de CREDITS.md sin entender: {skipped[:3]}")
    if not artists:
        raise CreditsError("CREDITS.md no tiene artistas")
    by_dex: dict[int, list[int]] = {}
    for i, a in enumerate(artists):
        for d in a["dex"]:
            by_dex.setdefault(d, []).append(i)
    return {"artists": artists, "by_dex": by_dex}


def sprite_credit(credits: dict, dex: int) -> dict | None:
    """Atribución completa de un sprite, o None si no hay ningún artista."""
    idx = credits["by_dex"].get(dex)
    if not idx:
        return None
    return {
        "artists": [{"name": credits["artists"][i]["name"], "url": credits["artists"][i]["url"]} for i in idx],
        "license": SPRITE_LICENSE["name"],
        "licenseUrl": SPRITE_LICENSE["url"],
        "sourceUrl": f"https://sprites.pmdcollab.org/#/{dex:04d}",
    }
