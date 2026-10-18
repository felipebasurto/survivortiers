"""Ida y vuelta del enlace de colección. python3 -m unittest build/test_share.py"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ShareLink(unittest.TestCase):
    def test_round_trip(self) -> None:
        script = ROOT / "build" / "test_share.js"
        result = subprocess.run(["node", str(script)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("round-trip ok", result.stdout)
        for name in ("src/share.js", "src/collection.js", "src/app.js", "src/ficha.js"):
            check = subprocess.run(["node", "--check", str(ROOT / name)], capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, name + "\n" + check.stderr)


if __name__ == "__main__":
    unittest.main()
