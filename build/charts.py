"""Gráficos en HTML, CSS y SVG, según los principios de Edward Tufte: sin leyendas ni rejillas, etiquetas directas,
gris por defecto y un solo color de acento, título que afirma lo que se ve y un texto alternativo en cada gráfico.
Los estilos están en site/style.css. Las animaciones son CSS, salvo las demos de la página Método, que mueve
site/app.js.

Cada función recibe el idioma (i18n.Lang) y devuelve un <figure> o un fragmento listo para pegar en la página.
"""
from __future__ import annotations

import math
import statistics
from collections.abc import Callable
from html import escape

from catalog import METHOD_KEYS
from i18n import NBSP, Lang

TOTAL = 966
TIER_CUTS = [("S", 1, 30), ("A", 31, 120), ("B", 121, 320), ("C", 321, 620), ("D", 621, 966)]
TIERS = [t for t, _, _ in TIER_CUTS]
PILLAR_KEYS = ("stats", "moves", "typedef", "size")
AGREE_MIN = 0.5  # inicio de la escala del gráfico de coincidencia
WALK_STEPS = 5
RARITY_ODDS = [(1, 45), (2, 30), (3, 17), (4, 6.5), (5, 1.5)]  # % por tirada, de js/data/gacha.js
REL_MAX = 3.0  # fin de la escala de las barras de ataques, en múltiplos de lo normal


def esc(x) -> str:
    return escape(str(x), quote=True)


def _pos(rank: float) -> float:
    return (rank - 1) / (TOTAL - 1) * 100


def _figure(kind: str, title: str, sub: str, body: str, alt: str) -> str:
    return (f'<figure class="fig anim fig-{kind}"><figcaption><h3>{esc(title)}</h3><p>{esc(sub)}</p></figcaption>'
            f'<div class="fig-body" role="img" aria-label="{esc(alt)}">{body}</div></figure>')


def _interactive(kind: str, title: str, sub: str, body: str, attr: str) -> str:
    return (f'<figure class="fig anim fig-{kind}" {attr}><figcaption><h3>{esc(title)}</h3><p>{esc(sub)}</p></figcaption>'
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
    segs = "".join(f'<i class="rb-seg{" on" if t == r["tier"] else ""}" style="flex:{b - a + 1}"></i>'
                   for t, a, b in TIER_CUTS)
    letters = "".join(f'<i style="flex:{b - a + 1}">{t}</i>' for t, a, b in TIER_CUTS)
    ticks = "".join(f'<span style="left:{_pos(n):.2f}%">{n}</span>' for n in (1, 30, 120, 320, 620, 966))
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
    lo, hi = r["p10"], r["p90"]
    key = "band_firm" if hi - lo <= 12 else "band_mid" if hi - lo <= 60 else "band_wide"
    return _figure("band", L.t(key, name=name, lo=lo, hi=hi), L.t("band_sub", total=TOTAL), _band_body(L, r),
                   _band_alt(L, r, name))


def pillars(L: Lang, r: dict, name: str) -> str:
    """Gráfico de puntos: en qué percentil queda en cada pieza de la ficha, de más alto a más bajo."""
    rows = sorted(((L.t(f"pill_{k}"), L.t(f"pill_{k}_p"), r["pillars"][k]) for k in PILLAR_KEYS), key=lambda t: -t[2])
    best, worst = rows[0], rows[-1]
    if best[2] - worst[2] < 0.15:
        title = L.t("pillars_even", name=name)
    else:
        title = L.t("pillars_title", name=name, best=best[1], bv=L.pct(best[2]), worst=worst[1], wv=L.pct(worst[2]))
    out = [f'<div class="lp-ref"><span style="left:50%">{esc(L.t("median"))}</span></div>']
    for i, (label, _, v) in enumerate(rows):
        x = v * 100
        hot = " hot" if i == 0 else ""
        out.append(f'<div class="lp-row" style="--i:{i}"><span class="lp-name">{esc(label)}</span>'
                   f'<span class="lp-track"><i class="lp-line" style="width:{x:.1f}%"></i>'
                   f'<b class="lp-dot{hot}" style="left:{x:.1f}%"></b>'
                   f'<em class="lp-val{hot}" style="left:{x:.1f}%">{L.pct(v)}</em></span></div>')
    alt = f"{name}: " + "; ".join(L.t("pillars_alt_item", label=label, v=round(v * 100)) for label, _, v in rows) + "."
    return _figure("pillars", title, L.t("pillars_sub"), "".join(out), alt)


def _methods_plot(L: Lang, r: dict) -> str:
    final = r["rank"]
    xf = _pos(final)
    rows = [(L.t(f"m_{k}"), _pos(r["methods"][k]), str(r["methods"][k])) for k in METHOD_KEYS]
    return _dotplot((L.t("methods_final", rank=final), xf, _side(xf)), rows, ("1", str(TOTAL)))


def methods(L: Lang, r: dict, name: str) -> str:
    """Un punto por método sobre la escala de puestos 1 a 966, con una línea en el puesto final."""
    final = r["rank"]
    vals = [(L.t(f"m_{k}"), r["methods"][k]) for k in METHOD_KEYS]
    lo, hi = min(v for _, v in vals), max(v for _, v in vals)
    far = max(vals, key=lambda t: abs(t[1] - final))
    title = L.t("methods_same", lo=lo) if hi == lo else L.t("methods_title", name=name, lo=lo, hi=hi)
    sub = L.t("methods_sub") + (L.t("methods_far", label=far[0], v=far[1]) if far[1] != final else L.t("methods_all"))
    alt = L.t("methods_alt", name=name, rank=final) + "; ".join(L.t("methods_alt_item", label=l, v=v) for l, v in vals) + "."
    return _figure("methods", title, sub, _methods_plot(L, r), alt)


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
    body = _dotplot((L.t("sim_median", s=f"{median_s:.0f}"), xm, _side(xm)),
                    [(label, x_of(s), f"{s:.0f} s") for label, s in items], (f"{lo:.0f} s", f"{hi:.0f} s"))
    best_s = items[-1][1]
    diff = best_s - median_s
    if len(items) == 1:
        title = L.t("sim_title_one", s=f"{best_s:.0f}")
    else:
        title = L.t("sim_title_up" if diff >= 0 else "sim_title_down", s=f"{best_s:.0f}", d=f"{abs(diff):.0f}")
    alt = L.t("sim_alt") + "; ".join(f"{label}, {s:.0f} s" for label, s in items) + "."
    return _figure("sim", title, L.t("sim_sub", total=TOTAL), body, alt)


# ================================================================ barras
def bars(items: list[tuple[str, float, str]], title: str, sub: str, alt: str,
         hot: int | set[int] | None = 0, scale: float | None = None) -> str:
    """Barras horizontales: (etiqueta, valor, texto del valor). Las filas `hot` llevan el acento; `scale` fija el 100 %."""
    top = scale or max(v for _, v, _ in items) or 1
    hots = {hot} if isinstance(hot, int) else set(hot or ())
    rows = "".join(
        f'<div class="bar-row" style="--i:{i}"><span class="bar-name">{esc(lbl)}</span>'
        f'<span class="bar-track"><i class="bar-fill{" hot" if i in hots else ""}" style="width:{v / top * 100:.1f}%"></i>'
        f'<em class="bar-val" style="left:{v / top * 100:.1f}%">{esc(txt)}</em></span></div>'
        for i, (lbl, v, txt) in enumerate(items))
    return _figure("bars", title, sub, rows, alt)


def odds(L: Lang) -> str:
    """Probabilidad de cada rareza en una tirada, como en gacha.js."""
    items = [(f"{n}★", p, f"{L.dec(p) if p % 1 else int(p)}{'' if L.en else NBSP}%") for n, p in RARITY_ODDS]
    alt = L.t("odds_alt") + ", ".join(f"{n} {txt}" for n, _, txt in items) + "."
    return bars(items, L.t("odds_title"), L.t("odds_sub"), alt, hot={3, 4}, scale=50)


def composition(L: Lang, gachas: list[dict]) -> str:
    """Una tira por banner con sus Pokémon repartidos por tier, ordenadas por parte de S + A."""
    rows, parts = [], []
    for i, g in enumerate(gachas):
        total = g["poolSize"]
        name = L.banner(g["name"])
        segs = "".join(
            f'<i class="cp-seg t-{t}" style="flex:{g["tiers"][t]}">{t if g["tiers"][t] / total >= 0.07 else ""}</i>'
            for t in TIERS if g["tiers"][t])
        rows.append(f'<div class="cp-row" style="--i:{i}"><span class="cp-name">{esc(name)}</span>'
                    f'<span class="cp-strip">{segs}</span><em class="cp-val">{L.dec(g["sPlusARate"])}%</em></div>')
        parts.append(f"{name}: " + ", ".join(L.t("comp_alt_item", n=g["tiers"][t], t=t) for t in TIERS))
    best, worst = gachas[0], gachas[-1]
    title = L.t("comp_title", a=L.banner(best["name"]), x=round(100 / best["sPlusARate"]),
                b=L.banner(worst["name"]), y=round(100 / worst["sPlusARate"]))
    return _figure("comp", title, L.t("comp_sub"), "".join(rows), L.t("comp_alt") + ". ".join(parts) + ".")


# ================================================================ página Método
def pipeline(L: Lang) -> str:
    steps = [(L.t(f"pipe_{i}"), L.t(f"pipe_{i}t", total=TOTAL)) for i in range(1, 7)]
    items = "".join(f'<li style="--i:{i}"><b>{esc(h)}</b><span>{esc(t)}</span></li>' for i, (h, t) in enumerate(steps))
    alt = L.t("pipe_alt") + "; ".join(f"{i + 1}, {h}" for i, (h, _) in enumerate(steps)) + "."
    return (f'<figure class="fig anim fig-pipe"><figcaption><h3>{esc(L.t("pipe_title"))}</h3>'
            f'<p>{esc(L.t("pipe_sub", total=TOTAL))}</p></figcaption>'
            f'<ol class="pipe" aria-label="{esc(alt)}">{items}</ol></figure>')


def _weights_bar(L: Lang, pieces: list[dict]) -> str:
    segs = "".join(
        f'<div class="wb-seg w{i}" style="flex:{p["weight"]};--i:{i}"><b>{p["weight"]}{"%" if L.en else chr(160) + "%"}</b>'
        f'<span>{esc(L.t("w_" + p["key"]))}</span></div>' for i, p in enumerate(pieces))
    return f'<div class="wb">{segs}</div>'


def weights(L: Lang, pieces: list[dict]) -> str:
    top = max(pieces, key=lambda p: p["weight"])
    alt = L.t("weights_alt") + ", ".join(f'{L.t("w_" + p["key"])} {p["weight"]}%' for p in pieces) + "."
    return _figure("weights", L.t("weights_title", w=top["weight"]), L.t("weights_sub"), _weights_bar(L, pieces), alt)


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
    first, last = cuts[0], cuts[-1]
    alt = L.t("tiers_alt") + ", ".join(f'{c["tier"]} {c["to"] - c["from"] + 1}' for c in cuts) + "."
    title = L.t("tiers_title", s=first["to"], d=last["to"] - last["from"] + 1)
    return _figure("tiers", title, L.t("tiers_sub"), _tier_strip_body(L, cuts), alt)


def gate(L: Lang, gates: list[dict], capped: int) -> str:
    rows = "".join(
        f'<div class="gt-row" style="--i:{i}"><span class="gt-name">{esc(L.t("gate_name", t=g["tier"]))}</span>'
        f'<span class="gt-track"><i class="gt-fill{" hot" if i == 0 else ""}" style="left:{100 - g["top"]}%;'
        f'width:{g["top"]}%"></i></span><em class="gt-val">{esc(L.t("gate_val", top=g["top"]))}</em></div>'
        for i, g in enumerate(gates))
    alt = L.t("gate_alt") + ", ".join(L.t("gate_alt_item", t=g["tier"], top=g["top"]) for g in gates) + "."
    axis = f'<div class="gt-axis" aria-hidden="true"><span>{esc(L.t("gate_worst"))}</span><span>{esc(L.t("gate_best"))}</span></div>'
    return _figure("gate", L.t("gate_title"), L.t("gate_sub", n=capped), rows + axis, alt)


def agreement(L: Lang, items: list[dict]) -> str:
    rows = [(L.t(f"m_{it['key']}"), (it["corr"] - AGREE_MIN) / (1 - AGREE_MIN) * 100, L.dec(it["corr"], 2))
            for it in items]
    hi, lo = max(items, key=lambda i: i["corr"]), min(items, key=lambda i: i["corr"])
    title = L.t("agree_title", hi=L.t(f"m_{hi['key']}"), hv=L.dec(hi["corr"], 2),
                lo=L.t(f"m_{lo['key']}"), lv=L.dec(lo["corr"], 2))
    alt = L.t("agree_alt") + "; ".join(f"{L.t('m_' + i['key'])} {L.dec(i['corr'], 2)}" for i in items) + "."
    return _figure("agree", title, L.t("agree_sub"), _dotplot(None, rows, (L.dec(AGREE_MIN), "1")), alt)


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
    widest = max(med, key=med.get)
    xt = "".join(f'<text x="{x(n):.1f}" y="{h - bottom + 16}" text-anchor="middle">{n}</text>' for n in (1, 120, 320, 620, 966))
    yt = "".join(f'<text x="{left - 8}" y="{y(n) + 4:.1f}" text-anchor="end">{n}</text>' for n in (1, 320, 966))
    tl = "".join(f'<text class="tl" x="{x((a + b) / 2):.1f}" y="{h - bottom + 34}" text-anchor="middle">{t}</text>'
                 for t, a, b in TIER_CUTS)
    cuts = "".join(f'<path class="cut" d="M{x(n + .5):.1f} {h - bottom + 2}v5"/>' for n in (30, 120, 320, 620))
    note = (L.t("rib_note1"), L.t("rib_note2", t=widest, m=med[widest]))
    nt = "".join(f'<text x="{w - right}" y="{y(60) + 17 * i:.0f}" text-anchor="end">{esc(t)}</text>' for i, t in enumerate(note))
    axes = (f'<text class="ax" x="{(left + w - right) / 2:.0f}" y="{h - 4}" text-anchor="middle">{esc(L.t("rib_x"))}</text>'
            f'<text class="ax" transform="translate(12 {(top + h - bottom) / 2:.0f}) rotate(-90)" text-anchor="middle">'
            f'{esc(L.t("rib_y"))}</text>')
    svg = (f'<svg class="rib" viewBox="0 0 {w} {h}" focusable="false" aria-hidden="true">'
           f'<path class="rib-gray" d="{"".join(gray)}"/><path class="rib-hot" d="{"".join(hot)}"/>'
           f'{cuts}{xt}{yt}{tl}{axes}<g class="note">{nt}</g></svg>')
    title = L.t("rib_title", s=med["S"], w=widest, m=med[widest])
    alt = L.t("rib_alt") + ", ".join(L.t("rib_alt_item", t=t, m=med[t]) for t in TIERS) + "."
    return _figure("ribbon", title, L.t("rib_sub"), svg, alt)


def stability(L: Lang, rows: list[dict], firm_share: int) -> str:
    items = [(L.t("tier", t=s["tier"]), s["firm"], L.pcts(s["firm"])) for s in rows]
    best, worst = max(rows, key=lambda s: s["firm"]), min(rows, key=lambda s: s["firm"])
    title = L.t("stab_title", w=worst["tier"], wv=worst["firm"], b=best["tier"], bv=best["firm"])
    return bars(items, title, L.t("stab_sub", share=firm_share),
                L.t("stab_alt") + ", ".join(f'{s["tier"]} {s["firm"]}%' for s in rows) + ".",
                hot=rows.index(worst), scale=100)


def weights_pillars(L: Lang, pillars_: list[dict]) -> str:
    items = [(L.t(f"pill_{p['key']}"), p["weight"], L.pcts(p["weight"])) for p in pillars_]
    alt = L.t("pw_alt") + ", ".join(f'{L.t("pill_" + p["key"])} {p["weight"]}%' for p in pillars_) + "."
    return bars(items, L.t("pw_title"), L.t("pw_sub") + L.t("pw_detail"), alt, scale=100)


def _geo(vals: list[int], ws: list[int]) -> float:
    return math.exp(sum(w * math.log(max(v, 1) / 100) for v, w in zip(vals, ws)) / sum(ws))


def _arith(vals: list[int], ws: list[int]) -> float:
    return sum(w * v / 100 for v, w in zip(vals, ws)) / sum(ws)


def geo_demo(L: Lang, pillars_: list[dict], presets: list[tuple[str, list[int]]]) -> str:
    """Deslizadores de percentil por pieza de la ficha: la media geométrica frente a la aritmética. Lo mueve app.js."""
    ws = [p["weight"] for p in pillars_]
    first = presets[0][1]
    buttons = "".join(f'<button type="button" class="chip-btn" data-v="{",".join(map(str, v))}">{esc(n)}</button>'
                      for n, v in presets)
    sliders = "".join(
        f'<label class="dm-row"><span class="dm-name">{esc(L.t("pill_" + p["key"]))}</span>'
        f'<input type="range" min="1" max="100" value="{v}" data-w="{p["weight"]}" '
        f'aria-label="{esc(L.t("demo_aria", name=L.t("pill_" + p["key"])))}"><output>{L.pcts(v)}</output></label>'
        for p, v in zip(pillars_, first))
    g, a = _geo(first, ws), _arith(first, ws)

    def row(kind: str, label: str, v: float, hot: str) -> str:
        return (f'<div class="bar-row"><span class="bar-name">{esc(label)}</span><span class="bar-track">'
                f'<i class="bar-fill{hot}" data-out="{kind}" style="width:{v * 100:.1f}%"></i>'
                f'<em class="bar-val" data-out-val="{kind}" style="left:{v * 100:.1f}%">{L.pct(v)}</em></span></div>')

    body = (f'<div class="dm-presets"><span>{esc(L.t("demo_try"))}</span>{buttons}</div>'
            f'<div class="dm-sliders">{sliders}</div>'
            f'<div class="dm-out" aria-live="polite">{row("geo", L.t("demo_geo"), g, " hot")}'
            f'{row("arith", L.t("demo_arith"), a, "")}</div>')
    return _interactive("demo", L.t("demo_title"), L.t("demo_sub"), body, "data-demo")


def _reps_row(name: str, p: dict) -> str:
    rank, _, lo, hi, _ = p["r"]
    return (f'<div class="rp-row"><span class="rp-name">{esc(name)}</span><span class="rp-track">'
            f'<i class="rp-band" style="left:{_pos(lo):.2f}%;width:{max(_pos(hi) - _pos(lo), 0.4):.2f}%"></i>'
            f'<i class="rp-med" style="left:{_pos(rank):.2f}%"></i>'
            f'<b class="rp-dot" data-lo="{lo}" data-hi="{hi}" style="left:{_pos(rank):.2f}%"></b></span></div>')


def repeats_demo(L: Lang, rows: list[tuple[str, dict]]) -> str:
    """Puntos que saltan dentro de su rango real (percentiles 10 a 90). Es una ilustración y se avisa en el subtítulo."""
    controls = (f'<div class="rp-ctl"><button type="button" class="btn ghost small" data-play>{esc(L.t("reps_pause"))}</button>'
                f'<output data-count aria-live="off">{esc(L.t("reps_count", n=1, total=L.num(2000)))}</output></div>')
    axis = f'<div class="mt-axis rp-axis" aria-hidden="true"><span>1</span><span>{TOTAL}</span></div>'
    return _interactive("reps", L.t("reps_title"), L.t("reps_sub"),
                        controls + "".join(_reps_row(n, p) for n, p in rows) + axis, "data-reps")


def walk(L: Lang, mons: list[dict], cuts: list[dict], pieces: list[dict]) -> str:
    """«Sigue a un Pokémon»: cinco pasos con los datos reales de cada Pokémon de ejemplo. Lo maneja app.js.
    mons = {name, dex, w, h, index (entrada de pokemon-index), r (ranking completo), assets (prefijo a la raíz)}."""
    chips = "".join(f'<button type="button" class="chip-btn" data-mon="{i}" aria-pressed="{"true" if i == 0 else "false"}">'
                    f'{esc(m["name"])}</button>' for i, m in enumerate(mons))
    panels = []
    for i, m in enumerate(mons):
        r, name = m["r"], m["name"]
        steps = [
            (_walk_plot(_methods_plot(L, r), L.t("methods_alt", name=name, rank=r["rank"])),
             L.t("walk_1_p", name=name, total=TOTAL)),
            (_walk_plot(_weights_bar(L, pieces), ""), L.t("walk_2_p")),
            (_walk_plot(f'<div data-reps data-auto>{_reps_row(name, m["index"])}</div>'
                        f'<div class="mt-axis rp-axis" aria-hidden="true"><span>1</span><span>{TOTAL}</span></div>', ""),
             L.t("walk_3_p", name=name, lo=r["p10"], hi=r["p90"])),
            (_walk_plot(_band_body(L, r), _band_alt(L, r, name)),
             L.t("walk_4_p", rank=r["rank"], total=TOTAL)),
            (_walk_plot(_tier_strip_body(L, cuts, (r["rank"], r["tier"])), L.t("walk_tier_alt", rank=r["rank"])),
             L.t("walk_5_p", rank=r["rank"], tier=r["tier"], share=round(r["pTier"] * 100), name=name)),
        ]
        body = "".join(
            f'<div class="walk-step" data-step="{k}"><h3>{esc(L.t(f"walk_{k + 1}_h"))}</h3><p>{esc(text)}</p>{vis}</div>'
            for k, (vis, text) in enumerate(steps))
        head = (f'<div class="walk-head"><img class="px" src="{m["assets"]}sprites/{m["dex"]}.png" width="{m["w"] * 2}" '
                f'height="{m["h"] * 2}" alt=""><b>{esc(name)}</b>'
                f'<span class="tier-badge {r["tier"]}">{r["tier"]}</span></div>')
        panels.append(f'<div class="walk-mon" data-mon-panel="{i}"{"" if i == 0 else " hidden"}>{head}{body}</div>')
    dots = "".join(f'<button type="button" class="walk-dot" data-go="{k}" aria-label="{esc(L.t("walk_step", i=k + 1, n=WALK_STEPS))}"></button>'
                   for k in range(WALK_STEPS))
    ctl = (f'<div class="walk-ctl"><button type="button" class="btn ghost small" data-prev>{esc(L.t("walk_prev"))}</button>'
           f'<span class="walk-dots">{dots}</span>'
           f'<button type="button" class="btn small" data-next>{esc(L.t("walk_next"))}</button>'
           f'<button type="button" class="btn ghost small" data-auto>{esc(L.t("walk_auto"))}</button>'
           f'<output class="walk-pos" aria-live="polite">{esc(L.t("walk_step", i=1, n=WALK_STEPS))}</output></div>')
    return (f'<figure class="fig anim fig-walk" data-walk><div class="walk-chips">{chips}</div>{"".join(panels)}{ctl}</figure>')


def _walk_plot(inner: str, alt: str) -> str:
    aria = f' role="img" aria-label="{esc(alt)}"' if alt else ""
    return f'<div class="walk-vis"{aria}>{inner}</div>'


def arena(L: Lang, name: str, sprite_src: str) -> str:
    """Ilustración con canvas de una partida simulada. La dibuja app.js. Es una ilustración y no datos."""
    hud = (f'<div class="ar-hud"><span>{esc(L.t("arena_time"))} <b data-t>0</b> s</span>'
           f'<span>{esc(L.t("arena_kills"))} <b data-k>0</b></span>'
           f'<button type="button" class="btn ghost small" data-play>{esc(L.t("reps_pause"))}</button></div>')
    canvas = (f'<canvas class="px" width="320" height="180" data-sprite="{esc(sprite_src)}" role="img" '
              f'aria-label="{esc(L.t("arena_alt"))}"></canvas>')
    return _interactive("arena", L.t("arena_title"), L.t("arena_sub", name=name), canvas + hud, "data-arena")


# ================================================================ ataques
def _level(rel: float, top: float) -> int:
    return 0 if rel >= top else 1 if rel >= 1.15 else 2 if rel >= 0.85 else 3 if rel >= 0.55 else 4


def _rel_row(label: str, rel: float, value: str, word: str, good: bool) -> str:
    x = min(rel, REL_MAX) / REL_MAX * 100
    return (f'<div class="mb-row"><span class="mb-name">{esc(label)}<small>{esc(word)}</small></span>'
            f'<span class="mb-track" aria-hidden="true"><i class="mb-med" style="left:{100 / REL_MAX:.1f}%"></i>'
            f'<i class="mb-fill{" hot" if good else ""}" style="width:{x:.1f}%"></i></span>'
            f'<em class="mb-val">{esc(value)}</em></div>')


def move_bars(L: Lang, rel: dict) -> str:
    """Tres barras de un ataque con daño: daño y aguante al minuto 15 y daño al minuto 5, frente a lo normal."""
    rows = []
    for key, label, words, top in (("dps15", "mv_dps15", "lv_dps_", 1.6), ("ttd15", "mv_ttd15", "lv_ttd_", 1.5),
                                   ("dps5", "mv_dps5", "lv_dps_", 1.6)):
        v = rel[key]
        rows.append(_rel_row(L.t(label), v, f"{L.dec(v)}×", L.t(f"{words}{_level(v, top)}"), v >= 1))
    return f'<div class="mb">{"".join(rows)}</div>'


def buff_bars(L: Lang, buff: dict) -> str:
    """Un potenciador: cuánto cambia el valor de tus ataques al fusionarlo, y el porcentaje de tiempo que está activo."""
    rows = []
    for minute, v in zip((5, 10, 15), buff["fused"]):
        change = round((v - 1) * 100)
        word = L.t("mv_up", v=change) if change > 0 else L.t("mv_down", v=-change) if change < 0 else L.t("mv_same")
        rows.append(_rel_row(L.t("mv_fused", n=minute), v, f"{L.dec(v, 2)}×", word, v >= 1))
    cover = buff["cover"]
    rows.append(f'<div class="mb-row"><span class="mb-name">{esc(L.t("mv_cover"))}<small>{esc(L.t("mv_cover_w"))}</small></span>'
                f'<span class="mb-track" aria-hidden="true"><i class="mb-fill" style="width:{cover}%"></i></span>'
                f'<em class="mb-val">{cover}{"" if L.en else NBSP}%</em></div>')
    return f'<div class="mb">{"".join(rows)}</div>'


def move_scale(L: Lang) -> str:
    """Eje de ejemplo para el cuadro «cómo leer un ataque»: 0, lo normal (×1) y el final de la escala."""
    return (f'<div class="mb-axis" aria-hidden="true"><span class="ax-track"><i style="left:0">0</i>'
            f'<i style="left:{100 / REL_MAX:.1f}%">×1 {esc(L.t("mv_typical"))}</i>'
            f'<i style="left:100%">×{L.dec(REL_MAX, 0)}</i></span></div>')
