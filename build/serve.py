"""Servidor local que se comporta como el hosting: sirve site/, devuelve 404.html con estado 404 para lo que no existe
y publica sprites/ en /_sprites/ para ver el sitio sin conexión.

    SPRITE_BASE=http://127.0.0.1:8765/_sprites/ python3 build/catalog.py && python3 build/render.py
    python3 build/serve.py            # http://127.0.0.1:8765/
"""
from __future__ import annotations

import argparse
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SPRITES = ROOT / "sprites"
PREFIX = "/_sprites/"


def _redirects() -> dict[str, str]:
    out = {}
    for line in (ROOT / "src" / "_redirects").read_text(encoding="utf8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            out[parts[0]] = parts[1]
    return out


REDIRECTS = _redirects()


class Handler(SimpleHTTPRequestHandler):
    def _go(self) -> bool:
        path = self.path.split("?", 1)[0]
        dest = REDIRECTS.get(path)
        if not dest:
            return False
        qs = self.path.split("?", 1)[1] if "?" in self.path else ""
        self.send_response(301)
        self.send_header("Location", dest + ("?" + qs if qs else ""))
        self.send_header("Content-Length", "0")
        self.end_headers()
        return True

    def do_GET(self):
        if not self._go():
            super().do_GET()

    def do_HEAD(self):
        if not self._go():
            super().do_HEAD()

    def translate_path(self, path: str) -> str:
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith(PREFIX):
            return str(SPRITES / clean[len(PREFIX):])
        fs = super().translate_path(path)
        # URLs limpias como en Workers y Pages: /en/metodo sirve en/metodo.html
        if not os.path.exists(fs) and not clean.endswith("/") and os.path.isfile(fs + ".html"):
            return fs + ".html"
        return fs

    def send_error(self, code, message=None, explain=None):
        page = SITE / "404.html"
        if code != 404 or not page.exists() or self.command == "HEAD":
            return super().send_error(code, message, explain)
        body = page.read_bytes()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(SITE)))
    print(f"http://127.0.0.1:{args.port}/  (site/ + /_sprites/)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
