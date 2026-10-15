"""Insignias de región para las tarjetas de gacha: un cuadrado redondeado con el degradado de la región (los colores
de cada generación que usan las wikis de Pokémon), un motivo propio en SVG (monumento o paisaje típico) y encima los
sprites de sus legendarios de portada o de su inicial. Todo el dibujo es original y los sprites son los mismos
de SpriteCollab que ya usa el sitio, con su atribución en el pie y en Info."""
from __future__ import annotations

from html import escape

from i18n import Lang
import legal

SIZE = 96  # lado del viewBox
RADIUS = 22

# gen -> (clave, sprites de portada por número de Pokédex). Kanto lleva a Charizard, la portada de Rojo Fuego,
# y Paldea solo a Koraidon porque Miraidon no está en el juego.
REGIONS: dict[int, tuple[str, tuple[int, ...]]] = {
    1: ("kanto", (6,)),
    2: ("johto", (249, 250)),
    3: ("hoenn", (383, 382)),
    4: ("sinnoh", (483, 484)),
    5: ("unova", (643, 644)),
    6: ("kalos", (716, 717)),
    7: ("alola", (791, 792)),
    8: ("galar", (888, 889)),
    9: ("paldea", (1007,)),
}


def _grad(key: str, stops: list[tuple[float, str]], x2: int = 1, y2: int = 1) -> str:
    body = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
    return f'<linearGradient id="g-{key}" x1="0" y1="0" x2="{x2}" y2="{y2}">{body}</linearGradient>'


def _building_row(fill: str, clip: str) -> str:
    towers = [(6, 14, 34), (16, 12, 52), (26, 12, 40), (36, 14, 62), (48, 10, 46), (58, 14, 58), (70, 12, 38), (80, 12, 50)]
    rects = "".join(f'<rect x="{x}" y="{88 - h}" width="{w}" height="{h}"/>' for x, w, h in towers)
    return f'<g fill="{fill}" clip-path="url(#{clip})">{rects}</g>'


def _kanto() -> tuple[str, str]:
    defs = _grad("kanto", [(0, "#ff6b5e"), (.55, "#e0443a"), (.56, "#4cb860"), (1, "#2f8f4a")])
    art = ('<g fill="none" stroke="#fff" stroke-opacity=".4" stroke-width="4"><circle cx="48" cy="42" r="30"/>'
           '<path d="M18 42H78"/><circle cx="48" cy="42" r="8"/></g>'
           '<path d="M0 82Q24 64 48 78T96 72V96H0Z" fill="#1f6b3a" fill-opacity=".65"/>')
    return defs, art


def _johto() -> tuple[str, str]:
    defs = _grad("johto", [(0, "#ffd45c"), (1, "#c9ccd8")], 0, 1)
    arcs = "".join(f'<path d="M{48 - r} 58A{r} {r} 0 0 1 {48 + r} 58" stroke="{c}"/>'
                   for r, c in ((40, "#ff7a7a"), (35, "#ffd35c"), (30, "#6fd48a"), (25, "#6aa9ff")))
    tiers = ""
    for i, y in enumerate((66, 48, 30)):
        w = 22 - 6 * i
        tiers += (f'<path d="M{48 - w} {y + 12}H{48 + w}L{48 + w - 6} {y}H{48 - w + 6}Z"/>'
                  f'<rect x="{48 - w + 8}" y="{y + 12}" width="{2 * w - 16}" height="6"/>')
    art = (f'<g fill="none" stroke-width="3" stroke-opacity=".6">{arcs}</g>'
           f'<g fill="#7a4a12" fill-opacity=".85">{tiers}<rect x="47" y="14" width="2" height="16"/>'
           '<circle cx="48" cy="13" r="3"/><rect x="38" y="84" width="20" height="4"/></g>')
    return defs, art


def _hoenn() -> tuple[str, str]:
    defs = ""
    art = ('<rect width="96" height="96" fill="#2f6fd6"/><path d="M0 0H96L0 96Z" fill="#d9453a"/>'
           '<path d="M4 92L28 54H40L64 92Z" fill="#3b140f" fill-opacity=".75"/>'
           '<ellipse cx="34" cy="54" rx="7" ry="2.5" fill="#ffb347"/>'
           '<g fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="3"><path d="M52 76q6-6 12 0t12 0t12 0"/>'
           '<path d="M56 86q6-6 12 0t12 0t8 0"/></g>')
    return defs, art


def _sinnoh() -> tuple[str, str]:
    defs = _grad("sinnoh", [(0, "#ffc8d6"), (1, "#7a93ff")])
    art = ('<path d="M0 84L28 38L42 58L60 28L96 84Z" fill="#fff" fill-opacity=".88"/>'
           '<path d="M60 28L96 84H62L52 56Z" fill="#9fb0ff" fill-opacity=".55"/>'
           '<path d="M76 12L86 24L76 38L66 24Z" fill="#fff"/><path d="M76 12L86 24H66Z" fill="#c9f0ff"/>'
           '<circle cx="20" cy="22" r="8" fill="#fff" fill-opacity=".9"/><circle cx="17" cy="19" r="2.5" fill="#ffe7f0"/>')
    return defs, art


def _unova() -> tuple[str, str]:
    defs = ('<clipPath id="u-dark"><path d="M0 0H96L0 96Z"/></clipPath><clipPath id="u-light"><path d="M96 0V96H0Z"/></clipPath>')
    art = ('<rect width="96" height="96" fill="#26262c"/><path d="M96 0V96H0Z" fill="#efefef"/>'
           + _building_row("#efefef", "u-dark") + _building_row("#26262c", "u-light"))
    return defs, art


def _kalos() -> tuple[str, str]:
    defs = _grad("kalos", [(0, "#f46f87"), (1, "#2b6cc0")])
    art = ('<g fill="none" stroke="#fff" stroke-width="3" stroke-linejoin="round"><path d="M48 12L62 86H34Z"/>'
           '<path d="M43 40H53M40 58H56M38 72H58"/><path d="M42 86Q48 68 54 86"/></g>'
           '<g fill="#fff" fill-opacity=".8"><circle cx="48" cy="10" r="3"/><circle cx="16" cy="20" r="2"/>'
           '<circle cx="82" cy="30" r="2.5"/><circle cx="22" cy="48" r="1.8"/><circle cx="80" cy="60" r="1.8"/></g>')
    return defs, art


def _alola() -> tuple[str, str]:
    defs = _grad("alola", [(0, "#f7a13a"), (1, "#6bb6e6")], 0, 1)
    art = ('<circle cx="68" cy="30" r="15" fill="#ffe27a"/>'
           '<path d="M0 78q12-8 24 0t24 0t24 0t24 0V96H0Z" fill="#245e96" fill-opacity=".7"/>'
           '<path d="M24 88Q28 62 36 44" fill="none" stroke="#5a3a1a" stroke-width="3.5"/>'
           '<g fill="none" stroke="#1f6b3a" stroke-width="4" stroke-linecap="round"><path d="M36 44Q22 34 10 44"/>'
           '<path d="M36 44Q30 28 16 28"/><path d="M36 44Q46 28 60 34"/><path d="M36 44Q50 40 56 52"/></g>')
    return defs, art


def _galar() -> tuple[str, str]:
    defs = _grad("galar", [(0, "#d5598c"), (1, "#0aa6ea")])
    art = ('<path d="M14 90V58Q14 28 48 28Q82 28 82 58V90Z" fill="#1b1528" fill-opacity=".6"/>'
           '<path d="M28 90V60Q28 44 48 44Q68 44 68 60V90Z" fill="#fff" fill-opacity=".3"/>'
           '<g fill="#1b1528" fill-opacity=".75"><rect x="4" y="42" width="4" height="48"/>'
           '<rect x="88" y="42" width="4" height="48"/></g>'
           '<g fill="#fff6b0"><rect x="1" y="35" width="10" height="6"/><rect x="85" y="35" width="10" height="6"/></g>'
           '<g stroke="#fff" stroke-opacity=".7" stroke-width="2.5" stroke-linecap="round"><path d="M48 8V16M36 12L40 18M60 12L56 18"/></g>')
    return defs, art


def _paldea() -> tuple[str, str]:
    defs = _grad("paldea", [(0, "#a878d4"), (1, "#f2452f")], 0, 1)
    art = ('<ellipse cx="48" cy="64" rx="42" ry="17" fill="#3a1e5a" fill-opacity=".5"/>'
           '<ellipse cx="48" cy="62" rx="31" ry="11" fill="#1b1528" fill-opacity=".65"/>'
           '<path d="M5 66Q9 44 28 48Q40 38 56 46Q82 42 91 66" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="3.5"/>'
           '<circle cx="48" cy="54" r="7" fill="#ffe7a3"/><circle cx="48" cy="54" r="12" fill="none" stroke="#ffe7a3" stroke-opacity=".5" stroke-width="2"/>'
           '<g fill="#fff" fill-opacity=".8"><circle cx="18" cy="16" r="2"/><circle cx="76" cy="12" r="2.4"/>'
           '<circle cx="58" cy="24" r="1.6"/><circle cx="30" cy="30" r="1.6"/></g>')
    return defs, art


MOTIFS = {"kanto": _kanto, "johto": _johto, "hoenn": _hoenn, "sinnoh": _sinnoh, "unova": _unova, "kalos": _kalos,
          "alola": _alola, "galar": _galar, "paldea": _paldea}


def _sprite(sprites: str, mon: dict, box_w: int, box_h: int, side: str) -> str:
    scale = min(box_w / mon["w"], box_h / mon["h"])
    w, h = round(mon["w"] * scale), round(mon["h"] * scale)
    return (f'<img class="px rg-mon rg-{side}" src="{sprites}{mon["dex"]}{legal.SPRITE_EXT}" width="{w}" height="{h}" alt="">')


def badge(L: Lang, sprites: str, gen: int, name: str, index: dict[int, dict], small: bool = False) -> str:
    """Insignia de la región. Con small=True sale sin sprites ni etiqueta, para la ficha."""
    key, dexes = REGIONS[gen]
    defs, art = MOTIFS[key]()
    fill = f'url(#g-{key})' if f'id="g-{key}"' in defs else "none"
    svg = (f'<svg viewBox="0 0 {SIZE} {SIZE}" class="rg-art" aria-hidden="true" focusable="false"><defs>{defs}'
           f'<clipPath id="c-{key}"><rect width="{SIZE}" height="{SIZE}" rx="{RADIUS}"/></clipPath></defs>'
           f'<g clip-path="url(#c-{key})"><rect width="{SIZE}" height="{SIZE}" fill="{fill}"/>{art}</g></svg>')
    label = escape(name, quote=True)
    if small:
        return f'<span class="rg rg-s rg-{key}" role="img" aria-label="{label}" title="{label}">{svg}</span>'
    mons = [index[d] for d in dexes if d in index]
    if len(mons) == 1:
        imgs = _sprite(sprites, mons[0], 56, 56, "solo")
    else:
        imgs = _sprite(sprites, mons[0], 40, 46, "l") + _sprite(sprites, mons[1], 40, 46, "r")
    return (f'<span class="rg rg-{key}" role="img" aria-label="{label}" title="{label}">{svg}{imgs}'
            f'<span class="rg-name" aria-hidden="true">{label}</span></span>')
