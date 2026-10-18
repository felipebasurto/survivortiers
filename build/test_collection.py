"""Comando de la consola, lectura de la colección y filas shiny. python3 -m unittest build/test_collection.py"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class CollectionImport(unittest.TestCase):
    def test_node_suite(self) -> None:
        result = subprocess.run(["node", str(ROOT / "build" / "test_collection.js")], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("collection ok", result.stdout)

    def test_syntax(self) -> None:
        for name in ("src/collection.js", "console/coleccion.js", "console/coleccion.en.js"):
            check = subprocess.run(["node", "--check", str(ROOT / name)], capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, name + "\n" + check.stderr)


if __name__ == "__main__":
    unittest.main()
