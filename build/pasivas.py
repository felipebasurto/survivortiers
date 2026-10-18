"""Tier list de las cartas de nivel de PokéSurvivor, en español e inglés.

Los porcentajes son la mediana, entre 150 Pokémon, de cuánto alarga la supervivencia priorizar esa carta
(grupo fijo 2+2, 100 partidas). Cada texto es una pareja (es, en).
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

from i18n import Lang

DATA = Path(__file__).resolve().parent.parent / "data"
ICONS = json.loads((DATA / "card_icons.json").read_text(encoding="utf8"))
ITEM_ICONS = json.loads((DATA / "item_icons.json").read_text(encoding="utf8"))
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
    {"item": "shellbell", "item_name": ("Cascabel", "Shell Bell"), "card": "rgn", "lift": "+3%"},
    {"item": "leftovers", "item_name": ("Restos", "Leftovers"), "card": "rgn", "lift": "+3%"},
    {"item": "leftovers", "item_name": ("Restos", "Leftovers"), "card": "hp", "lift": "+3%"},
    {"item": "assaultvest", "item_name": ("Chaleco", "Assault Vest"), "card": "def", "lift": "0",
     "why": ("El chaleco y Coraza entran en el mismo tope del 70% de reducción, así que priorizar "
             "Coraza con el chaleco puesto no alarga nada.",
             "The vest and Armor share the same 70% reduction cap, so prioritizing Armor while you "
             "wear the vest does not add time.")},
    {"item": "choiceband", "item_name": ("Cinta", "Choice Band"), "card": "cd", "lift": "−1%",
     "why": ("La cinta ya sube el daño un 40%. Reflejos solo acorta la recarga, y cogerla antes deja "
             "fuera una carta de vida, así que aguantas un poco menos.",
             "The band already adds 40% damage. Reflexes only shortens cooldown, and taking it first "
             "crowds out an HP card, so you last a little less.")},
    {"item": "quickclaw", "item_name": ("Garra", "Quick Claw"), "card": "cd", "lift": "0",
     "why": ("La garra ya baja un 20% la recarga. Con ella puesta, priorizar Reflejos no suma tiempo.",
             "The claw already cuts cooldown by 20%. With it equipped, prioritizing Reflexes does not add time.")},
]

# Qué significa el porcentaje de cada fila (mediana, 150 Pokémon, grupo 2+2, 100 partidas).
MEAN = ("Cuánto más aguantas si priorizas esa carta cuando ya llevas el objeto, frente a no priorizarla. "
        "Es la mediana entre 150 Pokémon, con un grupo fijo de 2+2 y 100 partidas.",
        "How much longer you last if you prioritize that card while you already hold the item, versus not "
        "prioritizing it. It is the median across 150 Pokémon, in a fixed 2+2 group, over 100 runs.")

ORDER = ["rgn", "hp", "heal", "atk"]

NOTE = ("Estos números salen de una simulación. El bot no esquiva nunca, así que la vida y la curación "
        "cuentan más que para quien sí esquiva. Si una carta evoluciona tu ataque, va siempre la primera.",
        "These numbers come from a simulation. The bot never dodges, so HP and healing count for more than "
        "they would for someone who does. A card that evolves your move always goes first.")

EXCEPTIONS = [
    {"k": ("Cono", "Cone"),
     "text": ("Un cono es un chorro en abanico que se queda corto, como Lanzallamas. Síntesis sube aún más "
              "en el orden: hay que acercarse para que llegue, y esa regeneración no tiene tope, así que aguanta los golpes.",
              "A cone is a short fan of shots, like Flamethrower. Synthesis climbs further up the order: you have to "
              "step in close for it to land, and that regen has no cap, so it soaks up the hits.")},
    {"k": ("Órbita", "Orbit"),
     "text": ("Una órbita son bolas que giran a tu alrededor y pegan solas, como Giro Fuego. Pon Vigor delante de "
              "Síntesis, que la vida entra al momento, y deja Reflejos: el tiempo entre golpes es el del ataque, y esa carta no lo cambia.",
              "An orbit is orbs that spin around you and hit on their own, like Fire Spin. Put Vigor ahead of Synthesis, "
              "since the HP lands right away, and skip Reflexes: the gap between hits is the move's own cooldown, and that card does not touch it.")},
    {"k": ("Aura", "Aura"),
     "text": ("Un aura es un pulso a tu alrededor que pega a todo lo cercano, como Chispazo. Ninguna carta alarga "
              "la partida: se acaba antes de que la mejora llegue a notarse.",
              "An aura is a pulse around you that hits everything nearby, like Discharge. No card makes the run last "
              "longer: it ends before the bonus has time to show.")},
    {"k": ("Torreta y estela", "Turret and trail"),
     "text": ("La torreta se queda disparando sola, como Fuego Fatuo, y la estela va dejando charcos al pasar, como Tóxico. "
              "Reflejos no suma: ni los tiros de la torreta ni el ritmo de los charcos usan esa recarga.",
              "A turret stays put and shoots on its own, like Will-O-Wisp, and a trail drops puddles as you move, like Toxic. "
              "Reflexes adds nothing: neither the turret's shots nor the puddle ticks use that cooldown.")},
    {"k": ("Cuerpo a cuerpo", "Melee"),
     "text": ("Si sales a cuerpo a cuerpo, como con Placaje, tienes que estar encima para pegar. La Baya Zidra va primera: "
              "cura un 45% al momento, y ahí eso rinde más que ir sumando Síntesis.",
              "If you start in melee, like Tackle, you have to stand on the enemy to hit. The Sitrus Berry goes first: "
              "it heals 45% on the spot, and that does more here than stacking Synthesis.")},
]


def _t(pair: tuple[str, str], L: Lang) -> str:
    return pair[1] if L.en else pair[0]


def _symbols() -> str:
    out = []
    packs = [(f"card-{k}", v) for k, v in ICONS.items()] + [(f"item-{k}", v) for k, v in ITEM_ICONS.items()]
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


def _combos(L: Lang) -> str:
    bits = []
    for row in COMBOS:
        item = _t(row["item_name"], L)
        card = _t(_by_id(row["card"])["name"], L)
        down = " pv-down" if row["lift"].startswith(("−", "-")) else ""
        why = row.get("why")
        why_html = f'<p class="pv-why">{escape(_t(why, L))}</p>' if why else ""
        bits.append(
            f'<li class="pv-combo">'
            f'<span class="pv-names">{_icon("item", row["item"])}{escape(item)}'
            f'<span class="pv-plus">+</span>{_icon("card", row["card"])}{escape(card)}</span>'
            f'<b class="pv-lift{down}">{escape(row["lift"])}</b>{why_html}</li>')
    return f'<p class="pv-mean">{escape(_t(MEAN, L))}</p><ul class="pv-combos">{"".join(bits)}</ul>'


def _exceptions(L: Lang) -> str:
    return "".join(
        f'<li><span class="pv-k">{escape(_t(row["k"], L))}</span>'
        f'<p>{escape(_t(row["text"], L))}</p></li>'
        for row in EXCEPTIONS)


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
            + f'<ul class="plain pv-except">{_exceptions(L)}</ul>'
            + f'<h2>{escape(items_h)}</h2>'
            + _combos(L)
            + f'<p class="note small">{escape(_t(NOTE, L))}</p>')
