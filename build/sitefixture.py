"""Renders the site once for the tests that read `site/` or `build/out/`.

A test module calls `ensure_site()` from `setUpModule`. When `site/` is already rendered
nothing happens. Otherwise it runs `build/catalog.py` and `build/render.py`; if that fails
the module is skipped and the reason says what failed, so a missing page never shows up as an
unexplained assertion error.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = ROOT / "build" / "out"
_state: dict[str, str | None] = {}


def _run(script: str) -> str | None:
    proc = subprocess.run([sys.executable, str(ROOT / "build" / script)], cwd=ROOT, capture_output=True, text=True)
    if proc.returncode == 0:
        return None
    tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["no output"]
    return f"{script} failed: {tail[0]}"


def ensure_site(need_site: bool = True) -> None:
    """Render what is missing, or skip the calling module with the reason."""
    if "error" not in _state:
        error = None
        if not (OUT / "public" / "species.json").exists():
            error = _run("catalog.py")
        if error is None and need_site and not (SITE / "index.html").exists():
            error = _run("render.py")
        _state["error"] = error
    elif _state["error"] is None and need_site and not (SITE / "index.html").exists():
        _state["error"] = _run("render.py")
    if _state["error"]:
        raise unittest.SkipTest(f"site could not be rendered ({_state['error']})")
