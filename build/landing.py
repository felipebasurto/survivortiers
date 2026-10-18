"""Páginas de consulta: mejores Pokémon, mejores iniciales, legendarios, uno por tipo y mejores pasivas.

Todo sale de los datos del build (pokemon.json, species.json, moves.json, meta.json) y de la tabla de pasivas de
pasivas.py. No hay textos escritos a mano por Pokémon: cada página responde en sus dos primeras líneas con la lista
que muestra debajo, y el JSON-LD (CollectionPage con ItemList) repite exactamente esa lista.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape

import legal
import pasivas
import static_ficha
from i18n import EN, ES, TYPE_NAMES, Lang
from slugs import slugify, species_path

TOP_BEST = 30  # el tier S entero
TOP_STARTERS = 20
TOP_TYPE = 20
CARD_SCALE = 2  # la misma escala de sprite que la tier list
LEDE_NAMES = 3  # nombres que nombra la primera línea
TIER_S = "S"
TYPE_KEYS = tuple(TYPE_NAMES["es"])


@dataclass(frozen=True)
class Page:
    key: str  # "best", "starters", "legendary", "passives" o "type:<clave del tipo>"
    es: str   # carpeta en español, con barra final
    en: str   # carpeta en inglés, con barra final


@dataclass(frozen=True)
class Built:
    title: str
    desc: str
    h1: str
    content: str
    jsonld: str
    alternates: str


def pages() -> list[Page]:
    out = [
        Page("best", "mejores-pokemon/", "best-pokemon/"),
        Page("starters", "mejores-iniciales/", "best-starters/"),
        Page("legendary", "mejores-legendarios/", "best-legendaries/"),
    ]
    out += [Page(f"type:{t}", f"mejores-tipo/{slugify(TYPE_NAMES['es'][t])}/",
                 f"best-type/{slugify(TYPE_NAMES['en'][t])}/") for t in TYPE_KEYS]
    out.append(Page("passives", "mejores-pasivas/", "best-passives/"))
    return out


def page_for(key: str) -> Page:
    return next(p for p in pages() if p.key == key)


def folder(L: Lang, page: Page) -> str:
    return page.en if L.en else page.es


def rel(L: Lang, page: Page) -> str:
    """Ruta del HTML dentro de su idioma, p. ej. mejores-tipo/fuego/index.html."""
    return folder(L, page) + "index.html"


def url(L: Lang, page: Page) -> str:
    return f"{legal.SITE_URL}/{'en/' if L.en else ''}{folder(L, page)}"


def alternates(page: Page) -> str:
    es, en = url(ES, page), url(EN, page)
    return "\n".join((
        f'<link rel="alternate" hreflang="es" href="{escape(es)}">',
        f'<link rel="alternate" hreflang="en" href="{escape(en)}">',
        f'<link rel="alternate" hreflang="x-default" href="{escape(es)}">',
    ))


def _type_key(page: Page) -> str:
    return page.key.split(":", 1)[1]


def _ficha_url(L: Lang, p: dict) -> str:
    return f"{legal.SITE_URL}/{'en/' if L.en else ''}pokemon/{species_path(p['dex'], p['nameEn'])}/"


def _move_name(L: Lang, moves: dict[str, dict], mid: str) -> str:
    return moves[mid]["en"]["name"] if L.en else moves[mid]["name"]


def _members(page: Page, index: list[dict]) -> list[dict]:
    if page.key == "legendary":
        return [p for p in index if p["legendary"]]
    if page.key.startswith("type:"):
        t = _type_key(page)
        return [p for p in index if t in p["types"]]
    return index


def _select(page: Page, index: list[dict], by_dex: dict[int, dict], details: dict[str, list], moves: dict[str, dict],
            L: Lang) -> list[tuple[dict, str, str]]:
    """Filas (Pokémon, puesto que se muestra, ataque inicial en este idioma) en el orden de la página."""
    if page.key == "best":
        return [(p, str(p["r"][0]), "") for p in sorted(index, key=lambda p: p["r"][0])[:TOP_BEST]]
    if page.key == "starters":
        mons = sorted(index, key=lambda p: by_dex[p["dex"]]["r"]["methods"]["simStart"])[:TOP_STARTERS]
        return [(p, str(by_dex[p["dex"]]["r"]["methods"]["simStart"]),
                 _move_name(L, moves, details[str(p["dex"])][2])) for p in mons]
    if page.key == "legendary":
        return [(p, str(p["r"][0]), "") for p in sorted(_members(page, index), key=lambda p: p["r"][0])]
    if page.key == "passives":
        return []
    mons = sorted(_members(page, index), key=lambda p: p["r"][0])[:TOP_TYPE]
    return [(p, str(p["r"][0]), "") for p in mons]


def _card(L: Lang, home: str, p: dict, right: str, sub: str) -> str:
    w, h = p["w"] * CARD_SCALE, p["h"] * CARD_SCALE
    subline = f'<span class="ql-sub">{escape(L.t("lp_start_move", move=sub))}</span>' if sub else ""
    return (f'<li><a class="mon" href="{home}pokemon/{species_path(p["dex"], p["nameEn"])}/" data-dex="{p["dex"]}">'
            f'<span class="sp"><img class="px" src="{legal.SPRITE_BASE}{p["dex"]}{legal.SPRITE_EXT}" width="{w}" '
            f'height="{h}" alt="" loading="lazy" decoding="async"></span>'
            f'<span class="nm">{escape(L.mon(p))}</span>{subline}<span class="rk">{escape(right)}</span></a></li>')


def _passives_html(L: Lang) -> str:
    items = "".join(
        f'<li><span class="ql-val">{escape(pasivas._pct(c["coin"], L, 0))}</span>'
        f'<span class="ql-name">{escape(pasivas._t(c["name"], L))}</span></li>'
        for c in pasivas.CARDS)
    return f'<ol class="ql-rows">{items}</ol>'


def _list_html(L: Lang, home: str, rows: list[tuple[dict, str, str]]) -> str:
    return f'<ol class="ql-grid">{"".join(_card(L, home, p, right, sub) for p, right, sub in rows)}</ol>'


def guides_nav(L: Lang, home: str, types: list[str] | None = None, skip: str | None = None) -> str:
    """Enlaces a la tier list y a las páginas de consulta. Las fichas pasan sus tipos; la portada, todos."""
    chips = [
        ("tierlist", f"{home}index.html", "guide_tierlist"),
        ("best", f"{home}{folder(L, page_for('best'))}", "guide_best"),
        ("starters", f"{home}{folder(L, page_for('starters'))}", "guide_starters"),
        ("legendary", f"{home}{folder(L, page_for('legendary'))}", "guide_legendary"),
        ("passives", f"{home}{folder(L, page_for('passives'))}", "guide_passives"),
    ]
    items = [f'<li><a href="{href}">{escape(L.t(key))}</a></li>' for k, href, key in chips if k != skip]
    wanted = TYPE_KEYS if types is None else types
    for t in wanted:
        page = page_for(f"type:{t}")
        if page.key != skip:
            items.append(f'<li><a href="{home}{folder(L, page)}">{escape(L.type_name(t))}</a></li>')
    return (f'<nav class="ql-guides" aria-label="{escape(L.t("guides_h"))}"><p class="ql-guides-h">{escape(L.t("guides_h"))}</p>'
            f'<ul class="toc">{"".join(items)}</ul></nav>')


def _jsonld(L: Lang, page: Page, title: str, desc: str, rows: list[tuple[dict, str, str]], meta: dict) -> str:
    if page.key == "passives":
        elements = [{"@type": "ListItem", "position": i + 1, "name": pasivas._t(c["name"], L)}
                    for i, c in enumerate(pasivas.CARDS)]
    else:
        elements = [{"@type": "ListItem", "position": i + 1, "name": L.mon(p), "url": _ficha_url(L, p)}
                    for i, (p, _, _) in enumerate(rows)]
    doc = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": title,
        "description": desc,
        "url": url(L, page),
        "inLanguage": "en" if L.en else "es",
        "dateModified": meta["generatedAt"][:10],
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(elements), "itemListElement": elements},
    }
    text = json.dumps(doc, ensure_ascii=False, indent=1).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{text}\n</script>'


def build(L: Lang, page: Page, index: list[dict], by_dex: dict[int, dict], details: dict[str, list],
          moves: dict[str, dict], meta: dict, home: str) -> Built:
    members = _members(page, index)
    rows = _select(page, index, by_dex, details, moves, L)
    note = L.t("lp_note", sims=L.num(meta["simSeeds"]), reps=L.num(meta["method"]["repeats"]))
    s = sum(1 for p in members if p["r"][1] == TIER_S)
    top_h = L.t("lp_top_h")
    types = None
    if page.key == "passives":
        cards = pasivas.CARDS
        best, nxt = cards[0], cards[1]
        title, h1 = L.t("lp_pas_title"), L.t("lp_pas_h1")
        lede = L.t("lp_pas_lede", best=f"{pasivas._t(best['name'], L)} ({pasivas._pct(best['coin'], L, 0)})",
                   next=f"{pasivas._t(nxt['name'], L)} ({pasivas._pct(nxt['coin'], L, 0)})")
        note = L.t("lp_pas_note")
        desc = L.t("lp_pas_desc", top=static_ficha._join(L, [pasivas._t(c["name"], L) for c in cards[:2]]))
        body = (f'<section class="ql-list"><h2>{escape(top_h)}</h2>{_passives_html(L)}'
                f'<p><a href="{home}pasivas.html">{escape(L.t("lp_pas_link"))} →</a></p></section>')
    else:
        top = static_ficha._join(L, [L.mon(p) for p, _, _ in rows[:LEDE_NAMES]])
        if page.key == "best":
            title, h1 = L.t("lp_best_title"), L.t("lp_best_h1")
            lede = L.t("lp_best_lede", top=top, n=TOP_BEST)
            desc = L.t("lp_best_desc", n=TOP_BEST, top=top)
        elif page.key == "starters":
            title, h1 = L.t("lp_start_title"), L.t("lp_start_h1")
            lede = L.t("lp_start_lede", top=top)
            note = L.t("lp_start_note")
            desc = L.t("lp_start_desc", top=top)
        elif page.key == "legendary":
            title, h1 = L.t("lp_leg_title"), L.t("lp_leg_h1")
            lede = L.t("lp_leg_lede", top=top, n=len(members), s=s)
            desc = L.t("lp_leg_desc", n=len(members), top=top)
        else:
            tname = L.type_name(_type_key(page))
            types = [_type_key(page)]
            title, h1 = L.t("lp_type_title", type=tname), L.t("lp_type_h1", type=tname)
            lede = L.t("lp_type_lede", type=tname, top=top, n=len(members), s=s)
            desc = L.t("lp_type_desc", type=tname, top=top)
        body = f'<section class="ql-list"><h2>{escape(top_h)}</h2>{_list_html(L, home, rows)}</section>'
    content = (f'<div class="ql"><h1>{escape(h1)}</h1>'
               f'<p class="ql-lede">{escape(lede)}</p><p class="ql-note">{escape(note)}</p>'
               f'<p class="fresh">{escape(legal.freshness_text(L, meta))}</p>'
               f'{body}{guides_nav(L, home, types=types, skip=page.key)}</div>')
    return Built(title=title, desc=desc, h1=h1, content=content, jsonld=_jsonld(L, page, title, desc, rows, meta),
                 alternates=alternates(page))
