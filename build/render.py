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

import agents  # noqa: E402
import balls  # noqa: E402
import charts  # noqa: E402
import legal  # noqa: E402
import objetos  # noqa: E402
import pasivas  # noqa: E402
import pack  # noqa: E402
import regions  # noqa: E402
import share_image  # noqa: E402
import theme  # noqa: E402
import typedata  # noqa: E402
from i18n import ES, LANGS, TYPE_NAMES, Lang  # noqa: E402

SITE = ROOT / "site"
OUT = ROOT / "build" / "out"
SRC = ROOT / "src"
TEMPLATES = Path(__file__).resolve().parent / "templates"
SPRITES = legal.SPRITE_BASE
EXT = legal.SPRITE_EXT
SCALE_LIST = 2
TIERS = ["S", "A", "B", "C", "D"]
CATEGORIES = [("melee", "cuerpo a cuerpo"), ("ranged", "distancia"), ("stat", "estadística")]  # (id, valor del CSV)
NAV = [("index", "index.html", "nav_tiers"),
       ("ataques", "ataques.html", "nav_ataques"), ("objetos", "objetos.html", "nav_objetos"),
       ("pasivas", "pasivas.html", "nav_pasivas"),
       ("gachas", "gachas.html", "nav_gachas"),
       ("coleccion", "coleccion.html", "nav_coleccion"), ("acerca", "acerca.html", "nav_acerca"),
       ("metodo", "metodo.html", "nav_metodo")]
SORT_KEYS = ("rank", "name", "dex", "atk", "hp", "spd", "ehp", "rad", "td", "mv", "st", "rar")  # orden de la lista
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


def social_head(c: Ctx, title: str, description: str) -> str:
    """Etiquetas para compartir: canónica, Open Graph (Reddit, Discord, WhatsApp...) y Twitter/X (tarjeta grande con la
    imagen de build/share_image.py). La URL es la de la página en el idioma de la página, sin .html."""
    L = c.L
    path = c.rel.removesuffix("index.html").removesuffix(".html")
    url = f"{legal.SITE_URL}/{'en/' if L.en else ''}{path}"
    image = f"{legal.SITE_URL}/og.png"
    alt = L.t("og_alt")
    tags = [
        f'<link rel="canonical" href="{esc(url)}">',
        '<meta property="og:type" content="website">',
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


def page(c: Ctx, page_id: str, title: str, description: str, content: str, meta: dict, extra_head: str = "") -> str:
    L = c.L
    agents_html = (f'<p class="agents">{esc(L.t("agents_label"))} <a href="{c.assets}llms.txt">llms.txt</a> · '
              f'<a href="{c.assets}llms-full.txt">llms-full.txt</a> · '
              f'<a href="{c.assets}data/ranking.csv">ranking.csv</a></p>')
    follow = (f'<a class="follow" href="{legal.X_URL}" target="_blank" rel="noopener" '
              f'aria-label="{esc(L.t("follow_label", handle=legal.X_HANDLE))}">{esc(legal.X_HANDLE)}</a>')
    social = "" if page_id == "404" else social_head(c, title, description)
    analytics = (f"<script defer src='https://static.cloudflareinsights.com/beacon.min.js' "
                 f"data-cf-beacon='{{\"token\": \"{legal.WEB_ANALYTICS_TOKEN}\"}}'></script>")
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
        nav_aria=esc(L.t("nav_main")), foot_aria=esc(L.t("nav_foot")), switch=switch, theme=theme_button(L), nav=nav,
        content=content, footer_nav=footer_nav, disclaimer=esc(L.t("disclaimer", game=legal.GAME_NAME)),
        sprites_line=sprites_line, build_info=esc(build_info.replace("--", "-")), agents=agents_html,
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
    content = f"""
{balls.defs()}
<h1>{esc(L.t("index_h1", game=legal.GAME_NAME))}</h1>
<div class="finder">
  <div class="search">
    <label class="sr" for="q">{esc(L.t("search_label"))}</label>
    <div class="search-field">
      <svg class="search-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><circle cx="7" cy="7" r="4.6" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10.6 10.6 14.5 14.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>
      <input id="q" type="search" placeholder="{esc(L.t("search_ph"))}" autocomplete="off" spellcheck="false">
      <button id="clear" class="clear" type="button" hidden aria-label="{esc(L.t("search_clear"))}">×</button>
    </div>
  </div>
  <div class="sortline">
    <label class="sr" for="sort">{esc(L.t("sort_by"))}</label><select id="sort">{options}</select>
    <button id="dir" class="icon-btn" type="button" data-asc="{esc(L.t("dir_asc"))}" data-desc="{esc(L.t("dir_desc"))}" aria-label="{esc(L.t("dir_asc"))}" title="{esc(L.t("dir_asc"))}"><i class="ico ico-arrow" aria-hidden="true"></i></button>
    <button id="random" class="icon-btn" type="button" aria-label="{esc(L.t("random_btn"))}" title="{esc(L.t("random_btn"))}"><i class="ico ico-dice" aria-hidden="true"></i></button>
  </div>
  <div class="group-by" role="group" aria-label="{esc(L.t("group_by"))}">{groups}</div>
  <p id="count" aria-live="polite"></p>
  <p id="nomatch" class="nomatch" hidden>{esc(L.t("no_match"))}</p>
</div>
<div id="tierlist">
{"".join(sections)}
</div>
<script type="application/json" id="labels">{labels_json}</script>
<noscript><p class="muted">{esc(L.t("noscript"))}</p></noscript>
"""
    return page(c, "index", L.t("index_title", site=legal.SITE_NAME, game=legal.GAME_NAME),
                L.t("index_desc", n=meta["total"], game=legal.GAME_NAME), content, meta,
                extra_head=agents.dataset_jsonld(L, meta))


FICHA_KEYS = (
    "crumb_home", "legendary", "stars_alt", "sprite_alt", "ficha_title", "ficha_desc", "flag_status", "flag_melee",
    "flag_capped", "flag_types", "pager_aria", "dex_no", "tier", "f_missing", "t_band", "t_pillars", "t_methods", "t_sim",
    "band_rank", "band_range", "band_alt", "t_learn", "learn_start", "t_build", "build_start", "build_best", "build_boost", "build_alt", "build_items", "build_cards", "build_card_evo", "build_super", "build_neutral",
    "build_share", "build_copied", "build_slot", "build_brand", "build_group", "build_best_item", "build_card_n", "build_more",
    "t_rank", "rank_how", "ficha_rank", "pill_stats", "pill_moves", "pill_typedef", "pill_size", "pillars_alt_item",
    "median", "m_sheet", "m_simStart", "m_simBest", "m_lateMax", "m_lateFresh", "methods_final", "methods_alt",
    "methods_alt_item", "sim_start", "sim_best", "sim_median", "sim_alt", "sim_gain", "sim_noshop",
    "rar_1", "rar_2", "rar_3", "rar_4", "rar_5", "t_base", "bs_hp", "bs_atk", "bs_def", "bs_spa", "bs_spd", "bs_spe",
    "bs_total", "bs_alt_item", "bs_s_hp", "bs_s_atk", "bs_s_def", "bs_s_spa", "bs_s_spd", "bs_s_spe")


def render_ficha(c: Ctx, index: list[dict], meta: dict) -> str:
    """Plantilla única de ficha: la estructura y los textos salen de aquí y src/ficha.js pone los datos del ?id=."""
    L = c.L
    strings = {k: L.t_raw(k).replace("{site}", legal.SITE_NAME).replace("{game}", legal.GAME_NAME)
               .replace("{total}", str(charts.TOTAL)) for k in FICHA_KEYS}
    blob = json.dumps({"en": L.en, "s": strings}, ensure_ascii=False).replace("</", "<\\/")
    pills = "".join(f'<span data-t="{t}">{type_pill(L, t)}</span>' for t in typedata.TYPE_COLOR)
    badges = "".join(
        f'<span data-gen="{gen}">{regions.badge(L, SPRITES, gen, L.banner(name), {}, small=True)}</span>'
        for gen, name in BANNER_NAMES.items())
    content = f"""
{balls.defs()}
<article id="ficha"><noscript><p>{esc(L.t("noscript_ficha"))}</p></noscript></article>
<template id="tpl-types">{pills}</template>
<template id="tpl-regions">{badges}</template>
<script type="application/json" id="i18n">{blob}</script>
"""
    return page(c, "ficha", legal.SITE_NAME,
                L.t("index_desc", n=meta["total"], game=legal.GAME_NAME), content, meta)


# Cada tipo de movimiento del juego se dibuja con uno de estos patrones (la animación de la tarjeta).
KIND_FX = {"melee": "swing", "cone": "swing", "trail": "swing", "dash": "dash",
           "projectile": "shot", "beam": "beam", "chain": "chain", "boomerang": "shot", "turret": "shot",
           "orbit": "ring", "aura": "ring", "nova": "ring", "mine": "drop", "meteor": "drop", "buff": "boost"}
LETTERS = "abcdefghijklmnopqrstuvwxyz"  # la rejilla de píxeles de moves.json usa letras para la paleta


def demo_mon(index: list[dict], move_type: str) -> dict:
    """El Pokémon de la animación: el de mejor puesto que tiene ese tipo."""
    return min((p for p in index if move_type in p["types"]), key=lambda p: p["r"][0])


def move_icon_svg(icon: dict) -> str:
    """El icono del juego (ui/icons.js) como SVG: la misma rejilla de píxeles que usa la ficha."""
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
    return (f'<svg class="mv-icon" viewBox="0 0 {w} {h}" width="{w * 3}" height="{h * 3}" aria-hidden="true" '
            f'focusable="false" shape-rendering="crispEdges">{"".join(rects)}</svg>')


# Posiciones de las dianas en el escenario (%), según cómo las alcanza el ataque en el juego.
# El Pokémon está en el centro (50 %, 64 %). Chain: cuatro dianas, las que golpea el juego (count 4).
FOE_POS = {
    "shot": [(80, 64)],
    "home": [(74, 64)],
    "pierce": [(72, 64), (90, 64)],          # atraviesa la primera y sigue hasta la segunda
    "beam": [(72, 64)],                       # el rayo pasa por ella y sigue hasta el borde
    # Chain: orden de salto del juego (combat.js chain): desde cada impacto, la diana no alcanzada más cercana.
    "chain": [(68, 86), (88, 72), (90, 24), (70, 22)],
}


def move_fx(m: dict) -> str:
    """El patrón de animación que enseña el juego: teledirigido, perforante, rayo, salto o el de su tipo de movimiento."""
    if m["kind"] == "projectile":
        mech = m["mech"]
        if mech["homing"] > 0:
            return "home"
        if mech["pierce"] > 0:
            return "pierce"
        return "shot"
    return KIND_FX[m["kind"]]


def move_stage(L: Lang, m: dict, mon: dict, home: str) -> str:
    """El escenario: el Pokémon de ejemplo y el patrón de ataque de ese movimiento, en CSS y SVG."""
    fx = move_fx(m)
    name = L.mon(mon)
    particles = "".join(f'<i class="mv-p p{i}"></i>' for i in (1, 2, 3))
    hero = (f'<span class="mv-hero"><img src="{SPRITES}{mon["dex"]}{EXT}" width="{mon["w"]}" height="{mon["h"]}" '
            f'alt="" loading="lazy"></span>')
    # Dianas: el ataque sale del Pokémon y acierta ahí. Los potenciadores no tienen objetivo.
    foes = "" if fx == "boost" else "".join(
        f'<span class="mv-foe f{i + 1}" style="--tx:{x}%;--hy:{y}%"><i></i></span>'
        for i, (x, y) in enumerate(FOE_POS.get(fx, FOE_POS["shot"])))
    # Rayo: una barra desde el Pokémon hasta el borde. Cadena: un trazo por salto, en orden, hasta cada diana.
    ray = '<i class="mv-ray"></i>' if fx == "beam" else ""
    svg = ""
    if fx == "chain":
        pts = [(50, 64)] + FOE_POS["chain"]
        links = "".join(f'<line class="mv-link k{i + 1}" x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}"/>'
                        for i, (a, b) in enumerate(zip(pts, pts[1:])))
        svg = f'<svg class="mv-beams" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">{links}</svg>'
    orb = '<i class="mv-orb"></i>' if fx in ("home", "pierce") else ""
    return (f'<div class="mv-stage fx-{fx}" aria-hidden="true"><i class="mv-arc"></i>{particles}{ray}{svg}{orb}{foes}{hero}</div>'
            f'<a class="mv-ex" href="{home}pokemon/?id={mon["dex"]}">{esc(L.t("mv_example", name=name))}</a>')


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
    if "buff" in m:
        b = m["buff"]
        facts.append(L.t("mv_buff", dur=L.dec(b["dur"], 0), cd=L.dec(b["cd"], 2)))
    if not facts:
        return ""
    return '<ul class="mv-facts">' + "".join(f"<li>{esc(f)}</li>" for f in facts) + "</ul>"


def move_card(L: Lang, m: dict, mon: dict, home: str) -> str:
    name = m["en"]["name"] if L.en else m["name"]
    # Teledirigido y perforante se nombran aparte del proyectil normal: cambian cómo se usa el ataque.
    kind = L.t("mv_kind_" + {"home": "homing", "pierce": "pierce"}.get(move_fx(m), m["kind"]))
    bars = charts.buff_bars(L, m["score"], m["buff"]) if "buff" in m else charts.move_bars(L, m["score"])
    types = TYPE_NAMES["en" if L.en else "es"]
    search = " ".join([m["name"], m["en"]["name"] or "", types[m["type"]], kind]).lower()
    return (f'<li class="mv-card" data-q="{esc(search)}">'
            f'<div class="mv-top">{move_icon_svg(m["icon"])}<div class="mv-title"><h4>{esc(name)}</h4>'
            f'<div class="mv-tags">{type_pill(L, m["type"])}<span class="mv-kind">{esc(kind)}</span></div></div></div>'
            f'{move_stage(L, m, mon, home)}<div class="mv-meter">{bars}</div>{move_facts(L, m)}</li>')


def render_ataques(c: Ctx, moves: list[dict], meta: dict, index: list[dict]) -> str:
    L = c.L
    blocks, toc = [], []
    for cat_id, cat_csv in CATEGORIES:
        inner = []
        for t in TIERS:
            ms = sorted((m for m in moves if m["category"] == cat_csv and m["tier"] == t), key=lambda m: m["rank"])
            if not ms:
                continue
            items = "".join(move_card(L, m, demo_mon(index, m["type"]), c.home) for m in ms)
            inner.append(f'<div class="mv-tier"><h3>{tier_badge(L, t)} <small>{len(ms)}</small></h3>'
                         f'<ul class="mv-grid">{items}</ul></div>')
        icon_name = {"melee": "sword", "ranged": "bow", "stat": "sparkle"}[cat_id]
        blocks.append(f'<section id="{cat_id}" class="mv-section"><h2>{icon(icon_name)}{esc(L.t("cat_" + cat_id))}</h2>'
                      f'{"".join(inner)}</section>')
        toc.append(f'<li><a href="#{cat_id}">{icon(icon_name)}{esc(L.t("cat_" + cat_id))}</a></li>')
    search_icon = ('<svg class="search-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><circle cx="7" cy="7" '
                   'r="4.6" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10.6 10.6 14.5 14.5" '
                   'stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>')
    content = f"""
<h1>{esc(L.t("ataques_h1"))}</h1>
<p class="lede">{esc(L.t("ataques_lede"))}</p>
<div class="search-field mv-finder">{search_icon}<input id="mv-q" type="search" autocomplete="off" placeholder="{esc(L.t("mv_search"))}" aria-label="{esc(L.t("mv_search"))}"></div>
<p id="mv-none" class="mv-none" hidden>{esc(L.t("mv_none"))}</p>
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


def render_pasivas(c: Ctx, meta: dict) -> str:
    L = c.L
    content = pasivas.content(L, L.t("pv_h1"), L.t("pv_lede"), L.t("pv_order_h"), L.t("pv_phases_h"),
                              L.t("pv_items_h"), L.t("pv_except_h"))
    return page(c, "pasivas", L.t("pv_title", site=legal.SITE_NAME),
                L.t("pv_desc", game=legal.GAME_NAME), content, meta)


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
            f'<span class="gc-one">{esc(L.t("g_one_in", n=round(100 / g["sPlusARate"])))}</span>'
            f'<span class="gc-own" data-gen="{g["gen"]}"></span></div>'
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
<p class="g-hint">{icon("dice")}<a href="{c.home}coleccion.html">{esc(L.t("g_yours"))}</a></p>
{banners_script(L, gachas)}
<ol class="gacha">{cards}</ol>
"""
    return page(c, "gachas", L.t("gachas_title", site=legal.SITE_NAME), L.t("gachas_desc", game=legal.GAME_NAME),
                content, meta)


def banners_script(L: Lang, gachas: list[dict]) -> str:
    """Nombre de cada banner en este idioma. La colección y el progreso de gacha lo leen de aquí."""
    data = [{"gen": g["gen"], "name": L.banner(g["name"])} for g in sorted(gachas, key=lambda g: g["gen"])]
    return f'<script type="application/json" id="banners">{json.dumps(data, ensure_ascii=False)}</script>'


def render_coleccion(c: Ctx, gachas: list[dict], meta: dict) -> str:
    L = c.L
    snippet = (ROOT / "console" / ("coleccion.en.js" if L.en else "coleccion.js")).read_text(encoding="utf8")
    content = f"""
<h1>{esc(L.t("col_h1"))}</h1>
{banners_script(L, gachas)}
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
    missing = theme.csp_missing(ROOT)
    if missing:
        print(f"ERROR: la CSP de {', '.join(missing)} no lleva la huella {theme.csp_hash()} de build/theme.py", file=sys.stderr)
        return 1
    if SITE.exists():
        for child in SITE.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    ASSET_V = pack.build(SRC, SITE, OUT / "public")
    for L in LANGS:
        def put(rel: str, build) -> None:
            write(f"{L.prefix}{rel}", build(Ctx.of(L, rel)))

        put("index.html", lambda c: render_index(c, index, meta))
        put("ataques.html", lambda c: render_ataques(c, moves, meta, index))
        put("objetos.html", lambda c: render_objetos(c, meta))
        put("pasivas.html", lambda c: render_pasivas(c, meta))
        put("gachas.html", lambda c: render_gachas(c, gachas, index, meta))
        put("coleccion.html", lambda c: render_coleccion(c, gachas, meta))
        put("metodo.html", lambda c: render_metodo(c, index, full, meta))
        put("acerca.html", lambda c: render_acerca(c, meta))
        put("pokemon/index.html", lambda c: render_ficha(c, index, meta))
    write("404.html", render_404(meta))
    share_image.save(SITE / "og.png")
    agents.write_all(SITE, meta, gachas)
    files = [f for f in SITE.rglob("*") if f.is_file()]
    size = sum(f.stat().st_size for f in files)
    print(f"render: {len(files)} archivos, {size / 1e6:.2f} MB → {SITE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
