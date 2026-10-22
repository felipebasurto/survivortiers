"""HTML de la ficha de cada Pokémon: puesto, mejores builds, por qué está ahí y sus estadísticas.

Los números salen de los datos ya generados (build/catalog.py, data/bounded_ranking.json, data/species_why.csv,
moves.json) y de la misma regla de tirada que build/catalog.py (RATES y el pool de rareza más cercano). No hay cifras
nuevas. No hay aparición salvaje en los datos: solo la gacha de su región.
"""
from __future__ import annotations

import json
import math
import unicodedata
from html import escape

import bounded_view
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
    inv = (f'<span class="mv-inv" title="{esc(L.t("mv_inv_tip"))}">{esc(L.t("mv_inv_tag"))}</span>'
           if move["kind"] == "dash" else "")
    return label + inv + mark


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




def _obtain(L: Lang, region: str, legendary: bool, pct: str, pulls: int) -> str:
    where = L.t("faq_get_where_leg" if legendary else "faq_get_where", banner=region)
    return f"{where} {L.t('faq_get_odds', pct=pct, n=L.num(pulls))}"


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
            f'<h2 id="why-h">{esc(L.t("why_h", rank=entry["r"]["rank"]))}</h2>{body}</section>')


# ---------------------------------------------------------------- estadísticas
_BARS = (("hp", "st_hp", 0, ""), ("pa", "cb_pa", 2, "×"), ("sa", "cb_sa", 2, "×"), ("df", "cb_df", 0, ""),
         ("sd", "cb_sd", 0, ""), ("spd", "st_spd", 0, ""))
_EXTRA = (("size", "st_size", 1, ""), ("types", "st_types", 2, "×"))


def _shown(L: Lang, v: float, digits: int, pre: str) -> str:
    return pre + (L.dec(v, digits) if digits else str(round(v)))


def stats(L: Lang, entry: dict) -> str:
    bars = "".join(
        f'<li><span class="st-name">{esc(L.t(lab))}</span><output>{esc(_shown(L, entry["game"][key], digits, pre))}</output>'
        f'{_pct_bar(entry["pct"][key], L.t("pct_alt", pct=entry["pct"][key]))}</li>' for key, lab, digits, pre in _BARS)
    extra = "".join(f'<li><span>{esc(L.t(lab))}</span> <b>{esc(_shown(L, entry["game"][key], digits, pre))}</b></li>'
                    for key, lab, digits, pre in _EXTRA)
    return (f'<section class="sheet stats" id="stats" aria-labelledby="stats-h">'
            f'<h2 id="stats-h">{esc(L.t("st_h"))}</h2><ul class="st-list">{bars}</ul>'
            f'<ul class="st-extra">{extra}</ul></section>')


# ---------------------------------------------------------------- página
def head_texts(L: Lang, entry: dict, moves: dict[str, dict]) -> tuple[str, str]:
    """<title> y meta description de la ficha, con el tier, el puesto y la mejor build."""
    name, (rank, tier) = L.mon(entry), (entry["r"]["rank"], entry["r"]["tier"])
    _, b = bounded_view.best_build(entry["dex"])
    title = L.t("fh_title", name=name, tier=tier)
    desc = L.t("fh_desc", name=name, tier=tier, rank=rank, total=catalog.TOTAL,
               moves=_join(L, [bounded_view.move_name(L, m, moves) for m in b["attacks"]]), banner=L.banner(entry["banner"]))
    return title, desc


def build(L: Lang, home: str, sprites: str, ext: str, entry: dict, moves: dict[str, dict], meta: dict,
          start_move: str, prev: dict | None, nxt: dict | None, odds: tuple[float, int], *,
          guides: str, tms: str) -> str:
    """Devuelve el HTML visible (sin <head>). guides es el bloque de enlaces a las listas; tms, la lista de MT."""
    name = L.mon(entry)
    rank, tier = entry["r"]["rank"], entry["r"]["tier"]
    p_pull, pulls = odds
    if not p_pull or not pulls:
        raise ValueError(f"{entry['dex']}: la tirada no tiene probabilidad")
    pct = L.dec(p_pull * 100, _digits(p_pull * 100))
    banner = L.banner(entry["banner"])
    obtain = _obtain(L, banner, bool(entry["legendary"]), pct, pulls)
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
{bounded_view.builds_section(L, entry["dex"], moves)}
{tms}
{why(L, entry, moves)}
{stats(L, entry)}
<section class="sheet" id="obtain" aria-labelledby="obtain-h">
<h2 id="obtain-h">{esc(L.t("sheet_obtain_h"))}</h2>
<p>{esc(obtain)} <a href="{home}coleccion.html">{esc(L.t("nav_coleccion"))}</a></p>
</section>
</article>
<nav class="pager" aria-label="{esc(L.t("pager_aria"))}">{pager}</nav>
{guides}
"""
    return f'<div class="ficha-col">{html}</div>'
