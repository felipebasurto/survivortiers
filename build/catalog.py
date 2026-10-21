"""Genera build/out/ (datos intermedios y public/ con los JSON que usa el navegador) a partir de data/: el ranking y las
builds de la fase 3, el porqué de cada puesto (build/why.py), la tier list de ataques de la fase 1, los datos del juego,
los créditos y los sprites.

    python3 build/catalog.py

Aborta (código de salida 1) si algo no cuadra: conteos por tier, un sprite sin artista y licencia,
un Pokémon que falta en alguna fuente o un banner de gacha con un pool inesperado.
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import statistics
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import credits as credits_mod  # noqa: E402
import game_moves  # noqa: E402
import gamestats  # noqa: E402
import legal  # noqa: E402
import tiers  # noqa: E402
import coverage  # noqa: E402

DATA = ROOT / "data"
SPRITES = ROOT / "sprites"
OUT = ROOT / "build" / "out"
PUBLIC = OUT / "public"  # lo que render.py copia a site/data/
V3 = ROOT / "simulator" / "v3" / "v3_data.json"
RESULTS = ROOT / "simulator" / "results"

RANKING_CSV = DATA / "ranking_fase3.csv"
BUILDS_CSV = DATA / "species_builds.csv"
WHY_CSV = DATA / "species_why.csv"
VARIANTS_CSV = DATA / "species_variants.csv"
VARIANTS = ("aggro", "cover")
ATTACKS_CSV = DATA / "attack_tiers.csv"
BONDS_CSV = DATA / "bond_tiers.csv"
VERSION = "fase3"
TIER_CUTS = tiers.CUTS
EXPECTED_COUNTS = tiers.COUNTS
TOTAL = tiers.TOTAL
BUILD_KINDS = ("melee", "ranged")
WHY_FACTORS = ("atk", "group", "hp", "df", "sd", "spd", "size", "types")

# Partidas por grupo y referencia en cada ronda de las fases (build/attack_tiers.py SEEDS, bond_tiers.ROUNDS y
# species_builds.ROUNDS). La fase 1 juega cada ataque en 6 referencias; la fase 2, cada grupo en 6.
PHASE1_REFS, PHASE1_SEEDS = 6, 128
PHASE2_REFS, PHASE2_SEEDS = 6, (2, 16, 64)
PHASE3_SEEDS = (4, 32, 128)
SIM_SECONDS = 900

# gacha.js: probabilidades por tirada de 1★..5★ y orden de búsqueda del pool más cercano.
RATES = [(1, 45.0), (2, 30.0), (3, 17.0), (4, 6.5), (5, 1.5)]
NEAR_ORDER = [0, -1, 1, -2, 2, -3, 3, -4, 4]
BANNERS = {1: "Kanto", 2: "Johto", 3: "Hoenn", 4: "Sinnoh", 5: "Teselia", 6: "Kalos", 7: "Alola", 8: "Galar", 9: "Paldea"}
EXPECTED_POOL = {1: 151, 2: 100, 3: 135, 4: 107, 5: 141, 6: 70, 7: 83, 8: 87, 9: 92}

# Cartas de nivel del juego (js/systems/levelup.js STATS): la que evoluciona cada ataque (needs en v3_data.json).
CARD_NAMES = {"hp": ("Vigor", "Vigor"), "atk": ("Potencia", "Power"), "spd": ("Carrera", "Sprint"),
              "cd": ("Reflejos", "Reflexes"), "def": ("Coraza", "Armor"), "rgn": ("Síntesis", "Synthesis"),
              "mag": ("Imán", "Magnet"), "xp": ("Aprendizaje", "Learning")}


class CatalogError(RuntimeError):
    pass


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def _comment(path: Path) -> str:
    with path.open(encoding="utf8") as f:
        first = f.readline()
    return first[1:].strip() if first.startswith("#") else ""


def tier_of_rank(rank: int) -> str:
    for name, lo, hi in TIER_CUTS:
        if lo <= rank <= hi:
            return name
    raise CatalogError(f"puesto fuera de rango: {rank}")


def png_size(path: Path) -> tuple[int, int]:
    """Ancho y alto de un PNG leyendo su cabecera (sin Pillow, que Vercel no trae)."""
    head = path.read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise CatalogError(f"{path.name} no es un PNG válido")
    return struct.unpack(">II", head[16:24])


def load_moves() -> list[dict]:
    """La tier list de ataques de la fase 1 (data/attack_tiers.csv), con el icono, la mecánica y la evolución del juego."""
    rows = _read_csv(ATTACKS_CSV)
    if not rows:
        raise CatalogError("data/attack_tiers.csv está vacío")
    icons = json.loads((DATA / "move_icons.json").read_text(encoding="utf8"))  # node build/export_move_icons.js
    mechanics = json.loads((DATA / "move_mechanics.json").read_text(encoding="utf8"))  # node build/export_move_mechanics.js
    v3 = json.loads(V3.read_text(encoding="utf8"))["moves"]
    moves = []
    for r in rows:
        mid, game = r["move_id"], gamestats.move(r["move_id"])
        if game["kind"] == "buff":
            raise CatalogError(f"{mid}: la tier list solo lleva ataques (los potenciadores salen del juego)")
        if game["cat"] != r["class"]:
            raise CatalogError(f"{mid}: el juego dice {game['cat']}, la tier list {r['class']}")
        evo, needs = game.get("evo"), v3[mid].get("needs")
        move = {"id": mid, "name": r["name"], "category": r["class"], "tier": r["tier"], "rank": int(r["rank"]),
                "type": r["type"], "kind": r["kind"],
                # El valor de la tier list (score_rel): 1 es el ataque mediano de su categoría, más es mejor.
                "score": round(float(r["score_rel"]), 2),
                "evolvesTo": evo["name"] if evo else None, "needsCard": CARD_NAMES[needs][0] if evo and needs else None,
                "en": {"name": r["name_en"], "evolvesTo": evo["en"] if evo else None,
                       "needsCard": CARD_NAMES[needs][1] if evo and needs else None}}
        icon = icons.get(mid)
        if icon is None:
            raise CatalogError(f"sin icono del juego para {mid!r} (node build/export_move_icons.js)")
        if (icon["type"], icon["kind"]) != (r["type"], r["kind"]):
            raise CatalogError(f"{mid}: el juego dice {icon['type']}/{icon['kind']}, la tier list {r['type']}/{r['kind']}")
        move["icon"] = {"size": icon["size"], "pal": icon["pal"], "rows": icon["rows"]}
        # Cómo se comporta en el juego (node build/export_move_mechanics.js): distingue teledirigido, perforante y salto.
        mech = mechanics.get(mid)
        if mech is None:
            raise CatalogError(f"sin mecánica del juego para {mid!r} (node build/export_move_mechanics.js)")
        move["mech"] = {"homing": mech["homing"], "pierce": mech["pierce"], "count": mech["count"]}
        move["damage"] = game_moves.damage_class(mid, r["kind"])
        moves.append(move)
    return moves


def load_unranked() -> list[dict]:
    """Los potenciadores del juego (data/game_stats.json, en el orden de gamestats.BOOST_ORDER): sin tier ni valor,
    porque la tier list mide ataques; van aparte de moves.json."""
    icons = json.loads((DATA / "move_icons.json").read_text(encoding="utf8"))
    game = gamestats.GAME["moves"]
    buffs = [mid for mid, m in game.items() if m["kind"] == "buff"]
    if sorted(buffs) != sorted(gamestats.BOOST_ORDER):
        raise CatalogError(f"potenciadores del juego {sorted(buffs)} ≠ gamestats.BOOST_ORDER")
    out = []
    for mid in gamestats.BOOST_ORDER:
        g = game[mid]
        icon = icons.get(mid)
        if icon is None:
            raise CatalogError(f"sin icono del juego para {mid!r} (node build/export_move_icons.js)")
        if (icon["type"], icon["kind"]) != (g["type"], g["kind"]):
            raise CatalogError(f"{mid}: el icono dice {icon['type']}/{icon['kind']}, game_stats {g['type']}/{g['kind']}")
        b = g["buff"]
        move = {"id": mid, "name": g["name"], "en": {"name": g["en"]}, "type": g["type"], "kind": g["kind"],
                "damage": game_moves.damage_class(mid, g["kind"]),
                "buff": {"stat": b["stat"], "amount": b["amount"], "stacks": b["stacks"], "dur": b["dur"], "cd": b["cd"],
                         "cover": round(100 * min(1.0, b["dur"] / b["cd"])), "max": b["max"]},
                "icon": {"size": icon["size"], "pal": icon["pal"], "rows": icon["rows"]}}
        if mid in game_moves.NOTES:
            es, en_note = game_moves.NOTES[mid]
            move["note"] = {"es": es, "en": en_note}
        out.append(move)
    return out


def load_shiny(dexes: list[int]) -> set[int]:
    """Pokémon con sprite shiny en el juego: data/shiny_species.json, que hace build/shiny_sprites.py desde el
    sprites-meta.js de JPTER78/pokesurvivor. Aquí solo se comprueba que cuadre con los 966 y con sprites/shiny/."""
    doc = json.loads((DATA / "shiny_species.json").read_text(encoding="utf8"))
    shiny = doc["dex"]
    if shiny != sorted(set(shiny)) or doc["count"] != len(shiny):
        raise CatalogError("data/shiny_species.json: lista sin ordenar, repetida o con un count que no cuadra")
    if sorted(set(shiny) | set(doc["withoutShiny"])) != dexes:
        raise CatalogError("data/shiny_species.json no cubre exactamente los 966 Pokémon de pokedex_export.json")
    gone = [d for d in shiny if not (SPRITES / "shiny" / f"{d}.png").exists()]
    if gone:
        raise CatalogError(f"faltan sprites/shiny/<n>.png para {gone[:5]} (build/shiny_sprites.py --fetch)")
    return set(shiny)


def _build(row: dict) -> dict:
    """Una build de data/species_builds.csv: ataques y potenciadores en el orden del grupo (el primero es con el que
    empieza) y las medianas de sus partidas."""
    ids = row["group"].split("+")
    n_boost = sum(1 for mid in ids if gamestats.move(mid)["kind"] == "buff")
    if any(gamestats.move(mid)["kind"] == "buff" for mid in ids[:len(ids) - n_boost]):
        raise CatalogError(f"{row['dex']} {row['build']}: un potenciador antes de un ataque en {row['group']}")
    cov = coverage.of_build(ids)
    return {"moves": ids, "nBoost": n_boost, "mix": row.get("mix") or _mix(ids), "time": round(float(row["median_s"]), 1),
            "kills": round(float(row["median_kills"]), 1), "dealt": round(float(row["median_dealt"])),
            "score": round(float(row["median_score"]), 1), "lo": round(float(row["score_lo"]), 1),
            "hi": round(float(row["score_hi"]), 1),
            "cover": {"good": cov["good"], "resist": cov["resist"], "by": list(cov["resist_by"])[:2]}}


def _mix(ids: list[str]) -> str:
    cats = {gamestats.move(m)["cat"] for m in ids if gamestats.move(m)["kind"] != "buff"}
    return cats.pop() if len(cats) == 1 else "mixed"


def percentiles(values: dict[int, float], lower_better: bool = False) -> dict[int, int]:
    """Percentil de cada valor entre los 966, 0 el peor y 100 el mejor (los empates cuentan la mitad)."""
    xs = list(values.values())
    out = {}
    for dex, x in values.items():
        below = sum(1 for v in xs if (v > x if lower_better else v < x))
        equal = sum(1 for v in xs if v == x)
        out[dex] = round(100 * (below + equal / 2) / len(xs))
    return out


def load_pokemon(credits: dict, shiny: set[int]) -> list[dict]:
    dex_export = {p["dex"]: p for p in json.load(open(DATA / "pokedex_export.json", encoding="utf8"))}
    v3 = {m["dex"]: m for m in json.loads(V3.read_text(encoding="utf8"))["dex"]}
    names_en = {int(r["dex"]): r["name_en"] for r in _read_csv(DATA / "species_names_en.csv")}
    rows = {int(r["dex"]): r for r in _read_csv(RANKING_CSV)}
    builds: dict[int, dict[str, dict]] = {}
    for r in _read_csv(BUILDS_CSV):
        builds.setdefault(int(r["dex"]), {})[r["build"]] = _build(r)
    # Variantes de cada build (build/species_builds.py --variants): agresiva sin potenciador de defensa y de más
    # cobertura de tipos, cada una con sus cifras de la ronda final.
    for r in _read_csv(VARIANTS_CSV):
        b = builds[int(r["dex"])][r["build"]]
        if b["moves"] != r["main"].split("+"):
            raise CatalogError(f"species_variants.csv: {r['dex']} {r['build']} no parte de la build publicada")
        b.setdefault("alt", {})[r["variant"]] = _build(r)
    why: dict[int, list[dict]] = {}
    for r in _read_csv(WHY_CSV):
        why.setdefault(int(r["dex"]), []).append(
            {"f": r["factor"], "value": float(r["value"]), "pct": int(r["pct"]), "effect": float(r["effect"])})
    dexes = sorted(dex_export)
    for name, table in (("ranking_fase3.csv", rows), ("species_builds.csv", builds), ("species_why.csv", why)):
        if sorted(table) != dexes:
            raise CatalogError(f"{name}: los números de Pokédex no coinciden con pokedex_export.json")
    if any(sorted(b) != sorted(BUILD_KINDS) for b in builds.values()):
        raise CatalogError("species_builds.csv: cada Pokémon lleva una build melee y una ranged")
    if any([w["f"] for w in ws] != list(WHY_FACTORS) for ws in why.values()):
        raise CatalogError(f"species_why.csv: cada Pokémon lleva los factores {WHY_FACTORS} en ese orden")
    # Estadísticas del juego que usa el simulador (v3_data.json) y su percentil entre los 966.
    game = {d: {"hp": v3[d]["hp"], "spd": v3[d]["spd"], "pa": v3[d]["pa"], "sa": v3[d]["sa"], "df": v3[d]["df"],
                "sd": v3[d]["sd"], "size": next(w["value"] for w in why[d] if w["f"] == "size"),
                "types": next(w["value"] for w in why[d] if w["f"] == "types")} for d in dexes}
    pct = {k: percentiles({d: game[d][k] for d in dexes}, lower_better=k in ("size", "types")) for k in game[dexes[0]]}

    entries = []
    for dex in dexes:
        px, row = dex_export[dex], rows[dex]
        name_en = names_en.get(dex)
        if not name_en:
            raise CatalogError(f"sin nombre inglés para el Pokémon {dex}")
        if row["name"] != v3[dex]["name"]:
            raise CatalogError(f"nombre distinto en el ranking y en v3_data.json para {dex}: "
                               f"{row['name']!r} / {v3[dex]['name']!r}")
        sprite_path = SPRITES / f"{dex}.png"
        if not sprite_path.exists():
            raise CatalogError(f"falta el sprite {dex}.png")
        cred = credits_mod.sprite_credit(credits, dex)
        if cred is None:
            raise CatalogError(f"el sprite {dex}.png no tiene artista ni licencia en CREDITS.md")
        w, h = png_size(sprite_path)
        sprite = {"src": f"{dex}.png", "w": w, "h": h, "artist": ", ".join(a["name"] for a in cred["artists"]),
                  "artists": cred["artists"], "license": cred["license"], "licenseUrl": cred["licenseUrl"],
                  "sourceUrl": cred["sourceUrl"]}
        rank = int(row["rank"])
        tier = tier_of_rank(rank)
        if row["tier"] != tier:
            raise CatalogError(f"{dex}: tier del CSV {row['tier']} ≠ {tier} según el puesto {rank}")
        best = builds[dex][row["build"]]
        if best["moves"] != row["group"].split("+"):
            raise CatalogError(f"{dex}: el grupo del ranking no es el de su build {row['build']}")
        entries.append({
            "dex": dex, "name": px["name"], "nameEn": name_en, "types": px["types"],
            "rarity": px["rarity"], "legendary": px["legendary"],
            "bannerId": px["gen"], "banner": px["banner"], "sprite": sprite, "sh": dex in shiny, "bst": v3[dex]["bst"],
            "start": v3[dex]["start"],
            "r": {"rank": rank, "tier": tier, "best": row["build"], "score": best["score"], "lo": best["lo"],
                  "hi": best["hi"], "time": best["time"], "kills": best["kills"], "dealt": best["dealt"]},
            "builds": builds[dex],
            "game": game[dex], "pct": {k: pct[k][dex] for k in pct},
            "why": why[dex],
        })
    return entries


def check_ranks(entries: list[dict]) -> dict:
    """Conteos por tier y que el puesto sea una permutación de 1..966."""
    if sorted(e["r"]["rank"] for e in entries) != list(range(1, TOTAL + 1)):
        raise CatalogError(f"los puestos no son 1..{TOTAL} sin repetir")
    counts = {t: 0 for t, _, _ in TIER_CUTS}
    for e in entries:
        counts[e["r"]["tier"]] += 1
    if counts != EXPECTED_COUNTS:
        raise CatalogError(f"conteos {counts}, esperados {EXPECTED_COUNTS}")
    return counts


def _pull_chance(pool_by_rarity: dict, all_mons: list, good: set) -> float:
    """P(una tirada sale S o A) según gacha.js: rareza por tirada y Pokémon al azar del pool más cercano.
    No cuenta las garantías (×10 con un 4★ y 5★ a las 70 tiradas)."""
    total = 0.0
    for rarity, pct in RATES:
        pool = None
        for d in NEAR_ORDER:
            r = rarity + d
            if 1 <= r <= 5 and pool_by_rarity.get(r):
                pool = pool_by_rarity[r]
                break
        pool = pool or all_mons
        total += pct / 100 * sum(1 for p in pool if p in good) / len(pool)
    return total


def build_gachas(entries: list[dict]) -> list[dict]:
    out = []
    for gen, name in BANNERS.items():
        mons = [e for e in entries if e["bannerId"] == gen]
        if len(mons) != EXPECTED_POOL[gen]:
            raise CatalogError(f"banner {name}: pool de {len(mons)}, esperado {EXPECTED_POOL[gen]}")
        by_rarity: dict[int, list[int]] = {}
        for e in mons:
            by_rarity.setdefault(e["rarity"], []).append(e["dex"])
        good = {e["dex"] for e in mons if e["r"]["tier"] in ("S", "A")}
        s = sum(1 for e in mons if e["r"]["tier"] == "S")
        tiers_n = {t: sum(1 for e in mons if e["r"]["tier"] == t) for t, _, _ in TIER_CUTS}
        out.append({"gen": gen, "name": name, "poolSize": len(mons), "legendaryCount": sum(e["legendary"] for e in mons),
                    "tiers": tiers_n, "sCount": s, "aCount": len(good) - s, "sPlusARate": round(100 * len(good) / len(mons), 1),
                    "pullChance": round(100 * _pull_chance(by_rarity, [e["dex"] for e in mons], good), 1)})
    if sum(g["poolSize"] for g in out) != TOTAL:
        raise CatalogError("los pools de los banners no suman 966")
    return out


def _groups(path: Path) -> set[tuple[str, str]]:
    return {(r["dex"], r["group"]) for r in _read_csv(path)}


def _promoted() -> int:
    """Builds que son una variante que ganó el desempate (data/species_builds.csv frente a rD_pairs.csv)."""
    won = {(r["dex"], r["build"], r["challenger"]) for r in _read_csv(RESULTS / "fase3" / "rD_pairs.csv")}
    return sum((r["dex"], r["build"], r["group"]) in won for r in _read_csv(BUILDS_CSV))


def _lines(path: Path) -> int:
    """Filas de datos de un CSV de resultados (sin la cabecera)."""
    with path.open("rb") as f:
        return sum(chunk.count(b"\n") for chunk in iter(lambda: f.read(1 << 20), b"")) - 1


def score_refs() -> dict:
    """Las dos referencias de la puntuación de una partida (simulator/sim-rs/src/stats.rs run_score)."""
    text = (ROOT / "simulator" / "sim-rs" / "src" / "stats.rs").read_text(encoding="utf8")
    refs = {k: re.search(rf"const {k}_REF: f64 = (\d+(?:\.\d+)?);", text) for k in ("DPS", "KPM")}
    if not all(refs.values()):
        raise CatalogError("stats.rs no define DPS_REF y KPM_REF")
    return {"dpsRef": float(refs["DPS"].group(1)), "kpmRef": float(refs["KPM"].group(1))}


def method_numbers(moves: list[dict]) -> dict:
    """Cuántos ataques, grupos y partidas hay detrás de cada fase, contados en sus salidas guardadas."""
    p1_games = len(moves) * PHASE1_REFS * PHASE1_SEEDS
    bonds = _read_csv(BONDS_CSV)
    cumulative = {s: sum(PHASE2_SEEDS[:i + 1]) for i, s in enumerate(PHASE2_SEEDS)}
    p2_games = sum(PHASE2_REFS * cumulative[int(r["seeds"])] for r in bonds)
    rounds = [_lines(RESULTS / "fase3" / f"r{k}_raw.csv") for k in "ABC"]
    p3_games = sum(n * s for n, s in zip(rounds, PHASE3_SEEDS))
    # Variantes y desempate (species_builds.py --variants y --promote): solo los grupos que no jugó la búsqueda.
    fresh = [len(_groups(RESULTS / "fase3" / f"v{k}_raw.csv") - _groups(RESULTS / "fase3" / f"r{k}_raw.csv"))
             for k in "ABC"]
    duels = _lines(RESULTS / "fase3" / "rD_pairs.csv")
    p3_games += sum(n * s for n, s in zip(fresh, PHASE3_SEEDS)) + 2 * duels * PHASE3_SEEDS[-1]
    return {
        "seconds": SIM_SECONDS, "score": score_refs(),
        "p1": {"attacks": len(moves), "refs": PHASE1_REFS, "seeds": PHASE1_SEEDS, "games": p1_games},
        "p2": {"groups": len(bonds), "refs": PHASE2_REFS, "seeds": list(PHASE2_SEEDS), "games": p2_games,
               "final": sum(1 for r in bonds if int(r["seeds"]) == PHASE2_SEEDS[-1])},
        "p3": {"groups": rounds, "seeds": list(PHASE3_SEEDS), "games": p3_games, "variants": len(_read_csv(VARIANTS_CSV)),
               "duels": duels, "promoted": _promoted()},
        "games": p1_games + p2_games + p3_games,
    }


def why_model() -> dict:
    """R² y pesos del modelo del porqué, de la primera línea de data/species_why.csv (build/why.py)."""
    head = _comment(WHY_CSV)
    r2 = re.search(r"R² (\d+\.\d+)", head)
    if not r2 or "Pesos: " not in head:
        raise CatalogError("data/species_why.csv no lleva el R² y los pesos en la primera línea (build/why.py)")
    weights = dict(part.split() for part in head.split("Pesos: ")[1].split(", "))
    return {"r2": float(r2.group(1)), "weights": {k: float(v) for k, v in weights.items()}}


def build_meta(entries: list[dict], moves: list[dict], credits: dict, counts: dict) -> dict:
    when = os.environ.get("SOURCE_DATE_EPOCH")
    stamp = datetime.fromtimestamp(int(when), timezone.utc) if when else datetime.now(timezone.utc)
    ranked = sorted(entries, key=lambda e: e["r"]["rank"])
    times = sorted(e["r"]["time"] for e in entries)
    longest = max(entries, key=lambda e: e["r"]["time"])
    return {
        "version": VERSION, "generatedAt": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tierCuts": [{"tier": t, "from": a, "to": b} for t, a, b in TIER_CUTS],
        "tierCounts": counts, "total": TOTAL, "gameCommit": legal.GAME_COMMIT,
        "top": [{"dex": e["dex"], "name": e["name"], "nameEn": e["nameEn"]} for e in ranked[:3]],
        "time": {"median": round(statistics.median(times), 1), "min": times[0], "max": times[-1],
                 "maxDex": longest["dex"]},
        "seeds": PHASE3_SEEDS[-1], "method": method_numbers(moves), "why": why_model(),
        "credits": [{"name": a["name"], "url": a["url"], "dex": a["dex"]} for a in credits["artists"]],
        "spriteLicense": {"name": credits_mod.SPRITE_LICENSE["name"], "url": credits_mod.SPRITE_LICENSE["url"],
                          "source": credits_mod.SPRITE_SOURCE["name"], "sourceUrl": credits_mod.SPRITE_SOURCE["url"]},
    }


SIDE = {"physical": "phys", "special": "spec", "mixed": "mix"}


def slim(entries: list[dict]) -> list[dict]:
    """Lo mínimo para la tier list, el buscador y la colección: r = [puesto, tier]; side es phys, spec o mix según los
    ataques de su mejor build; v, los valores por los que se ordena la lista (s = segundos que aguanta).
    bst = suma de stats base del juego (v3_data.json), el orden de featured() en systems/gacha.js."""
    return [{"dex": e["dex"], "name": e["name"], "nameEn": e["nameEn"], "types": e["types"],
             "rarity": e["rarity"], "legendary": e["legendary"], "bannerId": e["bannerId"], "sh": e["sh"],
             "bst": e["bst"], "w": e["sprite"]["w"], "h": e["sprite"]["h"],
             "r": [e["r"]["rank"], e["r"]["tier"]], "side": SIDE[e["builds"][e["r"]["best"]]["mix"]],
             "v": {"s": e["r"]["time"], "pa": e["game"]["pa"], "sa": e["game"]["sa"], "hp": e["game"]["hp"],
                   "spd": e["game"]["spd"], "df": e["game"]["df"], "sd": e["game"]["sd"], "rad": e["game"]["size"]}}
            for e in entries]


def species_public(entries: list[dict]) -> dict:
    """data/species.json: las dos builds de cada Pokémon (melee y ranged) y cuál gana. Lo lee el planificador."""
    lean = {"cover", "alt"}  # solo los usa la ficha
    return {"builds": {str(e["dex"]): {**{k: {f: v for f, v in b.items() if f not in lean} for k, b in e["builds"].items()},
                                       "best": e["r"]["best"]} for e in entries}}


def write_json(name: str, obj, pretty: bool = False, public: bool = False) -> None:
    folder = PUBLIC if public else OUT
    folder.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=1 if pretty else None, separators=None if pretty else (",", ":"))
    (folder / name).write_text(text + "\n", encoding="utf8")


def main() -> int:
    try:
        credits = credits_mod.parse_credits(DATA / "CREDITS.md")
        moves = load_moves()
        unranked = load_unranked()
        dexes = sorted(p["dex"] for p in json.loads((DATA / "pokedex_export.json").read_text(encoding="utf8")))
        entries = load_pokemon(credits, load_shiny(dexes))
        known = {m["id"] for m in moves} | {m["id"] for m in unranked}
        unknown = sorted({mid for e in entries for b in e["builds"].values() for mid in b["moves"]} - known)
        if unknown:
            raise CatalogError(f"movimientos de las builds sin ficha de ataque: {unknown}")
        counts = check_ranks(entries)
        gachas = build_gachas(entries)
        meta = build_meta(entries, moves, credits, counts)
    except (CatalogError, credits_mod.CreditsError, ValueError, KeyError, OSError) as exc:
        print(f"ERROR de catálogo: {exc}", file=sys.stderr)
        return 1
    shutil.rmtree(OUT, ignore_errors=True)
    write_json("pokemon.json", entries)
    write_json("moves.json", moves)
    write_json("moves_unranked.json", unranked)
    write_json("pokemon-index.json", slim(entries), public=True)
    write_json("species.json", species_public(entries), public=True)
    write_json("moves.json", moves, public=True)
    write_json("tiers.json", json.loads((DATA / "tiers.json").read_text(encoding="utf8")), public=True)
    write_json("moves_unranked.json", unranked, public=True)
    write_json("gachas.json", gachas, pretty=True)
    write_json("meta.json", meta, pretty=True)
    print(f"catálogo: {len(entries)} Pokémon, {len(moves)} ataques, {len(gachas)} banners → {OUT}")
    print("  " + " ".join(f"{t} {n}" for t, n in counts.items()))
    print(f"  partidas: {meta['method']['games']:,} · porqué R² {meta['why']['r2']}")
    for g in sorted(gachas, key=lambda g: -g["sPlusARate"]):
        print(f"  {g['name']:8s} pool {g['poolSize']:3d}  S+A {g['sCount'] + g['aCount']:2d}  {g['sPlusARate']:5.1f} %"
              f"  (por tirada {g['pullChance']:.1f} %)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
