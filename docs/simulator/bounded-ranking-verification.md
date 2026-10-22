# Bounded ranking verification

Status: FINAL

Verified locally on 2026-10-22, revised after review. No Runpod resource was created or charged. The approximately 30-minute Runpod target remains unmeasured; there is no automatic runtime cutoff.

## Real artifact and planning checks

The release binary ran all 97 damaging moves, each at initial and maximum move level, across seven enemy scenes for 60 simulated seconds on two seeds: 2,716 short laboratory matches. The follow-up measured offensive-buff groups against the best other attack in the same slot, and Hex/status pairs against their solo scores. The output was consumed by the actual all-species planner; no survival matches were played for this full-roster count.

- 966 species; 3,010 active style/TM strata out of 3,864 possible cohorts.
- 29,599 candidate configurations, at most 12 per stratum; 966 distinct stock controls (stock opener, default ability).
- Stage A ceiling: 61,130 observation matches, including stock controls.
- Stage B ceiling: 79,160.
- Independent confirmation ceiling: 63,616.
- Survival-search ceiling: **203,906**, compared with the historical 12,068,512-task funnel ledger.

These are structural task counts. The planner now also proposes Harden/Agility groups, which is why the candidate count grew from the first draft (25,579).

## Local timing evidence (not a Pod measurement)

On a 10-core development machine, with 900 seconds as the match cap:

- A 6-species sample (25, 6, 94, 149, 248, 9; 1,342 matches) finished in 5.5 s wall, 17.4 s CPU. Mean survival was 138 s and no match reached the cap, so a match cost about 13 ms of CPU on average.
- The real all-roster run was started locally and stopped in stage A: 22,244 of 29,599 candidate configurations (two seeds each) were done after 181 s. It was not run to completion, so no end-to-end figure exists.

Extrapolating the sample gives about 2,700 CPU-seconds for 203,906 matches, but survival lengthens in later rounds because the best builds survive longest, so this is a lower bound. The roughly 30-minute target is **not** established. Use `bash simulator/runpod/run.sh ranking pilot` (41 species at full length) on the chosen host first; `full` takes about its wall time × 966 / 41 plus the laboratory.

Puño Meteoro had the highest equal-weight solo fixture mean in the first draft's run. This is an observation under these fixtures, not a universal move ranking or a claim that it wins every species build.

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
