"""Ranking acotado (data/bounded_ranking.json) en la ficha, y habilidades y naturalezas por estadística en pasivas.html.

Todo sale de simulator/data/game.json, data/abilities.json (build/ability_export.py, código del juego en el commit
fijado) y data/bounded_ranking.json (build/bounded_export.py). Los textos van aquí en parejas (es, en).
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME = json.loads((ROOT / "simulator/data/game.json").read_text(encoding="utf8"))
BOUNDED = json.loads((ROOT / "data/bounded_ranking.json").read_text(encoding="utf8"))
ABIL = json.loads((ROOT / "data/abilities.json").read_text(encoding="utf8"))["abilities"]
NAT = {n["id"]: n for n in GAME["natures"]}
DEX = {d["dex"]: d for d in GAME["dex"]}
if BOUNDED["gameCommit"] != GAME["gameCommit"]:
    raise SystemExit("data/bounded_ranking.json no es del commit de game.json")

T = {
    "h": ("Builds del ranking acotado (simulador nuevo)", "Bounded ranking builds (new simulator)"),
    "lede": ("La mejor build observada por estilo, con habilidad, naturaleza y MT, entre como mucho 12 candidatas por "
             "estrato y confirmada con {seeds} semillas. Es diagnóstico (bounded-ranking-v2): no es un óptimo global ni "
             "cambia el tier de arriba, que sigue siendo el de la fase 3.",
             "The best observed build per style, with ability, nature and TMs, among at most 12 candidates per stratum "
             "and confirmed with {seeds} seeds. It is diagnostic (bounded-ranking-v2): not a global optimum, and it does "
             "not change the tier above, which is still the phase 3 one."),
    "melee": ("Cuerpo a cuerpo", "Melee"), "ranged": ("A distancia", "Ranged"),
    "no_tm": ("sin MT", "no TM"), "optimized": ("con MT", "with TMs"),
    "ability": ("Habilidad", "Ability"), "nature": ("Naturaleza", "Nature"), "tms": ("MT necesarias", "TMs needed"),
    "start": ("Empieza con", "Starts with"),
    "metrics": ("{s} s de supervivencia · {kpm} bajas/min · {dps} daño/s", "{s} s survival · {kpm} kills/min · {dps} damage/s"),
    "run": ("Runpod cpu3c 32 vCPU, ranking full con búsqueda de naturalezas (aa98123), 441.486 partidas, 1.717 s",
            "Runpod cpu3c 32 vCPU, full ranking with nature search (aa98123), 441,486 matches, 1,717 s"),
    "untested": ("no probadas", "not tested"),
    "none": ("ninguna", "none"),
    "src": ("Fuente: {file} (sha256 {sha}), {run}; juego {game}.", "Source: {file} (sha256 {sha}), {run}; game {game}."),
    "ab_h": ("Habilidades", "Abilities"),
    "ab_lede": ("Las {n} habilidades de game.json con su efecto en el juego (js/data/ability-fx.js). Las que no tienen "
                "efecto propio dan la pasiva genérica: +8 % de daño con los movimientos del tipo principal.",
                "The {n} abilities in game.json with their in-game effect (js/data/ability-fx.js). Those without an "
                "effect of their own give the generic passive: +8 % damage with moves of the main type."),
    "ab_generic": ("Pasiva genérica: +8 % de daño con los movimientos de su tipo principal.",
                   "Generic passive: +8 % damage with moves of its main type."),
    "ab_plus": (" Además, la pasiva genérica de su tipo.", " Also the generic passive of its type."),
    "ab_col": ("Habilidad", "Ability"), "ab_eff": ("Efecto", "Effect"),
    "ns_h": ("Mejores naturalezas por estadística", "Best natures per stat"),
    "ns_lede": ("Para cada estadística, las cuatro naturalezas que la suben un 10 % y la que bajan un 10 %. Criterio de "
                "orden: primero las que más veces lleva una de las {rows} mejores builds del ranking acotado (966 especies); a "
                "igualdad, el orden de game.json. El ranking solo probó la neutra y las que suben el ataque dominante "
                "(Ataque o Ataque especial), así que en Defensa, Defensa especial y Velocidad no hay recuento: van en "
                "el orden de game.json. ",
                "For each stat, the four natures that raise it 10 % and the one each lowers 10 %. Order: first those "
                "used most often by the {rows} best builds of the bounded ranking (966 species); ties keep the game.json "
                "order. The ranking only tried neutral natures and those raising the dominant attack stat (Attack or "
                "Special attack), so Defense, Special defense and Speed have no count and keep the game.json order. "),
    "ns_link": ("Tabla completa de naturalezas", "Full nature table"),
    "ns_col_n": ("Naturaleza", "Nature"), "ns_col_d": ("Baja", "Lowers"),
    "ns_col_w": ("Veces elegida (cuerpo a cuerpo / distancia)", "Times picked (melee / ranged)"),
    "ns_neutral": ("Neutras (sin cambios), veces elegidas: {m} / {r}", "Neutral (no change), times picked: {m} / {r}"),
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


def nature_label(L, nid: str) -> str:
    n = NAT[nid]
    name = n["n"][_i(L)]
    if not n["up"]:
        return name
    return f'{name} (+{STAT[n["up"]][_i(L)]}, −{STAT[n["down"]][_i(L)]})'


def ficha_section(L, dex: int, moves_by: dict) -> str:
    rows = BOUNDED["species"][str(dex)]
    cards = []
    for style in ("melee", "ranged"):
        for avail in ("no_tm", "optimized"):
            b = rows.get(f"{style}|{avail}")
            if not b:
                continue
            atk = " + ".join(escape(move_name(L, m, moves_by)) for m in b["attacks"])
            tms = ", ".join(f'{escape(move_name(L, m, moves_by))} ({L.num(GAME["tmPrices"][m])})' for m in b["tms"]) or t(L, "none")
            cards.append(
                f'<li class="bd-sim"><h3>{escape(t(L, style))} · {escape(t(L, avail))}</h3>'
                f'<p class="bd-sim-moves">{atk}</p><dl>'
                f'<dt>{escape(t(L, "start"))}</dt><dd>{escape(", ".join(move_name(L, m, moves_by) for m in b["start"]))}</dd>'
                f'<dt>{escape(t(L, "ability"))}</dt><dd>{escape(ability_name(L, b["ability"]))}</dd>'
                f'<dt>{escape(t(L, "nature"))}</dt><dd>{escape(nature_label(L, b["nature"]))}</dd>'
                f'<dt>{escape(t(L, "tms"))}</dt><dd>{tms}</dd></dl>'
                f'<p class="bd-sim-metrics">{escape(t(L, "metrics", s=L.dec(b["survival"], 1), kpm=L.dec(b["kpm"], 1), dps=L.dec(b["dps"], 1)))}</p></li>')
    src = BOUNDED["source"]
    return (f'<section class="learn bounded" id="ranking-acotado" aria-labelledby="bnd-h">'
            f'<h2 id="bnd-h">{escape(t(L, "h"))}</h2><p>{escape(t(L, "lede", seeds=BOUNDED["confirmationSeeds"]))}</p>'
            f'<ul class="bd-sim-list">{"".join(cards)}</ul>'
            f'<p class="bd-sim-src">{escape(t(L, "src", file=src["file"], sha=src["sha256"][:12], run=t(L, "run"), game=BOUNDED["gameCommit"][:7]))}</p>'
            f'</section>')


def abilities_section(L) -> str:
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

    def cell(nid: str, stat: str) -> str:
        if stat not in ("pa", "sa"):  # el ranking no probó estas naturalezas: no es un 0
            return escape(t(L, "untested"))
        return f'{w(nid, "melee")} / {w(nid, "ranged")}'

    blocks = []
    for stat in ("pa", "sa", "df", "sd", "spd"):
        ns = sorted((n for n in GAME["natures"] if n["up"] == stat),
                    key=lambda n: (-(w(n["id"], "melee") + w(n["id"], "ranged")), order.index(n["id"])))
        body = "".join(f'<tr><th scope="row">{escape(n["n"][_i(L)])}</th><td class="nat-down">{escape(STAT[n["down"]][_i(L)])}</td>'
                       f'<td>{cell(n["id"], stat)}</td></tr>' for n in ns)
        blocks.append(f'<h3>+{escape(STAT[stat][_i(L)])}</h3><div class="nat-table"><table><thead><tr>'
                      f'<th scope="col">{escape(t(L, "ns_col_n"))}</th><th scope="col">{escape(t(L, "ns_col_d"))}</th>'
                      f'<th scope="col">{escape(t(L, "ns_col_w"))}</th></tr></thead><tbody>{body}</tbody></table></div>')
    neutral = [n["id"] for n in GAME["natures"] if not n["up"]]
    nm = sum(w(n, "melee") for n in neutral)
    nr = sum(w(n, "ranged") for n in neutral)
    return (f'<section class="pv-natures" id="naturalezas-por-estadistica" aria-labelledby="pv-ns-h">'
            f'<h2 id="pv-ns-h">{escape(t(L, "ns_h"))}</h2><p class="lede">{escape(t(L, "ns_lede", rows=BOUNDED["source"]["rows"]))}'
            f'<a href="{home}naturalezas.html">{escape(t(L, "ns_link"))}</a></p>'
            f'{"".join(blocks)}<p>{escape(t(L, "ns_neutral", m=nm, r=nr))}</p></section>')
