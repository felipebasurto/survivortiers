# Overnight prompt for a Cursor cloud agent: ship a Runpod-ready funnel to main (v4)

/poteto-mode

This is unattended overnight work. You are a Cursor cloud agent on a Linux VM. The human runs the big simulation on Runpod tomorrow morning from `main`.

Under poteto-mode this routes to figure-it-out with the Autonomous run discipline. Steps S0 to S9 are your Phase B, already designed. Run them under the Phase C loop and keep the Phase D log. The landing in S9 follows the Shipping playbook. Run until done.

**Tonight you build and test the funnel and merge it to main. You do not run the big simulation.**

## Repo and inputs

- Repo: github.com/felipebasurto/survivortiers. Start from `main` at 3fae073 or later. Work on branch `sim/funnel-runpod-2026-10-22`.
- Game source for S8: github.com/JPTER78/pokesurvivor at commit ce5785313b0205af8b9477423f64b0a7b7039dcd.
- These files from the human's Mac are not on this VM:
  - the old Runpod results;
  - /tmp/pokesurvivor-pinned;
  - python3.13 under ~/.local/bin.
- Use these measured facts from the old Runpod run (fingerprint 6f53…) instead of the results file:
  - 240,480 tasks, 0 failures, 445 s wall time, 32 threads on 16 vCPU;
  - 11,058 strata, of which 6,155 are best_observed and 4,903 no_safe_candidate.
- Python: use 3.12, the same version as CI. Install numpy and Pillow, as the CI workflow does.
- Read first:
  - docs/simulator/status-2026-10-21.md, readiness-2026-10-21.md, production-policy.md and web-contract.md;
  - docs/simulator/runpod-hardware-2026-10-21.md;
  - simulator/runpod/README.md and simulator/runpod/run.sh;
  - .github/workflows/tests.yml.

## Done predicate

All of the following are true, and you checked each one on the real artifact:

1. CI is green on the PR and on the merge commit on `main`.
2. From a fresh clone of `origin/main`, three commands pass on this VM:
   - `bash simulator/runpod/run.sh prepare`;
   - `bash simulator/runpod/run.sh funnel smoke`;
   - `bash simulator/runpod/run.sh funnel full --dry-run`.
3. The smoke run writes three things:
   - builds for 3 species;
   - a v1 web document that passes validate_results;
   - report.md.
4. After you kill the smoke run partway through, resuming it finishes without replaying any completed match.
5. `funnel full --dry-run` prints the total match count. It also prints an ETA and a cost for a 32-vCPU cpu5c Pod at $1.12/h (inferred from the rate measured on this VM). The full preset is at most 2.5 h and $3 by that estimate.
6. `pokesim production plan` accepts simulator/runpod/production.json at the fingerprint on `main`.
7. Rendering the site from `main` gives output identical to rendering it from 3fae073. This shows the merge changes nothing the public site serves.
8. RUNPOD-MORNING.md on `main` gives every command from renting the Pod to terminating it.
9. The decision log and docs/simulator/funnel-2026-10-22/report.md are on `main`.

Never relax the predicate. A point that fails is NOT VERIFIED in the report, and it blocks the merge.

## Limits

- **Simulation tonight is small.**
  - No single simulation command runs longer than 5 minutes of wall time.
  - All simulation tonight totals 45 minutes at most. Keep a running total in the decision log.
  - No exhaustive enumerations. No full-roster runs, except with --dry-run.
- **Merging to main is authorized** once predicates 1 to 7 hold on the PR branch.
  - Merge through the PR with a rebase merge, so the small commits stay.
  - Never force-push. Never push directly to main.
- **No deploys.** Do not run wrangler, build/indexnow.py or anything that touches Cloudflare or Vercel.
  - Before merging, read the repo's deployments and commit statuses with gh. Log whether a push to main triggers any deploy.
  - If a push to main triggers a deploy, the merge is only allowed when predicate 7 holds.
  - Do not touch sprites/, data/*.csv, src/ or the site templates. jsDelivr serves sprites from @main.
- **No cloud resources.** Do not create a Runpod Pod or any paid resource.
- rankingReady stays false everywhere.
- Never print or commit secrets.
- Stop and report instead of acting in any of these cases:
  - a deploy would happen and predicate 7 does not hold;
  - CI on main goes red after the merge;
  - something would need deleting data or spending money.

## Engine facts you need

- research::fingerprint() hashes these files:
  - engine*, data.rs, terrain.rs, radii.rs, rng.rs and math.rs;
  - main.rs, research.rs, selection*.rs, batch.rs and production.rs;
  - Cargo.toml, Cargo.lock and simulator/data/game.json.
- After any change to a fingerprinted file:
  1. Rebuild with `cargo build --release --locked --manifest-path simulator/sim-rs/Cargo.toml --bin pokesim`.
  2. Run `pokesim fingerprint`.
  3. Update engineFingerprint in simulator/runpod/production.json.
  4. Validate with `production plan`.
- `cargo test` does not rebuild the binary.
- `production run` stops after maxWallSeconds (900 at most) per invocation. Continue with `resume`.
- `benchmark` and `run` only accept scenes of 15 s or less. Those are not full matches.

## poteto-mode rules for tonight

- Keep a decision log with show-me-your-work at docs/simulator/funnel-2026-10-22/decisions.tsv. Commit it.
- Every number follows explain-the-number. It carries a measured or inferred label, a run count and a spread. Apply benchmark-checklist to throughput.
- Make one commit per verified unit (sequence-verifiable-units). Use Conventional Commits titles.
- Before code that crosses function boundaries, name the data shape and run architect.
- Before each commit, run deslop, no-comments and unslop.
- Decide reversible calls yourself and log them (never-block-on-the-human).

## Decisions already made (reopen only with data)

- **D1. Builds per species.** Each species gets 4 builds: melee and ranged, each without TMs and with at least one TM.
  - The 19 species with no legal TM get only the two no-TM builds, and that is documented.
  - A TM build is reported even when it loses, with its paired difference and CI.
- **D2. Simplification.** Do not port the additive model or attack_tiers.py. Their training data comes from the retired engine. The funnel prior is the existing `ranking_prior` and proposal score in production.rs. The recall stage on Runpod measures whether that prior is good enough.
- **D3. Funnel stages** per (species, style, branch), base role only. Aggro × Coverage stays out and is a web control.

  | Stage | What runs | Seeds |
  |---|---|---|
  | A | Top 30 groups by the prior | 1001–1004 |
  | B | Top 4 | 1101–1132 |
  | C | Top 2, with every distinct nature-stat class × ability | 1001–1004 |
  | D | The best configuration and the stock no-TM control | 3001–3032, never used for selection |

  You may shrink stages A to C only to meet predicate 5. Log the ledger for every change.
- **D4. TM cost.** tmCost sums only the TMs that must be taught. A move already in the natural pool costs 0.
  - tmBudget is optional and has no default.
  - It filters at roster time and is checked again in analyze_winners.
- **D5. Objective and margins.** The objective is mean paired survival against the control.
  - Exposure margins are provisional, at 10% relative to the control value.
  - The report gives the no_safe_candidate rate at 0%, 5% and 10%.
- **D6. Recall.** It passes when the CI95 upper bound of (real best − funnel best), over seeds 3001–3032, is at most 5% of the real best's survival.

## Steps

**S0. Baseline.**
- Install the toolchain. Get both test suites green.
- Calibrate with about 200 full-match tasks at 1, half and all of the VM's cores. Use 3 alternating runs per setting.
- Report matches/s and simulated s/s as a median with a range, plus the core count, failures and limiter.

**S1. TM cost.**
- Do D4. candidate_value(data, c) returns Result. Add tmCost to the roster and the winner row.
- Write behavior tests with literal values:
  - the sum of prices;
  - a natural move costs 0;
  - the budget excludes candidates;
  - no budget gives an identical planHash.

**S2. Funnel subcommand.**
- Add `pokesim funnel plan|run|resume|report`, implementing D3 on the existing resumable cache and checkpoints.
- Planning runs no matches.
- Output columns:
  - dex, style, branch, group, nature, ability, tms, tmCost;
  - mean survival, CI95 and seeds;
  - exposure metrics, safe flag and fingerprint.

**S3. Recall subcommand.**
- Add `pokesim funnel recall <dex>`. It enumerates every group with the default profile (hardy, slot-1 ability) on seeds 1001–1004. Then it re-evaluates the top 50 on seeds 3001–3032.
- For each branch, report:
  - the real best's rank in the stage A shortlist, or "absent";
  - the gap with its CI95;
  - pass or fail per D6.
- Tonight, test it only on the species with the fewest groups.

**S4. Web adapter.** Convert funnel output to schema_version 1 of build/sim_results.py and run validate_results on the smoke output. Fix it until it passes, or list exactly which fields cannot be produced yet.

**S5. Runpod wrapper.** Extend simulator/runpod/run.sh with `funnel smoke|full [--dry-run]`. Keep the existing actions working.
- `funnel full` runs these stages:
  1. calibrate;
  2. print the ETA and cost;
  3. abort if they exceed POKESIM_BUDGET_USD;
  4. recall on Psyduck (54) and the small species;
  5. funnel on all species;
  6. web adapter;
  7. report.
- It loops resume across the 900 s invocation cap. It respects the existing budget cap and GNU timeout, and prints progress.
- It writes to `simulator/runpod-funnel/` and packs a single `funnel-results.tar.gz` at the end.
- If recall fails, the run continues, and report.md says so in its first line.
- Prove predicates 3 to 5 here. Kill the smoke run with SIGINT and resume it.

**S6. Policy.** Document D1, D4, D5 and D6 in production-policy.md as provisional until gate 2. Mark items that need the human as PENDING DECISION.

**S7. Docs.**
- Update status-2026-10-21.md. Mark the old beam as discarded, with 6,155 best_observed and 4,903 no_safe_candidate (measured).
- Update simulator/runpod/README.md.
- Write RUNPOD-MORNING.md with these items:
  1. which Pod to rent: cpu5c, 32 vCPU;
  2. how to install Rust and the build dependencies on it;
  3. the clone command;
  4. the exact commands in order;
  5. the expected ETA and cost (inferred);
  6. what to read first, which is the recall verdict in report.md;
  7. how to resume after a disconnect;
  8. how to copy funnel-results.tar.gz back;
  9. a reminder that terminating the Pod is manual and billing continues until you do.

**S8. Gate 2 feasibility (90 minutes at most, no simulator compute).**
- Clone the game at the pinned commit and install Playwright with Chromium.
- Control requestAnimationFrame, performance.now, Date.now, setTimeout, setInterval and Math.random with a seed.
- Check: the same seed gives the same state hash after 3,600 frames, and a different seed gives a different hash. If that fails, document why.
- No bot and no parity work.
- Commit the harness and the finding, or the blocker.

**S9. Land.**
- Open the PR with the Opening a PR playbook. It is ready, not a draft.
- Wait for green CI.
- Run an independent review with the Shipping playbook. Use a subagent on another model family, which reads the diff and the decision log.
- Check predicate 7.
- Rebase-merge.
- Watch CI on `main` until it is green.
- Run predicate 2 from a fresh clone of `origin/main`.
- Audit the decision log against what actually happened.

**Final reply.** It goes in report.md as well as your message. It has two parts.

The summary is 10 lines at most:
- the predicate state;
- the merged PR URL and merge commit;
- the morning commands;
- the inferred ETA and cost;
- the total compute used tonight.

The explanation, in plain language, covers:
- what the funnel does;
- why it is simpler than the old Python pipeline;
- what the recall stage proves and what it cannot prove;
- what the numbers will and will not mean;
- the pending decisions;
- an Attention section from the cross-model review.
