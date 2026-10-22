"""Habilidades: las 271 habilidades de game.json con su efecto tal como lo define el juego y qué especies la tienen.

Los efectos salen de data/abilities.json (build/ability_export.py, js/data/ability-fx.js del juego en el commit
fijado), los mismos que usaba pasivas.html. Las especies salen de simulator/data/game.json (dex[].abilities;
un 0 es un hueco sin habilidad). Cada texto es una pareja (es, en).
"""
from __future__ import annotations

from html import escape

import slugs
from bounded_view import ABIL, GAME

TXT = {
    "h1": ("Habilidades", "Abilities"),
    "lede": ("Las {n} habilidades de PokéSurvivor y lo que hace cada una en el juego, con las especies que pueden "
             "tenerla. Las {g} sin efecto propio dan la pasiva genérica: +8 % de daño con los movimientos del tipo "
             "principal.",
             "The {n} abilities in PokéSurvivor and what each one does in the game, with the species that can have "
             "it. The {g} without an effect of their own give the generic passive: +8 % damage with moves of the "
             "main type."),
    "src": ("Fuente: js/data/ability-fx.js del código del juego (commit {c}), exportado en data/abilities.json; "
            "especies de game.json.",
            "Source: js/data/ability-fx.js in the game code (commit {c}), exported to data/abilities.json; species "
            "from game.json."),
    "search": ("Buscar habilidad, efecto o Pokémon", "Search ability, effect or Pokémon"),
    "none": ("Ninguna habilidad coincide.", "No ability matches."),
    "col": ("Habilidad", "Ability"), "eff": ("Efecto", "Effect"), "sp": ("Especies", "Species"),
    "generic": ("Pasiva genérica: +8 % de daño con los movimientos de su tipo principal.",
                "Generic passive: +8 % damage with moves of its main type."),
    "plus": (" Además, la pasiva genérica de su tipo.", " Also the generic passive of its type."),
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
    eff = (a["en"] or a["es"]) if L.en else a["es"]
    return eff + (t(L, "plus") if a["plus"] else "")


def content(L, home: str, index: list[dict]) -> str:
    """index: public/pokemon-index.json, para el nombre en inglés que da la ruta de cada ficha."""
    name_en = {p["dex"]: p["nameEn"] for p in index}
    i = 1 if L.en else 0
    rows = []
    for aid, a in sorted(ABIL.items(), key=lambda kv: kv[1]["n"][i]):
        sp = SPECIES.get(aid, [])
        eff = effect(L, a)
        links = ", ".join(f'<a href="{home}pokemon/{slugs.species_path(d["dex"], name_en[d["dex"]])}/">{escape(d["name"])}</a>'
                          for d in sp)
        if not sp:
            cell = escape(t(L, "nosp"))
        elif len(sp) <= 6:
            cell = links
        else:
            cell = f'<details><summary>{escape(t(L, "nsp", n=len(sp)))}</summary>{links}</details>'
        q = " ".join([a["n"][0], a["n"][1], eff] + [d["name"] for d in sp]).lower()
        lang = ' lang="es"' if L.en and not a["generic"] and not a["en"] else ""
        rows.append(f'<tr class="lab-row" id="{escape(aid)}" data-q="{escape(q)}"><th scope="row">{escape(a["n"][i])}</th>'
                    f'<td{lang} data-label="{escape(t(L, "eff"))}">{escape(eff)}</td>'
                    f'<td data-label="{escape(t(L, "sp"))}">{cell}</td></tr>')
    icon = ('<svg class="search-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><circle cx="7" cy="7" '
            'r="4.6" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10.6 10.6 14.5 14.5" '
            'stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>')
    gen = sum(1 for a in ABIL.values() if a["generic"])
    return (f'<div class="pv"><h1>{escape(t(L, "h1"))}</h1>'
            f'<p class="lede">{escape(t(L, "lede", n=len(ABIL), g=gen))}</p>'
            f'<p class="pv-cap">{escape(t(L, "src", c=GAME["gameCommit"][:7]))}</p>'
            f'<div class="search-field mv-finder">{icon}<input id="mv-q" type="search" autocomplete="off" '
            f'placeholder="{escape(t(L, "search"))}" aria-label="{escape(t(L, "search"))}"></div>'
            f'<p id="mv-none" class="mv-none" hidden>{escape(t(L, "none"))}</p>'
            f'<section class="pv-abilities"><div class="nat-table"><table><thead><tr>'
            f'<th scope="col">{escape(t(L, "col"))}</th><th scope="col">{escape(t(L, "eff"))}</th>'
            f'<th scope="col">{escape(t(L, "sp"))}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            f'</section></div>')
