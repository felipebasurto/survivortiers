"""Tier cuts, read from data/tiers.json. Every build script imports them from here; the
ficha page fetches the same file (data/tiers.json in the published site)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_RAW = json.loads((ROOT / "data" / "tiers.json").read_text(encoding="utf8"))

CUTS = [(t, int(a), int(b)) for t, a, b in _RAW["cuts"]]
BANDS = {t: (a, b) for t, a, b in CUTS}
COUNTS = {t: b - a + 1 for t, a, b in CUTS}
TOTAL = CUTS[-1][2]
TIER_OF = {rank: t for t, a, b in CUTS for rank in range(a, b + 1)}
EDGES = [b for _, _, b in CUTS[:-1]]
