"""Naturalezas del juego y MT que aprende cada Pokémon.

Fuente: simulator/data/game.json, la misma que lee catalog.py. Una naturaleza sube una estadística un 10 % y baja otra
un 10 %: es lo que aplica simulator/sim-rs/src/data.rs (configure: up 1,1, down 0,9). Las MT de cada especie son
`dex[n]["tms"]` y su precio en la tienda es `tmPrices`.
"""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME = json.loads((ROOT / "simulator/data/game.json").read_text(encoding="utf8"))
_DEX = {d["dex"]: d for d in GAME["dex"]}
_STAT_KEY = {"pa": "nat_pa", "df": "nat_df", "sa": "nat_sa", "sd": "nat_sd", "spd": "nat_spd"}


def _stat(L, stat: str) -> str:
    return L.t(_STAT_KEY[stat])


def _name(L, nature: dict) -> str:
    return nature["n"][1] if L.en else nature["n"][0]


def nature_rows(L) -> list[tuple[str, str, str]]:
    rows = []
    for n in GAME["natures"]:
        up = _stat(L, n["up"]) if n["up"] else L.t("nat_neutral")
        down = _stat(L, n["down"]) if n["down"] else L.t("nat_neutral")
        rows.append((_name(L, n), up, down))
    return rows


def naturalezas_content(L) -> str:
    head = (f'<h1>{escape(L.t("nat_h1"))}</h1>'
            f'<p class="lede">{escape(L.t("nat_lede"))}</p>')
    neutral = L.t("nat_neutral")

    def cell(text: str, kind: str) -> str:
        cls = "nat-neutral" if text == neutral else kind
        return f'<td class="{cls}">{escape(text)}</td>'

    body = "".join(f'<tr><th scope="row">{escape(name)}</th>{cell(up, "nat-up")}{cell(down, "nat-down")}</tr>'
                   for name, up, down in nature_rows(L))
    table = (f'<div class="nat-table"><table><thead><tr>'
             f'<th scope="col">{escape(L.t("nat_col_name"))}</th>'
             f'<th scope="col">{escape(L.t("nat_col_up"))}</th>'
             f'<th scope="col">{escape(L.t("nat_col_down"))}</th>'
             f'</tr></thead><tbody>{body}</tbody></table></div>')
    return f'<div class="pv">{head}{table}</div>'


def _move_name(L, mid: str, moves_by: dict) -> str:
    m = moves_by.get(mid)
    if m is None:  # moves_by debe ser moves + unranked (render.py): sin él, un potenciador saldría con su id en inglés
        name = (GAME["moves"].get(mid) or {}).get("levels", [{}])[0].get("name")
        if not name or L.en:
            raise ValueError(f"MT {mid!r} sin nombre en el catálogo (¿falta moves_unranked?)")
        return name
    if L.en:
        return (m.get("en") or {}).get("name") or m["name"]
    return m["name"]


def tm_section(L, dex: int, moves_by: dict) -> str:
    """Lista de MT de una especie. Vacía si la especie no aprende ninguna."""
    tms = _DEX.get(dex, {}).get("tms") or []
    if not tms:
        return ""
    items = "".join(
        f'<li><span class="tm-name">{escape(_move_name(L, mid, moves_by))}</span>'
        f'<span class="tm-price">{L.num(GAME["tmPrices"].get(mid, 0))}</span></li>'
        for mid in tms)
    return (f'<section class="learn" aria-labelledby="learn-h">'
            f'<h2 id="learn-h">{escape(L.t("mt_h"))}</h2>'
            f'<ul class="tm-list">{items}</ul></section>')
