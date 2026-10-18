"""Planificador de build: eliges un Pokémon y ves su grupo vinculado (hasta cuatro movimientos de su grupo, con dos
potenciadores como máximo), su objeto y sus cartas, con la cobertura del grupo y el enlace para compartirlo. Empieza
con la build recomendada (species.json, posición 9 y 10), que el navegador calcula en src/tools.js.

Sin JavaScript queda el texto de la página y el enlace a la ficha de cada Pokémon; el planificador necesita los datos.
"""
from __future__ import annotations

from html import escape

import gamestats
import toolpages
from i18n import Lang

TOOL_KEYS = (
    "bp_pick_move", "bp_slot", "bp_cat_phys", "bp_cat_spec", "bp_cat_boost", "bp_cat_phys_adj", "bp_cat_spec_adj",
    "bp_boost_count", "bp_boost_max", "bp_mismatch_none", "bp_mismatch_some", "bp_both", "bp_swapped",
    "bp_item_none", "bp_item_best", "bp_card_n", "bp_card_none", "bp_result_h", "bp_cover", "bp_none_attack",
    "bp_link", "bp_copy", "bp_copied", "bp_reset", "bp_rank", "bp_side", "bp_open_sheet", "bp_group_h", "bp_item_h",
    "bp_cards_h", "bp_pick_ph", "tf_card_pa", "tf_card_sa", "tool_noscript", "tool_fail", "tool_load",
)


def content(L: Lang) -> str:
    finder = "../" + toolpages.folder(L, "finder")
    source = L.t("bp_source", url=escape(gamestats.game_url("js/data/moves.js")),
                 stats=escape(gamestats.game_url("js/data/pokedex.js")), sha=gamestats.COMMIT)
    return f"""
<div class="bp tool" id="bp-app" hidden>
<h1>{escape(L.t("bp_h1"))}</h1>
<p class="lede">{escape(L.t("bp_lede"))}</p>
<section class="tool-pick" aria-labelledby="bp-pick-h">
  <h2 id="bp-pick-h">{escape(L.t("bp_pick_h"))}</h2>
  <label class="bp-field" for="bp-q"><span class="sr">{escape(L.t("bp_pick_h"))}</span>
    <input id="bp-q" class="bp-q" type="search" list="bp-list" autocomplete="off" placeholder="{escape(L.t("bp_pick_ph"))}"></label>
  <datalist id="bp-list"></datalist>
  <div id="bp-mon" class="bp-mon" aria-live="polite"></div>
</section>
<div class="bp-layout">
  <section class="bp-build" aria-labelledby="bp-group-h">
    <h2 id="bp-group-h">{escape(L.t("bp_group_h"))}</h2>
    <p class="tool-rule">{escape(L.t("bp_group_note"))}</p>
    <div id="bp-slots" class="bp-slots"></div>
    <div id="bp-warn" class="bp-warns" aria-live="polite"></div>
    <p id="bp-boostcount" class="bp-count"></p>
    <h2>{escape(L.t("bp_item_h"))}</h2>
    <label class="bp-field" for="bp-item"><span class="sr">{escape(L.t("bp_item_h"))}</span><select id="bp-item" class="bp-select"></select></label>
    <h2>{escape(L.t("bp_cards_h"))}</h2>
    <p class="tool-rule">{escape(L.t("bp_cards_note"))}</p>
    <div id="bp-cards" class="bp-cards"></div>
  </section>
  <aside id="bp-result" class="bp-result" aria-live="polite"></aside>
</div>
<noscript><p class="muted">{escape(L.t("tool_noscript"))}</p></noscript>
<section class="tool-sec" aria-labelledby="bp-how-h">
  <h2 id="bp-how-h">{escape(L.t("bp_boost_guide"))}</h2>
  <p>{escape(L.t("bp_how"))}</p>
  <p><a href="../pasivas.html#potenciadores">{escape(L.t("pv_buff_link"))} →</a> · <a href="{escape(finder)}">{escape(L.t("guide_finder"))}</a></p>
  <p class="muted small">{source}</p>
</section>
{toolpages.blob(L, TOOL_KEYS)}
</div>
"""
