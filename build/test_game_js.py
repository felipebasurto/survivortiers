"""The sim's damage, types, spawn rate and Sentencia match the game's own JS.

The game files are the read-only snapshot in simulator/vendor/pokesurvivor-5a23d49
(JPTER78/pokesurvivor @ 5a23d49). simulator/validate/game_formulas.js executes them.

    python3 build/test_game_js.py
"""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class GameFormulas(unittest.TestCase):
    def test_vendored_commit_and_engine(self):
        pin = (ROOT / "simulator/vendor/pokesurvivor-5a23d49/COMMIT").read_text().strip()
        self.assertEqual(pin, "5a23d49")
        binary = ROOT / "simulator/sim-rs/target/release/pokesim"
        if not binary.exists():
            subprocess.run(
                ["cargo", "build", "--release", "--manifest-path", str(ROOT / "simulator/sim-rs/Cargo.toml")],
                check=True,
            )
        node = shutil.which("node")
        self.assertIsNotNone(node)
        proc = subprocess.run(
            ["node", str(ROOT / "simulator/validate/game_formulas.js"), str(binary)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("game formulas match the sim", proc.stdout)


if __name__ == "__main__":
    unittest.main()
