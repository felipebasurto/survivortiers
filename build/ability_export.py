"""Exporta el efecto de cada habilidad a data/abilities.json desde el código del juego en el commit fijado.

    python3 build/ability_export.py /ruta/a/pokesurvivor   # checkout en ce57853

Efecto en español: js/data/ability-fx.js (build/sim_export.parse_ability_effects). Inglés: el diccionario de
js/data/lang-en.js. Las habilidades sin entrada en FX dan la pasiva genérica del juego (+8 % con su tipo principal).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build.sim_export import parse_ability_effects  # noqa: E402

OUT = ROOT / "data" / "abilities.json"
ALIASES = {"pure-power": "huge-power", "libero": "protean"}  # ability-fx.js: FX['pure-power'] = FX['huge-power'] ...


def main(game_dir: Path) -> None:
    game = json.loads((ROOT / "simulator/data/game.json").read_text(encoding="utf8"))
    head = subprocess.run(["git", "-C", str(game_dir), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != game["gameCommit"]:
        raise SystemExit(f"el juego está en {head}, game.json espera {game['gameCommit']}")
    fx = parse_ability_effects(game_dir / "js/data/ability-fx.js")
    en_text = (game_dir / "js/data/lang-en.js").read_text(encoding="utf8")
    en = {}
    for q in ("'", '"'):
        pat = rf"{q}((?:[^{q}\\]|\\.)*){q}\s*:\s*{q}((?:[^{q}\\]|\\.)*){q}"
        for a, b in re.findall(pat, en_text):
            en.setdefault(a.replace("\\'", "'"), b.replace("\\'", "'"))
    fx_text = (game_dir / "js/data/ability-fx.js").read_text(encoding="utf8")
    # contact(fn, 'texto'): el parser toma el primer literal (un color); el texto es el último argumento.
    for aid, desc in re.findall(r"'([a-z0-9-]+)'\s*:\s*contact\(.*,\s*'([^']+)'\)\s*,?\s*$", fx_text, re.M):
        fx[aid] = {"effect": desc, "plus_type_fallback": (fx.get(aid) or {}).get("plus_type_fallback", False)}
    types_es = [k for k in ("Acero", "Agua", "Bicho", "Dragón", "Eléctrico", "Fantasma", "Fuego", "Hada", "Hielo", "Lucha",
                            "Planta", "Psíquico", "Roca", "Siniestro", "Tierra", "Veneno", "Volador", "Normal") if k in en]

    def to_en(es: str):
        if es in en:
            return en[es]
        for ty in types_es:
            key = re.sub(rf"\b{ty}\b", "{x}", es, count=1)
            if key != es and key in en:
                return en[key].replace("{x}", en[ty])
        return None
    out = {}
    for aid, names in sorted(game["abilities"].items()):
        e = fx.get(aid) or fx.get(ALIASES.get(aid, ""))
        es = e["effect"] if e else None
        out[aid] = {"n": names[:2], "es": es, "en": to_en(es) if es else None,
                    "plus": bool(e and e.get("plus_type_fallback")), "generic": e is None}
    OUT.write_text(json.dumps({"gameCommit": head, "abilities": out}, ensure_ascii=False, indent=0, sort_keys=True) + "\n",
                   encoding="utf8")
    miss = [a for a, v in out.items() if v["es"] and not v["en"]]
    print(f"{OUT}: {len(out)} habilidades, {sum(not v['generic'] for v in out.values())} con efecto propio; sin inglés: {len(miss)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
