"""Turn selection-policy production records into validated, render-ready JSON."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from build.sim_results import ResultContractError, validate_results


class ExportError(ValueError):
    """Production records or pinned source metadata cannot form a web export."""


TYPE_ES = {
    "normal": "Normal", "fire": "Fuego", "water": "Agua", "electric": "Eléctrico",
    "grass": "Planta", "ice": "Hielo", "fighting": "Lucha", "poison": "Veneno",
    "ground": "Tierra", "flying": "Volador", "psychic": "Psíquico", "bug": "Bicho",
    "rock": "Roca", "ghost": "Fantasma", "dragon": "Dragón", "dark": "Siniestro",
    "steel": "Acero", "fairy": "Hada",
}
STAT_ES = {"hp": "PS", "atk": "Ataque", "pa": "Ataque", "sa": "Ataque especial",
           "df": "Defensa", "sd": "Defensa especial", "spd": "Velocidad"}
ROLE_AXES = {
    "base": ("baseline", "baseline"),
    "aggro": ("subtle", "baseline"),
    "coverage": ("baseline", "subtle"),
    "both": ("subtle", "subtle"),
}
BRANCHES = {"optimized_tm": "optimized", "optimized_no_tm": "no_tm"}


def parse_ability_effects(source: str | Path) -> dict[str, dict[str, Any]]:
    """Read the pinned game's `ability-fx.js` descriptions, resolving its helpers."""
    source_path = Path(source) if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source and Path(source).is_file()) else None
    text = source_path.read_text(encoding="utf8") if source_path else str(source)
    start = text.find("  const FX = {")
    if start < 0:
        raise ExportError("ability-fx.js has no FX table")
    end = text.find("\n  };", start)
    if end < 0:
        raise ExportError("ability-fx.js FX table is unterminated")
    block = text[start:end]
    entries: dict[str, str] = {}
    # Descriptions written directly as an FX object's first property.
    for ability, desc in re.findall(r"'([a-z0-9-]+)'\s*:\s*\{\s*d:\s*'((?:\\.|[^'])*)'", block):
        entries[ability] = _js_unescape(desc)
    # FX entries using the file's small, stable description helpers.
    helper_patterns = (
        (r"'([a-z0-9-]+)'\s*:\s*pinch\('([a-z]+)'\)", lambda m: f"+35 % de daño de tipo {TYPE_ES[m[2]]} con poca vida (menos de 1/3)."),
        (r"'([a-z0-9-]+)'\s*:\s*boost\('([a-z]+)'\)", lambda m: f"+20 % de daño con movimientos de tipo {TYPE_ES[m[2]]}."),
        (r"'([a-z0-9-]+)'\s*:\s*absorb\('([a-z]+)'\)", lambda m: f"Los ataques de tipo {TYPE_ES[m[2]]} no le hacen daño: le curan un poco."),
        (r"'([a-z0-9-]+)'\s*:\s*rush\('[^']+',\s*'([^']+)'\)", lambda m: f"+50 % de velocidad con {m[2]}."),
        (r"'([a-z0-9-]+)'\s*:\s*summon\('[^']+',\s*'([^']+)'\)", lambda m: f"Pone {m[2]} al empezar la partida y cada 3 minutos."),
        (r"'([a-z0-9-]+)'\s*:\s*contact\([^\n]*?,\s*'((?:\\.|[^'])*)'\)", lambda m: _js_unescape(m[2])),
    )
    for pattern, describe in helper_patterns:
        for match in re.finditer(pattern, block):
            entries.setdefault(match[1], describe(match))
    # Alias groups share these exact effect objects.
    for match in re.finditer(r"'([a-z0-9-]+)'\s*:\s*(moxie|steady)\b", block):
        entries.setdefault(match[1], 
            "Cada enemigo derrotado le da +0,5 % de daño (hasta +15 %)." if match[2] == "moxie"
            else "No le frenan las trampas pegajosas ni el terreno.")
    for match in re.finditer(r"'([a-z0-9-]+)'\s*:\s*byName\(/[^\n]*?,\s*'([^']+)'(?:,\s*([0-9.]+))?\)", block):
        k = float(match[3]) if match[3] else 1.3
        entries.setdefault(match[1], f"+{round((k - 1) * 100)} % de daño con {match[2]}.")
    for match in re.finditer(r"'([a-z0-9-]+)'\s*:\s*Object\.assign\(\{\},\s*steady,\s*\{\s*plus:\s*true\s*\}\)", block):
        entries.setdefault(match[1], "No le frenan las trampas pegajosas ni el terreno.")
    plus_ids = set(re.findall(r"'([a-z0-9-]+)'\s*:\s*\{[^\n]*\bplus:\s*true", block))
    plus_ids.update(re.findall(r"'([a-z0-9-]+)'\s*:\s*Object\.assign\(\{\},\s*steady,\s*\{\s*plus:\s*true", block))
    return {ability: {"effect": desc, "plus_type_fallback": ability in plus_ids}
            for ability, desc in entries.items()}


def parse_ability_capsules(source: str | Path) -> dict[str, dict[str, Any]]:
    """Read normal and hidden ability capsule purchase metadata from pinned shop.js."""
    source_path = Path(source) if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source and Path(source).is_file()) else None
    text = source_path.read_text(encoding="utf8") if source_path else str(source)
    out = {key: {"name": name, "price": int(price)}
           for key, name, price in re.findall(r"\b(cap|caph)\s*:\s*\{[^}]*?name:\s*'([^']+)'[^}]*?price:\s*(\d+)", text, re.S)}
    if not {"cap", "caph"}.issubset(out):
        raise ExportError("shop.js must include both normal and hidden ability capsules")
    return out


def parse_shop_metadata(source: str | Path) -> dict[str, Any]:
    """Extract only static shop prices/descriptions needed by result cards."""
    source_path = Path(source) if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source and Path(source).is_file()) else None
    text = source_path.read_text(encoding="utf8") if source_path else str(source)
    items = {}
    for key, name, price, desc in re.findall(
        r"\b(mint|cap|caph)\s*:\s*\{[^}]*?name:\s*'([^']+)'[^}]*?price:\s*(\d+)[^}]*?desc:\s*'([^']*)'", text, re.S
    ):
        items[key] = {"name": name, "price": int(price), "description": desc}
    if not {"mint", "cap", "caph"}.issubset(items):
        raise ExportError("shop.js must include mint and both ability capsules")
    return items


def build_metadata(game: dict[str, Any], *, source_commit: str, source_hashes: dict[str, str],
                   ability_effects: dict[str, dict[str, Any]], shop_items: dict[str, Any]) -> dict[str, Any]:
    """Build the committed static descriptor artifact from pinned official-source extracts."""
    abilities = {}
    for ability_id in game.get("abilities", {}):
        found = ability_effects.get(ability_id)
        abilities[ability_id] = ({"kind": "custom", **found} if found else
                                 {"kind": "primary_type_fallback", "effect": None, "plus_type_fallback": False})
    upgrades = {row["id"]: {"name": row.get("name"), "price": row.get("base"), "requires": row.get("needs")}
                for row in game.get("upgrades", []) if row.get("id") in ("moves", "start", "start2")}
    if set(upgrades) != {"moves", "start", "start2"}:
        raise ExportError("game data lacks moves/start/start2 upgrade descriptors")
    return {"schema": 1, "source_commit": source_commit, "source_hashes": source_hashes,
            "ability_effects": abilities, "shop_items": shop_items, "upgrades": upgrades,
            "nature_stat_rule": {"raised": 1.1, "lowered": 0.9, "neutral": 1.0,
                                 "source": "game.json#/natures"},
            "starting_choice_rule": "native non-buff pool plus stock move; native learned attacks may be owned type or same as stock; purchased TM starters legal if species TM compatible",
            "sources": {"starting_choices": "js/data/starters.js#G.startChoices",
                        "upgrades": "js/data/upgrades.js", "shop": "js/data/shop.js",
                        "ability_effects": "js/data/ability-fx.js", "tm_prices": "simulator/data/game.json#/tmPrices"}}


def validate_build_metadata(metadata: dict[str, Any], game: dict[str, Any]) -> None:
    if metadata.get("schema") != 1 or not metadata.get("source_commit") or not isinstance(metadata.get("source_hashes"), dict):
        raise ExportError("build metadata requires schema, pinned source commit, and source hashes")
    if metadata.get("source_commit") != game.get("gameCommit"):
        raise ExportError("build metadata source commit does not match supplied game data")
    abilities = metadata.get("ability_effects")
    if not isinstance(abilities, dict) or set(abilities) != set(game.get("abilities", {})):
        raise ExportError("build metadata must resolve every game ability exactly once")
    if any(not isinstance(path, str) or not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
           for path, digest in metadata["source_hashes"].items()):
        raise ExportError("build metadata source hashes must be SHA-256 digests")
    for ability_id, row in abilities.items():
        if row.get("kind") == "custom":
            if not isinstance(row.get("effect"), str) or not row["effect"].strip():
                raise ExportError(f"custom ability {ability_id} is missing its source effect")
        elif row.get("kind") == "primary_type_fallback":
            if row.get("effect") is not None:
                raise ExportError(f"fallback ability {ability_id} must use the species primary type")
        else:
            raise ExportError(f"ability {ability_id} has unsupported metadata kind")
    if not {"mint", "cap", "caph"}.issubset(metadata.get("shop_items", {})):
        raise ExportError("build metadata lacks nature/capsule shop prices")
    if set(metadata.get("upgrades", {})) != {"moves", "start", "start2"}:
        raise ExportError("build metadata lacks starter/repertorio upgrade prices")


def build_web_export(production: dict[str, Any], game_data: dict[str, Any],
                     ability_effects: dict[str, Any], *, source_game: str = "simulator/data/game.json",
                     source_ability_fx: str = "js/data/ability-fx.js",
                     ability_capsules: dict[str, dict[str, Any]] | None = None,
                     source_shop: str = "js/data/shop.js",
                     metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalize production.rs JSON and enrich winning rows from pinned source data.

    The adapter rejects an unknown role/branch. It never invents missing winners;
    policy statuses without a publishable selection become unavailable variants.
    """
    if not isinstance(production, dict) or production.get("schema") != 1:
        raise ExportError("production schema must be 1")
    if metadata is not None:
        validate_build_metadata(metadata, game_data)
        ability_effects = metadata["ability_effects"]
        ability_capsules = {key: metadata["shop_items"][key] for key in ("cap", "caph")}
        source_ability_fx = f"build-metadata.json@{metadata['source_commit']}#/ability_effects"
        source_shop = f"build-metadata.json@{metadata['source_commit']}#/shop_items"
    prov = production.get("provenance") or production
    game_commit = prov.get("gameCommit") or prov.get("game_commit")
    if game_commit != game_data.get("gameCommit"):
        raise ExportError("production gameCommit does not match supplied game.json")
    if metadata is None:
        raise ExportError("source-backed build metadata is required for web export")
    seeds = production.get("seedSets") or production.get("seed_sets") or {}
    if not seeds and isinstance(production.get("observations"), list):
        seeds = {stage: sorted({row.get("seed") for row in production["observations"]
                                if isinstance(row, dict) and row.get("stage") == stage and isinstance(row.get("seed"), int)})
                 for stage in ("screening", "confirmation")}
    screening = _seed_set(seeds.get("screening"))
    confirmation = _seed_set(seeds.get("confirmation"))
    if not set(screening["ids"]).isdisjoint(confirmation["ids"]):
        raise ExportError("screening and confirmation seeds overlap")
    dexes = {w.get("dex") for w in production.get("winners", []) if isinstance(w, dict) and isinstance(w.get("dex"), int)}
    dexes.update(u.get("dex") for u in production.get("unavailable", []) if isinstance(u, dict) and isinstance(u.get("dex"), int))
    dexes = sorted(dexes)
    if not dexes:
        raise ExportError("production has no species records")
    variants = [{"id": f"aggro-{a}__coverage-{c}", "aggro": a, "coverage": c}
                for a in ("baseline", "subtle") for c in ("baseline", "subtle")]
    out: dict[str, Any] = {
        "schema_version": 1,
        "export_mode": "renderable_web",
        "provenance": {"game_commit": game_commit, "engine_fingerprint": prov.get("engineFingerprint") or prov.get("engine_fingerprint"),
                       "policy_version": production.get("policyVersion"), "policy_hash": production.get("policyHash"),
                       "plan_hash": production.get("planHash") or production.get("manifestHash"),
                       "source_acquisition": {"game": source_game, "ability_effects": source_ability_fx,
                                               "ability_capsules": source_shop,
                                               **({"source_commit": metadata["source_commit"],
                                                   "source_hashes": metadata["source_hashes"]} if metadata else {})}},
        "experiment": {"score_version": "selection-metrics-v1", "seed_sets": {"screening": screening, "confirmation": confirmation},
                       "pokemon_dexes": dexes, "axes": {"aggro": ["baseline", "subtle"], "coverage": ["baseline", "subtle"]},
                       "expected_variants": variants},
        "results": [], "unavailable_cohorts": [], "unavailable_variants": [],
        "ranking_method": {"id": "selection-policy-pareto-v1", "status": "diagnostic_only"},
        "optimized_potential": [],
    }
    # Convert production-level unavailable species into all four explicit cohorts.
    for item in production.get("unavailable", []):
        if not isinstance(item, dict):
            raise ExportError("production unavailable entries must be objects")
        if isinstance(item.get("variantId"), str):
            dex = item.get("dex")
            if not isinstance(dex, int):
                raise ExportError("unavailable variant record requires dex")
            style, role, branch = _variant_parts(item["variantId"])
            if branch == "control_no_tm":
                out.setdefault("unavailable_controls", []).append(item)
                continue
            out["unavailable_variants"].append({"dex": dex, "style": style, "availability": BRANCHES[branch],
                "variant": _variant(role), "reason": item.get("reason") or "No confirmed candidate."})
        elif isinstance(item.get("dex"), int):
            for style in ("melee", "ranged"):
                for availability in ("optimized", "no_tm"):
                    out["unavailable_cohorts"].append({"dex": item["dex"], "style": style,
                                                        "availability": availability, "reason": item.get("reason") or "No candidate was confirmed."})
    for winner in production.get("winners", []):
        if not isinstance(winner, dict):
            raise ExportError("production winners must be objects")
        config = winner.get("configuration") or winner.get("config") or {}
        variant_id = winner.get("variantId")
        if not isinstance(variant_id, str):
            raise ExportError("winner.variantId is required")
        style, role, branch = _variant_parts(variant_id)
        if config.get("build") != style or config.get("role") != role or config.get("branch") != branch:
            raise ExportError(f"winner {variant_id} disagrees with config build/role/branch")
        variant = _variant(role)
        if branch == "control_no_tm":
            out.setdefault("controls", []).append(_renderable_control(winner, config, game_data, source_game))
            continue
        availability = BRANCHES[branch]
        dex = winner.get("dex")
        status = winner.get("status")
        if status not in ("best_observed", "tied_best") or winner.get("winnerConfirmed") is not True or not config:
            out["unavailable_variants"].append({"dex": dex, "style": style, "availability": availability,
                                                 "variant": variant, "reason": status or "No confirmed candidate."})
            continue
        winner = _normalize_policy_winner(winner)
        row = _renderable_winner(winner, config, variant, availability, game_data,
                                 ability_effects, ability_capsules or {}, source_game, source_ability_fx, source_shop,
                                 metadata["shop_items"])
        row["confirmation_seed_set"] = {"count": confirmation["count"], "hash": confirmation["hash"]}
        out["results"].append(row)
    row_lookup = {(r["pokemon"]["dex"], r["build"]["style"], r["build"]["availability"], r["variant"]["id"]): r for r in out["results"]}
    missing_lookup = {(r["dex"], r["style"], r["availability"], r["variant"]["id"]): r for r in out["unavailable_variants"]}
    for row in out["results"]:
        if row["build"]["availability"] != "optimized":
            continue
        key = (row["pokemon"]["dex"], row["build"]["style"], "no_tm", row["variant"]["id"])
        fallback = row_lookup.get(key)
        if fallback:
            row["build"]["no_tm_alternative"] = {"build_id": fallback["build"]["id"],
                "attacks": [a["id"] for a in fallback["build"]["attacks"]]}
        else:
            unavailable = missing_lookup.get(key)
            row["build"]["no_tm_alternative"] = {"available": False,
                "reason": unavailable["reason"] if unavailable else "No measured no-TM comparison was produced."}
    try:
        return validate_results(out, game_data)
    except ResultContractError as exc:
        raise ExportError(f"production result failed web contract: {exc}") from exc


def _renderable_winner(winner: dict[str, Any], config: dict[str, Any], variant: dict[str, Any], availability: str,
                       game: dict[str, Any], effects: dict[str, Any], capsules: dict[str, dict[str, Any]],
                       source_game: str, source_fx: str, source_shop: str,
                       shop_items: dict[str, dict[str, Any]]) -> dict[str, Any]:
    dex = winner["dex"]
    species = next((p for p in game.get("dex", []) if p.get("dex") == dex), None)
    if species is None:
        raise ExportError(f"dex {dex} absent from game data")
    group = config.get("group")
    if not isinstance(group, list) or not group:
        raise ExportError(f"winner {winner.get('configurationId')} has no move group")
    ability_id = config.get("ability") or (next((a for a in species.get("abilities", []) if a), None))
    nature_id = config.get("nature")
    ability_names = game.get("abilities", {}).get(ability_id)
    nature = next((n for n in game.get("natures", []) if n.get("id") == nature_id), None)
    if not isinstance(ability_names, list) or nature is None:
        raise ExportError(f"winner {winner.get('configurationId')} has unknown ability or nature")
    effect_meta = effects.get(ability_id)
    if isinstance(effect_meta, dict):
        effect, plus = effect_meta.get("effect"), effect_meta.get("plus_type_fallback") is True
    else:
        effect, plus = effect_meta, False
    if effect is None:
        effect_kind = "generic_type_fallback"
        effect = f"+8 % de daño con movimientos de tipo {TYPE_ES[species['types'][0]]}."
    else:
        effect_kind = "ability_specific_plus" if plus else "ability_specific"
        if plus:
            effect += f" Además, +8 % de daño con movimientos de tipo {TYPE_ES[species['types'][0]]}."
    effect_source = source_fx + ("#/generic" if effect_kind == "generic_type_fallback" else f"#/{ability_id}")
    raw_abilities = species.get("abilities", [])
    ability_slot = raw_abilities.index(ability_id) if isinstance(raw_abilities, list) and ability_id in raw_abilities else -1
    if ability_slot < 0:
        raise ExportError(f"ability {ability_id} is not a species ability")
    capsule_key = "cap" if ability_slot == 1 else "caph" if ability_slot == 2 else None
    capsule = capsules.get(capsule_key) if capsule_key else None
    if capsule_key and capsule is None:
        raise ExportError(f"missing acquisition metadata for {capsule_key}")
    capsule_info = ({"id": capsule_key, "name": capsule["name"], "price": capsule["price"], "source": source_shop}
                    if capsule_key and capsule else None)
    moves = game.get("moves", {})
    tms = config.get("tms", [])
    upgrades = {u.get("id"): u for u in game.get("upgrades", [])}
    move_rows = []
    for pos, mid in enumerate(group, 1):
        move = moves.get(mid)
        if not move:
            raise ExportError(f"unknown move id {mid}")
        move_rows.append({"id": mid, "position": pos, "name": move.get("name", mid), "type": move.get("type"),
                          "kind": move.get("kind"), "category": (move.get("levels") or [{}])[0].get("cat")})
    tm_rows = []
    for mid in tms:
        if mid not in game.get("tmPrices", {}):
            raise ExportError(f"TM {mid} is not in game data")
        tm_rows.append({"id": mid, "source": f"{source_game}#/tmPrices/{mid}",
                        "name": moves.get(mid, {}).get("name", mid), "price": game["tmPrices"][mid]})
    first = group[0]
    second = config.get("secondStart") or config.get("second")
    initial = [first] + ([second] if second and second != first else [])
    start_upgrade = upgrades.get("start", {})
    start2_upgrade = upgrades.get("start2", {})
    move_upgrade = upgrades.get("moves", {})
    starter_details = [{"id": mid, "name": moves[mid].get("name", mid), "order": order,
                        "unlock": {"upgrade_id": "start" if order == 1 else "start2",
                                   "price": (0 if order == 1 and mid == species.get("start") else start_upgrade.get("base", 400)) if order == 1 else start2_upgrade.get("base", 400),
                                   "requires": ([{"upgrade_id": "moves", "price": move_upgrade.get("base", 1500)}] if order == 2 else []),
                                   "source": f"{source_game}#/upgrades"}}
                       for order, mid in enumerate(initial, 1)]
    natural_pool = [{"id": mid, "name": moves.get(mid, {}).get("name", mid), "type": moves.get(mid, {}).get("type")}
                    for mid in species.get("pool", [])]
    alt = None
    metrics = winner.get("summary") or {}
    return {
        "pokemon": {"dex": dex, "slug": _slug(species.get("name", str(dex))), "name": species.get("name", str(dex))},
        "build": {
            "id": winner.get("configurationId"), "style": config.get("build"), "availability": availability,
            "attacks": move_rows,
            "ability": {"id": ability_id, "source": f"{source_game}#/abilities/{ability_id}", "name": ability_names[0],
                        "names": ability_names, "effect": effect, "effect_kind": effect_kind, "effect_source": effect_source},
            "nature": {"id": nature_id, "source": f"{source_game}#/natures/{nature_id}",
                       "name": nature.get("n", [nature_id])[0], "names": nature.get("n", [nature_id]),
                       "up": {"id": nature.get("up"), "name": STAT_ES.get(nature.get("up"), "Sin cambios")},
                       "down": {"id": nature.get("down"), "name": STAT_ES.get(nature.get("down"), "Sin cambios")},
                       "resulting_stats": _nature_stats(species, nature),
                       "change_item": {"id": "mint", "name": shop_items["mint"]["name"], "price": shop_items["mint"]["price"],
                                       "source": source_shop}},
            "ability_slot": "default" if ability_slot == 0 else "normal" if ability_slot == 1 else "hidden",
            "ability_capsule": capsule_info,
            "tm_requirements": tm_rows, "initial_attacks": initial, "initial_attack_details": starter_details,
            "natural_pool": natural_pool,
            "acquisition_sources": {"natural_pool": f"{source_game}#/dex/{dex}/pool",
                                    "starting_choices": "js/data/starters.js#G.startChoices",
                                    "startup_upgrades": f"{source_game}#/upgrades",
                                    "nature_stats": f"{source_game}#/natures/{nature_id}"},
            **({"no_tm_alternative": alt} if availability == "optimized" else {}),
        },
        "variant": variant, "status": "confirmed", "winner_confirmed": True,
        "selection": {"outcome": winner.get("status"), "claim": "best observed; no superiority claimed",
                      "confidence": winner.get("confidence"), "paired": winner.get("paired", [])},
        "score": {"version": "selection-metrics-v1", "metrics": _metric_numbers(metrics)},
    }


def _normalize_policy_winner(winner: dict[str, Any]) -> dict[str, Any]:
    """Normalize production.rs observation-based confirmation to the card contract."""
    if "pairedConfirmation" not in winner:
        return winner
    paired = winner["pairedConfirmation"]
    interval_keys = ("survivalSeconds", "contactDamagePerMinute", "contactFraction", "trappedFraction")
    confidence = {}
    for key in interval_keys:
        interval = paired.get(key)
        if isinstance(interval, dict):
            confidence[key] = {"n": interval.get("n", paired.get("n")),
                               "meanDifference": interval.get("mean", interval.get("meanDelta")),
                               "lower": interval.get("lower"), "upper": interval.get("upper")}
    per_seed = []
    for item in paired.get("perSeed", []):
        if not isinstance(item, dict) or not isinstance(item.get("seed"), int):
            continue
        per_seed.append({"seed": item["seed"], "candidate": item.get("candidate", {}),
                         "control": item.get("control", {})})
    configuration = winner.get("configuration") or {}
    return {**winner, "configurationId": configuration.get("id", winner.get("configurationId")),
            "config": configuration, "confidence": confidence, "paired": per_seed,
            "summary": {"paired_confirmation_n": paired.get("n", len(per_seed)),
                        **(paired.get("meanDelta") if isinstance(paired.get("meanDelta"), dict) else {})}}


def _renderable_control(control: dict[str, Any], config: dict[str, Any], game: dict[str, Any], source_game: str) -> dict[str, Any]:
    species = next((p for p in game.get("dex", []) if p.get("dex") == control.get("dex")), None)
    if species is None:
        raise ExportError("control dex missing from game data")
    return {"dex": control["dex"], "style": config.get("build"), "variant_id": control.get("variantId"),
            "summary": _metric_numbers(control.get("summary") or {}), "confidence": control.get("confidence"),
            "build": {"group": config.get("group", []), "tms": config.get("tms", []),
                      "source": f"{source_game}#/dex/{control['dex']}"}}


def _variant_parts(variant_id: str) -> tuple[str, str, str]:
    parts = variant_id.split(":")
    if len(parts) != 3 or parts[0] not in ("melee", "ranged") or parts[1] not in ROLE_AXES or parts[2] not in (*BRANCHES, "control_no_tm"):
        raise ExportError(f"unsupported variantId {variant_id}")
    return parts[0], parts[1], parts[2]


def _variant(role: str) -> dict[str, str]:
    aggro, coverage = ROLE_AXES[role]
    return {"id": f"aggro-{aggro}__coverage-{coverage}", "aggro": aggro, "coverage": coverage}


def _metric_numbers(metrics: Any) -> dict[str, float]:
    if not isinstance(metrics, dict):
        raise ExportError("summary metrics must be an object")
    out = {}
    for key, value in metrics.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[key] = float(value)
    if not out:
        raise ExportError("summary has no numeric metrics")
    return out


def _nature_stats(species: dict[str, Any], nature: dict[str, Any]) -> dict[str, dict[str, float]]:
    base = {"pa": float(species.get("pa", 0)), "sa": float(species.get("sa", 0)),
            "df": float(species.get("df", 0)), "sd": float(species.get("sd", 0)),
            "spd": float(species.get("spd", 0))}
    result = {}
    for stat, value in base.items():
        factor = 1.1 if nature.get("up") == stat else 0.9 if nature.get("down") == stat else 1.0
        result[stat] = {"base": value, "after_nature": round(value * factor, 4)}
    return result


def _seed_set(ids: Any) -> dict[str, Any]:
    if not isinstance(ids, list) or not ids or any(not isinstance(x, int) or x < 0 for x in ids) or len(set(ids)) != len(ids):
        raise ExportError("seedSets entries must be nonempty unique integer lists")
    canonical = json.dumps(sorted(ids), separators=(",", ":")).encode("utf8")
    import hashlib
    return {"ids": sorted(ids), "count": len(ids), "hash": "sha256:" + hashlib.sha256(canonical).hexdigest()}


def _js_unescape(value: str) -> str:
    return value.replace("\\'", "'").replace("\\n", "\n").replace("\\\\", "\\")


def _slug(value: str) -> str:
    import unicodedata
    value = unicodedata.normalize("NFKD", value.lower())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("production", type=Path, help="production.rs JSON export")
    parser.add_argument("game_data", type=Path, help="pinned simulator/data/game.json")
    parser.add_argument("--metadata", type=Path, default=Path("simulator/data/build-metadata.json"),
                        help="committed source-backed descriptors (no upstream checkout required)")
    parser.add_argument("--out", type=Path, required=True, help="render-ready validated JSON output")
    args = parser.parse_args()
    production = json.loads(args.production.read_text(encoding="utf8"))
    game = json.loads(args.game_data.read_text(encoding="utf8"))
    metadata = json.loads(args.metadata.read_text(encoding="utf8"))
    output = build_web_export(production, game, metadata["ability_effects"], metadata=metadata,
                              source_game=str(args.game_data))
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(f"validated {len(output['results'])} result cards into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
