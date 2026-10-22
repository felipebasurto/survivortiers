---
name: runpod-sim-ranking
description: Runs the bounded ranking simulator (run.sh ranking smoke|pilot|full) in survivortiers, on a local machine or a Runpod CPU pod, and covers updating the pinned PokéSurvivor game commit and the Gate 2 review. Use when launching, timing, costing, copying or tearing down a Runpod simulation, when the game repo updates, or when the user mentions ranking pilot/full, cpu5c, cpu3c, EUR-IS-1, pokesim, Gate 2 or ce57853.
---

# Runpod sim ranking

Playbook for the bounded ranking. Read it before touching Runpod or the game pin. Run numbers and history are in [reference.md](reference.md).

## Non-negotiables

- Never commit to `main`, merge, deploy, or touch production. Changes go on a branch with a PR.
- Results live in `simulator/runpod-ranking/` (gitignored). Do not publish them. `rankingReady` stays `false` until Gate 2 and a human review are done.
- Never print the API key. Read it with `awk -F"'" '/^apikey/ {print $2; exit}' ~/.runpod/config.toml`. Do not `cat`, `sed` or `grep` that file, because the key appears in the output.
- Run `runpodctl update && runpodctl version` before the first Runpod command.
- Before you finish: stop AND delete every pod you created, then confirm `runpodctl pod list` is `[]` and a GET on the pod id returns 404.

## 1. Local checks (free)

```sh
cd <repo>
git pull --ff-only origin main
bash simulator/runpod/run.sh prepare                 # tests + release build, about 1 min
bash simulator/runpod/run.sh ranking smoke           # about 5 s
bash simulator/runpod/run.sh ranking full --dry-run  # task upper bound, no simulation
```

`--dry-run` writes `plan.json` into `simulator/runpod-ranking/<preset>/`. It only reads an existing lab artifact if its fingerprint matches the current binary. Otherwise it prints an analytic estimate. The number is an estimate. The pod's `plan.json` is the real one.

## 2. Presets

The wrapper takes only the preset name. The manifests are fixed files: `simulator/runpod/ranking-<preset>.json`.

- `smoke`: 2 species, 15 s matches.
- `pilot`: 41 species (1 in 24 of the roster), 900 s matches.
- `full`: all 966 species, 900 s matches.

Since `aa98123` (PR #64) the ranking also searches natures. Each move group (up to 12 per stratum) fans out to neutral plus the four natures that raise the dominant offensive stat. The full plan has 441.486 matches, about 2,2 times the earlier 203.902. Abilities are still picked by `ranking_prior`, not simulated.

There is no species-list argument. Changing the subset means editing the manifest, which changes the plan. Do that only on a branch.

`ranking` ignores `POKESIM_BUDGET_USD` and `POKESIM_MAX_WALL_SECONDS`. Those only affect `run`/`resume`. Enforce a cap yourself, for example `timeout --kill-after=60s 1800s bash simulator/runpod/run.sh ranking full`.

## 3. Pick the machine and create the pod

Two CPU flavors have been used. Confirm the price and stock before you create anything:

| Flavor | vCPU | RAM | Price | Use |
| --- | --- | --- | --- | --- |
| `cpu5c` | 32 | 64 GB | 1,12 USD/h | Default in the morning runbook. Pilot timing was measured on this. |
| `cpu3c` | 32 | 64 GB | 0,96 USD/h | Used for the full run after cpu5c had no stock. The engine is the same, but the hardware is not. |

Check stock with a read-only call: `GET https://api.runpod.io/v2/catalog/cpus?include=AVAILABILITY&product=POD`, with the Bearer key.

`runpodctl pod create` (v3.0.1) has no flag for the CPU flavor or vCPU count. Create CPU pods through REST v2 with the same key:

```json
{
  "name": "pokesim-ranking-full-cpu3c-32",
  "cloud": "SECURE",
  "cpu": {"id": "cpu3c", "vcpuCount": 32},
  "dataCenterIds": ["EUR-IS-1"],
  "image": "runpod/base:1.0.2-ubuntu2204",
  "disk": 50,
  "ports": ["22/tcp"],
  "startSsh": true
}
```

Send it with `curl -X POST https://api.runpod.io/v2/pods -H "Authorization: Bearer $RPK" -H "Content-Type: application/json" -d @file.json`. Keep the body in a file.

- A 400 with "There are no longer any instances available" means no stock for that flavor. The web form can show stock while the API refuses. Retry with pauses, and alternate `dataCenterIds` (`EUR-IS-1`, then no datacenter field). For cpu5c, stock came back after about 4 minutes of retries. cpu3c succeeded on the first try.
- Do not change the flavor, vCPU count or region without asking the user. The user said region did not matter, but flavor changes the measured timing.
- Check that the web form matches what you asked for. In one session the web offered cpu3c at 0,96 USD/h while the plan used cpu5c at 1,12 USD/h.
- The account's SSH key `runpodctl-ssh-key` in `~/.runpod/ssh/` is already registered and is injected through `startSsh`.
- Get the direct SSH endpoint from `GET /v2/pods/<id>` at `ssh.direct.host` and `ssh.direct.port`. `runpodctl pod get` does not show that field. Wait until `ssh.direct` appears. It takes about 1 to 3 minutes.

## 4. Setup on the pod

SSH with inline options. Do not keep options in a shell variable: zsh does not word-split it, and the `-i` flag gets the whole string.

```sh
ssh -i ~/.runpod/ssh/runpodctl-ssh-key -p <port> -o StrictHostKeyChecking=accept-new root@<host> '<command>'
```

Write a setup script on the pod and run it with `nohup ... > /root/setup.log 2>&1 &`. Poll the log. The script does:

```sh
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq build-essential pkg-config python3 python3-pip git tmux curl ca-certificates
curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
source "$HOME/.cargo/env"
python3 -m pip install -q --user numpy Pillow
git clone -q https://github.com/felipebasurto/survivortiers.git /root/survivortiers
cd /root/survivortiers && git checkout -q main && git log --oneline -1
bash simulator/runpod/run.sh prepare
bash simulator/runpod/run.sh ranking smoke
```

Setup takes about 4 minutes; `prepare` compiles for about 1 minute. Confirm the commit is the one you expect before running anything. The `prepare` step includes the test suite. Do not skip it.

## 5. Run in tmux with a cap

```sh
tmux new-session -d -s full "cd /root/survivortiers && source \$HOME/.cargo/env && echo FULL_START \$(date -u +%FT%TZ) > /root/full.status && timeout --kill-after=60s 1800s bash simulator/runpod/run.sh ranking full > /root/full.out 2>&1; echo FULL_EXIT=\$? \$(date -u +%FT%TZ) >> /root/full.status"
```

- Size the cap at 2 to 3 times the expected run, and keep the total well under the budget you agreed with the user. A 1800 s cap at 0,96 USD/h is at most 0,48 USD of compute.
- Monitor `simulator/runpod-ranking/<preset>/runner.log`. The runner heartbeats every 60 s during long stages.

## 6. Verify before you trust the number

In `simulator/runpod-ranking/<preset>/`:

- `results.json`: `complete: true`. `counts.candidateMatchesCompleted + counts.controlMatchesCompleted` equals `plan.json` `counts.matchesUpperBound`.
- `lab.json`: `complete: true`, `partialScope: false`, `scope: all-supported-attacks`, 97 moves.
- `sim-results.json`: every row `status: confirmed`. Count species with `len(set(dex))`.
- `results.json.elapsedWallSeconds` is the ranking time. The runner's `total` lines are the lab times, with 0.1 s resolution.

If any check fails, the timing is not a clean measurement. Say so, and do not use the run as a baseline.

## 7. Copy out and clean up

Copy with a tar stream. `scp -r` on hundreds of thousands of small cache files is very slow.

```sh
ssh <ssh-opts> root@<host> 'tar -C /root/survivortiers/simulator/runpod-ranking -cf - full' | tar -xf - -C simulator/runpod-ranking/
```

If a local directory with that name already exists, rename it first. Do not merge caches from two runs. Compare SHA-256 of `results.json`, `sim-results.json`, `attacks.json`, `runner.log`, `plan.json`, `lab.json`. Then:

```sh
runpodctl pod stop <id>
runpodctl pod delete <id>
runpodctl pod list                                   # expect []
curl -s https://api.runpod.io/v2/pods/<id> -H "Authorization: Bearer $RPK"   # expect 404
```

Get the real charge from `runpodctl user` (`clientBalance`) before the pod exists and after it is deleted.

## 8. When the game updates

The game pin is `ce5785313b0205af8b9477423f64b0a7b7039dcd` (PokéSurvivor, 21 Oct 2026). Every item below carries the pin, and a partial update gives mixed results. Do all of it on a branch.

1. **Import the new game data.** The importer takes two args: `import-game UPSTREAM_CHECKOUT OUTPUT_JSON` (`simulator/sim-rs/src/bin/import-game.rs`). Write to a temp file first, then diff it with `simulator/data/game.json`. Replace `game.json` only after the diff is reviewed. It is a fingerprinted input.
2. **Update the pin everywhere it lives.** Search with `rg -n "ce5785313b0205af8b9477423f64b0a7b7039dcd|ce57853"`. At the time of writing:
   - `simulator/sim-rs/src/research.rs`: `GAME_COMMIT`.
   - `simulator/sim-rs/src/bin/import-game.rs`: `PIN`.
   - `simulator/runpod/ranking-smoke.json`, `ranking-pilot.json`, `ranking-full.json`, `production.json`, `funnel-*.json`: `gameCommit`.
   - `simulator/data/build-metadata.json`: `source_commit` and the SHA-256 digests of the upstream JS files. This is a reviewed source-acquisition task. The normal exporter does not regenerate it.
   - Test oracles: `simulator/tests/oracles/official-*-ce57853.json`, and the constants at `simulator/sim-rs/src/engine/abilities.rs:726` and `simulator/sim-rs/src/engine/kind_tests.rs:361`.
   - Doc comments that say `ce57853` in `engine.rs`, `abilities.rs`, `data.rs`, and `README.md`. These are not functional, but leave them accurate.
3. **Refresh the fingerprint.** `pokesim fingerprint` hashes the engine files and `game.json`. Any change to them changes the fingerprint and invalidates the lab and ranking caches. Old caches and results must not be mixed with the new engine. The `build/*.py` scripts already refuse archived ranking outputs for this reason.
4. **Archive, do not delete, old results.** Move `simulator/runpod-ranking/<preset>/` to a dated folder. Never feed old-commit artifacts into a new export.
5. **Run the checks, in order:**
   ```sh
   bash simulator/runpod/run.sh prepare
   bash simulator/runpod/run.sh ranking smoke
   python3 -m unittest build.test_sim_results build.test_sim_export build.test_laboratory_export build.test_funnel_export -v
   ```
   Then run the Gate 2 harness (section 9) against the new pinned checkout.
6. **Run the ranking on a pod** (section 3 to 7) only after the checks pass. Compare the new run with the old one by species and by the same metrics before anyone reads it as a change.
7. **Hand over to review.** Do not publish. Report the new commit, the changed files, the fingerprint, and the test results. Gate 2 must be open or explicitly accepted by the user first.

## 9. Gate 2: trace parity

Gate 2 is the open item that blocks the ranking. Source: [`docs/simulator/readiness-2026-10-21.md`](../../../docs/simulator/readiness-2026-10-21.md), "Remaining gates", item 2.

- **What it asks.** Validate abilities and movement against observed game traces. Capture bounded representative mature scenes from the pinned game and compare them with the Rust engine. Isolate every discrepancy before ranking. The scripted expected-value tests do not prove parity.
- **Status.** Not done as of 21 Oct 2026. Re-check before you rely on that. Do not assume it closed.
- **The harness that exists.** `simulator/gate2/frame-clock.mjs` steps the game with a fixed clock (`POKESURVIVOR_DIR` = the pinned checkout; needs `playwright`). `simulator/gate2/finding.md` records the last run: same seed gave the same canvas pixel hash twice; the Playwright PNG hash did not match; `Math.random` call counts were stable only once `AudioContext.currentTime` followed the stepped clock; sprite requests did not finish. That means the harness proves determinism for the canvas buffer, not the full game state.
- **Acceptance for a Gate 2 pass.** For each category (abilities, moves, walls/projectiles, crowd escape), pick a deterministic scene, capture the game trace, replay it in the engine, and record the match or the discrepancy. Attach the list to the PR. A listed discrepancy blocks ranking until it is fixed or explicitly accepted by the user.
- **Who decides.** The user reviews Gate 2 with the results. The agent prepares the evidence and does not declare the gate passed.

## 10. Gotchas

- Background jobs from killed shell commands report `error` later. Before trusting notifications, check `pgrep -fl "ssh -i|scp"` and `runpodctl pod list`.
- `ranking` prints `Duration is not yet measured on Runpod`. That is the wrapper's default text, not a failure.
- The web deploy form and the API can disagree on flavor. Check the flavor on the pod (`cpu.id`, `vcpuCount`) after it is created.
- A pod deployed from the web is billed the same way. If you see one in the web and it is not yours, check before you delete it.
- zsh does not expand `--include=*.rs` the way bash does. Quote globs in `rg` and `grep`.
- `ranking.rs` is inside the engine fingerprint. Any change to ranking logic changes `pokesim fingerprint`, which makes the attack lab stale. `ranking plan` refuses a lab whose fingerprint does not match. Regenerate the lab (`attack-lab run`, then `synergy-lab run`). Do not relabel `engineFingerprint` by hand, because that breaks provenance. A relabel is acceptable only as a control test in `/tmp` when the lab is verified identical.
- The attack lab is not bit-identical across machines. A pod lab and a local lab on the same code differed in 59 of 97 scores (third decimal). That changes move groups and the plan's match count by a few dozen. Compare plans by their own `matchesUpperBound`, and never mix plan and lab from different machines.
- Winners are chosen by mean survival, then damage per second (`rank_rows`). The canvas and the site sort by kills per minute. Do not read the table's order as "best kills/min" without saying so.
- Stage A keeps only the top 3 per stratum for stage B, with 2 seeds. More candidates per stratum (for example, nature variants) can push out a previous winner that stage B would have confirmed. Check this when you change the candidate count.
- Pod setup gotcha: `ssh ... 'cat > file && nohup ... &' <<EOF` backgrounds the whole list, so `cat` reads a closed stdin and the file ends up empty. Write the file in the foreground, then start the job in a separate command.
- The setup must check out the branch you are testing, not `main`. Otherwise the pod runs old code and the numbers do not match the PR.
- A 1800 s cap was tight for the nature run. Ranking took 1.642 s, with results `elapsedWallSeconds` 1.717 s, against a rough estimate of about 1.370 s. Stage A ran at about 150 configurations/s, stage B slower, and stage D about 9/s. Size the cap at 2 to 3 times the expected time, as section 5 says, not at the estimate.
