"""Comprobaciones de aceptación sobre un sitio ya servido (local o desplegado).

    python3 build/check_site.py http://localhost:8765/
    python3 build/check_site.py https://mi-proyecto.vercel.app/ --external

Comprueba, en español y en inglés: enlaces internos y anclas sin romper, aviso legal en Info, conteos por
tier, % de gacha, barras en cada ataque, que el inglés no mezcla español, que los créditos de sprites solo salen en
Acerca y cubren los 966 Pokémon, que no se carga nada de otros dominios salvo los sprites del repositorio (jsDelivr o
el sitio mismo), que cada Pokémon tiene sus datos y su sprite, que los enlaces viejos /pokemon/<n>.html caen en la
404, que site/ cabe en el presupuesto de archivos y que, si hay Playwright, la ficha de cada Pokémon se dibuja con sus
cuatro gráficos y su sprite. Con --external, también los enlaces externos.

Los datos de build (meta.json, gachas.json) se leen de build/out/, donde los deja build/catalog.py. El servidor debe
devolver 404.html con estado 404 para lo que no existe, como el hosting: usa build/serve.py.
"""
from __future__ import annotations

import argparse
import csv
import html as html_lib
import json
import random
import re
import sys
import time
from collections import Counter, deque
from html.parser import HTMLParser
from shutil import which
from urllib.error import HTTPError, URLError
from pathlib import Path
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

import agents  # noqa: E402
import indexnow  # noqa: E402
import landing  # noqa: E402
import legal  # noqa: E402
import toolpages  # noqa: E402
import theme  # noqa: E402
import tiers  # noqa: E402
from i18n import EN, ES  # noqa: E402

try:
    from playwright.sync_api import Error, sync_playwright
except ImportError:
    Error = sync_playwright = None

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "SurvivorTiers-check/1.0"}
BEACON_URL = "https://static.cloudflareinsights.com/beacon.min.js"
SPRITE_CDN_PREFIX = "https://cdn.jsdelivr.net/gh/felipebasurto/survivortiers@"
# 8 páginas × 2 idiomas + 966 fichas × 2, más CSS, JSON y fuentes. Pages admite 20 000 archivos.
MAX_FILES, MAX_BYTES = 4_000, 180_000_000
EXPECTED_COUNTS = tiers.COUNTS
SPANISH_WORDS = re.compile(r"\b(el|los|las|del|con|para|puesto|aguante|daño|ficha|partidas?|repeticiones|cuántos)\b", re.I)
LANGS = ("", "en/")
# S+A rates from build/catalog.py on the phase-3 ranking.
EXPECTED_GACHA = {"Kanto": 3.3, "Johto": 10.0, "Hoenn": 10.4, "Sinnoh": 15.0, "Teselia": 17.0, "Kalos": 15.7,
                  "Alola": 16.9, "Galar": 11.5, "Paldea": 17.4}



class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.assets: list[str] = []
        self.ids: set[str] = set()
        self.imgs: list[dict] = []
        self.text: list[str] = []
        self.sprites = ""

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        if tag == "html" and a.get("data-sprites"):
            self.sprites = a["data-sprites"]
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "img":
            self.imgs.append(a)
            if a.get("src"):
                self.assets.append(a["src"])
        elif tag == "script" and a.get("src"):
            self.assets.append(a["src"])
        elif tag == "link" and a.get("href") and a.get("rel") in ("stylesheet", "icon"):
            self.assets.append(a["href"])

    def handle_data(self, data: str) -> None:
        self.text.append(data)


class _Redirect308(HTTPRedirectHandler):
    """urllib no sigue las 308, y Pages las usa para las .html; se siguen como una 301 (GET y HEAD)."""

    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_301(req, fp, 301, msg, headers)


_OPENER = build_opener(_Redirect308)


def fetch(url: str, method: str = "GET"):
    try:
        with _OPENER.open(Request(url, headers=UA, method=method), timeout=30) as r:
            return r.status, r.read() if method == "GET" else b""
    except HTTPError as e:
        return e.code, e.read() if method == "GET" else b""
    except URLError as e:
        return 0, str(e).encode()


def agent_check(base: str, body_by_url: dict[str, str], err, notes: list[str], n_sheets: int) -> None:
    """Archivos para agentes (build/agents.py): robots.txt, llms.txt y llms-full.txt, sitemap, datos descritos, pie y
    JSON-LD de la portada. Los enlaces absolutos de llms.txt apuntan a legal.SITE_URL; aquí se piden a este servidor."""
    site_url = legal.SITE_URL
    root = base.rstrip("/")

    def local(url: str) -> str:
        return root + url[len(site_url):] if url.startswith(site_url) else url

    code, body = fetch(base + "robots.txt")
    robots = body.decode("utf8", "replace")
    if code != 200 or b"Sitemap:" not in body:
        err(f"robots.txt: responde {code} o no enlaza el sitemap")
    for path in ("llms.txt", "llms-full.txt", "sitemap.xml", "data/ranking.csv", "data/meta.json", "data/gachas.json"):
        code, body = fetch(base + path)
        if code != 200 or not body:
            err(f"{path}: responde {code}")
    llms = fetch(base + "llms.txt")[1].decode("utf8", "replace")
    if not llms.startswith("# "):
        err("llms.txt no empieza por el título")
    links = re.findall(r"\]\((https?://[^)\s]+)\)", llms)
    local_links = [local(u) for u in links if u.startswith(site_url)]
    for url in local_links:
        code, _ = fetch(url)
        if code != 200:
            err(f"llms.txt: enlace roto ({code}) {url}")
    if len(local_links) < 15:
        err(f"llms.txt: solo {len(local_links)} enlaces locales")

    # el CSV tiene una cabecera y un Pokémon por fila
    csv_text = fetch(base + "data/ranking.csv")[1].decode("utf8", "replace")
    rows = csv_text.splitlines()
    if not rows or not rows[0].startswith("rank,dex,name,tier"):
        err("data/ranking.csv: falta la cabecera rank,dex,name,tier…")
    elif len(rows) != 967 or any(r.startswith("#") for r in rows):
        err(f"data/ranking.csv: {len(rows) - 1} filas, se esperaban 966 y sin líneas de comentario")

    # sitemap: una entrada por página de menú, por ficha, por página de consulta y por idioma
    expected = (len(agents.PAGES) + n_sheets + len(landing.pages()) + len(toolpages.FOLDERS)) * len(agents.LANG_PREFIX)
    sitemap = fetch(base + "sitemap.xml")[1].decode("utf8", "replace")
    if sitemap.count("<url>") != expected:
        err(f"sitemap.xml: {sitemap.count('<url>')} entradas, se esperaban {expected}")

    # los enlaces para agentes salen en Info (acerca), no en el pie de cada página
    for lang in LANGS:
        about = body_by_url.get(f"{base}{lang}acerca.html", "")
        if about and 'class="agents"' not in about:
            err(f"{lang}acerca.html: faltan los enlaces para agentes")
    # cada página (salvo la 404) lleva la canónica, Open Graph y la tarjeta de Twitter/X con la imagen compartida
    shared = (f'<meta property="og:image" content="{legal.SITE_URL}/og.png">', '<meta name="twitter:card" content="summary_large_image">',
              f'<meta name="twitter:site" content="{legal.X_HANDLE}">')
    for url, html in body_by_url.items():
        if url.startswith(base) and html and not url.endswith("404.html"):
            if '<link rel="canonical" href="' not in html or any(t not in html for t in shared):
                err(f"{url}: faltan las etiquetas para compartir (canónica, Open Graph o Twitter/X)")
            if legal.WEB_ANALYTICS_TOKEN not in html:
                err(f"{url}: falta el beacon de Cloudflare Web Analytics")
    key = indexnow.key_file().stem
    st, key_body = fetch(f"{base}{key}.txt")
    if st != 200 or key_body.decode("utf8", "replace").strip() != key:
        err(f"{key}.txt: la clave de IndexNow no se sirve en la raíz con su contenido")
    st, png = fetch(base + "og.png")
    if st != 200 or png[:8] != b"\x89PNG\r\n\x1a\n" or int.from_bytes(png[16:20], "big") != 1200 or int.from_bytes(png[20:24], "big") != 630:
        err("og.png no es un PNG de 1200 × 630")
    for lang in ("", "en/"):
        html = body_by_url.get(f"{base}{lang}", "")
        if '"@type": "Dataset"' not in html:
            err(f"{base}{lang}: falta el JSON-LD Dataset")
    notes.append(f"agentes: llms.txt con {len(local_links)} enlaces, sitemap con {expected} entradas")
    sitemap_check(base, sitemap, body_by_url, err, notes)
    for bot in agents.ALLOWED_BOTS:
        if f"User-agent: {bot}\nAllow: /" not in robots:
            err(f"robots.txt: falta permitir a {bot}")
    if legal.UPDATED_COMMIT not in llms:
        err("llms.txt: falta el parche al que está puesto al día el sitio")


LD_RE = re.compile(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', re.S)


NO_JS_PHRASES = re.compile(r"necesita JavaScript|needs JavaScript", re.I)
MIN_VISIBLE_CHARS = 300  # texto que un rastreador lee sin ejecutar JavaScript (sin script, style ni noscript)
META_DESC = re.compile(r'<meta name="description" content="([^"]*)">')
FRESH_LINE = {"es": "Actualizado al parche del", "en": "Updated to the"}


def visible_text(html: str) -> str:
    html = re.sub(r"<(script|style|noscript|template)\b.*?</\1>", " ", html, flags=re.S | re.I)
    return " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", html)).split())


def sitemap_check(base: str, sitemap: str, body_by_url: dict[str, str], err, notes: list[str]) -> None:
    """Cada URL del sitemap existe en el sitio construido, con lastmod y las tres alternativas hreflang."""
    locs = re.findall(r"<loc>([^<]+)</loc>", sitemap)
    if len(locs) != len(set(locs)):
        err("sitemap.xml: URL repetidas")
    for entry in re.findall(r"<url>.*?</url>", sitemap, re.S):
        if not re.search(r"<lastmod>\d{4}-\d{2}-\d{2}</lastmod>", entry) or entry.count("<xhtml:link") != 3:
            err(f"sitemap.xml: entrada sin lastmod o sin hreflang: {entry[:90]}")
            break
    broken = []
    for loc in locs:
        url = base + loc.removeprefix(legal.SITE_URL + "/")
        if url in body_by_url or url + ".html" in body_by_url:
            continue
        code, _ = fetch(url)
        if code != 200:
            broken.append((loc, code))
    if broken:
        err(f"sitemap.xml: {len(broken)} URL no resuelven en el sitio ({broken[:3]})")
    notes.append(f"sitemap: {len(locs)} URL, todas resuelven")


def seo_check(base: str, body_by_url: dict[str, str], index: list[dict], err, notes: list[str]) -> None:
    """Lo que ve un buscador o un asistente de IA que no ejecuta JavaScript: título, descripción, canónica y hreflang en
    cada página indexable, texto real en cada una, línea de actualización y la portada con su texto y su JSON-LD."""
    titles: dict[str, str] = {}
    pages = {u: h for u, h in body_by_url.items() if u.startswith(base) and h and not u.endswith("404.html")}
    for url, html in pages.items():
        title = re.search(r"<title>([^<]+)</title>", html)
        desc = META_DESC.search(html)
        canon = re.search(r'<link rel="canonical" href="([^"]+)">', html)
        if not title or not title.group(1).strip():
            err(f"{url}: título vacío")
        elif title.group(1) in titles and canon and titles[title.group(1)] != canon.group(1):
            err(f"{url}: título repetido con la página {titles[title.group(1)]}")
        elif canon:
            titles[title.group(1)] = canon.group(1)
        if not desc or not html_lib.unescape(desc.group(1)).strip():
            err(f"{url}: meta description vacía")
        if not canon or not canon.group(1).startswith(legal.SITE_URL + "/"):
            err(f"{url}: falta la canónica absoluta")
        if not all(f'<link rel="alternate" hreflang="{code}" href="{legal.SITE_URL}/' in html for code in ("es", "en", "x-default")):
            err(f"{url}: faltan los hreflang es, en y x-default")
        text = visible_text(html)
        if len(text) < MIN_VISIBLE_CHARS or NO_JS_PHRASES.search(text):
            err(f"{url}: sin texto propio fuera de JavaScript ({len(text)} caracteres)")
        # la línea de fecha y commit sale solo bajo el título de la portada y de Método
        lang = "en" if url.startswith(base + "en/") else "es"
        fresh_pages = {base, f"{base}en/", f"{base}metodo.html", f"{base}en/metodo.html"}
        if url in fresh_pages and (FRESH_LINE[lang] not in text or f"({legal.UPDATED_COMMIT})" not in text):
            err(f"{url}: falta la línea «{FRESH_LINE[lang]} …»")
    for lang in ("", "en/"):
        html = body_by_url.get(f"{base}{lang}", "")
        ld = [json.loads(m.replace("<\\/", "</")) for m in LD_RE.findall(html)]
        types = {n["@type"] for d in ld for n in d.get("@graph", [d])}
        if not {"WebSite", "Dataset"} <= types:
            err(f"{base}{lang}: JSON-LD de la portada incompleto ({sorted(types)})")
    for url, html in pages.items():
        if re.search(r"/pokemon/\d+-[a-z0-9-]+/$", url):
            ld = [json.loads(m.replace("<\\/", "</")) for m in LD_RE.findall(html)]
            faq = next((d for d in ld if d.get("@type") == "FAQPage"), None)
            if not faq or not faq.get("dateModified") or not faq.get("mainEntity"):
                err(f"{url}: falta el FAQPage con dateModified")
            tier = re.search(r"\btier [SABCD]\b|\b[SABCD] tier\b", html_lib.unescape(re.search(r"<title>([^<]+)</title>", html).group(1)))
            if not tier:
                err(f"{url}: el título no lleva el tier")
    notes.append(f"SEO: {len(pages)} páginas con título, descripción, canónica, hreflang, texto y actualización")


STEEL_NOTE_RE = re.compile(r'<p class="tier-note" data-steel="(\d+)" data-n="(\d+)" data-meteor="(\d+)"')


def steel_note_check(base: str, body_by_url: dict[str, str], index: list[dict], meta: dict, pairs: dict, err,
                     notes: list[str]) -> None:
    """La nota de tier S y la pregunta de Método (build/tier_s_note.py) dicen las cifras que enseña la tier list: los
    Acero y las builds con Puño Meteoro se recuentan aquí desde pokemon-index.json y species.json, y sin la condición
    de la nota no aparece ni la nota ni la pregunta."""
    ts = meta["tierS"]
    top = [p for p in index if p["r"][1] == "S"]
    steel = sum("steel" in p["types"] for p in top)
    meteor = 0
    for p in top:
        pair = pairs[str(p["dex"])]
        meteor += "meteor-mash" in pair[pair["best"]]["moves"]
    want = (steel, len(top), meteor)
    if want != (ts["steel"], ts["n"], ts["meteor"]):
        err(f"meta.json tierS {(ts['steel'], ts['n'], ts['meteor'])} ≠ recuento de la tier list {want}")
    for lang in ("", "en/"):
        html = body_by_url.get(f"{base}{lang}", "")
        found = [tuple(map(int, m)) for m in STEEL_NOTE_RE.findall(html)]
        if not ts["show"]:
            if found:
                err(f"{base}{lang}: sale la nota de tier S y la condición no se cumple")
            continue
        if found != [want, want]:
            err(f"{base}{lang}: la nota de tier S dice {found}, la tier list {want} (sección y plantilla)")
        method = body_by_url.get(f"{base}{lang}metodo.html", "")
        if method.count('<h3 id="acero">') != 1:
            err(f"{base}{lang}metodo.html: falta la pregunta sobre el Acero")
    if not ts["show"]:
        return
    notes.append(f"tier S: {steel} de {len(top)} Acero, {meteor} con Puño Meteoro (nota y método de acuerdo)")


def landing_check(base: str, body_by_url: dict[str, str], err, notes: list[str]) -> None:
    """Páginas de consulta: la lista visible es la del JSON-LD (mismos nombres y orden), la respuesta va antes de la
    lista, la línea de datos está, y cada ficha enlaza la tier list y sus listas de consulta."""
    checked = 0
    for lang in (ES, EN):
        for page in landing.pages():
            url = base + ("en/" if lang.en else "") + landing.folder(lang, page)
            html = body_by_url.get(url)
            if html is None:
                err(f"{url}: no se alcanza desde la portada")
                continue
            checked += 1
            ld = LD_RE.search(html)
            items = json.loads(ld.group(1).replace("<\\/", "</"))["mainEntity"]["itemListElement"] if ld else None
            if not items:
                err(f"{url}: falta el ItemList en JSON-LD")
                continue
            if page.key == "passives":
                visible = re.findall(r'<span class="ql-name">(.*?)</span>', html)
            else:
                visible = re.findall(r'<span class="nm">(.*?)</span>', html)
            if [html_lib.unescape(v) for v in visible] != [i["name"] for i in items]:
                err(f"{url}: la lista visible no coincide con el ItemList del JSON-LD")
            if html.index('<p class="ql-lede">') > html.index('<section class="ql-list"'):
                err(f"{url}: la respuesta no va antes de la lista")
            if f"({legal.UPDATED_COMMIT})" not in html:
                err(f"{url}: falta la línea de datos del juego")
            if page.key != "passives" and not re.search(r'<p class="ql-lede">[^<]*' + re.escape(html_lib.unescape(items[0]["name"])), html):
                err(f"{url}: la primera línea no nombra al primero de la lista")
    fichas = [(u, h) for u, h in body_by_url.items() if re.search(r"/pokemon/\d+-[a-z0-9-]+/$", u)]
    for url, html in fichas:
        if 'href="../../index.html"' not in html and 'href="../../en/index.html"' not in html and 'class="ql-guides"' not in html:
            err(f"{url}: la ficha no enlaza la tier list ni las listas de consulta")
    notes.append(f"páginas de consulta comprobadas: {checked}; fichas con enlaces a listas: {len(fichas)}")


def landing_browser_check(base: str, err, notes: list[str]) -> None:
    """Páginas de consulta a 390 px: sin desbordamiento horizontal y con la lista dibujada."""
    if sync_playwright is None:
        return
    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        if browser is None:
            return
        page = browser.new_page(viewport={"width": 390, "height": 800})
        n = 0
        for lang in ("", "en/"):
            for lp in landing.pages():
                url = base + lang + landing.folder(EN if lang else ES, lp)
                page.goto(url, wait_until="domcontentloaded")
                wide = page.evaluate("() => document.documentElement.scrollWidth > innerWidth + 1")
                drawn = page.evaluate("() => document.querySelectorAll('.ql-grid .mon, .ql-rows li').length")
                if wide:
                    err(f"{url}: se desborda en 390 px de ancho")
                if drawn == 0:
                    err(f"{url}: no hay filas en la lista")
                n += 1
        browser.close()
    notes.append(f"páginas de consulta en 390 px: {n}")


def launch_chromium(pw):
    """Chromium de Playwright, o el Chrome del sistema si no está instalado. None si no hay ninguno."""
    try:
        return pw.chromium.launch()
    except Error:
        exe = which("google-chrome") or which("chromium") or which("chromium-browser")
        if not exe:
            return None
        return pw.chromium.launch(executable_path=exe, args=["--no-sandbox"])


def wait_js(page, js: str, timeout_ms: int) -> None:
    """Espera a que la función js (sin argumentos) devuelva true. No usa page.wait_for_function: Playwright evalúa
    sus cadenas con eval, y la CSP de producción (script-src 'self', sin unsafe-eval) lo bloquea. page.evaluate sí."""
    deadline = time.monotonic() + timeout_ms / 1000
    while not page.evaluate(js):
        if time.monotonic() > deadline:
            raise TimeoutError(f"no se cumple: {js[:60]}")
        page.wait_for_timeout(100)


def browser_check(base: str, index: list[dict], args, err, notes: list[str]) -> None:
    """Dibuja la ficha de cada Pokémon en un navegador de verdad: las dos builds, por qué, supervivencia y stats, el
    sprite cargado, el nombre correcto y ningún error de consola. También prueba que un enlace viejo acaba en la ficha."""
    if sync_playwright is None:
        notes.append("fichas en el navegador: omitido (pip install playwright)")
        return
    by_dex = {p["dex"]: p for p in index}
    dexes = sorted(by_dex)
    rng = random.Random(7)
    sample = dexes if args.all_species else sorted(set(rng.sample(dexes, min(args.species, len(dexes)))) | {dexes[0], dexes[-1]} | ({94, 354} & set(dexes)))
    pairs = json.loads(fetch(base + "data/species.json")[1])["builds"]
    drawn = 0
    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        if browser is None:
            notes.append("fichas en el navegador: omitido (no hay Chromium)")
            return
        page = browser.new_page(viewport={"width": 390, "height": 800})
        problems: list[str] = []
        # el beacon de Cloudflare Web Analytics solo acepta hosts registrados: en local (127.0.0.1) su petición se bloquea
        # por CORS, y eso no es un error de la ficha. Los demás errores de consola sí cuentan.
        page.on("console", lambda m: problems.append(m.text)
                if m.type == "error" and "cloudflareinsights" not in m.text and "ERR_FAILED" not in m.text else None)
        page.on("pageerror", lambda e: problems.append(str(e)))
        for lang in LANGS:
            en = lang == "en/"
            for d in sample:
                problems.clear()
                page.goto(f"{base}{lang}pokemon/?id={d}", wait_until="domcontentloaded")
                try:
                    page.wait_for_url(re.compile(rf"/pokemon/{d}-[^/?#]+/?$"), timeout=15000)
                    wait_js(page, "() => document.querySelectorAll('#build .bd-opt').length === 2", 15000)
                    wait_js(page, "() => { const i = document.querySelector('.ficha-sprite img'); return !!i && i.complete; }", 15000)
                except (Error, TimeoutError):
                    err(f"{lang}pokemon/?id={d}: la ficha no se dibuja")
                    continue
                info = page.evaluate("""() => ({
                    h1: document.querySelector('h1').firstChild.textContent.trim(),
                    img: document.querySelector('.ficha-sprite img').naturalWidth,
                    src: document.querySelector('.ficha-sprite img').src,
                    kinds: [...document.querySelectorAll('#build .bd-opt')].map(e => e.dataset.build),
                    best: [...document.querySelectorAll('#build .bd-opt.is-best')].map(e => e.dataset.build),
                    starts: [...document.querySelectorAll('#build .bd-opt')].map(o => [...o.querySelectorAll(':scope > .bd-rows > .bd-row')].map(r => r.classList.contains('is-start'))),
                    stats: document.querySelectorAll('#build .bd-opt .bd-stats dd').length,
                    why: document.querySelectorAll('#porque .why-row, #porque .why-flat').length,
                    surv: !!document.querySelector('#supervivencia .surv-bar'),
                    icons: [...document.querySelectorAll('#build .bd-ico img')].every(i => i.complete && i.naturalWidth > 0) && document.querySelectorAll('#build .bd-ico img').length >= 4,
                    statRows: document.querySelectorAll('#stats li').length,
                    overflow: [...document.querySelectorAll('#ficha, #ficha *')].some(e => e.getBoundingClientRect().right > innerWidth + 1),
                    base: new URL(document.documentElement.dataset.sprites, location.href).href,
                    ext: document.documentElement.dataset.spritesExt || '.png' })""")
                want = by_dex[d]["nameEn" if en else "name"]
                if info["h1"] != want:
                    err(f"{lang}pokemon/?id={d}: el título es {info['h1']!r} y debería ser {want!r}")
                pair = pairs.get(str(d), {})
                if info["kinds"][:1] != [pair.get("best")] or sorted(info["kinds"]) != ["melee", "ranged"] \
                        or info["best"] != [pair.get("best")]:
                    err(f"{lang}pokemon/?id={d}: las builds no son las dos de species.json con la mejor primero ({info})")
                if any(r[:1] != [True] or any(r[1:]) or not 2 <= len(r) <= 4 for r in info["starts"]) or info["stats"] != 8:
                    err(f"{lang}pokemon/?id={d}: cada build debe tener 2 a 4 ataques, el primero marcado, y sus cuatro cifras ({info})")
                if not info["icons"]:
                    err(f"{lang}pokemon/?id={d}: los iconos de los ataques no cargan ({info})")
                if not info["why"] or not info["surv"] or not info["statRows"]:
                    err(f"{lang}pokemon/?id={d}: faltan por qué, supervivencia o stats ({info})")
                if info["overflow"]:
                    err(f"{lang}pokemon/?id={d}: la ficha se desborda en 390 px de ancho")
                if info["src"] != f"{info['base']}{d}{info['ext']}" or info["img"] == 0:
                    err(f"{lang}pokemon/?id={d}: el sprite no carga ({info['src']})")
                if problems:
                    err(f"{lang}pokemon/?id={d}: errores en el navegador: {problems[:2]}")
                drawn += 1
            page.goto(f"{base}{lang}pokemon/?id=99999")
            page.wait_for_selector("h1", timeout=8000)
            if page.locator("#build").count():
                err(f"{lang}pokemon/?id=99999 debería decir que no existe")
            page.goto(f"{base}{lang}pokemon/25.html", wait_until="domcontentloaded")
            try:
                page.wait_for_url(re.compile(r"/pokemon/25-pikachu/?$"), timeout=15000)
                wait_js(page, "() => document.querySelectorAll('#build .bd-opt').length === 2", 15000)
            except (Error, TimeoutError):
                err(f"{lang}pokemon/25.html no acaba en la ficha de Pikachu")
            else:
                if not page.url.rstrip("/").endswith(f"{lang}pokemon/25-pikachu"):
                    err(f"{lang}pokemon/25.html acaba en {page.url}")
        browser.close()
    notes.append(f"fichas dibujadas en el navegador: {drawn} de {2 * len(dexes)}")


THEME_LIGHT, THEME_DARK = theme.THEME_COLOR["light"], theme.THEME_COLOR["dark"]
PNG_OK = ("og.png", "apple-touch-icon.png")
THEME_PAGES = ("", "novedades.html", "coleccion.html", "pokemon/25-pikachu/", "metodo.html", "ataques.html", "pasivas.html", "en/", "en/novedades.html", "en/pokemon/25-pikachu/", "en/coleccion.html", "en/pasivas.html")
THEME_STATE_JS = """() => ({
    theme: document.documentElement.dataset.theme || null,
    bg: getComputedStyle(document.documentElement).getPropertyValue('--bg').trim(),
    meta: document.getElementById('theme-color').content,
    label: document.getElementById('theme').getAttribute('aria-label') })"""


def theme_check(base: str, err, notes: list[str]) -> None:
    """Botón de tema en cada página: cambia el fondo, la barra del navegador y la etiqueta; recuerda la elección tras
    recargar; sin elección sigue al sistema, también cuando cambia con la página abierta; y el gráfico de la portada
    y de métodos se repinta al cambiar."""
    if sync_playwright is None:
        return
    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        if browser is None:
            return
        problems: list[str] = []

        def watch(page) -> None:
            page.on("pageerror", lambda e: problems.append(str(e)))
            page.on("console", lambda m: problems.append(m.text)
                    if m.type == "error" and "cloudflareinsights" not in m.text and "ERR_FAILED" not in m.text else None)

        def expect(page, where: str, theme_value, bg: str) -> dict:
            st = page.evaluate(THEME_STATE_JS)
            if st["theme"] != theme_value or st["bg"] != bg or st["meta"] != bg or not st["label"]:
                err(f"tema en {where}: {st} (se esperaba data-theme={theme_value!r} y fondo {bg})")
            return st

        try:
            ctx = browser.new_context(viewport={"width": 390, "height": 800}, color_scheme="light")
            page = ctx.new_page()
            watch(page)
            page.goto(base + "coleccion.html")
            page.wait_for_selector("#theme:not([hidden])", timeout=8000)
            first = expect(page, "coleccion (sistema claro)", None, THEME_LIGHT)
            page.click("#theme")
            dark = expect(page, "coleccion tras pulsar", "dark", THEME_DARK)
            if dark["label"] == first["label"]:
                err("el botón de tema no cambia su etiqueta al cambiar de tema")
            page.reload()
            page.wait_for_selector("#theme:not([hidden])", timeout=8000)
            expect(page, "coleccion tras recargar (oscuro guardado)", "dark", THEME_DARK)
            page.click("#theme")
            expect(page, "coleccion vuelta a claro", "light", THEME_LIGHT)
            page.reload()
            page.wait_for_selector("#theme:not([hidden])", timeout=8000)
            expect(page, "coleccion recargada (claro guardado)", "light", THEME_LIGHT)
            for path in THEME_PAGES:
                page.goto(base + path)
                page.wait_for_selector("#theme:not([hidden])", timeout=8000)
                expect(page, path or "portada", "light", THEME_LIGHT)
                page.click("#theme")
                expect(page, f"{path or 'portada'} en oscuro", "dark", THEME_DARK)
                page.click("#theme")
                expect(page, f"{path or 'portada'} en claro", "light", THEME_LIGHT)
            ctx.close()

            ctx = browser.new_context(viewport={"width": 390, "height": 800}, color_scheme="dark")
            page = ctx.new_page()
            watch(page)
            page.goto(base + "coleccion.html")
            page.wait_for_selector("#theme:not([hidden])", timeout=8000)
            expect(page, "coleccion (sistema oscuro)", None, THEME_DARK)
            page.emulate_media(color_scheme="light")
            wait_js(page, f"() => document.getElementById('theme-color').content === '{THEME_LIGHT}' && "
                          "document.getElementById('theme').getAttribute('aria-label') === 'Cambiar a modo oscuro'", 4000)
            expect(page, "coleccion (el sistema pasa a claro)", None, THEME_LIGHT)
            ctx.close()

        except (Error, TimeoutError) as e:
            err(f"comprobación de tema: {str(e).splitlines()[0]}")
        browser.close()
    if problems:
        err(f"errores en el navegador al cambiar de tema: {problems[:2]}")
    notes.append(f"tema: botón comprobado en {len(THEME_PAGES)} páginas, en claro, en oscuro y siguiendo al sistema")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--external", action="store_true", help="comprueba también los enlaces externos (red)")
    ap.add_argument("--build-dir", type=Path, default=ROOT / "build" / "out", help="datos de build/catalog.py")
    ap.add_argument("--species", type=int, default=60, help="fichas por idioma que se dibujan en el navegador")
    ap.add_argument("--all-species", action="store_true", help="dibuja las 966 fichas de cada idioma (lento)")
    args = ap.parse_args()
    base = args.base if args.base.endswith("/") else args.base + "/"
    origin = urlparse(base).netloc
    errors: list[str] = []
    notes: list[str] = []

    def err(msg: str) -> None:
        errors.append(msg)

    for name in theme.csp_missing(ROOT):
        err(f"{name}: la CSP no lleva la huella {theme.csp_hash()} del script de tema (build/theme.py)")
    status, body = fetch(base + "data/pokemon-index.json")
    if status != 200:
        print(f"ERROR: no se puede leer {base}data/pokemon-index.json ({status})")
        return 1
    index = json.loads(body)
    try:
        meta = json.loads((args.build_dir / "meta.json").read_text(encoding="utf8"))
        gachas = json.loads((args.build_dir / "gachas.json").read_text(encoding="utf8"))
    except OSError as e:
        print(f"ERROR: faltan los datos de build ({e}). Ejecuta antes python3 build/catalog.py")
        return 1
    dexes = sorted(p["dex"] for p in index)
    if len(dexes) != 966:
        err(f"el índice tiene {len(dexes)} Pokémon, no 966")

    # conteos y gacha
    c = Counter(p["r"][1] for p in index)
    if dict(c) != EXPECTED_COUNTS:
        err(f"conteos por tier: {dict(c)}")
    notes.append(f"ranking {meta['version']}: " + ", ".join(f"{t} {c[t]}" for t in "SABCD"))
    for g in gachas:
        want = EXPECTED_GACHA[g["name"]]
        if abs(g["sPlusARate"] - want) > 0.05:
            err(f"gacha {g['name']}: {g['sPlusARate']} ≠ {want}")
    if sum(g["poolSize"] for g in gachas) != 966:
        err("los pools de gacha no suman 966")

    # sprites: no viajan en site/. Salen de data-sprites, que debe ser el sitio mismo o el CDN del repositorio.
    sprites_dir = ROOT / "sprites"
    missing_files = [d for d in dexes if not (sprites_dir / f"{d}.png").exists()]
    if missing_files:
        err(f"faltan en sprites/: {missing_files[:10]}")
    try:
        pairs = json.loads(fetch(base + "data/species.json")[1])["builds"]
        moves = json.loads(fetch(base + "data/moves.json")[1])
        unranked = json.loads(fetch(base + "data/moves_unranked.json")[1])
    except (ValueError, KeyError):
        err("data/species.json, data/moves.json o data/moves_unranked.json no se pueden leer")
        pairs, moves, unranked = {}, [], []
    move_ids = {m["id"] for m in moves} | {m["id"] for m in unranked}
    # species.json: las dos builds de la fase 3 (build/species_builds.py) y cuál puntúa más
    for d in dexes:
        pair = pairs.get(str(d))
        ok = isinstance(pair, dict) and pair.get("best") in ("melee", "ranged") and all(
            isinstance(pair.get(k), dict) and 2 <= len(pair[k]["moves"]) <= 4 and all(m in move_ids for m in pair[k]["moves"])
            and len(set(pair[k]["moves"])) == len(pair[k]["moves"]) and pair[k]["nBoost"] in (0, 1, 2)
            and pair[k]["time"] > 0 and pair[k]["lo"] <= pair[k]["score"] <= pair[k]["hi"]
            for k in ("melee", "ranged"))
        if ok and pair["melee"]["score"] != pair["ranged"]["score"]:
            ok = pair[pair["best"]]["score"] == max(pair["melee"]["score"], pair["ranged"]["score"])
        if not ok:
            err(f"data/species.json: builds incompletas o raras para el Pokémon {d}")

    # side: phys / spec / mix según los ataques de la mejor build
    side_of = {"physical": "phys", "special": "spec", "mixed": "mix"}
    for p in index:
        pair = pairs.get(str(p["dex"]))
        if not isinstance(pair, dict) or pair.get("best") not in pair:
            continue
        if p.get("side") != side_of.get(pair[pair["best"]]["mix"]):
            err(f"pokemon-index {p['dex']}: side {p.get('side')} no sale de la mejor build ({pair[pair['best']]['mix']})")

    # rastreo
    start = [f"{base}{lang}{p}" for lang in LANGS
             for p in ("", "novedades.html", "metodo.html", "ataques.html", "objetos.html", "pasivas.html", "gachas.html", "coleccion.html", "acerca.html",
                       "pokemon/")]
    start.append(base + "404.html")
    seen: dict[str, Page | None] = {}
    queue = deque(start)
    external: dict[str, str] = {}
    body_by_url: dict[str, str] = {}
    sprite_bases: set[str] = set()
    sprite_refs: set[str] = set()
    ficha_ids: dict[str, set[int]] = {lang: set() for lang in LANGS}
    names = {p["dex"]: (p["name"], p["nameEn"]) for p in index}

    def is_page(u: str) -> bool:
        return u.endswith(".html") or u.endswith("/")

    while queue:
        url = queue.popleft()
        if url in seen:
            continue
        status, body = fetch(url)
        if status != 200:
            err(f"{url} → {status}")
            seen[url] = None
            continue
        if not is_page(url):
            seen[url] = None
            continue
        page = Page()
        page.feed(body.decode("utf8"))
        body_by_url[url] = body.decode("utf8")
        seen[url] = page
        text = " ".join(page.text)
        if re.search(r"\bv[34]\b|fórmula v", text, re.I):
            err(f"{url}: menciona una fórmula interna (v3/v4)")
        english = url.startswith(base + "en/")
        # el aviso de fan no oficial vive en Info (acerca), no en el pie de cada página
        if url.endswith("acerca.html"):
            notice = ("unofficial", "not affiliated") if english else ("no oficial", "no afiliado")
            if not all(n in text.lower() for n in notice):
                err(f"{url}: falta el aviso de fan no oficial")
        lang = re.search(r'<html lang="(\w+)"', body_by_url[url])
        if not lang or lang.group(1) != ("en" if english else "es"):
            err(f"{url}: atributo lang incorrecto")
        if page.sprites:
            sprite_bases.add(urljoin(url, page.sprites))
        if english:
            visible = re.sub(r'<ul class="credits-list">.*?</ul>', "",
                             body_by_url[url], flags=re.S)
            visible = " ".join(re.sub(r"<[^>]+>", " ", visible).split())
            leak = SPANISH_WORDS.findall(visible)
            if leak:
                err(f"{url}: español en la página en inglés ({', '.join(sorted(set(w.lower() for w in leak)))})")
        for href in page.links + page.assets:
            full = urljoin(url, href)
            parts = urlparse(full)
            if parts.scheme not in ("http", "https"):
                if not full.startswith("data:"):
                    err(f"{url}: esquema raro {href[:40]}")
                continue
            if page.sprites and full.startswith(urljoin(url, page.sprites)) and href in page.assets:
                sprite_refs.add(full)
                continue
            if parts.netloc != origin:
                # el único recurso externo permitido en la página es el beacon de Web Analytics (sin cookies, CSP lo fija)
                if href in page.assets and full != BEACON_URL:
                    err(f"{url}: carga un recurso externo {full}")
                external.setdefault(full, url)
                continue
            lang_of = LANGS[1] if parts.path.startswith("/en/") else LANGS[0]
            static_ficha = re.search(r"/pokemon/(\d+)-[a-z0-9-]+/?$", parts.path)
            if static_ficha:
                ficha_ids[lang_of].add(int(static_ficha.group(1)))
            elif parts.path.endswith("/pokemon/") and parts.query:
                ids = parse_qs(parts.query).get("id", [])
                if len(ids) == 1 and ids[0].isdigit():
                    ficha_ids[lang_of].add(int(ids[0]))
                else:
                    err(f"{url}: enlace de ficha raro {href}")
                full = full.split("?", 1)[0]
            target = urldefrag(full)[0]
            if target not in seen and target not in queue and href in page.links and is_page(target):
                queue.append(target)
            elif target not in seen and href in page.assets:
                queue.append(target)
        for img in page.imgs:
            if not img.get("src"):
                err(f"{url}: imagen sin src")
        ficha = re.search(r"/pokemon/(\d+)-[a-z0-9-]+/?$", urlparse(url).path)
        if ficha and int(ficha.group(1)) in names:
            dex = int(ficha.group(1))
            want = names[dex][1 if english else 0]
            h1 = re.search(r"<h1>(.*?)<small", body_by_url[url], re.S)
            got = html_lib.unescape(h1.group(1)).strip() if h1 else None
            if got != want:
                err(f"{url}: el título es {got!r} y debería ser {want!r}")
            if not any(want in (i.get("alt") or "") for i in page.imgs if i.get("class") == "px"):
                err(f"{url}: el texto alternativo del sprite no nombra a {want!r}")

    # anclas
    for url, page in list(seen.items()):
        if page is None:
            continue
        for href in page.links:
            full = urljoin(url, href)
            target, frag = urldefrag(full)
            target = target.split("?", 1)[0]
            if urlparse(full).netloc == origin and frag and target in seen and seen[target] is not None:
                if frag not in seen[target].ids:
                    err(f"{url}: ancla rota {href}")

    # sprites, enlaces a fichas y plantilla de ficha
    if len(sprite_bases) != 1:
        err(f"las páginas no coinciden en data-sprites: {sorted(sprite_bases)}")
    else:
        sprite_base = next(iter(sprite_bases))
        if not (sprite_base.startswith(SPRITE_CDN_PREFIX) or urlparse(sprite_base).netloc == origin):
            err(f"data-sprites apunta a un origen no permitido: {sprite_base}")
        if not sprite_base.endswith("/sprites/") and "/_sprites/" not in sprite_base:
            err(f"data-sprites no termina en /sprites/: {sprite_base}")
        if urlparse(sprite_base).netloc != origin:
            host = f"{urlparse(sprite_base).scheme}://{urlparse(sprite_base).netloc}"
            for name, text in (("src/_headers", (ROOT / "src" / "_headers").read_text(encoding="utf8")),
                               ("vercel.json", (ROOT / "vercel.json").read_text(encoding="utf8"))):
                img_src = re.search(r"img-src([^;\"]*)", text)
                if not img_src or host not in img_src.group(1):
                    err(f"{name}: la CSP no permite imágenes de {host}")
        alts = {m for t in body_by_url.values() for m in re.findall(r'data-sprites-alt="([^"]*)"', t)}
        if len(alts) != 1:
            err(f"las páginas no coinciden en data-sprites-alt: {sorted(alts)}")
        alt = next(iter(alts), "")
        if alt:
            if not alt.startswith("https://raw.githubusercontent.com/felipebasurto/survivortiers/") or not alt.endswith("/sprites/"):
                err(f"data-sprites-alt raro: {alt}")
            for name, text in (("src/_headers", (ROOT / "src" / "_headers").read_text(encoding="utf8")),
                               ("vercel.json", (ROOT / "vercel.json").read_text(encoding="utf8"))):
                img_src = re.search(r"img-src([^;\"]*)", text)
                if not img_src or "https://raw.githubusercontent.com" not in img_src.group(1):
                    err(f"{name}: la CSP no permite imágenes de raw.githubusercontent.com (respaldo de sprites)")
        elif urlparse(sprite_base).netloc != origin:
            err("hay CDN de sprites pero no respaldo (data-sprites-alt vacío)")
        wrong = [u for u in sprite_refs if not re.fullmatch(re.escape(sprite_base) + r"\d+\.(png|webp)", u)]
        if wrong:
            err(f"sprites con una URL rara: {wrong[:3]}")
        gone = {int(u[len(sprite_base):].split(".")[0]) for u in sprite_refs if u not in wrong} - set(dexes)
        if gone:
            err(f"sprites de Pokémon que no existen: {sorted(gone)[:5]}")
        if len(sprite_refs) != 966:
            err(f"las páginas enlazan {len(sprite_refs)} sprites distintos, se esperaban 966")
    for lang in LANGS:
        if ficha_ids[lang] != set(dexes):
            err(f"{lang or 'es'}: la tier list no enlaza a las 966 fichas "
                f"(faltan {sorted(set(dexes) - ficha_ids[lang])[:5]}, sobran {sorted(ficha_ids[lang] - set(dexes))[:5]})")
        tpl = body_by_url.get(f"{base}{lang}pokemon/", "")
        if not (tpl.count('id="ficha"') == 1 and 'id="slugs"' in tpl):
            err(f"{lang}pokemon/: falta algo de la plantilla de ficha")
        if f'<link rel="canonical" href="{legal.SITE_URL}/{lang}">' not in tpl:
            err(f"{lang}pokemon/: la canónica de la plantilla debe ser la portada del idioma")
        if tpl.count('<ol class="slug-list">') != 1 or len(re.findall(r'<li><a href="[^"]*pokemon/\d+-', tpl)) != len(dexes):
            err(f"{lang}pokemon/: la plantilla no lista las {len(dexes)} fichas en HTML")
    for lang, labels in (("", ("Todos", "Físico", "Especial", "Mixto")), ("en/", ("All", "Physical", "Special", "Mixed"))):
        home = body_by_url.get(f"{base}{lang}", "")
        if 'class="side-filter"' not in home or any(f">{label}<" not in home for label in labels):
            err(f"{lang or 'es'}: la tier list no tiene el filtro de ataque ({labels})")

    # enlaces viejos: /pokemon/<n>.html cae en la 404, que los reenvía a la ficha
    for lang in LANGS:
        status, body = fetch(f"{base}{lang}pokemon/25.html")
        if status != 404 or b'data-page="404"' not in body:
            err(f"{lang}pokemon/25.html debería caer en 404.html con estado 404 (da {status}); sirve site/ con build/serve.py")
    app_js = fetch(base + "app.js")[1].decode("utf8", "replace")
    if "location.replace" not in app_js or "pokemon" not in app_js:
        err("app.js no reenvía los enlaces viejos de fichas")
    if "sideFilter" not in app_js:
        err("app.js no aplica el filtro de ataque")

    # créditos: cada Pokémon tiene artista y todos los artistas salen en Acerca
    credited = {d for cr in meta["credits"] for d in cr["dex"]}
    if credited != set(dexes):
        err(f"créditos de sprites: faltan {sorted(set(dexes) - credited)[:5]}, sobran {sorted(credited - set(dexes))[:5]}")
    if any(not cr["name"].strip() for cr in meta["credits"]):
        err("hay un artista sin nombre en los créditos")
    for lang in LANGS:
        about = body_by_url.get(f"{base}{lang}acerca.html", "")
        listed = re.search(r'<ul class="credits-list">(.*?)</ul>', about, flags=re.S)
        n = listed.group(1).count("<li>") if listed else 0
        if n != len(meta["credits"]):
            err(f"{lang}acerca.html: salen {n} artistas y hay {len(meta['credits'])} en los créditos")
        if "CC BY-NC" not in about or "SpriteCollab" not in about:
            err(f"{lang}acerca.html: falta la licencia o la fuente de los sprites")

    # presupuesto de site/
    site_dir = ROOT / "site"
    if site_dir.exists():
        files = [f for f in site_dir.rglob("*") if f.is_file()]
        total = sum(f.stat().st_size for f in files)
        notes.append(f"site/: {len(files)} archivos, {total / 1e6:.2f} MB")
        if len(files) > MAX_FILES or total > MAX_BYTES:
            err(f"site/ se pasa del presupuesto ({len(files)} archivos, {total / 1e6:.1f} MB; máximo {MAX_FILES} y {MAX_BYTES / 1e6:.0f} MB)")
        if any(f.suffix == ".png" and f.name not in PNG_OK for f in files):
            err("site/ lleva PNG: los sprites tienen que salir del CDN (og.png y apple-touch-icon.png son la excepción)")

    # ataques: barras en cada ataque y nada de jerga sin explicar
    rows_expected = len(moves)  # una barra por ataque; los potenciadores no tienen puesto ni barra
    for lang in LANGS:
        url = f"{base}{lang}ataques.html"
        html = body_by_url.get(url, "")
        rows = html.count('class="mb-row"')
        if rows != rows_expected:
            err(f"{url}: {rows} barras, se esperaban {rows_expected}")
        if re.search(r"al minuto \d|at minute \d", html):
            err(f"{url}: queda jerga sin explicar")

    # créditos de sprites solo en Acerca
    for lang in LANGS:
        about = body_by_url.get(f"{base}{lang}acerca.html", "")
        if about.count('class="credits-list"') != 1 or about.count("<li><a") < 5:
            err(f"{lang}acerca.html: faltan los créditos de los artistas")
        for url, text in body_by_url.items():
            if url.startswith(base + lang) and not url.endswith("acerca.html") and 'class="credits-list"' in text:
                err(f"{url}: los créditos de artistas solo van en Acerca")
    notes.append(f"páginas rastreadas: {sum(1 for p in seen.values() if p)}; sprites enlazados: {len(sprite_refs)}")
    agent_check(base, body_by_url, err, notes, len(index))
    landing_check(base, body_by_url, err, notes)
    seo_check(base, body_by_url, index, err, notes)
    steel_note_check(base, body_by_url, index, meta, pairs, err, notes)
    landing_browser_check(base, err, notes)
    browser_check(base, index, args, err, notes)
    theme_check(base, err, notes)

    if args.external:
        bad_ext = []
        unique = {urldefrag(u)[0]: src for u, src in external.items()}
        for url in sorted(unique):
            code, _ = fetch(url, "GET")
            if code == 403:
                notes.append(f"aviso: {url} responde 403 (bloqueo anti-bots probable), revisar a mano")
            elif code != 200:
                bad_ext.append((url, code, unique[url]))
        notes.append(f"enlaces externos distintos (sin ancla): {len(unique)}; rotos: {len(bad_ext)}")
        for url, code, src in bad_ext:
            err(f"externo roto ({code}): {url}  (en {src})")
    else:
        notes.append(f"enlaces externos distintos (no comprobados): {len(external)}")

    print("\n".join(notes))
    if errors:
        print(f"\n{len(errors)} ERRORES:")
        for e in errors[:60]:
            print(" -", e)
        return 1
    print("\nTodo correcto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
