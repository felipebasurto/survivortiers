"""Los grupos posibles de cada Pokémon, para las fases 2 y 3 (build/bond_tiers.py, build/species_builds.py).

Cuerpo a cuerpo: el grupo tiene al menos un ataque de tipo `melee` (data/game_stats.json). A distancia: ninguno.

El resto no se decide a mano: cualquier ataque que haga daño, de cualquier categoría, y todas las formas que llenan
los cuatro huecos del vínculo (`picks.BOND_SLOTS`) y que el simulador admite (variants()):
- dos ataques, un potenciador de ataque y uno de defensa (Fortaleza o Agilidad);
- tres ataques y un potenciador de ataque, o tres ataques y uno de defensa.
Un potenciador de ataque solo entra si sube al menos un ataque del grupo (Danza Espada y Danza Dragón los físicos,
Maquinación los especiales; data/v3_data.json `stat`), y Danza Dragón solo si la especie la aprende. Límites del
motor, no reglas: un solo potenciador de ataque y uno de defensa por grupo, cuatro ataques sin potenciador se leen
como "sin grupo fijo", y Acua Aro no está modelado.
"""
from __future__ import annotations

import itertools
import json
from functools import lru_cache
from pathlib import Path

import picks

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEF_BUFFS = ("harden", "agility")


@lru_cache(maxsize=1)
def _pokedex() -> dict[int, dict]:
    return {int(p["dex"]): p for p in json.loads((DATA / "pokedex_export.json").read_text(encoding="utf8"))}


@lru_cache(maxsize=1)
def _game_moves() -> dict[str, dict]:
    return json.loads((DATA / "game_stats.json").read_text(encoding="utf8"))["moves"]


@lru_cache(maxsize=1)
def _sim_pools() -> dict[int, dict]:
    v3 = json.loads((ROOT / "simulator" / "v3" / "v3_data.json").read_text(encoding="utf8"))
    return {int(m["dex"]): m for m in v3["dex"]}


def decent_attacks(dex: int) -> list[str]:
    """Ataques del pool del simulador (y el inicial) que lanzan daño."""
    moves = picks._v3_moves()
    mon = _sim_pools()[dex]
    out = []
    for mid in sorted(set(mon["pool"]) | {mon["start"]}):
        move = moves.get(mid)
        if move is None or move["kind"] == "buff":
            continue
        level = move["levels"][0]
        if (level.get("buff") or 0) != 0 or not float(level.get("dmg") or 0) > 0:
            continue
        out.append(mid)
    return out


def _is_melee(mid: str) -> bool:
    return _game_moves()[mid]["kind"] == "melee"


def attack_buffs(attacks: list[str] | tuple[str, ...], dragon_dance: bool = True) -> list[str]:
    """Potenciadores de ataque que suben al menos uno de estos ataques."""
    cats = {_game_moves()[a]["cat"] for a in attacks}
    return [b for b, side in sorted(picks.attack_buff_side().items())
            if side in cats and (dragon_dance or b != "dragon-dance")]


def variants(attacks: list[str] | tuple[str, ...], dragon_dance: bool = True) -> list[str]:
    """Nombres de grupo de estos ataques (en este orden, el primero abre) con cada relleno de los huecos."""
    attacks = list(attacks)
    atk = attack_buffs(attacks, dragon_dance)
    if len(attacks) == 2:
        return ["+".join([*attacks, a, d]) for a in atk for d in DEF_BUFFS]
    if len(attacks) == 3:
        return ["+".join([*attacks, a]) for a in atk] + ["+".join([*attacks, d]) for d in DEF_BUFFS]
    raise ValueError(f"un grupo tiene dos o tres ataques: {attacks}")


def candidates(dex: int) -> dict[str, str]:
    """group name -> build (melee | ranged) for every group of this species."""
    atk = decent_attacks(dex)
    dd = "dragon-dance" in _sim_pools()[dex]["pool"]
    out: dict[str, str] = {}
    if len(atk) < 2:
        return out
    for pair in itertools.permutations(atk, 2):
        for g in variants(pair, dd):
            out[g] = _kind(list(pair))
    for trio in itertools.combinations(atk, 3):
        for lead in trio:
            for g in variants([lead, *(x for x in trio if x != lead)], dd):
                out[g] = _kind(list(trio))
    return out


def _kind(attacks: list[str]) -> str:
    return "melee" if any(_is_melee(a) for a in attacks) else "ranged"
