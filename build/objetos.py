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
        "reason": ("Si juegas con un grupo fijo de cuatro movimientos vinculados y no cambias nunca, el bloqueo no te "
                   "cuesta nada y el +40 % es puro (también a los ataques del grupo). En la simulación de grupo fijo "
                   "(2 ataques + Danza Espada y Fortaleza, 150 Pokémon, 100 partidas) sube la mediana un 9 % "
                   "(estimación). Solo pierde si todavía cambias de movimiento.",
                   "If you play one fixed group of four bonded moves and never switch, the lock costs nothing and "
                   "the +40% is pure (it applies to every move in the group). In the fixed-group simulation "
                   "(2 attacks + Swords Dance and Harden, 150 Pokémon, 100 runs) it raises the median by 9% "
                   "(estimate). It only loses if you still switch moves."),
    },
    {
        "id": "luckyegg", "name": ("Huevo Suerte", "Lucky Egg"), "tiers": ("S", "S", "A"),
        "effect": ("+30 % de experiencia.", "+30% experience."),
        "reason": ("Más niveles, más cartas. Un ×1,3 de XP suma pocos niveles, pero la prueba con ×3,2 pasa de "
                   "21 / 39 / 49 a 34 / 62 / 77 niveles a los 5 / 10 / 15 min.",
                   "More levels, more cards. A ×1.3 XP gain adds only a few levels, but the ×3.2 test goes from "
                   "21 / 39 / 49 to 34 / 62 / 77 levels at 5 / 10 / 15 min."),
    },
    {
        "id": "choicescarf", "name": ("Pañuelo Elección", "Choice Scarf"), "tiers": ("S", "A", "B"),
        "effect": ("+35 % de velocidad.", "+35% speed."),
        "reason": ("Sale del enjambre cuando aún no tienes defensa. Pierde valor cuando matas rápido.",
                   "Gets you out of the swarm before you have defence. Loses value when you kill fast."),
    },
    {
        "id": "quickclaw", "name": ("Garra Rápida", "Quick Claw"), "tiers": ("A", "A", "A"),
        "effect": ("-20 % de recarga en todos tus movimientos.", "-20% cooldown on all your moves."),
        "reason": ("Ritmo de disparo para todo tu arsenal, sin depender de qué ataque tengas.",
                   "Fire rate for your whole arsenal, no matter which moves you have."),
    },
    {
        "id": "lifeorb", "name": ("Vidasfera", "Life Orb"), "tiers": ("B", "C", "C"),
        "effect": ("+30 % de daño, pero cada ataque te quita un poco de vida.",
                   "+30% damage, but each attack costs you some HP."),
        "reason": ("Cada ataque te cuesta el 1 % de tu vida máxima (no te mata, y las órbitas no cuentan). Con varios "
                   "movimientos, esas pérdidas se acumulan.",
                   "Each attack costs 1% of your max HP (it cannot kill you, and orbits do not count). With several "
                   "moves, those losses add up."),
    },
    {
        "id": "assaultvest", "name": ("Chaleco Asalto", "Assault Vest"), "tiers": ("B", "A", "B"),
        "effect": ("+20 % de reducción de daño recibido.", "+20% damage reduction."),
        "reason": ("Vale más mientras la reducción total esté lejos del tope del 80 %. Las cartas Coraza suman "
                   "reducción por el mismo camino, así que, con ellas, el tope llega antes.",
                   "Worth more while your total reduction is far from the 80% cap. Armor cards add reduction too, "
                   "so with them the cap is reached sooner."),
    },
    {
        "id": "rockyhelmet", "name": ("Casco Dentado", "Rocky Helmet"), "tiers": ("B", "A", "A"),
        "effect": ("Los que te golpean cuerpo a cuerpo reciben daño.",
                   "Enemies that hit you in melee take damage."),
        "reason": ("Cuando un enemigo te toca, le devuelve 15 + 4 × tu nivel de daño. A nivel 30 son 135 de golpe; "
                   "a nivel 100, 415. Solo cuenta contra los que te tocan.",
                   "When an enemy touches you, it takes 15 + 4 × your level in damage. At level 30 that is 135 per hit; "
                   "at level 100, 415. Only counts against enemies that touch you."),
    },
    {
        "id": "leftovers", "name": ("Restos", "Leftovers"), "tiers": ("C", "B", "B"),
        "effect": ("Recuperas un 1,5 % de tu vida máxima por segundo.",
                   "Recover 1.5% of your max HP per second."),
        "reason": ("Escala con tu vida máxima, pero pesa poco frente al daño de la partida tardía.",
                   "Scales with your max HP, but matters little against late-game damage."),
    },
    {
        "id": "shellbell", "name": ("Cascabel Concha", "Shell Bell"), "tiers": ("C", "C", "C"),
        "effect": ("Recuperas vida con el daño que haces.", "Heal from the damage you deal."),
        "reason": ("Cura el 4 % del daño que haces, pero guarda como máximo 4 de vida pendiente a la vez. Con vida "
                   "máxima alta, casi no cura.",
                   "Heals 4% of the damage you deal, but holds at most 4 pending HP at a time. With high max HP, it "
                   "barely heals."),
    },
    {
        "id": "focussash", "name": ("Banda Focus", "Focus Sash"), "tiers": ("C", "B", "A"),
        "effect": ("Un golpe que te dejaría KO te deja con 1 de vida (cada 60 s).",
                   "A hit that would KO you leaves you at 1 HP (once every 60 s)."),
        "reason": ("Lista desde el primer segundo. En la partida tardía, con enemigos que pegan fuerte, cada golpe "
                   "salvado decide más partidas.",
                   "Ready from the first second. Late game, with hard-hitting enemies, each saved hit decides more runs."),
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


def _table(L: Lang) -> str:
    head = ["Objeto", "Efecto", "Temprano", "Medio", "Tardío", "Por qué"] if not L.en else \
        ["Item", "Effect", "Early", "Mid", "Late", "Why"]
    body = []
    for it in ITEMS:
        cells = "".join(f'<td class="tier-cell">{_badge(t)}</td>' for t in it["tiers"])
        body.append(f'<tr><th scope="row"><span class="item-name">{_icon(it["id"])}{escape(_t(it["name"], L))}</span></th><td>{escape(_t(it["effect"], L))}</td>'
                    f'{cells}<td>{escape(_t(it["reason"], L))}</td></tr>')
    thead = "".join(f'<th>{escape(h)}</th>' for h in head)
    return (f'<div class="tablewrap"><table><thead><tr>{thead}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def items_content(L: Lang, h1: str, lede: str, phases_h: str, table_h: str) -> str:
    """Contenido de la página Objetos: tres fases con su tier, y la tabla con el efecto y la razón de cada objeto."""
    phases = "".join(_phase(L, i, name, span) for i, (_, name, span) in enumerate(PHASES))
    return (_symbols()
            + f'<h1>{escape(h1)}</h1>'
            f'<p class="lede">{escape(lede)}</p>'
            f'<h2>{escape(phases_h)}</h2>'
            f'<div class="ph-grid">{phases}</div>'
            f'<h2>{escape(table_h)}</h2>'
            f'{_table(L)}'
            f'<p class="note small">{escape(_t(EXCLUDED_NOTE, L))}</p>')
