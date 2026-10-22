"""Shared boundary checks for laboratory artifacts and their display export."""
from __future__ import annotations

import math
from typing import Any

SCENARIOS = [("boss", 1)] + [(shape, count) for shape in ("line", "surround", "approach") for count in (3, 12)]
PHASES = ("initial", "maximum")
EFFECTS = ("burn", "poison", "slow", "hex", "stun", "knockback", "pull", "drain", "bounce")


def nonnegative(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"invalid {label}")
    return float(value)


def validated_moves(document: dict[str, Any]) -> list[dict[str, Any]]:
    if document.get("complete") is not True:
        raise ValueError("attack lab is incomplete")
    if document.get("policyVersion") != "attack-lab-v1":
        raise ValueError("unsupported attack lab fixture policy")
    for key in ("gameCommit", "engineFingerprint"):
        if not isinstance(document.get(key), str) or not document[key]:
            raise ValueError(f"attack lab {key} is missing")
    scope = document.get("scope")
    if scope not in ("all-supported-attacks", "filtered-moves") or document.get("partialScope") is not (scope == "filtered-moves"):
        raise ValueError("attack lab scope is inconsistent")
    seconds = nonnegative(document.get("secondsPerScenario"), "scenario duration")
    if seconds <= 0:
        raise ValueError("scenario duration must be positive")
    rows = document.get("moves")
    if not isinstance(rows, list) or not rows:
        raise ValueError("attack lab has no completed move rows")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("attack lab contains a malformed move row")
        if "complete" in row and row["complete"] is not True:
            raise ValueError(f"attack lab move {row.get('id')} is incomplete")
        mid = row.get("id")
        if not isinstance(mid, str) or not mid or mid in seen:
            raise ValueError("attack lab move ids must be unique")
        seen.add(mid)
        for key in ("score", "earlyScore", "lateScore"):
            nonnegative(row.get(key), f"{mid} {key}")
        effects = row.get("effects", [])
        if not isinstance(effects, list) or any(e not in EFFECTS for e in effects) or len(set(effects)) != len(effects):
            raise ValueError(f"{mid}: invalid effects")
        scenarios = row.get("scenarios")
        if not isinstance(scenarios, list) or len(scenarios) != 14:
            raise ValueError(f"{mid}: expected seven scenarios at two move levels")
        expected = {f"{shape}-{count}-{phase}" for shape, count in SCENARIOS for phase in PHASES}
        observed: set[str] = set()
        common_seeds = None
        phase_levels: dict[str, int] = {}
        for scenario in scenarios:
            if not isinstance(scenario, dict) or scenario.get("id") not in expected or scenario["id"] in observed:
                raise ValueError(f"{mid}: duplicate or unknown scenario")
            observed.add(scenario["id"])
            phase = scenario.get("phase")
            level = scenario.get("level")
            if phase not in PHASES or not scenario["id"].endswith("-" + phase):
                raise ValueError(f"{mid}: invalid scenario phase")
            if isinstance(level, bool) or not isinstance(level, int) or level < 1 or (phase == "initial" and level != 1):
                raise ValueError(f"{mid}: invalid scenario level")
            if phase in phase_levels and phase_levels[phase] != level:
                raise ValueError(f"{mid}: inconsistent move levels")
            phase_levels[phase] = level
            for key in ("damagePerSecond", "killsPerMinute"):
                nonnegative(scenario.get(key), f"{mid} scenario {key}")
            seeds = scenario.get("seeds")
            if not isinstance(seeds, list) or len(seeds) != 2 or any(type(seed) is not int or seed < 0 or seed > 2**32 - 1 for seed in seeds) or len(set(seeds)) != 2:
                raise ValueError(f"{mid}: expected two unique integer seeds")
            if common_seeds is not None and seeds != common_seeds:
                raise ValueError(f"{mid}: inconsistent scenario seeds")
            common_seeds = seeds
        if observed != expected:
            raise ValueError(f"{mid}: missing scenarios")
        for phase, key in (("initial", "earlyScore"), ("maximum", "lateScore")):
            mean = sum(s["damagePerSecond"] for s in scenarios if s["phase"] == phase) / 7
            if not math.isclose(mean, row[key], rel_tol=1e-9, abs_tol=1e-8):
                raise ValueError(f"{mid}: {key} does not match measured scenarios")
        if not math.isclose((row["earlyScore"] + row["lateScore"]) / 2, row["score"], rel_tol=1e-9, abs_tol=1e-8):
            raise ValueError(f"{mid}: headline does not match measured scenarios")
    return rows
