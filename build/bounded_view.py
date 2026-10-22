"""Mejores builds de la ficha (data/bounded_ranking.json) y tabla de habilidades.

Todo sale de simulator/data/game.json, data/abilities.json y data/bounded_ranking.json. Los textos van aquí en
parejas (es, en).
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

from typedata import TYPE_COLOR

ROOT = Path(__file__).resolve().parent.parent
GAME = json.loads((ROOT / "simulator/data/game.json").read_text(encoding="utf8"))
BOUNDED = json.loads((ROOT / "data/bounded_ranking.json").read_text(encoding="utf8"))
ABIL = json.loads((ROOT / "data/abilities.json").read_text(encoding="utf8"))["abilities"]
NAT = {n["id"]: n for n in GAME["natures"]}
DEX = {d["dex"]: d for d in GAME["dex"]}
if BOUNDED["gameCommit"] != GAME["gameCommit"]:
    raise SystemExit("data/bounded_ranking.json no es del commit de game.json")

T = {
    "h": ("Mejores builds", "Best builds"),
    "melee": ("Cuerpo a cuerpo", "Melee"), "ranged": ("A distancia", "Ranged"),
    "no_tm": ("Sin MT", "No TMs"), "optimized": ("Con MT", "With TMs"),
    "start": ("Empieza con", "Starts with"), "ability": ("Habilidad", "Ability"), "nature": ("Naturaleza", "Nature"),
    "tm": ("MT", "TMs"), "best": ("Mejor", "Best"),
    "surv": ("{s} s de supervivencia", "{s} s survival"),
    "untested": ("no probadas", "not tested"),
    "none": ("ninguna", "none"),
    "ab_h": ("Habilidades", "Abilities"),
    "ab_lede": ("Las {n} habilidades de game.json con su efecto en el juego (js/data/ability-fx.js). Las que no tienen "
                "efecto propio dan la pasiva genérica: +8 % de daño con los movimientos del tipo principal.",
                "The {n} abilities in game.json with their in-game effect (js/data/ability-fx.js). Those without an "
                "effect of their own give the generic passive: +8 % damage with moves of the main type."),
    "ab_generic": ("Pasiva genérica: +8 % de daño con los movimientos de su tipo principal.",
                   "Generic passive: +8 % damage with moves of its main type."),
    "ab_plus": (" Además, la pasiva genérica de su tipo.", " Also the generic passive of its type."),
    "ab_col": ("Habilidad", "Ability"), "ab_eff": ("Efecto", "Effect"),
}
STAT = {"pa": ("Ataque", "Attack"), "sa": ("Ataque especial", "Special attack"), "df": ("Defensa", "Defense"),
        "sd": ("Defensa especial", "Special defense"), "spd": ("Velocidad", "Speed")}


def t(L, key: str, **kw) -> str:
    s = T[key][1 if L.en else 0]
    return s.format(**kw) if kw else s


def _i(L) -> int:
    return 1 if L.en else 0


def move_name(L, mid: str, moves_by: dict) -> str:
    m = moves_by.get(mid)
    if m is not None:
        return ((m.get("en") or {}).get("name") or m["name"]) if L.en else m["name"]
    g = GAME["moves"].get(mid)
    if g is None:
        raise SystemExit(f"movimiento desconocido {mid!r}")
    return g["levels"][0]["name"]


def ability_name(L, aid: str | None) -> str:
    if not aid:
        return t(L, "none")
    return ABIL[aid]["n"][_i(L)]


def cards(dex: int, avail: str) -> list[tuple[str, dict]]:
    """(estilo, build) de una rama, la que más aguanta primero."""
    rows = BOUNDED["species"][str(dex)]
    out = [(s, rows[f"{s}|{avail}"]) for s in ("melee", "ranged") if f"{s}|{avail}" in rows]
    return sorted(out, key=lambda sb: -sb[1]["survival"])


def best_build(dex: int) -> tuple[str, dict]:
    return cards(dex, "no_tm")[0]


def _chip(L, mid: str, moves_by: dict) -> str:
    m = moves_by.get(mid) or GAME["moves"][mid]
    buff = " is-buff" if m["kind"] == "buff" else ""
    return (f'<li class="bx-chip{buff}" style="--tc:{TYPE_COLOR[m["type"]]}">'
            f'{escape(move_name(L, mid, moves_by))}</li>')


def _card(L, style: str, b: dict, moves_by: dict, best: bool) -> str:
    start = ", ".join(move_name(L, m, moves_by) for m in b["start"])
    facts = [(t(L, "start"), start), (t(L, "ability"), ability_name(L, b["ability"])),
             (t(L, "nature"), NAT[b["nature"]]["n"][_i(L)])]
    if b["tms"]:
        facts.append((t(L, "tm"), ", ".join(f'{move_name(L, m, moves_by)} {L.num(GAME["tmPrices"][m])}' for m in b["tms"])))
    dl = "".join(f"<div><dt>{escape(k)}</dt><dd>{escape(v)}</dd></div>" for k, v in facts)
    tag = f'<span class="bx-best">{escape(t(L, "best"))}</span>' if best else ""
    return (f'<li class="bx-card" data-build="{style}"><div class="bx-top"><h4>{escape(t(L, style))}{tag}</h4>'
            f'<span class="bx-surv">{escape(t(L, "surv", s=L.dec(b["survival"], 0)))}</span></div>'
            f'<ul class="bx-chips">{"".join(_chip(L, m, moves_by) for m in b["attacks"])}</ul>'
            f'<dl class="bx-facts">{dl}</dl></li>')


def best_card(dex: int) -> tuple[str, str] | None:
    """La build con más supervivencia. A igualdad, gana la primera en este orden."""
    rows = BOUNDED["species"][str(dex)]
    best = None
    for avail in ("no_tm", "optimized"):
        for style in ("melee", "ranged"):
            b = rows.get(f"{style}|{avail}")
            if b is None:
                continue
            if best is None or b["survival"] > best[0]:
                best = (b["survival"], avail, style)
    if best is None:
        return None
    return best[1], best[2]


def builds_section(L, dex: int, moves_by: dict) -> str:
    winner = best_card(dex)
    avails = [a for a in ("no_tm", "optimized") if cards(dex, a)]
    lists = "".join(f'<ul class="bx-list" data-av="{a}">'
                    f'{"".join(_card(L, s, b, moves_by, (a, s) == winner) for s, b in cards(dex, a))}</ul>' for a in avails)
    seg = ""
    if len(avails) > 1:
        seg = ('<div class="bx-seg" role="radiogroup" aria-label="' + escape(t(L, "h")) + '">'
               f'<input type="radio" name="bx-av" id="bx-av-no" checked><label for="bx-av-no">{escape(t(L, "no_tm"))}</label>'
               f'<input type="radio" name="bx-av" id="bx-av-tm"><label for="bx-av-tm">{escape(t(L, "optimized"))}</label></div>')
    return (f'<section class="bx" id="build" aria-labelledby="bx-h"><div class="bx-head">'
            f'<h2 id="bx-h">{escape(t(L, "h"))}</h2>{seg}</div>{lists}</section>')


def abilities_full_section(L) -> str:
    rows = []
    for aid, a in sorted(ABIL.items(), key=lambda kv: kv[1]["n"][_i(L)]):
        if a["generic"]:
            eff = t(L, "ab_generic")
        else:
            eff = (a["en"] or a["es"]) if L.en else a["es"]
            if a["plus"]:
                eff += t(L, "ab_plus")
        lang = ' lang="es"' if L.en and not a["generic"] and not a["en"] else ""
        rows.append(f'<tr><th scope="row">{escape(a["n"][_i(L)])}</th><td{lang}>{escape(eff)}</td></tr>')
    return (f'<section class="pv-abilities" id="habilidades" aria-labelledby="pv-ab-h">'
            f'<h2 id="pv-ab-h">{escape(t(L, "ab_h"))}</h2><p class="lede">{escape(t(L, "ab_lede", n=len(ABIL)))}</p>'
            f'<div class="nat-table"><table><thead><tr><th scope="col">{escape(t(L, "ab_col"))}</th>'
            f'<th scope="col">{escape(t(L, "ab_eff"))}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>')
