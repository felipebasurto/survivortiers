"""Gráficos en HTML, CSS y SVG, según los principios de Edward Tufte: sin leyendas ni rejillas, etiquetas directas,
gris por defecto y un solo color de acento, título que afirma lo que se ve y un texto alternativo en cada gráfico.
Los estilos están en src/style.css. Las animaciones son CSS, salvo las demos de la página Método, que mueve
src/app.js. La ficha de cada Pokémon la dibuja src/ficha.js con las mismas fórmulas que pillars(), methods(), rank_band() y sim_dots().

Cada función recibe el idioma (i18n.Lang) y devuelve un <figure> o un fragmento listo para pegar en la página.
"""
from __future__ import annotations

import re
import statistics
from collections.abc import Callable
from html import escape

import tiers
from catalog import METHOD_KEYS
from i18n import Lang

TOTAL = 966
TIER_CUTS = tiers.CUTS
TIERS = [t for t, _, _ in TIER_CUTS]
PILLAR_KEYS = ("stats", "moves", "typedef", "size")
AGREE_MIN = 0.5  # inicio de la escala del gráfico de coincidencia
WALK_STEPS = 5
REL_MAX = 2.0  # fin de la escala de las barras de ataques, en múltiplos de lo normal (el valor más alto es 1,97×)


def esc(x) -> str:
    return escape(str(x), quote=True)


_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def num_html(x) -> str:
    """Texto escapado con las cifras en <span class="n">: la letra pixel confunde el 2 con el 8 y el 5 con la S."""
    return _NUMBER.sub(lambda m: f'<span class="n">{m.group(0)}</span>', esc(x))


def _pos(rank: float) -> float:
    return (rank - 1) / (TOTAL - 1) * 100


def _lede(text: str) -> str:
    return f'<p class="fig-lede">{esc(text)}</p>' if text else ""


def _figure(kind: str, title: str, body: str, alt: str, lede: str = "") -> str:
    return (f'<figure class="fig anim fig-{kind}"><figcaption><h3>{num_html(title)}</h3>{_lede(lede)}</figcaption>'
            f'<div class="fig-body" role="img" aria-label="{esc(alt)}">{body}</div></figure>')


def _interactive(kind: str, title: str, body: str, attr: str, lede: str = "") -> str:
    return (f'<figure class="fig anim fig-{kind}" {attr}><figcaption><h3>{num_html(title)}</h3>{_lede(lede)}</figcaption>'
            f'<div class="fig-body">{body}</div></figure>')


def _dotplot(ref: tuple[str, float, str] | None, rows: list[tuple[str, float, str]], axis: tuple[str, str]) -> str:
    """Un punto por fila sobre una escala común. rows = (etiqueta, posición 0-100, texto del valor);
    ref = (texto, posición, clase de lado) dibuja una línea vertical de referencia en todas las filas."""
    out = []
    if ref:
        text, x, side = ref
        out.append(f'<div class="mt-ref"><span class="{side}" style="left:{x:.2f}%">{esc(text)}</span></div>')
    for i, (label, x, text) in enumerate(rows):
        flip = x > 85
        pos = f"right:{100 - x:.2f}%" if flip else f"left:{x:.2f}%"
        line = f'<i class="mt-final" style="left:{ref[1]:.2f}%"></i>' if ref else ""
        out.append(f'<div class="mt-row" style="--i:{i}"><span class="mt-name">{esc(label)}</span>'
                   f'<span class="mt-track">{line}<b class="mt-dot" style="left:{x:.2f}%"></b>'
                   f'<em class="mt-val{" flip" if flip else ""}" style="{pos}">{esc(text)}</em></span></div>')
    out.append(f'<div class="mt-axis" aria-hidden="true"><span>{esc(axis[0])}</span><span>{esc(axis[1])}</span></div>')
    return "".join(out)


def _side(x: float) -> str:
    return "s-l" if x < 12 else "s-r" if x > 88 else ""


# ================================================================ fichas
def _band_body(L: Lang, r: dict) -> str:
    """Barra de 966 puestos partida en tiers, con el puesto del Pokémon y su rango habitual (percentiles 10 a 90)."""
    rank, lo, hi = r["rank"], r["p10"], r["p90"]
    x = _pos(rank)
    side = "l" if x < 14 else "r" if x > 86 else "c"
    note_style = f"left:{x:.2f}%" if side != "r" else f"right:{100 - x:.2f}%"
    segs = "".join(f'<i class="rb-seg t-{t}{" on" if t == r["tier"] else ""}" style="flex:{b - a + 1}"></i>'
                   for t, a, b in TIER_CUTS)
    letters = "".join(f'<i class="t-{t}" style="flex:{b - a + 1}">{t}</i>' for t, a, b in TIER_CUTS)
    ticks = "".join(f'<span style="left:{_pos(n):.2f}%">{n}</span>' for n in (1, *tiers.EDGES, tiers.TOTAL))
    span = max(_pos(hi) - _pos(lo), 0.5)
    return (f'<div class="rb-note rb-{side}" style="{note_style}"><b>{esc(L.t("band_rank", rank=rank))}</b>'
            f'<span>{esc(L.t("band_range", lo=lo, hi=hi))}</span></div>'
            f'<div class="rb-track">{segs}<b class="rb-range" style="left:{_pos(lo):.2f}%;width:{span:.2f}%"></b>'
            f'<b class="rb-dot" style="left:{x:.2f}%"></b></div>'
            f'<div class="rb-tiers" aria-hidden="true">{letters}</div>'
            f'<div class="rb-ticks" aria-hidden="true">{ticks}</div>')


def _band_alt(L: Lang, r: dict, name: str) -> str:
    return L.t("band_alt", name=name, rank=r["rank"], total=TOTAL, tier=r["tier"], lo=r["p10"], hi=r["p90"])


def rank_band(L: Lang, r: dict, name: str) -> str:
    return _figure("band", L.t("t_band"), _band_body(L, r), _band_alt(L, r, name))


def pillars(L: Lang, r: dict, name: str) -> str:
    """Gráfico de puntos: en qué percentil queda en cada pieza de la ficha, de más alto a más bajo."""
    rows = sorted(((L.t(f"pill_{k}"), r["pillars"][k]) for k in PILLAR_KEYS), key=lambda t: -t[1])
    out = [f'<div class="lp-ref"><span style="left:50%">{esc(L.t("median"))}</span></div>']
    for i, (label, v) in enumerate(rows):
        x = v * 100
        hot = " hot" if i == 0 else ""
        out.append(f'<div class="lp-row" style="--i:{i}"><span class="lp-name">{esc(label)}</span>'
                   f'<span class="lp-track"><i class="lp-line" style="width:{x:.1f}%"></i>'
                   f'<b class="lp-dot{hot}" style="left:{x:.1f}%"></b>'
                   f'<em class="lp-val{hot}" style="left:{x:.1f}%">{L.pct(v)}</em></span></div>')
    alt = f"{name}: " + "; ".join(L.t("pillars_alt_item", label=label, v=round(v * 100)) for label, v in rows) + "."
    return _figure("pillars", L.t("t_pillars"), "".join(out), alt)


def _methods_plot(L: Lang, r: dict) -> str:
    final = r["rank"]
    xf = _pos(final)
    rows = [(L.t(f"m_{k}"), _pos(r["methods"][k]), str(r["methods"][k])) for k in METHOD_KEYS]
    return _dotplot((L.t("methods_final", rank=final), xf, _side(xf)), rows, ("1", str(TOTAL)))


def methods(L: Lang, r: dict, name: str) -> str:
    """Un punto por método sobre la escala de puestos 1 a 966, con una línea en el puesto final."""
    final = r["rank"]
    vals = [(L.t(f"m_{k}"), r["methods"][k]) for k in METHOD_KEYS]
    alt = L.t("methods_alt", name=name, rank=final) + "; ".join(L.t("methods_alt_item", label=l, v=v) for l, v in vals) + "."
    body = f'<p class="fig-lede">{L.t("methods_lede")}</p>' + _methods_plot(L, r)
    return _figure("methods", L.t("t_methods"), body, alt)


def sim_dots(L: Lang, r: dict, sim_range: list[float], median_s: float, mname: Callable[[str], str]) -> str:
    """Segundos que aguanta en la simulación con su ataque inicial y con el mejor, frente a la mediana de todos."""
    lo, hi = sim_range
    sim = r["sim"]
    items = [(L.t("sim_start", name=mname(sim["start"]["id"])), sim["start"]["seconds"])]
    if sim["best"]["id"] != sim["start"]["id"]:
        items.append((L.t("sim_best", name=mname(sim["best"]["id"])), sim["best"]["seconds"]))

    def x_of(s: float) -> float:
        return (s - lo) / (hi - lo) * 100

    xm = x_of(median_s)
    body = (f'<p class="fig-lede">{L.t("sim_lede")}</p>'
            + _dotplot((L.t("sim_median", s=f"{median_s:.0f}"), xm, _side(xm)),
                       [(label, x_of(s), f"{s:.0f} s") for label, s in items], (f"{lo:.0f} s", f"{hi:.0f} s"))
            + f'<p class="fig-note">{L.t("sim_scale", lo=f"{lo:.0f}", hi=f"{hi:.0f}")}</p>')
    alt = L.t("sim_alt") + "; ".join(f"{label}, {s:.0f} s" for label, s in items) + "."
    return _figure("sim", L.t("t_sim"), body, alt)


# ================================================================ barras
def bars(items: list[tuple[str, float, str]], title: str, alt: str,
         hot: int | set[int] | None = 0, scale: float | None = None, lede: str = "", kind: str = "bars") -> str:
    """Barras horizontales: (etiqueta, valor, texto del valor). Las filas `hot` llevan el acento; `scale` fija el 100 %."""
    top = scale or max(v for _, v, _ in items) or 1
    hots = {hot} if isinstance(hot, int) else set(hot or ())
    rows = "".join(
        f'<div class="bar-row" style="--i:{i}"><span class="bar-name">{esc(lbl)}</span>'
        f'<span class="bar-track"><i class="bar-fill{" hot" if i in hots else ""}" style="width:{v / top * 100:.1f}%"></i>'
        f'<em class="bar-val" style="left:{v / top * 100:.1f}%">{esc(txt)}</em></span></div>'
        for i, (lbl, v, txt) in enumerate(items))
    return _figure(kind, title, rows, alt, lede)


# ================================================================ página Método
def pipeline(L: Lang, method: dict) -> str:
    reps = L.num(method["repeats"])
    steps = [L.t(f"pipe_{i}", reps=reps) for i in range(1, 7)]
    items = "".join(f'<li style="--i:{i}"><b>{num_html(h)}</b></li>' for i, h in enumerate(steps))
    alt = L.t("pipe_alt") + "; ".join(f"{i + 1}, {h}" for i, h in enumerate(steps)) + "."
    return (f'<figure class="fig anim fig-pipe"><figcaption><h3>{esc(L.t("pipe_title"))}</h3></figcaption>'
            f'<ol class="pipe" aria-label="{esc(alt)}">{items}</ol></figure>')


def kpis(L: Lang, stats: dict, method: dict) -> str:
    """Cuatro cifras grandes arriba: cuántos Pokémon, cuántas partidas, cuánto juego y cuántas repeticiones."""
    cells = [(L.num(TOTAL), L.t("kpi_pokemon")),
             (f'{L.dec(stats["games"] / 1e6, 2)} M', L.t("kpi_games")),
             (f'{L.num(stats["hours"])} h', L.t("kpi_hours", years=stats["years"])),
             (L.num(method["repeats"]), L.t("kpi_reps"))]
    body = "".join(f'<div class="met-kpi"><b>{num_html(v)}</b><span>{esc(t)}</span></div>' for v, t in cells)
    return f'<div class="met-kpis">{body}</div>'


def stage_games(L: Lang, stages: list[dict]) -> str:
    """Barras de partidas por fase. La de grupos lleva el acento: es casi todo el cálculo."""
    top = max(s["games"] for s in stages)
    total = sum(s["games"] for s in stages)
    hot = max(stages, key=lambda s: s["games"])["id"]
    share = next(s["games"] for s in stages if s["id"] == "group_screen") / total
    rows, alt = [], []
    for i, s in enumerate(stages):
        x = s["games"] / top * 100
        name = L.t(f"stg_{s['id']}")
        detail = L.t(f"stg_d_{s['id']}", per=L.num(s["perSpecies"]), seeds=L.num(s["seeds"]), species=L.num(s["species"]))
        rows.append(f'<div class="bar-row" style="--i:{i}"><span class="bar-name">{esc(name)}<small>{esc(detail)}</small></span>'
                    f'<span class="bar-track"><i class="bar-fill{" hot" if s["id"] == hot else ""}" style="width:{x:.1f}%"></i>'
                    f'<em class="bar-val" style="left:{x:.1f}%">{esc(L.num(s["games"]))}</em></span></div>')
        alt.append(f"{name}, {L.num(s['games'])}")
    lede = L.t("stg_lede", share=L.pct(share), seeds=L.num(stages[-1]["seeds"]))
    return _figure("stages", L.t("stg_title"), "".join(rows), L.t("stg_alt") + "; ".join(alt) + ".", lede)


def _hist(counts: list[int], hot: int, ticks: list[tuple[float, str]], mark: tuple[float, str]) -> str:
    """Barras verticales sin ejes. ticks = (posición en barras, texto); mark = línea de la mediana con su texto."""
    w, h, pl, pr, pt, pb = 760, 230, 18, 18, 34, 34
    n, top = len(counts), max(counts)
    bw = (w - pl - pr) / n
    base = h - pb
    scale = (base - pt) / top
    rects = "".join(f'<rect class="{"hot" if i == hot else ""}" x="{pl + i * bw + 2:.1f}" y="{base - c * scale:.1f}" '
                    f'width="{bw - 4:.1f}" height="{c * scale:.1f}"/>' for i, c in enumerate(counts))
    tk = "".join(f'<text x="{pl + p * bw:.1f}" y="{base + 16}" text-anchor="middle">{esc(t)}</text>' for p, t in ticks)
    mx = pl + mark[0] * bw
    mk = (f'<line class="mk" x1="{mx:.1f}" x2="{mx:.1f}" y1="{pt - 6}" y2="{base}"/>'
          f'<text class="mk-t" x="{mx:.1f}" y="{pt - 12}" text-anchor="middle">{esc(mark[1])}</text>')
    return (f'<svg class="hist" viewBox="0 0 {w} {h}" aria-hidden="true" focusable="false">'
            f'<line class="base" x1="{pl}" x2="{w - pr}" y1="{base}" y2="{base}"/>{rects}{tk}{mk}</svg>')


def start_hist(L: Lang, start: dict) -> str:
    """Pokémon por tramo de segundos que aguanta su apertura (mediana de 16 partidas)."""
    lo, bw, counts, med = start["binStart"], start["binWidth"], start["counts"], start["median"]
    pos = (med - lo) / bw
    ticks = [((v - lo) / bw, str(v)) for v in range(lo, lo + bw * len(counts) + 1, 20)]
    svg = _hist(counts, int(pos), ticks, (pos, L.t("dur_median", s=med)))
    alt = L.t("dur_alt", s=med, lo=start["min"], hi=start["max"])
    body = svg + f'<p class="fig-note">{esc(L.t("dur_axis"))}</p>'
    return _figure("hist", L.t("dur_title"), body, alt,
                   L.t("dur_lede", lo=start["min"], hi=start["max"], cap=L.num(900)))


def _curve(xmax: int, ref: int, x: float, s: float, ox: int, axis: str, ex_label: str, half_label: str) -> str:
    """Una curva de saturación s = v / (v + ref) con su punto de ejemplo. ox desplaza el panel dentro del SVG."""
    pl, pt, pw, ph = 40, 28, 300, 150
    base = pt + ph

    def X(v: float) -> float:
        return ox + pl + v / xmax * pw

    def Y(v: float) -> float:
        return pt + (1 - v) * ph

    pts = [(X(v), Y(v / (v + ref))) for v in range(0, xmax + 1, max(xmax // 60, 1))]
    path = "M" + " L".join(f"{px:.1f} {py:.1f}" for px, py in pts)
    ticks = "".join(f'<text x="{X(v):.1f}" y="{base + 18}" text-anchor="middle">{v}</text>' for v in range(0, xmax + 1, ref))
    yt = "".join(f'<text x="{ox + pl - 8}" y="{Y(v) + 4:.1f}" text-anchor="end">{t}</text>'
                 for v, t in ((0, "0"), (0.5, "0,5"), (1, "1")))
    return (f'<path class="c" d="{path}"/>'
            f'<path class="ref" d="M{X(ref):.1f} {pt}V{base}M{ox + pl} {Y(0.5):.1f}H{X(ref):.1f}"/>'
            f'<text class="lbl" x="{X(ref) + 6:.1f}" y="{pt + 12}">{esc(half_label)}</text>'
            f'<line class="axis" x1="{ox + pl}" x2="{ox + pl + pw}" y1="{base}" y2="{base}"/>'
            f'{ticks}{yt}'
            f'<text class="ax" x="{ox + pl + pw / 2:.0f}" y="{base + 36}" text-anchor="middle">{esc(axis)}</text>'
            f'<circle class="ex" cx="{X(x):.1f}" cy="{Y(s):.1f}" r="5"/>'
            f'<text class="lbl ex-l" x="{X(x) + 9:.1f}" y="{Y(s) + 20:.1f}">{esc(ex_label)}</text>')


def score_curves(L: Lang, score: dict, ex: dict, name: str) -> str:
    """La fórmula de la nota y las dos curvas de saturación, con el Pokémon del puesto 1 sobre ellas."""
    dps_ref, kpm_ref = score["dpsRef"], score["kpmRef"]
    formula = L.t("score_formula", dps=L.num(dps_ref), kpm=L.num(kpm_ref))
    left = _curve(240, dps_ref, ex["dps"], ex["sDps"], 0, L.t("score_dps_axis"),
                  L.t("score_dot", name=name, v=L.num(ex["dps"])), L.t("score_half", v=L.num(dps_ref)))
    right = _curve(120, kpm_ref, ex["kpm"], ex["sKpm"], 400, L.t("score_kpm_axis"),
                   L.t("score_dot", name=name, v=L.num(ex["kpm"])), L.t("score_half", v=L.num(kpm_ref)))
    svg = f'<svg class="curves" viewBox="0 0 760 240" aria-hidden="true" focusable="false">{left}{right}</svg>'
    line = L.t("score_ex", name=name, s=L.num(ex["seconds"]), dps=L.num(ex["dps"]), kpm=L.num(ex["kpm"]),
               sd=L.dec(ex["sDps"], 2), sk=L.dec(ex["sKpm"], 2), score=L.num(ex["score"]))
    body = f'<p class="formula">{esc(formula)}</p>{svg}<p class="fig-note">{esc(line)}</p>'
    alt = L.t("score_alt", dps=L.num(dps_ref), kpm=L.num(kpm_ref))
    return _figure("curves", L.t("score_title"), body, alt,
                   L.t("score_lede", dps=L.num(dps_ref), kpm=L.num(kpm_ref)))


def funnels(L: Lang, stages: dict[str, dict]) -> str:
    """Cuántas aperturas y cuántos grupos prueba de media cada Pokémon antes de quedarse con uno."""
    moves = [(L.t("fm_screen"), stages["start_screen"]["perSpecies"]),
             (L.t("fm_refine"), stages["start_refine"]["perSpecies"]),
             (L.t("fm_duel"), stages["move_duel"]["perSpecies"])]
    groups = [(L.t("fm_screen"), stages["group_screen"]["perSpecies"]),
              (L.t("fm_refine"), stages["group_refine"]["perSpecies"])]
    duel = stages["move_duel"]
    first = bars([(lbl, v, L.num(v)) for lbl, v in moves], L.t("fm_moves_title"),
                 L.t("fm_moves_alt") + "; ".join(f"{lbl}, {v}" for lbl, v in moves) + ".", hot=2,
                 lede=L.t("fm_moves_lede", species=L.num(duel["species"]), seeds=L.num(duel["seeds"])), kind="funnel")
    refine = stages["group_refine"]
    second = bars([(lbl, v, L.num(v)) for lbl, v in groups], L.t("fm_groups_title"),
                  L.t("fm_groups_alt") + "; ".join(f"{lbl}, {v}" for lbl, v in groups) + ".", hot=1,
                  lede=L.t("fm_groups_lede", per=L.num(refine["perSpecies"]), seeds=L.num(refine["seeds"])), kind="funnel")
    return first + second


def width_hist(L: Lang, width: dict) -> str:
    """Cuántos Pokémon tienen cada ancho de margen entre el percentil 10 y el 90 de su puesto."""
    counts, bw, med = width["counts"], width["binWidth"], width["median"]
    pos = med / bw
    ticks = [(p, str(p * bw)) for p in range(0, len(counts), 4)]
    svg = _hist(counts, int(pos), ticks, (pos, L.t("width_median", n=med)))
    body = svg + f'<p class="fig-note">{esc(L.t("width_axis"))}</p>'
    alt = L.t("width_alt", n=med) + "; ".join(f"{p * bw} a {(p + 1) * bw}, {c}" for p, c in enumerate(counts) if c) + "."
    return _figure("hist", L.t("width_title", w=med), body, alt, L.t("width_lede"))


def tier_width(L: Lang, tier_w: dict[str, int]) -> str:
    items = [(L.t("tier", t=t), tier_w[t], L.t("places_n", n=tier_w[t])) for t in TIERS]
    return bars(items, L.t("tw_title"), L.t("tw_alt") + "; ".join(f"{t} {tier_w[t]}" for t in TIERS) + ".",
                hot=None, lede=L.t("tw_lede", s=tier_w["S"], b=tier_w["B"]))


def frontier(L: Lang, stats: dict) -> str:
    """Cuántos Pokémon tienen su margen a caballo de un corte de tier."""
    cuts = stats["straddle"]
    items = [(L.t("front_label", a=c["from"], b=c["to"], edge=c["edge"]), c["count"], L.num(c["count"])) for c in cuts]
    hot = max(range(len(cuts)), key=lambda i: cuts[i]["count"])
    any_n = stats["straddleAny"]
    lede = L.t("front_lede", n=L.num(any_n), total=L.num(TOTAL), pct=L.pct(any_n / TOTAL))
    return bars(items, L.t("front_title"), L.t("front_alt") + "; ".join(f"{t}, {v}" for t, v, _ in items) + ".",
                hot=hot, lede=lede)


def _tier_strip_body(L: Lang, cuts: list[dict], marker: tuple[int, str] | None = None) -> str:
    segs = "".join(f'<i class="ts-seg t-{c["tier"]}{" on" if marker and marker[1] == c["tier"] else ""}" '
                   f'style="flex:{c["to"] - c["from"] + 1}">{c["tier"]}</i>' for c in cuts)
    counts = "".join(f'<i style="flex:{c["to"] - c["from"] + 1}">{c["to"] - c["from"] + 1}</i>' for c in cuts)
    mark = ""
    if marker:
        x = _pos(marker[0])
        mark = f'<b class="ts-mark" style="left:{x:.2f}%"></b>'
    return f'<div class="ts">{segs}{mark}</div><div class="ts-n" aria-hidden="true">{counts}</div>'


def tier_strip(L: Lang, cuts: list[dict]) -> str:
    alt = L.t("tiers_alt") + ", ".join(f'{c["tier"]} {c["to"] - c["from"] + 1}' for c in cuts) + "."
    return _figure("tiers", L.t("tiers_title"), _tier_strip_body(L, cuts), alt)


def ribbon(L: Lang, index: list[dict]) -> str:
    """966 trazos, uno por Pokémon, del percentil 10 al 90 de su puesto en las 2.000 repeticiones."""
    w, h, left, right, top, bottom = 760, 440, 54, 14, 12, 52

    def x(n: float) -> float:
        return left + (n - 1) / (TOTAL - 1) * (w - left - right)

    def y(n: float) -> float:
        return top + (n - 1) / (TOTAL - 1) * (h - top - bottom)

    gray, hot = [], []
    widths: dict[str, list[int]] = {t: [] for t in TIERS}
    for p in index:
        rank, tier, lo, hi, _ = p["r"]
        (hot if tier == "S" else gray).append(f"M{x(rank):.1f} {y(lo):.1f}V{max(y(hi), y(lo) + 1):.1f}")
        widths[tier].append(hi - lo)
    med = {t: round(statistics.median(v)) for t, v in widths.items()}
    xt = "".join(f'<text x="{x(n):.1f}" y="{h - bottom + 16}" text-anchor="middle">{n}</text>' for n in (1, *tiers.EDGES[1:], tiers.TOTAL))
    yt = "".join(f'<text x="{left - 8}" y="{y(n) + 4:.1f}" text-anchor="end">{n}</text>' for n in (1, tiers.EDGES[2], tiers.TOTAL))
    tl = "".join(f'<text class="tl" x="{x((a + b) / 2):.1f}" y="{h - bottom + 34}" text-anchor="middle">{t}</text>'
                 for t, a, b in TIER_CUTS)
    cuts = "".join(f'<path class="cut" d="M{x(n + .5):.1f} {h - bottom + 2}v5"/>' for n in tiers.EDGES)
    axes = (f'<text class="ax" x="{(left + w - right) / 2:.0f}" y="{h - 4}" text-anchor="middle">{esc(L.t("rib_x"))}</text>'
            f'<text class="ax" transform="translate(12 {(top + h - bottom) / 2:.0f}) rotate(-90)" text-anchor="middle">'
            f'{esc(L.t("rib_y"))}</text>')
    svg = (f'<svg class="rib" viewBox="0 0 {w} {h}" focusable="false" aria-hidden="true">'
           f'<path class="rib-gray" d="{"".join(gray)}"/><path class="rib-hot" d="{"".join(hot)}"/>'
           f'{cuts}{xt}{yt}{tl}{axes}</svg>')
    alt = L.t("rib_alt") + ", ".join(L.t("rib_alt_item", t=t, m=med[t]) for t in TIERS) + "."
    return _figure("ribbon", L.t("rib_title"), svg, alt, lede=L.t("rib_lede", s=med["S"], c=med["C"]))


def stability(L: Lang, rows: list[dict]) -> str:
    items = [(L.t("tier", t=s["tier"]), s["firm"], L.pcts(s["firm"])) for s in rows]
    worst = min(rows, key=lambda s: s["firm"])
    return bars(items, L.t("stab_title"), L.t("stab_alt") + ", ".join(f'{s["tier"]} {s["firm"]}%' for s in rows) + ".",
                hot=rows.index(worst), scale=100)


def _reps_row(name: str, p: dict) -> str:
    rank, _, lo, hi, _ = p["r"]
    return (f'<div class="rp-row"><span class="rp-name">{esc(name)}</span><span class="rp-track">'
            f'<i class="rp-band" style="left:{_pos(lo):.2f}%;width:{max(_pos(hi) - _pos(lo), 0.4):.2f}%"></i>'
            f'<i class="rp-med" style="left:{_pos(rank):.2f}%"></i>'
            f'<b class="rp-dot" data-lo="{lo}" data-hi="{hi}" style="left:{_pos(rank):.2f}%"></b></span></div>')


def repeats_demo(L: Lang, rows: list[tuple[str, dict]]) -> str:
    """Ilustración: puntos que saltan dentro de su rango real (percentiles 10 a 90)."""
    controls = (f'<div class="rp-ctl"><button type="button" class="btn ghost small" data-play>{esc(L.t("reps_pause"))}</button>'
                f'<output data-count aria-live="off">{esc(L.t("reps_count", n=1, total=L.num(2000)))}</output></div>')
    axis = f'<div class="mt-axis rp-axis" aria-hidden="true"><span>1</span><span>{TOTAL}</span></div>'
    return _interactive("reps", L.t("reps_title"), controls + "".join(_reps_row(n, p) for n, p in rows) + axis,
                        "data-reps", lede=L.t("reps_lede"))


def arena(L: Lang, sprite_src: str) -> str:
    """Ilustración con canvas de una partida simulada. La dibuja app.js. Es una ilustración y no datos."""
    hud = (f'<div class="ar-hud"><span>{esc(L.t("arena_time"))} <b data-t>0</b> s</span>'
           f'<span>{esc(L.t("arena_kills"))} <b data-k>0</b></span>'
           f'<button type="button" class="btn ghost small" data-play>{esc(L.t("reps_pause"))}</button></div>')
    canvas = (f'<canvas class="px" width="320" height="180" data-sprite="{esc(sprite_src)}" role="img" '
              f'aria-label="{esc(L.t("arena_alt"))}"></canvas>')
    return _interactive("arena", L.t("arena_title"), canvas + hud, "data-arena", lede=L.t("arena_lede"))


# ================================================================ ataques
def _level(rel: float, top: float) -> int:
    return 0 if rel >= top else 1 if rel >= 1.15 else 2 if rel >= 0.85 else 3 if rel >= 0.55 else 4


def _rel_row(label: str, rel: float, value: str, good: bool) -> str:
    x = min(rel, REL_MAX) / REL_MAX * 100
    return (f'<div class="mb-row"><span class="mb-name">{esc(label)}</span>'
            f'<span class="mb-track" aria-hidden="true"><i class="mb-med" style="left:{100 / REL_MAX:.1f}%"></i>'
            f'<i class="mb-fill{" hot" if good else ""}" style="width:{x:.1f}%"></i></span>'
            f'<em class="mb-val">{esc(value)}</em></div>')


def move_bars(L: Lang, score: float) -> str:
    """Una barra por ataque: su valor frente a un movimiento normal (1×). La raya vertical es el 1×."""
    return f'<div class="mb">{_rel_row(L.t("mv_value"), score, f"{L.dec(score, 2)}×", score >= 1)}</div>'


def move_scale(L: Lang) -> str:
    """Leyenda de las barras: rojo por encima de lo normal, gris por debajo y la raya vertical es lo normal (×1)."""
    return (f'<div class="mv-key" aria-hidden="true"><span><i class="k-bar hot"></i>{esc(L.t("mv_better"))}</span>'
            f'<span><i class="k-bar"></i>{esc(L.t("mv_worse"))}</span>'
            f'<span><i class="k-tick"></i>{esc(L.t("mv_typical"))}</span></div>')
