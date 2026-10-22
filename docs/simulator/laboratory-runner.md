# Bounded attack laboratory and ranking runner

The supported default is `bash simulator/runpod/run.sh ranking smoke|full [--dry-run]`.
It uses the Rust `pokesim` combat implementation. Run `prepare` first to build the
release binary. The wrapper does not create or manage a Runpod resource.

## Artifact and command flow

The runner writes to `simulator/runpod-ranking/<preset>/`. It reruns the lab
with its existing cache on each invocation, so the artifact gets the current
binary fingerprint before planning. Smoke uses 15 seconds per lab match; full
uses the attack-lab default of 60 seconds. It resolves the engine fingerprint
from the binary and stamps a temporary runtime manifest;
the committed manifests use a documented placeholder so they do not freeze an
old binary fingerprint.

1. Run the attack lab into `lab.json` and `lab-cache/`:
   `pokesim attack-lab run <out.json> <cache-dir> [threads] [seconds] [move-id,...]`.
2. Build the bounded ranking plan from the completed lab artifact:
   `pokesim ranking plan <manifest> <lab.json> <plan.json>`.
3. Execute or resume the cached ranking ledger:
   `pokesim ranking run|resume <plan> <cache> <results>`.
4. Export `attacks.json` (`kind: attack-lab-export`) and site-compatible
   `sim-results.json` with
   `python3 -m build.laboratory_export <lab> <ranking> <game> <attacks-out> <ranking-out>`.

The runner refuses the retired exhaustive `funnel` alias and directs operators
to `ranking`. Explicit legacy production `run`/`resume` commands remain
separate commands with their historical behavior.

## Bound and seeds

Both manifests use schema 1, policy `bounded-ranking-v2`, game commit
`ce5785313b0205af8b9477423f64b0a7b7039dcd`, and at most 12 candidates per
species/style/TM stratum. The smoke manifest covers dex 54 and 132 with 15
seconds per ranking match; full covers all game species with 900 seconds per
ranking match. Both use 32 threads. Ranking stages use A seeds 1001–1002, B seeds 1101–1108,
and D seeds 3001–3016. The analytic ranking upper bound assumes four
style/TM strata per species, 12 screened candidates per stratum, three B
shortlist candidates, one D confirmation candidate, and one stock control at
A/B/D: 90 matches per stratum before planner-specific exclusions.

The laboratory task-count estimate is `attack moves x 7 scenarios x 2 levels x
2 seeds`. `--dry-run` starts no simulations. It prints this estimate and either
an analytic ranking upper bound or a real plan upper bound if a complete lab
artifact is already present. These are task counts, not wall-time or cost
predictions. Full-run time has not been measured on Runpod.
The rough planning target is about 30 minutes, to be measured on a future run;
the runner does not stop or abort at that target.

During execution, the wrapper emits a heartbeat every 60 seconds, reports
readable progress artifacts when available, and runs until the Rust command
finishes. It has no automatic wall-time/cost cutoff, calibration abort, or
timeout/relaunch loop. On shell exit or a termination signal it cleans up its
child process and preserves the command's exit status. Keep the cache and
results if a command exits unsuccessfully; resolve the cause and invoke the
appropriate Rust resume command manually.

## Reading exported values

Attack-lab DPS and kills per minute describe the tested fixtures and are not a
safety gate. Ranking survival is descriptive, and a winner means best observed
among the bounded candidate set; it does not establish a global optimum or
statistical superiority. Export requires completed artifacts whose game
commit and engine fingerprint agree. Incomplete rows are rejected. Unavailable
cohorts remain represented through the site's existing result contract.

`rankingReady` remains false. No Pod launch, actual Runpod duration, runtime
calibration, or cloud-cost measurement is implied by this runner.

## Measured interactions and the moves page

Between solo measurements and species planning, the wrapper runs
`pokesim synergy-lab run <lab.json> <guide.json> <cache-dir> [threads] [seconds]`.
It measures at most 24 selected interactions, including Hex with supported
status applicators and the strongest attacks with a matching offensive buff.
The guide preserves solo results and adds `measuredSynergies`. A pair's
comparison with the sum of solo DPS is descriptive: it is not a guarantee that
its relative gain transfers to every species. Species planning reserves a
candidate for a legal measured interaction, alongside unmeasured supported
status combinations and complementary enemy-scene specialists.

The site can show the separate laboratory table on the moves page with:

```sh
POKESIM_ATTACK_LAB=simulator/runpod-ranking/full/attacks.json python3 build/catalog.py
python3 build/render.py
```

The display requires every attack, all fourteen scene/level rows, two seeds,
and an actual duration of 60 seconds. Filtered and smoke artifacts remain
useful diagnostics, but cannot appear as the full laboratory table. Existing
historical ranking data remains labelled separately. Exporting these diagnostic
artifacts does not deploy the site or replace the published species ranking.

## Cache dependency boundaries

The match runner is isolated in `combat_runner.rs`. Search, report, roster and
stage changes do not change a match's identity. Player learnsets are keyed per
species. Global enemy tables and the species statistics used to select and
construct bosses remain global dependencies, so a boss-stat change can
invalidate the full survival cache. Laboratory measurements use their own
fixed enemies and do not depend on the species roster.

Rust writers use an OS-owned exclusive cache lock, released even when the
process crashes or is killed. Lock files remain as stable inodes; their presence
alone does not mean a run is active. The shell wrapper separately locks each
preset before changing its shared manifest, plan, logs or output files.
