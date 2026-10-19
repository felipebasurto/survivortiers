"""Pasivas: las cartas de nivel de PokéSurvivor, ordenadas por la recompensa en monedas, en español e inglés.

Las cifras son medianas de simulator/results/fixed_group/pasivas_rank_g2p2.csv (escenario del bot que no esquiva),
tal como las saca `simulator/pasivas_rank.py report`. Surv es el tiempo de partida y kills el ritmo de bajas (kpm).
test_pasivas.py recalcula cada cifra desde el CSV y falla si no cuadra. Cada texto es una pareja (es, en).
"""
from __future__ import annotations

import csv
import json
import re
from html import escape
from pathlib import Path
from statistics import median

import gamestats
import toolpages
from i18n import Lang, NBSP

DATA = Path(__file__).resolve().parent.parent / "data"
RANK_CSV = Path(__file__).resolve().parent.parent / "simulator" / "results" / "fixed_group" / "pasivas_rank_g2p2.csv"
ICONS = json.loads((DATA / "card_icons.json").read_text(encoding="utf8"))
ITEM_ICONS = json.loads((DATA / "item_icons.json").read_text(encoding="utf8"))
MOVE_ICONS = json.loads((DATA / "move_icons.json").read_text(encoding="utf8"))
ICON_LETTERS = "abcdefghijklmnopqrstuvwxyz"

# Orden de cogida: de más a menos monedas. fill es el índice de carta de simulator/pasivas_rank.py.
# coin / surv / kpm se miden en pasivas_rank_g2p2.csv (mediana de la subida frente a la base).
_CARD_META = [
    {"id": "rgn", "name": ("Síntesis", "Synthesis"), "fill": "5"},
    {"id": "hp", "name": ("Vigor", "Vigor"), "fill": "2"},
    {"id": "atk", "name": ("Potencia", "Power"), "fill": "0"},
    {"id": "def", "name": ("Coraza", "Armor"), "fill": "3"},
    {"id": "cd", "name": ("Reflejos", "Reflexes"), "fill": "4"},
    {"id": "spd", "name": ("Carrera", "Sprint"), "fill": "1"},
    {"id": "xp", "name": ("Aprendizaje", "Learning"), "fill": "7"},
    {"id": "mag", "name": ("Imán", "Magnet"), "fill": "6"},
]


def _card_lifts() -> dict[str, dict[str, float]]:
    """Median percent lift of each stat card versus the no-card row. Same definition as test_pasivas."""
    rows = list(csv.DictReader(RANK_CSV.open(encoding="utf8")))
    by: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        by.setdefault((row["item"], row["fill"], row.get("heal_below", "")), {})[(row["dex"], row["move"])] = row
    base = by[("none", "", "0.70")]
    out = {}
    for meta in _CARD_META:
        treat = by[("none", meta["fill"], "0.70")]
        stats = {}
        for field, key in (("median_coins", "coin"), ("median_s", "surv"), ("median_kpm", "kpm")):
            vals = []
            for k, b in base.items():
                if k not in treat:
                    continue
                b0 = float(b[field])
                if b0 <= 0:
                    continue
                vals.append((float(treat[k][field]) - b0) / b0)
            stats[key] = round(100 * median(vals), 1)
        out[meta["fill"]] = stats
    return out


def _cards() -> list[dict]:
    lifts = _card_lifts()
    cards = []
    for meta in _CARD_META:
        row = dict(meta)
        row.update(lifts[meta["fill"]])
        cards.append(row)
    cards.sort(key=lambda c: (-c["coin"], -c["surv"], -c["kpm"], c["fill"]))
    return cards


CARDS = _cards()

# levelup.js:26-27. Cura el 45% de la vida máxima de golpe. Se coge solo con hp/maxHp <= 0.70.
ZIDRA = {
    "id": "heal", "name": ("Baya Zidra", "Sitrus Berry"), "at": 0.70,
    "rule": ("La simulación la coge al 70% de vida o menos. No es una regla del juego.",
             "The simulation takes it at 70% HP or below. It is not a game rule."),
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
     "why": ("Suma 20% de reducción, y el total no pasa del 80%. Coraza topa el total en 70%: si la subes después, "
             "te quita lo que pase de ahí.",
             "Adds 20% reduction, and the total never passes 80%. Armor caps the total at 70%: if you raise Armor after "
             "this, it takes away whatever is above that.")},
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
     "why": ("En la simulación, con ataques cuerpo a cuerpo la curación al momento vale casi el doble. El juego no lo cambia.",
             "In the simulation, with melee attacks the on-the-spot heal is worth about twice as much. The game doesn't change it.")},
]
EXCEPTION_MOVES = sorted({m for row in EXCEPTIONS for m in row["moves"]})

# Qué cartas salen al subir de nivel. levelup.js:58-59: los movimientos de su lado fuerte pesan el doble al elegir
# (y los empatados y los potenciadores, que no tienen lado, también). El tope de dos potenciadores ya lo explica
# la sección de potenciadores (levelup.js:47-49 y :56).
OFFER = (
    "En las cartas de movimiento nuevo, los ataques de tu lado fuerte salen el doble de veces que los demás. Tu lado "
    "fuerte es el físico o el especial, el que tenga más ataque. Los empatados y los potenciadores también cuentan doble.",
    "On new-move cards, attacks on your strong side come up twice as often as the rest. Your strong side is physical "
    "or special, whichever has more attack. Ties and boosts count double too.",
)

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


def _offers(L: Lang) -> str:
    return (f'<section class="pv-box pv-offers"><h2>{escape(L.t("pv_offers_h"))}</h2>'
            f'<p class="pv-why">{escape(_t(OFFER, L))}</p></section>')


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


# Los potenciadores y su tope vienen de data/game_stats.json (commit e868b5e). Tope de dos potenciadores:
# js/systems/levelup.js:46-56. Danza Espada y Danza Dragón comparten el contador de ataque físico (patk) y Maquinación
# el de especial (satk): js/entities/player.js:42-50 y :99-102, y js/systems/combat.js:201-202.
NUM_HEAD = ("pv_buff_th_cd", "pv_buff_th_dur", "pv_buff_th_max")
BOOST_LABEL = {"patk": "pv_buff_cat_phys", "satk": "pv_buff_cat_spec", "spd": "pv_buff_stat_spd",
               "def": "pv_buff_stat_def", "regen": "pv_buff_stat_regen"}


def _amount(value: float, stat: str, L: Lang, digits: int) -> str:
    if stat == "regen":
        return f"+{L.dec(value, digits)} HP/s"
    return f"+{L.dec(value * 100, 0)}{'' if L.en else NBSP}%"


def _boost_rows(L: Lang) -> str:
    rows = []
    for mid in gamestats.BOOST_ORDER:
        m = gamestats.move(mid)
        b = m["buff"]
        name = m["en"] if L.en else m["name"]
        digits = 1 if b["stat"] == "regen" else 0
        per = _amount(b["amount"], b["stat"], L, digits)
        top = _amount(b["amount"] * b["stacks"], b["stat"], L, digits)
        rows.append(
            f'<tr><th scope="row">{escape(name)}</th>'
            f'<td data-label="{escape(L.t("pv_buff_th_stat"))}">{escape(L.t(BOOST_LABEL[b["stat"]]))} {escape(per)}</td>'
            f'<td class="num" data-label="{escape(L.t("pv_buff_th_cd"))}">{L.dec(b["cd"], 2)}{NBSP if not L.en else " "}s</td>'
            f'<td class="num" data-label="{escape(L.t("pv_buff_th_dur"))}">{b["dur"]}{NBSP if not L.en else " "}s</td>'
            f'<td class="num" data-label="{escape(L.t("pv_buff_th_max"))}">{escape(top)}</td></tr>')
    return "".join(rows)


def _boosts(L: Lang, home: str) -> str:
    cells = []
    for k in ("pv_buff_th_boost", "pv_buff_th_stat", "pv_buff_th_cd", "pv_buff_th_dur", "pv_buff_th_max"):
        cls = ' class="num"' if k in NUM_HEAD else ""
        cells.append(f'<th scope="col"{cls}>{escape(L.t(k))}</th>')
    head = "".join(cells)
    rules = "".join(f"<li>{escape(L.t(k))}</li>" for k in ("pv_buff_r1", "pv_buff_r2", "pv_buff_r3"))
    return (f'<section class="pv-boosts" id="potenciadores" aria-labelledby="pv-boosts-h">'
            f'<h2 id="pv-boosts-h">{escape(L.t("pv_buff_h"))}</h2>'
            f'<p class="pv-lede-sm">{escape(L.t("pv_buff_lede"))}</p>'
            f'<div class="pv-tablewrap"><table class="pv-buffs"><thead><tr>{head}</tr></thead>'
            f'<tbody>{_boost_rows(L)}</tbody></table></div>'
            f'<p class="pv-cap">{escape(L.t("pv_buff_cap_note", commit=gamestats.COMMIT))}</p>'
            f'<ul class="pv-rules">{rules}</ul>'
            f'<p class="pv-rec">{escape(L.t("pv_buff_rec"))}</p>'
            f'<p class="pv-link"><a href="{home}{toolpages.folder(L, "planner")}">'
            f'{escape(L.t("pv_buff_link"))} →</a></p></section>')


def content(L: Lang, home: str) -> str:
    return (_symbols()
            + '<div class="pv">'
            + f'<h1>{escape(L.t("pv_h1"))}</h1>'
            + f'<p class="lede">{escape(L.t("pv_lede"))}</p>'
            + '<div class="pv-main">'
            + _top(L) + _zidra(L) + _rest(L) + _combos(L) + _offers(L)
            + '</div>'
            + f'<section class="pv-styles-sec">{_styles(L)}</section>'
            + _boosts(L, home)
            + _method(L, home)
            + '</div>')
