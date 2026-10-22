"""Tipos: qué tipo de ataque pega mejor a los Pokémon que salen como enemigos.

Todo sale del código del juego tal como lo aplica el simulador: la tabla de tipos (v3_data.json `tmult`), los
enemigos de cada tramo de la partida (v3_data.json `tiers`, build/coverage.py), el ×1,2 de un Pokémon de un solo tipo
(player.js monoType) y el clima (weather.js, simulator/sim-rs/src/engine.rs wx_mult). No hay cifras de simulación.
"""
from __future__ import annotations

import statistics as st
from html import escape

import coverage
import toolpages
from bounded_view import GAME
from i18n import TYPE_NAMES, Lang
from static_ficha import _type_pill
from typedata import TYPE_COLOR

EARLY_UNTIL = 160  # los tramos que empiezan antes de este segundo son el principio de la partida (0:00-2:39)
LATE_FROM = 380  # y los que empiezan desde este, el final (6:20 en adelante)
# weather.js (engine.rs wx_mult): el clima multiplica el daño de estos tipos, el tuyo y el de los enemigos.
WEATHER = (
    ("sun", (("fire", 1.5), ("water", 0.5))),
    ("rain", (("water", 1.5), ("electric", 1.2), ("fire", 0.5))),
    ("sand", (("rock", 1.3), ("ground", 1.3), ("steel", 1.3))),
    ("snow", (("ice", 1.5),)),
    ("fog", (("ghost", 1.3), ("fairy", 1.3), ("psychic", 1.3))),
)


def _pool(pred) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for start, foes in coverage.tiers():
        if pred(start):
            for dex, types in foes.items():
                out.setdefault(dex, types)
    return out


def rows() -> list[dict]:
    """Un tipo de ataque por fila, del que más pega de media al que menos, contra cada especie enemiga una vez."""
    pools = {"all": coverage.enemies(), "early": _pool(lambda s: s < EARLY_UNTIL), "late": _pool(lambda s: s >= LATE_FROM)}
    out = []
    for t in sorted(coverage._v3()["tmult"]):
        c = coverage.of_types([t])
        out.append({"type": t, "good": c["good"], "resist": c["resist"], "n": c["n"],
                    **{k: st.mean(coverage.best_mult([t], foe) for foe in pool.values()) for k, pool in pools.items()}})
    return sorted(out, key=lambda r: -r["all"])


def _x(L: Lang, v: float) -> str:
    return "×" + L.dec(v, 2)


_CELL = {1.6: "up", 0.6: "dn", 0.3: "bad"}
_ORDER = list(TYPE_NAMES["es"])


def _matrix(L: Lang) -> str:
    head = "<th></th>" + "".join(
        f'<th scope="col"><abbr title="{escape(L.type_name(t))}" style="--tc:{TYPE_COLOR[t]}"></abbr></th>'
        for t in _ORDER)
    body = []
    for atk in _ORDER:
        cells = []
        for dfn in _ORDER:
            v = GAME["tmult"][atk][dfn]
            if v == 1:
                cells.append("<td></td>")
            else:
                cells.append(f'<td class="tp-{_CELL[v]}">{L.dec(v, 1)}</td>')
        body.append(f'<tr><th scope="row">{_type_pill(L, atk)}</th>{"".join(cells)}</tr>')
    key = "".join(
        f'<li><i class="tp-{cls}"></i>{L.dec(v, 1)}</li>'
        for v, cls in ((1.0, "one"), (1.6, "up"), (0.6, "dn"), (0.3, "bad")))
    return (f'<div class="tp-scroll" id="tabla"><table class="tp-matrix"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div><ul class="tp-key">{key}</ul>')


def _bars(L: Lang) -> str:
    rs = rows()
    top = max(r["all"] for r in rs) or 1
    items = "".join(
        f'<li>{_type_pill(L, r["type"])}<span class="tp-track"><b style="width:{100 * r["all"] / top:.1f}%"></b></span>'
        f'<b class="tp-x">{_x(L, r["all"])}</b></li>'
        for r in rs)
    return f'<ol class="tp-bars">{items}</ol>'


def _weather(L: Lang) -> str:
    chips = []
    for w, effects in WEATHER:
        bits = "".join(f'<span class="tp-wx">{_type_pill(L, t)}<b>×{L.dec(k, 1)}</b></span>' for t, k in effects)
        chips.append(f'<li><b>{escape(L.t("tp_wx_" + w))}</b><span class="wx-fx">{bits}</span></li>')
    return (f'<section id="clima" aria-labelledby="tp-wx-h"><h2 id="tp-wx-h">{escape(L.t("tp_wx_h"))}</h2>'
            f'<ul class="wx-list">{"".join(chips)}</ul></section>')


def content(L: Lang, home: str) -> str:
    return ('<div class="pv tp">'
            f'<h1>{escape(L.t("tp_h1"))}</h1>'
            + _matrix(L)
            + f'<h2 id="tp-table-h">{escape(L.t("tp_table_h"))}</h2>'
            + _bars(L)
            + _weather(L)
            + f'<p class="pv-link"><a href="{home}{toolpages.folder(L, "finder")}">{escape(L.t("tp_finder"))}</a></p>'
            '</div>')
