"""Genera build/out/ (datos intermedios y public/ con los JSON que usa el navegador) a partir de data/ (ranking definitivo, pokedex_export.json, créditos, movimientos).

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

import combos  # noqa: E402
import passives  # noqa: E402
import credits as credits_mod  # noqa: E402
import game_moves  # noqa: E402
import legal  # noqa: E402
import objetos  # noqa: E402
import summaries  # noqa: E402
import summary_facts  # noqa: E402

DATA = ROOT / "data"
SPRITES = ROOT / "sprites"
OUT = ROOT / "build" / "out"
PUBLIC = OUT / "public"  # lo que render.py copia a site/data/

RANKING_CSV = "ranking_definitive.csv"
VERSION = "definitivo"
TIER_CUTS = [("S", 1, 30), ("A", 31, 120), ("B", 121, 320), ("C", 321, 620), ("D", 621, 966)]
EXPECTED_COUNTS = {"S": 30, "A": 90, "B": 200, "C": 300, "D": 346}
TOTAL = 966
# Simulación de grupo fijo que usa el ranking (make_definitive.py): la mediana de cada Pokémon sale de sus partidas.
SIM_RANK = ROOT / "simulator" / "results" / "fixed_group" / "g2p2" / "rank_200.csv"
PRESETS = ("Kyurem", "Keldeo", "Pikachu")  # ejemplos del deslizador de la página Método
FIRM = 0.8  # un tier es «firme» si el Pokémon cae en él en al menos el 80 % de las repeticiones

# gacha.js: probabilidades por tirada de 1★..5★ y orden de búsqueda del pool más cercano.
RATES = [(1, 45.0), (2, 30.0), (3, 17.0), (4, 6.5), (5, 1.5)]
NEAR_ORDER = [0, -1, 1, -2, 2, -3, 3, -4, 4]
BANNERS = {1: "Kanto", 2: "Johto", 3: "Hoenn", 4: "Sinnoh", 5: "Teselia", 6: "Kalos", 7: "Alola", 8: "Galar", 9: "Paldea"}
EXPECTED_POOL = {1: 151, 2: 100, 3: 135, 4: 107, 5: 141, 6: 70, 7: 83, 8: 87, 9: 92}

# Estructura numérica del método. Los textos de cada pieza viven en build/i18n.py (claves w_*, pill_*, m_*).
METHOD = {
    "pieces": [{"key": "sheet", "weight": 45}, {"key": "sim", "weight": 30}, {"key": "late", "weight": 25}],
    "pillars": [{"key": "stats", "weight": 45}, {"key": "moves", "weight": 25},
                {"key": "typedef", "weight": 15}, {"key": "size", "weight": 15}],
    "gates": [{"tier": "S", "top": 40}, {"tier": "A", "top": 60}, {"tier": "B", "top": 80}],
    # Requisitos extra de entrada (make_definitive.py: TYPES_GATE y NO_MELEE_TIERS).
    "typesMin": {"S": 3},          # ataques de al menos tres tipos distintos
    "noMeleeTiers": ["S"],         # S excluye a quien sigue en cuerpo a cuerpo tras Repertorio y 3 Vetos
    "repeats": 2000,
}
METHOD_KEYS = ("sheet", "simStart", "simBest", "lateMax", "lateFresh")


class CatalogError(RuntimeError):
    pass


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf8", newline="") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


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


BUFF_RE = re.compile(
    r"^(?P<type>[^,]+), potenciador: hasta \+(?P<amount>\d+(?:,\d+)?)(?P<pct> %)? de (?P<stat>\w+) "
    r"con todas las acumulaciones a nivel máximo, dura (?P<dur>\d+) s con recarga de (?P<cd>\d+(?:,\d+)?) s "
    r"\(cobertura (?P<cover>\d+) %\)\. Fusionado con tus ataques multiplica su valor "
    r"×(?P<g5>\d+(?:,\d+)?) / ×(?P<g10>\d+(?:,\d+)?) / ×(?P<g15>\d+(?:,\d+)?) a los minutos 5 / 10 / 15; "
    r"alternándolo en otro hueco, ×(?P<weave>\d+(?:,\d+)?) al minuto 15\.$"
)
STAT_IDS = {"ataque": "atk", "velocidad": "spd", "defensa": "def", "regeneración": "regen", "vida": "hp"}


def _num(text: str) -> float:
    return float(text.replace(",", "."))


def _buff(r: dict) -> dict:
    """Cifras de un potenciador, leídas de su descripción en el CSV (que es donde las deja move_tierlist_v4.py)."""
    m = BUFF_RE.match(r["blurb"])
    if not m:
        raise CatalogError(f"descripción de potenciador no reconocida: {r['move_id']}")
    return {"stat": STAT_IDS[m["stat"]], "amount": _num(m["amount"]), "pct": bool(m["pct"]), "dur": int(m["dur"]),
            "cd": _num(m["cd"]), "cover": int(m["cover"]),
            "fused": [_num(m["g5"]), _num(m["g10"]), _num(m["g15"])], "weave": _num(m["weave"])}


def load_moves() -> list[dict]:
    rows = _read_csv(DATA / "move_tierlist_v4.csv")
    if not rows:
        raise CatalogError("data/move_tierlist_v4.csv está vacío")
    names_en = json.loads((DATA / "lang_en_moves.json").read_text(encoding="utf8"))
    icons = json.loads((DATA / "move_icons.json").read_text(encoding="utf8"))  # node build/export_move_icons.js
    mechanics = json.loads((DATA / "move_mechanics.json").read_text(encoding="utf8"))  # node build/export_move_mechanics.js
    def en(name: str | None, table: str) -> str | None:
        if not name:
            return None
        if name not in names_en[table]:
            raise CatalogError(f"sin nombre en inglés para {name!r}")
        return names_en[table][name]

    moves = []
    for r in rows:
        move = {"id": r["move_id"], "name": r["name"], "category": r["category"], "tier": r["tier"],
                "rank": int(r["rank"]), "type": r["type"], "kind": r["kind"],
                "evolvesTo": r["evolves_to"] or None, "needsCard": r["needs_card"] or None,
                "en": {"name": en(r["name"], "moves"), "evolvesTo": en(r["evolves_to"], "moves"),
                       "needsCard": en(r["needs_card"], "cards")}}
        # El valor de la tier list (score_rel): 1 es un movimiento normal, más es mejor. Es lo que ordena cada tier.
        move["score"] = round(float(r["score_rel"]), 2)
        if not r["dps_m15"]:
            move["buff"] = _buff(r)
        icon = icons.get(r["move_id"])
        if icon is None:
            raise CatalogError(f"sin icono del juego para {r['move_id']!r} (node build/export_move_icons.js)")
        if (icon["type"], icon["kind"]) != (r["type"], r["kind"]):
            raise CatalogError(f"{r['move_id']}: el juego dice {icon['type']}/{icon['kind']}, la tier list {r['type']}/{r['kind']}")
        move["icon"] = {"size": icon["size"], "pal": icon["pal"], "rows": icon["rows"]}
        # Cómo se comporta en el juego (node build/export_move_mechanics.js): distingue teledirigido, perforante y salto.
        mech = mechanics.get(r["move_id"])
        if mech is None:
            raise CatalogError(f"sin mecánica del juego para {r['move_id']!r} (node build/export_move_mechanics.js)")
        if mech["kind"] != r["kind"]:
            raise CatalogError(f"{r['move_id']}: el juego dice {mech['kind']}, la tier list {r['kind']}")
        move["mech"] = {"homing": mech["homing"], "pierce": mech["pierce"], "count": mech["count"]}
        move["damage"] = game_moves.damage_class(r["move_id"], r["kind"])
        if r["move_id"] in game_moves.NOTES:
            es, en_note = game_moves.NOTES[r["move_id"]]
            move["note"] = {"es": es, "en": en_note}
        moves.append(move)
    return moves


def load_unranked() -> list[dict]:
    """Movimientos del juego que aún no tienen puesto (game_moves.UNRANKED): sin tier ni valor, para no mezclarlos
    con los 64 de moves.json (la ficha cuenta y lista por tier)."""
    icons = json.loads((DATA / "move_icons.json").read_text(encoding="utf8"))
    out = []
    for ref in game_moves.UNRANKED:
        icon = icons.get(ref["id"])
        if icon is None:
            raise CatalogError(f"sin icono del juego para {ref['id']!r} (node build/export_move_icons.js)")
        if (icon["type"], icon["kind"]) != (ref["type"], ref["kind"]):
            raise CatalogError(f"{ref['id']}: el juego dice {icon['type']}/{icon['kind']}, el dato {ref['type']}/{ref['kind']}")
        dur, cd = ref["dur"], ref["cd"]
        out.append({
            "id": ref["id"], "name": ref["name"][0], "en": {"name": ref["name"][1]}, "type": ref["type"],
            "kind": ref["kind"], "damage": game_moves.damage_class(ref["id"], ref["kind"]),
            "note": {"es": ref["note"][0], "en": ref["note"][1]},
            "buff": {"stat": ref["stat"][0], "statEn": ref["stat"][1], "amount": ref["amount"], "stacks": ref["stacks"],
                     "dur": dur, "cd": cd, "cover": round(100 * min(1.0, dur / cd))},
            "icon": {"size": icon["size"], "pal": icon["pal"], "rows": icon["rows"]},
        })
    return out


def _move(move_names: dict, mid: str) -> dict:
    if mid not in move_names:
        raise CatalogError(f"movimiento desconocido en el ranking: {mid!r}")
    return {"id": mid, "name": move_names[mid]}


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


def load_pokemon(move_names: dict, credits: dict, shiny: set[int]) -> list[dict]:
    dex_export = {p["dex"]: p for p in json.load(open(DATA / "pokedex_export.json", encoding="utf8"))}
    base_stats = json.loads((DATA / "base_stats.json").read_text(encoding="utf8"))  # build/fetch_base_stats.py
    if {str(d) for d in dex_export} != set(base_stats):
        raise CatalogError("data/base_stats.json no coincide con pokedex_export.json; vuelve a ejecutar fetch_base_stats.py")
    names_en = {int(r["dex"]): r["name_en"] for r in _read_csv(DATA / "species_names_en.csv")}
    rows = {int(r["dex"]): r for r in _read_csv(DATA / RANKING_CSV)}
    if len(rows) != TOTAL:
        raise CatalogError(f"{RANKING_CSV}: {len(rows)} Pokémon distintos, se esperaban {TOTAL}")
    dexes = sorted(dex_export)
    if sorted(rows) != dexes:
        raise CatalogError(f"{RANKING_CSV}: los números de Pokédex no coinciden con pokedex_export.json")

    entries = []
    for dex in dexes:
        px, row = dex_export[dex], rows[dex]
        name_en = names_en.get(dex)
        if not name_en:
            raise CatalogError(f"sin nombre inglés para el Pokémon {dex}")
        if row["name"] != name_en:
            raise CatalogError(f"nombre inglés distinto en el ranking y en species_names para {dex}: "
                               f"{row['name']!r} / {name_en!r}")
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
        pair = [_move(move_names, m) for m in row["move_pair"].split(" + ") if m]
        ranking = {
            "rank": rank, "tier": tier, "p10": int(row["rank_p10"]), "p90": int(row["rank_p90"]),
            "pTier": float(row["p_tier"]), "pS": float(row["p_S"]),
            "pillars": {"stats": float(row["pct_stats"]), "moves": float(row["pct_moves"]),
                        "typedef": float(row["pct_typedef"]), "size": float(row["pct_size"])},
            "methods": {"sheet": int(row["rank_sheet"]), "simStart": int(row["rank_sim_start"]),
                        "simBest": int(row["rank_sim_best"]), "lateMax": int(row["rank_v4_max"]),
                        "lateFresh": int(row["rank_v4_fresh"])},
            "sim": {"start": {**_move(move_names, row["start_move"]), "kind": row["start_kind"],
                              "seconds": float(row["start_median_s"])},
                    "noshop": {"seconds": float(row["start_noshop_s"])},
                    "best": {**_move(move_names, row["best_move"]), "seconds": float(row["best_median_s"])}},
            "pair": pair,
            "flags": {"statsCapped": row["stats_capped"] == "1", "statusUnmodelled": row["status_unmodelled"] == "1",
                      "melee": row["melee_locked"] == "1", "typesCapped": row["types_capped"] == "1"},
        }
        entries.append({
            "dex": dex, "name": px["name"], "nameEn": name_en, "types": px["types"],
            "rarity": px["rarity"], "legendary": px["legendary"],
            "bannerId": px["gen"], "banner": px["banner"], "sprite": sprite, "r": ranking, "sh": dex in shiny,
            "base": {"atk": px["atk"], "hp": px["hp"], "spd": px["spd"], "ehp": px["effective_hp"],
                     "rad": px["body_radius"]},
            "stats": base_stats[str(dex)],
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


def build_stability(entries: list[dict]) -> list[dict]:
    """Por tier: cuántos son firmes (≥ 80 % de las repeticiones en su tier) y el ancho típico de la banda p10–p90."""
    out = []
    for t, lo, hi in TIER_CUTS:
        es = [e["r"] for e in entries if e["r"]["tier"] == t]
        out.append({"tier": t, "from": lo, "to": hi, "n": len(es),
                    "firm": round(100 * sum(r["pTier"] >= FIRM for r in es) / len(es)),
                    "bandWidth": round(statistics.median(r["p90"] - r["p10"] for r in es))})
    return out


def _pearson(xs: list[float], ys: list[float]) -> float:
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5


def build_agreement(entries: list[dict]) -> list[dict]:
    """Correlación de rangos (Spearman) entre el puesto de cada método y el puesto final."""
    final = [e["r"]["rank"] for e in entries]
    return [{"key": k, "corr": round(_pearson([e["r"]["methods"][k] for e in entries], final), 2)}
            for k in METHOD_KEYS]


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
        tiers = {t: sum(1 for e in mons if e["r"]["tier"] == t) for t, _, _ in TIER_CUTS}
        out.append({"gen": gen, "name": name, "poolSize": len(mons), "legendaryCount": sum(e["legendary"] for e in mons),
                    "tiers": tiers, "sCount": s, "aCount": len(good) - s, "sPlusARate": round(100 * len(good) / len(mons), 1),
                    "pullChance": round(100 * _pull_chance(by_rarity, [e["dex"] for e in mons], good), 1)})
    if sum(g["poolSize"] for g in out) != TOTAL:
        raise CatalogError("los pools de los banners no suman 966")
    return out


def sim_seeds() -> int:
    """Partidas simuladas por Pokémon en la sim del ranking (columna n de rank_200.csv). Tienen que ser todas iguales."""
    counts = {int(r["n"]) for r in _read_csv(SIM_RANK)}
    if len(counts) != 1:
        raise CatalogError(f"{SIM_RANK.name}: partidas por Pokémon distintas {sorted(counts)}")
    return counts.pop()


def build_meta(entries: list[dict], credits: dict, counts: dict) -> dict:
    when = os.environ.get("SOURCE_DATE_EPOCH")
    stamp = datetime.fromtimestamp(int(when), timezone.utc) if when else datetime.now(timezone.utc)
    top = sorted(entries, key=lambda e: e["r"]["rank"])[:3]
    return {
        "version": VERSION, "generatedAt": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tierCuts": [{"tier": t, "from": a, "to": b} for t, a, b in TIER_CUTS],
        "tierCounts": counts, "total": TOTAL, "gameCommit": legal.GAME_COMMIT, "firmShare": int(FIRM * 100),
        "simSeeds": sim_seeds(),
        "top": [{"dex": e["dex"], "name": e["name"], "nameEn": e["nameEn"]} for e in top],
        "simMedianSeconds": round(statistics.median(e["r"]["sim"]["start"]["seconds"] for e in entries)),
        "stability": build_stability(entries), "method": METHOD, "agreement": build_agreement(entries),
        "simRange": [min(sec for e in entries for sec in (e["r"]["sim"]["start"]["seconds"], e["r"]["sim"]["best"]["seconds"])),
                     max(sec for e in entries for sec in (e["r"]["sim"]["start"]["seconds"], e["r"]["sim"]["best"]["seconds"]))],
        "cappedCount": sum(e["r"]["flags"]["statsCapped"] for e in entries),
        "presets": [e["dex"] for name in PRESETS for e in entries if e["name"] == name],
        "credits": [{"name": a["name"], "url": a["url"], "dex": a["dex"]} for a in credits["artists"]],
        "spriteLicense": {"name": credits_mod.SPRITE_LICENSE["name"], "url": credits_mod.SPRITE_LICENSE["url"],
                          "source": credits_mod.SPRITE_SOURCE["name"], "sourceUrl": credits_mod.SPRITE_SOURCE["url"]},
    }


def slim(entries: list[dict]) -> list[dict]:
    """Lo mínimo para la tier list, el buscador y la colección: r = [puesto, tier, p10, p90, % en su tier].
    bst = suma de stats base: es el campo bst de js/data/pokedex.js del juego para los 966 Pokémon."""
    return [{"dex": e["dex"], "name": e["name"], "nameEn": e["nameEn"], "types": e["types"],
             "rarity": e["rarity"], "legendary": e["legendary"], "bannerId": e["bannerId"], "sh": e["sh"],
             "bst": sum(e["stats"]), "w": e["sprite"]["w"], "h": e["sprite"]["h"],
             "r": [e["r"]["rank"], e["r"]["tier"], e["r"]["p10"], e["r"]["p90"], round(100 * e["r"]["pTier"])],
             "v": sort_values(e)}
            for e in entries]


def sort_values(e: dict) -> dict:
    """Valores por los que se ordena la lista: los de la Pokédex (atk, hp, spd, ehp, rad) y los pilares en %
    (td = defensa de tipos, mv = movimientos, st = estadísticas). Los claves son cortas para que el JSON pese poco."""
    b, pil = e["base"], e["r"]["pillars"]
    return {"atk": round(b["atk"], 2), "hp": b["hp"], "spd": b["spd"], "ehp": round(b["ehp"]),
            "rad": round(b["rad"], 1), "td": round(100 * pil["typedef"]), "mv": round(100 * pil["moves"]),
            "st": round(100 * pil["stats"])}


def build_items() -> list[dict]:
    """Objetos recomendados en la build (build/objetos.py), con el icono del juego en el mismo formato que los movimientos."""
    out = []
    for it in objetos.recommended():
        icon = objetos.ICONS[it["id"]]
        out.append({"id": it["id"], "name": it["name"][0], "en": {"name": it["name"][1]},
                    "icon": {"size": icon["size"], "pal": icon["pal"], "rows": icon["rows"]}})
    return out


def build_cards() -> dict:
    """Cartas de subida de nivel con su dibujo del juego (data/card_icons.json, de build/export_move_icons.js)."""
    icons = json.loads((DATA / "card_icons.json").read_text(encoding="utf8"))
    names = {"hp": "Vigor", "atk": "Power", "spd": "Sprint", "cd": "Reflexes", "def": "Armor", "rgn": "Synthesis",
             "mag": "Magnet", "xp": "Learning"}
    return {k: {"id": "card:" + k, "name": v["title"], "en": {"name": names[k]},
                "icon": {"size": v["size"], "pal": v["pal"], "rows": v["rows"]}} for k, v in icons.items() if k in names}


def species_details(entries: list[dict], sim_range: list[float], median: float, combo: dict) -> dict:
    psim = passives.load()
    """Lo que la ficha necesita además de pokemon-index.json, en listas para que pese poco. Orden de cada entrada:
    [pilares (stats, moves, typedef, size), puestos por medida (METHOD_KEYS), ataque inicial, segundos de la
    apertura con Repertorio, mejor ataque, segundos, pareja de ataques, banderas (1 estado sin simular, 2 sigue en
    cuerpo a cuerpo tras Repertorio, 4 estadísticas, 8 tipos), estadísticas base oficiales [PS, ataque, defensa,
    ataque especial, defensa especial, velocidad], combo de cobertura [% super efectivo, % no resistido, ids de los
    ataques y el potenciador, tipos de ataque distintos (1-3), ids de los ataques opcionales] (build/combos.py),
    cartas, segundos del ataque inicial a solas (sin Repertorio ni Veto)].
    Lo lee src/ficha.js.
    «items» son los objetos de la build, iguales para todos. «statMedian» es la mediana de cada estadística base entre los 966, para la línea de referencia de la ficha."""
    out = {}
    for e in entries:
        r = e["r"]
        f = r["flags"]
        out[str(e["dex"])] = [
            [r["pillars"][k] for k in ("stats", "moves", "typedef", "size")], [r["methods"][k] for k in METHOD_KEYS],
            r["sim"]["start"]["id"], r["sim"]["start"]["seconds"], r["sim"]["best"]["id"], r["sim"]["best"]["seconds"],
            [m["id"] for m in r["pair"]], int(f["statusUnmodelled"]) + 2 * int(f["melee"]) + 4 * int(f["statsCapped"]) + 8 * int(f["typesCapped"]),
            e["stats"], [combo[e["dex"]]["super"], combo[e["dex"]]["neutral"], combo[e["dex"]]["moves"],
                         combo[e["dex"]]["types"], combo[e["dex"]]["alts"], combo[e["dex"]]["nBoost"]],
            # cartas que coge el bot (build/passives.py): [ids, cuántas de las primeras se cogen una sola vez]
            passives.compute(e["dex"], combo[e["dex"]]["moves"], psim),
            r["sim"]["noshop"]["seconds"]]
    medians = [statistics.median(e["stats"][i] for e in entries) for i in range(6)]
    return {"sim": [*sim_range, median], "statMedian": medians, "items": build_items(), "cards": build_cards(), "d": out}


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
        move_names = {m["id"]: m["name"] for m in moves}
        dexes = sorted(p["dex"] for p in json.loads((DATA / "pokedex_export.json").read_text(encoding="utf8")))
        entries = load_pokemon(move_names, credits, load_shiny(dexes))
        counts = check_ranks(entries)
        gachas = build_gachas(entries)
        meta = build_meta(entries, credits, counts)
    except (CatalogError, credits_mod.CreditsError, ValueError, KeyError, OSError) as exc:
        print(f"ERROR de catálogo: {exc}", file=sys.stderr)
        return 1
    # Los resúmenes de la ficha se validan contra los datos de hoy (solo biblioteca estándar: aquí no hay numpy).
    # Un dato que cambió, un nombre que ya no es el de la build o una afirmación sin respaldo paran el build.
    texts = summaries.load()
    errs, sstats = summaries.check(summary_facts.base_records(), texts)
    if errs:
        for e in errs[:40]:
            print("  " + e, file=sys.stderr)
        print(f"ERROR de catálogo: {len(errs)} errores en data/summaries.json; ver build/summary_pipeline.py",
              file=sys.stderr)
        return 1
    shutil.rmtree(OUT, ignore_errors=True)
    write_json("pokemon.json", entries)
    write_json("moves.json", moves)
    write_json("moves_unranked.json", unranked)
    write_json("pokemon-index.json", slim(entries), public=True)
    dex_types = {p["dex"]: p["types"] for p in json.loads((DATA / "pokedex_export.json").read_text(encoding="utf8"))}
    write_json("species.json", species_details(entries, meta["simRange"], meta["simMedianSeconds"],
                                               combos.compute_all(dex_types, {e["dex"]: e["r"]["sim"]["best"]["id"] for e in entries})), public=True)
    write_json("moves.json", moves, public=True)
    for lang in ("es", "en"):
        write_json(f"summaries-{lang}.json", summaries.public(texts, lang), public=True)
    write_json("gachas.json", gachas, pretty=True)
    write_json("meta.json", meta, pretty=True)
    print(f"catálogo: {len(entries)} Pokémon, {len(moves)} movimientos, {len(gachas)} banners → {OUT}")
    print("  " + " ".join(f"{t} {n}" for t, n in counts.items()))
    print(f"  resúmenes: {sstats['texts']} textos, {sstats['claims']} afirmaciones validadas, {sstats['flagged']} marcados")
    for g in sorted(gachas, key=lambda g: -g["sPlusARate"]):
        print(f"  {g['name']:8s} pool {g['poolSize']:3d}  S+A {g['sCount'] + g['aCount']:2d}  {g['sPlusARate']:5.1f} %"
              f"  (por tirada {g['pullChance']:.1f} %)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
