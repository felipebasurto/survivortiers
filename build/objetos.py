"""Tier list de objetos de PokéSurvivor por fase de la partida, en español e inglés.

Es una estimación a partir del código del juego (js/data/items.js, js/entities/player.js, js/systems/combat.js y
js/systems/levelup.js), no un resultado medido con partidas simuladas. Cada texto es una pareja (es, en).
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

PHASES = [
    ("early", ("Temprano", "Early"), ("0–5 min", "0–5 min")),
    ("mid", ("Medio", "Mid"), ("5–10 min", "5–10 min")),
    ("late", ("Tardío", "Late"), ("10 min o más", "10+ min")),
]
TIER_ORDER = ["S", "A", "B", "C"]

# tiers = (temprano, medio, tardío); "-" = no entra en esa fase
ITEMS = [
    {
        "id": "choiceband", "name": ("Cinta Elección", "Choice Band"), "tiers": ("S", "A", "A"),
        "effect": ("+40 % de daño, pero no puedes cambiar de movimiento.",
                   "+40% damage, but you cannot switch moves."),
        "reason": (
        "Con cuatro movimientos fijos no pierdes nada. Si cambias de ataque a menudo, sí. Mediana +12 % (estimación).",
        "With four fixed moves you lose nothing. If you switch attacks often, you do. Median +12% (estimate)."),
    },
    {
        "id": "luckyegg", "name": ("Huevo Suerte", "Lucky Egg"), "tiers": ("S", "S", "A"),
        "effect": ("+30 % de experiencia.", "+30% experience."),
        "reason": (
        "Más niveles, más cartas. Con ×3,2 de XP, a los 10 min pasas de 39 a 62 niveles.",
        "More levels, more cards. At ×3.2 XP, you go from 39 to 62 levels at 10 min."),
    },
    {
        "id": "choicescarf", "name": ("Pañuelo Elección", "Choice Scarf"), "tiers": ("S", "A", "B"),
        "effect": ("+35 % de velocidad.", "+35% speed."),
        "reason": (
        "Te saca del enjambre antes de tener defensa. Vale menos si matas rápido.",
        "Gets you out of the swarm before you have defence. Worth less if you kill fast."),
    },
    {
        "id": "quickclaw", "name": ("Garra Rápida", "Quick Claw"), "tiers": ("A", "A", "A"),
        "effect": ("-20 % de recarga en todos tus movimientos.", "-20% cooldown on all your moves."),
        "reason": (
        "Recarga más rápida para todo tu arsenal, sea cual sea el ataque.",
        "Faster cooldowns for your whole arsenal, whatever the attack."),
    },
    {
        "id": "lifeorb", "name": ("Vidasfera", "Life Orb"), "tiers": ("B", "C", "C"),
        "effect": ("+30 % de daño, pero cada ataque te quita un poco de vida.",
                   "+30% damage, but each attack costs you some HP."),
        "reason": (
        "Cada ataque te quita el 1 % de tu vida máxima. Con varios ataques, se acumula.",
        "Each attack costs 1% of your max HP. With several attacks, it adds up."),
    },
    {
        "id": "assaultvest", "name": ("Chaleco Asalto", "Assault Vest"), "tiers": ("B", "A", "B"),
        "effect": ("+20 % de reducción de daño recibido.", "+20% damage reduction."),
        "reason": (
        "Vale más mientras tu reducción total esté lejos del tope del 80 %. Las cartas Coraza lo acercan.",
        "Worth more while your total reduction is far from the 80% cap. Armor cards get you there faster."),
    },
    {
        "id": "rockyhelmet", "name": ("Casco Dentado", "Rocky Helmet"), "tiers": ("B", "A", "A"),
        "effect": ("Los que te golpean cuerpo a cuerpo reciben daño.",
                   "Enemies that hit you in melee take damage."),
        "reason": (
        "Devuelve 15 + 4 × tu nivel a quien te toca: 135 a nivel 30. Mediana +3 % (estimación).",
        "Hits back 15 + 4 × your level at whoever touches you: 135 at level 30. Median +3% (estimate)."),
    },
    {
        "id": "leftovers", "name": ("Restos", "Leftovers"), "tiers": ("C", "B", "B"),
        "effect": ("Recuperas un 1,5 % de tu vida máxima por segundo.",
                   "Recover 1.5% of your max HP per second."),
        "reason": (
        "Mediana +28 % (estimación). El bot no esquiva, así que es un techo. Escala con tu vida máxima.",
        "Median +28% (estimate). The bot doesn't dodge, so treat it as a ceiling. It scales with max HP."),
    },
    {
        "id": "shellbell", "name": ("Cascabel Concha", "Shell Bell"), "tiers": ("A", "B", "C"),
        "effect": ("Recuperas vida con el daño que haces.", "Heal from the damage you deal."),
        "reason": (
        "Cura el 4 % del daño que haces, con tope de 4 de vida por segundo. Mediana +36 % (estimación).",
        "Heals 4% of the damage you deal, capped at 4 HP per second. Median +36% (estimate)."),
    },
    {
        "id": "focussash", "name": ("Banda Focus", "Focus Sash"), "tiers": ("C", "B", "A"),
        "effect": ("Un golpe que te dejaría KO te deja con 1 de vida (cada 60 s).",
                   "A hit that would KO you leaves you at 1 HP (once every 60 s)."),
        "reason": (
        "Mediana +6 % (estimación). Vale más en partidas tardías, con enemigos que pegan fuerte.",
        "Median +6% (estimate). Worth more late, against hard-hitting enemies."),
    },
]

TIER_POINTS = {"S": 3, "A": 2, "B": 1, "C": 0, "-": 0}
# La build es un grupo fijo vinculado (no se cambia de movimiento), así que la Cinta Elección ya no choca con ella.
NOT_FOR_BUILDS: set[str] = set()


def recommended(count: int = 3) -> list[dict]:
    """Los objetos mejor puestos de la tier list de arriba sumando las tres fases (S 3, A 2, B 1, C 0), sin los que
    chocan con una build de varios ataques. A igualdad, manda el orden de ITEMS. Es la misma lista para todos los
    Pokémon: la tier list de objetos no distingue por especie."""
    pool = [it for it in ITEMS if it["id"] not in NOT_FOR_BUILDS]
    pool.sort(key=lambda it: -sum(TIER_POINTS[t] for t in it["tiers"]))
    return pool[:count]


EXCLUDED_NOTE = ("Moneda Amuleto no entra en la tier list: solo da más Pokémonedas al acabar la partida.",
                 "Amulet Coin is not in the tier list: it only gives more Pokécoins when a run ends.")


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


def _badge(t: str) -> str:
    if t == "-":
        return '<span class="muted">—</span>'
    return f'<span class="tier-badge {t}">{t}</span>'


def _phase(L: Lang, idx: int, name: tuple[str, str], span: tuple[str, str]) -> str:
    rows = []
    for tier in TIER_ORDER:
        if not any(it["tiers"][idx] == tier for it in ITEMS):
            continue
        chips = "".join(f'<span class="ph-chip">{_icon(it["id"])}{escape(_t(it["name"], L))}</span>'
                        for it in ITEMS if it["tiers"][idx] == tier)
        rows.append(f'<li>{_badge(tier)}<span class="ph-chips">{chips}</span></li>')
    return (f'<section class="ph"><h2>{escape(_t(name, L))}</h2>'
            f'<p class="muted small">{escape(_t(span, L))}</p><ul class="ph-list">{"".join(rows)}</ul></section>')


def _cards(L: Lang) -> str:
    cards = "".join(
        f'<li><details class="it-card"><summary>{_icon(it["id"])}'
        f'<span class="it-txt"><b>{escape(_t(it["name"], L))}</b><span>{escape(_t(it["effect"], L))}</span></span>'
        f'<i class="it-more" aria-hidden="true"></i></summary>'
        f'<p>{escape(_t(it["reason"], L))}</p></details></li>'
        for it in ITEMS)
    return f'<ul class="it-grid">{cards}</ul>'


def items_content(L: Lang, h1: str, lede: str, phases_h: str, table_h: str) -> str:
    """Contenido de la página Objetos: tres fases con su tier, y una tarjeta por objeto con su efecto (la razón, plegada)."""
    phases = "".join(_phase(L, i, name, span) for i, (_, name, span) in enumerate(PHASES))
    return (_symbols()
            + f'<h1>{escape(h1)}</h1>'
            f'<p class="lede">{escape(lede)}</p>'
            f'<h2>{escape(phases_h)}</h2>'
            f'<div class="ph-grid">{phases}</div>'
            f'<h2>{escape(table_h)}</h2>'
            f'{_cards(L)}'
            f'<p class="note small">{escape(_t(EXCLUDED_NOTE, L))}</p>')
