# Runpod sim runs: log and numbers

Companion to [SKILL.md](SKILL.md). Every number here comes from a run in `simulator/runpod-ranking/` or from the RunPod account balance. None of them is a publishable result. `rankingReady` is `false` for all of them.

All runs used commit `d6c7592` on `main`, the game pin `ce5785313b0205af8b9477423f64b0a7b7039dcd`, and the wrapper `run.sh ranking`.

## Runs

| Run | Machine | Species | Lab moves | Ranking matches | Ranking time | Matches/s | Cost (balance delta) | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| smoke, local Mac | 10 cores | 2 | 97 | n/a | < 5 s | n/a | 0 | passed |
| smoke, pod | cpu3c 32 vCPU | 2 | 97 | n/a | 4 s | n/a | included | passed |
| pilot | cpu5c 32 vCPU, EUR-IS-1 | 41 | 97 | 8.884 | 9,75 s | ≈911 | ≈0,29 USD | complete |
| full | cpu3c 32 vCPU, EUR-IS-1 | 966 | 97 | 203.902 | 333,35 s | ≈612 | ≈0,16 USD | complete |
| full, nature search (`feat/ranking-nature-search`, aa98123) | cpu3c 32 vCPU, no DC filter | 966 | 97 | 441.486 | 1.717 s | ≈257 | ≈0,6 USD (39 min pod) | complete, rankingReady false |

Notes on the table:

- The pilot number is the ranking stage only. Its total pod run was 13 s from start to finish, with the lab at 0,1 s and synergies at 0,4 s.
- The full run took 5 min 51 s from start to exit, including the lab (0,3 s) and synergies (2,6 s). The pod was created at 13:59:50 UTC, reached SSH at 14:00:26, and was deleted after 14:11 UTC.
- Matches/s are not comparable across pilot and full. They use different CPUs (cpu5c vs cpu3c) and different species mixes.
- Cost includes setup time and pod uptime, so it is larger than the pure compute cost. The pilot pod ran about 16 min and the full pod about 11 min.

## Pilot details (cpu5c)

- Pod `xulbxp8auja7as`, created 13:34:43 UTC, at 1,12 USD/h. It was first refused for stock in EUR-IS-1 for about 4 minutes. The third attempt of the loop succeeded.
- `ranking-pilot.json`: 41 species from `dex [1, 25, 49, …, 1015]`, 900 s matches, 32 threads.
- The matches `plan.json` upper bound equals completed matches: 8.884 = 2.676 round A + 3.456 round B + 2.752 round D.
- Candidate matches 7.818 and control matches 1.066. All 131 result rows are `confirmed`.
- Ranking time 9,75 s. Total pod run 13 s.
- Output copied to `simulator/runpod-ranking/pilot/`. Logs to `simulator/runpod-ranking/pilot-run-logs/`. Hashes matched.

## Full details (cpu3c)

- Pod `ylr69ezsfwgmvv`, created 13:59:50 UTC, at 0,96 USD/h. Created on the first attempt in EUR-IS-1.
- `ranking-full.json`: `dex: all`, 966 species, 900 s matches, 32 threads.
- Plan on the pod: `candidateConfigurations` 29.597, `controlConfigurations` 966, `matchesUpperBound` 203.902, `stageAMatchesUpperBound` 61.126.
- Completed matches: 178.786 candidate + 25.116 control = 203.902. Equal to the upper bound.
- Results: 3.010 rows, all `confirmed`, 966 species. 854 `unavailable_variants`, which is expected for the bounded frontier.
- `attacks.json`: 97 moves, `complete: true`, `partialScope: false`.
- Output copied to `simulator/runpod-ranking/full/` (about 1 GB, 203.903 cache files). Hashes matched.
- The local `plan.json` from the dry-run and the pod's `plan.json` can differ. The dry-run used an older local lab artifact. Use the pod's plan for the real count.

## Dry-run estimates vs real

| Estimate | Value | Source | Real |
| --- | ---: | --- | ---: |
| Pilot extrapolation to full (41 → 966) | ≈209.000 matches | 8.884 / 41 × 966 | 203.902 |
| PR #62 claim | 195.810 matches, about 30 min | PR text | n/a |
| Local dry-run `ranking full --dry-run` | 203.844 tasks | local lab artifact from an earlier run | n/a |
| Time extrapolation (pilot × 966/41) | ≈230 s | 9,75 s × 23,56 | 333 s on cpu3c |

The PR's "about 30 min" was a planning target. The measured full ranking took 5,6 min of compute on cpu3c.

## Interrupted local run

`simulator/runpod-ranking/full-interrupted-2026-10-22-partial/` is a local `ranking full` run that stopped in stage D at 1.181 of 3.010 configurations (13:08 UTC). It has no `results.json`. It predates this session, and nobody has confirmed who started it. Do not use it as a result. It is kept only for the log.

## Costs and balance

| Moment | clientBalance (USD) |
| --- | ---: |
| Start of the session, before any pod | 8,8089 |
| After the pilot pod deleted | 8,5238 |
| Before the full pod | 8,4849 |
| After the full pod deleted | 8,3221 |

The API key was exposed once in a terminal log during the first session. Rotate it at https://console.runpod.io/user/settings.

## Limits of these numbers

- Ranking results are diagnostic. `rankingReady` is `false`, and the ranking method is `bounded-ranking-v2`, labelled diagnostic-only.
- The runs measure runtime and cost only. They do not validate the engine against the game. That is Gate 2.
- The lab times are coarse: the runner reports them to 0,1 s.
