# Simulator result contract for the web

`build/sim_results.py` defines the publication boundary. Its version-1 JSON is an experiment export, not a replacement for `data/species_builds.csv`, `data/tiers.json`, `site/data/ranking.csv`, or `site/data/species.json`. Until a calibrated ranking method is explicitly declared and reviewed, exports are diagnostic and the current public ranking remains the source of truth.

## Required top-level shape

```json
{
  "schema_version": 1,
  "provenance": {
    "game_commit": "<40-character source commit>",
    "engine_fingerprint": "sha256:<engine and simulation input fingerprint>",
    "policy_version": "<selection and control policy version>"
  },
  "experiment": {
    "score_version": "<metric definitions version>",
    "seed_sets": {
      "screening": {"ids": [0, 1], "count": 2, "hash": "sha256:<canonical seeds>"},
      "confirmation": {"ids": [1000, 1001], "count": 2, "hash": "sha256:<canonical disjoint seeds>"}
    },
    "pokemon_dexes": [25],
    "axes": {"aggro": ["baseline", "subtle"], "coverage": ["baseline", "subtle"]},
    "expected_variants": [
      {"id": "aggro-baseline__coverage-baseline", "aggro": "baseline", "coverage": "baseline"},
      {"id": "aggro-baseline__coverage-subtle", "aggro": "baseline", "coverage": "subtle"},
      {"id": "aggro-subtle__coverage-baseline", "aggro": "subtle", "coverage": "baseline"},
      {"id": "aggro-subtle__coverage-subtle", "aggro": "subtle", "coverage": "subtle"}
    ]
  },
  "results": [],
  "unavailable_cohorts": [],
  "ranking_method": {"id": "diagnostic", "status": "diagnostic_only"},
  "optimized_potential": []
}
```

The seed lists contain the actual unique nonnegative integer IDs. Their count must match the list length, and the hash is SHA256 of the sorted IDs encoded as compact JSON (`[0,1]`). Screening and confirmation IDs must be disjoint. Each `results` row is a confirmed winner for one `(pokemon, style, availability, variant)` cohort and must state `winner_confirmed: true`. `style` is `melee` or `ranged`; `availability` is `optimized` or `no_tm`. `pokemon_dexes` declares the full species cohort under review. For each dex, all four style/availability cohorts must either be complete across the declared variant product or appear in `unavailable_cohorts` with a concrete reason. An impossible combination is never silently dropped. Each row carries the same confirmation seed hash and count, the declared `score.version`, and a `score.metrics` object of named finite values. Screening observations belong in experiment provenance or separate internal artifacts; they must not be mixed into confirmation outcomes.

The build contains up to four distinct positioned attacks, a source-backed ability and nature, and source-backed TM requirements (an empty list is valid). With `game_data`, the validator checks species ability legality, each move, every declared TM's species compatibility, and whether the species can learn off-pool moves through the listed TMs. `initial_attacks` lists one or two distinct attacks in start order and both must be among the build attacks. A stock attack is always a valid start choice; a native-pool choice must be an own-type non-buff attack; a purchased TM may also be a start choice when it is a legal TM for that species and appears in `tm_requirements`. Optimized builds include a separately measured `no_tm_alternative` with its own build ID and attack list, which must resolve to the no-TM result for the same species, style, and variant. A no-TM result must have an empty TM requirement list. This is a distinct measured branch, not a mechanically edited optimized build. Optional `game_data` validation also checks the source game commit against `simulator/data/game.json`.

## Presentation contract

The future simulator page should let a visitor choose a Pokémon and compare melee and ranged build cards. Aggro and Coverage are two small, independent controls with a visible baseline and subtle setting; all four combinations are measured and addressable, so visitors can combine them. Show each build's attacks in order, starting attack and second attack, ability, nature, TM requirements, and the measured no-TM alternative. Label any calibrated whole-build optimization aggregate “Optimized potential”; show the underlying metrics and experimental method beside it. Keep survival, damage, and other metric columns named rather than folding them into an unexplained score. A `diagnostic_only` export cannot contain ranks or optimized-potential rankings; show measured metrics only. Unavailable cohorts show their reason.

The validator rejects absent provenance, incomplete variant cross-products, incorrect or overlapping seed lists, mismatched confirmation seed sets or score versions, missing source metadata, unknown or species-illegal game catalog IDs (when game data is supplied), unconfirmed or placeholder results, dangling no-TM references, and ambiguous optimized-potential labels. A calibrated rank needs an explicit method ID, version, and calibration source. No numerical weighting is implied by this contract.

## Render-ready adapter and source metadata

`build/sim_export.py` translates the current `production.rs` JSON (`winners`, `unavailable`, `observations`, `configuration`, and `pairedConfirmation`) into the validated version-1 web document. It derives screening and confirmation seed lists from stage-tagged observations when they are not included explicitly, then stores the real sorted IDs, counts, and canonical SHA256 hashes. It preserves paired intervals and labels observed/tied outcomes without claiming statistical superiority. An unconfirmed or inconclusive candidate becomes unavailable; an absent legal stratum stays unavailable with its policy reason. No scoring weights or rank are generated.

`simulator/data/build-metadata.json` is the runtime, source-backed acquisition catalog. It records pinned source commit `ce5785313b0205af8b9477423f64b0a7b7039dcd` and SHA256 digests for `ability-fx.js`, `shop.js`, `starters.js`, `upgrades.js`, `tms.js`, and consumed `game.json`. Its 271 ability IDs resolve to either the game's exact custom description (including helper-resolved descriptions and the `plus` type bonus) or an explicit primary-type +8% fallback for abilities without a custom description. It also contains the Menta/ability-capsule prices and upgrade prices/requirements. Runtime export needs no upstream checkout or network. The asset stores restricted descriptions and static descriptors only; it does not execute or vendor game JavaScript.

The HTML adapter is a renderable integration artifact, not a live page: it produces semantic cards and Aggro/Coverage control markup while the historical ranking and page remain untouched. It includes ability slot/capsule cost, nature up/down stats and resulting multipliers plus Menta cost, attack ordering, learned pool, TM requirements/prices, first/second start unlock costs, the independently measured no-TM branch, paired uncertainty, and unavailable strata.

Use these commands after a real production run:

```sh
python3 build/sim_export.py /path/to/production.json simulator/data/game.json \
  --metadata simulator/data/build-metadata.json --out /tmp/sim-web-results.json
python3 build/sim_cards.py /tmp/sim-web-results.json 25 --out /tmp/sim-web-cards.html
python3 -m unittest build.test_sim_results build.test_sim_export -v
```

`build/test_sim_export.py` uses deliberately synthetic, test-only records. They must never be copied into a site export or presented as measured results. A production export requires the real game commit, engine fingerprint, policy version, nonempty disjoint actual seed sets, completed confirmation, and complete winner/unavailable variant declarations. The source asset can be regenerated only as a reviewed source-acquisition task; the normal exporter does not regenerate it.

## Card details

In each existing Pokémon ficha, A/B remain the main build choices. Place two compact switches directly under them: **Más agresivo** and **Cubrir tipos**. Both on must resolve to the separately evaluated combined variant. Changing a switch updates the full configuration and its requirements, not just a visually substituted attack.

Show **Habilidad** with its exact effect from this game, whether it is a normal or hidden slot, and any capsule requirement. Show **Naturaleza** with the raised/lowered stats, resulting build stats, and Menta cost; neutral natures remain recognizable even when their simulated profile is shared. Put an **MT** badge on taught attacks, alongside a small “MT necesarias” list; compatible does not mean already learned or guaranteed in today's shop. List the first and optional second starting attack with the relevant Movimiento inicial/Repertorio/Segundo movimiento inicial requirements. These unlocks come from the pinned source catalog and are enforced by the render-metadata validator.

Offer **Sin MT** as the measured alternative. It still states its own recommended ability/nature, so “Sin MT” is not confused with “sin mejoras”. A short explanation reports the concrete tradeoff: damage/survival/contact exposure for Aggro, and resistant enemy types or species covered for Coverage. For monotype Pokémon, disclose the actual ×1.2 own-type bonus; do not display that bonus on dual-type builds.

## Integration paths

1. The simulation runner writes the versioned export and records the exact game commit, engine fingerprint, policy version, metric version, and canonical seed IDs.
2. Before any renderer consumes it, call `validate_results(document, game_data)` with `game_data` loaded from `simulator/data/game.json`. A failure blocks publication.
3. A future web implementation can consume validated JSON in a new simulator page/module and localized strings. `build/sim_cards.py` proves a validated document can render cards, but does not implement or publish the page. Do not wire exports into `build/catalog.py`, `build/species_builds.py`, `build/tiers.py`, or the existing `data/species_builds.csv` ranking until a separately calibrated policy is approved and measured.
4. After a later approved integration, the static renderer can emit page data beside the current `site/data/species.json`; the interactive page may load that resource. This contract itself does not alter the existing build or ranking generation path.
