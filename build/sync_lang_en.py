#!/usr/bin/env python3
"""Adds every move of data/game_stats.json, and the move it evolves into, to data/lang_en_moves.json
('moves': Spanish name -> English).

game_stats.json already carries the English name the game shows (js/data/lang-en.js through
build/export_game_stats.js). Entries already in the file are checked, not overwritten.

    node build/export_game_stats.js /ruta/pokesurvivor
    python3 build/sync_lang_en.py
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    path = DATA / "lang_en_moves.json"
    lang = json.loads(path.read_text(encoding="utf8"))
    stats = json.loads((DATA / "game_stats.json").read_text(encoding="utf8"))
    added = 0
    names = [(m["name"], m["en"]) for m in stats["moves"].values()]
    names += [(m["evo"]["name"], m["evo"]["en"]) for m in stats["moves"].values() if "evo" in m]
    for es, en in names:
        have = lang["moves"].get(es)
        if have is None:
            lang["moves"][es] = en
            added += 1
        elif have != en:
            raise SystemExit(f"{es}: {have!r} in lang_en_moves.json, {en!r} in game_stats.json")
    lang["moves"] = dict(sorted(lang["moves"].items()))
    path.write_text(json.dumps(lang, ensure_ascii=False, indent=1) + "\n", encoding="utf8")
    print(f"lang_en_moves.json: {added} moves added, {len(lang['moves'])} in total")


if __name__ == "__main__":
    main()
