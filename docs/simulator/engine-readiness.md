# Rust engine readiness evidence

Pinned game source: `ce5785313b0205af8b9477423f64b0a7b7039dcd` in `/tmp/pokesurvivor-review-20261021`.
This note records the simulator's bounded validation surface; it is not a claim that every build
or long-run interaction has been compared with a live game trace.

## Buff configurations

`Ext::with_planned_buffs(data, ids)` is the canonical assembled-build API. It accepts zero, one,
or two unique IDs whose move records are stat buffs; it rejects non-buffs, duplicate IDs, invalid
indices, and a third buff. `planned_buffs: None` retains the legacy behavior, while `Some([])`
means an explicitly buff-free group. Explicit planned buffs initialize at level one and are part of
the assembled group. Opening simulations still acquire buffs through their ordinary card/rift path.
The two buff slots now apply the actual data stat field independently, including attack, speed,
defense, regeneration, physical attack and special attack, so mixed Swords Dance/Nasty Plot and
Aqua Ring combinations are representable. Existing `buffs`, `dd`, `np` and `agi` fields remain as
legacy configuration.

Focused tests cover mixed physical/special scaling, Aqua Ring regeneration, invalid configurations,
open-vs-assembled planned-buff state, acquired buff activation, and shared same-stat stacks. They do
not enumerate all buff acquisition orders or compare every buff's full five-upgrade timing against
a running game.

`benchmark_scene` is a separate CPU fixture for screening throughput, not a ranking interface. It
requires a duration no greater than 15 seconds and exactly 10, 20 or 30 fixed-HP ranged foes, which
generate regular hostile projectiles. Its mature label means a synthetic level-25 state with
`[8, 3, 5, 4, 3, 1, 1]` stat-card counts, attack levels up to five, buffs up to three and all group
bonds active. Foe positions and speeds are deterministic. Seeded terrain follows `Opts`, but does
not guarantee a wall encounter. It returns that fixture label, hostile projectile count and the
`RunResult`; it rejects rift progression. Its time is not a prediction of full-game cost and its
metrics must not enter selection.

## High-impact behavior checks

The focused engine test module contains deterministic scenes, with no call to `run_match`: crowded
contact at 10/20/30 bodies; dash protection expiration; dash clipping at a generated wall; failed
lead and companion target gates with Life Orb; Life Orb crossing the Blaze threshold; swapping to
the learned second move and removing the duplicate alternate after bonding; Moxie-family kill
progression; projectile collisions above 64 bodies; plus selected charge, bounce, homing, spin,
quake, vortex, stun, shove, drain, absorption and hazard behaviors. Each scripted combat scene is
bounded to at most 15 simulated seconds. These are behavior-specific regression tests, not a
Cartesian test of move, ability, enemy and terrain combinations.

The ability audit compared `engine/abilities.rs` against pinned `js/data/ability-fx.js`. The
specific effect set is enumerated at `engine/abilities.rs:5-167`; shared hit/status/defense/regen
handling is in that module's `Ability` and `AbilityFrame` implementations. The source audit found
no missing high-impact ability family. It found Schooling's start transform applies once to initial
max HP (`Math.round(maxHp * 1.25)`; `ability-fx.js:154-155`), while each HP level card adds an
unscaled 20 (`systems/levelup.js:11`, `entities/player.js:326`). The engine models
`round(mon.hp * 1.25) + 20 * hpCards`, with a regression test including an HP card. Imposter's stat
transform is in `data.rs:666-675`, corresponding to `ability-fx.js:161-162`.

## Explicit residual limits

- The ability inventory and selected scenarios do not prove parity for every ability pair, every
  stat threshold, or every order of Life Orb, healing and ability hooks. Source-shaped call order
  is covered only at selected boundaries.
- Buff records are data-driven and all six buff stat effects can be represented, but arbitrary
  opening acquisition paths and upgrade/expiration combinations have not been exhaustively
  compared with game traces. The fixed assembled configuration path is better-covered than the
  full level-up policy.
- Wall and projectile interaction coverage is selective: it verifies one generated-wall dash,
  target-gated casts, and crowded collision storage. It does not establish exact movement or shot
  parity through every destructible prop, liquid, wall corner, or simultaneous hit ordering.
- The mature benchmark is a synthetic fixed-foe scene; it omits full-match spawning, weather
  progression, map pickups, rift/boss scheduling and natural level-up acquisition. Use it to compare
  bounded implementation throughput only.
- Deterministic mature scenes validate engine systems under controlled inputs. They do not estimate
  full-run survival, rank candidates, establish a unique optimal build, or replace observed-game
  trace calibration.

## Source anchors

- `js/systems/combat.js`: target preflight and `pl.cast` at lines 33-39; `needsTarget` and `reach`
  at lines 80-95; buff dispatch at lines 55-56 and `buff` at lines 215-224; dash at line 314 onward.
- `js/entities/player.js`: `addBuff` shares stacks, timer and amount by stat at lines 365-372;
  the stat getters consume those shared states at lines 104-125.
- `js/data/moves.js`: six buff entries at lines 191-205, Aqua Ring at 238, Dragon Dance at 381.
- `js/data/ability-fx.js`: Schooling and Imposter at lines 154-162; effect hooks throughout this
  file are the reference for `engine/abilities.rs`.
- `engine/kinds.rs`: selected current-game effect handlers; `engine.rs` owns ordinary casts,
  Life Orb target preflight, player/enemy step ordering and buff ticking.
