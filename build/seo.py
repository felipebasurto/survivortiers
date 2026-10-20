"""Lo que la portada ofrece a buscadores y a asistentes de IA sin ejecutar JavaScript: el párrafo de arriba, la tabla
de los 30 mejores y el JSON-LD. Todo sale del ranking ya generado y de las constantes de legal.py; no hay cifras nuevas.
"""
from __future__ import annotations

import json

import legal
import static_ficha
from i18n import Lang

TOP_LEDE = 5


def _ranked(index: list[dict], n: int) -> list[dict]:
    return sorted(index, key=lambda p: p["r"][0])[:n]


def top_names(L: Lang, index: list[dict], n: int = TOP_LEDE) -> str:
    """«Kartana (S), Gholdengo (S) y …»: los n primeros del ranking con su tier."""
    return static_ficha._join(L, [f'{L.mon(p)} ({p["r"][1]})' for p in _ranked(index, n)])


def home_texts(L: Lang, index: list[dict], meta: dict) -> tuple[str, str]:
    """Título y descripción de la portada."""
    title = L.t("home_title", n=meta["total"])
    desc = L.t("home_desc", n=meta["total"], date=L.date(legal.UPDATED_DATE), top=top_names(L, index, 3))
    return title, desc


def home_jsonld(L: Lang, index: list[dict], meta: dict, url: str, title: str, desc: str) -> str:
    """WebSite y página de colección. url es la de la portada en este idioma."""
    lang = "en" if L.en else "es"
    site = {"@type": "WebSite", "@id": f"{legal.SITE_URL}/#website", "name": legal.SITE_NAME, "url": f"{legal.SITE_URL}/",
            "inLanguage": ["es", "en"]}
    doc = {
        "@context": "https://schema.org",
        "@graph": [
            site,
            {"@type": "CollectionPage", "@id": f"{url}#page", "url": url, "name": title, "description": desc,
             "inLanguage": lang, "isPartOf": {"@id": site["@id"]}, "dateModified": meta["generatedAt"][:10]},
        ],
    }
    text = json.dumps(doc, ensure_ascii=False, indent=1).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{text}\n</script>'
