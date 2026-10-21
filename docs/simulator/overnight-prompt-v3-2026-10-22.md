# Overnight prompt: build the funnel, test small, hand over one command (v3)

/pstack:poteto-mode

This is unattended overnight work. The human reviews it in the morning. Under poteto-mode this routes to the figure-it-out skill with the Autonomous run discipline. Steps S0 to S8 below are your Phase B, already designed. Execute them under the Phase C loop and keep the Phase D log. Run until done.

**The goal tonight is a ready-to-run big simulation. You do not run it.** In the morning the human runs one command that does the full simulation and produces the 4 builds per species. Tonight you build that command, prove it on small runs, and leave it pinned and validated.

Repo: /Users/felipe/Downloads/survivortiers, main at 3fae073, origin github.com/felipebasurto/survivortiers.
Create a worktree off main on branch sim/funnel-local-2026-10-22 and work only there.
docs/simulator/overnight-prompt-*.md are untracked. Do not add them. Never use git add -A.

## Done predicate

All of the following are true, and you checked each one on the real artifact:

1. cargo test --release and the Python tests are green. The --check runs for attack_tiers, bond_tiers, species_builds and why also pass.
2. pokesim production plan accepts simulator/runpod/production.json with the fingerprint of the last commit.
3. `simulator/funnel/run.sh --preset smoke` completes end to end on 3 species. It writes builds, a v1 web document that passes validate_results, and a report.
4. After you kill it partway through, a resumed smoke run finishes and replays zero completed matches.
5. `simulator/funnel/run.sh --preset full --dry-run` prints the total match count and an ETA based on a measured rate. The full preset fits in 6 hours or less at that rate.
6. MORNING.md says exactly what to type, how long it takes, and what to check afterwards.
7. The PR is open and ready, not merged. The decision log is committed.

Never relax the predicate. If a point fails, the report says NOT VERIFIED.

## Hard limits on simulation tonight

- No single simulation command may run for more than 5 minutes of wall time.
- Total simulation compute tonight is capped at 45 minutes. Log every run's wall time in the decision log, and keep a running total.
- No exhaustive enumerations and no full-roster runs. The full preset only runs with --dry-run.
- Runpod is off limits. So are paid resources, deploys, build/indexnow.py, changes to data/*.csv, and publishing anything. site/ is untracked. You may render it for the tests.
- rankingReady stays false everywhere.
- Push only your branch. Never push to main and never force-push.
- Do not read or print ~/.runpod/* or SSH keys.
- Large outputs go to /Users/felipe/Downloads/sim-funnel/, outside the repo.
- Pause only for a push to main, a force-push, a deploy, publishing, deleting data or spending money. Everything else proceeds and gets logged.

Read first: docs/simulator/status-2026-10-21.md, readiness-2026-10-21.md, production-policy.md and web-contract.md.

## Environment

- Python is /Users/felipe/.local/bin/python3.13. Do not use the system 3.9.
- To test Rust, run `cargo test --release --manifest-path simulator/sim-rs/Cargo.toml`.
- Rebuild the binary separately with `cargo build --release --locked --manifest-path simulator/sim-rs/Cargo.toml --bin pokesim`. cargo test does not rebuild it.
- research::fingerprint() hashes engine*, data.rs, terrain.rs, radii.rs, rng.rs, math.rs, main.rs, research.rs, selection*.rs, batch.rs, production.rs, Cargo.toml, Cargo.lock and simulator/data/game.json.
- After any change to a fingerprinted file, do three things in order:
  1. Rebuild the binary and run `pokesim fingerprint`.
  2. Update engineFingerprint in simulator/runpod/production.json.
  3. From simulator/, validate with `./sim-rs/target/release/pokesim production plan runpod/production.json /tmp/plan.json`.
- Runner limits:
  - production run stops after maxWallSeconds (900 at most) per invocation. Continue with resume.
  - benchmark and run only accept scenes of 15 s or less. Those are not full matches.
- The old Runpod results are read only. They are at ~/Downloads/runpod-results-2026-10-21/runpod-results.json.
- Do not use echo with "===" in zsh.
- The machine is an Apple M4 with 4 performance cores and 6 efficiency cores.

## poteto-mode rules for tonight

- Keep a decision log with the show-me-your-work skill at docs/simulator/funnel-2026-10-22/decisions.tsv. Commit it.
- Every number follows the explain-the-number principle. It carries a measured or inferred label, a run count and a spread. For throughput, apply the benchmark-checklist skill.
- Make one commit per verified unit (sequence-verifiable-units). Use Conventional Commits titles.
- Before code that crosses function boundaries, name the data shape and run the architect skill.
- Before each commit, apply no-comments and unslop. deslop is not installed. Log that once and move on.
- Decide reversible calls yourself and log them (never-block-on-the-human).

## Decisions already made (reopen only with data)

- D1. Each species gets 4 builds: melee and ranged, each without TMs and with at least one TM. The 19 species with no legal TM get only the 2 builds without TMs, and that is documented. A TM build is reported even when it loses to the no-TM build, with the paired difference and CI.
- D2. **Simplification.** Do not port the additive model or attack_tiers.py. Their training data comes from the retired engine, and regenerating it is a big simulation. The funnel prior is the existing `ranking_prior` and proposal score in production.rs. The morning recall stage measures whether that prior is good enough.
- D3. Funnel per (species, style, branch), base role only. Aggro × Coverage stays out and is a web control.
  - A. Enumerate legal groups, score them with the prior and keep the top 30. Simulate those with 4 seeds (1001–1004).
  - B. Simulate the top 4 with 32 seeds (1101–1132).
  - C. For the top 2, sweep the distinct nature-stat class × ability profiles with seeds 1001–1004.
  - D. The best configuration and the stock no-TM control get 32 final seeds (3001–3032). These seeds are never used for selection.
  - The agent may shrink the sizes in A to C only to meet predicate 5. Log each change with its ledger.
- D4. tmCost sums only the TMs that must be taught. A move already in the natural pool costs 0. tmBudget is optional with no default. It filters at roster time and is checked again in analyze_winners.
- D5. The objective is mean paired survival against the control. Exposure margins are provisional at 10% relative to the control value. The report also gives the no_safe_candidate rate at 0%, 5% and 10%. A measured data point from the Runpod run (fingerprint 6f53…) is 4,903 of 11,058 strata as no_safe_candidate with margin 0.
- D6. The PR is ready, not a draft, and not merged.

## Steps

**S0. Baseline.**
- Get both test suites green and record the fingerprint.
- Calibrate throughput with a manifest of about 200 full-match tasks. Use 4 and 10 threads, 3 alternating runs each, and stay under 5 minutes total.
- Report matches/s and simulated s/s, both as a median with a range, plus the failure count. Name the limiter.
- The old ~340/s is inferred from Runpod. Do not use it.

**S1. TM cost.**
- Do D4 in data.rs and production.rs. candidate_value(data, c) returns Result. Add tmCost to the roster and the winner row.
- Write behavior tests with literal values:
  - the sum of prices;
  - a natural move costs 0;
  - the budget excludes candidates;
  - no budget gives an identical planHash.

**S2. Funnel subcommand.**
- Add `pokesim funnel plan|run|resume|report` that implements D3 on the existing resumable cache and checkpoint machinery.
- The ledger is deterministic. Planning runs no matches.
- Output columns:
  - dex, style, branch, group, nature, ability, tms, tmCost;
  - mean survival, CI95 and seeds;
  - exposure metrics, safe flag and fingerprint.
- Test it on 1 species with 15-second matches.

**S3. Recall stage, built but not run at scale.**
- Add `pokesim funnel recall <dex>`. It enumerates every group with the default profile (hardy, slot-1 ability) and seeds 1001–1004, then re-evaluates the top 50 with 3001–3032.
- It reports these items for each branch:
  - the real best's rank in the stage A shortlist, or "absent";
  - the gap in seconds with CI95;
  - pass or fail. Pass means the CI95 upper bound of (real − funnel) is at most 5% of the real best's survival.
- Tonight, test it only on the species with the fewest groups, under 5 minutes.

**S4. Web adapter.**
- Convert funnel output to schema_version 1 of build/sim_results.py.
- Run validate_results on the smoke output. Fix the adapter until it passes, or list exactly which contract fields cannot be produced yet.

**S5. The morning command.**
- Write `simulator/funnel/run.sh --preset smoke|fast|full [--dry-run]`.
  - It runs under caffeinate -i.
  - It refuses to start with a dirty tree or a fingerprint mismatch.
  - It loops resume across the 900 s invocation cap.
  - It prints progress and ETA.
  - It writes to /Users/felipe/Downloads/sim-funnel/<preset>-<date>/.
- Stages, in order:
  1. calibrate (200 matches);
  2. recall on Psyduck (54) and the small species;
  3. funnel on all species;
  4. web adapter plus validate_results;
  5. report.md.
- If recall fails, the run continues, but report.md says so at the top.
- Presets:
  - smoke is 3 species with 15-second matches.
  - fast is the full roster with stage B at 16 seeds, stage C on the top 1 and 16 final seeds. It must fit in 2 hours or less by the dry-run ETA.
  - full uses D3 and must fit in 6 hours or less.
- Verify predicates 3, 4 and 5 here. Kill the smoke run with SIGINT partway through, resume it, and confirm zero replayed matches.

**S6. Policy.** Document D1, D4 and D5 in production-policy.md as provisional until gate 2. Mark items that need the human as PENDING DECISION.

**S7. Gate 2 feasibility (2 hours at most, no simulator compute).**
- Use /tmp/pokesurvivor-pinned at ce5785313b0205af8b9477423f64b0a7b7039dcd. Check that the checkout is clean.
- Install playwright for python3.13. Downloading Chromium is allowed.
- Control requestAnimationFrame, performance.now, Date.now, setTimeout, setInterval and Math.random with a seed.
- Check: two runs with the same seed give the same state hash after 3,600 frames, and a different seed gives a different hash. If that fails, document why.
- No bot and no parity work.
- You can delegate this step to a subagent in its own worktree, but not while S0 calibration is running.

**S8. Hand-off.**
- Update status-2026-10-21.md. Mark the old beam as discarded, with 6,155 best_observed and 4,903 no_safe_candidate (measured).
- Write MORNING.md at the repo root of the branch. It covers:
  - the single command for the fast and full presets, and the ETA of each (inferred from S0);
  - what to look at first, which is the recall verdict;
  - how to resume after an interruption;
  - what not to do.
- Audit the decision log against what actually happened.
- Run a cross-model review of the log. Check orchestrator_capabilities and use delegate_task with a provider other than Anthropic. If none is available, say so under "Attention".
- Open the PR with the Opening a PR playbook and register it with link_pull_request.
- Final reply:
  - the predicate state;
  - the total compute used tonight;
  - the morning command;
  - the pending decisions;
  - the Attention section.
