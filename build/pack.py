"""Empaqueta los recursos de src/ en site/: un style.css (con los iconos dentro, minificado), un app.js (share.js +
app.js + ficha.js, sin comentarios ni sangrías), la letra, los JSON del navegador y _headers. Solo biblioteca estándar.

Los minificadores son conservadores a propósito: solo quitan lo que no puede cambiar el significado. El CSS se puede
comparar con el original regla a regla (cssText en el navegador) y el JS se comprueba con node --check."""
from __future__ import annotations

import base64
import hashlib
import re
import shutil
from pathlib import Path

JS_FILES = ("share.js", "app.js", "ficha.js")
FONT_FILES = ("PixelifySans.ttf", "OFL.txt", "ZenKakuGothicNew-400.woff2", "ZenKakuGothicNew-500.woff2",
              "ZenKakuGothicNew-700.woff2", "ZenKakuGothicNew-OFL.txt")
STRING = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
ICON = re.compile(r"url\(img/ui/([\w-]+)\.png\)")


def _squeeze(code: str) -> str:
    code = re.sub(r"\s+", " ", code)
    code = re.sub(r" ?([{};,>]) ?", r"\1", code)
    code = re.sub(r":\s+", ":", code)
    return code.replace(";}", "}")


def minify_css(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    out, pos = [], 0
    for m in STRING.finditer(text):
        out.append(_squeeze(text[pos:m.start()]))
        out.append(m.group())
        pos = m.end()
    out.append(_squeeze(text[pos:]))
    return "".join(out).strip()


def inline_icons(css: str, src: Path) -> str:
    def data_uri(m: re.Match) -> str:
        png = (src / "img" / "ui" / f"{m.group(1)}.png").read_bytes()
        return f"url(data:image/png;base64,{base64.b64encode(png).decode()})"
    return ICON.sub(data_uri, css)


def minify_js(text: str) -> str:
    """Quita comentarios de línea completa y de bloque que empiezan la línea, la sangría y las líneas en blanco."""
    text = re.sub(r"^[ \t]*/\*.*?\*/[ \t]*\n", "", text, flags=re.S | re.M)
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln and not ln.startswith("//")) + "\n"


def build(src: Path, site: Path, public: Path) -> str:
    """Escribe los recursos en site/ y devuelve la huella corta de style.css y app.js, para versionarlos en las páginas."""
    css = inline_icons(minify_css((src / "style.css").read_text(encoding="utf8")), src)
    js = "".join(minify_js((src / name).read_text(encoding="utf8")) for name in JS_FILES)
    site.mkdir(parents=True, exist_ok=True)
    (site / "style.css").write_text(css, encoding="utf8")
    (site / "app.js").write_text(js, encoding="utf8")
    (site / "fonts").mkdir(exist_ok=True)
    for name in FONT_FILES:
        shutil.copy2(src / "fonts" / name, site / "fonts" / name)
    (site / "data").mkdir(exist_ok=True)
    for f in sorted(public.glob("*.json")):
        shutil.copy2(f, site / "data" / f.name)
    shutil.copy2(src / "_headers", site / "_headers")
    return hashlib.sha1((css + js).encode("utf8")).hexdigest()[:8]
