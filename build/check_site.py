"""Comprobaciones de aceptación sobre un sitio ya servido (local o desplegado).

    python3 build/check_site.py http://localhost:8765/
    python3 build/check_site.py https://mi-proyecto.vercel.app/ --external

Comprueba, en español y en inglés: enlaces internos y anclas sin romper, aviso legal en cada página, conteos por
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
import json
import re
import sys
import time
from collections import Counter, deque
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from pathlib import Path
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

import agents  # noqa: E402
import legal  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "SurvivorTiers-check/1.0"}
SPRITE_CDN_PREFIX = "https://cdn.jsdelivr.net/gh/felipebasurto/survivortiers@"
MAX_FILES, MAX_BYTES = 50, 5_000_000  # presupuesto de site/ para el despliegue
EXPECTED_COUNTS = {"S": 30, "A": 90, "B": 200, "C": 300, "D": 346}
SPANISH_WORDS = re.compile(r"\b(el|los|las|del|con|para|puesto|aguante|daño|ficha|partidas?|repeticiones|cuántos)\b", re.I)
LANGS = ("", "en/")
EXPECTED_GACHA = {"Paldea": 19.6, "Alola": 18.1, "Galar": 16.1, "Sinnoh": 15.0, "Kanto": 11.3, "Teselia": 10.6,
                  "Johto": 10.0, "Kalos": 10.0, "Hoenn": 5.9}


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


def agent_check(base: str, body_by_url: dict[str, str], err, notes: list[str]) -> None:
    """Archivos para agentes (build/agents.py): robots.txt, llms.txt y llms-full.txt, sitemap, datos descritos, pie y
    JSON-LD de la portada. Los enlaces absolutos de llms.txt apuntan a legal.SITE_URL; aquí se piden a este servidor."""
    site_url = legal.SITE_URL
    root = base.rstrip("/")

    def local(url: str) -> str:
        return root + url[len(site_url):] if url.startswith(site_url) else url

    code, body = fetch(base + "robots.txt")
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

    # sitemap: una entrada por página y por idioma
    expected = len(agents.PAGES) * len(agents.LANG_PREFIX)
    sitemap = fetch(base + "sitemap.xml")[1].decode("utf8", "replace")
    if sitemap.count("<url>") != expected:
        err(f"sitemap.xml: {sitemap.count('<url>')} entradas, se esperaban {expected}")

    # cada página lleva los enlaces para agentes en el pie, y la portada el JSON-LD Dataset
    for url, html in body_by_url.items():
        if url.startswith(base) and html and 'class="agents"' not in html:
            err(f"{url}: falta el pie con los enlaces para agentes")
    # cada página (salvo la 404) lleva la canónica, Open Graph y la tarjeta de Twitter/X con la imagen compartida
    shared = (f'<meta property="og:image" content="{legal.SITE_URL}/og.png">', '<meta name="twitter:card" content="summary_large_image">',
              f'<meta name="twitter:site" content="{legal.X_HANDLE}">')
    for url, html in body_by_url.items():
        if url.startswith(base) and html and not url.endswith("404.html"):
            if '<link rel="canonical" href="' not in html or any(t not in html for t in shared):
                err(f"{url}: faltan las etiquetas para compartir (canónica, Open Graph o Twitter/X)")
    st, png = fetch(base + "og.png")
    if st != 200 or png[:8] != b"\x89PNG\r\n\x1a\n" or int.from_bytes(png[16:20], "big") != 1200 or int.from_bytes(png[20:24], "big") != 630:
        err("og.png no es un PNG de 1200 × 630")
    for lang in ("", "en/"):
        html = body_by_url.get(f"{base}{lang}", "")
        if '"@type": "Dataset"' not in html:
            err(f"{base}{lang}: falta el JSON-LD Dataset")
    notes.append(f"agentes: llms.txt con {len(local_links)} enlaces, sitemap con {expected} entradas")


def wait_js(page, js: str, timeout_ms: int) -> None:
    """Espera a que la función js (sin argumentos) devuelva true. No usa page.wait_for_function: Playwright evalúa
    sus cadenas con eval, y la CSP de producción (script-src 'self', sin unsafe-eval) lo bloquea. page.evaluate sí."""
    deadline = time.monotonic() + timeout_ms / 1000
    while not page.evaluate(js):
        if time.monotonic() > deadline:
            raise TimeoutError(f"no se cumple: {js[:60]}")
        page.wait_for_timeout(100)


def browser_check(base: str, index: list[dict], args, err, notes: list[str]) -> None:
    """Dibuja la ficha de cada Pokémon en un navegador de verdad: 4 gráficos con texto alternativo, el sprite cargado,
    el nombre correcto y ningún error de consola. También prueba que un enlace viejo acaba en la ficha."""
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError:
        notes.append("fichas en el navegador: omitido (pip install playwright)")
        return
    import random
    from shutil import which

    by_dex = {p["dex"]: p for p in index}
    dexes = sorted(by_dex)
    rng = random.Random(7)
    sample = dexes if args.all_species else sorted(set(rng.sample(dexes, min(args.species, len(dexes)))) | {dexes[0], dexes[-1]})
    drawn = 0
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Error:
            exe = which("google-chrome") or which("chromium") or which("chromium-browser")
            if not exe:
                notes.append("fichas en el navegador: omitido (no hay Chromium)")
                return
            browser = pw.chromium.launch(executable_path=exe, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 390, "height": 800})
        problems: list[str] = []
        page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: problems.append(str(e)))
        for lang in LANGS:
            en = lang == "en/"
            for d in sample:
                problems.clear()
                page.goto(f"{base}{lang}pokemon/?id={d}")
                try:
                    wait_js(page, "() => document.querySelectorAll('figure.fig').length === 5", 8000)
                    wait_js(page, "() => { const i = document.querySelector('.ficha-sprite img'); return !!i && i.complete; }", 8000)
                except (Error, TimeoutError):
                    err(f"{lang}pokemon/?id={d}: la ficha no se dibuja")
                    continue
                info = page.evaluate("""() => ({
                    alts: [...document.querySelectorAll('.fig-body[role=img]')].map(e => (e.getAttribute('aria-label') || '').length),
                    h1: document.querySelector('h1').firstChild.textContent.trim(),
                    img: document.querySelector('.ficha-sprite img').naturalWidth,
                    src: document.querySelector('.ficha-sprite img').src,
                    base: new URL(document.documentElement.dataset.sprites, location.href).href,
                    ext: document.documentElement.dataset.spritesExt || '.png' })""")
                want = by_dex[d]["nameEn" if en else "name"]
                if info["h1"] != want:
                    err(f"{lang}pokemon/?id={d}: el título es {info['h1']!r} y debería ser {want!r}")
                if len(info["alts"]) != 5 or min(info["alts"]) < 20:
                    err(f"{lang}pokemon/?id={d}: {len(info['alts'])} gráficos con texto alternativo (se esperaban 5 de 20+ letras)")
                if info["src"] != f"{info['base']}{d}{info['ext']}" or info["img"] == 0:
                    err(f"{lang}pokemon/?id={d}: el sprite no carga ({info['src']})")
                if problems:
                    err(f"{lang}pokemon/?id={d}: errores en el navegador: {problems[:2]}")
                drawn += 1
            page.goto(f"{base}{lang}pokemon/?id=99999")
            page.wait_for_selector("#ficha h1", timeout=8000)
            if page.locator("figure.fig").count():
                err(f"{lang}pokemon/?id=99999 debería decir que no existe")
            page.goto(f"{base}{lang}pokemon/25.html")
            try:
                wait_js(page, "() => document.querySelectorAll('figure.fig').length === 5", 8000)
            except (Error, TimeoutError):
                err(f"{lang}pokemon/25.html no acaba en la ficha de Pikachu")
            else:
                if not page.url.endswith(f"{lang}pokemon/?id=25"):
                    err(f"{lang}pokemon/25.html acaba en {page.url}")
        browser.close()
    notes.append(f"fichas dibujadas en el navegador: {drawn} de {2 * len(dexes)}")


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
        species = json.loads(fetch(base + "data/species.json")[1])["d"]
        moves = json.loads(fetch(base + "data/moves.json")[1])
    except (ValueError, KeyError):
        err("data/species.json o data/moves.json no se pueden leer")
        species, moves = {}, []
    move_ids = {m["id"] for m in moves}
    for d in dexes:
        e = species.get(str(d))
        ok = (isinstance(e, list) and len(e) == 10 and len(e[0]) == 4 and all(0 <= v <= 1 for v in e[0])
              and len(e[1]) == 5 and all(isinstance(v, int) and 1 <= v <= 966 for v in e[1])
              and e[2] in move_ids and e[4] in move_ids and e[3] > 0 and e[5] > 0
              and all(m in move_ids for m in e[6]) and isinstance(e[7], int) and 0 <= e[7] <= 15
              and len(e[8]) == 6 and all(isinstance(v, int) and 1 <= v <= 255 for v in e[8])
              # trío de cobertura: % super efectivo, % no resistido y 2-4 ids de movimientos (build/combos.py)
              and len(e[9]) == 4 and all(isinstance(v, int) and 0 <= v <= 100 for v in e[9][:2])
              and 2 <= len(e[9][2]) <= 4 and all(m in move_ids for m in e[9][2]) and e[9][3] in (1, 2, 3))
        if not ok:
            err(f"data/species.json: datos incompletos o raros para el Pokémon {d}")

    # rastreo
    start = [f"{base}{lang}{p}" for lang in LANGS
             for p in ("", "metodo.html", "ataques.html", "gachas.html", "coleccion.html", "acerca.html",
                       "pokemon/")]
    start.append(base + "404.html")
    seen: dict[str, Page | None] = {}
    queue = deque(start)
    external: dict[str, str] = {}
    body_by_url: dict[str, str] = {}
    sprite_bases: set[str] = set()
    sprite_refs: set[str] = set()
    ficha_ids: dict[str, set[int]] = {lang: set() for lang in LANGS}

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
                if href in page.assets:
                    err(f"{url}: carga un recurso externo {full}")
                external.setdefault(full, url)
                continue
            lang_of = LANGS[1] if parts.path.startswith("/en/") else LANGS[0]
            if parts.path.endswith("/pokemon/") and parts.query:
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
        if not (tpl.count('id="ficha"') == 1 and 'id="i18n"' in tpl and 'id="tpl-types"' in tpl and 'id="tpl-regions"' in tpl):
            err(f"{lang}pokemon/: falta algo de la plantilla de ficha")
        if len(re.findall(r'<span data-t="', tpl)) != 18 or len(re.findall(r'<span data-gen="', tpl)) != 9:
            err(f"{lang}pokemon/: tipos o regiones incompletos en la plantilla")

    # enlaces viejos: /pokemon/<n>.html cae en la 404, que los reenvía a la ficha
    for lang in LANGS:
        status, body = fetch(f"{base}{lang}pokemon/25.html")
        if status != 404 or b'data-page="404"' not in body:
            err(f"{lang}pokemon/25.html debería caer en 404.html con estado 404 (da {status}); sirve site/ con build/serve.py")
    app_js = fetch(base + "app.js")[1].decode("utf8", "replace")
    if "location.replace" not in app_js or "pokemon" not in app_js:
        err("app.js no reenvía los enlaces viejos de fichas")

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
        if any(f.suffix == ".png" and f.name != "og.png" for f in files):
            err("site/ lleva PNG: los sprites tienen que salir del CDN (og.png es la excepción: la imagen para compartir)")

    # ataques: barras en cada ataque y nada de jerga sin explicar
    rows_expected = sum(2 if "buff" in m else 1 for m in moves)  # un valor por ataque; el potenciador suma tiempo activo
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
    agent_check(base, body_by_url, err, notes)
    browser_check(base, index, args, err, notes)

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
