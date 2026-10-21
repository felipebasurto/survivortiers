"""Objetos de PokéSurvivor en español e inglés: qué hace cada uno según el código del juego, agrupados por efecto.

Los efectos salen de js/data/items.js, js/entities/player.js y js/systems/combat.js. El bot de la simulación no lleva
objeto, así que no hay tier ni recomendación. Cada texto es una pareja (es, en).
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

from i18n import Lang

DATA = Path(__file__).resolve().parent.parent / "data"
# Dibujos de los objetos tal y como los pinta el juego (scripts: build/export_move_icons.js → data/item_icons.json).
ICONS = json.loads((DATA / "item_icons.json").read_text(encoding="utf8"))
ICON_LETTERS = "abcdefghijklmnopqrstuvwxyz"  # rows[y][x] es '.' o la letra de su color en pal

GROUPS = [
    ("damage", ("Daño", "Damage")),
    ("defense", ("Defensa", "Defense")),
    ("heal", ("Curación", "Healing")),
    ("speed", ("Velocidad y recarga", "Speed and cooldown")),
    ("progress", ("Progreso", "Progress")),
]

# fact: el detalle del código del juego que el efecto no dice (archivo:línea en el commit de legal.GAME_COMMIT).
ITEMS = [
    {"id": "choiceband", "group": "damage", "name": ("Cinta Elección", "Choice Band"),
     "effect": ("+40 % de daño, pero no puedes cambiar de movimiento.", "+40% damage, but you cannot switch moves.")},
    {"id": "lifeorb", "group": "damage", "name": ("Vidasfera", "Life Orb"),
     "effect": ("+30 % de daño, pero cada ataque te quita un poco de vida.", "+30% damage, but each attack costs you some HP."),
     "fact": ("Cada ataque cuesta el 1 % de tu vida máxima y nunca te deja KO. Las órbitas y las estelas no cuestan.",
              "Each attack costs 1% of your max HP and never knocks you out. Orbits and trails cost nothing.")},
    {"id": "assaultvest", "group": "defense", "name": ("Chaleco Asalto", "Assault Vest"),
     "effect": ("+20 % de reducción de daño recibido.", "+20% damage reduction.")},
    {"id": "rockyhelmet", "group": "defense", "name": ("Casco Dentado", "Rocky Helmet"),
     "effect": ("Los que te golpean cuerpo a cuerpo reciben daño.", "Enemies that hit you in melee take damage."),
     "fact": ("Devuelve 15 + 4 × tu nivel: 135 a nivel 30.", "Hits back 15 + 4 × your level: 135 at level 30.")},
    {"id": "focussash", "group": "defense", "name": ("Banda Focus", "Focus Sash"),
     "effect": ("Un golpe que te dejaría KO te deja con 1 de vida.", "A hit that would KO you leaves you at 1 HP."),
     "fact": ("Una vez cada 60 s.", "Once every 60 s.")},
    {"id": "leftovers", "group": "heal", "name": ("Restos", "Leftovers"),
     "effect": ("Recuperas un 1,5 % de tu vida máxima por segundo.", "Recover 1.5% of your max HP per second."),
     "fact": ("La cura se calcula con tu vida máxima al equiparlo.", "The heal uses your max HP when you equip it.")},
    {"id": "shellbell", "group": "heal", "name": ("Cascabel Concha", "Shell Bell"),
     "effect": ("Recuperas vida con el daño que haces.", "Heal from the damage you deal."),
     "fact": ("Cura el 4 % del daño que haces, hasta 4 de vida por segundo.",
              "Heals 4% of the damage you deal, up to 4 HP per second.")},
    {"id": "choicescarf", "group": "speed", "name": ("Pañuelo Elección", "Choice Scarf"),
     "effect": ("+35 % de velocidad.", "+35% speed.")},
    {"id": "quickclaw", "group": "speed", "name": ("Garra Rápida", "Quick Claw"),
     "effect": ("-20 % de recarga en todos tus movimientos.", "-20% cooldown on all your moves.")},
    {"id": "luckyegg", "group": "progress", "name": ("Huevo Suerte", "Lucky Egg"),
     "effect": ("+30 % de experiencia.", "+30% experience.")},
    {"id": "amuletcoin", "group": "progress", "name": ("Moneda Amuleto", "Amulet Coin"),
     "effect": ("Más Pokémonedas al acabar la partida. No cambia el combate.",
                "More Pokécoins when a run ends. It does not change combat.")},
]


def _t(pair: tuple[str, str], L: Lang) -> str:
    return pair[1] if L.en else pair[0]


def _symbols() -> str:
    """Un <symbol> por objeto, en rectángulos de píxeles del juego. Va una vez por página; los <use> lo referencian."""
    out = []
    for item_id, ic in ICONS.items():
        w, h = ic["size"]
        rects = []
        for y, row in enumerate(ic["rows"]):
            x = 0
            while x < w:
                ch = row[x]
                if ch == ".":
                    x += 1
                    continue
                run = 1
                while x + run < w and row[x + run] == ch:
                    run += 1
                color = ic["pal"][ICON_LETTERS.index(ch)]
                rects.append(f'<rect x="{x}" y="{y}" width="{run}" height="1" fill="{color}"/>')
                x += run
        out.append(f'<symbol id="ico-{item_id}" viewBox="0 0 {w} {h}">{"".join(rects)}</symbol>')
    return ('<svg class="sprites-defs" width="0" height="0" aria-hidden="true" focusable="false">'
            + "".join(out) + "</svg>")


def _icon(item_id: str) -> str:
    return (f'<svg class="item-ico" aria-hidden="true" focusable="false" shape-rendering="crispEdges">'
            f'<use href="#ico-{item_id}"/></svg>')


def _card(L: Lang, it: dict) -> str:
    fact = f'<p class="it-fact">{escape(_t(it["fact"], L))}</p>' if it.get("fact") else ""
    return (f'<li class="it-card">{_icon(it["id"])}<span class="it-txt"><b>{escape(_t(it["name"], L))}</b>'
            f'<span>{escape(_t(it["effect"], L))}</span>{fact}</span></li>')


def items_content(L: Lang, h1: str, lede: str) -> str:
    """Contenido de la página Objetos: un bloque por tipo de efecto, con lo que hace cada objeto."""
    groups = "".join(
        f'<section class="it-group"><h2>{escape(_t(name, L))}</h2>'
        f'<ul class="it-grid">{"".join(_card(L, it) for it in ITEMS if it["group"] == gid)}</ul></section>'
        for gid, name in GROUPS)
    return _symbols() + f'<h1>{escape(h1)}</h1><p class="lede">{escape(lede)}</p>{groups}'
