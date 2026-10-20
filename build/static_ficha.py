"""HTML estático de una ficha: lo que un buscador lee sin ejecutar JavaScript.

Los números salen de los datos ya generados (ranking, species.json, moves.json) y de la misma
regla de tirada que build/catalog.py (RATES y el pool de rareza más cercano). No hay cifras nuevas.
No hay aparición salvaje en los datos: solo el banner de gacha.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from html import escape

import catalog
import charts
import game_moves
import legal
import regions
import typedata
from i18n import Lang
from slugs import species_path

STAT_KEYS = ("bs_hp", "bs_atk", "bs_def", "bs_spa", "bs_spd", "bs_spe")
SUMMARY_MARK = re.compile(r"\[([^\[\]|]+)\|([^\[\]]+)\]")  # [clave|texto] en data/summaries-<idioma>.json


def esc(x) -> str:
    return escape(str(x), quote=True)


def damage_badge(L: Lang, cls: str) -> str:
    return f'<span class="cat-tag is-{cls}" title="{esc(L.t("dmg_tip_" + cls))}">{esc(L.t("dmg_" + cls))}</span>'


def range_html(L: Lang, move: dict) -> str:
    """Cuerpo a cuerpo o a distancia, el eje que separa las dos builds. Cada uno tiene su color e icono."""
    cls = "melee" if move["kind"] == "melee" else "ranged"
    return (f'<span class="rng-tag is-{cls}" title="{esc(L.t("rng_tip_" + cls))}">'
            f'{esc(L.t("bd_" + cls))}</span>')


def shape_html(L: Lang, move: dict) -> str:
    """La forma del ataque (la misma etiqueta que ataques.html) y, si el dato trae `nuevo`, una marca pequeña.
    El cuerpo a cuerpo no repite su forma: ya lo dice la etiqueta de rango."""
    label = "" if move["kind"] == "melee" else \
        f'<span class="mv-shape">{esc(L.t("mv_kind_" + game_moves.shape_key(move)))}</span>'
    mark = f'<span class="mv-new">{esc(L.t("mv_new"))}</span>' if move.get("nuevo") else ""
    return label + mark


def move_tags(L: Lang, move: dict) -> str:
    return f'<span class="bd-tags">{range_html(L, move)}{damage_badge(L, move["damage"])}{shape_html(L, move)}</span>'


def js_round(x: float) -> int:
    """Math.round de JavaScript para positivos: mitad hacia arriba, como la página de gacha."""
    return int(math.floor(x + 0.5))


def pull_p(rarity: int, counts: dict[int, int]) -> float:
    """Probabilidad de que una tirada sea este Pokémon. Igual que newPerPull de src/app.js con un solo objetivo:
    cada rareza tirada cae en el pool no vacío más cercano y ahí se elige al azar. Sin la garantía de las 70."""
    total = 0.0
    for rolled, pct in catalog.RATES:
        resolved = None
        for delta in catalog.NEAR_ORDER:
            r = rolled + delta
            if 1 <= r <= 5 and counts.get(r):
                resolved = r
                break
        if resolved == rarity and counts.get(rarity):
            total += pct / 100 / counts[rarity]
    return total


def odds_table(entries: list[dict]) -> dict[int, tuple[float, int]]:
    """dex -> (probabilidad por tirada, tiradas esperadas redondeadas)."""
    counts: dict[int, dict[int, int]] = {}
    for e in entries:
        bucket = counts.setdefault(e["bannerId"], {})
        bucket[e["rarity"]] = bucket.get(e["rarity"], 0) + 1
    out = {}
    for e in entries:
        p = pull_p(e["rarity"], counts[e["bannerId"]])
        out[e["dex"]] = (p, js_round(1 / p) if p else 0)
    return out


def _digits(pct: float) -> int:
    if pct >= 1:
        return 1
    if pct >= 0.1:
        return 2
    return 3


def _starts_i_sound(word: str) -> bool:
    """La RAE pide «e» antes de i- y de hi- (Hipnosis, Impactrueno), pero no ante hie-, hia-, hio-, hiu- (hierba)."""
    w = "".join(c for c in unicodedata.normalize("NFKD", word.lower()) if not unicodedata.combining(c))
    if w.startswith("i"):
        return True
    return w.startswith("hi") and w[2:3] not in ("a", "e", "i", "o", "u")


def _join(L: Lang, names: list[str]) -> str:
    if len(names) <= 1:
        return names[0] if names else ""
    conj = " and " if L.en else (" e " if _starts_i_sound(names[-1]) else " y ")
    return ", ".join(names[:-1]) + conj + names[-1]



def _move_name(L: Lang, moves: dict[str, dict], mid: str) -> str:
    m = moves.get(mid)
    if not m:
        raise KeyError(mid)
    return m["en"]["name"] if L.en else m["name"]


def _type_pill(L: Lang, t: str) -> str:
    return (f'<span class="type" style="--tc:{typedata.TYPE_COLOR[t]};--tg:{typedata.text_color(t)}">'
            f'{typedata.glyph_svg(t)}<span>{esc(L.type_name(t))}</span></span>')


def alternates(slug: str) -> str:
    es = f"{legal.SITE_URL}/pokemon/{slug}/"
    en = f"{legal.SITE_URL}/en/pokemon/{slug}/"
    return "\n".join((
        f'<link rel="alternate" hreflang="es" href="{esc(es)}">',
        f'<link rel="alternate" hreflang="en" href="{esc(en)}">',
        f'<link rel="alternate" hreflang="x-default" href="{esc(es)}">',
    ))


def _card_name(L: Lang, card: dict) -> str:
    return card["en"]["name"] if L.en else card["name"]


def card_answer(L: Lang, names: list[str], once: str | None) -> str:
    """La misma frase en la FAQ y en el JSON-LD. `once` es la carta que hace falta una vez para evolucionar el ataque."""
    cards = _join(L, names)
    if once:
        return L.t("faq_a_cards_gate", cards=cards, once=once)
    return L.t("faq_a_cards", cards=cards)


BUILD_NAME = {"melee": "bd_melee", "ranged": "bd_ranged"}
BUILD_OTHER = {"melee": "bd_other_ranged", "ranged": "bd_other_melee"}
BUILD_NONE = {"melee": "bd_none_melee", "ranged": "bd_none_ranged"}
BUILD_LOWER = {"melee": "bd_other_melee", "ranged": "bd_other_ranged"}
BUILD_OTHER_KIND = {"melee": "ranged", "ranged": "melee"}
GAP_SMALL_PCT = 5


def _faqs(L: Lang, tier: str, rank: int, build_text: str, card_text: str, banner: str, legendary: bool,
          pct: str, pulls: int) -> list[tuple[str, str]]:
    worth = (L.t("faq_q_worth"), L.t(f"faq_a_{tier}", rank=rank, total=charts.TOTAL))
    out = [worth, (L.t("faq_q_moves"), build_text)]
    if card_text:
        out.append((L.t("faq_q_cards"), card_text))
    where = L.t("faq_get_where_leg" if legendary else "faq_get_where", banner=banner)
    out.append((L.t("faq_q_get"), f"{where} {L.t('faq_get_odds', pct=pct, n=L.num(pulls))}"))
    return out


def summary_plain(text: str) -> str:
    """El resumen de la ficha (data/summaries-<idioma>.json) sin las marcas: el texto que se ve."""
    return SUMMARY_MARK.sub(lambda m: m.group(2), text)


def jsonld(faqs: list[tuple[str, str]], updated: str, url: str, name: str, lang: str) -> str:
    doc = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "url": url,
        "name": name,
        "inLanguage": lang,
        "dateModified": updated,
        "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                       for q, a in faqs],
    }
    text = json.dumps(doc, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{text}</script>'


def _neighbor(L: Lang, home: str, sprites: str, ext: str, entry: dict | None, direction: str) -> str:
    if not entry:
        return "<span></span>"
    w, h = entry["sprite"]["w"], entry["sprite"]["h"]
    k = max(1, min(2, 40 // max(w, h)))
    slug = species_path(entry["dex"], entry["nameEn"])
    name = L.mon(entry)
    return (f'<a class="pg pg-{direction}" href="{home}pokemon/{slug}/">'
            f'<b aria-hidden="true">{"‹" if direction == "prev" else "›"}</b>'
            f'<img class="px" src="{sprites}{entry["dex"]}{ext}" width="{w * k}" height="{h * k}" alt="" loading="lazy">'
            f'<span>{esc(name)}<small>{esc(L.t("dex_no", dex=entry["dex"]))}</small></span></a>')


# Ataque y defensa del juego (js/systems/stats.js:17-43): el daño que recibe es ×clamp((75/defensa)^0.35, 0,78, 1,25).
COMBAT_REF_DEF = 75
COMBAT_LO, COMBAT_HI = 0.78, 1.25
ATK_BAR_MAX, DEF_BAR_MAX = 1.8, 255  # escala de las barras: ×1,00 es el neutro de ataque; 255 como las estadísticas base
KIND_KEY = {"phys": "cb_kind_phys", "spec": "cb_kind_spec", "mix": "cb_kind_mix"}
# Mismo sistema de etiquetas que los ataques (cat-tag): físico, especial y mixto tienen icono y color propios.
KIND_CLASS = {"phys": "physical", "spec": "special", "mix": "mix"}


def _bar(cls: str, label: str, shown: str, fill: float, mark: float) -> str:
    return (f'<div class="cb-row {cls}"><span class="cb-name">{esc(label)}</span>'
            f'<span class="cb-track"><i class="cb-fill" style="width:{fill * 100:.2f}%"></i>'
            f'<b class="cb-mark" style="left:{mark * 100:.2f}%"></b></span>'
            f'<output class="cb-val">{esc(shown)}</output></div>')


def combat(L: Lang, entry: dict) -> str:
    """Ataque y defensa del juego: lado fuerte, las cuatro cifras con su barra y una línea sobre la defensa."""
    b = entry["base"]
    kind = catalog.attack_kind(b["pa"], b["sa"])
    atk = (_bar("cb-atk-phys", L.t("cb_pa"), "×" + L.dec(b["pa"], 2), b["pa"] / ATK_BAR_MAX, 1 / ATK_BAR_MAX)
           + _bar("cb-atk-spec", L.t("cb_sa"), "×" + L.dec(b["sa"], 2), b["sa"] / ATK_BAR_MAX, 1 / ATK_BAR_MAX))
    dfn = (_bar("cb-def", L.t("cb_df"), str(b["df"]), b["df"] / DEF_BAR_MAX, COMBAT_REF_DEF / DEF_BAR_MAX)
           + _bar("cb-def", L.t("cb_sd"), str(b["sd"]), b["sd"] / DEF_BAR_MAX, COMBAT_REF_DEF / DEF_BAR_MAX))
    note = L.t("cb_note", less=round((1 - COMBAT_LO) * 100), more=round((COMBAT_HI - 1) * 100))
    return (f'<section class="combat" id="combate" aria-labelledby="cb-h" data-kind="{kind}">'
            f'<header class="cb-head"><h3 id="cb-h">{esc(L.t("t_combat"))}</h3>'
            f'<span class="cat-tag is-{KIND_CLASS[kind]}">{esc(L.t(KIND_KEY[kind]))}</span></header>'
            f'<div class="cb-list">{atk}</div><div class="cb-list">{dfn}</div>'
            f'<p class="cb-note">{esc(note)}</p></section>')


def _gap_pct(high: float, low: float) -> int:
    return round((high - low) / high * 100) if high > 0 else 0


def _winner(pair: dict[str, dict | None]) -> str | None:
    """La build de mayor puntuación. Con empate, ninguna; si solo hay una, esa."""
    have = {k: b for k, b in pair.items() if b}
    if len(have) < 2:
        return next(iter(have), None)
    if have["melee"]["score"] == have["ranged"]["score"]:
        return None
    return max(have, key=lambda k: have[k]["score"])


DMG_KEY = {"physical": "dmg_physical", "special": "dmg_special", "mix": "dmg_mix"}


def build_damage(moves: dict[str, dict], ids: list[str]) -> str | None:
    """Tipo de daño de una build: físico o especial si todos sus ataques de daño lo son, mixto si mezcla los dos.
    Los potenciadores no cuentan. None si la build no tiene ataques de daño."""
    kinds = {moves[m]["damage"] for m in ids if m in moves and moves[m]["damage"] in ("physical", "special")}
    if not kinds:
        return None
    if len(kinds) == 2:
        return "mix"
    return kinds.pop()


def combo_html(L: Lang, dmg: str | None, rng: str) -> str:
    """Tipo de daño y rango de una build, con las mismas etiquetas que los ataques: por ejemplo Físico · Cuerpo a cuerpo."""
    dmg_chip = f'<span class="cat-tag is-{dmg}">{esc(L.t(DMG_KEY[dmg]))}</span>' if dmg else ""
    return (dmg_chip + f'<span class="rng-tag is-{rng}" title="{esc(L.t("rng_tip_" + rng))}">'
            f'{esc(L.t(BUILD_NAME[rng]))}</span>')


def best_range_html(L: Lang, pair: dict[str, dict | None], moves: dict[str, dict]) -> str:
    """La build que puntúa más: su combinación de daño y rango. Con empate, nada."""
    win = _winner(pair)
    if not win:
        return ""
    dmg = build_damage(moves, pair[win]["moves"])
    return f'<p class="bd-best"><span class="bd-best-lbl">{esc(L.t("bd_best_label"))}</span>{combo_html(L, dmg, win)}</p>'


def _lead(pair: dict[str, dict | None]) -> str:
    """La build que encabeza la descripción: la ganadora o, con empate o una sola, la cuerpo a cuerpo si existe."""
    return _winner(pair) or ("melee" if pair.get("melee") else "ranged")


def build_names(L: Lang, moves: dict[str, dict], b: dict) -> tuple[str, str]:
    """Los ataques de una build y sus potenciadores, ya unidos en una frase."""
    ids, nb = b["moves"], int(b["nBoost"])
    return (_join(L, [_move_name(L, moves, m) for m in ids[:len(ids) - nb]]),
            _join(L, [_move_name(L, moves, m) for m in ids[len(ids) - nb:]]))


def _build_answer(L: Lang, moves: dict[str, dict], pair: dict[str, dict | None]) -> str:
    parts = []
    for kind in BUILD_NAME:
        b = pair.get(kind)
        if not b:
            parts.append(L.t(BUILD_NONE[kind]))
            continue
        attacks, boosts = build_names(L, moves, b)
        parts.append(L.t("faq_a_build", kind=L.t(BUILD_NAME[kind]), attacks=attacks, buffs=boosts))
    win = _winner(pair)
    if win and len(pair) == 2 and all(pair.values()):
        parts.append(L.t("faq_a_build_best", kind=L.t(BUILD_LOWER[win])))
    return " ".join(parts)


def _verdict(L: Lang, kind: str, b: dict, other: dict | None, win: str | None) -> str:
    if other is None:
        return ""
    if win == kind:
        return f'<p class="bd-verdict is-best">{esc(L.t("bd_best"))}</p>'
    if win is None:
        return f'<p class="bd-verdict">{esc(L.t("bd_tie"))}</p>'
    gap = _gap_pct(other["score"], b["score"])
    if gap == 0:
        return f'<p class="bd-verdict">{esc(L.t("bd_tie"))}</p>'
    key = "bd_gap_small" if gap < GAP_SMALL_PCT else "bd_gap"
    return f'<p class="bd-verdict">{esc(L.t(key, pct=L.pcts(gap), other=L.t(BUILD_OTHER[kind])))}</p>'


def _move_row(L: Lang, moves: dict[str, dict], mid: str, n: str = "", boost: bool = False) -> str:
    """Una fila de la build: número, nombre y etiquetas de daño y forma. Los potenciadores van marcados."""
    cls = "bd-row is-buff" if boost else "bd-row"
    return (f'<li class="{cls}"><span class="bd-n">{n}</span><span class="bd-info"><span class="bd-nm">'
            f'{esc(_move_name(L, moves, mid))}</span>{move_tags(L, moves[mid])}</span></li>')


def _meter(label: str, v: int, cls: str) -> str:
    return (f'<div class="bd-meter {cls}"><span>{esc(label)}</span>'
            f'<i class="bd-track" role="img" aria-label="{v} %"><b style="width:{v}%"></b></i>'
            f'<strong>{v}&nbsp;%</strong></div>')


def _build_option(L: Lang, moves: dict[str, dict], cards: dict, kind: str, b: dict | None, other: dict | None,
                  win: str | None) -> str:
    """Una de las dos builds: veredicto, ataques en filas, estadísticas y las cartas en orden, todo a la vista."""
    dmg = build_damage(moves, b["moves"]) if b else None
    head = f'<h3 class="bd-kind">{combo_html(L, dmg, kind)}</h3>'
    if not b:
        return (f'<article class="bd-opt is-none" data-build="{kind}">{head}'
                f'<p class="bd-none">{esc(L.t(BUILD_NONE[kind]))}</p></article>')
    ids, nb = b["moves"], int(b["nBoost"])
    rows = "".join(_move_row(L, moves, mid, str(i + 1), i >= len(ids) - nb) for i, mid in enumerate(ids))
    stats = (f'<dl class="bd-stats">'
             f'<div><dt>{esc(L.t("bd_time"))}</dt><dd>{esc(L.dec(b["time"], 1))} s</dd></div>'
             f'<div><dt>{esc(L.t("bd_dealt"))}</dt><dd>{esc(L.num(b["dealt"]))}</dd></div>'
             f'<div><dt>{esc(L.t("bd_kills"))}</dt><dd>{esc(L.dec(b["kills"], 1))}</dd></div>'
             f'<div><dt>{esc(L.t("bd_score"))}</dt><dd>{esc(L.dec(b["score"], 1))}</dd></div></dl>')
    card_ids, gate = b["cards"]
    items = []
    for i, cid in enumerate(card_ids, 1):
        once = f' <small class="bd-gate" title="{esc(L.t("build_card_once"))}">1×</small>' if cid == gate else ""
        items.append(f'<li class="{"is-gate" if cid == gate else ""}"><span class="bd-n">{i}</span>'
                     f'<span class="bd-nm">{esc(_card_name(L, cards[cid]))}</span>{once}</li>')
    cards_html = (f'<p class="bd-cap">{esc(L.t("build_cards"))}</p>'
                  f'<ol class="bd-cardlist">{"".join(items)}</ol>'
                  + (f'<p class="bd-legend">{esc(L.t("build_card_once"))}</p>' if gate else ""))
    note = f'<p class="bd-note">{esc(L.t("bd_melee_note"))}</p>' if kind == "melee" else ""
    best = " is-best" if win == kind and other else ""
    return (f'<article class="bd-opt{best}" data-build="{kind}">{head}'
            f'{_verdict(L, kind, b, other, win)}<ol class="bd-rows">{rows}</ol>{stats}{cards_html}{note}</article>')



def head_texts(L: Lang, entry: dict, pair: dict[str, dict | None], moves: dict[str, dict], total: int) -> tuple[str, str]:
    """<title> y meta description de la ficha, con el tier, el puesto y la build que encabeza."""
    name, (rank, tier) = L.mon(entry), (entry["r"]["rank"], entry["r"]["tier"])
    attacks, buffs = build_names(L, moves, pair[_lead(pair)])
    title = L.t("fh_title", name=name, tier=tier)
    desc = L.t("fh_desc_buffs" if buffs else "fh_desc", name=name, tier=tier, rank=rank, total=total,
               attacks=attacks, buffs=buffs, banner=L.banner(entry["banner"]))
    return title, desc


def build(L: Lang, home: str, sprites: str, ext: str, entry: dict, detail: list, pair: dict[str, dict | None],
          moves: dict[str, dict], cards: dict, prev: dict | None, nxt: dict | None, odds: tuple[float, int], *,
          summary: str, guides: str, updated: str, url: str, title: str) -> tuple[str, str]:
    """Devuelve el HTML visible (sin <head>) y el JSON-LD de las preguntas. detail es la fila de la simulación (inicio,
    mejor ataque y cobertura); pair son las dos builds ({melee, ranged}; falta la clave si no hay build). summary es el
    resumen ya en texto plano; guides, el bloque de enlaces a las listas."""
    name = L.mon(entry)
    rank, tier = entry["r"]["rank"], entry["r"]["tier"]
    methods = entry["r"]["methods"]
    stats = list(entry["stats"])
    if len(stats) != 6:
        raise ValueError(f"{entry['dex']}: se esperaban 6 estadísticas base")
    p_pull, pulls = odds
    if not p_pull or not pulls:
        raise ValueError(f"{entry['dex']}: la tirada no tiene probabilidad")
    pct = L.dec(p_pull * 100, _digits(p_pull * 100))
    banner = L.banner(entry["banner"])
    win = _winner(pair)
    lead = pair[_lead(pair)]
    card_ids, gate = lead["cards"]
    card_text = card_answer(L, [_card_name(L, cards[c]) for c in card_ids], _card_name(L, cards[gate]) if gate else None)
    faqs = _faqs(L, tier, rank, _build_answer(L, moves, pair), card_text, banner,
                 bool(entry["legendary"]), pct, pulls)
    w, h = entry["sprite"]["w"], entry["sprite"]["h"]
    scale = max(1, min(5, 170 // max(w, h)))
    types = entry["types"]
    tc = typedata.TYPE_COLOR[types[0]]
    tc2 = typedata.TYPE_COLOR[types[1] if len(types) > 1 else types[0]]
    other = ""
    if not L.en and entry["nameEn"] != entry["name"]:
        other = f'<small>{esc(entry["nameEn"])}</small>'
    pills = "".join(_type_pill(L, t) for t in types)
    rarity = entry["rarity"]
    rarity_name = esc(L.t(f"rar_{rarity}"))
    legendary = f'<span class="chip">{esc(L.t("legendary"))}</span>' if entry["legendary"] else ""
    region = regions.badge(L, sprites, entry["bannerId"], banner, {}, small=True)
    start_row = _move_row(L, moves, detail[2])
    super_pct, neutral_pct = detail[9][0], detail[9][1]
    options = "".join(
        _build_option(L, moves, cards, kind, pair.get(kind), pair.get(BUILD_OTHER_KIND[kind]), win)
        for kind in BUILD_NAME)
    stat_rows = "".join(
        f'<tr><th scope="row">{esc(L.t(key))}</th><td class="num">{n}</td></tr>'
        for key, n in zip(STAT_KEYS, stats))
    stat_rows += f'<tr><th scope="row">{esc(L.t("bs_total"))}</th><td class="num">{sum(stats)}</td></tr>'
    faq_html = "".join(f"<dt>{esc(q)}</dt><dd>{esc(a)}</dd>" for q, a in faqs)
    pager = (_neighbor(L, home, sprites, ext, prev, "prev") + _neighbor(L, home, sprites, ext, nxt, "next"))
    html = f"""
<article id="ficha" data-dex="{entry['dex']}">
<a class="back" href="{home}index.html"><b aria-hidden="true">‹</b>{esc(L.t("crumb_home"))}</a>
<header class="ficha-head">
<div class="ficha-sprite" style="--tc:{tc};--tc2:{tc2}">
<img class="px" src="{sprites}{entry['dex']}{ext}" width="{w * scale}" height="{h * scale}" alt="{esc(L.t("sprite_alt", name=name))}">
<span class="tier-badge medal {tier}" title="{esc(L.t("tier", t=tier))}">{tier}</span>
</div>
<div class="fh-main">
<h1>{esc(name)} <span class="fh-game">{esc(L.t("fh_game"))}</span> {other}<small class="fh-dex">{esc(L.t("dex_no", dex=entry["dex"]))}</small></h1>
<div class="facts"><span class="types">{pills}</span>
<span class="rarity r{rarity}" role="img" aria-label="{rarity_name}" title="{rarity_name}"><svg class="rball" viewBox="0 0 12 12" aria-hidden="true"><use href="#rball-{rarity}"/></svg></span>
{legendary}{region}</div>
<p class="rankline"><i class="ico ico-trophy" aria-hidden="true"></i><strong>{rank}</strong><span>/ {charts.TOTAL}</span></p>
<p class="simline">{esc(L.t("sheet_sim_line", rank=methods["simBest"]))}</p>
<p class="simline">{esc(L.t("sheet_open_line", rank=methods["simStart"]))}</p>
<p class="resumen">{esc(summary)}</p>
</div>
</header>
<section class="fig fig-build" id="build" aria-labelledby="bd-h">
<div class="bd-card" style="--p1:{tc};--p2:{tc2}">
<header class="bd-head"><div><h2 id="bd-h">{esc(L.t("t_build"))}</h2><span class="bd-who">{esc(name)}</span></div>{best_range_html(L, pair, moves)}</header>
<div class="bd-block bd-start"><h3 class="bd-cap">{esc(L.t("build_start"))}</h3><ul class="bd-rows">{start_row}</ul></div>
<p class="bd-cap">{esc(L.t("bd_pair_cap"))}</p>
<div class="bd-pair">{options}</div>
<div class="bd-cover">{_meter(L.t("build_super"), int(super_pct), "bd-super")}{_meter(L.t("build_neutral"), int(neutral_pct), "bd-neutral")}</div>
<p class="bd-brand">{esc(L.t("build_brand", site=legal.SITE_NAME))}</p>
</div>
</section>
{combat(L, entry)}
<section class="sheet" id="stats" aria-labelledby="stats-h">
<h2 id="stats-h">{esc(L.t("t_base"))}</h2>
<table><tbody>{stat_rows}</tbody></table>
</section>
<nav class="pager" aria-label="{esc(L.t("pager_aria"))}">{pager}</nav>
</article>
<section class="sheet" id="obtain" aria-labelledby="obtain-h">
<h2 id="obtain-h">{esc(L.t("sheet_obtain_h"))}</h2>
<p><a href="{home}gachas.html">{esc(L.t("nav_gachas"))}</a></p>
</section>
<section class="sheet faq" id="faq" aria-labelledby="faq-h">
<h2 id="faq-h">{esc(L.t("sheet_faq_h"))}</h2>
<dl>{faq_html}</dl>
</section>
{guides}
"""
    return html, jsonld(faqs, updated, url, title, "en" if L.en else "es")
