# Rust simulator

The only simulation engine and the only game-data importer are Rust. There is no JavaScript simulator, JS interpreter, vendored JS, Node validator or parity mode in this directory.

The current engine uses PokéSurvivor **ce5785313b0205af8b9477423f64b0a7b7039dcd** (21 October 2026). It is prepared for diagnostics, **not for publishing a new ranking**. The existing website and CSVs still describe the previous `5a23d49` model.

## Build and test

From the repository root:

```sh
cargo build --release --manifest-path simulator/sim-rs/Cargo.toml --bin pokesim --bin import-game
cargo test --manifest-path simulator/sim-rs/Cargo.toml
```

`sim-rs/src/engine.rs` owns combat and the frame loop. `engine/abilities.rs` implements the current ability effects, including the official fallback to primary-type damage. `data.rs` validates nature, ability and TM configurations. `research.rs` generates move groups and evaluates explicit diagnostic manifests.

## Import upstream data

Use an unmodified checkout at the exact commit above:

```sh
./simulator/sim-rs/target/release/import-game /path/to/pokesurvivor simulator/data/game.json
```

The importer parses declarative literals with a Rust JSON5 parser. It does not execute JavaScript. It applies the official ladders, melee adjustments, evolutions, projectile defaults, type chart and enemy definitions in Rust. Every imported source file carries a SHA-256 hash in the result. A different commit or dirty upstream checkout is rejected.

The dataset contains 966 species, 103 moves, 25 natures, 271 ability names and 58 TM moves. Abilities and TMs belong to species; nature and selected ability belong to a build. Natural moves and learned TMs remain distinct. A configuration cannot teach an incompatible TM or select another species' ability.

## Diagnostics

From `simulator/`:

```sh
./sim-rs/target/release/pokesim fingerprint
./sim-rs/target/release/pokesim candidates 150
./sim-rs/target/release/pokesim candidates 150 --list > /tmp/mewtwo-candidates.jsonl
./sim-rs/target/release/pokesim evaluate tests/smoke.jsonl
```

`candidates` performs no runs. It considers the natural pool plus all compatible TMs and every eligible attack lead. It reports melee/ranged, no-defense groups, own-type attack count and elemental resistance coverage. It does not impose two own-type attacks, one attack per type, or a Normal-type penalty. Nature/ability profile counts are reported separately; the command does not claim to have optimized those profiles.

A diagnostic manifest has one JSON object per run, with `gameCommit`, `engine`, `engineFingerprint`, `dex`, `nature`, `ability`, `tms`, `group`, `second`, `mode`, `seed` and `seconds`. All rows are validated before the first run. A stale fingerprint, illegal configuration, more than 20 rows or a duration above 15 simulated seconds is rejected. `mode` is `opening` (acquire moves and unlock bonds through rifts) or `assembled` (the complete group is bonded at the start). These are different questions and must remain labelled separately.

The committed smoke manifest and its result belong to the exact fingerprint they contain. Source or data changes invalidate it; generate a new manifest with the new fingerprint instead of editing historical results. Single `run` diagnostics also require an explicit duration of at most 15 seconds. Old bulk commands (`rank`, `sweep`, `synergy`, `tasks`, `repertorio`) are retired. The Python historical writers refuse `--sim`; their `--check` readers still verify the published snapshots.

## Correctness changes

- Dashes use the shared aim at the target. They do not choose a separate landing direction that maximizes hits and avoids crowds. Their actual 0.3-second protection remains.
- Enemy movement and body separation precede attack casts. Projectiles resolve before contact; fields, pickups, hazards and interactions follow. Hazards clear invulnerability on detonation, including non-pure damage.
- Ranged combat distance comes from attack reach. XP collection is a separate movement decision, not a requirement to remain inside the pickup magnet during combat.
- The normal spawn cap remains 64, as in the game. Bosses can enter above it without deleting a regular enemy. Projectile collision storage no longer has a 64-body limit or silently discards player projectiles above 80.
- The new projectile defaults actually add projectiles through upgrades. The monotype own-type damage multiplier remains ×1.2; dual types do not gain it.
- Ability hooks cover hit modifiers, incoming damage, criticals, statuses, contact retaliation, absorption, regeneration, speed, buffs and weather. Springs and traps now participate in terrain interactions, including sticky slow and ability protection.
- The artificial `--dodge` fraction is gone. Evasion probabilities come from abilities; movement comes from the bot.

## What the measurements mean

Results include actual damage taken and hit count, attempted contacts, contact time, time surrounded, longest surrounding episode, invulnerability time, dash count and hits shortly after a dash. Surrounded time samples 16 possible escape corridors against bodies and terrain; it is a diagnostic definition, not a new game rule or an added damage penalty.

The historical survival/DPS/kills formula remains only for reading and testing old results. These diagnostics do not invent weights for exposure or publish a replacement score. Selecting those weights requires calibration against real play. Neither a passing unit suite nor a 15-second smoke run establishes ranking quality, long-run fidelity, the value of a nature/ability profile, or the best build.

`tests/smoke-results.jsonl` records the 20 authorized startup runs. The crowd tests are scripted scenarios, since those short startup runs do not establish behavior during a mature swarm.

`v3/v3_data.json` and `results/` are historical inputs/results for the existing website. They are not loaded by the current engine and must not be relabelled as results from the new patch. The A/B builds and aggro/coverage presentation are preserved in the published snapshot; new recommendations need new measured results, including a combined aggro+coverage configuration where offered.

PokéSurvivor and its code are by JPTER78. Upstream sources and extracted game data retain their original licensing: [PolyForm Noncommercial 1.0.0 for the current source](https://github.com/JPTER78/pokesurvivor/blob/ce57853/LICENSE). This simulator is unofficial.
