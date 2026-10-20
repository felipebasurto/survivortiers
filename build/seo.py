"""Lo que la portada ofrece a buscadores y a asistentes de IA sin ejecutar JavaScript: el párrafo de arriba, la tabla
de los 30 mejores y el JSON-LD. Todo sale del ranking ya generado y de las constantes de legal.py; no hay cifras nuevas.
"""
from __future__ import annotations

import json
from html import escape

import legal
import static_ficha
from i18n import Lang
from slugs import species_path

TOP_LEDE = 5
TOP_TABLE = 30


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


def lede_html(L: Lang, index: list[dict], meta: dict, home: str) -> str:
    return L.t("value_html", top=escape(top_names(L, index)), n=meta["total"], date=L.date(legal.UPDATED_DATE),
               sha=legal.UPDATED_COMMIT, built=L.date(meta["generatedAt"][:10]), method=f"{home}metodo.html",
               repo=escape(legal.REPO_URL), **legal.method_counts(L, meta))


def top30_html(L: Lang, index: list[dict], home: str) -> str:
    rows = []
    for p in _ranked(index, TOP_TABLE):
        rank, tier, lo, hi = p["r"][:4]
        href = f"{home}pokemon/{species_path(p['dex'], p['nameEn'])}/"
        types = ", ".join(L.type_name(t) for t in p["types"])
        places = L.t("top30_places", lo=lo, hi=hi)
        rows.append(f'<tr><td class="num">{rank}</td><th scope="row"><a href="{href}">{escape(L.mon(p))}</a></th>'
                    f'<td><span class="tier-badge {tier}">{tier}</span></td><td>{escape(types)}</td>'
                    f'<td class="num">{escape(places)}</td></tr>')
    head = "".join(f'<th scope="col">{escape(L.t(k))}</th>'
                   for k in ("top30_rank", "top30_mon", "top30_tier", "top30_types", "top30_band"))
    return (f'<section class="top30" id="top30" aria-labelledby="top30-h"><h2 id="top30-h">'
            f'{escape(L.t("top30_h", game=legal.GAME_NAME))}</h2><p class="muted">{escape(L.t("top30_lede"))}</p>'
            f'<div class="table-wrap"><table><caption class="sr">{escape(L.t("top30_caption", game=legal.GAME_NAME))}</caption>'
            f'<thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>')


def home_jsonld(L: Lang, index: list[dict], meta: dict, url: str, title: str, desc: str) -> str:
    """WebSite, página de colección y ItemList con los mismos 30 que la tabla. url es la de la portada en este idioma."""
    lang = "en" if L.en else "es"
    prefix = f"{legal.SITE_URL}/{'en/' if L.en else ''}"
    items = [{"@type": "ListItem", "position": p["r"][0], "name": L.mon(p),
              "url": f"{prefix}pokemon/{species_path(p['dex'], p['nameEn'])}/"} for p in _ranked(index, TOP_TABLE)]
    site = {"@type": "WebSite", "@id": f"{legal.SITE_URL}/#website", "name": legal.SITE_NAME, "url": f"{legal.SITE_URL}/",
            "inLanguage": ["es", "en"]}
    doc = {
        "@context": "https://schema.org",
        "@graph": [
            site,
            {"@type": "CollectionPage", "@id": f"{url}#page", "url": url, "name": title, "description": desc,
             "inLanguage": lang, "isPartOf": {"@id": site["@id"]}, "dateModified": meta["generatedAt"][:10],
             "mainEntity": {"@id": f"{url}#top"}},
            {"@type": "ItemList", "@id": f"{url}#top", "name": L.t("top30_caption", game=legal.GAME_NAME),
             "itemListOrder": "https://schema.org/ItemListOrderAscending", "numberOfItems": len(items),
             "itemListElement": items},
        ],
    }
    text = json.dumps(doc, ensure_ascii=False, indent=1).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{text}\n</script>'
