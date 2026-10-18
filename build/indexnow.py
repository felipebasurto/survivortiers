"""Avisa a IndexNow (Bing, Yandex y otros buscadores) de las URL de sitemap.xml.

Se ejecuta a mano después de cada deploy, cuando la clave ya responde en /<clave>.txt:

    python3 build/indexnow.py --dry-run   muestra lo que enviaría, sin red
    python3 build/indexnow.py             envía las URL a api.indexnow.org

La clave es el archivo src/<clave>.txt (32 caracteres hexadecimales, con la clave dentro). pack.py lo copia a la raíz
del sitio. Sin deploy previo IndexNow rechaza la petición, así que no tiene sentido correrlo antes.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import legal

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
SITE = ROOT / "site"
ENDPOINT = "https://api.indexnow.org/indexnow"
BATCH = 10_000  # máximo de URL por petición, según la especificación de IndexNow
KEY_RE = re.compile(r"[0-9a-f]{32}")
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


class IndexNowError(RuntimeError):
    pass


def key_file(src: Path = SRC) -> Path:
    found = [p for p in src.glob("*.txt") if KEY_RE.fullmatch(p.stem)]
    if len(found) != 1:
        raise IndexNowError(f"hace falta exactamente un archivo <clave>.txt en {src}; hay {len(found)}")
    path = found[0]
    if path.read_text(encoding="utf8").strip() != path.stem:
        raise IndexNowError(f"{path.name} tiene que contener solo la clave")
    return path


def sitemap_urls(site: Path = SITE) -> list[str]:
    root = ET.parse(site / "sitemap.xml").getroot()
    seen: dict[str, None] = {}
    for loc in root.iter(f"{SITEMAP_NS}loc"):
        url = (loc.text or "").strip()
        if url:
            seen.setdefault(url, None)
    return list(seen)


def host() -> str:
    return urlparse(legal.SITE_URL).netloc


def payloads(urls: list[str], key: str) -> list[dict]:
    """Un cuerpo JSON por lote. Todas las URL tienen que ser del host del sitio: IndexNow rechaza el resto."""
    foreign = [u for u in urls if urlparse(u).netloc != host()]
    if foreign:
        raise IndexNowError(f"URL fuera de {host()}: {foreign[:3]}")
    return [{"host": host(), "key": key, "keyLocation": f"{legal.SITE_URL}/{key}.txt", "urlList": urls[i:i + BATCH]}
            for i in range(0, len(urls), BATCH)]


def submit(body: dict) -> int:
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body, ensure_ascii=False).encode("utf8"), method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="muestra lotes y URL sin enviar nada")
    args = ap.parse_args(argv)
    try:
        key = key_file().stem
        bodies = payloads(sitemap_urls(), key)
    except (IndexNowError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    total = sum(len(b["urlList"]) for b in bodies)
    print(f"indexnow: {total} URL en {len(bodies)} lote(s) para {host()}, clave en {legal.SITE_URL}/{key}.txt")
    if args.dry_run:
        print(json.dumps(bodies[0]["urlList"][:5], ensure_ascii=False, indent=1))
        return 0
    for i, body in enumerate(bodies, 1):
        try:
            status = submit(body)
        except urllib.error.HTTPError as exc:
            print(f"ERROR: lote {i}: HTTP {exc.code}", file=sys.stderr)
            return 1
        print(f"lote {i}: HTTP {status}, {len(body['urlList'])} URL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
