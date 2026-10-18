"""Rutas limpias de cada Pokémon: /pokemon/150-mewtwo/ y /en/pokemon/150-mewtwo/.

El nombre es el inglés, en ASCII. La misma función está en src/app.js (speciesSlug): si cambia una, cambia la otra.
El número de Pokédex va delante, así que dos nombres que acaben igual no chocan.
"""
from __future__ import annotations

import re
import unicodedata

_NON = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    s = name.replace("♀", "-f").replace("♂", "-m")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return _NON.sub("-", s.lower()).strip("-")


def species_path(dex: int, name_en: str) -> str:
    return f"{dex}-{slugify(name_en)}"
