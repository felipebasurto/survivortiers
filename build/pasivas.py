"""Pasivas: las cartas de nivel de PokéSurvivor, ordenadas por la recompensa en monedas, en español e inglés.

Las cifras son medianas de simulator/results/fixed_group/pasivas_rank_g2p2.csv (escenario del bot que no esquiva),
tal como las saca `simulator/pasivas_rank.py report`. Surv es el tiempo de partida y kills el ritmo de bajas (kpm).
test_pasivas.py recalcula cada cifra desde el CSV y falla si no cuadra. Cada texto es una pareja (es, en).
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

from i18n import Lang, NBSP

DATA = Path(__file__).resolve().parent.parent / "data"
ICONS = json.loads((DATA / "card_icons.json").read_text(encoding="utf8"))
ITEM_ICONS = json.loads((DATA / "item_icons.json").read_text(encoding="utf8"))
MOVE_ICONS = json.loads((DATA / "move_icons.json").read_text(encoding="utf8"))
ICON_LETTERS = "abcdefghijklmnopqrstuvwxyz"

# Orden de cogida: de más a menos monedas. fill es el índice de carta de simulator/pasivas_rank.py.
CARDS = [
    {"id": "rgn", "name": ("Síntesis", "Synthesis"), "fill": "5", "coin": 6.1, "surv": 5.6, "kpm": -0.5},
    {"id": "hp", "name": ("Vigor", "Vigor"), "fill": "2", "coin": 1.6, "surv": 2.2, "kpm": -0.4},
    {"id": "atk", "name": ("Potencia", "Power"), "fill": "0", "coin": 0.0, "surv": 0.0, "kpm": 0.0},
    {"id": "def", "name": ("Coraza", "Armor"), "fill": "3", "coin": 0.0, "surv": -0.4, "kpm": -0.9},
    {"id": "cd", "name": ("Reflejos", "Reflexes"), "fill": "4", "coin": 0.0, "surv": -0.5, "kpm": 0.8},
    {"id": "spd", "name": ("Carrera", "Sprint"), "fill": "1", "coin": 0.0, "surv": -0.6, "kpm": -1.5},
    {"id": "xp", "name": ("Aprendizaje", "Learning"), "fill": "7", "coin": -0.7, "surv": -1.3, "kpm": -0.6},
    {"id": "mag", "name": ("Imán", "Magnet"), "fill": "6", "coin": -3.1, "surv": -2.0, "kpm": -1.0},
]

# levelup.js:26-27. Cura el 45% de la vida máxima de golpe. Se coge solo con hp/maxHp <= 0.70.
ZIDRA = {
    "id": "heal", "name": ("Baya Zidra", "Sitrus Berry"), "at": 0.70,
    "rule": ("Cógela al 70% de vida o menos.", "Take it at 70% HP or below."),
    "why": ("Cura el 45% al momento. Con la vida llena no hace nada.",
            "Heals 45% on the spot. At full HP it does nothing."),
}

# Lo que suma priorizar la carta cuando ya llevas el objeto. Subida de monedas, misma escala que CARDS.
COMBOS = [
    {"item": "shellbell", "item_name": ("Cascabel", "Shell Bell"), "card": "rgn", "lift": "+2%",
     "why": ("Cura el 4% del daño que haces, hasta 4 de vida por segundo.",
             "Heals 4% of the damage you deal, up to 4 HP per second.")},
    {"item": "leftovers", "item_name": ("Restos", "Leftovers"), "card": "rgn", "lift": "+2%",
     "why": ("Recupera el 1,5% de tu vida máxima por segundo.",
             "Recovers 1.5% of your max HP per second.")},
    {"item": "leftovers", "item_name": ("Restos", "Leftovers"), "card": "hp", "lift": "+1%",
     "why": ("Igual que con Síntesis.", "Same as with Synthesis.")},
    {"item": "assaultvest", "item_name": ("Chaleco", "Assault Vest"), "card": "def", "lift": "0",
     "why": ("Comparte el tope de reducción del 70% con Coraza. No alarga nada.",
             "Shares the 70% reduction cap with Armor. Adds no time.")},
    {"item": "choiceband", "item_name": ("Cinta", "Choice Band"), "card": "cd", "lift": "0",
     "why": ("Ya sube el daño un 40%. Reflejos no suma monedas.",
             "Already adds 40% damage. Reflexes adds no coins.")},
    {"item": "quickclaw", "item_name": ("Garra", "Quick Claw"), "card": "cd", "lift": "0",
     "why": ("Ya baja la recarga un 20%. Reflejos no suma.",
             "Already cuts cooldown 20%. Reflexes adds nothing.")},
]

# Ataques que cambian el orden. rule usa {id} para dibujar la carta con su icono.
EXCEPTIONS = [
    {"k": ("Cono", "Cone"), "moves": ["flamethrower"], "ex": ("Lanzallamas", "Flamethrower"),
     "rule": ("{rgn} sube aún más", "{rgn} climbs even higher"),
     "why": ("Hay que acercarse para que llegue, y su regeneración no tiene tope.",
             "You have to get close for it to land, and its regen has no cap.")},
    {"k": ("Órbita", "Orbit"), "moves": ["fire-spin"], "ex": ("Giro Fuego", "Fire Spin"),
     "rule": ("{cd} no suma", "{cd} adds nothing"),
     "why": ("El tiempo entre golpes es el del ataque.", "The gap between hits is the move's own cooldown.")},
    {"k": ("Aura", "Aura"), "moves": ["discharge"], "ex": ("Chispazo", "Discharge"),
     "rule": ("Ninguna carta suma", "No card adds anything"),
     "why": ("La partida acaba antes de que la mejora se note.", "The run ends before the bonus shows.")},
    {"k": ("Torreta y estela", "Turret and trail"), "moves": ["will-o-wisp", "toxic"],
     "ex": ("Fuego Fatuo · Tóxico", "Will-O-Wisp · Toxic"),
     "rule": ("{cd} no suma", "{cd} adds nothing"),
     "why": ("Ni los tiros ni los charcos usan esa recarga.", "Neither the shots nor the puddles use that cooldown.")},
    {"k": ("Cuerpo a cuerpo", "Melee"), "moves": ["tackle"], "ex": ("Placaje", "Tackle"),
     "rule": ("{heal} suma más", "{heal} adds more"),
     "why": ("Hay que estar encima, así que el 45% al momento vale casi el doble.",
             "You have to stand on the enemy, so the 45% on the spot is worth about twice as much.")},
]
EXCEPTION_MOVES = sorted({m for row in EXCEPTIONS for m in row["moves"]})

ORDER_NOTE = ("Excepción: una carta que evoluciona tu ataque va siempre primera.",
              "Exception: a card that evolves your move always goes first.")

METHOD = [
    ("Monedas = parte entera de tiempo/5 + parte entera de bajas × 0,25 + jefes × 80 + monedas recogidas. Sin Fortuna.",
     "Coins = floor(time/5) + floor(kills × 0.25) + bosses × 80 + coins picked up. No Fortune."),
    ("Mediana de 150 Pokémon, grupo fijo 2+2, 100 partidas por carta. Aguante es el tiempo hasta caer. "
     "Bajas/min son las bajas por minuto. El bot no esquiva.",
     "Median of 150 Pokémon, fixed 2+2 group, 100 runs per card. Survival is the time until you fall. "
     "Kills/min is kills per minute. The bot does not dodge."),
    ("Segunda prueba: el bot ignora la mitad de cada golpe. El orden se mantiene y Síntesis sube más.",
     "Second test: the bot ignores half of each hit. The order holds and Synthesis climbs further."),
]

TOP_N = 3  # cartas destacadas arriba, con la baya debajo; el resto va después

_SYMBOL_RE = re.compile(r"\{(\w+)\}")


def _t(pair: tuple[str, str], L: Lang) -> str:
    if L.en:
        return pair[1]
    return re.sub(r"(\d)%", "\\1" + NBSP + "%", pair[0])


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


def _by_id(card_id: str) -> dict:
    for c in CARDS:
        if c["id"] == card_id:
            return c
    if card_id == ZIDRA["id"]:
        return ZIDRA
    raise KeyError(card_id)


def _pct(v: float, L: Lang, digits: int) -> str:
    r = round(v, digits)
    if r == 0:
        sign, body = "", "0"
    else:
        sign, body = ("+" if r > 0 else "−"), L.dec(abs(r), digits)
    return f"{sign}{body}{'' if L.en else NBSP}%"


def _tone(v: float) -> str:
    r = round(v, 1)
    return "pv-up" if r > 0 else "pv-down" if r < 0 else ""


def _cref(card_id: str, L: Lang) -> str:
    return (f'<span class="pv-cref">{_icon("card", card_id)}'
            f'{escape(_t(_by_id(card_id)["name"], L))}</span>')


def _rule(text: str, L: Lang) -> str:
    parts = _SYMBOL_RE.split(text)
    return "".join(escape(p) if i % 2 == 0 else _cref(p, L) for i, p in enumerate(parts))


def _rows(L: Lang, first: int, last: int, top: float) -> str:
    rows = []
    for i in range(first, last):
        c = CARDS[i]
        width = max(c["coin"], 0) / top * 100
        rows.append(
            f'<li class="pv-row{" is-top" if i == 0 else ""}">'
            f'<span class="pv-pos">{i + 1}</span>'
            f'{_icon("card", c["id"], big=True)}'
            f'<span class="pv-name">{escape(_t(c["name"], L))}</span>'
            f'<span class="pv-val {_tone(c["coin"])}">{_pct(c["coin"], L, 0)}</span>'
            f'<span class="pv-sub">{escape(L.t("pv_surv"))} {_pct(c["surv"], L, 1)} · '
            f'{escape(L.t("pv_kills"))} {_pct(c["kpm"], L, 1)}</span>'
            f'<span class="pv-bar" aria-hidden="true"><i style="--w:{width:.1f}%"></i></span>'
            f'</li>')
    return "".join(rows)


def _top(L: Lang) -> str:
    top = max(c["coin"] for c in CARDS)
    return (f'<section class="pv-col pv-top"><h2>{escape(L.t("pv_rank_h"))}</h2>'
            f'<ol class="pv-list">{_rows(L, 0, TOP_N, top)}</ol></section>')


def _rest(L: Lang) -> str:
    top = max(c["coin"] for c in CARDS)
    return (f'<section class="pv-col pv-rest"><ol class="pv-list" start="{TOP_N + 1}">{_rows(L, TOP_N, len(CARDS), top)}</ol>'
            f'<p class="pv-note"><span>{escape(L.t("pv_rank_note"))}</span> '
            f'<span>{escape(_t(ORDER_NOTE, L))}</span></p></section>')


def _zidra(L: Lang) -> str:
    return (f'<section class="pv-box pv-zidra">'
            f'<h2>{escape(_t(ZIDRA["name"], L))}</h2>'
            f'<div class="pv-zrow">{_icon("card", ZIDRA["id"], big=True)}'
            f'<p class="pv-rule">{escape(_t(ZIDRA["rule"], L))}</p></div>'
            f'<div class="pv-hp" aria-hidden="true">'
            f'<span class="pv-hp-take" style="width:{ZIDRA["at"] * 100:.0f}%">{escape(L.t("pv_take"))}</span>'
            f'<span class="pv-hp-wait">{escape(L.t("pv_wait"))}</span>'
            f'<span class="pv-hp-mark" style="left:{ZIDRA["at"] * 100:.0f}%">'
            f'{_pct(ZIDRA["at"] * 100, L, 0).replace("+", "")}</span></div>'
            f'<p class="pv-why">{escape(_t(ZIDRA["why"], L))}</p></section>')


def _combos(L: Lang) -> str:
    rows = []
    for row in COMBOS:
        lift = row["lift"].replace("−", "-").replace("%", "")
        value = float(lift)
        rows.append(
            f'<li class="pv-row pv-row-sm">'
            f'{_icon("item", row["item"], big=True)}'
            f'<span class="pv-name">{escape(_t(row["item_name"], L))} + '
            f'{escape(_t(_by_id(row["card"])["name"], L))}</span>'
            f'<span class="pv-val {_tone(value)}">{_pct(value, L, 0)}</span>'
            f'<span class="pv-sub">{escape(_t(row["why"], L))}</span></li>')
    return (f'<section class="pv-box pv-combos"><h2>{escape(L.t("pv_items_h"))}</h2>'
            f'<p class="pv-lede-sm">{escape(L.t("pv_items_note"))}</p>'
            f'<ul class="pv-list">{"".join(rows)}</ul></section>')


def _styles(L: Lang) -> str:
    cards = []
    for row in EXCEPTIONS:
        icons = "".join(_icon("move", m, big=True) for m in row["moves"])
        cards.append(
            f'<li class="pv-style">'
            f'<div class="pv-style-h"><span class="pv-kicons">{icons}</span>'
            f'<div><h3>{escape(_t(row["k"], L))}</h3><p class="pv-ex">{escape(_t(row["ex"], L))}</p></div></div>'
            f'<p class="pv-rule">{_rule(_t(row["rule"], L), L)}</p>'
            f'<p class="pv-why">{escape(_t(row["why"], L))}</p></li>')
    return (f'<h2>{escape(L.t("pv_except_h"))}</h2>'
            f'<ul class="pv-styles">{"".join(cards)}</ul>')


def _method(L: Lang, home: str) -> str:
    lines = "".join(f"<p>{escape(_t(line, L))}</p>" for line in METHOD)
    return (f'<details class="pv-method"><summary>{escape(L.t("pv_method_sum"))}</summary>'
            f'<div class="pv-method-body">{lines}'
            f'<p><a href="{home}metodo.html">{escape(L.t("pv_method_link"))} →</a></p></div></details>')


def content(L: Lang, home: str) -> str:
    return (_symbols()
            + '<div class="pv">'
            + f'<h1>{escape(L.t("pv_h1"))}</h1>'
            + f'<p class="lede">{escape(L.t("pv_lede"))}</p>'
            + '<div class="pv-main">'
            + _top(L) + _zidra(L) + _rest(L) + _combos(L)
            + '</div>'
            + f'<section class="pv-styles-sec">{_styles(L)}</section>'
            + _method(L, home)
            + '</div>')
