"""Genera site/ entero (español en la raíz, inglés en /en/) a partir de build/out/, que escribe build/catalog.py, y de
src/. site/ queda en unos 25 archivos: seis páginas por idioma, la plantilla única de ficha de cada idioma
(pokemon/index.html, que dibuja src/ficha.js con ?id=), la página 404, el CSS y el JS empaquetados, la letra y tres JSON.
Los sprites no van en site/: se piden a legal.SPRITE_BASE (WebP, ver legal.py).

    python3 build/catalog.py && python3 build/render.py
"""
from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import charts  # noqa: E402
import legal  # noqa: E402
import objetos  # noqa: E402
import pack  # noqa: E402
import regions  # noqa: E402
import typedata  # noqa: E402
from i18n import ES, LANGS, Lang  # noqa: E402

SITE = ROOT / "site"
OUT = ROOT / "build" / "out"
SRC = ROOT / "src"
TEMPLATES = Path(__file__).resolve().parent / "templates"
SPRITES = legal.SPRITE_BASE
EXT = legal.SPRITE_EXT
SCALE_LIST = 2
TIERS = ["S", "A", "B", "C", "D"]
CATEGORIES = [("melee", "cuerpo a cuerpo"), ("ranged", "distancia"), ("stat", "estadística")]  # (id, valor del CSV)
NAV = [("index", "index.html", "nav_tiers"), ("metodo", "metodo.html", "nav_metodo"),
       ("ataques", "ataques.html", "nav_ataques"), ("objetos", "objetos.html", "nav_objetos"),
       ("gachas", "gachas.html", "nav_gachas"),
       ("coleccion", "coleccion.html", "nav_coleccion"), ("acerca", "acerca.html", "nav_acerca")]
REPEAT_RANKS = (2, 40, 150, 350, 650)  # puestos de los Pokémon que salen en la ilustración de repeticiones
PILLAR_KEYS = ("stats", "moves", "typedef", "size")
ARENA_DEX = 25
BANNER_NAMES = {1: "Kanto", 2: "Johto", 3: "Hoenn", 4: "Sinnoh", 5: "Teselia", 6: "Kalos", 7: "Alola", 8: "Galar", 9: "Paldea"}


class RenderError(RuntimeError):
    pass


@dataclass(frozen=True)
class Ctx:
    """Idioma y posición de una página: de dónde cuelgan los recursos y los enlaces."""
    L: Lang
    rel: str            # ruta de la página dentro de su idioma, por ejemplo "index.html" o "pokemon/index.html"
    assets: str         # prefijo hasta la raíz del sitio, donde viven style.css, app.js y data/
    home: str           # prefijo hasta la raíz de este idioma, donde viven los enlaces del menú
    other: str | None   # enlace a la misma página en el otro idioma, o None si no existe

    @staticmethod
    def of(L: Lang, rel: str) -> "Ctx":
        up = "../" * rel.count("/")
        assets = up + ("../" if L.en else "")
        twin = rel.removesuffix("index.html") if rel.startswith("pokemon/") else rel
        return Ctx(L, rel, assets, up, f"{assets}{'' if L.en else 'en/'}{twin}")


BASE = Template((TEMPLATES / "base.html").read_text(encoding="utf8"))


def esc(x) -> str:
    return escape(str(x), quote=True)


def load(name: str):
    path = OUT / name
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


LOAD_EAGER = 'fetchpriority="high"'
LOAD_LAZY = 'loading="lazy" decoding="async"'


def mon_card(c: Ctx, p: dict, eager: bool = False) -> str:
    L = c.L
    rank, tier = p["r"][:2]
    w, h = p["w"] * SCALE_LIST, p["h"] * SCALE_LIST
    name = L.mon(p)
    title = L.t("card_title", name=name, dex=p["dex"], rank=rank, tier=tier)
    return (f'<a class="mon" href="{c.home}pokemon/?id={p["dex"]}" data-dex="{p["dex"]}" '
            f'title="{esc(title)}">'
            f'<span class="sp"><img class="px" src="{SPRITES}{p["dex"]}{EXT}" width="{w}" height="{h}" alt="" '
            f'{LOAD_EAGER if eager else LOAD_LAZY}></span>'
            f'<span class="nm">{esc(name)}</span><span class="rk">{rank}</span></a>')


ASSET_V = ""  # huella de style.css y app.js; la fija main() tras empaquetarlos


def page(c: Ctx, page_id: str, title: str, description: str, content: str, meta: dict) -> str:
    L = c.L
    current = ' aria-current="page"'
    nav = "\n".join(
        f'      <a href="{c.home}{href}"{current if pid == page_id else ""}>{esc(L.t(key))}</a>' for pid, href, key in NAV)
    footer_nav = "\n".join(f'      <a href="{c.home}{href}">{esc(L.t(key))}</a>' for _, href, key in NAV)
    lic = meta["spriteLicense"]
    sprites_line = L.t("sprites_line_html", url=esc(lic["sourceUrl"]), source=esc(lic["source"]),
                       lic_url=esc(lic["url"]), lic=esc(lic["name"]), about=f"{c.home}acerca.html")
    build_info = f'{legal.GAME_NAME} {meta["gameCommit"]}, ranking {meta["version"]}, generated {meta["generatedAt"][:10]}'
    switch, alternates = "", ""
    if c.other:
        other = "es" if L.en else "en"
        links = "".join(
            f'<a href="{c.other if code != L.code else "#"}" lang="{code}" hreflang="{code}"'
            f'{current if code == L.code else ""}>{code.upper()}</a>' for code in ("es", "en"))
        switch = f'<nav class="lang" aria-label="{esc(L.t("lang_label"))}">{links}</nav>'
        alternates = f'<link rel="alternate" hreflang="{other}" href="{c.other}">'
    return BASE.substitute(
        lang=L.code, assets=c.assets, home=c.home, sprites=esc(SPRITES), sprites_alt=esc(legal.SPRITE_ALT), sprites_ext=EXT, asset_v=ASSET_V, page_id=page_id, title=esc(title),
        description=esc(description), alternates=alternates, skip=esc(L.t("skip")),
        nav_aria=esc(L.t("nav_main")), foot_aria=esc(L.t("nav_foot")), switch=switch, nav=nav, content=content,
        footer_nav=footer_nav, disclaimer=esc(L.t("disclaimer", game=legal.GAME_NAME)), sprites_line=sprites_line,
        build_info=esc(build_info.replace("--", "-")))


def write(rel: str, text: str) -> None:
    path = SITE / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8")


# ---------------------------------------------------------------- páginas
def render_index(c: Ctx, pokemon: list[dict], meta: dict) -> str:
    L = c.L
    sections = []
    for t in TIERS:
        mons = sorted((p for p in pokemon if p["r"][1] == t), key=lambda p: p["r"][0])
        cards = "".join(mon_card(c, p, eager=(t == TIERS[0] and i < 12)) for i, p in enumerate(mons))
        sections.append(
            f'<section class="tier tier-{t}" id="tier-{t}" aria-label="{esc(L.t("tier", t=t))}">'
            f'<header class="tier-head"><b>{t}</b>{icon("crown") if t == "S" else ""}<span class="n">{len(mons)}</span></header>'
            f'<div class="grid">{cards}</div></section>')
    content = f"""
<h1>{esc(L.t("index_h1", game=legal.GAME_NAME))}</h1>
<div class="controls">
  <div class="field"><label for="q">{esc(L.t("search_label"))}</label>
    <input id="q" type="search" placeholder="{esc(L.t("search_ph"))}" autocomplete="off" spellcheck="false"></div>
  <p id="count" aria-live="polite"></p>
</div>
<div id="tierlist">
{"".join(sections)}
</div>
<noscript><p class="muted">{esc(L.t("noscript"))}</p></noscript>
"""
    return page(c, "index", L.t("index_title", site=legal.SITE_NAME, game=legal.GAME_NAME),
                L.t("index_desc", n=meta["total"], game=legal.GAME_NAME), content, meta)


FICHA_KEYS = (
    "crumb_home", "legendary", "stars_alt", "sprite_alt", "ficha_title", "ficha_desc", "flag_status", "flag_melee",
    "flag_capped", "pager_aria", "dex_no", "tier", "f_missing", "t_band", "t_pillars", "t_methods", "t_sim",
    "band_rank", "band_range", "band_alt", "pill_stats", "pill_moves", "pill_typedef", "pill_size", "pillars_alt_item",
    "median", "m_sheet", "m_simStart", "m_simBest", "m_lateMax", "m_lateFresh", "methods_final", "methods_alt",
    "methods_alt_item", "sim_start", "sim_best", "sim_median", "sim_alt")


def render_ficha(c: Ctx, index: list[dict], meta: dict) -> str:
    """Plantilla única de ficha: la estructura y los textos salen de aquí y src/ficha.js pone los datos del ?id=."""
    L = c.L
    strings = {k: L.t_raw(k).replace("{site}", legal.SITE_NAME).replace("{game}", legal.GAME_NAME)
               .replace("{total}", str(charts.TOTAL)) for k in FICHA_KEYS}
    blob = json.dumps({"en": L.en, "s": strings}, ensure_ascii=False).replace("</", "<\\/")
    pills = "".join(f'<span data-t="{t}">{type_pill(L, t)}</span>' for t in typedata.TYPE_COLOR)
    badges = "".join(
        f'<span data-gen="{gen}">{regions.badge(L, SPRITES, gen, L.t("banner_of", name=L.banner(name)), {}, small=True)}</span>'
        for gen, name in BANNER_NAMES.items())
    content = f"""
<article id="ficha"><noscript><p>{esc(L.t("noscript_ficha"))}</p></noscript></article>
<template id="tpl-types">{pills}</template>
<template id="tpl-regions">{badges}</template>
<script type="application/json" id="i18n">{blob}</script>
"""
    return page(c, "ficha", legal.SITE_NAME,
                L.t("index_desc", n=meta["total"], game=legal.GAME_NAME), content, meta)


def move_card(L: Lang, m: dict) -> str:
    name = m["en"]["name"] if L.en else m["name"]
    bars = charts.buff_bars(L, m["score"], m["buff"]) if "buff" in m else charts.move_bars(L, m["score"])
    return (f'<li class="mv"><div class="mv-head"><h4>{esc(name)}</h4>{type_pill(L, m["type"])}</div>'
            f'<div class="mv-body">{bars}</div></li>')


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
            inner.append(f'<div class="mv-tier anim"><h3>{tier_badge(L, t)} <small>{len(ms)}</small></h3>'
                         f'<ul class="mv-list">{items}</ul></div>')
        icon_name = {"melee": "sword", "ranged": "bow", "stat": "sparkle"}[cat_id]
        blocks.append(f'<section id="{cat_id}"><h2>{icon(icon_name)}{esc(L.t("cat_" + cat_id))}</h2>{"".join(inner)}</section>')
        toc.append(f'<li><a href="#{cat_id}">{icon(icon_name)}{esc(L.t("cat_" + cat_id))}</a></li>')
    content = f"""
<h1>{esc(L.t("ataques_h1"))}</h1>
<p class="lede">{esc(L.t("ataques_lede"))}</p>
<ul class="toc">{"".join(toc)}</ul>
{charts.move_scale(L)}
{"".join(blocks)}
"""
    return page(c, "ataques", L.t("ataques_title", site=legal.SITE_NAME),
                L.t("ataques_desc", n=len(moves), game=legal.GAME_NAME), content, meta)


def render_objetos(c: Ctx, meta: dict) -> str:
    L = c.L
    content = objetos.items_content(L, L.t("obj_h1"), L.t("obj_lede"), L.t("obj_phases_h"), L.t("obj_table_h"))
    return page(c, "objetos", L.t("obj_title", site=legal.SITE_NAME),
                L.t("obj_desc", game=legal.GAME_NAME), content, meta)


GACHA_STARS = (5, 4, 4, 3, 3, 3, 2, 2, 1)  # estrellas de cada banner, del mejor al peor


def gacha_card(c: Ctx, i: int, g: dict, last: int, by_banner: dict[int, list[dict]], by_dex: dict[int, dict]) -> str:
    L = c.L
    name = L.banner(g["name"])
    best = sorted(by_banner[g["gen"]], key=lambda p: p["r"][0])[:3]
    pulls = "".join(
        f'<a class="gc-mon" href="{c.home}pokemon/?id={p["dex"]}" title="{esc(L.mon(p))}">'
        f'<img class="px" src="{SPRITES}{p["dex"]}{EXT}" width="{p["w"] * k}" height="{p["h"] * k}" '
        f'alt="{esc(L.mon(p))}" loading="lazy" decoding="async"></a>'
        for p in best for k in [max(1, min(4, 56 // max(p["w"], p["h"])))])
    stars_n = GACHA_STARS[i]
    verdict = ""
    if i == 0:
        verdict = f'<b class="gc-tag go" role="img" aria-label="{esc(L.t("g_best"))}">{icon("crown")}</b>'
    elif i == last:
        verdict = f'<b class="gc-tag stop">{esc(L.t("g_worst"))}</b>'
    cls = "gc best" if i == 0 else "gc worst" if i == last else "gc"
    return (f'<li class="{cls}" style="--i:{i}">{regions.badge(L, SPRITES, g["gen"], name, by_dex)}'
            f'<div class="gc-main"><span class="stars big" role="img" aria-label="{esc(L.t("stars_alt", n=stars_n))}">'
            f'{"★" * stars_n}{"☆" * (5 - stars_n)}</span>{verdict}'
            f'<span class="gc-one">{esc(L.t("g_one_in", n=round(100 / g["sPlusARate"])))}</span></div>'
            f'<div class="gc-pulls" role="group" aria-label="{esc(L.t("g_pulls", name=name))}">{pulls}</div></li>')


def render_gachas(c: Ctx, gachas: list[dict], pokemon: list[dict], meta: dict) -> str:
    L = c.L
    ordered = sorted(gachas, key=lambda g: -g["sPlusARate"])
    by_banner: dict[int, list[dict]] = {}
    for p in pokemon:
        by_banner.setdefault(p["bannerId"], []).append(p)
    by_dex = {p["dex"]: p for p in pokemon}
    cards = "".join(gacha_card(c, i, g, len(ordered) - 1, by_banner, by_dex) for i, g in enumerate(ordered))
    content = f"""
<h1>{esc(L.t("gachas_h1"))}</h1>
<ol class="gacha">{cards}</ol>
"""
    return page(c, "gachas", L.t("gachas_title", site=legal.SITE_NAME), L.t("gachas_desc", game=legal.GAME_NAME),
                content, meta)


def render_coleccion(c: Ctx, meta: dict) -> str:
    L = c.L
    snippet = (ROOT / "console" / ("coleccion.en.js" if L.en else "coleccion.js")).read_text(encoding="utf8")
    content = f"""
<h1>{esc(L.t("col_h1"))}</h1>
<ol class="steps">
  <li>{L.t("col_step1_html")}</li>
  <li>{L.t("col_step2_html")}
    <pre class="snippet" id="snippet" tabindex="0">{esc(snippet)}</pre>
    <button class="btn ghost" type="button" id="copy-snippet">{esc(L.t("col_copy"))}</button>
    <span class="muted small" id="copy-msg" aria-live="polite"></span></li>
  <li>{L.t("col_step3_html")}</li>
</ol>
<div class="field"><label for="paste">{esc(L.t("col_json"))}</label>
  <textarea id="paste" spellcheck="false" placeholder="{{ … }}"></textarea></div>
<div class="controls">
  <button class="btn" type="button" id="import">{esc(L.t("col_view"))}</button>
  <div class="field"><label for="file">{esc(L.t("col_file"))}</label><input id="file" type="file" accept="application/json,.json"></div>
</div>
<div id="result" aria-live="polite"></div>
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
                "index": idx_by_dex[d], "r": by_dex[d]["r"], "sprites": SPRITES, "ext": EXT} for d in meta["presets"]]
    reps = [(L.mon(p), p) for p in (min(index, key=lambda p: abs(p["r"][0] - n)) for n in REPEAT_RANKS)]
    limits = "".join(f'<li>{esc(L.t(f"met_lim_{i}"))}</li>' for i in range(1, 5))
    arena_src = f"{SPRITES}{ARENA_DEX}{EXT}"
    content = f"""
<h1>{esc(L.t("met_h1"))}</h1>
<p class="lede">{esc(L.t("met_lede"))}</p>
{charts.pipeline(L)}
{charts.method_steps(L, m["pieces"], meta["tierCuts"], m["gates"])}
{charts.walk(L, walkers, meta["tierCuts"], m["pieces"])}
{charts.weights(L, m["pieces"])}
{charts.weights_pillars(L, m["pillars"])}
{charts.arena(L, arena_src)}
{charts.geo_demo(L, m["pillars"], presets)}
{charts.repeats_demo(L, reps)}
{charts.ribbon(L, index)}
{charts.stability(L, meta["stability"])}
{charts.tier_strip(L, meta["tierCuts"])}
{charts.gate(L, m["gates"])}
{charts.agreement(L, meta["agreement"])}
<h2>{esc(L.t("met_limits_h"))}</h2>
<ul class="plain limits">{limits}</ul>
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
        creds.append(f"<li>{name}</li>")
    legal_html = "".join(f'<h2 id="{s["id"]}">{esc(s["title"])}</h2>{s["html"]}' for s in legal.legal_sections(L))
    ui = next(x for x in json.loads((SRC / "img" / "CREDITS.json").read_text(encoding="utf8")) if x["set"] == "ui")
    icons = L.t("about_icons_html", author=esc(ui["author"]), url=esc(ui["sourceUrl"]), title=esc(ui["title"]),
                lic=esc(ui["license"]), lic_url=esc(ui["licenseUrl"]))
    content = f"""
<h1>{esc(L.t("about_h1"))}</h1>
{legal_html}
<h2 id="creditos">{esc(L.t("about_credits_h"))}</h2>
<h3>{esc(L.t("about_sprites_h"))}</h3>
<p>{L.t("about_sprites_html", url=esc(lic["sourceUrl"]), source=esc(lic["source"]), lic_url=esc(lic["url"]),
        lic=esc(lic["name"]))}</p>
<ul class="credits-list">{"".join(creds)}</ul>
<h3>{esc(L.t("about_icons_h"))}</h3>
<p>{icons}</p>
<p>{L.t("about_font_html", root=c.assets)}</p>
"""
    return page(c, "acerca", L.t("about_title", site=legal.SITE_NAME), L.t("about_desc", site=legal.SITE_NAME),
                content, meta)


def render_404(meta: dict) -> str:
    L = ES
    c = Ctx(L, "404.html", "/", "/", None)
    content = f'<h1>{esc(L.t("nf_h1"))}</h1><p>{L.t("nf_p_html")}</p>'
    return page(c, "404", L.t("nf_title", site=legal.SITE_NAME), L.t("nf_title", site=legal.SITE_NAME), content, meta)


def main() -> int:
    global ASSET_V
    try:
        meta = load("meta.json")
        index = load("public/pokemon-index.json")
        full = load("pokemon.json")
        moves = load("moves.json")
        gachas = load("gachas.json")
    except RenderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    # Un Pokémon solo se publica con sprite y atribución: el build falla si falta una.
    for p in full:
        s = p["sprite"]
        if not s or not s["artists"] or not s["license"]:
            print(f"ERROR: {p['name']} ({p['dex']}) sin sprite o sin atribución", file=sys.stderr)
            return 1
    if SITE.exists():
        for child in SITE.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    ASSET_V = pack.build(SRC, SITE, OUT / "public")
    for L in LANGS:
        def put(rel: str, build) -> None:
            write(f"{L.prefix}{rel}", build(Ctx.of(L, rel)))

        put("index.html", lambda c: render_index(c, index, meta))
        put("ataques.html", lambda c: render_ataques(c, moves, meta))
        put("objetos.html", lambda c: render_objetos(c, meta))
        put("gachas.html", lambda c: render_gachas(c, gachas, index, meta))
        put("coleccion.html", lambda c: render_coleccion(c, meta))
        put("metodo.html", lambda c: render_metodo(c, index, full, meta))
        put("acerca.html", lambda c: render_acerca(c, meta))
        put("pokemon/index.html", lambda c: render_ficha(c, index, meta))
    write("404.html", render_404(meta))
    files = [f for f in SITE.rglob("*") if f.is_file()]
    size = sum(f.stat().st_size for f in files)
    print(f"render: {len(files)} archivos, {size / 1e6:.2f} MB → {SITE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
