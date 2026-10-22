"""Only complete, full-duration laboratory measurements may appear on the moves page."""
from __future__ import annotations

from typing import Any


def laboratory_rows(document: dict[str, Any], game_commit: str) -> dict[str, dict[str, Any]]:
    try:
        from .lab_contract import validated_moves
    except ImportError:
        from lab_contract import validated_moves
    if document.get("schema") != 1 or document.get("kind") != "attack-lab-export":
        raise ValueError("expected a completed attack-lab-export")
    rows = validated_moves(document)
    if document["gameCommit"] != game_commit:
        raise ValueError("laboratory provenance does not match the pinned game")
    if document["partialScope"] or document["secondsPerScenario"] != 60:
        raise ValueError("moves page requires a full-scope, 60-second laboratory run")
    return {row["id"]: row for row in rows}
