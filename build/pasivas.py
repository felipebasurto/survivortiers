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
    {"item": "assaultvest", "item_name": ("Chaleco", "Assault Vest"), "card": "def", "lift": "0"},
    {"item": "choiceband", "item_name": ("Cinta", "Choice Band"), "card": "cd", "lift": "−1%"},
    {"item": "quickclaw", "item_name": ("Garra", "Quick Claw"), "card": "cd", "lift": "0"},
]

ORDER = ["rgn", "hp", "heal", "atk"]

NOTE = ("Tiempos estimados. El bot no esquiva, así que vida y curación son un techo. "
        "Si la carta evoluciona tu ataque, va la primera.",
        "Times are estimates. The bot does not dodge, so HP and healing are a ceiling. "
        "If a card evolves your move, it goes first.")

EXCEPTIONS = [
    ("Cono: Síntesis sube más.", "Cone: Synthesis climbs more."),
    ("Órbita: Vigor por delante. Reflejos no entra.", "Orbit: Vigor ahead. Reflexes does nothing."),
    ("Aura: ninguna carta alarga.", "Aura: no card adds time."),
    ("Torreta y estela: Reflejos no suma.", "Turret and trail: Reflexes adds nothing."),
    ("Cuerpo a cuerpo de salida: la baya primero.", "Melee starter: the berry first."),
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
        label = _t(row["item_name"], L)
        bits.append(
            f'<li class="pv-combo">{_icon("item", row["item"])}'
            f'<span class="pv-plus">+</span>{_icon("card", row["card"])}'
            f'<b>{escape(row["lift"])}</b>'
            f'<span class="pv-combo-name">{escape(label)}</span></li>')
    return f'<ul class="pv-combos">{"".join(bits)}</ul>'


def _exceptions(L: Lang) -> str:
    return "".join(f"<li>{escape(_t(pair, L))}</li>" for pair in EXCEPTIONS)


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
