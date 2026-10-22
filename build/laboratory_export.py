"""Validate bounded attack-lab and ranking artifacts for the site exporter.

All values remain diagnostic observations. In particular, attack DPS is a
fixture measurement and a selected build is not a global optimum.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from build.funnel_export import export_document, legal_initial, seed_set
from build.sim_results import validate_results


def _same_provenance(lab: dict[str, Any], ranking: dict[str, Any], game: dict[str, Any]) -> None:
    for key, label in (("gameCommit", "game commit"), ("engineFingerprint", "engine fingerprint")):
        lab_value, ranking_value = lab.get(key), ranking.get(key)
        if not isinstance(lab_value, str) or not lab_value or lab_value != ranking_value:
            raise ValueError(f"lab and ranking {label} mismatch")
    game_commit = game.get("commit") or game.get("gameCommit")
    if game_commit and ranking.get("gameCommit") != game_commit:
        raise ValueError("ranking game commit does not match game.json")


def export_attacks(lab: dict[str, Any]) -> dict[str, Any]:
    from build.lab_contract import validated_moves
    if lab.get("schema") != 1 or lab.get("kind") != "attack-lab-results":
        raise ValueError("attack lab schema/kind mismatch")
    rows = validated_moves(lab)
    return {
        "schema": 1, "kind": "attack-lab-export", "complete": True,
        "gameCommit": lab["gameCommit"], "engineFingerprint": lab["engineFingerprint"],
        "policyVersion": lab["policyVersion"], "scope": lab["scope"],
        "partialScope": lab["partialScope"], "secondsPerScenario": lab["secondsPerScenario"],
        "rankingReady": False,
        "interpretation": "Fixture DPS and KPM are descriptive measurements; they are not a global optimum.",
        "moves": rows,
    }


def _ranking_as_funnel(ranking: dict[str, Any]) -> dict[str, Any]:
    if ranking.get("schema") != 1 or ranking.get("kind") != "bounded-ranking-results":
        raise ValueError("ranking results schema/kind mismatch")
    if ranking.get("complete") is not True:
        raise ValueError("ranking results are incomplete")
    winners = []
    for row in ranking.get("winners") or []:
        if not isinstance(row, dict):
            raise ValueError("ranking contains a malformed winner row")
        if row.get("complete") is False:
            raise ValueError(f"ranking winner for dex {row.get('dex')} is incomplete")
        if "complete" in row and row["complete"] is not True:
            raise ValueError("ranking row completeness must be true")
        if type(row.get("winnerConfirmed")) is not bool:
            raise ValueError("winnerConfirmed must be boolean")
        config = row.get("configuration") or row.get("config") or {}
        config = dict(config)
        config.setdefault("group", config.get("moves") or [])
        config.setdefault("secondStart", config.get("second"))
        winners.append({
            "dex": row.get("dex", config.get("dex")),
            "status": "best_observed",
            "winnerConfirmed": row["winnerConfirmed"] is True,
            "configuration": config,
            "meanSurvival": row.get("meanSurvival"),
            "meanDamagePerSecond": row.get("meanDamagePerSecond"),
            "meanKills": row.get("meanKills"),
            "pairedConfirmation": row.get("pairedConfirmation"),
        })
    return {
        "schema": 1,
        "kind": "funnel-results",
        "rankingReady": False,
        "gameCommit": ranking.get("gameCommit"),
        "engineFingerprint": ranking.get("engineFingerprint"),
        "policyVersion": ranking.get("policyVersion") or "bounded-ranking-v2",
        "policyHash": ranking.get("policyHash"),
        "planHash": ranking.get("planHash"),
        "seedSets": {
            "screening": ((ranking.get("seedSets") or {}).get("screening")
                          or list((ranking.get("seedSets") or {}).get("A") or [])
                          + list((ranking.get("seedSets") or {}).get("B") or [])),
            "confirmation": ((ranking.get("seedSets") or {}).get("confirmation")
                             or (ranking.get("seedSets") or {}).get("D") or []),
            "A": (ranking.get("seedSets") or {}).get("A") or [],
            "B": (ranking.get("seedSets") or {}).get("B") or [],
            "D": (ranking.get("seedSets") or {}).get("D") or [],
        },
        "winners": winners,
        "controls": [],
        "unavailable": [r for r in ranking.get("unavailable") or [] if isinstance(r, dict)],
    }


def export_ranking(ranking: dict[str, Any], game: dict[str, Any]) -> dict[str, Any]:
    if ranking.get("gameCommit") is None or ranking.get("engineFingerprint") is None:
        raise ValueError("ranking provenance is missing")
    from build.lab_contract import nonnegative
    if ranking.get("policyVersion") != "bounded-ranking-v2":
        raise ValueError("unsupported ranking policy")
    seeds = ranking.get("seedSets") or {}
    sets = []
    for phase, count in (("A", 2), ("B", 8), ("D", 16)):
        values = seeds.get(phase)
        if not isinstance(values, list) or len(values) != count or any(type(v) is not int or not 0 <= v <= 2**32 - 1 for v in values) or len(set(values)) != count:
            raise ValueError(f"invalid {phase} seed set")
        sets.append(set(values))
    if len(set.union(*sets)) != 26:
        raise ValueError("ranking seed sets must be disjoint")
    if "screening" in seeds and set(seeds["screening"]) != sets[0] | sets[1]:
        raise ValueError("screening seeds disagree with A/B")
    if "confirmation" in seeds and set(seeds["confirmation"]) != sets[2]:
        raise ValueError("confirmation seeds disagree with D")
    for winner in ranking.get("winners") or []:
        if not isinstance(winner, dict) or type(winner.get("winnerConfirmed")) is not bool:
            raise ValueError("winnerConfirmed must be boolean")
        if winner["winnerConfirmed"]:
            paired = winner.get("pairedConfirmation") or {}
            if winner.get("status") != "best_observed" or paired.get("seeds") != seeds["D"] or paired.get("n") != 16:
                raise ValueError("winner lacks completed independent confirmation")
        config = winner.get("configuration") or winner.get("config") or {}
        dex = winner.get("dex", config.get("dex"))
        species = next((r for r in game["dex"] if r["dex"] == dex), None)
        group, tms = config.get("group") or config.get("moves") or [], config.get("tms") or []
        if species is None or not group or len(group) > 4 or len(set(group)) != len(group):
            raise ValueError("winner has an invalid species or move group")
        if legal_initial(game, species, group, set(tms)) != group[0]:
            raise ValueError("winner has an illegal opener")
        taught = set(tms) - set(species["pool"]) - {species["start"]}
        if (config.get("branch") == "optimized_tm") != bool(taught):
            raise ValueError("winner TM branch does not match taught moves")
        for key in ("meanSurvival", "meanDamagePerSecond", "meanKills"):
            nonnegative(winner.get(key), key)
    funnel = _ranking_as_funnel(ranking)
    document = export_document(funnel, game)
    document["stock_controls"] = ranking.get("controls") or []
    document["ranking_method"] = {
        "id": "bounded-ranking-v2",
        "status": "diagnostic_only",
        "interpretation": "Best observed among at most 12 candidates per species/style/TM stratum. No global optimum claim.",
    }
    document["provenance"]["policy_version"] = ranking.get("policyVersion")
    seed_sets = ranking.get("seedSets") or {}
    document["experiment"]["seed_sets"] = {
        "screening": seed_set(list(seed_sets.get("A") or []) + list(seed_sets.get("B") or [])),
        "confirmation": seed_set(list(seed_sets.get("D") or [])),
        "paired_confirmation": seed_set(list(seed_sets.get("B") or [])),
    }
    document["experiment"]["score_version"] = "bounded-ranking-v2"
    # Keep the additional measured quantities that the legacy funnel adapter
    # does not model, while retaining its established site result shape.
    winners = [r for r in ranking.get("winners") or [] if isinstance(r, dict)]
    for result in document["results"]:
        dex = result["pokemon"]["dex"]
        build_id = result["build"]["id"]
        winner = next((r for r in winners if r.get("dex", (r.get("config") or {}).get("dex")) == dex and (r.get("configuration") or r.get("config") or {}).get("id") == build_id), None)
        if winner is None:
            continue
        metrics = result["score"]["metrics"]
        result["score"]["version"] = "bounded-ranking-v2"
        result["observed_status"] = winner.get("status", "best_observed")
        result["paired_confirmation"] = winner.get("pairedConfirmation")
        result["mean_damage_per_second"] = winner.get("meanDamagePerSecond")
        result["mean_kills"] = winner.get("meanKills")
        result["exposure_diagnostic"] = winner.get("exposureDiagnostic")
        if winner.get("meanKillsPerMinute") is not None:
            metrics["killsPerMinute"] = nonnegative(winner["meanKillsPerMinute"], "killsPerMinute")
        if winner.get("meanDamagePerSecond") is not None:
            metrics["damagePerSecond"] = float(winner["meanDamagePerSecond"])
        if winner.get("meanKills") is not None:
            metrics["meanKills"] = float(winner["meanKills"])
    return validate_results(document, game)


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print("usage: python3 -m build.laboratory_export <lab.json> <ranking.json> <game.json> <attacks-out.json> <ranking-out.json>", file=sys.stderr)
        return 2
    lab, ranking, game = (json.loads(Path(p).read_text()) for p in argv[1:4])
    _same_provenance(lab, ranking, game)
    attacks = export_attacks(lab)
    results = export_ranking(ranking, game)
    attacks_path = Path(argv[4])
    attacks_path.write_text(json.dumps(attacks, indent=2) + "\n")
    Path(argv[5]).write_text(json.dumps(results, indent=2) + "\n")
    print(f"validated {len(attacks['moves'])} attack rows and {len(results['results'])} ranking rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
