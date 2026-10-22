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

`prepare` tests and builds the release binary. `funnel full --dry-run` prints the match ceiling, the ETA, and the cost. It does not simulate. `funnel full` calibrates on the Pod, runs recall for Psyduck (dex 54) and the smallest pool, then searches every species. Each invocation stops at the plan's 900 second wall and the wrapper resumes it. Output lands in `simulator/runpod-funnel/full/`. The archive is `simulator/runpod-funnel/funnel-results.tar.gz`.

## ETA and cost

Inferred from this VM, not from the Pod. Three runs at 4 threads on 4 cores, 207 tasks each, 0 failures. Match rates 168.12, 171.16, and 176.08 per second. The median is 171.16. Linear scaling to 32 vCPU is 1369.28 matches per second. `funnel full --dry-run` on fingerprint `9e41dc3b…` printed `tasksUpperBound 10939668`, `fullGroupCap 5082`, `strataFull 1905`, `strataBeam 1093`, ETA 2.219 hours, cost 2.49 USD at 1.12 USD per hour. The bound includes recall (69,024 tasks) and counts stage B and stage C as if every shortlisted group survived. The real job should be shorter. The abort line is 2.5 hours or 3 USD. This estimate meets both. A linear scale of the old 16-vCPU host (about 540 matches per second at 32 threads) is about 1080 matches per second, 2.81 hours, and 3.15 USD. That reading misses the cap. Trust the Pod's own `calibrate` line. If that rate is under about 1216 matches per second, the upper bound misses 2.5 hours. Stop before the full run in that case.

The 2.219 hour figure is match time only. It does not include the read of checkpoints between stages. Each stage is indexed once. On this 4-core VM, three reads of 1,193,640 checkpoint files took 36.4 s, 20.8 s, and 5.6 s. The median is 20.8 s. The fastest run spent the whole wall on one core. CPU time equaled wall time. `drop_caches` was not permitted, so the reads were not forced cold. Ranking 298,410 four-seed comparisons took 0.13 s. A linear scale of that median to the 9,137,012 stage A files is about 159 s, and the slowest of the three readings scales to about 279 s. That scale was not remeasured at the new size. It still sits under the 900 second wall.

Smoke checkpoints in a 200-file sample average 678 bytes. `du` on the earlier 5,020-file smoke cache is 21 MB, about 4 KB per file. The full upper bound is 10,939,668 files. At 4 KB each that is about 42 GB of disk blocks, plus a 4.8 GB plan file. Keep at least 50 GB free. The runner loads that plan into memory and clones it to check the hash. Rent the 64 GB cpu5c. Smoke and full write the same archive, `simulator/runpod-funnel/funnel-results.tar.gz`. The dry-run reads `plan-counts.json` and does not parse the plan. The wrapper reads the recall list from the front of the plan the same way.

Of the 2,284,253 stage A candidates, 971,403 have a lead the web contract will not publish. That is 42.5%. The proxy-top candidate is illegal in 1,212 of 2,998 strata. 387 strata have no legal lead at all. The adapter drops those rows. When a species would otherwise have no web row, it publishes the measured stock control.

## Read this first

Open `simulator/runpod-funnel/full/report.md`. The first line is the recall verdict. If recall failed, the funnel still finished and that line says so. On Ditto, recall was run again on this VM after stage A started enumerating every legal group under the cap. Both styles still fail the 5% gap. The screening best is in the shortlist (melee prior rank 43, ranged prior rank 107). The confirmation winner is a different group. Do not treat the funnel rows as a ranking. `rankingReady` stays false.

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
