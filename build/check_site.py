"""Comprobaciones de aceptación sobre un sitio ya servido (local o desplegado).

    python3 build/check_site.py http://localhost:8765/
    python3 build/check_site.py https://mi-proyecto.vercel.app/ --external

Comprueba, en español y en inglés: 966 fichas con sprite, enlaces internos y anclas sin romper, aviso legal en cada página,
conteos por tier, % de gacha, gráficos con texto alternativo, barras en cada ataque, que el inglés no mezcla español,
que los créditos de sprites solo salen en Acerca y que no se carga nada de otros dominios. Con --external, también
los enlaces externos.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, deque
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen

UA = {"User-Agent": "SurvivorTiers-check/1.0"}
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

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
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


def fetch(url: str, method: str = "GET"):
    try:
        with urlopen(Request(url, headers=UA, method=method), timeout=30) as r:
            return r.status, r.read() if method == "GET" else b""
    except HTTPError as e:
        return e.code, b""
    except URLError as e:
        return 0, str(e).encode()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--external", action="store_true", help="comprueba también los enlaces externos (red)")
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
    meta = json.loads(fetch(base + "data/meta.json")[1])
    gachas = json.loads(fetch(base + "data/gachas.json")[1])
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

    # rastreo
    start = [f"{base}{lang}{p}" for lang in LANGS
             for p in ("index.html", "metodo.html", "ataques.html", "gachas.html", "coleccion.html", "acerca.html")]
    start += [f"{base}{lang}pokemon/{d}.html" for lang in LANGS for d in dexes]
    seen: dict[str, Page | None] = {}
    queue = deque(start)
    external: dict[str, str] = {}
    fichas_ok = 0
    body_by_url: dict[str, str] = {}
    while queue:
        url = queue.popleft()
        if url in seen:
            continue
        status, body = fetch(url)
        if status != 200:
            err(f"{url} → {status}")
            seen[url] = None
            continue
        if not url.endswith(".html"):
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
            if parts.netloc != origin:
                if href in page.assets:
                    err(f"{url}: carga un recurso externo {full}")
                external.setdefault(full, url)
                continue
            target = urldefrag(full)[0]
            if target not in seen and target not in queue and href in page.links and target.endswith(".html"):
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
            if urlparse(full).netloc == origin and frag and target in seen and seen[target] is not None:
                if frag not in seen[target].ids:
                    err(f"{url}: ancla rota {href}")

    # fichas
    fichas_ok = 0
    for lang in LANGS:
        for d in dexes:
            url = f"{base}{lang}pokemon/{d}.html"
            page = seen.get(url)
            if page is None:
                continue
            sprite = [i for i in page.imgs if i.get("src", "").endswith(f"sprites/{d}.png")]
            figs = len(re.findall(r'<figure class="fig ', body_by_url[url]))
            alts = len(re.findall(r'class="fig-body" role="img" aria-label="[^"]{20,}"', body_by_url[url]))
            if figs != 4 or alts != 4:
                err(f"ficha {url}: {figs} gráficos y {alts} con texto alternativo (se esperaban 4)")
            if not sprite:
                err(f"ficha {url}: sin imagen de sprite")
            elif " ".join(page.text).count("SpriteCollab") > 1:
                err(f"ficha {url}: repite los créditos de sprites")
            else:
                fichas_ok += 1

    # ataques: barras en cada ataque y nada de jerga sin explicar
    moves = json.loads(fetch(base + "data/moves.json")[1])
    rows_expected = sum(3 if "rel" in m else 4 for m in moves)
    for lang in LANGS:
        url = f"{base}{lang}ataques.html"
        html = body_by_url.get(url, "")
        rows = html.count('class="mb-row"')
        if rows != rows_expected:
            err(f"{url}: {rows} barras, se esperaban {rows_expected}")
        if re.search(r"la mediana al minuto|median at minute|× la mediana", html):
            err(f"{url}: queda jerga sin explicar")

    # créditos de sprites solo en Acerca
    for lang in LANGS:
        about = body_by_url.get(f"{base}{lang}acerca.html", "")
        if about.count('class="credits-list"') != 1 or about.count("<li><a") < 5:
            err(f"{lang}acerca.html: faltan los créditos de los artistas")
    imgs = sum(1 for u in seen if u.endswith(".png"))
    notes.append(f"páginas rastreadas: {sum(1 for p in seen.values() if p)}; PNG cargados: {imgs}; fichas con sprite: {fichas_ok}/1932")

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
