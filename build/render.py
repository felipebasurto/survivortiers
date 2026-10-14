"""Genera las páginas HTML de site/ (español) y site/en/ (inglés) a partir de site/data/*.json, que escribe
build/catalog.py.

    python3 build/catalog.py && python3 build/render.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import charts  # noqa: E402
import legal  # noqa: E402
import typedata  # noqa: E402
from i18n import ES, LANGS, Lang  # noqa: E402

SITE = ROOT / "site"
DATA = SITE / "data"
TEMPLATES = Path(__file__).resolve().parent / "templates"
SCALE_LIST, FICHA_BOX = 2, 170  # px del lado mayor del sprite en la ficha, para que quepa en su caja
TIERS = ["S", "A", "B", "C", "D"]
UNSURE = 50  # % de repeticiones en su tier por debajo del cual el tier se marca como dudoso
CATEGORIES = [("melee", "cuerpo a cuerpo"), ("ranged", "distancia"), ("stat", "estadística")]  # (id, valor del CSV)
NAV = [("index", "index.html", "nav_tiers"), ("metodo", "metodo.html", "nav_metodo"),
       ("ataques", "ataques.html", "nav_ataques"), ("gachas", "gachas.html", "nav_gachas"),
       ("coleccion", "coleccion.html", "nav_coleccion"), ("acerca", "acerca.html", "nav_acerca")]
REPEAT_RANKS = (2, 40, 150, 350, 650)  # puestos de los Pokémon que salen en la ilustración de repeticiones
PILLAR_KEYS = ("stats", "moves", "typedef", "size")
ARENA_DEX = 25


class RenderError(RuntimeError):
    pass


@dataclass(frozen=True)
class Ctx:
    """Idioma y posición de una página: de dónde cuelgan los recursos y los enlaces."""
    L: Lang
    rel: str            # ruta de la página dentro de su idioma, por ejemplo "index.html" o "pokemon/25.html"
    assets: str         # prefijo hasta la raíz del sitio, donde viven style.css, sprites/ y data/
    home: str           # prefijo hasta la raíz de este idioma, donde viven los enlaces del menú
    other: str | None   # enlace a la misma página en el otro idioma, o None si no existe

    @staticmethod
    def of(L: Lang, rel: str) -> "Ctx":
        up = "../" * rel.count("/")
        assets = up + ("../" if L.en else "")
        return Ctx(L, rel, assets, up, f"{assets}{'' if L.en else 'en/'}{rel}")


def asset_version() -> str:
    """Huella corta de style.css y app.js: cambia con cada edición y evita ver el CSS viejo en caché."""
    h = hashlib.sha1()
    for name in ("style.css", "app.js"):
        h.update((SITE / name).read_bytes())
    return h.hexdigest()[:8]


BASE = Template((TEMPLATES / "base.html").read_text(encoding="utf8"))


def esc(x) -> str:
    return escape(str(x), quote=True)


def load(name: str):
    path = DATA / name
    if not path.exists():
        raise RenderError(f"falta {path}: ejecuta antes python3 build/catalog.py")
    return json.loads(path.read_text(encoding="utf8"))


# ---------------------------------------------------------------- piezas
def type_pill(L: Lang, t: str) -> str:
    return (f'<span class="type" style="--tc:{typedata.TYPE_COLOR[t]};--tg:{typedata.text_color(t)}">{typedata.glyph_svg(t)}'
            f'<span>{esc(L.type_name(t))}</span></span>')


def type_pills(L: Lang, types: list[str]) -> str:
    return '<span class="types">' + "".join(type_pill(L, t) for t in types) + "</span>"


def tier_badge(L: Lang, t: str) -> str:
    return f'<span class="tier-badge {t}" title="{esc(L.t("tier", t=t))}">{t}</span>'


def stars(L: Lang, n: int) -> str:
    return f'<span class="stars" role="img" aria-label="{esc(L.t("stars_alt", n=n))}">{"★" * n}{"☆" * (5 - n)}</span>'


def icon(name: str) -> str:
    return f'<i class="ico ico-{name}" aria-hidden="true"></i>'


def mon_card(c: Ctx, p: dict) -> str:
    L = c.L
    rank, tier, _, _, ptier = p["r"]
    w, h = p["w"] * SCALE_LIST, p["h"] * SCALE_LIST
    unsure = ptier < UNSURE
    name = L.mon(p)
    hint = L.t("card_hint", share=ptier, tier=tier) if unsure else ""
    title = L.t("card_title", name=name, dex=p["dex"], rank=rank, tier=tier, hint=hint)
    return (f'<a class="{"mon unsure" if unsure else "mon"}" href="{c.home}pokemon/{p["dex"]}.html" data-dex="{p["dex"]}" '
            f'title="{esc(title)}">'
            f'<span class="sp"><img class="px" src="{c.assets}sprites/{p["dex"]}.png" width="{w}" height="{h}" alt="" '
            f'loading="lazy" decoding="async"></span>'
            f'<span class="nm">{esc(name)}</span><span class="rk">{rank}</span></a>')


def page(c: Ctx, page_id: str, title: str, description: str, content: str, meta: dict) -> str:
    L = c.L
    current = ' aria-current="page"'
    nav = "\n".join(
        f'      <a href="{c.home}{href}"{current if pid == page_id else ""}>{esc(L.t(key))}</a>' for pid, href, key in NAV)
    footer_nav = "\n".join(f'      <a href="{c.home}{href}">{esc(L.t(key))}</a>' for _, href, key in NAV)
    lic = meta["spriteLicense"]
    sprites_line = L.t("sprites_line_html", url=esc(lic["sourceUrl"]), source=esc(lic["source"]),
                       lic_url=esc(lic["url"]), lic=esc(lic["name"]), about=f"{c.home}acerca.html")
    model_line = L.t("model_line", game=esc(legal.GAME_NAME), commit=esc(meta["gameCommit"]),
                     version=esc(L.t("version_name")), date=esc(meta["generatedAt"][:10]))
    switch, alternates = "", ""
    if c.other:
        other = "es" if L.en else "en"
        links = "".join(
            f'<a href="{c.other if code != L.code else "#"}" lang="{code}" hreflang="{code}"'
            f'{current if code == L.code else ""}>{code.upper()}</a>' for code in ("es", "en"))
        switch = f'<nav class="lang" aria-label="{esc(L.t("lang_label"))}">{links}</nav>'
        alternates = f'<link rel="alternate" hreflang="{other}" href="{c.other}">'
    return BASE.substitute(
        lang=L.code, assets=c.assets, home=c.home, asset_v=asset_version(), page_id=page_id, title=esc(title),
        description=esc(description), alternates=alternates, skip=esc(L.t("skip")), unofficial=esc(L.t("unofficial")),
        nav_aria=esc(L.t("nav_main")), foot_aria=esc(L.t("nav_foot")), switch=switch, nav=nav, content=content,
        footer_nav=footer_nav, disclaimer=esc(L.t("disclaimer", game=legal.GAME_NAME)), sprites_line=sprites_line,
        model_line=model_line, no_tracking=esc(L.t("no_tracking")))


def write(rel: str, text: str) -> None:
    path = SITE / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8")


# ---------------------------------------------------------------- páginas
def render_index(c: Ctx, pokemon: list[dict], meta: dict) -> str:
    L = c.L
    cuts = {t["tier"]: t for t in meta["tierCuts"]}
    sections = []
    for t in TIERS:
        mons = sorted((p for p in pokemon if p["r"][1] == t), key=lambda p: p["r"][0])
        cut = cuts[t]
        cards = "".join(mon_card(c, p) for p in mons)
        head = L.t("tier_head", a=cut["from"], b=cut["to"], n=f'<span class="n">{len(mons)}</span>')
        sections.append(
            f'<section class="tier tier-{t}" id="tier-{t}" aria-label="{esc(L.t("tier", t=t))}">'
            f'<header class="tier-head"><b>{t}</b>{icon("crown") if t == "S" else ""}<span>{head}</span></header>'
            f'<div class="grid">{cards}</div></section>')
    a, b, c3 = (L.mon(x) for x in meta["top"])
    lead = L.t("index_lead_html", a=esc(a), b=esc(b), c=esc(c3), n=meta["total"], method=f"{c.home}metodo.html")
    content = f"""
<h1>{esc(L.t("index_h1", game=legal.GAME_NAME))}</h1>
<p class="lead">{lead}</p>
<div class="controls">
  <div class="field"><label for="q">{esc(L.t("search_label"))}</label>
    <input id="q" type="search" placeholder="{esc(L.t("search_ph"))}" autocomplete="off" spellcheck="false"></div>
  <p id="count" aria-live="polite"></p>
</div>
<p class="key"><span class="u-key" aria-hidden="true"></span> {esc(L.t("unsure_key"))}</p>
<div id="tierlist">
{"".join(sections)}
</div>
<noscript><p class="muted">{esc(L.t("noscript"))}</p></noscript>
"""
    return page(c, "index", L.t("index_title", site=legal.SITE_NAME, game=legal.GAME_NAME),
                L.t("index_desc", n=meta["total"], game=legal.GAME_NAME), content, meta)


def verdict(L: Lang, r: dict) -> str:
    """Una frase: tier, puesto y cuánto se repite ese tier entre las 2.000 repeticiones."""
    share, t = round(r["pTier"] * 100), r["tier"]
    key = "verdict_firm" if share >= 80 else "verdict_mid" if share >= UNSURE else "verdict_low"
    return (f'{tier_badge(L, t)} <strong>{esc(L.t("verdict_rank", rank=r["rank"], total=charts.TOTAL))}</strong> '
            f'{esc(L.t(key, share=share, t=t))}')


def notes(L: Lang, r: dict) -> str:
    f = r["flags"]
    items = [L.t(key) for flag, key in (("statusUnmodelled", "note_status"), ("melee", "note_melee"),
                                        ("statsCapped", "note_capped")) if f[flag]]
    if not items:
        return ""
    return f'<h2>{esc(L.t("notes_h"))}</h2><ul class="plain">' + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"


def gloss(L: Lang, keys: tuple[str, ...]) -> str:
    return "".join(f'<dt>{esc(L.t(k))}</dt><dd>{esc(L.t(k + "_d", total=charts.TOTAL))}</dd>' for k in keys)


class Moves:
    """Nombres de movimientos por id, en cada idioma."""

    def __init__(self, moves: list[dict]):
        self.by_id = {m["id"]: m for m in moves}

    def name(self, L: Lang, move_id: str) -> str:
        m = self.by_id[move_id]
        return m["en"]["name"] if L.en else m["name"]


def render_ficha(c: Ctx, p: dict, prev_p: dict | None, next_p: dict | None, meta: dict, mv: Moves) -> str:
    L = c.L
    s, r = p["sprite"], p["r"]
    name = L.mon(p)
    scale = max(1, min(5, FICHA_BOX // max(s["w"], s["h"])))
    w, h = s["w"] * scale, s["h"] * scale
    legendary = f'<span class="chip">{esc(L.t("legendary"))}</span>' if p["legendary"] else ""

    def link(q: dict, left: bool) -> str:
        label = f'{esc(L.mon(q))}<span> {esc(L.t("dex_no", dex=q["dex"]))}</span>'
        return f'<a href="{q["dex"]}.html">{"← " + label if left else label + " →"}</a>'

    pager = (link(prev_p, True) if prev_p else "<span></span>") + (link(next_p, False) if next_p else "<span></span>")
    other_name = f'<small>{esc(p["nameEn"])}</small>' if not L.en and p["nameEn"] != p["name"] else ""
    pair = ""
    if r["pair"]:
        pair = "<p>" + L.t("pair_html", pair=" + ".join(esc(mv.name(L, m["id"])) for m in r["pair"])) + "</p>"
    sim = charts.sim_dots(L, r, meta["simRange"], meta["simMedianSeconds"], lambda i: mv.name(L, i))
    content = f"""
<p class="crumbs"><a href="{c.home}index.html">{esc(L.t("crumb_home"))}</a> › {esc(name)}</p>
<article>
<div class="ficha-head">
  <div class="ficha-sprite"><img class="px" src="{c.assets}sprites/{p["dex"]}.png" width="{w}" height="{h}"
    alt="{esc(L.t("sprite_alt", name=name))}"></div>
  <div>
    <h1>{esc(name)} {other_name}<small>{esc(L.t("dex_no", dex=p["dex"]))}</small></h1>
    <div class="facts">{type_pills(L, p["types"])} {stars(L, p["rarity"])} {legendary}
      <span class="muted">{esc(L.t("gacha_banner", name=L.banner(p["banner"])))}</span></div>
  </div>
</div>
<p class="verdict">{verdict(L, r)}</p>
{charts.rank_band(L, r, name)}
{charts.pillars(L, r, name)}
{charts.methods(L, r, name)}
{sim}
{pair}
{notes(L, r)}
<p class="muted small">{L.t("ficha_foot_html", href=f"{c.home}metodo.html")}</p>
<details class="how"><summary>{esc(L.t("ficha_how"))}</summary><dl class="gloss">{gloss(L, ("gl_rank", "gl_pct", "gl_med", "gl_band"))}</dl></details>
<nav class="pager" aria-label="{esc(L.t("pager_aria"))}">{pager}</nav>
</article>
"""
    label = name if L.en or p["nameEn"] == p["name"] else f'{p["name"]} ({p["nameEn"]})'
    desc = L.t("ficha_desc", label=label, tier=r["tier"], rank=r["rank"], total=charts.TOTAL, game=legal.GAME_NAME)
    return page(c, "ficha", L.t("ficha_title", name=name, tier=r["tier"], site=legal.SITE_NAME), desc, content, meta)


def move_card(L: Lang, m: dict) -> str:
    en = m["en"]
    name = en["name"] if L.en else m["name"]
    if "buff" in m:
        b = m["buff"]
        amount = L.pcts(b["amount"]) if b["pct"] else L.dec(b["amount"])
        text = L.t("mv_buff_text", stat=L.t("st_" + b["stat"]), amount=amount, dur=b["dur"], cd=L.dec(b["cd"], 2))
        bars = charts.buff_bars(L, b)
        extra = f'<p class="mv-note">{esc(L.t("mv_weave", w=L.dec(b["weave"], 2)))}</p>'
    else:
        text, bars, extra = "", charts.move_bars(L, m["rel"]), ""
    evo = ""
    if m["evolvesTo"]:
        evo = f'<p class="mv-note">{esc(L.t("mv_evo", evo=en["evolvesTo"] if L.en else m["evolvesTo"], card=en["needsCard"] if L.en else m["needsCard"]))}</p>'
    kind = f'<span class="mv-kind">{esc(L.t("mk_" + m["kind"]))}</span>'
    intro = f'<p class="mv-note">{esc(text)}</p>' if text else ""
    return (f'<li class="mv"><div class="mv-head"><h4>{esc(name)}</h4>{type_pill(L, m["type"])}{kind}{evo}</div>'
            f'<div class="mv-body">{intro}{bars}{extra}</div></li>')


def moves_howto(L: Lang, moves: list[dict]) -> str:
    example = next(m for m in moves if m["category"] == CATEGORIES[0][1] and m["rank"] == 1)
    n = sum(1 for m in moves if "rel" in m)
    terms = gloss(L, ("mv_g_dps15", "mv_g_ttd15", "mv_g_dps5", "mv_g_buff", "mv_g_tier"))
    return (f'<section class="howto anim"><h2>{esc(L.t("mv_howto_h"))}</h2><p>{esc(L.t("mv_howto_p", n=n))}</p>'
            f'<div class="howto-ex"><h3>{esc(L.t("mv_howto_ex"))}</h3><ul class="mv-list">{move_card(L, example)}</ul>'
            f'{charts.move_scale(L)}</div><dl class="gloss">{terms}</dl></section>')


def render_ataques(c: Ctx, moves: list[dict], meta: dict) -> str:
    L = c.L
    blocks, toc = [], []
    for cat_id, cat_csv in CATEGORIES:
        inner = []
        for t in TIERS:
            ms = sorted((m for m in moves if m["category"] == cat_csv and m["tier"] == t), key=lambda m: m["rank"])
            if not ms:
                continue
            items = "".join(move_card(L, m) for m in ms)
            inner.append(f'<div class="mv-tier anim"><h3>{tier_badge(L, t)} <span>{esc(L.t("tier", t=t))}</span> '
                         f'<small>{len(ms)}</small></h3><ul class="mv-list">{items}</ul></div>')
        icon_name = {"melee": "sword", "ranged": "bow", "stat": "sparkle"}[cat_id]
        blocks.append(f'<section id="{cat_id}"><h2>{icon(icon_name)}{esc(L.t("cat_" + cat_id))}</h2>'
                      f'<p class="muted">{esc(L.t("cat_" + cat_id + "_text"))}</p>{"".join(inner)}</section>')
        toc.append(f'<li><a href="#{cat_id}">{esc(L.t("cat_" + cat_id))}</a></li>')
    content = f"""
<h1>{esc(L.t("ataques_h1"))}</h1>
<p class="lead">{esc(L.t("ataques_lead", n=len(moves)))}</p>
<ul class="toc">{"".join(toc)}</ul>
{moves_howto(L, moves)}
{"".join(blocks)}
"""
    return page(c, "ataques", L.t("ataques_title", site=legal.SITE_NAME),
                L.t("ataques_desc", n=len(moves), game=legal.GAME_NAME), content, meta)


def render_gachas(c: Ctx, gachas: list[dict], meta: dict) -> str:
    L = c.L
    ordered = sorted(gachas, key=lambda g: -g["sPlusARate"])
    rows = "".join(
        f'<tr><th scope="row">{esc(L.banner(g["name"]))}</th><td class="num">{g["poolSize"]}</td>'
        f'<td class="num">{g["legendaryCount"]}</td><td class="num">{g["sCount"]}</td><td class="num">{g["aCount"]}</td>'
        f'<td class="num">{L.dec(g["sPlusARate"])}{"" if L.en else " "}%</td>'
        f'<td class="num">{L.dec(g["pullChance"])}{"" if L.en else " "}%</td></tr>' for g in ordered)
    pools = ", ".join(f'{L.banner(g["name"])} {g["poolSize"]}' for g in gachas)
    head = "".join(f'<th{"" if i == 0 else " class=" + chr(34) + "num" + chr(34)}>{esc(L.t(k))}</th>'
                   for i, k in enumerate(("th_banner", "th_pool", "th_leg", "th_s", "th_a", "th_pool_rate", "th_pull_rate")))
    content = f"""
<h1>{esc(L.t("gachas_h1"))}</h1>
<p class="lead">{L.t("gachas_lead_html")}</p>
{charts.composition(L, ordered)}
<h2>{esc(L.t("gachas_read_h"))}</h2>
<dl class="gloss">{gloss(L, ("gl2_pool", "gl2_sa", "gl2_rate", "gl2_pull"))}</dl>
<div class="tablewrap"><table>
<thead><tr>{head}</tr></thead>
<tbody>{rows}</tbody></table></div>
<h2>{esc(L.t("gachas_two_h"))}</h2>
<p>{L.t("gachas_two_html")}</p>
{charts.odds(L)}
<p class="muted">{esc(L.t("gachas_pools", pools=pools, total=meta["total"]))}</p>
"""
    return page(c, "gachas", L.t("gachas_title", site=legal.SITE_NAME), L.t("gachas_desc", game=legal.GAME_NAME),
                content, meta)


def render_coleccion(c: Ctx, meta: dict) -> str:
    L = c.L
    snippet = (ROOT / "console" / ("coleccion.en.js" if L.en else "coleccion.js")).read_text(encoding="utf8")
    content = f"""
<h1>{esc(L.t("col_h1"))}</h1>
<p class="lead">{esc(L.t("col_lead"))}</p>
<ol class="steps">
  <li>{L.t("col_step1_html")}</li>
  <li>{L.t("col_step2_html")}
    <pre class="snippet" id="snippet" tabindex="0">{esc(snippet)}</pre>
    <button class="btn ghost" type="button" id="copy-snippet">{esc(L.t("col_copy"))}</button>
    <span class="muted small" id="copy-msg" aria-live="polite"></span></li>
  <li>{L.t("col_step3_html")}</li>
</ol>
<div class="field"><label for="paste">{esc(L.t("col_json"))}</label>
  <textarea id="paste" spellcheck="false" placeholder='{{"version":1,"name":"…","updated":0,"dex":[…],"shiny":[…]}}'></textarea></div>
<div class="controls">
  <button class="btn" type="button" id="import">{esc(L.t("col_view"))}</button>
  <div class="field"><label for="file">{esc(L.t("col_file"))}</label><input id="file" type="file" accept="application/json,.json"></div>
</div>
<div id="result" aria-live="polite"></div>
<h2>{esc(L.t("col_limits"))}</h2>
<ul class="plain">
  <li>{L.t("col_l1_html")}</li>
  <li>{L.t("col_l2_html")}</li>
  <li>{L.t("col_l3_html")}</li>
  <li>{L.t("col_l4_html", commit=esc(meta["gameCommit"]))}</li>
  <li>{esc(L.t("col_l5"))}</li>
</ul>
"""
    return page(c, "coleccion", L.t("col_title", site=legal.SITE_NAME), L.t("col_desc", game=legal.GAME_NAME),
                content, meta)


def render_metodo(c: Ctx, index: list[dict], full: list[dict], meta: dict) -> str:
    L = c.L
    m = meta["method"]
    by_dex = {p["dex"]: p for p in full}
    idx_by_dex = {p["dex"]: p for p in index}
    presets = [(L.mon(by_dex[d]), [round(by_dex[d]["r"]["pillars"][k] * 100) for k in PILLAR_KEYS])
               for d in meta["presets"]]
    walkers = [{"name": L.mon(by_dex[d]), "dex": d, "w": by_dex[d]["sprite"]["w"], "h": by_dex[d]["sprite"]["h"],
                "index": idx_by_dex[d], "r": by_dex[d]["r"], "assets": c.assets} for d in meta["presets"]]
    reps = [(L.mon(p), p) for p in (min(index, key=lambda p: abs(p["r"][0] - n)) for n in REPEAT_RANKS)]
    pieces = "".join(f'<li><strong>{esc(L.t("w_" + x["key"]))}.</strong> {esc(L.t("w_" + x["key"] + "_t"))}</li>'
                     for x in m["pieces"])
    limits = "".join(f'<li>{esc(L.t(f"met_lim_{i}"))}</li>' for i in range(1, 6))
    cuts_text = ", ".join(L.t("met_cut", t=t["tier"], a=t["from"], b=t["to"]) for t in meta["tierCuts"])
    glossary = gloss(L, ("gl_pct", "gl_med", "gl_geo", "gl_hit", "gl_band", "gl_firm"))
    arena_name = L.mon(by_dex[ARENA_DEX])
    arena_src = f"{c.assets}sprites/{ARENA_DEX}.png"
    content = f"""
<h1>{esc(L.t("met_h1"))}</h1>
<p class="lead">{esc(L.t("met_lead", game=legal.GAME_NAME, total=charts.TOTAL))}</p>
{charts.pipeline(L)}

<h2>{esc(L.t("met_walk_h"))}</h2>
<p>{esc(L.t("met_walk_p"))}</p>
{charts.walk(L, walkers, meta["tierCuts"], m["pieces"])}

<h2>{esc(L.t("met_1_h"))}</h2>
<ul class="plain">{pieces}</ul>
{charts.weights(L, m["pieces"])}
{charts.weights_pillars(L, m["pillars"])}

<h3>{esc(L.t("met_sim_h"))}</h3>
<p>{esc(L.t("met_sim_p", total=charts.TOTAL, s=f'{meta["simMedianSeconds"]:.0f}'))}</p>
{charts.arena(L, arena_name, arena_src)}

<h2>{esc(L.t("met_2_h"))}</h2>
<p>{esc(L.t("met_2_p"))}</p>
{charts.geo_demo(L, m["pillars"], presets)}

<h2>{esc(L.t("met_3_h"))}</h2>
<p>{esc(L.t("met_3_p"))}</p>
{charts.repeats_demo(L, reps)}
{charts.ribbon(L, index)}
{charts.stability(L, meta["stability"], meta["firmShare"])}
<p>{esc(L.t("met_3b_p", share=meta["firmShare"]))}</p>

<h2>{esc(L.t("met_4_h"))}</h2>
<p>{esc(L.t("met_4_p", cuts=cuts_text))}</p>
{charts.tier_strip(L, meta["tierCuts"])}
{charts.gate(L, m["gates"], meta["cappedCount"])}

<h2>{esc(L.t("met_5_h"))}</h2>
<p>{esc(L.t("met_5_p"))}</p>
{charts.agreement(L, meta["agreement"])}

<h2>{esc(L.t("met_limits_h"))}</h2>
<ul class="plain">{limits}</ul>

<h2>{esc(L.t("met_gloss_h"))}</h2>
<dl class="gloss">{glossary}</dl>
<p class="muted">{L.t("met_foot_html", version=esc(L.t("version_name")), game=esc(legal.GAME_NAME),
                        commit=esc(meta["gameCommit"]), date=esc(meta["generatedAt"][:10]))}</p>
"""
    return page(c, "metodo", L.t("met_title", site=legal.SITE_NAME), L.t("met_desc", site=legal.SITE_NAME),
                content, meta)


def render_acerca(c: Ctx, meta: dict) -> str:
    L = c.L
    lic = meta["spriteLicense"]
    creds = []
    for cr in meta["credits"]:
        name = (f'<a href="{esc(cr["url"])}" rel="noopener nofollow">{esc(cr["name"])}</a>' if cr["url"]
                else esc(cr["name"]))
        creds.append(f'<li>{name} <span class="muted">({len(cr["dex"])})</span></li>')
    legal_html = "".join(f'<h3 id="{s["id"]}">{esc(s["title"])}</h3>{s["html"]}' for s in legal.legal_sections(L))
    ui = next(x for x in json.loads((SITE / "img" / "CREDITS.json").read_text(encoding="utf8")) if x["set"] == "ui")
    icons = L.t("about_icons_html", author=esc(ui["author"]), url=esc(ui["sourceUrl"]), title=esc(ui["title"]),
                lic=esc(ui["license"]), lic_url=esc(ui["licenseUrl"]))
    content = f"""
<h1>{esc(L.t("about_h1"))}</h1>
<div class="note"><p><strong>{esc(L.t("disclaimer", game=legal.GAME_NAME))}</strong></p></div>
<ul class="toc"><li><a href="{c.home}metodo.html">{esc(L.t("nav_metodo"))}</a></li>
<li><a href="#legal">{esc(L.t("about_toc_legal"))}</a></li><li><a href="#creditos">{esc(L.t("about_toc_credits"))}</a></li></ul>

<p>{L.t("about_p_html", version=esc(L.t("version_name")), game=esc(legal.GAME_NAME), commit=esc(meta["gameCommit"]),
        repo=esc(legal.GAME_REPO_URL), url=esc(legal.GAME_URL), date=esc(meta["generatedAt"][:10]),
        method=f"{c.home}metodo.html")}</p>

<h2 id="legal">{esc(L.t("about_toc_legal"))}</h2>
{legal_html}

<h2 id="creditos">{esc(L.t("about_credits_h"))}</h2>
<h3>{esc(L.t("about_sprites_h"))}</h3>
<p>{L.t("about_sprites_html", url=esc(lic["sourceUrl"]), source=esc(lic["source"]), lic_url=esc(lic["url"]),
        lic=esc(lic["name"]))}</p>
<ul class="credits-list">{"".join(creds)}</ul>
<h3>{esc(L.t("about_icons_h"))}</h3>
<p>{icons}</p>
<p>{L.t("about_font_html", game=esc(legal.GAME_NAME), root=c.assets)}</p>
"""
    return page(c, "acerca", L.t("about_title", site=legal.SITE_NAME), L.t("about_desc", site=legal.SITE_NAME),
                content, meta)


def render_404(meta: dict) -> str:
    L = ES
    c = Ctx(L, "404.html", "/", "/", None)
    content = f'<h1>{esc(L.t("nf_h1"))}</h1><p class="lead">{L.t("nf_p_html")}</p>'
    return page(c, "404", L.t("nf_title", site=legal.SITE_NAME), L.t("nf_title", site=legal.SITE_NAME), content, meta)


def main() -> int:
    try:
        meta = load("meta.json")
        index = load("pokemon-index.json")
        full = load("pokemon.json")
        moves = load("moves.json")
        gachas = load("gachas.json")
    except RenderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    # Una ficha solo se escribe con sprite y atribución: el build falla si falta una.
    for p in full:
        s = p["sprite"]
        if not s or not s["artists"] or not s["license"]:
            print(f"ERROR: {p['name']} ({p['dex']}) sin sprite o sin atribución", file=sys.stderr)
            return 1
    mv = Moves(moves)
    ordered = sorted(full, key=lambda p: p["dex"])
    for L in LANGS:
        def put(rel: str, build) -> None:
            write(f"{L.prefix}{rel}", build(Ctx.of(L, rel)))

        put("index.html", lambda c: render_index(c, index, meta))
        put("ataques.html", lambda c: render_ataques(c, moves, meta))
        put("gachas.html", lambda c: render_gachas(c, gachas, meta))
        put("coleccion.html", lambda c: render_coleccion(c, meta))
        put("metodo.html", lambda c: render_metodo(c, index, full, meta))
        put("acerca.html", lambda c: render_acerca(c, meta))
        for i, p in enumerate(ordered):
            prev_p, next_p = ordered[i - 1] if i else None, ordered[i + 1] if i + 1 < len(ordered) else None
            put(f"pokemon/{p['dex']}.html", lambda c: render_ficha(c, p, prev_p, next_p, meta, mv))
    write("404.html", render_404(meta))
    print(f"render: 2 idiomas x (6 páginas + {len(ordered)} fichas) + 404 → {SITE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
