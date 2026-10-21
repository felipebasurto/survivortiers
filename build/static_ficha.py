"""HTML de la ficha de cada Pokémon: puesto, por qué está ahí, cuánto aguanta, sus dos builds y sus estadísticas.

Los números salen de los datos ya generados (build/catalog.py: ranking y builds de la fase 3, data/species_why.csv,
moves.json) y de la misma regla de tirada que build/catalog.py (RATES y el pool de rareza más cercano). No hay cifras
nuevas. No hay aparición salvaje en los datos: solo el banner de gacha.
"""
from __future__ import annotations

import json
import math
import unicodedata
from html import escape

import catalog
import game_moves
import legal
import regions
import typedata
from i18n import Lang
from slugs import species_path


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
    """Rango, tipo de daño y forma. Un potenciador no tiene rango: no ataca."""
    rng = "" if move["kind"] == "buff" else range_html(L, move)
    return f'<span class="bd-tags">{rng}{damage_badge(L, move["damage"])}{shape_html(L, move)}</span>'


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


def mmss(seconds: float) -> str:
    """Segundos de partida como minutos y segundos: 407,8 -> 6:48."""
    s = round(seconds)
    return f"{s // 60}:{s % 60:02d}"


BUILD_NAME = {"melee": "bd_melee", "ranged": "bd_ranged"}
BUILD_OTHER = {"melee": "bd_other_ranged", "ranged": "bd_other_melee"}
BUILD_LOWER = {"melee": "bd_other_melee", "ranged": "bd_other_ranged"}
BUILD_OTHER_KIND = {"melee": "ranged", "ranged": "melee"}
GAP_SMALL_PCT = 5


def _faqs(L: Lang, tier: str, rank: int, build_text: str, banner: str, legendary: bool,
          pct: str, pulls: int) -> list[tuple[str, str]]:
    worth = (L.t("faq_q_worth"), L.t(f"faq_a_{tier}", rank=rank, total=catalog.TOTAL))
    where = L.t("faq_get_where_leg" if legendary else "faq_get_where", banner=banner)
    return [worth, (L.t("faq_q_moves"), build_text),
            (L.t("faq_q_get"), f"{where} {L.t('faq_get_odds', pct=pct, n=L.num(pulls))}")]


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


# ---------------------------------------------------------------- por qué
WHY_MIN = 0.02  # un factor que mueve la puntuación menos de un 2 % no se nombra
WHY_ROWS = 3
MIX_KEY = {"physical": "why_atk_phys", "special": "why_atk_spec", "mixed": "why_atk_mix"}


def why_label(L: Lang, entry: dict, w: dict, moves: dict[str, dict]) -> str:
    """El factor con su valor, en una línea: «Ataque físico ×1,36», «PS 115», «Sus ataques: Puño Meteoro y …»."""
    f, v = w["f"], w["value"]
    best = entry["builds"][entry["r"]["best"]]
    if f == "atk":
        return L.t(MIX_KEY[best["mix"]], v=L.dec(v, 2))
    if f == "group":
        ids = best["moves"][:len(best["moves"]) - best["nBoost"]]
        return L.t("why_group", moves=_join(L, [_move_name(L, moves, m) for m in ids]))
    if f in ("size", "types"):
        return L.t(f"why_{f}", v=L.dec(v, 1 if f == "size" else 2))
    return L.t(f"why_{f}", v=round(v))


def why_rows(entry: dict) -> list[dict]:
    """Los factores que se nombran: en la mitad de arriba del ranking los dos que más suman y el que más resta; en la de
    abajo, el que más suma y los dos que más restan. Solo los que mueven la puntuación al menos un WHY_MIN."""
    top_half = entry["r"]["rank"] <= catalog.TOTAL // 2
    ups = sorted((w for w in entry["why"] if w["effect"] >= WHY_MIN), key=lambda w: -w["effect"])
    downs = sorted((w for w in entry["why"] if w["effect"] <= -WHY_MIN), key=lambda w: w["effect"])
    n_up = min(len(ups), 2 if top_half else 1)
    n_down = min(len(downs), WHY_ROWS - n_up)
    n_up = min(len(ups), WHY_ROWS - n_down)
    return ups[:n_up] + downs[:n_down]


def _pct_bar(pct: int, label: str) -> str:
    return (f'<i class="pct-bar" role="img" aria-label="{esc(label)}"><b style="width:{max(2, pct)}%"></b></i>')


def why(L: Lang, entry: dict, moves: dict[str, dict]) -> str:
    rows = []
    for w in why_rows(entry):
        eff = round(w["effect"] * 100)
        sign = "+" if eff > 0 else "−"
        cls = "is-up" if eff > 0 else "is-down"
        rows.append(f'<li class="why-row {cls}"><span class="why-eff">{sign}{abs(eff)}{"%" if L.en else "&nbsp;%"}</span>'
                    f'<span class="why-txt">{esc(why_label(L, entry, w, moves))}</span>'
                    f'{_pct_bar(w["pct"], L.t("pct_alt", pct=w["pct"]))}</li>')
    body = f'<ul class="why-list">{"".join(rows)}</ul>' if rows else f'<p>{esc(L.t("why_flat"))}</p>'
    return (f'<section class="why" id="porque" aria-labelledby="why-h">'
            f'<h2 id="why-h">{esc(L.t("why_h", rank=entry["r"]["rank"]))}</h2>{body}'
            f'<p class="why-note">{esc(L.t("why_note"))}</p></section>')


# ---------------------------------------------------------------- supervivencia
def survival(L: Lang, entry: dict, meta: dict) -> str:
    """Lo que dura en la simulación, en pequeño y al final: sirve para comparar Pokémon, no para prever una partida."""
    r, t = entry["r"], meta["time"]
    fill = r["time"] / t["max"] * 100
    med = t["median"] / t["max"] * 100
    text = L.t("surv_text", minutes=meta["method"]["seconds"] // 60, kind=L.t(BUILD_LOWER[r["best"]]),
               t=mmss(r["time"]), med=mmss(t["median"]))
    return (f'<section class="surv" id="supervivencia" aria-labelledby="surv-h">'
            f'<h2 id="surv-h">{esc(L.t("surv_h"))}</h2><p>{esc(text)}</p>'
            f'<div class="surv-bar" role="img" aria-label="{esc(L.t("surv_alt", t=mmss(r["time"]), med=mmss(t["median"]), max=mmss(t["max"])))}">'
            f'<b style="width:{fill:.2f}%"></b><i style="left:{med:.2f}%"></i></div></section>')


# ---------------------------------------------------------------- builds
def _gap_pct(high: float, low: float) -> int:
    return round((high - low) / high * 100) if high > 0 else 0


def _winner(pair: dict[str, dict]) -> str | None:
    """La build de mayor puntuación; con empate, ninguna."""
    if pair["melee"]["score"] == pair["ranged"]["score"]:
        return None
    return max(BUILD_NAME, key=lambda k: pair[k]["score"])


DMG_KEY = {"physical": "dmg_physical", "special": "dmg_special", "mixed": "dmg_mix"}
DMG_CLASS = {"physical": "physical", "special": "special", "mixed": "mix"}


def combo_html(L: Lang, mix: str, rng: str) -> str:
    """Tipo de daño y rango de una build, con las mismas etiquetas que los ataques: por ejemplo Físico · Cuerpo a cuerpo."""
    return (f'<span class="cat-tag is-{DMG_CLASS[mix]}">{esc(L.t(DMG_KEY[mix]))}</span>'
            f'<span class="rng-tag is-{rng}" title="{esc(L.t("rng_tip_" + rng))}">{esc(L.t(BUILD_NAME[rng]))}</span>')


def build_names(L: Lang, moves: dict[str, dict], b: dict) -> tuple[str, str]:
    """Los ataques de una build y sus potenciadores, ya unidos en una frase."""
    ids, nb = b["moves"], int(b["nBoost"])
    return (_join(L, [_move_name(L, moves, m) for m in ids[:len(ids) - nb]]),
            _join(L, [_move_name(L, moves, m) for m in ids[len(ids) - nb:]]))


def _build_answer(L: Lang, moves: dict[str, dict], pair: dict[str, dict], best: str) -> str:
    parts = []
    for kind in (best, BUILD_OTHER_KIND[best]):
        attacks, boosts = build_names(L, moves, pair[kind])
        parts.append(L.t("faq_a_build", kind=L.t(BUILD_NAME[kind]), attacks=attacks, buffs=boosts,
                         start=_move_name(L, moves, pair[kind]["moves"][0])))
    parts.append(L.t("faq_a_build_best", kind=L.t(BUILD_LOWER[best])))
    return " ".join(parts)


def _verdict(L: Lang, kind: str, b: dict, other: dict, win: str | None) -> str:
    if win == kind:
        return f'<p class="bd-verdict is-best">{esc(L.t("bd_best"))}</p>'
    gap = _gap_pct(other["score"], b["score"])
    if win is None or gap == 0:
        return f'<p class="bd-verdict">{esc(L.t("bd_tie"))}</p>'
    key = "bd_gap_small" if gap < GAP_SMALL_PCT else "bd_gap"
    return f'<p class="bd-verdict">{esc(L.t(key, pct=L.pcts(gap), other=L.t(BUILD_OTHER[kind])))}</p>'


def _move_row(L: Lang, assets: str, moves: dict[str, dict], mid: str, n: str, boost: bool, start: bool) -> str:
    """Una fila de la build: número, icono del juego, nombre, etiquetas y el tier del ataque en la fase 1. Los
    potenciadores van marcados, y el ataque con el que empieza lleva la marca dorada."""
    m = moves[mid]
    ico = (f'<span class="bd-ico"><img src="{assets}img/moves/{mid}.svg" width="32" height="32" alt="" '
           f'decoding="async"></span>' if "icon" in m else "")
    cls = "bd-row" + (" is-buff" if boost else "") + (" is-start" if start else "")
    pill = f'<span class="bd-pill is-gold">{esc(L.t("bd_start_with"))}</span>' if start else ""
    tier = (f'<span class="tier-badge mini {m["tier"]}" title="{esc(L.t("mv_tier_tip", t=m["tier"]))}">{m["tier"]}</span>'
            if "tier" in m else "")
    return (f'<li class="{cls}"><span class="bd-n">{n}</span>{ico}<span class="bd-info"><span class="bd-nm">'
            f'{esc(_move_name(L, moves, mid))}</span>{pill}{move_tags(L, m)}</span>{tier}</li>')


def _build_option(L: Lang, assets: str, moves: dict[str, dict], kind: str, b: dict, other: dict, win: str | None) -> str:
    """Una de las dos builds: veredicto, ataques en filas y lo que hace en partida."""
    head = f'<h3 class="bd-kind">{combo_html(L, b["mix"], kind)}</h3>'
    ids, nb = b["moves"], int(b["nBoost"])
    rows = "".join(_move_row(L, assets, moves, mid, str(i + 1), i >= len(ids) - nb, i == 0) for i, mid in enumerate(ids))
    stats = (f'<dl class="bd-stats">'
             f'<div><dt>{esc(L.t("bd_time"))}</dt><dd>{mmss(b["time"])}</dd></div>'
             f'<div><dt>{esc(L.t("bd_kills"))}</dt><dd>{esc(L.num(b["kills"]))}</dd></div>'
             f'<div><dt>{esc(L.t("bd_dealt"))}</dt><dd>{esc(L.num(b["dealt"]))}</dd></div>'
             f'<div><dt>{esc(L.t("bd_score"))}</dt><dd>{esc(L.dec(b["score"], 1))}</dd></div></dl>')
    best = " is-best" if win == kind else ""
    return (f'<article class="bd-opt{best}" data-build="{kind}">{head}'
            f'{_verdict(L, kind, b, other, win)}<ol class="bd-rows">{rows}</ol>{stats}</article>')


def builds(L: Lang, assets: str, entry: dict, moves: dict[str, dict], start_move: str) -> str:
    pair = entry["builds"]
    win = _winner(pair)
    order = (entry["r"]["best"], BUILD_OTHER_KIND[entry["r"]["best"]])
    options = "".join(_build_option(L, assets, moves, k, pair[k], pair[BUILD_OTHER_KIND[k]], win) for k in order)
    t = entry["types"]
    tint = f'--p1:{typedata.TYPE_COLOR[t[0]]};--p2:{typedata.TYPE_COLOR[t[-1]]}'
    return (f'<section class="fig fig-build" id="build" aria-labelledby="bd-h">'
            f'<div class="bd-card" style="{tint}"><header class="bd-head"><h2 id="bd-h">{esc(L.t("t_builds"))}</h2></header>'
            f'<div class="bd-pair">{options}</div>'
            f'<p class="bd-default">{esc(L.t("build_default_start", move=_move_name(L, moves, start_move)))}</p>'
            f'</div></section>')


# ---------------------------------------------------------------- estadísticas
STAT_ROWS = (("pa", "cb_pa", 2, "×"), ("sa", "cb_sa", 2, "×"), ("hp", "st_hp", 0, ""), ("df", "cb_df", 0, ""),
             ("sd", "cb_sd", 0, ""), ("spd", "st_spd", 0, ""), ("size", "st_size", 1, ""), ("types", "st_types", 2, "×"))


def stats(L: Lang, entry: dict) -> str:
    rows = []
    for key, label, digits, pre in STAT_ROWS:
        v, pct = entry["game"][key], entry["pct"][key]
        shown = pre + (L.dec(v, digits) if digits else str(round(v)))
        rows.append(f'<li><span class="st-name">{esc(L.t(label))}</span><output>{esc(shown)}</output>'
                    f'{_pct_bar(pct, L.t("pct_alt", pct=pct))}</li>')
    return (f'<section class="sheet stats" id="stats" aria-labelledby="stats-h">'
            f'<h2 id="stats-h">{esc(L.t("st_h"))}</h2><ul class="st-list">{"".join(rows)}</ul>'
            f'<p class="why-note">{esc(L.t("st_note", n=catalog.TOTAL))}</p></section>')


# ---------------------------------------------------------------- página
def head_texts(L: Lang, entry: dict, moves: dict[str, dict]) -> tuple[str, str]:
    """<title> y meta description de la ficha, con el tier, el puesto y la mejor build."""
    name, (rank, tier) = L.mon(entry), (entry["r"]["rank"], entry["r"]["tier"])
    attacks, buffs = build_names(L, moves, entry["builds"][entry["r"]["best"]])
    title = L.t("fh_title", name=name, tier=tier)
    desc = L.t("fh_desc_buffs", name=name, tier=tier, rank=rank, total=catalog.TOTAL, attacks=attacks, buffs=buffs,
               banner=L.banner(entry["banner"]))
    return title, desc


def build(L: Lang, home: str, sprites: str, ext: str, entry: dict, moves: dict[str, dict], meta: dict,
          start_move: str, prev: dict | None, nxt: dict | None, odds: tuple[float, int], *,
          guides: str, url: str, title: str, assets: str) -> tuple[str, str]:
    """Devuelve el HTML visible (sin <head>) y el JSON-LD de las preguntas. start_move es el ataque con el que empieza de
    serie en el juego; guides, el bloque de enlaces a las listas."""
    name = L.mon(entry)
    rank, tier = entry["r"]["rank"], entry["r"]["tier"]
    p_pull, pulls = odds
    if not p_pull or not pulls:
        raise ValueError(f"{entry['dex']}: la tirada no tiene probabilidad")
    pct = L.dec(p_pull * 100, _digits(p_pull * 100))
    banner = L.banner(entry["banner"])
    faqs = _faqs(L, tier, rank, _build_answer(L, moves, entry["builds"], entry["r"]["best"]), banner,
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
<h1>{esc(name)} {other}<small class="fh-dex">{esc(L.t("dex_no", dex=entry["dex"]))}</small></h1>
<div class="facts"><span class="types">{pills}</span>
<span class="rarity r{rarity}" role="img" aria-label="{rarity_name}" title="{rarity_name}"><svg class="rball" viewBox="0 0 12 12" aria-hidden="true"><use href="#rball-{rarity}"/></svg></span>
{legendary}{region}</div>
<p class="rankline"><i class="ico ico-trophy" aria-hidden="true"></i><strong>{rank}</strong><span>/ {catalog.TOTAL}</span></p>
</div>
</header>
{why(L, entry, moves)}
{builds(L, assets, entry, moves, start_move)}
{stats(L, entry)}
{survival(L, entry, meta)}
<nav class="pager" aria-label="{esc(L.t("pager_aria"))}">{pager}</nav>
</article>
<section class="sheet" id="obtain" aria-labelledby="obtain-h">
<h2 id="obtain-h">{esc(L.t("sheet_obtain_h"))}</h2>
<p>{esc(faqs[-1][1])} <a href="{home}gachas.html">{esc(L.t("nav_gachas"))}</a></p>
</section>
<section class="sheet faq" id="faq" aria-labelledby="faq-h">
<h2 id="faq-h">{esc(L.t("sheet_faq_h"))}</h2>
<dl>{faq_html}</dl>
</section>
{guides}
"""
    return html, jsonld(faqs, meta["generatedAt"][:10], url, title, "en" if L.en else "es")
