"""Mejores builds de la ficha (data/bounded_ranking.json), y habilidades y naturalezas por estadística en pasivas.html.

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
    "line": ("Empieza con {start} · Habilidad {ability} · Naturaleza {nature}",
             "Starts with {start} · Ability {ability} · Nature {nature}"),
    "tms": ("MT: {tms}", "TMs: {tms}"),
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
    "ab_short": ("Las {n} habilidades del juego y lo que hace cada una están en su propia página.",
                 "The {n} abilities in the game and what each one does have their own page."),
    "ab_link": ("Ver todas las habilidades", "See all abilities"),
    "ab_col": ("Habilidad", "Ability"), "ab_eff": ("Efecto", "Effect"),
    "ns_h": ("Mejores naturalezas por estadística", "Best natures per stat"),
    "ns_lede": ("Para cada estadística, las cuatro naturalezas que la suben un 10 % y la que bajan un 10 %. Criterio de "
                "orden: primero las que más veces llevan las mejores builds de los 966 Pokémon; a "
                "igualdad, el orden de game.json. El ranking solo probó la neutra y las que suben el ataque dominante "
                "(Ataque o Ataque especial), así que en Defensa, Defensa especial y Velocidad no hay recuento: van en "
                "el orden de game.json. ",
                "For each stat, the four natures that raise it 10 % and the one each lowers 10 %. Order: first those "
                "used most often by the best builds of the 966 Pokémon; ties keep the game.json "
                "order. The ranking only tried neutral natures and those raising the dominant attack stat (Attack or "
                "Special attack), so Defense, Special defense and Speed have no count and keep the game.json order. "),
    "ns_link": ("Tabla completa de naturalezas", "Full nature table"),
    "ns_col_n": ("Naturaleza", "Nature"), "ns_col_d": ("Baja", "Lowers"),
    "ns_col_w": ("Veces elegida (cuerpo a cuerpo / distancia)", "Times picked (melee / ranged)"),
    "ns_neutral": ("Neutras {m} / {r}", "Neutral {m} / {r}"),
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
    nat = NAT[b["nature"]]
    line = t(L, "line", start=start, ability=ability_name(L, b["ability"]), nature=nat["n"][_i(L)])
    tms = ""
    if b["tms"]:
        names = ", ".join(f'{move_name(L, m, moves_by)} ({L.num(GAME["tmPrices"][m])})' for m in b["tms"])
        tms = f'<p class="bx-tm">{escape(t(L, "tms", tms=names))}</p>'
    cls = "bx-card is-best" if best else "bx-card"
    return (f'<li class="{cls}" data-build="{style}"><div class="bx-top"><h4>{escape(t(L, style))}</h4>'
            f'<span class="bx-surv">{escape(t(L, "surv", s=L.dec(b["survival"], 0)))}</span></div>'
            f'<ul class="bx-chips">{"".join(_chip(L, m, moves_by) for m in b["attacks"])}</ul>'
            f'<p class="bx-line">{escape(line)}</p>{tms}</li>')


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
    groups = []
    for avail in ("no_tm", "optimized"):
        cs = cards(dex, avail)
        if cs:
            groups.append(f'<h3>{escape(t(L, avail))}</h3><ul class="bx-list">'
                          f'{"".join(_card(L, s, b, moves_by, (avail, s) == winner) for s, b in cs)}</ul>')
    return (f'<section class="bx" id="build" aria-labelledby="bx-h"><h2 id="bx-h">{escape(t(L, "h"))}</h2>'
            f'{"".join(groups)}</section>')


def abilities_section(L, home: str = "") -> str:
    """Enlace corto a habilidades.html, que tiene la lista completa."""
    return (f'<section class="pv-abilities" id="habilidades" aria-labelledby="pv-ab-h">'
            f'<h2 id="pv-ab-h">{escape(t(L, "ab_h"))}</h2><p class="lede">{escape(t(L, "ab_short", n=len(ABIL)))} '
            f'<a href="{home}habilidades.html">{escape(t(L, "ab_link"))}</a></p></section>')


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


def natures_by_stat_section(L, home: str) -> str:
    wins = BOUNDED["natureWins"]
    order = [n["id"] for n in GAME["natures"]]

    def w(nid: str, style: str) -> int:
        return wins.get(style, {}).get(nid, 0)

    blocks = []
    for stat in ("pa", "sa", "df", "sd", "spd"):
        ns = sorted((n for n in GAME["natures"] if n["up"] == stat),
                    key=lambda n: (-(w(n["id"], "melee") + w(n["id"], "ranged")), order.index(n["id"])))
        items = []
        for n in ns:
            count = ""
            if stat in ("pa", "sa"):
                count = f'<b class="ns-n">{w(n["id"], "melee")} / {w(n["id"], "ranged")}</b>'
            items.append(f'<li><span>{escape(n["n"][_i(L)])} <small>{escape(STAT[n["down"]][_i(L)])}</small></span>{count}</li>')
        blocks.append(f'<section><h3>+{escape(STAT[stat][_i(L)])}</h3><ol>{"".join(items)}</ol></section>')
    neutral = [n["id"] for n in GAME["natures"] if not n["up"]]
    nm = sum(w(n, "melee") for n in neutral)
    nr = sum(w(n, "ranged") for n in neutral)
    return (f'<section class="pv-natures" id="naturalezas-por-estadistica" aria-labelledby="pv-ns-h">'
            f'<h2 id="pv-ns-h">{escape(t(L, "ns_h"))}</h2>'
            f'<p><a href="{home}naturalezas.html">{escape(t(L, "ns_link"))}</a></p>'
            f'<div class="ns-cols">{"".join(blocks)}</div>'
            f'<p class="ns-neutral">{escape(t(L, "ns_neutral", m=nm, r=nr))}</p></section>')
