"""Parecido entre fichas: Jaccard de tejas de palabras sobre el texto visible de cada ficha estática.

    python3 build/dupcheck.py                 # site/ en español
    python3 build/dupcheck.py --lang en

Cada ficha se reduce a sus palabras (sin scripts ni etiquetas), y cada par de fichas se compara por Jaccard de sus
tejas de 5 palabras. Imprime la distribución del parecido, el vecino más parecido de cada ficha y el peso de la
plantilla (tejas que aparecen en más de la mitad de las fichas). Solo biblioteca estándar.
"""
from __future__ import annotations

import argparse
import re
import statistics
import sys
import zlib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHINGLE = 5
TEMPLATE_SHARE = 0.5
WORD = re.compile(r"[^\W\d_]+|\d+", re.UNICODE)
MAIN = re.compile(r"<main\b.*?</main>", re.S | re.I)
NOISE = re.compile(r"<(script|style|svg)\b.*?</\1>|<[^>]+>", re.S | re.I)


def visible_words(html: str) -> list[str]:
    main = MAIN.search(html)
    body = main.group(0) if main else html
    text = NOISE.sub(" ", body)
    return WORD.findall(text.lower())


def shingles(words: list[str], k: int = SHINGLE) -> frozenset[int]:
    return frozenset(zlib.crc32(" ".join(words[i:i + k]).encode("utf8")) for i in range(len(words) - k + 1))


def jaccard(a: frozenset[int], b: frozenset[int]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def pages(site: Path, lang: str) -> dict[str, str]:
    root = site / ("en" if lang == "en" else "") / "pokemon"
    out = {}
    for path in sorted(root.glob("*/index.html")):
        out[path.parent.name] = path.read_text(encoding="utf8")
    return out


def analyse(html_by_slug: dict[str, str]) -> dict:
    words = {s: visible_words(h) for s, h in html_by_slug.items()}
    sets = {s: shingles(w) for s, w in words.items()}
    slugs = sorted(sets)
    doc_freq: Counter[int] = Counter()
    for s in slugs:
        doc_freq.update(sets[s])
    template = {g for g, n in doc_freq.items() if n > TEMPLATE_SHARE * len(slugs)}
    pairs: list[tuple[float, str, str]] = []
    nearest: dict[str, tuple[float, str]] = {s: (0.0, "") for s in slugs}
    for i, a in enumerate(slugs):
        for b in slugs[i + 1:]:
            j = jaccard(sets[a], sets[b])
            pairs.append((j, a, b))
            if j > nearest[a][0]:
                nearest[a] = (j, b)
            if j > nearest[b][0]:
                nearest[b] = (j, a)
    values = [p[0] for p in pairs]
    unique = {s: sets[s] - template for s in slugs}
    unique_pairs = [jaccard(unique[a], unique[b]) for i, a in enumerate(slugs) for b in slugs[i + 1:]]
    q = statistics.quantiles(values, n=100)
    return {
        "pages": len(slugs), "words_median": statistics.median(len(w) for w in words.values()),
        "shingles_median": statistics.median(len(s) for s in sets.values()),
        "template_shingles": len(template),
        "mean": statistics.fmean(values), "median": statistics.median(values), "p90": q[89], "p99": q[98],
        "max": max(values), "over_50": sum(v >= 0.5 for v in values), "over_30": sum(v >= 0.3 for v in values),
        "pairs": len(values), "top": sorted(pairs, reverse=True)[:5], "nearest": nearest,
        "unique_mean": statistics.fmean(unique_pairs), "unique_max": max(unique_pairs),
        "unique_over_30": sum(v >= 0.3 for v in unique_pairs),
    }


def report(lang: str, r: dict) -> str:
    lines = [
        f"[{lang}] {r['pages']} fichas, mediana {r['words_median']:.0f} palabras, {r['shingles_median']:.0f} tejas de 5 por ficha",
        f"  Jaccard entre pares ({r['pairs']}): media {r['mean']:.3f}, mediana {r['median']:.3f}, p90 {r['p90']:.3f}, "
        f"p99 {r['p99']:.3f}, máximo {r['max']:.3f}",
        f"  pares con Jaccard ≥ 0,3: {r['over_30']}; ≥ 0,5: {r['over_50']}",
        f"  plantilla: {r['template_shingles']} tejas presentes en más de la mitad de las fichas",
        f"  sin plantilla: media {r['unique_mean']:.3f}, máximo {r['unique_max']:.3f}, pares ≥ 0,3: {r['unique_over_30']}",
        "  más parecidas:",
    ]
    lines += [f"    {j:.3f}  {a}  ~  {b}" for j, a, b in r["top"]]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", type=Path, default=ROOT / "site")
    ap.add_argument("--lang", choices=("es", "en"), default="es")
    args = ap.parse_args()
    html = pages(args.site, args.lang)
    if len(html) != 966:
        print(f"ERROR: {len(html)} fichas en {args.site}; ejecuta python3 build/render.py", file=sys.stderr)
        return 1
    print(report(args.lang, analyse(html)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
