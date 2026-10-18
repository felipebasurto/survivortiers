"""Tier list de las cartas de nivel de PokéSurvivor, en español e inglés.

Los porcentajes son la mediana, entre 150 Pokémon, de cuánto alarga la supervivencia priorizar esa carta
(grupo fijo 2+2, 100 partidas). Cada texto es una pareja (es, en).
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

from i18n import Lang

DATA = Path(__file__).resolve().parent.parent / "data"
ICONS = json.loads((DATA / "card_icons.json").read_text(encoding="utf8"))
ITEM_ICONS = json.loads((DATA / "item_icons.json").read_text(encoding="utf8"))
MOVE_ICONS = json.loads((DATA / "move_icons.json").read_text(encoding="utf8"))
ICON_LETTERS = "abcdefghijklmnopqrstuvwxyz"

PHASES = [
    ("early", ("Al empezar", "At the start"), ("La primera carta.", "The first card.")),
    ("mid", ("A mitad", "Midway"), ("El orden se queda.", "The order holds.")),
    ("late", ("Si duras", "If it lasts"), ("Síntesis se aleja.", "Synthesis pulls ahead.")),
]
TIER_ORDER = ["S", "A", "B", "C", "D"]

# tiers = (al empezar, a mitad, si duras). El orden de cogida no cambia con la fase:
# Síntesis se aleja, el resto no la adelanta.
CARDS = [
    {
        "id": "rgn", "name": ("Síntesis", "Synthesis"), "tiers": ("S", "S", "S"), "lift": "+6%",
        "tip": ("La primera. En las partidas que duran, aún más.",
                "First. On the runs that last, even more."),
    },
    {
        "id": "heal", "name": ("Baya Zidra", "Sitrus Berry"), "tiers": ("A", "A", "A"), "lift": "+4%",
        "tip": ("45% de vida al momento. En cuerpo a cuerpo, antes que Síntesis.",
                "45% HP on the spot. On melee, before Synthesis."),
    },
    {
        "id": "hp", "name": ("Vigor", "Vigor"), "tiers": ("A", "A", "A"), "lift": "+3%",
        "tip": ("Justo después de Síntesis. No tiene tope.",
                "Right after Synthesis. No cap."),
    },
    {
        "id": "atk", "name": ("Potencia", "Power"), "tiers": ("B", "B", "B"), "lift": "0",
        "tip": ("El grupo ya pega. No la pongas delante.",
                "The group already hits. Do not put it first."),
    },
    {
        "id": "def", "name": ("Coraza", "Armor"), "tiers": ("C", "C", "C"), "lift": "0",
        "tip": ("Poca subida. Con el chaleco, el 70% se come las dos.",
                "Small bump. The vest shares a 70% cap with it."),
    },
    {
        "id": "cd", "name": ("Reflejos", "Reflexes"), "tiers": ("C", "C", "C"), "lift": "0",
        "tip": ("Órbita, torreta y estela no la usan al golpear.",
                "Orbit, turret and trail ignore it on the hit."),
    },
    {
        "id": "spd", "name": ("Carrera", "Sprint"), "tiers": ("C", "C", "C"), "lift": "0",
        "tip": ("Correr más no esquiva en esta prueba.",
                "Running faster does not dodge in this test."),
    },
    {
        "id": "xp", "name": ("Aprendizaje", "Learning"), "tiers": ("D", "D", "D"), "lift": "−2%",
        "tip": ("Unos niveles de más, y dejas Síntesis.",
                "A few extra levels, and you skip Synthesis."),
    },
    {
        "id": "mag", "name": ("Imán", "Magnet"), "tiers": ("D", "D", "D"), "lift": "−2%",
        "tip": ("La experiencia cae al matar. El radio no cuenta.",
                "Experience lands on the kill. Radius does nothing."),
    },
]

# Lo que suma priorizar la carta cuando ya llevas el objeto (no el objeto solo).
COMBOS = [
    {"item": "shellbell", "item_name": ("Cascabel", "Shell Bell"), "card": "rgn", "lift": "+3%",
     "why": ("Cura el 4% del daño que haces, hasta 4 de vida por segundo.",
             "Heals 4% of the damage you deal, up to 4 HP per second.")},
    {"item": "leftovers", "item_name": ("Restos", "Leftovers"), "card": "rgn", "lift": "+3%",
     "why": ("Recupera un 1,5% de tu vida máxima por segundo.",
             "Recovers 1.5% of your max HP per second.")},
    {"item": "leftovers", "item_name": ("Restos", "Leftovers"), "card": "hp", "lift": "+3%",
     "why": ("Lo mismo, y escala con tu vida máxima.",
             "The same, and it scales with your max HP.")},
    {"item": "assaultvest", "item_name": ("Chaleco", "Assault Vest"), "card": "def", "lift": "0",
     "why": ("Chaleco y Coraza comparten el tope del 70% de reducción: no alarga nada.",
             "Vest and Armor share the 70% reduction cap, so it adds no time.")},
    {"item": "choiceband", "item_name": ("Cinta", "Choice Band"), "card": "cd", "lift": "−1%",
     "why": ("Ya sube el daño un 40%. Reflejos solo acorta la recarga, y cogerla antes deja fuera una carta de vida.",
             "Already adds 40% damage. Reflexes only shortens cooldown, and taking it first crowds out an HP card.")},
    {"item": "quickclaw", "item_name": ("Garra", "Quick Claw"), "card": "cd", "lift": "0",
     "why": ("Ya baja un 20% la recarga, así que Reflejos no suma tiempo.",
             "Already cuts cooldown 20%, so Reflexes adds no time.")},
]
COMBO_HEAD = (("Objeto", "Item"), ("Carta", "Card"), ("Suma", "Adds"), ("Por qué", "Why"))

# Qué significa el porcentaje de cada fila (mediana, 150 Pokémon, grupo 2+2, 100 partidas).
MEAN = ("Cuánto más aguantas con el objeto si priorizas la carta. Mediana de 150 Pokémon, grupo fijo 2+2, 100 partidas.",
        "How much longer you last with the item if you prioritize the card. Median of 150 Pokémon, fixed 2+2 group, 100 runs.")

ORDER = ["rgn", "hp", "heal", "atk"]

NOTE = ("Simulación: el bot no esquiva, así que la vida y la curación cuentan más. "
        "Una carta que evoluciona tu ataque va siempre primera.",
        "Simulated: the bot never dodges, so HP and healing count for more. "
        "A card that evolves your move always goes first.")

# rule: el orden que cambia, con las cartas entre llaves ({id}), que se dibujan con su icono.
EXCEPTIONS = [
    {"k": ("Cono", "Cone"), "moves": ["flamethrower"], "ex": ("Lanzallamas", "Flamethrower"),
     "rule": ("{rgn} sube aún más", "{rgn} climbs even higher"),
     "why": ("Hay que acercarse para que llegue, y su regeneración no tiene tope: aguanta los golpes.",
             "You have to get close for it to land, and its regen has no cap: it soaks up hits.")},
    {"k": ("Órbita", "Orbit"), "moves": ["fire-spin"], "ex": ("Giro Fuego", "Fire Spin"),
     "rule": ("{hp} antes que {rgn}, {cd} no suma", "{hp} before {rgn}, {cd} adds nothing"),
     "why": ("Vigor da la vida al momento, y el tiempo entre golpes es el del ataque: Reflejos no lo cambia.",
             "Vigor heals right away, and the gap between hits is the move's own cooldown, which Reflexes does not change.")},
    {"k": ("Aura", "Aura"), "moves": ["discharge"], "ex": ("Chispazo", "Discharge"),
     "rule": ("Ninguna carta alarga la partida", "No card lengthens the run"),
     "why": ("La partida se acaba antes de que la mejora llegue a notarse.",
             "The run ends before the bonus has time to show.")},
    {"k": ("Torreta y estela", "Turret and trail"), "moves": ["will-o-wisp", "toxic"],
     "ex": ("Fuego Fatuo · Tóxico", "Will-O-Wisp · Toxic"),
     "rule": ("{cd} no suma", "{cd} adds nothing"),
     "why": ("Ni los tiros de la torreta ni los charcos usan esa recarga.",
             "Neither the turret's shots nor the puddles use that cooldown.")},
    {"k": ("Cuerpo a cuerpo", "Melee"), "moves": ["tackle"], "ex": ("Placaje", "Tackle"),
     "rule": ("{heal} va primera", "{heal} goes first"),
     "why": ("Tienes que estar encima para pegar, y cura un 45% al momento: rinde más que ir sumando Síntesis.",
             "You have to stand on the enemy to hit. It heals 45% on the spot, which beats stacking Synthesis.")},
]
EXCEPTION_MOVES = sorted({m for row in EXCEPTIONS for m in row["moves"]})


def _t(pair: tuple[str, str], L: Lang) -> str:
    return pair[1] if L.en else pair[0]


def _symbols() -> str:
    out = []
    packs = ([(f"card-{k}", v) for k, v in ICONS.items()] + [(f"item-{k}", v) for k, v in ITEM_ICONS.items()]
             + [(f"move-{k}", MOVE_ICONS[k]) for k in EXCEPTION_MOVES])
    for sid, ic in packs:
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
        out.append(f'<symbol id="pv-{sid}" viewBox="0 0 {w} {h}">{"".join(rects)}</symbol>')
    return ('<svg class="sprites-defs" width="0" height="0" aria-hidden="true" focusable="false">'
            + "".join(out) + "</svg>")


def _icon(kind: str, item_id: str, big: bool = False) -> str:
    cls = "pv-ico" if big else "item-ico"
    return (f'<svg class="{cls}" viewBox="0 0 12 12" aria-hidden="true" focusable="false" '
            f'shape-rendering="crispEdges"><use href="#pv-{kind}-{item_id}"/></svg>')


def _badge(t: str) -> str:
    return f'<span class="tier-badge {t}">{t}</span>'


def _by_id(card_id: str) -> dict:
    return next(c for c in CARDS if c["id"] == card_id)


def _phase(L: Lang, idx: int, name: tuple[str, str], note: tuple[str, str]) -> str:
    rows = []
    for tier in TIER_ORDER:
        if not any(c["tiers"][idx] == tier for c in CARDS):
            continue
        chips = "".join(
            f'<span class="ph-chip">{_icon("card", c["id"])}{escape(_t(c["name"], L))}</span>'
            for c in CARDS if c["tiers"][idx] == tier)
        rows.append(f'<li>{_badge(tier)}<span class="ph-chips">{chips}</span></li>')
    return (f'<section class="ph"><h2>{escape(_t(name, L))}</h2>'
            f'<p class="muted small">{escape(_t(note, L))}</p>'
            f'<ul class="ph-list">{"".join(rows)}</ul></section>')


def _hand(L: Lang) -> str:
    tiles = []
    for c in CARDS:
        tiles.append(
            f'<li class="pv-tile t-{c["tiers"][0]}">'
            f'{_icon("card", c["id"], big=True)}'
            f'<span class="pv-name">{escape(_t(c["name"], L))}</span>'
            f'<span class="pv-meta">{_badge(c["tiers"][0])}<b class="pv-lift">{escape(c["lift"])}</b></span>'
            f'<span class="pv-tip">{escape(_t(c["tip"], L))}</span>'
            f'</li>')
    return f'<ol class="pv-hand">{"".join(tiles)}</ol>'


def _order(L: Lang) -> str:
    steps = []
    for i, cid in enumerate(ORDER, start=1):
        c = _by_id(cid)
        steps.append(
            f'<li><span class="pv-n">{i}</span>{_icon("card", cid, big=True)}'
            f'<span>{escape(_t(c["name"], L))}</span></li>')
    return f'<ol class="pv-order">{"".join(steps)}</ol>'


def _cref(card_id: str, L: Lang) -> str:
    return (f'<span class="pv-cref">{_icon("card", card_id)}'
            f'{escape(_t(_by_id(card_id)["name"], L))}</span>')


def _rule(text: str, L: Lang) -> str:
    parts = re.split(r"\{(\w+)\}", text)
    return "".join(escape(p) if i % 2 == 0 else _cref(p, L) for i, p in enumerate(parts))


def _lift_class(lift: str) -> str:
    if lift.startswith(("−", "-")):
        return "pv-chip pv-down"
    return "pv-chip pv-up" if lift.startswith("+") else "pv-chip"


def _combos(L: Lang) -> str:
    head = "".join(f'<th scope="col" class="{cls}">{escape(_t(h, L))}</th>'
                   for h, cls in zip(COMBO_HEAD, ("pv-c-item", "pv-c-card", "pv-c-lift", "pv-c-why")))
    rows = []
    for row in COMBOS:
        rows.append(
            f'<tr>'
            f'<td class="pv-c-item"><span class="pv-cell">{_icon("item", row["item"])}'
            f'{escape(_t(row["item_name"], L))}</span></td>'
            f'<td class="pv-c-card"><span class="pv-cell">{_icon("card", row["card"])}'
            f'{escape(_t(_by_id(row["card"])["name"], L))}</span></td>'
            f'<td class="pv-c-lift"><span class="{_lift_class(row["lift"])}">{escape(row["lift"])}</span></td>'
            f'<td class="pv-why">{escape(_t(row["why"], L))}</td></tr>')
    return (f'<p class="pv-mean">{escape(_t(MEAN, L))}</p>'
            f'<div class="pv-wrap"><table class="pv-table"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def _exceptions(L: Lang) -> str:
    cards = []
    for row in EXCEPTIONS:
        icons = "".join(_icon("move", m, big=True) for m in row["moves"])
        cards.append(
            f'<li class="pv-card">'
            f'<div class="pv-kh"><span class="pv-kicons">{icons}</span>'
            f'<div><h3 class="pv-k">{escape(_t(row["k"], L))}</h3>'
            f'<p class="pv-ex">{escape(_t(row["ex"], L))}</p></div></div>'
            f'<p class="pv-rule">{_rule(_t(row["rule"], L), L)}</p>'
            f'<p class="pv-why">{escape(_t(row["why"], L))}</p></li>')
    return "".join(cards)


def content(L: Lang, h1: str, lede: str, order_h: str, phases_h: str, items_h: str, except_h: str) -> str:
    phases = "".join(_phase(L, i, name, note) for i, (_, name, note) in enumerate(PHASES))
    return (_symbols()
            + f'<h1>{escape(h1)}</h1>'
            + f'<p class="lede">{escape(lede)}</p>'
            + f'<h2>{escape(order_h)}</h2>'
            + _order(L)
            + _hand(L)
            + f'<h2>{escape(phases_h)}</h2>'
            + f'<div class="ph-grid">{phases}</div>'
            + f'<h2>{escape(except_h)}</h2>'
            + f'<ul class="pv-except">{_exceptions(L)}</ul>'
            + f'<h2>{escape(items_h)}</h2>'
            + _combos(L)
            + f'<p class="pv-note">{escape(_t(NOTE, L))}</p>')
