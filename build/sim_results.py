"""Strict boundary validation for publishable simulator web results.

Validation is intentionally separate from the historical ranking pipeline.
"""
from __future__ import annotations

import itertools
import hashlib
import json
import math
import re
from typing import Any


STAT_ES_LABELS = {"hp": "PS", "atk": "Ataque", "pa": "Ataque", "sa": "Ataque especial",
                  "df": "Defensa", "sd": "Defensa especial", "spd": "Velocidad"}


class ResultContractError(ValueError):
    """An export is incomplete, inconsistent, or not publishable."""


def validate_results(document: dict[str, Any], game_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate a version-1 export; optionally check IDs against game.json catalogs."""
    errors: list[str] = []
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ResultContractError("schema_version must be 1")
    provenance = document.get("provenance")
    if not isinstance(provenance, dict):
        errors.append("provenance is required")
        provenance = {}
    for key in ("game_commit", "engine_fingerprint", "policy_version"):
        if not _text(provenance.get(key)):
            errors.append(f"provenance.{key} is required")
    if game_data is not None:
        if provenance.get("game_commit") != game_data.get("gameCommit"):
            errors.append("provenance.game_commit does not match simulator/data/game.json")

    experiment = document.get("experiment")
    if not isinstance(experiment, dict):
        errors.append("experiment is required")
        experiment = {}
    score_version = experiment.get("score_version")
    if not _text(score_version):
        errors.append("experiment.score_version is required")
    seed_sets = experiment.get("seed_sets")
    if not isinstance(seed_sets, dict) or not seed_sets:
        errors.append("experiment.seed_sets must declare screening and confirmation seeds")
        seed_sets = {}
    for stage in ("screening", "confirmation"):
        seeds = seed_sets.get(stage)
        if not isinstance(seeds, dict):
            errors.append(f"experiment.seed_sets.{stage} is required")
        else:
            _validate_seed_set(seeds, f"experiment.seed_sets.{stage}", errors)
    screening = seed_sets.get("screening", {})
    confirmation = seed_sets.get("confirmation", {})
    if isinstance(screening, dict) and isinstance(confirmation, dict):
        sids, cids = screening.get("ids"), confirmation.get("ids")
        if isinstance(sids, list) and isinstance(cids, list) and not set(sids).isdisjoint(cids):
            errors.append("screening and confirmation seed sets must be disjoint")

    axes = experiment.get("axes")
    variants = experiment.get("expected_variants")
    expected: set[tuple[str, Any, Any]] = set()
    if not isinstance(axes, dict) or not isinstance(axes.get("aggro"), list) or not axes["aggro"] or not isinstance(axes.get("coverage"), list) or not axes["coverage"]:
        errors.append("experiment.axes must declare nonempty aggro and coverage values")
    elif not isinstance(variants, list) or not variants:
        errors.append("experiment.expected_variants is required")
    else:
        generated = {(f"aggro-{a}__coverage-{c}", a, c) for a, c in itertools.product(axes["aggro"], axes["coverage"])}
        declared: set[tuple[str, Any, Any]] = set()
        for v in variants:
            if not isinstance(v, dict) or not _text(v.get("id")):
                errors.append("each expected variant needs id, aggro, and coverage")
                continue
            declared.add((v["id"], v.get("aggro"), v.get("coverage")))
        if declared != generated:
            errors.append("expected_variants must exactly cover the aggro x coverage cross-product")
        expected = generated

    rows = document.get("results")
    if not isinstance(rows, list) or not rows:
        errors.append("results must be a nonempty list")
        rows = []
    seen: set[tuple[int, str, str, str]] = set()
    cohort_variants: dict[tuple[int, str, str], set[str]] = {}
    groups: set[tuple[int, str, str]] = set()
    result_index: dict[tuple[int, str, str, str], dict[str, Any]] = {}
    confirmation_signatures: set[tuple[Any, ...]] = set()
    for i, row in enumerate(rows):
        at = f"results[{i}]"
        if not isinstance(row, dict):
            errors.append(f"{at} must be an object")
            continue
        pokemon, build, variant = row.get("pokemon"), row.get("build"), row.get("variant")
        if not isinstance(pokemon, dict) or not isinstance(pokemon.get("dex"), int) or not _text(pokemon.get("slug")):
            errors.append(f"{at}.pokemon needs integer dex and slug")
            continue
        if not isinstance(build, dict) or not _text(build.get("id")):
            errors.append(f"{at}.build.id is required")
            continue
        dex, bid = pokemon["dex"], build["id"]
        style, availability = build.get("style"), build.get("availability")
        cohort = (dex, style, availability)
        if style not in ("melee", "ranged") or availability not in ("optimized", "no_tm"):
            errors.append(f"{at}.build needs style melee/ranged and availability optimized/no_tm")
        groups.add(cohort)
        if not isinstance(variant, dict):
            errors.append(f"{at}.variant is required")
            continue
        vid = variant.get("id")
        item = next((x for x in expected if x[0] == vid), None)
        if item is None or variant.get("aggro") != item[1] or variant.get("coverage") != item[2]:
            errors.append(f"{at}.variant is undeclared or disagrees with declared axes")
        key = (*cohort, vid)
        if key in seen:
            errors.append(f"{at} duplicates cohort/variant {key}")
        seen.add(key)
        result_index[(dex, style, availability, vid)] = row
        cohort_variants.setdefault(cohort, set()).add(vid)
        if row.get("status") != "confirmed" or row.get("winner_confirmed") is not True:
            errors.append(f"{at} is not confirmed")
        if row.get("placeholder") is True:
            errors.append(f"{at} is a placeholder or has an unconfirmed winner")
        if style in ("melee", "ranged") and availability in ("optimized", "no_tm"):
            _validate_build(build, at, errors, game_data, dex)
            if document.get("export_mode") == "renderable_web":
                _validate_render_metadata(build, at, errors, game_data, dex)
                selection = row.get("selection")
                if (not isinstance(selection, dict) or selection.get("outcome") not in ("best_observed", "tied_best")
                        or selection.get("claim") != "best observed; no superiority claimed"
                        or not isinstance(selection.get("confidence"), dict)):
                    errors.append(f"{at}.selection must preserve a confirmed observed outcome and uncertainty")
        score = row.get("score")
        if not isinstance(score, dict) or score.get("version") != score_version:
            errors.append(f"{at}.score.version must match experiment.score_version")
        elif not isinstance(score.get("metrics"), dict) or not score["metrics"] or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in score["metrics"].values()):
            errors.append(f"{at}.score.metrics must contain finite numeric metrics")
        seeds = row.get("confirmation_seed_set")
        expected_seed = seed_sets.get("confirmation", {})
        if not isinstance(seeds, dict) or seeds.get("hash") != expected_seed.get("hash") or seeds.get("count") != expected_seed.get("count"):
            errors.append(f"{at}.confirmation_seed_set must match the declared confirmation seed set")
        confirmation_signatures.add((seeds.get("hash") if isinstance(seeds, dict) else None,
                                     score.get("version") if isinstance(score, dict) else None))
    if len(confirmation_signatures) > 1:
        errors.append("results mix confirmation seed sets or score versions")

    unavailable = document.get("unavailable_cohorts", [])
    unavailable_keys: set[tuple[int, str, str]] = set()
    if not isinstance(unavailable, list):
        errors.append("unavailable_cohorts must be a list")
    else:
        for i, item in enumerate(unavailable):
            if not isinstance(item, dict) or not isinstance(item.get("dex"), int) or item.get("style") not in ("melee", "ranged") or item.get("availability") not in ("optimized", "no_tm") or not _text(item.get("reason")):
                errors.append(f"unavailable_cohorts[{i}] needs dex, style, availability, and reason")
            else:
                key = (item["dex"], item["style"], item["availability"])
                if key in unavailable_keys or key in groups:
                    errors.append(f"unavailable_cohorts[{i}] duplicates an available or unavailable cohort")
                unavailable_keys.add(key)

    unavailable_variants = document.get("unavailable_variants", [])
    unavailable_variant_keys: set[tuple[int, str, str, str]] = set()
    unavailable_variant_cohorts: set[tuple[int, str, str]] = set()
    if not isinstance(unavailable_variants, list):
        errors.append("unavailable_variants must be a list")
    else:
        for i, item in enumerate(unavailable_variants):
            if (not isinstance(item, dict) or not isinstance(item.get("dex"), int)
                    or item.get("style") not in ("melee", "ranged")
                    or item.get("availability") not in ("optimized", "no_tm")
                    or not isinstance(item.get("variant"), dict) or not _text(item["variant"].get("id"))
                    or not _text(item.get("reason"))):
                errors.append(f"unavailable_variants[{i}] needs dex, style, availability, variant, and reason")
                continue
            key = (item["dex"], item["style"], item["availability"], item["variant"]["id"])
            if key in unavailable_variant_keys or key in result_index:
                errors.append(f"unavailable_variants[{i}] duplicates an available/unavailable result")
            unavailable_variant_keys.add(key)
            unavailable_variant_cohorts.add(key[:3])
            spec = next((x for x in expected if x[0] == key[3]), None)
            if spec is None or item["variant"].get("aggro") != spec[1] or item["variant"].get("coverage") != spec[2]:
                errors.append(f"unavailable_variants[{i}].variant is undeclared or disagrees with axes")

    dexes = experiment.get("pokemon_dexes")
    if not isinstance(dexes, list) or not dexes or any(not isinstance(d, int) for d in dexes) or len(set(dexes)) != len(dexes):
        errors.append("experiment.pokemon_dexes must be a nonempty unique list of included dex numbers")
    else:
        extra_dexes = (groups | unavailable_keys | unavailable_variant_cohorts)
        undeclared = {cohort[0] for cohort in extra_dexes if cohort[0] not in set(dexes)}
        if undeclared:
            errors.append(f"results contain dexes absent from experiment.pokemon_dexes: {sorted(undeclared)}")
        for dex in dexes:
            for style, availability in itertools.product(("melee", "ranged"), ("optimized", "no_tm")):
                cohort = (dex, style, availability)
                present = cohort in groups or cohort in unavailable_keys or cohort in unavailable_variant_cohorts
                if not present:
                    errors.append(f"cohort {cohort} must be available in results or declared unavailable")
                if (cohort in groups or cohort in unavailable_variant_cohorts) and cohort in unavailable_keys:
                    errors.append(f"cohort {cohort} cannot be both available and unavailable")
                actual = cohort_variants.get(cohort, set()) | {v[3] for v in unavailable_variant_keys if v[:3] == cohort}
                if present and actual != {v[0] for v in expected} and cohort not in unavailable_keys:
                    missing = {v[0] for v in expected} - actual
                    errors.append(f"cohort {cohort} lacks result/unavailable variants: {', '.join(sorted(missing))}")

    # Every optimized row's fallback must point at a measured no-TM outcome for
    # the same species, style, and control variant.
    for key, row in result_index.items():
        dex, style, availability, vid = key
        if availability != "optimized":
            continue
        fallback = row.get("build", {}).get("no_tm_alternative", {})
        target = result_index.get((dex, style, "no_tm", vid))
        if isinstance(fallback, dict) and fallback.get("available") is False:
            if not _text(fallback.get("reason")) or target is not None:
                errors.append(f"optimized result {key} has an invalid unavailable no-TM alternative")
        elif not isinstance(fallback, dict) or target is None or target.get("build", {}).get("id") != fallback.get("build_id"):
            errors.append(f"optimized result {key} has no matching measured no-TM alternative")
        elif target.get("build", {}).get("tm_requirements") != []:
            errors.append(f"no-TM alternative for {key} has TM requirements")
        elif fallback.get("attacks") != [a.get("id") for a in target.get("build", {}).get("attacks", []) if isinstance(a, dict)]:
            errors.append(f"no-TM alternative for {key} attack list disagrees with its measured result")

    potentials = document.get("optimized_potential")
    if not isinstance(document.get("ranking_method"), dict):
        errors.append("ranking_method is required; diagnostic metrics cannot imply an uncalibrated rank")
    else:
        method = document["ranking_method"]
        if method.get("status") not in ("diagnostic_only", "calibrated") or not _text(method.get("id")):
            errors.append("ranking_method needs id and status diagnostic_only/calibrated")
        if method.get("status") == "calibrated" and (not _text(method.get("calibration_source")) or not _text(method.get("version"))):
            errors.append("calibrated ranking_method needs version and calibration_source")
        if method.get("status") == "diagnostic_only":
            if potentials:
                errors.append("diagnostic_only exports cannot publish optimized_potential rankings")
            if any(isinstance(row, dict) and any(k in row for k in ("rank", "ranking", "place")) for row in rows):
                errors.append("diagnostic_only exports cannot publish ranks")
    if not isinstance(potentials, list):
        errors.append("optimized_potential must be a list")
    else:
        for i, item in enumerate(potentials):
            if not isinstance(item, dict) or item.get("label") != "optimized potential" or item.get("status") != "confirmed" or not _text(item.get("build_id")):
                errors.append(f"optimized_potential[{i}] must be confirmed, identified, and labeled 'optimized potential'")
    if errors:
        raise ResultContractError("; ".join(errors))
    return document


def _validate_build(build: dict[str, Any], at: str, errors: list[str], game: dict[str, Any] | None, dex: int) -> None:
    if build.get("availability") == "no_tm" and build.get("tm_requirements") != []:
        errors.append(f"{at}.build no_tm availability must have no TM requirements")
    attacks = build.get("attacks")
    attack_ids: list[str] = []
    if not isinstance(attacks, list) or not attacks or len(attacks) > 4 or any(not isinstance(a, dict) or not _text(a.get("id")) or not isinstance(a.get("position"), int) for a in attacks):
        errors.append(f"{at}.build.attacks must identify one to four attacks and positions")
    else:
        attack_ids = [a["id"] for a in attacks]
        if len(set(attack_ids)) != len(attack_ids) or [a["position"] for a in attacks] != list(range(1, len(attacks) + 1)):
            errors.append(f"{at}.build.attacks must be unique and ordered in four-slot position order")
        if game is not None and any(mid not in game.get("moves", {}) for mid in attack_ids):
            errors.append(f"{at}.build.attacks contains an unknown move ID")
    for key in ("ability", "nature"):
        item = build.get(key)
        if not isinstance(item, dict) or not _text(item.get("id")) or not _text(item.get("source")):
            errors.append(f"{at}.build.{key} needs an id and source")
        elif game is not None:
            catalog = game.get("abilities", {}) if key == "ability" else game.get("natures", [])
            ids = set(catalog) if isinstance(catalog, dict) else {str(x.get("id")) for x in catalog if isinstance(x, dict)}
            if item["id"] not in ids:
                errors.append(f"{at}.build.{key}.id is absent from game.json")
    tms = build.get("tm_requirements")
    if not isinstance(tms, list) or any(not isinstance(tm, dict) or not _text(tm.get("id")) or not _text(tm.get("source")) for tm in tms):
        errors.append(f"{at}.build.tm_requirements must be a source-backed list (empty is allowed)")
    elif game is not None:
        allowed = set(game.get("tmPrices", {}))
        for tm in tms:
            if tm["id"] not in allowed:
                errors.append(f"{at}.build.tm_requirements contains TM absent from game.json")
    tm_ids = {tm["id"] for tm in tms if isinstance(tm, dict) and _text(tm.get("id"))} if isinstance(tms, list) else set()
    initial = build.get("initial_attacks")
    valid_initial = isinstance(initial, list) and bool(initial) and len(initial) <= 2 and all(_text(x) for x in initial)
    if not valid_initial or len(set(initial)) != len(initial):
        errors.append(f"{at}.build.initial_attacks must list one or two distinct first/second attacks")
        initial = []
    elif not set(initial).issubset(attack_ids):
        errors.append(f"{at}.build.initial_attacks must be selected from the build attacks")
    if game is not None:
        species = next((p for p in game.get("dex", []) if isinstance(p, dict) and p.get("dex") == dex), None)
        if species is None:
            errors.append(f"{at}.pokemon.dex is absent from game.json")
        else:
            learned = set(species.get("pool", [])) | {species.get("start")}
            tms_for_species = set(species.get("tms", []))
            for mid in attack_ids:
                if mid not in learned and (mid not in tm_ids or mid not in tms_for_species):
                    errors.append(f"{at}.build attack {mid} is neither learned nor a legal required TM")
            for tm_id in tm_ids:
                if tm_id not in tms_for_species:
                    errors.append(f"{at}.build TM {tm_id} is not compatible with this species")
            moves = game.get("moves", {})
            for mid in initial:
                if moves.get(mid, {}).get("kind") == "buff":
                    errors.append(f"{at}.build.initial_attacks must contain attacks, not buffs")
                    continue
                if mid == species.get("start"):
                    continue
                if mid in tms_for_species and mid in tm_ids:
                    continue
                move = moves.get(mid, {})
                move_type = move.get("type")
                native_types = set(species.get("types", [])) | {"normal"}
                if mid not in set(species.get("pool", [])) or move_type not in native_types or move.get("kind") == "buff":
                    errors.append(f"{at}.build.initial_attacks contains a move that is not a legal native start choice or purchased TM")
            ability = build.get("ability", {})
            legal_abilities = {x for x in species.get("abilities", []) if isinstance(x, str)}
            if isinstance(ability, dict) and ability.get("id") not in legal_abilities:
                errors.append(f"{at}.build.ability is not legal for this species")
    alt = build.get("no_tm_alternative")
    if build.get("availability") == "optimized" and (not isinstance(alt, dict) or (
            alt.get("available") is False and not _text(alt.get("reason"))) or (
            alt.get("available") is not False and (not _text(alt.get("build_id")) or not isinstance(alt.get("attacks"), list) or not alt["attacks"]))):
        errors.append(f"{at}.build.no_tm_alternative must identify a measured no-TM build")


def _validate_seed_set(seeds: dict[str, Any], label: str, errors: list[str]) -> None:
    ids = seeds.get("ids")
    if not isinstance(ids, list) or not ids or any(not isinstance(seed, int) or seed < 0 for seed in ids) or len(set(ids)) != len(ids):
        errors.append(f"{label}.ids must contain unique nonnegative integer seeds")
        return
    if seeds.get("count") != len(ids):
        errors.append(f"{label}.count must equal ids length")
    canonical = json.dumps(sorted(ids), separators=(",", ":")).encode("utf8")
    digest = "sha256:" + hashlib.sha256(canonical).hexdigest()
    if seeds.get("hash") != digest:
        errors.append(f"{label}.hash must be SHA256 of the sorted compact JSON seed ID list")


def _validate_render_metadata(build: dict[str, Any], at: str, errors: list[str], game: dict[str, Any] | None, dex: int) -> None:
    ability, nature = build.get("ability"), build.get("nature")
    if not isinstance(ability, dict) or not all(_text(ability.get(k)) for k in ("name", "effect", "effect_kind", "effect_source")):
        errors.append(f"{at}.build.ability needs acquired name, effect, kind, and source")
    if build.get("ability_slot") not in ("default", "normal", "hidden"):
        errors.append(f"{at}.build.ability_slot must identify the selected slot")
    capsule = build.get("ability_capsule")
    if build.get("ability_slot") == "default" and capsule is not None:
        errors.append(f"{at}.build default ability must not require a capsule")
    if build.get("ability_slot") == "normal" and (not isinstance(capsule, dict) or capsule.get("id") != "cap" or not isinstance(capsule.get("price"), int) or not _text(capsule.get("source"))):
        errors.append(f"{at}.build normal ability must include the normal capsule acquisition")
    if build.get("ability_slot") == "hidden" and (not isinstance(capsule, dict) or capsule.get("id") != "caph" or not isinstance(capsule.get("price"), int) or not _text(capsule.get("source"))):
        errors.append(f"{at}.build hidden ability must include the hidden capsule acquisition")
    if not isinstance(nature, dict) or not _text(nature.get("name")) or any(not isinstance(nature.get(k), dict) or not _text(nature[k].get("name")) for k in ("up", "down")) or not isinstance(nature.get("resulting_stats"), dict):
        errors.append(f"{at}.build.nature needs acquired name and up/down stat labels")
    mint = nature.get("change_item") if isinstance(nature, dict) else None
    if not isinstance(mint, dict) or mint.get("id") != "mint" or not isinstance(mint.get("price"), int) or not _text(mint.get("source")):
        errors.append(f"{at}.build.nature needs a source-backed mint price")
    if not isinstance(build.get("initial_attack_details"), list) or len(build["initial_attack_details"]) != len(build.get("initial_attacks", [])):
        errors.append(f"{at}.build.initial_attack_details must describe each selected start attack")
    else:
        for item in build["initial_attack_details"]:
            unlock = item.get("unlock") if isinstance(item, dict) else None
            if not isinstance(unlock, dict) or not isinstance(unlock.get("price"), int) or not _text(unlock.get("source")):
                errors.append(f"{at}.build.initial_attack_details needs upgrade price and source")
    if game is not None and isinstance(build.get("initial_attack_details"), list):
        upgrades = {u.get("id"): u for u in game.get("upgrades", []) if isinstance(u, dict)}
        species = next((p for p in game.get("dex", []) if p.get("dex") == dex), None)
        for index, item in enumerate(build["initial_attack_details"], 1):
            unlock = item.get("unlock", {}) if isinstance(item, dict) else {}
            expected_upgrade = "start" if index == 1 else "start2"
            expected_price = 0 if index == 1 and species and item.get("id") == species.get("start") else upgrades.get(expected_upgrade, {}).get("base")
            if unlock.get("upgrade_id") != expected_upgrade or unlock.get("price") != expected_price:
                errors.append(f"{at}.build.initial_attack_details upgrade cost disagrees with game.json")
            if index == 2 and unlock.get("requires") != [{"upgrade_id": "moves", "price": upgrades.get("moves", {}).get("base")}]:
                errors.append(f"{at}.build.initial_attack_details second attack must include Repertorio cost")
    tms = build.get("tm_requirements")
    if isinstance(tms, list):
        for tm in tms:
            if not isinstance(tm, dict) or not isinstance(tm.get("price"), int) or not _text(tm.get("name")):
                errors.append(f"{at}.build.tm_requirements needs acquired name and price")
            elif game is not None and game.get("tmPrices", {}).get(tm.get("id")) != tm.get("price"):
                errors.append(f"{at}.build.tm_requirements price disagrees with game.json")
    natural = build.get("natural_pool")
    sources = build.get("acquisition_sources")
    if not isinstance(natural, list) or not natural or any(not isinstance(m, dict) or not _text(m.get("id")) or not _text(m.get("name")) for m in natural):
        errors.append(f"{at}.build.natural_pool must contain named native moves")
    if not isinstance(sources, dict) or any(not _text(sources.get(k)) for k in ("natural_pool", "starting_choices", "startup_upgrades", "nature_stats")):
        errors.append(f"{at}.build.acquisition_sources is incomplete")
    elif game is not None:
        species = next((p for p in game.get("dex", []) if p.get("dex") == dex), None)
        natural_ids = [m.get("id") for m in natural] if isinstance(natural, list) else []
        if species is None or natural_ids != species.get("pool"):
            errors.append(f"{at}.build.natural_pool disagrees with game.json")
        if species is not None:
            choices = species.get("abilities", [])
            ability_id = build.get("ability", {}).get("id")
            slot_index = choices.index(ability_id) if ability_id in choices else -1
            expected_slot = "default" if slot_index == 0 else "normal" if slot_index == 1 else "hidden" if slot_index == 2 else None
            if build.get("ability_slot") != expected_slot:
                errors.append(f"{at}.build.ability_slot disagrees with species ability slots")
        nature = build.get("nature") if isinstance(build.get("nature"), dict) else {}
        source_nature = next((n for n in game.get("natures", []) if n.get("id") == nature.get("id")), {})
        for side in ("up", "down"):
            if nature.get(side, {}).get("id") != source_nature.get(side) or nature.get(side, {}).get("name") != STAT_ES_LABELS.get(source_nature.get(side), "Sin cambios"):
                errors.append(f"{at}.build.nature {side} stat disagrees with game.json")
        if species is not None and isinstance(nature.get("resulting_stats"), dict):
            for stat, base_key in (("pa", "pa"), ("sa", "sa"), ("df", "df"), ("sd", "sd"), ("spd", "spd")):
                expected_base = float(species.get(base_key, 0))
                factor = 1.1 if source_nature.get("up") == stat else 0.9 if source_nature.get("down") == stat else 1.0
                values = nature["resulting_stats"].get(stat, {})
                if values.get("base") != expected_base or values.get("after_nature") != round(expected_base * factor, 4):
                    errors.append(f"{at}.build.nature resulting {stat} disagrees with game.json")


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not re.search(r"placeholder|tbd|unknown|unconfirmed", value, re.I)
