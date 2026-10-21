from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from build.sim_results import validate_results

VARIANT = {"id": "aggro-baseline__coverage-baseline", "aggro": "baseline", "coverage": "baseline"}
AVAILABILITY = {"optimized_tm": "optimized", "optimized_no_tm": "no_tm"}
SCORE_VERSION = "funnel-survival-v1"


def seed_set(ids: list[int]) -> dict[str, Any]:
    ordered = sorted({int(seed) for seed in ids})
    digest = hashlib.sha256(json.dumps(ordered, separators=(",", ":")).encode()).hexdigest()
    return {"ids": ordered, "count": len(ordered), "hash": "sha256:" + digest}


def slug_for(name: str, dex: int) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return text or f"dex-{dex}"


def _species(game: dict[str, Any], dex: int) -> dict[str, Any]:
    species = next((row for row in game.get("dex", []) if row.get("dex") == dex), None)
    if species is None:
        raise ValueError(f"dex {dex} is absent from game.json")
    return species


def _attacks(config: dict[str, Any]) -> list[dict[str, Any]]:
    group = config.get("group") or []
    return [{"id": move_id, "position": index} for index, move_id in enumerate(group, 1)]


def legal_initial(game: dict[str, Any], species: dict[str, Any], group: list[str], tm_ids: set[str]) -> str | None:
    moves = game.get("moves") or {}
    learned = set(species.get("pool") or [])
    types = set(species.get("types") or [])
    start = species.get("start")
    taught = set(species.get("tms") or [])

    def ok(move_id: str) -> bool:
        move = moves.get(move_id) or {}
        if move.get("kind") == "buff":
            return False
        if move_id == start:
            return True
        if move_id in taught and move_id in tm_ids:
            return True
        return move_id in learned and move.get("type") in types

    if group and ok(group[0]):
        return group[0]
    return None


def _build(game: dict[str, Any], species: dict[str, Any], config: dict[str, Any], availability: str) -> dict[str, Any] | None:
    attacks = _attacks(config)
    if not attacks:
        return None
    ability = config.get("ability")
    nature = config.get("nature")
    tms = [] if availability == "no_tm" else list(config.get("tms") or [])
    initial = legal_initial(game, species, [attack["id"] for attack in attacks], set(tms))
    if initial is None:
        return None
    build = {
        "id": config["id"],
        "style": config["build"],
        "availability": availability,
        "attacks": attacks,
        "ability": {"id": ability, "source": f"simulator/data/game.json#/abilities/{ability}"},
        "nature": {"id": nature, "source": f"simulator/data/game.json#/natures/{nature}"},
        "tm_requirements": [
            {"id": tm, "source": f"simulator/data/game.json#/tmPrices/{tm}"} for tm in tms
        ],
        "initial_attacks": [initial],
    }
    second = config.get("secondStart")
    if isinstance(second, str) and second and second != initial and second in {attack["id"] for attack in attacks}:
        if legal_initial(game, species, [second], set(tms)) == second:
            build["initial_attacks"].append(second)
    return build


def _result_row(game: dict[str, Any], dex: int, config: dict[str, Any], availability: str,
                survival: float, confirmation: dict[str, Any]) -> dict[str, Any] | None:
    species = _species(game, dex)
    build = _build(game, species, config, availability)
    if build is None:
        return None
    return {
        "pokemon": {"dex": dex, "slug": slug_for(str(species.get("name") or ""), dex)},
        "build": build,
        "variant": dict(VARIANT),
        "status": "confirmed",
        "winner_confirmed": True,
        "placeholder": False,
        "confirmation_seed_set": {"count": confirmation["count"], "hash": confirmation["hash"]},
        "score": {"version": SCORE_VERSION, "metrics": {"survivalSeconds": float(survival)}},
    }


def _cohorts_from_unavailable(rows: list[dict[str, Any]]) -> dict[tuple[int, str, str], str]:
    found: dict[tuple[int, str, str], str] = {}
    for item in rows:
        variant_id = item.get("variantId")
        if not isinstance(variant_id, str) or not isinstance(item.get("dex"), int):
            continue
        parts = variant_id.split(":")
        if len(parts) != 3 or parts[1] != "base" or parts[2] not in AVAILABILITY:
            continue
        found[(item["dex"], parts[0], AVAILABILITY[parts[2]])] = str(item.get("reason") or "no candidate")
    return found


def export_document(funnel: dict[str, Any], game: dict[str, Any]) -> dict[str, Any]:
    if funnel.get("schema") != 1 or funnel.get("kind") != "funnel-results":
        raise ValueError("funnel results schema/kind mismatch")
    if funnel.get("rankingReady") is not False:
        raise ValueError("funnel rankingReady must stay false")
    seeds = funnel.get("seedSets") or {}
    screening = seed_set(list(seeds.get("screening") or []))
    confirmation = seed_set(list(seeds.get("confirmation") or []))
    winners = [row for row in funnel.get("winners") or [] if isinstance(row, dict)]
    safe: dict[tuple[int, str, str], dict[str, Any]] = {}
    unsafe_reason: dict[tuple[int, str, str], str] = {}
    for winner in winners:
        config = winner.get("configuration") or {}
        branch = config.get("branch")
        style = config.get("build")
        dex = winner.get("dex")
        if branch not in AVAILABILITY or style not in ("melee", "ranged") or not isinstance(dex, int):
            continue
        key = (dex, style, AVAILABILITY[branch])
        if winner.get("winnerConfirmed") is True and winner.get("status") == "best_observed":
            safe[key] = winner
        else:
            unsafe_reason[key] = str(winner.get("status") or "no_safe_candidate")
    missing = _cohorts_from_unavailable(list(funnel.get("unavailable") or []))
    dexes = sorted({key[0] for key in (*safe, *unsafe_reason, *missing)})
    if not dexes:
        raise ValueError("funnel results have no species")
    results = []
    unavailable_variants = []
    for key, winner in safe.items():
        dex, _style, availability = key
        row = _result_row(
            game, dex, winner["configuration"], availability,
            float(winner.get("meanSurvival") or 0), confirmation,
        )
        if row is None:
            unsafe_reason[key] = "web contract cannot represent the lead as a starting attack"
            continue
        results.append(row)
    published = {(row["pokemon"]["dex"], row["build"]["style"], row["build"]["availability"]) for row in results}
    species_with_results = {dex for dex, _style, _availability in published}
    for control in funnel.get("controls") or []:
        config = control.get("configuration") or {}
        style = config.get("build")
        dex = control.get("dex")
        if style not in ("melee", "ranged") or not isinstance(dex, int) or dex in species_with_results:
            continue
        key = (dex, style, "no_tm")
        if key in published:
            continue
        row = _result_row(
            game, dex, config, "no_tm", float(control.get("meanSurvival") or 0), confirmation,
        )
        if row is None:
            continue
        results.append(row)
        published.add(key)
        species_with_results.add(dex)
    for dex in dexes:
        for style in ("melee", "ranged"):
            for availability in ("optimized", "no_tm"):
                key = (dex, style, availability)
                if key in published:
                    continue
                reason = unsafe_reason.get(key) or missing.get(key) or "funnel v1 measures the base role only"
                unavailable_variants.append({
                    "dex": dex,
                    "style": style,
                    "availability": availability,
                    "variant": dict(VARIANT),
                    "reason": reason,
                })
    for row in results:
        if row["build"]["availability"] != "optimized":
            continue
        dex = row["pokemon"]["dex"]
        style = row["build"]["style"]
        match = next((other for other in results
                      if other["pokemon"]["dex"] == dex
                      and other["build"]["style"] == style
                      and other["build"]["availability"] == "no_tm"), None)
        if match:
            row["build"]["no_tm_alternative"] = {
                "build_id": match["build"]["id"],
                "attacks": [attack["id"] for attack in match["build"]["attacks"]],
            }
        else:
            reason = unsafe_reason.get((dex, style, "no_tm")) or missing.get((dex, style, "no_tm")) or "no measured no-TM build"
            row["build"]["no_tm_alternative"] = {"available": False, "reason": reason}
    document = {
        "schema_version": 1,
        "provenance": {
            "game_commit": funnel.get("gameCommit"),
            "engine_fingerprint": funnel.get("engineFingerprint"),
            "policy_version": funnel.get("policyVersion"),
            "policy_hash": funnel.get("policyHash"),
            "plan_hash": funnel.get("planHash"),
        },
        "experiment": {
            "score_version": SCORE_VERSION,
            "seed_sets": {"screening": screening, "confirmation": confirmation},
            "pokemon_dexes": dexes,
            "axes": {"aggro": ["baseline"], "coverage": ["baseline"]},
            "expected_variants": [dict(VARIANT)],
        },
        "results": results,
        "unavailable_cohorts": [],
        "unavailable_variants": unavailable_variants,
        "ranking_method": {"id": "funnel-survival-v1", "status": "diagnostic_only"},
        "optimized_potential": [],
    }
    return validate_results(document, game)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python3 build/funnel_export.py <funnel-results.json> <web.json>", file=sys.stderr)
        return 2
    game_path = Path(__file__).resolve().parents[1] / "simulator" / "data" / "game.json"
    funnel = json.loads(Path(argv[1]).read_text())
    game = json.loads(game_path.read_text())
    document = export_document(funnel, game)
    Path(argv[2]).write_text(json.dumps(document, indent=2) + "\n")
    print(f"validated {len(document['results'])} results, {len(document['unavailable_variants'])} unavailable variants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
