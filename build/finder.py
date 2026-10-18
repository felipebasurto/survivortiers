"""Buscador por tipos: eliges uno o dos tipos y ves qué Pokémon los tienen, a qué ataques son débiles y cuánto pega cada
uno con físicos y especiales (pa y sa). La tabla de un solo tipo va en HTML para quien no tiene JavaScript.

La tabla de tipos es la del juego (js/data/types.js, sin cambios entre c46c46b y e868b5e): suavizada, x1,6 super
efectivo, x0,6 poco efectivo, x0,3 inmune, y el producto de dos tipos entre x0,3 y x2,4 (SOFT, MIN y MAX de ese archivo).
La lógica de cálculo está en src/tools.js; aquí solo se pinta la parte estática.
"""
from __future__ import annotations

from html import escape

import gamestats
import toolpages
import typedata
from i18n import Lang

TOOL_KEYS = (
    "tf_g_x24", "tf_g_weak", "tf_g_res", "tf_g_imm", "tf_none", "tf_count", "tf_empty", "tf_card_double",
    "tf_card_pa", "tf_card_sa", "tool_noscript", "tool_fail", "tool_load",
)


def type_pill(L: Lang, t: str) -> str:
    return (f'<span class="type" style="--tc:{typedata.TYPE_COLOR[t]};--tg:{typedata.text_color(t)}">{typedata.glyph_svg(t)}'
            f'<span>{escape(L.type_name(t))}</span></span>')


def _chip(L: Lang, t: str) -> str:
    return (f'<button type="button" class="tf-chip" data-t="{t}" aria-pressed="false" '
            f'style="--tc:{typedata.TYPE_COLOR[t]};--tg:{typedata.text_color(t)}">'
            f'{typedata.glyph_svg(t)}<span>{escape(L.type_name(t))}</span></button>')


def _tag(L: Lang, t: str) -> str:
    return f'<span class="tt" style="--tc:{typedata.TYPE_COLOR[t]};--tg:{typedata.text_color(t)}">{escape(L.type_name(t))}</span>'


def _tags(L: Lang, types: list[str]) -> str:
    return "".join(_tag(L, t) for t in types) or '<span class="muted">—</span>'


def static_chart(L: Lang) -> str:
    chart = gamestats.single_chart()
    rows = []
    for d in gamestats.TYPE_KEYS:
        weak = [a for a in gamestats.TYPE_KEYS if chart[a][d] > 1]
        resist = [a for a in gamestats.TYPE_KEYS if 0.3 < chart[a][d] < 1]
        immune = [a for a in gamestats.TYPE_KEYS if chart[a][d] <= 0.3]
        rows.append(f'<tr><th scope="row">{_tag(L, d)}</th>'
                    f'<td>{_tags(L, weak)}</td><td>{_tags(L, resist)}</td><td>{_tags(L, immune)}</td></tr>')
    head = "".join(f'<th scope="col">{escape(L.t(k))}</th>' for k in ("tf_col_type", "tf_col_weak", "tf_col_res", "tf_col_imm"))
    return (f'<div class="tf-table-wrap"><table class="tf-table"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def content(L: Lang) -> str:
    chips = "".join(_chip(L, t) for t in gamestats.TYPE_KEYS)
    stats_url = gamestats.game_url("js/data/pokedex.js")
    types_url = gamestats.game_url("js/data/types.js")
    source = L.t("tf_source", url=escape(types_url), stats=escape(stats_url), sha=gamestats.COMMIT)
    return f"""
<div class="tf tool" id="tf-app">
<h1>{escape(L.t("tf_h1"))}</h1>
<p class="lede">{escape(L.t("tf_lede"))}</p>
<section class="tool-pick" aria-labelledby="tf-pick-h">
  <div class="tool-pick-head"><h2 id="tf-pick-h">{escape(L.t("tf_pick_h"))}</h2>
    <button type="button" class="btn ghost tool-clear" id="tf-clear" hidden>{escape(L.t("tf_clear"))}</button></div>
  <p class="tool-rule">{escape(L.t("tf_rule"))}</p>
  <div class="tf-chips" role="group" aria-label="{escape(L.t("tf_pick_h"))}">{chips}</div>
</section>
<div class="tf-layout">
  <section class="tf-side" aria-labelledby="tf-weak-h">
    <h2 id="tf-weak-h">{escape(L.t("tf_weak_h"))}</h2>
    <div id="tf-weak" aria-live="polite"></div>
  </section>
  <section class="tf-results" aria-labelledby="tf-res-h">
    <div class="tf-res-head"><h2 id="tf-res-h" class="sr">Pokémon</h2><p id="tf-count" class="tf-count" aria-live="polite"></p></div>
    <ol id="tf-list" class="tf-list"></ol>
    <p id="tf-empty" class="tf-empty" hidden>{escape(L.t("tf_empty"))}</p>
    <p id="tf-status" class="muted" aria-live="polite"></p>
  </section>
</div>
<noscript><p class="muted">{escape(L.t("tool_noscript"))}</p></noscript>
<section class="tool-sec" aria-labelledby="tf-table-h">
  <h2 id="tf-table-h">{escape(L.t("tf_table_h"))}</h2>
  <p class="tool-lede">{escape(L.t("tf_table_lede"))}</p>
  {static_chart(L)}
</section>
<section class="tool-sec" aria-labelledby="tf-how-h">
  <h2 id="tf-how-h">{escape(L.t("tf_how_h"))}</h2>
  <p>{escape(L.t("tf_how"))}</p>
  <p class="tool-stats-note">{escape(L.t("tf_stats_note"))}</p>
  <p class="muted small">{source}</p>
</section>
{toolpages.blob(L, TOOL_KEYS)}
</div>
"""
