"""Exporta el ranking acotado (bounded-ranking-v2) a data/bounded_ranking.json para la web.

    python3 build/bounded_export.py [simulator/runpod-ranking/full/sim-results.json]

La salida completa del simulador (results.json, ~400 MB) no va al repositorio. De sim-results.json se queda, por
especie, la mejor build observada de cada estilo (melee/ranged) y disponibilidad (sin MT / con MT): ataques en orden,
habilidad, naturaleza, MT necesarias y las métricas de confirmación (16 semillas). Las cifras son diagnósticas: la
mejor entre como mucho 12 candidatas por estrato, no un óptimo global. Felipe decidió publicarlas el 22-10-2026 antes
de cerrar Gate 2 (por eso rankingReady va a true aquí y en ningún otro artefacto del simulador).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bounded_ranking.json"
DEFAULT = ROOT / "simulator/runpod-ranking/full/sim-results.json"
if not DEFAULT.exists():
    DEFAULT = DEFAULT.with_suffix(".json.gz")


def export(src: Path) -> dict:
    raw = gzip.decompress(src.read_bytes()) if src.suffix == ".gz" else src.read_bytes()  # sha256 del JSON sin comprimir
    doc = json.loads(raw)
    game = json.loads((ROOT / "simulator/data/game.json").read_text(encoding="utf8"))
    prov = doc["provenance"]
    if prov["game_commit"] != game["gameCommit"]:
        raise SystemExit("sim-results.json no es del commit del juego de simulator/data/game.json")
    species: dict[str, dict] = {}
    natures: Counter = Counter()
    for r in doc["results"]:
        if r["status"] != "confirmed" or r["variant"]["id"] != "aggro-baseline__coverage-baseline":
            raise SystemExit(f"fila inesperada: {r['build']['id']}")
        b, m = r["build"], r["score"]["metrics"]
        key = f'{b["style"]}|{b["availability"]}'
        species.setdefault(str(r["pokemon"]["dex"]), {})[key] = {
            "attacks": [a["id"] for a in sorted(b["attacks"], key=lambda a: a["position"])],
            "start": b["initial_attacks"], "ability": b["ability"]["id"] if b.get("ability") else None,
            "nature": b["nature"]["id"] if b.get("nature") else None,
            "tms": [t["id"] for t in b["tm_requirements"]],
            "survival": round(m["survivalSeconds"], 1), "kpm": round(m["killsPerMinute"], 2),
            "dps": round(m["damagePerSecond"], 1), "kills": round(m["meanKills"], 1)}
        natures[(b["style"], b["nature"]["id"] if b.get("nature") else "hardy")] += 1
    if len(species) != len(game["dex"]):
        raise SystemExit(f"{len(species)} especies, game.json tiene {len(game['dex'])}")
    by_style: dict[str, dict[str, int]] = {}
    for (style, nat), n in sorted(natures.items()):
        by_style.setdefault(style, {})[nat] = n
    return {
        "schema": 1, "kind": "bounded-ranking-site-export", "rankingReady": True,
        "published": "2026-10-22, por decisión de Felipe antes de cerrar Gate 2",
        "method": doc["ranking_method"], "gameCommit": prov["game_commit"],
        "engineFingerprint": prov["engine_fingerprint"], "planHash": prov["plan_hash"],
        "source": {"file": "simulator/runpod-ranking/full/sim-results.json", "sha256": hashlib.sha256(raw).hexdigest(),
                   "run": "Runpod cpu3c 32 vCPU, ranking full con búsqueda de naturalezas (aa98123), 441.486 partidas, 1.717 s",
                   "rows": len(doc["results"])},
        "confirmationSeeds": doc["experiment"]["seed_sets"]["confirmation"]["count"],
        "natureWins": by_style, "species": species,
    }


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    data = export(src)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf8")
    print(f"{OUT}: {len(data['species'])} especies, {data['source']['rows']} builds")
