"""Pasivas: las cartas de subida de nivel de PokéSurvivor y los potenciadores, tal como los define el juego.

Las cartas son el STATS de js/systems/levelup.js en el commit de gamestats (pin, sin checkout del juego).
Los potenciadores salen de data/game_stats.json. No hay cifras de simulación: el bot coge las cartas con una
prioridad fija, así que la web no dice cuál conviene. Cada texto es una pareja (es, en).
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

import bounded_view
import gamestats
import toolpages
from i18n import Lang, NBSP

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ICONS = json.loads((DATA / "card_icons.json").read_text(encoding="utf8"))
ITEM_ICONS = json.loads((DATA / "item_icons.json").read_text(encoding="utf8"))
ICON_LETTERS = "abcdefghijklmnopqrstuvwxyz"

# Nombre y efecto en inglés de cada carta (el juego solo está en español).
EN = {
    "hp": ("Vigor", "+20 max HP (and heals it)."),
    "atk": ("Power", "+10% damage with every move."),
    "spd": ("Sprint", "+7% movement speed."),
    "cd": ("Reflexes", "-8% cooldown on every move."),
    "def": ("Armor", "+6% damage reduction."),
    "rgn": ("Synthesis", "+0.9 HP regenerated per second."),
    "mag": ("Magnet", "+30% experience pickup radius."),
    "xp": ("Learning", "+12% experience gained."),
    "heal": ("Sitrus Berry", "Restores 45% of your HP right now."),
}

# STATS de js/systems/levelup.js @ gamestats.COMMIT: id, título ES, desc ES, max (None = sin tope).
_STATS = (
    ("hp", "Vigor", "+20 de vida máxima (y la recupera).", None),
    ("atk", "Potencia", "+10% de daño con todos los movimientos.", 40),
    ("spd", "Carrera", "+7% de velocidad de movimiento.", 8),
    ("cd", "Reflejos", "-8% de recarga en todos los movimientos.", 10),
    ("def", "Coraza", "+6% de reducción de daño recibido.", 12),
    ("rgn", "Síntesis", "+0.9 de vida regenerada por segundo.", None),
    ("mag", "Imán", "+30% de radio de recogida de experiencia.", 6),
    ("xp", "Aprendizaje", "+12% de experiencia ganada.", 8),
    ("heal", "Baya Zidra", "Recupera el 45% de tu vida ahora mismo.", None),
)


def game_cards() -> list[dict]:
    """Las cartas de estadística de levelup.js STATS, en su orden: id, nombre, efecto y tope de veces (None = sin tope)."""
    out = [{"id": cid, "name": (title, EN[cid][0]), "effect": (desc, EN[cid][1]), "max": top}
           for cid, title, desc, top in _STATS]
    if [c["id"] for c in out] != list(EN):
        raise ValueError(f"levelup.js STATS no son las cartas esperadas: {[c['id'] for c in out]}")
    return out


CARDS = game_cards()

# Qué cartas salen al subir de nivel. levelup.js:58-59: los movimientos de su lado fuerte pesan el doble al elegir
# (y los empatados y los potenciadores, que no tienen lado, también). El tope de dos potenciadores ya lo explica
# la sección de potenciadores (levelup.js:47-49 y :56).
OFFER = (
    "En las cartas de movimiento nuevo, los ataques de tu lado fuerte salen el doble de veces que los demás. Tu lado "
    "fuerte es el físico o el especial, el que tenga más ataque. Los empatados y los potenciadores también cuentan doble.",
    "On new-move cards, attacks on your strong side come up twice as often as the rest. Your strong side is physical "
    "or special, whichever has more attack. Ties and boosts count double too.",
)


def _t(pair: tuple[str, str], L: Lang) -> str:
    if L.en:
        return pair[1]
    return re.sub(r"(\d)%", "\\1" + NBSP + "%", pair[0])


def _symbols() -> str:
    out = []
    packs = ([(f"card-{k}", v) for k, v in ICONS.items()] + [(f"item-{k}", v) for k, v in ITEM_ICONS.items()]
)
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


def _cards(L: Lang) -> str:
    rows = "".join(
        f'<tr><th scope="row"><span class="pv-cref">{_icon("card", c["id"])}{escape(_t(c["name"], L))}</span></th>'
        f'<td data-label="{escape(L.t("pv_th_effect"))}">{escape(_t(c["effect"], L))}</td>'
        f'<td class="num" data-label="{escape(L.t("pv_th_max"))}">'
        f'{escape(str(c["max"]) if c["max"] else L.t("pv_no_max"))}</td></tr>'
        for c in CARDS)
    head = (f'<th scope="col">{escape(L.t("pv_th_card"))}</th><th scope="col">{escape(L.t("pv_th_effect"))}</th>'
            f'<th scope="col" class="num">{escape(L.t("pv_th_max"))}</th>')
    return (f'<section class="pv-boosts" id="cartas" aria-labelledby="pv-cards-h">'
            f'<h2 id="pv-cards-h">{escape(L.t("pv_cards_h"))}</h2>'
            f'<div class="pv-tablewrap"><table class="pv-buffs"><thead><tr>{head}</tr></thead>'
            f'<tbody>{rows}</tbody></table></div>'
            f'<p class="pv-cap">{escape(L.t("pv_cards_note"))}</p>'
            f'<p class="pv-why">{escape(_t(OFFER, L))}</p></section>')


# Los potenciadores y su tope vienen de data/game_stats.json (commit 5a23d49). Tope de dos potenciadores:
# js/systems/levelup.js:46-56. Danza Espada y Danza Dragón comparten el contador de ataque físico (patk) y Maquinación
# el de especial (satk): js/entities/player.js:42-50 y :99-102, y js/systems/combat.js:201-202.
NUM_HEAD = ("pv_buff_th_cd", "pv_buff_th_dur", "pv_buff_th_max", "pv_buff_th_top")


def _boost_rows(L: Lang) -> str:
    rows = []
    sec = NBSP if not L.en else " "
    for mid in gamestats.BOOST_ORDER:
        m = gamestats.move(mid)
        b, top = m["buff"], m["buff"]["max"]
        name = m["en"] if L.en else m["name"]
        per = gamestats.boost_amount(L, b["amount"], b["stat"])
        full = gamestats.boost_amount(L, b["amount"] * b["stacks"], b["stat"])
        upgraded = L.t("pv_buff_top", amt=gamestats.boost_amount(L, top["amount"] * top["stacks"], b["stat"]),
                       dur=L.dec(top["dur"], 1))
        rows.append(
            f'<tr><th scope="row">{escape(name)}</th>'
            f'<td data-label="{escape(L.t("pv_buff_th_stat"))}">{escape(L.t(gamestats.BOOST_LABEL[b["stat"]]))} {escape(per)}</td>'
            f'<td class="num" data-label="{escape(L.t("pv_buff_th_cd"))}">{L.dec(b["cd"], 2)}{sec}s</td>'
            f'<td class="num" data-label="{escape(L.t("pv_buff_th_dur"))}">{b["dur"]}{sec}s</td>'
            f'<td class="num" data-label="{escape(L.t("pv_buff_th_max"))}">{escape(full)}</td>'
            f'<td class="num" data-label="{escape(L.t("pv_buff_th_top"))}">{escape(upgraded)}</td></tr>')
    return "".join(rows)


def _boosts(L: Lang, home: str) -> str:
    cells = []
    for k in ("pv_buff_th_boost", "pv_buff_th_stat", "pv_buff_th_cd", "pv_buff_th_dur", "pv_buff_th_max",
              "pv_buff_th_top"):
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
            f'<p class="pv-link"><a href="{home}{toolpages.folder(L, "planner")}">'
            f'{escape(L.t("pv_buff_link"))}</a></p></section>')


def content(L: Lang, home: str) -> str:
    return (_symbols()
            + '<div class="pv">'
            + f'<h1>{escape(L.t("pv_h1"))}</h1>'
            + f'<p class="lede">{escape(L.t("pv_lede"))}</p>'
            + _cards(L)
            + _boosts(L, home)
            + bounded_view.abilities_section(L)
            + bounded_view.natures_by_stat_section(L, home)
            + '</div>')
