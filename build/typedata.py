"""Colores y glifos de tipo, adaptados de PokéSurvivor (js/core/util.js TYPE_COLOR y js/ui/icons.js TYPE_GLYPH).
MIT License, Copyright (c) 2026 JPTER78. Ver build/legal.py (MIT_NOTICE)."""
from __future__ import annotations

TYPE_COLOR = {
    "normal": "#b0a99f", "fire": "#ff7b3d", "water": "#4b9bff", "grass": "#5fcb6a",
    "electric": "#ffd33d", "ice": "#7fe0e0", "fighting": "#e0533d", "poison": "#b45ec4",
    "ground": "#d6b25c", "flying": "#9bb8ff", "psychic": "#ff5f9e", "bug": "#a3c43d",
    "rock": "#bfa96b", "ghost": "#7a6bc4", "dragon": "#6b58ff", "dark": "#6b5c52",
    "steel": "#a8b8c4", "fairy": "#ff9ed8",
}

TYPE_GLYPH = {
    "normal": ["..####..", ".#....#.", "#......#", "#..##..#", "#..##..#", "#......#", ".#....#.", "..####.."],
    "fire": ["...#....", "...##...", "..###.#.", ".#####..", ".######.", "##.####.", "##..###.", ".######."],
    "water": ["...##...", "...##...", "..####..", ".######.", ".##.###.", ".#.####.", ".######.", "..####.."],
    "grass": [".....###", "...#####", "..######", ".####.##", ".###.###", ".##.####", ".#.####.", "#......."],
    "electric": ["....###.", "...###..", "..###...", ".######.", "...###..", "..###...", ".##.....", "#......."],
    "psychic": [".######.", "#......#", "#.####.#", "#.#..#.#", "#.#.##.#", "#.#....#", "#.######", "#......."],
    "ice": ["...#....", ".#.#.#..", "..###...", "#######.", "..###...", ".#.#.#..", "...#....", "........"],
    "fighting": [".######.", "########", "########", "#.#.#.##", "########", ".#######", "..#####.", "..####.."],
    "poison": [".....##.", "....####", ".....##.", ".###....", "#####...", "#####.##", ".###.###", ".....##."],
    "ground": ["........", "...##...", "..####..", ".##..##.", ".######.", "##.##.##", "########", "........"],
    "flying": ["#.......", "##......", "###.....", "####....", "######..", "########", ".#######", "...####."],
    "bug": [".#....#.", "..#..#..", "..####..", ".##.###.", "########", "###.####", ".######.", "..####.."],
    "rock": ["...###..", "..#####.", ".###.###", "######.#", "##.#####", "#######.", ".#####..", "........"],
    "ghost": ["..####..", ".######.", "##.##.##", "##.##.##", "########", "########", "########", "#.#..#.#"],
    "dragon": ["#.......", "##....#.", ".##..##.", ".######.", "..####..", ".######.", "##.##.##", "#..##..#"],
    "dark": ["..####..", ".###....", "###.....", "###.....", "###.....", "###.....", ".###....", "..####.."],
    "steel": ["..####..", ".######.", "###..###", "##....##", "##....##", "###..###", ".######.", "..####.."],
    "fairy": ["...#....", "...#....", "..###...", "#######.", "..###...", "..#.#...", ".#...#..", "........"],
}


def _luminance(hex_color: str) -> float:
    n = int(hex_color[1:], 16)
    chans = []
    for c in ((n >> 16) & 255, (n >> 8) & 255, n & 255):
        c = c / 255
        chans.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * chans[0] + 0.7152 * chans[1] + 0.0722 * chans[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


INK, PAPER = "#1b1528", "#ffffff"


def text_color(type_name: str) -> str:
    """Tinta oscura o blanca, la que más contraste da sobre el color del tipo."""
    bg = TYPE_COLOR[type_name]
    return INK if contrast(bg, INK) >= contrast(bg, PAPER) else PAPER


def glyph_svg(type_name: str) -> str:
    rows = TYPE_GLYPH[type_name]
    rects = "".join(f'<rect x="{x}" y="{y}" width="1" height="1"/>'
                    for y, row in enumerate(rows) for x, ch in enumerate(row) if ch == "#")
    return (f'<svg class="glyph" viewBox="0 0 8 8" width="14" height="14" aria-hidden="true" focusable="false" '
            f'shape-rendering="crispEdges" fill="currentColor">{rects}</svg>')
