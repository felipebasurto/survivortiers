"""Genera site/ entero (español en la raíz, inglés en /en/) a partir de build/out/, que escribe build/catalog.py, y de
src/. Cada Pokémon tiene una página HTML estática en /pokemon/<n>-<nombre>/ y /en/pokemon/<n>-<nombre>/.
pokemon/index.html sigue siendo la plantilla de ?id=, que redirige a esa URL. Los sprites no van en site/.

    python3 build/catalog.py && python3 build/render.py
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import agents  # noqa: E402
import balls  # noqa: E402
import finder  # noqa: E402
import game_moves  # noqa: E402
import gamestats  # noqa: E402
import landing  # noqa: E402
import legal  # noqa: E402
import novedades  # noqa: E402
import objetos  # noqa: E402
import pasivas  # noqa: E402
import tipos  # noqa: E402
import pack  # noqa: E402
import planner  # noqa: E402
import regions  # noqa: E402
import seo  # noqa: E402
import share_image  # noqa: E402
import static_ficha  # noqa: E402
import theme  # noqa: E402
import toolpages  # noqa: E402
import typedata  # noqa: E402
from i18n import EN, ES, LANGS, STR, TYPE_NAMES, Lang  # noqa: E402
from slugs import species_path  # noqa: E402

SITE = ROOT / "site"
OUT = ROOT / "build" / "out"
SRC = ROOT / "src"
TEMPLATES = Path(__file__).resolve().parent / "templates"
SPRITES = legal.SPRITE_BASE
EXT = legal.SPRITE_EXT
SCALE_LIST = 2
TIERS = ["S", "A", "B", "C", "D"]
CATEGORIES = [("melee", "cuerpo a cuerpo"), ("ranged", "distancia"), ("stat", "estadística")]  # (id, valor del CSV)
NAV_TOP = [("index", "index.html", "nav_tiers"), ("ataques", "ataques.html", "nav_ataques"),
           ("objetos", "objetos.html", "nav_objetos"), ("gachas", "gachas.html", "nav_gachas")]
NAV_GROUPS = [
    ("nav_more", [("novedades", "novedades.html", "nav_novedades"), ("planificador", "@planner", "nav_planificador"),
                  ("pasivas", "pasivas.html", "nav_pasivas"), ("tipos", "tipos.html", "nav_tipos"),
                  ("metodo", "metodo.html", "nav_metodo"), ("acerca", "acerca.html", "nav_acerca")]),
]
NAV = NAV_TOP + [item for _, items in NAV_GROUPS for item in items]
SORT_KEYS = ("rank", "name", "dex", "s", "pa", "sa", "hp", "spd", "df", "sd", "rad", "rar")  # orden de la lista
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
    def of(L: Lang, rel: str, twin: str | None = None) -> "Ctx":
        up = "../" * rel.count("/")
        assets = up + ("../" if L.en else "")
        if twin is None:
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


def mon_href(c: Ctx, p: dict) -> str:
    return f"{c.home}pokemon/{species_path(p['dex'], p['nameEn'])}/"


def mon_card(c: Ctx, p: dict, eager: bool = False) -> str:
    L = c.L
    rank, tier = p["r"][:2]
    w, h = p["w"] * SCALE_LIST, p["h"] * SCALE_LIST
    name = L.mon(p)
    title = L.t("card_title", name=name, dex=p["dex"], rank=rank, tier=tier)
    return (f'<a class="mon" href="{mon_href(c, p)}" data-dex="{p["dex"]}" '
            f'title="{esc(title)}">'
            f'<span class="sp"><img class="px" src="{SPRITES}{p["dex"]}{EXT}" width="{w}" height="{h}" alt="" '
            f'{LOAD_EAGER if eager else LOAD_LAZY}></span>'
            f'<span class="nm">{esc(name)}</span><span class="rk">{rank}</span></a>')


ASSET_V = ""  # huella de style.css y app.js; la fija main() tras empaquetarlos


def page_url(c: Ctx) -> str:
    """URL canónica de la página: absoluta, en su idioma y sin .html."""
    path = c.rel.removesuffix("index.html").removesuffix(".html")
    return f"{legal.SITE_URL}/{'en/' if c.L.en else ''}{path}"


def hreflang_links(c: Ctx) -> str:
    """Pareja es/en con URLs absolutas y x-default (el español). Sale de la ruta relativa del gemelo (c.other)."""
    own_file = f"{legal.SITE_URL}/{'en/' if c.L.en else ''}{c.rel}"
    twin = urljoin(own_file, c.other)
    urls = {c.L.code: page_url(c), ("es" if c.L.en else "en"): twin.removesuffix("index.html").removesuffix(".html")}
    return "\n".join((
        f'<link rel="alternate" hreflang="es" href="{esc(urls["es"])}">',
        f'<link rel="alternate" hreflang="en" href="{esc(urls["en"])}">',
        f'<link rel="alternate" hreflang="x-default" href="{esc(urls["es"])}">'))


def social_head(c: Ctx, title: str, description: str, og_type: str = "website", canonical: str | None = None) -> str:
    """Etiquetas para compartir: canónica, Open Graph (Reddit, Discord, WhatsApp...) y Twitter/X (tarjeta grande con la
    imagen de build/share_image.py). La URL es la de la página en el idioma de la página, sin .html."""
    L = c.L
    url = canonical or page_url(c)
    image = f"{legal.SITE_URL}/og.png"
    alt = L.t("og_alt")
    tags = [
        f'<link rel="canonical" href="{esc(url)}">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:site_name" content="{esc(legal.SITE_NAME)}">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(description)}">',
        f'<meta property="og:url" content="{esc(url)}">',
        f'<meta property="og:image" content="{esc(image)}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{esc(alt)}">',
        f'<meta property="og:locale" content="{"en_US" if L.en else "es_ES"}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:site" content="{esc(legal.X_HANDLE)}">',
        f'<meta name="twitter:creator" content="{esc(legal.X_HANDLE)}">',
        f'<meta name="twitter:title" content="{esc(title)}">',
        f'<meta name="twitter:description" content="{esc(description)}">',
        f'<meta name="twitter:image" content="{esc(image)}">',
        f'<meta name="twitter:image:alt" content="{esc(alt)}">',
    ]
    return "\n".join(tags)


def theme_button(L: Lang) -> str:
    """Botón de tema de la cabecera. Empieza oculto: sin JavaScript no hay nada que cambiar. app.js lo muestra y pone
    su etiqueta según el tema activo (data-to-dark / data-to-light)."""
    return (f'<button class="theme-btn" type="button" id="theme" hidden aria-label="{esc(L.t("theme_btn"))}" '
            f'title="{esc(L.t("theme_btn"))}" data-to-dark="{esc(L.t("theme_to_dark"))}" '
            f'data-to-light="{esc(L.t("theme_to_light"))}">'
            f'<i class="ico ico-sun" aria-hidden="true"></i><i class="ico ico-moon" aria-hidden="true"></i></button>')


def _nav_link(c: Ctx, page_id: str, pid: str, href: str, key: str) -> str:
    current = ' aria-current="page"' if pid == page_id else ""
    return f'<a href="{c.home}{toolpages.target(c.L, href)}"{current}>{esc(c.L.t(key))}</a>'


def _nav_html(c: Ctx, page_id: str) -> str:
    """Menú principal: Tiers y Novedades sueltos, y dos grupos desplegables (Herramientas y Guía)."""
    parts = [f'      {_nav_link(c, page_id, pid, href, key)}' for pid, href, key in NAV_TOP]
    for group, items in NAV_GROUPS:
        inside = any(pid == page_id for pid, _, _ in items)
        cls = "nav-group is-current" if inside else "nav-group"
        links = "\n".join(f'          {_nav_link(c, page_id, pid, href, key)}' for pid, href, key in items)
        parts.append(f'      <details class="{cls}"><summary>{esc(c.L.t(group))}</summary>\n'
                     f'        <div class="nav-menu">\n{links}\n        </div>\n      </details>')
    return "\n".join(parts)


def agents_line(c: Ctx) -> str:
    """Enlaces para agentes y datos. Sale en Info, no en el pie."""
    return (f'<p class="agents">{esc(c.L.t("agents_label"))} <a href="{c.assets}llms.txt">llms.txt</a> · '
            f'<a href="{c.assets}llms-full.txt">llms-full.txt</a> · '
            f'<a href="{c.assets}data/ranking.csv">ranking.csv</a></p>')


def page(c: Ctx, page_id: str, title: str, description: str, content: str, meta: dict, extra_head: str = "",
         head_links: str | None = None, og_type: str = "website", canonical: str | None = None) -> str:
    L = c.L
    follow = (f'<a class="follow" href="{legal.X_URL}" target="_blank" rel="noopener" '
              f'aria-label="{esc(L.t("follow_label", handle=legal.X_HANDLE))}">{esc(legal.X_HANDLE)}</a>')
    social = "" if page_id == "404" else social_head(c, title, description, og_type, canonical)
    analytics = (f"<script defer src='https://static.cloudflareinsights.com/beacon.min.js' "
                 f"data-cf-beacon='{{\"token\": \"{legal.WEB_ANALYTICS_TOKEN}\"}}'></script>")
    current = ' aria-current="page"'
    nav = _nav_html(c, page_id)
    build_info = f'{legal.GAME_NAME} {meta["gameCommit"]}, ranking {meta["version"]}, generated {meta["generatedAt"][:10]}'
    switch, alternates = "", ""
    if c.other:
        links = "".join(
            f'<a href="{c.other if code != L.code else "#"}" lang="{code}" hreflang="{code}"'
            f'{current if code == L.code else ""}>{code.upper()}</a>' for code in ("es", "en"))
        switch = f'<nav class="lang" aria-label="{esc(L.t("lang_label"))}">{links}</nav>'
        alternates = head_links if head_links is not None else hreflang_links(c)
    return BASE.substitute(
        lang=L.code, assets=c.assets, home=c.home, sprites=esc(SPRITES), sprites_alt=esc(legal.SPRITE_ALT), sprites_ext=EXT, asset_v=ASSET_V, page_id=page_id, title=esc(title),
        description=esc(description), alternates=alternates, skip=esc(L.t("skip")),
        nav_aria=esc(L.t("nav_main")), switch=switch, theme=theme_button(L), nav=nav,
        content=content, build_info=esc(build_info.replace("--", "-")),
        extra_head=extra_head, social=social, follow=follow, analytics=analytics, theme_init=theme.script_tag())


def write(rel: str, text: str) -> None:
    path = SITE / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8")


# ---------------------------------------------------------------- páginas
def render_index(c: Ctx, pokemon: list[dict], meta: dict) -> str:
    """Tier list: buscador, orden y agrupación. Sin JavaScript queda la lista por tiers; app.js la vuelve a agrupar."""
    L = c.L
    sections = []
    for t in TIERS:
        mons = sorted((p for p in pokemon if p["r"][1] == t), key=lambda p: p["r"][0])
        cards = "".join(mon_card(c, p, eager=(t == TIERS[0] and i < 12)) for i, p in enumerate(mons))
        sections.append(
            f'<section class="tier tier-{t}" id="tier-{t}" aria-label="{esc(L.t("tier", t=t))}">'
            f'<header class="tier-head"><b>{t}</b>{icon("crown") if t == "S" else ""}<span class="n">{len(mons)}</span></header>'
            f'<div class="grid">{cards}</div></section>')
    options = "".join(f'<option value="{k}">{esc(L.t("sort_" + k))}</option>' for k in SORT_KEYS)
    # Nombres y colores para las cabeceras de los grupos (tipo, rareza), que app.js dibuja.
    names = TYPE_NAMES["en" if L.en else "es"]
    labels = {
        "type": {t: names[t] for t in typedata.TYPE_COLOR},
        "typeColor": dict(typedata.TYPE_COLOR),
        "typeText": {t: typedata.text_color(t) for t in typedata.TYPE_COLOR},
        "typeGlyph": {t: typedata.glyph_svg(t) for t in typedata.TYPE_COLOR},
        "rar": {str(r): L.t(f"rar_{r}") for r in range(1, 6)},
        "rarColor": {str(r): col for r, col in balls.RARITY_COLOR.items()},
        "region": {str(gen): L.banner(name) for gen, name in BANNER_NAMES.items()},
    }
    labels_json = json.dumps(labels, ensure_ascii=False).replace("</", "<\\/")
    groups = "".join(
        f'<button type="button" class="seg" data-group="{g}" aria-pressed="{"true" if g == "tier" else "false"}">'
        f'{esc(L.t("group_" + g))}</button>'
        for g in ("tier", "type", "rar", "region", "leg", "none"))
    side_icons = {"phys": "sword", "spec": "sparkle", "mix": "ball"}
    sides = "".join(
        f'<button type="button" class="seg" data-side="{k}" aria-pressed="{"true" if not k else "false"}">'
        + (f'<i class="ico ico-{side_icons[k]}" aria-hidden="true"></i>' if k else "")
        + f'{esc(L.t(key))}</button>'
        for k, key in (("", "side_all"), ("phys", "side_phys"), ("spec", "side_spec"), ("mix", "side_mix")))
    content = f"""

<h1>{esc(L.t("index_h1", game=legal.GAME_NAME))}</h1>
{improved_notice(c)}
<p class="fresh">{esc(legal.freshness_text(L, meta))}</p>
<div class="finder">
  <div class="search">
    <label class="sr" for="q">{esc(L.t("search_label"))}</label>
    <div class="search-field">
      <svg class="search-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><circle cx="7" cy="7" r="4.6" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10.6 10.6 14.5 14.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>
      <input id="q" type="search" placeholder="{esc(L.t("search_ph"))}" autocomplete="off" spellcheck="false">
      <button id="clear" class="clear" type="button" hidden aria-label="{esc(L.t("search_clear"))}">×</button>
    </div>
  </div>
  <details class="filters">
    <summary>{esc(L.t("filters_btn"))}</summary>
    <div class="frow">
      <span class="flabel" id="lbl-sort">{esc(L.t("sort_by"))}</span>
      <div class="sortline">
        <select id="sort" aria-labelledby="lbl-sort">{options}</select>
        <button id="dir" class="seg" type="button" data-asc="{esc(L.t("dir_asc"))}" data-desc="{esc(L.t("dir_desc"))}"><i class="ico ico-arrow" aria-hidden="true"></i><span id="dir-label">{esc(L.t("dir_asc"))}</span></button>
        <button id="random" class="seg" type="button"><i class="ico ico-dice" aria-hidden="true"></i>{esc(L.t("random_btn"))}</button>
      </div>
    </div>
    <div class="frow">
      <span class="flabel" id="lbl-side">{esc(L.t("side_filter"))}</span>
      <div class="side-filter" role="group" aria-labelledby="lbl-side">{sides}</div>
    </div>
    <div class="frow">
      <span class="flabel" id="lbl-group">{esc(L.t("group_by"))}</span>
      <div class="group-by" role="group" aria-labelledby="lbl-group">{groups}</div>
    </div>
  </details>
  <p id="count" aria-live="polite"></p>
  <p id="nomatch" class="nomatch" hidden>{esc(L.t("no_match"))}</p>
</div>
<div id="tierlist">
{"".join(sections)}
</div>
<script type="application/json" id="labels">{labels_json}</script>
<noscript><p class="muted">{esc(L.t("noscript"))}</p></noscript>
{landing.guides_nav(L, c.home)}
{balls.defs()}
"""
    title, desc = seo.home_texts(L, pokemon, meta)
    ld = seo.home_jsonld(L, pokemon, meta, page_url(c), title, desc)
    return page(c, "index", title, desc, content, meta, extra_head=ld + "\n" + agents.dataset_jsonld(L, meta))


def render_ficha(c: Ctx, index: list[dict], meta: dict) -> str:
    """Plantilla de /pokemon/?id=. El hosting no puede redirigir por la query: ficha.js manda a la página estática; sin JS
    queda el texto y la lista de las 966 fichas. Su canónica es la portada, para que ?id=N no compita con las fichas."""
    L = c.L
    slugs = {str(p["dex"]): species_path(p["dex"], p["nameEn"]) for p in index}
    blob = json.dumps(slugs, separators=(",", ":")).replace("</", "<\\/")
    items = "".join(
        f'<li><a href="{c.home}pokemon/{slugs[str(p["dex"])]}/">{esc(L.mon(p))}</a> '
        f'<small>{esc(L.t("tier", t=p["r"][1]))} · {esc(L.t("dex_no", dex=p["dex"]))}</small></li>'
        for p in sorted(index, key=lambda p: p["dex"]))
    content = f"""
<article id="ficha">
<h1>{esc(L.t("tpl_h1", game=legal.GAME_NAME))}</h1>
<p class="lede">{esc(L.t("tpl_lede", game=legal.GAME_NAME, n=meta["total"]))}</p>
<p><a href="{c.home}index.html">{esc(L.t("crumb_home"))}</a></p>
<ol class="slug-list">{items}</ol>
</article>
<script type="application/json" id="slugs">{blob}</script>
"""
    home = f"{legal.SITE_URL}/{'en/' if L.en else ''}"
    return page(c, "ficha", L.t("tpl_title", game=legal.GAME_NAME, site=legal.SITE_NAME),
                L.t("tpl_desc", game=legal.GAME_NAME, n=meta["total"]), content, meta, canonical=home)


def render_species(c: Ctx, entry: dict, moves: dict, prev: dict | None, nxt: dict | None, odds: tuple[float, int],
                   meta: dict) -> str:
    L = c.L
    title, desc = static_ficha.head_texts(L, entry, moves)
    html, ld = static_ficha.build(L, c.home, SPRITES, EXT, entry, moves, meta, entry["start"], prev, nxt, odds,
                                  guides=landing.guides_nav(L, c.home, types=entry["types"]), url=page_url(c),
                                  title=title, assets=c.assets)
    return page(c, "ficha", title, desc, html + balls.defs(), meta, extra_head=ld,
                head_links=static_ficha.alternates(species_path(entry["dex"], entry["nameEn"])), og_type="article")


# Cada tipo de movimiento del juego se dibuja con uno de estos patrones (la animación de la tarjeta).
LETTERS = "abcdefghijklmnopqrstuvwxyz"  # la rejilla de píxeles de moves.json usa letras para la paleta


def move_icon_svg(icon: dict, standalone: bool = False) -> str:
    """El icono del juego (ui/icons.js) como SVG: la misma rejilla de píxeles en Ataques y en la ficha. La ficha lo
    pide como archivo (img/moves/<id>.svg), así el navegador lo guarda una vez para las 966 fichas."""
    w, h = icon["size"]
    rects = []
    for y, row in enumerate(icon["rows"]):
        x = 0
        while x < w:
            ch, n = row[x], 1
            while x + n < w and row[x + n] == ch:
                n += 1
            if ch != ".":
                rects.append(f'<rect x="{x}" y="{y}" width="{n}" height="1" fill="{icon["pal"][LETTERS.index(ch)]}"/>')
            x += n
    if standalone:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
                f'shape-rendering="crispEdges">{"".join(rects)}</svg>\n')
    return (f'<svg class="mv-icon" viewBox="0 0 {w} {h}" width="{w * 3}" height="{h * 3}" aria-hidden="true" '
            f'focusable="false" shape-rendering="crispEdges">{"".join(rects)}</svg>')


def move_facts(L: Lang, m: dict) -> str:
    """Hechos del ataque en una frase cada uno, sacados de los datos (no de la descripción larga)."""
    facts = []
    if m.get("evolvesTo"):
        evo = m["en"]["evolvesTo"] if L.en else m["evolvesTo"]
        if m.get("needsCard"):
            card = m["en"]["needsCard"] if L.en else m["needsCard"]
            facts.append(L.t("mv_evolves_card", move=evo, card=card))
        else:
            facts.append(L.t("mv_evolves", move=evo))
    if m["kind"] == "dash":
        cd, cd_max = game_moves.dash_cooldowns(m["id"])
        facts.append(L.t("mv_dash_fact", cd=L.dec(cd, 2), cd_max=L.dec(cd_max, 2),
                         pct=L.pcts(round(100 * game_moves.DASH_INVULN / cd))))
    if "buff" in m:
        b, top = m["buff"], m["buff"]["max"]
        stat = L.t(gamestats.BOOST_LABEL[b["stat"]])
        facts.append(L.t("mv_buff", dur=L.dec(b["dur"], 0), cd=L.dec(b["cd"], 2)))
        facts.append(L.t("mv_stacks", amt=gamestats.boost_amount(L, b["amount"], b["stat"]), stat=stat, n=b["stacks"]))
        facts.append(L.t("mv_buff_max", ups=top["level"] - 1, amt=gamestats.boost_amount(L, top["amount"], b["stat"]),
                         n=top["stacks"], dur=L.dec(top["dur"], 1)))
    if not facts:
        return ""
    return '<ul class="mv-facts">' + "".join(f"<li>{esc(f)}</li>" for f in facts) + "</ul>"


def move_card(L: Lang, m: dict) -> str:
    name = m["en"]["name"] if L.en else m["name"]
    # Teledirigido y perforante se nombran aparte del proyectil normal: cambian cómo se usa el ataque.
    kind = L.t("mv_kind_" + game_moves.shape_key(m))
    meter = ""
    if "score" in m:
        bar = _rel_row(L.t("mv_value"), m["score"], f"{L.dec(m['score'], 2)}×", m["score"] >= 1)
        meter = f'<div class="mv-meter"><div class="mb">{bar}</div></div>'
    note = m.get("note")
    note_html = f'<p class="mv-desc">{esc(note["en"] if L.en else note["es"])}</p>' if note else ""
    types = TYPE_NAMES["en" if L.en else "es"]
    search = " ".join([m["name"], m["en"]["name"] or "", types[m["type"]], kind]).lower()
    # El cuerpo a cuerpo no repite su forma: el rango ya lo dice.
    shape_html = "" if m["kind"] == "melee" else f'<span class="mv-kind">{esc(kind)}</span>'
    return (f'<li class="mv-card" data-q="{esc(search)}">'
            f'<div class="mv-top">{move_icon_svg(m["icon"])}<div class="mv-title"><h4>{esc(name)}</h4>'
            f'<div class="mv-tags">{type_pill(L, m["type"])}{"" if m["kind"] == "buff" else static_ficha.range_html(L, m)}'
            f'{static_ficha.damage_badge(L, m["damage"])}{shape_html}'
            f'</div></div></div>{note_html}'
            f'{meter}{move_facts(L, m)}</li>')


def damage_legend(L: Lang) -> str:
    items = "".join(f'<li>{static_ficha.damage_badge(L, cls)}<span>{esc(L.t("dmg_tip_" + cls))}</span></li>'
                    for cls in game_moves.DAMAGE_CLASSES)
    return f'<ul class="cat-legend" aria-label="{esc(L.t("mv_damage_h"))}">{items}</ul>'


def range_legend(L: Lang) -> str:
    items = "".join(f'<li>{static_ficha.range_html(L, {"kind": k})}<span>{esc(L.t("rng_tip_" + c))}</span></li>'
                    for k, c in (("melee", "melee"), ("ranged", "ranged")))
    return f'<ul class="cat-legend" aria-label="{esc(L.t("mv_range_h"))}">{items}</ul>'


REL_MAX = 2.0  # fin de la escala de las barras de ataques, en múltiplos de un ataque normal de su clase (el más alto es 1,69×)
GROUP_TOP = 5  # grupos por clase y build en la página de ataques


def _rel_row(label: str, rel: float, value: str, good: bool) -> str:
    x = min(rel, REL_MAX) / REL_MAX * 100
    return (f'<div class="mb-row"><span class="mb-name">{esc(label)}</span>'
            f'<span class="mb-track" aria-hidden="true"><i class="mb-med" style="left:{100 / REL_MAX:.1f}%"></i>'
            f'<i class="mb-fill{" hot" if good else ""}" style="width:{x:.1f}%"></i></span>'
            f'<em class="mb-val">{esc(value)}</em></div>')


def move_scale(L: Lang) -> str:
    """Leyenda de las barras: rojo por encima de lo normal, gris por debajo y la raya vertical es lo normal (×1)."""
    return (f'<div class="mv-key" aria-hidden="true"><span><i class="k-bar hot"></i>{esc(L.t("mv_better"))}</span>'
            f'<span><i class="k-bar"></i>{esc(L.t("mv_worse"))}</span>'
            f'<span><i class="k-tick"></i>{esc(L.t("mv_typical"))}</span></div>')


def best_groups(L: Lang, moves_by: dict[str, dict]) -> str:
    """Los mejores grupos de la fase 2 (data/bond_tiers.csv, ronda final) por clase de atacante y build."""
    with (ROOT / "data" / "bond_tiers.csv").open(encoding="utf8") as f:
        rows = list(csv.DictReader(line for line in f if not line.startswith("#")))
    final = max(int(r["seeds"]) for r in rows)
    cards = []
    for cls, cls_key in (("physical", "cb_kind_phys"), ("special", "cb_kind_spec")):
        for build in ("melee", "ranged"):
            top = sorted((r for r in rows if r["class"] == cls and r["build"] == build and int(r["seeds"]) == final),
                         key=lambda r: int(r["rank"]))[:GROUP_TOP]
            items = []
            for r in top:
                names = []
                for mid in r["group"].split("+"):
                    m = moves_by[mid]
                    badge = (f'<span class="tier-badge mini {m["tier"]}">{m["tier"]}</span>' if "tier" in m else "")
                    names.append(f'<span class="bg-mv{" is-buff" if "tier" not in m else ""}">{badge}'
                                 f'{esc(m["en"]["name"] if L.en else m["name"])}</span>')
                items.append(f'<li><span class="bg-moves">{"".join(names)}</span>'
                             f'<em class="bg-val">{esc(L.dec(float(r["score_rel"]), 2))}×</em></li>')
            cards.append(f'<article class="bg"><h3>{esc(L.t(cls_key))} · {esc(L.t("bd_" + build))}</h3>'
                         f'<ol>{"".join(items)}</ol></article>')
    return (f'<section id="grupos" class="bg-section"><h2>{icon("ball")}{esc(L.t("cat_groups"))}</h2>'
            f'<p class="lede">{esc(L.t("mv_groups_lede", n=GROUP_TOP))}</p><div class="bg-grid">{"".join(cards)}</div></section>')


def render_ataques(c: Ctx, moves: list[dict], meta: dict, unranked: list[dict]) -> str:
    L = c.L
    moves_by = {m["id"]: m for m in moves + unranked}
    blocks, toc = [], []
    for cat_id, icon_name in (("physical", "sword"), ("special", "sparkle"), ("stat", "bow")):
        inner = []
        if cat_id == "stat":
            items = "".join(move_card(L, m) for m in unranked)
            inner.append(f'<p class="lede">{esc(L.t("mv_unranked"))}</p><ul class="mv-grid">{items}</ul>')
        for t in TIERS if cat_id != "stat" else ():
            ms = sorted((m for m in moves if m["category"] == cat_id and m["tier"] == t), key=lambda m: m["rank"])
            if not ms:
                continue
            items = "".join(move_card(L, m) for m in ms)
            inner.append(f'<div class="mv-tier"><h3>{tier_badge(L, t)} <small>{len(ms)}</small></h3>'
                         f'<ul class="mv-grid">{items}</ul></div>')
        blocks.append(f'<section id="{cat_id}" class="mv-section"><h2>{icon(icon_name)}{esc(L.t("cat_" + cat_id))}</h2>'
                      f'{"".join(inner)}</section>')
        toc.append(f'<li><a href="#{cat_id}">{icon(icon_name)}{esc(L.t("cat_" + cat_id))}</a></li>')
    toc.append(f'<li><a href="#grupos">{icon("ball")}{esc(L.t("cat_groups"))}</a></li>')
    p1 = meta["method"]["p1"]
    search_icon = ('<svg class="search-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><circle cx="7" cy="7" '
                   'r="4.6" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10.6 10.6 14.5 14.5" '
                   'stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>')
    content = f"""
<h1>{esc(L.t("ataques_h1"))}</h1>
<p class="lede">{esc(L.t("mv_lede", refs=p1["refs"], seeds=p1["seeds"]))}</p>
<div class="search-field mv-finder">{search_icon}<input id="mv-q" type="search" autocomplete="off" placeholder="{esc(L.t("mv_search"))}" aria-label="{esc(L.t("mv_search"))}"></div>
<p id="mv-none" class="mv-none" hidden>{esc(L.t("mv_none"))}</p>
<ul class="toc">{"".join(toc)}</ul>
<details class="more">
<summary>{esc(L.t("mv_read_h"))}</summary>
{damage_legend(L)}
{range_legend(L)}
{move_scale(L)}
</details>
{"".join(blocks)}
{best_groups(L, moves_by)}
"""
    return page(c, "ataques", L.t("ataques_title", site=legal.SITE_NAME),
                L.t("ataques_desc", n=len(moves) + len(unranked), game=legal.GAME_NAME), content, meta)


def render_finder(c: Ctx, meta: dict) -> str:
    L = c.L
    return page(c, "buscador", L.t("tf_title", game=legal.GAME_NAME, site=legal.SITE_NAME),
                L.t("tf_desc", game=legal.GAME_NAME), finder.content(L), meta)


def render_planner(c: Ctx, meta: dict) -> str:
    L = c.L
    return page(c, "planificador", L.t("bp_title", game=legal.GAME_NAME, site=legal.SITE_NAME),
                L.t("bp_desc", game=legal.GAME_NAME), planner.content(L), meta)


def render_objetos(c: Ctx, meta: dict) -> str:
    L = c.L
    content = objetos.items_content(L, L.t("obj_h1"), L.t("obj_lede"))
    return page(c, "objetos", L.t("obj_title", site=legal.SITE_NAME),
                L.t("obj_desc", game=legal.GAME_NAME), content, meta)


def render_pasivas(c: Ctx, meta: dict) -> str:
    L = c.L
    content = pasivas.content(L, c.home)
    return page(c, "pasivas", L.t("pv_title", site=legal.SITE_NAME),
                L.t("pv_desc", game=legal.GAME_NAME), content, meta)


def render_tipos(c: Ctx, meta: dict) -> str:
    L = c.L
    return page(c, "tipos", L.t("tp_title", site=legal.SITE_NAME),
                L.t("tp_desc", game=legal.GAME_NAME), tipos.content(L, c.home), meta)


GACHA_STARS = (5, 4, 4, 3, 3, 3, 2, 2, 1)  # estrellas de cada banner, del mejor al peor


def gacha_card(c: Ctx, i: int, g: dict, last: int, by_banner: dict[int, list[dict]], by_dex: dict[int, dict]) -> str:
    L = c.L
    name = L.banner(g["name"])
    best = sorted(by_banner[g["gen"]], key=lambda p: p["r"][0])[:3]
    pulls = "".join(
        f'<a class="gc-mon" href="{mon_href(c, p)}" title="{esc(L.mon(p))}">'
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
            f'<span class="gc-one">{esc(L.t("g_one_in", n=round(100 / g["sPlusARate"])))}</span>'
            f'<span class="gc-own" data-gen="{g["gen"]}"></span></div>'
            f'<div class="gc-pulls" role="group" aria-label="{esc(L.t("g_pulls", name=name))}">{pulls}</div></li>')


def banners_script(L: Lang, gachas: list[dict]) -> str:
    """Nombre de cada banner en este idioma. La colección y el progreso de gacha lo leen de aquí."""
    data = [{"gen": g["gen"], "name": L.banner(g["name"])} for g in sorted(gachas, key=lambda g: g["gen"])]
    return f'<script type="application/json" id="banners">{json.dumps(data, ensure_ascii=False)}</script>'


def collection_panel(L: Lang, hidden: bool) -> str:
    snippet = (ROOT / "console" / ("coleccion.en.js" if L.en else "coleccion.js")).read_text(encoding="utf8")
    return f"""<section class="gc-panel" data-panel="coleccion"{" hidden" if hidden else ""}>
<div id="import-area">
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
  <label class="drop" id="drop" for="file">
    <span class="drop-text">{esc(L.t("col_drop"))}</span>
    <input id="file" type="file" accept="application/json,.json">
  </label>
</div>
</div>
<div id="saved" class="saved" aria-live="polite"></div>
<div id="result" aria-live="polite"></div>
</section>"""


def gacha_page(c: Ctx, gachas: list[dict], pokemon: list[dict], meta: dict, tab: str, title: str, desc: str,
               canonical: str | None = None) -> str:
    """Gacha y colección en una página. Las dos pestañas comparten la colección guardada: al importarla, las
    tarjetas de gacha muestran cuántos Pokémon te faltan en cada banner (app.js)."""
    L = c.L
    ordered = sorted(gachas, key=lambda g: -g["sPlusARate"])
    by_banner: dict[int, list[dict]] = {}
    for p in pokemon:
        by_banner.setdefault(p["bannerId"], []).append(p)
    by_dex = {p["dex"]: p for p in pokemon}
    cards = "".join(gacha_card(c, i, g, len(ordered) - 1, by_banner, by_dex) for i, g in enumerate(ordered))
    tabs = "".join(
        f'<button class="seg" type="button" data-tab="{key}" aria-pressed="{"true" if key == tab else "false"}">'
        f'{esc(L.t("tab_" + key))}</button>'
        for key in ("gacha", "coleccion"))
    content = f"""{balls.defs()}
<h1>{esc(L.t("gachas_h1", game=legal.GAME_NAME))}</h1>
{banners_script(L, gachas)}
<div class="gc-tabs" id="gc-tabs" data-tab="{tab}" role="group" aria-label="{esc(L.t("gc_tabs"))}">{tabs}</div>
<section class="gc-panel" data-panel="gacha"{" hidden" if tab != "gacha" else ""}>
<p class="gc-go-row"><button class="gc-link" type="button" data-go-tab="coleccion">{icon("dice")}{esc(L.t("g_yours"))}</button></p>
<ol class="gacha">{cards}</ol>
</section>
{collection_panel(L, hidden=tab != "coleccion")}
"""
    return page(c, "gachas", title, desc, content, meta, canonical=canonical)


def render_gachas(c: Ctx, gachas: list[dict], pokemon: list[dict], meta: dict) -> str:
    L = c.L
    return gacha_page(c, gachas, pokemon, meta, "gacha", L.t("gachas_title", site=legal.SITE_NAME),
                      L.t("gachas_desc", game=legal.GAME_NAME))


def render_coleccion(c: Ctx, gachas: list[dict], pokemon: list[dict], meta: dict) -> str:
    """Enlaces viejos a coleccion.html (también con #c= compartido): la misma página con la pestaña de colección
    abierta. La canónica es gachas.html, que es la URL que se indexa."""
    L = c.L
    canonical = f"{legal.SITE_URL}/{'en/' if L.en else ''}gachas"
    return gacha_page(c, gachas, pokemon, meta, "coleccion", L.t("col_title", site=legal.SITE_NAME),
                      L.t("col_desc", game=legal.GAME_NAME), canonical=canonical)


def render_landing(c: Ctx, built: landing.Built, meta: dict) -> str:
    return page(c, "landing", built.title, built.desc, built.content, meta, extra_head=built.jsonld,
                head_links=built.alternates)


def improved_notice(c: Ctx, link: bool = True) -> str:
    """Aviso del método nuevo: sale en la portada (con enlace a Método) y en Método."""
    L = c.L
    more = f' <a href="{c.home}metodo.html">{esc(L.t("m3_notice_link"))}</a>' if link else ""
    return f'<aside class="notice" role="note"><b>{esc(L.t("m3_notice_h"))}</b> {esc(L.t("m3_notice"))}{more}</aside>'


def render_metodo(c: Ctx, meta: dict) -> str:
    L = c.L
    m = meta["method"]
    p1, p2, p3 = m["p1"], m["p2"], m["p3"]
    sizes = " · ".join(f'{t["tier"]} {t["from"]}–{t["to"]}' for t in meta["tierCuts"])
    kpis = (("m3_k_games", L.num(m["games"])), ("m3_k_attacks", L.num(p1["attacks"])),
            ("m3_k_groups", L.num(p2["groups"] + p3["groups"][0])), ("m3_k_mons", L.num(meta["total"])))
    kpi_html = "".join(f'<div><dt>{esc(L.t(k))}</dt><dd>{esc(v)}</dd></div>' for k, v in kpis)
    steps = (
        ("m3_p1_h", L.t("m3_p1", attacks=p1["attacks"], refs=p1["refs"], seeds=p1["seeds"], games=L.num(p1["games"]))),
        ("m3_p2_h", L.t("m3_p2", groups=L.num(p2["groups"]), s1=p2["seeds"][0], s2=p2["seeds"][1], s3=p2["seeds"][2],
                        games=L.num(p2["games"]))),
        ("m3_p3_h", L.t("m3_p3", g1=L.num(p3["groups"][0]), g2=L.num(p3["groups"][1]), g3=L.num(p3["groups"][2]),
                        s1=p3["seeds"][0], s2=p3["seeds"][1], s3=p3["seeds"][2], games=L.num(p3["games"]))
         + " " + L.t("m3_p3_var", variants=L.num(p3["variants"]), seeds=p3["seeds"][2], duels=L.num(p3["duels"]),
                     promoted=L.num(p3["promoted"]))
         + " " + L.t("m3_p3_rule", rule=L.num(p3["rule"]))),
        ("m3_rank_h", L.t("m3_rank", seeds=meta["seeds"], sizes=sizes, dps=L.num(m["score"]["dpsRef"]),
                          kpm=L.num(m["score"]["kpmRef"]))),
        ("m3_why_h", L.t("m3_why", r2=L.pcts(meta["why"]["r2"] * 100))),
        ("m3_limits_h", L.t("m3_limits")),
    )
    body = "".join(f'<h2>{esc(L.t(h))}</h2><p class="met-text">{esc(t)}</p>' for h, t in steps)
    content = f"""
<h1>{esc(L.t("met_h1"))}</h1>
{improved_notice(c, link=False)}
<p class="lede">{esc(L.t("m3_lede", games=L.num(m["games"]), minutes=m["seconds"] // 60))}</p>
<p class="fresh">{esc(legal.freshness_text(L, meta))}</p>
<dl class="kpis">{kpi_html}</dl>
{body}
<p class="met-text">{esc(L.t("met_check", sha=legal.UPDATED_COMMIT))}</p>
"""
    return page(c, "metodo", L.t("met_title", site=legal.SITE_NAME, game=legal.GAME_NAME),
                L.t("m3_desc", game=legal.GAME_NAME, games=L.num(m["games"])), content, meta)


def render_novedades(c: Ctx, meta: dict) -> str:
    L = c.L
    return page(c, "novedades", novedades.title(L, legal.SITE_NAME, legal.GAME_NAME),
                novedades.desc(L, legal.GAME_NAME), novedades.content(L), meta)


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
<p class="lede">{L.t("about_value_html", repo=esc(legal.REPO_URL), **legal.method_counts(L, meta))}</p>
<p class="muted">{esc(L.t("disclaimer", game=legal.GAME_NAME))}</p>
{legal_html}
<h2 id="creditos">{esc(L.t("about_credits_h"))}</h2>
<h3>{esc(L.t("about_sprites_h"))}</h3>
<p>{L.t("about_sprites_html", url=esc(lic["sourceUrl"]), source=esc(lic["source"]), lic_url=esc(lic["url"]),
        lic=esc(lic["name"]))}</p>
<ul class="credits-list">{"".join(creds)}</ul>
<h3>{esc(L.t("about_icons_h"))}</h3>
<p>{icons}</p>
    <p>{L.t("about_font_html", root=c.assets)}</p>
{agents_line(c)}
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
        unranked = load("moves_unranked.json")
        species = load("public/species.json")
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
    missing = theme.csp_missing(ROOT)
    if missing:
        print(f"ERROR: la CSP de {', '.join(missing)} no lleva la huella {theme.csp_hash()} de build/theme.py", file=sys.stderr)
        return 1
    if SITE.exists():
        for child in SITE.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    ASSET_V = pack.build(SRC, SITE, OUT / "public")
    ordered = sorted(full, key=lambda e: e["dex"])
    # Boosts have no tier, so they live in moves_unranked.json. Species pages still name them.
    moves_by = {m["id"]: m for m in moves}
    moves_by.update({m["id"]: m for m in unranked})
    for mid, m in moves_by.items():
        if "icon" in m:
            write(f"img/moves/{mid}.svg", move_icon_svg(m["icon"], standalone=True))
    odds = static_ficha.odds_table(full)
    sheet_paths = [f"pokemon/{species_path(e['dex'], e['nameEn'])}/" for e in ordered]
    by_dex = {p["dex"]: p for p in full}
    for L in LANGS:
        def put(rel: str, build) -> None:
            write(f"{L.prefix}{rel}", build(Ctx.of(L, rel)))

        other = ES if L.en else EN
        for page_def in landing.pages():
            rel = landing.rel(L, page_def)
            c = Ctx.of(L, rel, twin=landing.folder(other, page_def))
            built = landing.build(L, page_def, index, meta, c.home)
            write(f"{L.prefix}{rel}", render_landing(c, built, meta))
        put("index.html", lambda c: render_index(c, index, meta))
        put("novedades.html", lambda c: render_novedades(c, meta))
        put("ataques.html", lambda c: render_ataques(c, moves, meta, unranked))
        put("objetos.html", lambda c: render_objetos(c, meta))
        put("pasivas.html", lambda c: render_pasivas(c, meta))
        put("tipos.html", lambda c: render_tipos(c, meta))
        put("gachas.html", lambda c: render_gachas(c, gachas, index, meta))
        put("coleccion.html", lambda c: render_coleccion(c, gachas, index, meta))
        put("metodo.html", lambda c: render_metodo(c, meta))
        for key, render_tool in (("finder", render_finder), ("planner", render_planner)):
            rel = toolpages.rel(L, key)
            c = Ctx.of(L, rel, twin=toolpages.twin(L, key))
            write(f"{L.prefix}{rel}", render_tool(c, meta))
        put("acerca.html", lambda c: render_acerca(c, meta))
        put("pokemon/index.html", lambda c: render_ficha(c, index, meta))
        for i, entry in enumerate(ordered):
            prev = ordered[i - 1] if i else None
            nxt = ordered[i + 1] if i + 1 < len(ordered) else None
            rel = f"pokemon/{species_path(entry['dex'], entry['nameEn'])}/index.html"
            put(rel, lambda c, e=entry, pv=prev, nx=nxt: render_species(c, e, moves_by, pv, nx, odds[e["dex"]], meta))
    write("data/game-stats.json", json.dumps(gamestats.site_json(), ensure_ascii=False, separators=(",", ":")) + "\n")
    write("404.html", render_404(meta))
    share_image.save(SITE / "og.png")
    agents.write_all(SITE, meta, gachas, index, sheet_paths)
    files = [f for f in SITE.rglob("*") if f.is_file()]
    size = sum(f.stat().st_size for f in files)
    print(f"render: {len(files)} archivos, {size / 1e6:.2f} MB → {SITE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
