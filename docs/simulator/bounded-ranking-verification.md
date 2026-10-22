# Bounded ranking verification

Status: FINAL

Verified locally on 2026-10-22. No Runpod resource was created or charged. The approximately 30-minute Runpod target remains unmeasured; there is no automatic runtime cutoff.

## Real artifact and planning checks

The release binary ran all 97 damaging moves, each at initial and maximum move level, across seven enemy scenes for 60 simulated seconds on two seeds: 2,716 short laboratory matches. The follow-up measured 15 selected status/buff groups: another 420 short matches. The output was consumed by the actual all-species planner; no survival matches were played for this full-roster count.

- Engine fingerprint: `0ac15cecff2ccdc93f7f0fcee834b76736b4ef9bd1658cd2ee1f750917aa8e4a`.
- Full plan hash: `017ec2c32280784403c03c0af8f6562c383b06a636fe199488453a6e42ddf8e1`.
- 966 species; 3,010 active style/TM strata out of 3,864 possible cohorts.
- 25,579 candidate configurations, at most 12 per stratum; 966 distinct stock controls.
- Stage A ceiling: 53,090 observation matches, including stock controls.
- Stage B ceiling: 79,104.
- Independent confirmation ceiling: 63,616.
- Survival-search ceiling: **195,810**, compared with the historical 12,068,512-task funnel ledger.

These are structural task counts, not a measured runtime improvement. A laboratory scene is not equivalent in cost to a full survival match. The generic dry-run estimate without measured laboratory data is deliberately more conservative: 347,760 survival matches.

Puño Meteoro had the highest equal-weight solo fixture mean in this run. This is an observation under these fixtures, not a universal move ranking or a claim that it wins every species build.

## Executed checks

- `cargo test --locked --release --manifest-path simulator/sim-rs/Cargo.toml`: 104 tests passed across simulator/importer; one historical stage-sized I/O benchmark remains ignored.
- `cargo build --locked --release --manifest-path simulator/sim-rs/Cargo.toml --bin pokesim`: passed; three existing dead-code warnings remain.
- `.venv/bin/python -m unittest discover -s build -p 'test_*.py'`: 157 tests, three skipped, no failures.
- Focused CLI/export/display integration also passed after final exporter changes. It runs solo lab, measured synergies, species planning, A/B/confirmation, export validation and resume. Changing the plan's thread count changes its hash without rewriting the existing match cache or changing winners.
- `bash simulator/runpod/run.sh ranking smoke`: completed the real runner and exported 97 diagnostic attack rows and five independently measured build rows for Psyduck/Ditto. Its shorter duration is labelled, and the moves-page boundary rejects it as a full laboratory table.
- Full-preset dry-run: starts no simulations and reports conservative ceilings. The normal `funnel` wrapper and CLI refuse the archived exhaustive route.
- All-roster proposal tests check legal starts, learned moves, genuinely taught MTs, pure melee/ranged classification, the candidate ceiling and retained buff/status proposals.
- Cache tests check real metric reuse, unrelated learnset reuse, and invalidation for changed move damage, player stats or global boss stats. Writer lock tests reject concurrent writers and verify release.
- Both ordinary catalog/render and the optional full laboratory table generated successfully. Browser navigation returned the moves-page title, but snapshot automation timed out; the alternate computer-use browser inventory was empty. No visual screenshot approval is claimed.
- `git diff --check` and shell syntax passed.

Generated raw observations and caches are retained locally in the ignored `simulator/runpod-ranking/verification/` and `smoke/` directories. They are not committed or automatically published. Reproduce the artifacts with the commands in [the runner guide](laboratory-runner.md).
