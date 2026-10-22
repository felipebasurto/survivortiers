# Funnel for the morning of 22 October

Predicates 1 to 9 hold. CI is green on PR 59 and on main `3b4c8b3`.
A fresh clone of `origin/main` passed `prepare`, `funnel smoke`, and `funnel full --dry-run`.
Smoke wrote Caterpie, Ditto, and Eevee, a v1 web document that passed `validate_results`, and `report.md`. The branch resume rewrote 0 of 8,682 checkpoints.
Dry-run printed 12,057,504 tasks, 2.446 hours, and 2.74 USD. `production plan` accepted 240,480 tasks at fingerprint `28efded8…`.
The pinned site render of this tree matches `3fae073`: 2,130 files, empty diff.
Merged https://github.com/felipebasurto/survivortiers/pull/59 by rebase at `3b4c8b3cc8a0b50dd8c453861165c390b13cf2ee`. This report is the commit after that tip.
Morning: rent a 32-vCPU cpu5c, run the commands in `docs/simulator/RUNPOD-MORNING.md`, and terminate the Pod yourself.
Inferred ETA is 2.446 hours and 2.74 USD at 1.12 USD per hour. The wrapper stops under about 1206 matches per second.
Pokesim wall tonight is about 853 seconds, under 45 minutes. `rankingReady` stays false.

The morning search is `pokesim funnel`. It is not the 21 October production beam.

## What it does

For each species the funnel keeps four builds when a legal TM exists, and two when it does not. Each style is melee or ranged. Each branch is the natural movepool or a movepool that teaches at least one TM. The search is the base role only. Aggro and coverage stay web controls.

Stage A enumerates every legal group for a species and branch when that count is at most 5932, and screens them on seeds 1001–1004. The cap is the largest distinct group count whose morning ledger stays inside 12,323,520 tasks, which is 2.5 hours at the 1369.28 matches per second inferred for 32 vCPU. Above the cap, stage A keeps the prior shortlist of 30. On this roster that is 1882 fully enumerated strata (2,521,343 groups) and 1128 beamed strata (33,840 groups). The prior move beam of 24 applies only on the beamed strata. The plan has 3,010 strata, the same count as the shortlist plan. Stage B keeps 4 groups on seeds 1101–1132. Stage C keeps 2 groups and expands nature and ability on seeds 1001–1004. Stage D measures the chosen build and the stock no-TM control on seeds 3001–3032. Those seeds are never used to choose the build. A TM build is reported even when it loses, with the paired difference and the interval.

A legal opener is the game's `startChoices` at commit ce57853. That set is the move pools of the species' own types, plus Normal, plus every TM taught on that build, plus the stock start `G.baseStartOf(dex)`. The stock start counts when it is off-type. Confusion is Psyduck's stock start. A TM opener is generated only on the TM branch, and it counts in `tmCost`. The recorded second start is the off-type stock start when the group keeps it beside another opener, and it has to differ from the first. Buffs are not openers. A taught buff is still a legal partner. Twelve species have a melee TM stratum only because Dragon Dance can sit beside a natural melee opener. Those strata are in the plan. The same partner also lengthens TM strata that already existed. Salazzle (dex 758) ranged `optimized_tm` is beamed on this plan. The stored shortlist has 30 groups, and 10 of them teach Dragon Dance. A review of `b1eba97` counted that stratum crossing the 5932 cap. This check confirmed the current side of that count.

`tmCost` is the sum of shop prices for TMs that must be taught. A move already in the natural pool costs 0. `tmBudget` is optional and has no default.

The objective is mean paired survival against the control. The exposure margin used for selection is 10% of the control value. The report also gives the no_safe_candidate rate at 0%, 5%, and 10%.

## Why this is simpler than the old Python pipeline

The old pipeline had a separate additive model and a Python search. This funnel does not port either one. The prior is the ranking prior and proposal score already in `production.rs`. One Rust command plans, runs, resumes, and writes the report. The web adapter only checks `validate_results`. It does not invent a ranking.

## What recall proves

Recall remeasures the legal groups for a species, then compares the funnel's pick with the best group it found, on seeds 3001–3032. It passes when the 95% upper bound of (real best − funnel best) is at most 5% of the real best's survival.

On Ditto, dex 132, both styles still fail D6 after the widening. The run is fingerprint `9e41dc3b839ba0847d75798eadbf9a4435344e84301421bfcce540bff1960a92`, file `/tmp/recall-ditto-wide.json`. Ditto is under the cap (44 melee groups, 445 ranged), so the shortlist is every legal group. The screening best is in that shortlist. Melee prior rank 43, gap upper 74.43, real mean 148.11. `funnelId` and `realId` are `tackle,swords-dance`. The 32-seed confirmation winner is `tackle,agility,harden`. The four screening seeds ranked that group 42nd of 44, so stage B's four groups never see it. Ranged prior rank 107, gap upper 27.03, real mean 131.28. `funnelId` and `realId` are `hyper-voice,rapid-spin,agility,harden`. The confirmation winner is `hyper-voice,hyper-beam,rapid-spin,nasty-plot`. Those two ranged means differ by 0.66 seconds. The paired interval's upper bound is 27.03, and 5% of 131.28 is 6.56. The confirmation winner's screening rank is 3, which is inside stage B, but recall scores the screening winner. The 5% rule was left as written. An earlier recall, when the real best was absent from a top-30 shortlist, is a different measurement.

Recall does not prove the prior is good for every species. It does not prove a build is the best the game can roll. It does not make `rankingReady` true. Psyduck was not recalled on this VM because that command would have exceeded the 5 minute cap. The morning wrapper recalls dex 54 and the smallest species.

## What the numbers will mean

A winner is the best build the funnel measured under the 10% margin, or the highest survivor when nothing cleared the margin. `no_safe_candidate` means the interval did not clear the margin. It does not mean the species has no usable build. The rates at 0%, 5%, and 10% show how many strata fail as the margin gets stricter. They are not a tier list.

The morning ETA from this VM's 4-thread median of 171.16 matches/s is 2.446 hours and 2.74 USD at 1.12 USD/h for a 32-vCPU host. The plan upper bound is 12,057,504 tasks. Stage A is 10,220,732 of those. Recall is 95,844. Later stages run fewer groups than the bound. A linear scale of the old 16-vCPU host is about 3.10 hours and 3.47 USD, which misses the cap. The number predicate 5 uses is the rate measured on this VM, and that one fits. The wrapper stops when the full-wave calibrate rate is under about 1206 matches per second, which is 0.9 of the 1340 steady rate that fills the 9000 second wall. A Pod between about 1206 and 1340 can pass that gate and still exit 75. The cache is kept. That ETA is match time. Selection reads each stage's cache once. Three reads of 1,193,640 files on this VM took 36.4 s, 20.8 s, and 5.6 s. Scaled linearly to 10,220,732 stage A files, the median is about 178 s and the slowest reading is about 312 s. That scale was not remeasured.

## Pending decisions

Stage A widening stays. Every species gets a full group search up to 5932 groups, and the prior shortlist of 30 only above that cap. Openers follow the game's `startChoices`. The 10% selection margin and the 5% recall gap stay provisional until gate 2. Ditto still fails D6, because four screening seeds disagree with the 32-seed confirmation. That recall is fingerprint `9e41dc3b…`. Ditto has no legal TM, and both of its styles were already under the previous cap of 5082, so this opener rule does not add Ditto groups. Stage B stays at 4 and stage C stays at 2. `rankingReady` stays false. Do not publish a ranking from this run.

## Gate 2

The frame harness matches the canvas buffer for one seed and changes it for another. The PNG screenshot does not match across two captures of the same seed. Details are in `simulator/gate2/finding.md`.

## Compute tonight

About 740 seconds of pokesim wall. The log through fingerprint `b8fde7d5…` was about 349 s. An intermediate smoke, before taught buffs kept their pool order, printed `total 94.6s`. The smoke on `a3f664be…` printed `total 90.9s`, wrote 20,412 checkpoints, and validated 3 web results. The dry-run on that fingerprint printed `total 73.9s` and is planning, not matches. The smoke on `28efded8…` printed `total 92.6s`, wrote 20,412 checkpoints, and validated 3 web results. That dry-run printed `total 73.8s`. A later SIGINT at 8,682 checkpoints resumed to 20,412 with 0 files rewritten. The resume printed `total 68.6s`. Gate 2 is Playwright and is not in that total. The index measurement is a unit test over fixture files, not matches.

## Attention

A shipping review of commit 477d484 failed because `rows_for` scanned every task once per candidate. At full scale that selection ran longer than the 900 second wall, so stage D never started and a resume repeated the same scan. The current code builds one index per stage. The nomination result is the same when the cache is complete. Stage A still wins when a seed exists in both stage A and stage B.

The rejected-start rate on this plan is 0. 0 of 2,555,183 stage A candidates open with a move the web contract rejects, and 0 of 3,010 strata have no legal opener. The earlier widened plan rejected 971,403 of 2,284,253 candidates, 42.5%. That check required the lead's type to be one of the species' own types, so it rejected Normal and a taught TM. The adapter now accepts Normal, the off-type stock start, and a TM start on a TM build. 305,486 candidates open with a taught TM. Every one of those is on the TM branch and has `tmCost` greater than 0. Psyduck's Confusion stays a no-TM opener. Ice Beam is an opener only when that TM is taught.

The full upper bound is about 49 GB of checkpoint blocks, plus a 5.4 GB plan. Keep at least 60 GB free for the cache and one plan, and rent the 64 GB cpu5c, because the runner loads the plan and clones it to check the hash. A rerun writes part files and a second plan copy before it replaces `plan.json`. This VM's dry-run reported 9,304,251 free inodes, short of 12,057,504 checkpoint files. `funnel full` stops before calibrate in that case. The archive omits the cache and the plan.

The wrapper wall for `funnel full` is 9000 seconds, from `maxHours` 2.5. Match time at the inferred rate is 8806 seconds. About 194 seconds of that wall remain after the matches. The stage A index scale was not remeasured, and its slow reading is larger than that remainder. One plan load of the 5.4 GB file was not timed. The plan's own wall is 10800 seconds, so the wrapper does not restart the process and reread the cache while time remains. A 900 second plan wall did that on every resume. The 3 USD line is 9642 seconds before the 300 second reserve, so 2.5 hours binds. A 7200 second wrapper would exit 75 before this ledger finished. The dry-run aborts when match time exceeds the wall the wrapper will enforce.

Calibrate's 200 matches on 32 threads are not equal length. The gate multiplies the raw rate by 7/6.25 and compares that with 0.9 of the steady rate the wrapper needs, about 1206 matches per second. A slow sample of a true 1369 passes. A fast sample of a true 1080 fails.

Recall's funnel pick is the best screening member of its own shortlist. Under the cap that shortlist is every legal group, and stage A uses the same list. Over the cap, recall keeps the top 30 by prior. Stage A uses the prior beam and then truncates to 30. Those lists can differ. Stage D and the 32-seed confirmation use other seeds and can name another group. Ditto is under the cap. Its recall failure is still the four screening seeds against the 32 confirmation seeds. If recall fails, the rows are diagnostic.

Harden (Fortaleza) and Agility are not forced into a fourth slot. `visit_groups` in `production.rs` keeps each attack group and appends buff copies only when the attack list is shorter than 4. A size-4 attack group gets no buff. `each_legal_group` does the same for strata under the cap, and that path does not use `MOVE_BEAM_CAP`. `main.rs:1037` is `group_name` for the old research sweep. It appends `agility` or `harden` when `kit.buffs` bit 2 is set. `kits` builds those kits as candidates. For two attacks it pairs an attack buff with either status move. For three attacks it offers an attack buff, and separately a Harden or Agility kit. The funnel does not call `kits` or `group_name`. On Ditto the melee confirmation winner is `tackle,agility,harden`, so the data selected both status moves. The ranged confirmation winner is `hyper-voice,hyper-beam,rapid-spin,nasty-plot`, with neither. The smoke web row for Ditto melee is `body-slam,tackle,swords-dance,harden` because that group won the staged search.

## Landing

The shipping review of `a40aacb` returned PASS+NOTES. That tree is the tree on main. The notes are that the 1369 rate is a linear scale of this 4-core VM, that about 194 seconds of wrapper slack sit against an unmeasured plan load and a stage A index whose slow scaled reading is about 312 seconds, and that a Pod between about 1206 and 1340 can pass and still exit 75. The review of `11ecbc9` also returned PASS+NOTES. An out-of-range `POKESIM_CALIBRATE_FLOOR` exits 2 after the 200 calibrate matches, not before them.

PR 59 CI was green on `a40aacb` (rust and python). The rebase-merge tip is `3b4c8b3cc8a0b50dd8c453861165c390b13cf2ee`. CI on that commit is success: https://github.com/felipebasurto/survivortiers/actions/runs/39714671821. GitHub listed no deployments. The only workflow is `tests.yml`. Hook listing returned 403. `vercel.json` would rebuild the site if Vercel is connected. The pinned render matched `3fae073`.

A fresh clone of that tip passed `prepare` (fingerprint `28efded862f089b48f6ee92ee978c4eaaf300ff02dde17ef3781941a1b747211`), `funnel smoke` (exit 0, 20,412 tasks, 0 failures, 112.6 s, 3 validated results, `report.md` present), and `funnel full --dry-run` (exit 0, 12,057,504 tasks, 2.446 h, 2.74 USD, wrapper 9000 s, match time 8806 s). `run.sh plan` wrote a production plan with `tasksUpperBound` 240,480 and `rankingReady` false. No deploy was run. No Pod was created.

The decision log matches the work through the pinned render. The opening row still says `in progress`. The 1340 stop line in an earlier row is the gate before the 0.9 floor. The site row names `e521e7e`. The merged tree is the same tree as `a40aacb`, and that render also matched. The log did not yet contain this review or this merge. Those rows are appended with this landing.
