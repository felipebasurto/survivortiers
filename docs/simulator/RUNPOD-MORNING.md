# Runpod morning

Rent a CPU Pod `cpu5c` with 32 vCPU. Do not rent a GPU. The rate used for the estimate is 1.12 USD per hour. This repo does not create the Pod, and it does not terminate it.

## Install

On the Pod, install Rust with rustup and a C linker. Ubuntu needs `build-essential` and `pkg-config`. Python 3.12 needs `numpy` and `Pillow`, the same packages as `.github/workflows/tests.yml`.

```sh
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
sudo apt-get update && sudo apt-get install -y build-essential pkg-config python3 python3-pip
python3 -m pip install --user numpy Pillow
```

## Clone

```sh
git clone https://github.com/felipebasurto/survivortiers.git
cd survivortiers
git checkout main
```

`main` must contain this funnel. The game pin inside the engine is `ce5785313b0205af8b9477423f64b0a7b7039dcd`.

## Commands, in order

```sh
bash simulator/runpod/run.sh prepare
bash simulator/runpod/run.sh funnel full --dry-run
POKESIM_HOURLY_USD=1.12 POKESIM_BUDGET_USD=3 bash simulator/runpod/run.sh funnel full
```

`prepare` tests and builds the release binary. `funnel full --dry-run` prints the match ceiling, the ETA, and the cost. It does not simulate. `funnel full` calibrates on the Pod, runs recall for Psyduck (dex 54) and the smallest pool, then searches every species. Each invocation stops at the plan's 900 second wall and the wrapper resumes it. Output lands in `simulator/runpod-funnel/full/`. The archive is `simulator/runpod-funnel/funnel-results.tar.gz`. It leaves out `cache`, `plan.json`, and `recall-cache-*`.

`funnel full` fills in the wrapper from `vm-rate.json` when the environment does not. The wall is `maxHours` times 3600, so 9000 seconds. An unset budget becomes `maxUsd`. The morning command sets the budget to 3 USD and the price to 1.12. `cost_limit` subtracts 300 seconds from the dollar budget, then clamps to that wall. The clamp is 9000 seconds. `run` and `resume` still default to 7200 seconds. On this ledger, 7200 seconds would exit 75 before the matches finished.

## ETA and cost

Inferred from this VM, not from the Pod. Three runs at 4 threads on 4 cores, 207 tasks each, 0 failures. Match rates 168.12, 171.16, and 176.08 per second. The median is 171.16. Linear scaling to 32 vCPU is 1369.28 matches per second. `funnel full --dry-run` on fingerprint `a3f664be…` printed `tasksUpperBound 12057504`, `fullGroupCap 5932`, `strataFull 1882`, `strataBeam 1128`, ETA 2.446 hours, cost 2.74 USD at 1.12 USD per hour. The bound includes recall (95,844 tasks) and counts stage B and stage C as if every shortlisted group survived. The abort line is 2.5 hours or 3 USD, and match time also has to fit the wrapper wall the same command will enforce. This estimate meets the money line and the 2.5 hour line. A linear scale of the old 16-vCPU host (about 540 matches per second at 32 threads) is about 1080 matches per second, 3.10 hours, and 3.47 USD. That reading misses the cap. The full command stops when the Pod calibrate rate cannot finish the upper bound inside the wrapper wall. At 9000 seconds that rate is about 1340 matches per second.

The wrapper clock starts after planning, calibrate, and recall. Match time at the inferred rate is 8806 seconds. The wrapper allows 9000 seconds, so about 194 seconds remain for checkpoint indexes and the gap between invocations. The 3 USD budget is 9643 seconds at 1.12 USD per hour. After the 300 second reserve the dollar cap is 9342 seconds, and the 2.5 hour wall is the one that binds. The dry-run aborts when match time exceeds that wall. A default wall of 7200 seconds would have aborted this plan.

The 2.446 hour figure is match time only. It does not include the read of checkpoints between stages. Each stage is indexed once. On this 4-core VM, three reads of 1,193,640 checkpoint files took 36.4 s, 20.8 s, and 5.6 s. The median is 20.8 s. The fastest run spent the whole wall on one core. CPU time equaled wall time. `drop_caches` was not permitted, so the reads were not forced cold. Ranking 298,410 four-seed comparisons took 0.13 s. A linear scale of that median to the 10,220,732 stage A files is about 178 s, and the slowest of the three readings scales to about 312 s. That scale was not remeasured at the new size. It still sits under the 900 second invocation wall. The slow reading is larger than the 194 seconds left on the wrapper after match time, so one cold index can still make the wrapper exit 75. That is not a new measured end-to-end ETA.

Smoke checkpoints in a 200-file sample average 678 bytes. `du` on the earlier 5,020-file smoke cache is 21 MB, about 4 KB per file. The full upper bound is 12,057,504 files. At 4 KB each that is about 49 GB of disk blocks, plus a 5.4 GB plan file. Keep at least 60 GB free for the cache and one plan. `write_plan` keeps part files and writes a second copy, then replaces `plan.json`. A rerun still has the old plan until that replace, so 60 GB does not cover the part files plus the second copy. Check `df` before a rerun. The runner loads that plan into memory and clones it to check the hash. Rent the 64 GB cpu5c. Smoke and full write the same archive, and the archive omits the cache and the plan. The dry-run reads `plan-counts.json` and does not parse the plan. The wrapper reads the recall list from the front of the plan the same way.

On this VM, `df -i` shows 9,304,313 free inodes. The ledger can create 12,057,504 checkpoint files, so this disk cannot hold the full cache. `funnel full` stops before calibrate when free inodes are below that file count. `funnel full --dry-run` prints the count and does not stop on it. Run `df -i` on the Pod before you rely on the ETA.

Every stage A candidate on this plan opens with a move the game can produce. The set is the species' own type pools, plus Normal, plus a taught TM, plus the stock start. 0 of 2,555,183 candidates fail that check. The rejected-start rate is 0, down from 42.5% (971,403 of 2,284,253) on the widened plan. 0 of 3,010 strata have no legal opener. 305,486 openers are taught TMs. Those sit on the TM branch and count in `tmCost`. The 334 strata an earlier count called no-legal-start were Normal openers. The game allows Normal for every species. When a species would otherwise have no web row, the adapter still publishes the measured stock control. Twelve melee TM strata are back. Their opener is a natural attack, and the taught move is Dragon Dance. That partner also lengthens TM strata that already had a group. Salazzle (dex 758) ranged `optimized_tm` is beamed. Its stored shortlist has 30 groups, and 10 teach Dragon Dance. A review of `b1eba97` counted that stratum crossing the 5932 cap.

## Read this first

Open `simulator/runpod-funnel/full/report.md`. The first line is the recall verdict. If recall fails, the funnel rows are diagnostic. They are not a ranking, and the run should not buy more seeds to close the gap. On Ditto, recall was run again on this VM after stage A started enumerating every legal group under the cap. Both styles still fail the 5% gap. The cause is the four screening seeds disagreeing with the 32 confirmation seeds. The screening best is in the shortlist (melee prior rank 43, ranged prior rank 107). The confirmation winner is a different group. `rankingReady` stays false.

For a stratum over the group cap, recall keeps the top 30 groups by prior. Stage A for that stratum uses the prior beam and then truncates to 30. Those lists can differ. Ditto is under the cap, so its recall compared the full list. The failure there stays the four screening seeds against the 32 confirmation seeds. A failed recall still leaves diagnostic rows.

## Resume

If the SSH session dies, the cache is on the Pod disk. From the repo:

```sh
POKESIM_HOURLY_USD=1.12 POKESIM_BUDGET_USD=3 bash simulator/runpod/run.sh funnel full
```

The same command plans again and skips completed checkpoints. A stale lock whose process is gone is removed. Do not delete `simulator/runpod-funnel/full/cache`.

## Copy the archive back

From your machine, with the Pod's SSH port:

```sh
scp -P <port> root@<pod-host>:~/survivortiers/simulator/runpod-funnel/funnel-results.tar.gz .
```

The path on the Pod follows wherever you cloned. Copy `report.md` as well if you want the verdict without unpacking.

## Terminate

Stop the Pod in the Runpod UI when the archive is on your machine. This script never stops the Pod. Billing continues until you terminate it.
