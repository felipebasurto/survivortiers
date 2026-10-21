"""Tipos: qué tipo de ataque pega mejor a los Pokémon que salen como enemigos.

Todo sale del código del juego tal como lo aplica el simulador: la tabla de tipos (v3_data.json `tmult`), los
enemigos de cada tramo de la partida (v3_data.json `tiers`, build/coverage.py), el ×1,2 de un Pokémon de un solo tipo
(player.js monoType) y el clima (weather.js, simulator/sim-rs/src/engine.rs wx_mult). No hay cifras de simulación.
"""
from __future__ import annotations

import statistics as st
from collections import Counter
from html import escape

import coverage
import toolpages
from i18n import Lang
from static_ficha import _type_pill

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


def enemy_types() -> list[tuple[str, int]]:
    return Counter(t for types in coverage.enemies().values() for t in types).most_common()


def _x(L: Lang, v: float) -> str:
    return "×" + L.dec(v, 2)


def _pct(L: Lang, k: int, n: int) -> str:
    return L.pcts(round(100 * k / n))


def _table(L: Lang) -> str:
    rs = rows()
    body = "".join(
        f'<tr><th scope="row">{_type_pill(L, r["type"])}</th>'
        f'<td class="num" data-label="{escape(L.t("tp_th_avg"))}"><b>{_x(L, r["all"])}</b></td>'
        f'<td class="num" data-label="{escape(L.t("tp_th_good"))}">{_pct(L, r["good"], r["n"])}</td>'
        f'<td class="num" data-label="{escape(L.t("tp_th_resist"))}">{_pct(L, r["resist"], r["n"])}</td>'
        f'<td class="num" data-label="{escape(L.t("tp_th_early"))}">{_x(L, r["early"])}</td>'
        f'<td class="num" data-label="{escape(L.t("tp_th_late"))}">{_x(L, r["late"])}</td></tr>'
        for r in rs)
    num = ' class="num"'
    head = "".join(f'<th scope="col"{num if k != "tp_th_type" else ""}>{escape(L.t(k))}</th>'
                   for k in ("tp_th_type", "tp_th_avg", "tp_th_good", "tp_th_resist", "tp_th_early", "tp_th_late"))
    common = enemy_types()[:4]
    return (f'<section class="pv-boosts" id="tabla" aria-labelledby="tp-table-h">'
            f'<h2 id="tp-table-h">{escape(L.t("tp_table_h"))}</h2>'
            f'<p class="pv-lede-sm">{escape(L.t("tp_table_lede", n=L.num(rs[0]["n"])))}</p>'
            f'<div class="pv-tablewrap"><table class="pv-buffs tp-table"><thead><tr>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>'
            f'<p class="pv-cap">{escape(L.t("tp_table_cap"))}</p>'
            f'<p class="pv-why">{escape(L.t("tp_common", types=", ".join(f"{L.type_name(t)} ({L.num(k)})" for t, k in common)))}</p>'
            f'</section>')


def _rules(L: Lang) -> str:
    items = "".join(f"<li>{escape(L.t(k))}</li>" for k in ("tp_rule_chart", "tp_rule_mono", "tp_rule_auto"))
    return (f'<section class="pv-boosts" id="reglas" aria-labelledby="tp-rules-h">'
            f'<h2 id="tp-rules-h">{escape(L.t("tp_rules_h"))}</h2><ul class="pv-rules">{items}</ul></section>')


def _weather(L: Lang) -> str:
    body = "".join(
        f'<tr><th scope="row">{escape(L.t("tp_wx_" + w))}</th><td>'
        + " ".join(f'<span class="tp-wx">{_type_pill(L, t)}<b>×{L.dec(k, 1)}</b></span>' for t, k in effects)
        + "</td></tr>"
        for w, effects in WEATHER)
    return (f'<section class="pv-boosts" id="clima" aria-labelledby="tp-wx-h">'
            f'<h2 id="tp-wx-h">{escape(L.t("tp_wx_h"))}</h2>'
            f'<p class="pv-lede-sm">{escape(L.t("tp_wx_lede"))}</p>'
            f'<div class="pv-tablewrap"><table class="pv-buffs tp-wx-table"><thead><tr>'
            f'<th scope="col">{escape(L.t("tp_wx_th"))}</th><th scope="col">{escape(L.t("tp_wx_th_fx"))}</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div></section>')


def content(L: Lang, home: str) -> str:
    return ('<div class="pv">'
            f'<h1>{escape(L.t("tp_h1"))}</h1>'
            f'<p class="lede">{escape(L.t("tp_lede"))}</p>'
            + _rules(L) + _table(L) + _weather(L)
            + f'<p class="pv-link"><a href="{home}{toolpages.folder(L, "finder")}">{escape(L.t("tp_finder"))}</a></p>'
            '</div>')
