"""HTML estático de una ficha: lo que un buscador lee sin ejecutar JavaScript.

Los números salen de los datos ya generados (ranking, species.json, moves.json) y de la misma
regla de tirada que build/catalog.py (RATES y el pool de rareza más cercano). No hay cifras nuevas.
No hay aparición salvaje en los datos: solo el banner de gacha.
"""
from __future__ import annotations

import json
import math
import unicodedata
from html import escape

import catalog
import charts
import legal
import regions
import typedata
from i18n import Lang
from slugs import species_path

STAT_KEYS = ("bs_hp", "bs_atk", "bs_def", "bs_spa", "bs_spd", "bs_spe")


def esc(x) -> str:
    return escape(str(x), quote=True)


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


def card_answer(L: Lang, names: list[str], n_once: int, keep_evolves: bool) -> str:
    """La misma frase en la FAQ y en el JSON-LD. `n_once` es la carta que se coge una vez y no se repite."""
    if n_once == 1 and len(names) >= 2:
        return L.t("faq_a_cards_once", once=names[0], card=_join(L, names[1:]))
    cards = _join(L, names)
    if keep_evolves:
        return L.t("faq_a_cards_evo", cards=cards)
    return L.t("faq_a_cards", cards=cards)


def _need_id(cards: dict, name: str | None) -> str | None:
    if not name:
        return None
    for cid, card in cards.items():
        if card["name"] == name:
            return cid
    raise KeyError(name)


def _faqs(L: Lang, tier: str, rank: int, attacks: str, buffs: str, n_buffs: int, super_pct: int,
          cards: str, banner: str, legendary: bool, pct: str, pulls: int) -> list[tuple[str, str]]:
    worth = (L.t("faq_q_worth"), L.t(f"faq_a_{tier}", rank=rank, total=charts.TOTAL))
    if n_buffs == 0:
        head = L.t("faq_a_moves_plain", attacks=attacks)
    elif n_buffs == 1:
        head = L.t("faq_a_moves_one", attacks=attacks, buffs=buffs)
    else:
        head = L.t("faq_a_moves", attacks=attacks, buffs=buffs)
    cover = L.t("faq_a_cover", super=L.pcts(super_pct)) if super_pct else L.t("faq_a_cover_none")
    out = [worth, (L.t("faq_q_moves"), f"{head} {cover}")]
    if cards:
        out.append((L.t("faq_q_cards"), cards))
    where = L.t("faq_get_where_leg" if legendary else "faq_get_where", banner=banner)
    out.append((L.t("faq_q_get"), f"{where} {L.t('faq_get_odds', pct=pct, n=L.num(pulls))}"))
    return out


def jsonld(faqs: list[tuple[str, str]]) -> str:
    doc = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
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


def build(L: Lang, home: str, sprites: str, ext: str, entry: dict, detail: list, moves: dict[str, dict],
          prev: dict | None, nxt: dict | None, odds: tuple[float, int], cards: dict) -> tuple[str, str]:
    """Devuelve el HTML visible (sin <head>) y el JSON-LD de las preguntas."""
    name = L.mon(entry)
    rank, tier = entry["r"]["rank"], entry["r"]["tier"]
    methods = entry["r"]["methods"]
    stats = list(entry["stats"])
    if len(stats) != 6:
        raise ValueError(f"{entry['dex']}: se esperaban 6 estadísticas base")
    super_pct, neutral_pct, ids, _atk_types, _alts, n_boost = detail[9]
    n_boost = int(n_boost)
    if n_boost > len(ids):
        raise ValueError(f"{entry['dex']}: más potenciadores que ataques en el grupo")
    buff_ids = ids[-n_boost:] if n_boost else []
    atk_ids = ids[:-n_boost] if n_boost else list(ids)
    attacks = _join(L, [_move_name(L, moves, mid) for mid in atk_ids])
    buffs = _join(L, [_move_name(L, moves, mid) for mid in buff_ids])
    p_pull, pulls = odds
    if not p_pull or not pulls:
        raise ValueError(f"{entry['dex']}: la tirada no tiene probabilidad")
    pct = L.dec(p_pull * 100, _digits(p_pull * 100))
    banner = L.banner(entry["banner"])
    card_ids, n_once = detail[10]
    card_names = [_card_name(L, cards[c]) for c in card_ids]
    need_ids = []
    for mid in ids:
        nid = _need_id(cards, moves[mid].get("needsCard"))
        if nid:
            need_ids.append(nid)
    keep_evolves = n_once == 0 and bool(card_ids) and card_ids[0] in need_ids
    card_text = card_answer(L, card_names, n_once, keep_evolves) if card_names else ""
    faqs = _faqs(L, tier, rank, attacks, buffs, len(buff_ids), int(super_pct), card_text, banner,
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
    buff_set = set(buff_ids)
    chips = "".join(
        f'<li class="is-buff">{esc(_move_name(L, moves, mid))}</li>' if mid in buff_set
        else f"<li>{esc(_move_name(L, moves, mid))}</li>"
        for mid in ids)
    card_chips = []
    for i, name in enumerate(card_names):
        if i < n_once:
            note = L.t("build_once")
        elif n_once == 0 and keep_evolves:
            note = L.t("build_first_evo")
        elif n_once == 0:
            note = L.t("build_keep")
        else:
            note = L.t("build_then")
        card_chips.append(f"<li>{esc(name)} <small>{esc(note)}</small></li>")
    card_list = "".join(card_chips)
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
<h1>{esc(name)} {other}<small class="fh-dex">{esc(L.t("dex_no", dex=entry["dex"]))}</small></h1>
<div class="facts"><span class="types">{pills}</span>
<span class="rarity r{rarity}" role="img" aria-label="{rarity_name}" title="{rarity_name}"><svg class="rball" viewBox="0 0 12 12" aria-hidden="true"><use href="#rball-{rarity}"/></svg></span>
{legendary}{region}</div>
<p class="rankline"><i class="ico ico-trophy" aria-hidden="true"></i><strong>{rank}</strong><span>/ {charts.TOTAL}</span></p>
<p class="simline">{esc(L.t("sheet_sim_line", rank=methods["simBest"]))}</p>
<p class="simline">{esc(L.t("sheet_open_line", rank=methods["simStart"]))}</p>
</div>
</header>
<section class="fig fig-build" id="build" aria-labelledby="bd-h">
<div class="bd-card" style="--p1:{tc};--p2:{tc2}">
<header class="bd-head"><div><h2 id="bd-h">{esc(L.t("t_build"))}</h2><span class="bd-who">{esc(name)}</span></div></header>
<p class="bd-cap">{esc(L.t("build_group"))}</p>
<ul class="bond">{chips}</ul>
<p class="bd-cap">{esc(L.t("build_cards"))}</p>
<ul class="bond">{card_list}</ul>
<p>{esc(L.t("sheet_a_build", attacks=attacks, buffs=buffs) if buffs else L.t("sheet_a_build_plain", attacks=attacks))}</p>
<p class="muted">{esc(L.t("sheet_a_cover", super=L.pcts(int(super_pct)), neutral=L.pcts(int(neutral_pct))))}</p>
</div>
</section>
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
"""
    return html, jsonld(faqs)
