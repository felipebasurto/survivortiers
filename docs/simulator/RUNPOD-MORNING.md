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

Inferred from this VM, not from the Pod. Three runs at 4 threads on 4 cores, 207 tasks each, 0 failures. Match rates 168.12, 171.16, and 176.08 per second. The median is 171.16. Linear scaling to 32 vCPU is 1369.28 matches per second. The full plan's upper bound is 2,147,412 tasks, including recall. That is 0.436 hours and 0.49 USD at 1.12 USD per hour. The bound counts stage B and stage C as if every shortlisted group survived. The real job should be shorter. The abort line is 2.5 hours or 3 USD, whichever the dry-run hits first. A slower reading of the old 16 vCPU host (540 matches per second at 32 threads) scaled to 32 vCPU is about 1081 matches per second, 0.55 hours, and 0.62 USD. Both sit under the cap. The Pod's own `calibrate` line is the number to trust once it has run.

## Read this first

Open `simulator/runpod-funnel/full/report.md`. The first line is the recall verdict. If recall failed, the funnel still finished and that line says so. On Ditto, recall already failed on this VM. The real best was absent from the prior's top 30 in both styles. Do not treat the funnel rows as a ranking. `rankingReady` stays false.

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
