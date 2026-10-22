"""Habilidades: las 271 habilidades de game.json con su efecto tal como lo define el juego y qué especies la tienen.

Los efectos salen de data/abilities.json (build/ability_export.py, js/data/ability-fx.js del juego en el commit
fijado), los mismos que usaba pasivas.html. Las especies salen de simulator/data/game.json (dex[].abilities;
un 0 es un hueco sin habilidad). Cada texto es una pareja (es, en).
"""
from __future__ import annotations

from html import escape

import slugs
from bounded_view import ABIL, GAME
from i18n import NBSP

TXT = {
    "h1": ("Habilidades", "Abilities"),
    "search": ("Buscar habilidad, efecto o Pokémon", "Search ability, effect or Pokémon"),
    "none": ("Ninguna habilidad coincide.", "No ability matches."),
    "generic": ("Pasiva genérica: +8 % de daño con los movimientos de su tipo principal.",
                "Generic passive: +8 % damage with moves of its main type."),
    "plus": ("Pasiva genérica del tipo", "Generic type passive"),
    "nosp": ("ninguna", "none"),
    "nsp": ("{n} especies", "{n} species"),
}


def t(L, k: str, **kw) -> str:
    return TXT[k][1 if L.en else 0].format(**kw)


def species_by_ability() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {a: [] for a in ABIL}
    for d in GAME["dex"]:
        for a in dict.fromkeys(x for x in d["abilities"] if x):
            out.setdefault(a, []).append(d)
    return out


SPECIES = species_by_ability()


def effect(L, a: dict) -> str:
    if a["generic"]:
        return t(L, "generic")
    return (a["en"] or a["es"]) if L.en else a["es"]


def _plus(L, a: dict) -> str:
    if not a["plus"] or a["generic"]:
        return ""
    mark = "+8%" if L.en else "+8" + NBSP + "%"
    return f'<b class="ab-plus" title="{escape(t(L, "plus"))}">{mark}</b>'


def _label(L, mon: dict) -> str:
    return mon["nameEn"] if L.en else mon["name"]


def _species(L, home: str, by_dex: dict, sp: list[dict]) -> str:
    links = ", ".join(
        f'<a href="{home}pokemon/{slugs.species_path(d["dex"], by_dex[d["dex"]]["nameEn"])}/">'
        f'{escape(_label(L, by_dex[d["dex"]]))}</a>' for d in sp)
    if not sp:
        return f'<span class="ab-sp">{escape(t(L, "nosp"))}</span>'
    if len(sp) <= 4:
        return f'<span class="ab-sp">{links}</span>'
    return f'<details class="ab-sp"><summary>{escape(t(L, "nsp", n=len(sp)))}</summary>{links}</details>'


def content(L, home: str, index: list[dict]) -> str:
    """index: public/pokemon-index.json, para el nombre de cada ficha en este idioma."""
    by_dex = {p["dex"]: p for p in index}
    i = 1 if L.en else 0
    custom, generic = [], []
    for aid, a in sorted(ABIL.items(), key=lambda kv: kv[1]["n"][i]):
        sp = SPECIES.get(aid, [])
        eff = effect(L, a)
        names = [n for d in sp for n in (by_dex[d["dex"]]["name"], by_dex[d["dex"]]["nameEn"])]
        extra = t(L, "plus") if a["plus"] and not a["generic"] else ""
        q = " ".join([a["n"][0], a["n"][1], eff, extra, *names]).lower()
        who = _species(L, home, by_dex, sp)
        if a["generic"]:
            generic.append(f'<li class="ab-chip lab-row" id="{escape(aid)}" data-q="{escape(q)}">'
                           f'<b>{escape(a["n"][i])}</b>{who}</li>')
            continue
        lang = ' lang="es"' if L.en and not a["en"] else ""
        custom.append(f'<li class="ab-card lab-row" id="{escape(aid)}" data-q="{escape(q)}">'
                      f'<h3>{escape(a["n"][i])}{_plus(L, a)}</h3><p{lang}>{escape(eff)}</p>{who}</li>')
    icon = ('<svg class="search-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><circle cx="7" cy="7" '
            'r="4.6" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10.6 10.6 14.5 14.5" '
            'stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>')
    return (f'<div class="pv"><h1>{escape(t(L, "h1"))}</h1>'
            f'<div class="search-field mv-finder">{icon}<input id="mv-q" type="search" autocomplete="off" '
            f'placeholder="{escape(t(L, "search"))}" aria-label="{escape(t(L, "search"))}"></div>'
            f'<p id="mv-none" class="mv-none" hidden>{escape(t(L, "none"))}</p>'
            f'<ul class="ab-cards">{"".join(custom)}</ul>'
            f'<p class="ab-generic">{escape(t(L, "generic"))}</p>'
            f'<ul class="ab-chips">{"".join(generic)}</ul></div>')
