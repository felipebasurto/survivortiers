# Funnel for the morning of 22 October

The morning search is `pokesim funnel`. It is not the 21 October production beam.

## What it does

For each species the funnel keeps four builds when a legal TM exists, and two when it does not. Each style is melee or ranged. Each branch is the natural movepool or a movepool that teaches at least one TM. The search is the base role only. Aggro and coverage stay web controls.

Stage A screens the top 30 groups from the existing prior, on seeds 1001–1004. Stage B keeps 4 groups on seeds 1101–1132. Stage C keeps 2 groups and expands nature and ability on seeds 1001–1004. Stage D measures the chosen build and the stock no-TM control on seeds 3001–3032. Those seeds are never used to choose the build. A TM build is reported even when it loses, with the paired difference and the interval.

`tmCost` is the sum of shop prices for TMs that must be taught. A move already in the natural pool costs 0. `tmBudget` is optional and has no default.

The objective is mean paired survival against the control. The exposure margin used for selection is 10% of the control value. The report also gives the no_safe_candidate rate at 0%, 5%, and 10%.

## Why this is simpler than the old Python pipeline

The old pipeline had a separate additive model and a Python search. This funnel does not port either one. The prior is the ranking prior and proposal score already in `production.rs`. One Rust command plans, runs, resumes, and writes the report. The web adapter only checks `validate_results`. It does not invent a ranking.

## What recall proves

Recall remeasures the legal groups for a species, then compares the funnel's pick with the best group it found, on seeds 3001–3032. It passes when the 95% upper bound of (real best − funnel best) is at most 5% of the real best's survival.

On Ditto, dex 132, both styles failed. The real best was absent from the prior's top 30. Melee gap upper 54.57 against a real mean of 148.11. Ranged gap upper 21.87 against a real mean of 131.28. Rank is absent for both. Stage A stays at 30 because the full-plan upper bound already fits the time and money cap. Widening A is a pending decision.

Recall does not prove the prior is good for every species. It does not prove a build is the best the game can roll. It does not make `rankingReady` true. Psyduck was not recalled on this VM because that command would have exceeded the 5 minute cap. The morning wrapper recalls dex 54 and the smallest species.

## What the numbers will mean

A winner is the best build the funnel measured under the 10% margin, or the highest survivor when nothing cleared the margin. `no_safe_candidate` means the interval did not clear the margin. It does not mean the species has no usable build. The rates at 0%, 5%, and 10% show how many strata fail as the margin gets stricter. They are not a tier list.

The morning ETA from this VM's 4-thread median of 171.16 matches/s is 0.436 hours and 0.49 USD at 1.12 USD/h for a 32-vCPU host. The plan upper bound is 2,147,412 tasks. Later stages run fewer groups than that bound. The old 16-vCPU host, scaled the same way, is slower and still under the 2.5 hour and 3 USD cap.

## Pending decisions

The 10% selection margin and the 5% recall gap are provisional. Ditto failed recall. Do not widen stage A on the strength of that one species until you decide to. `rankingReady` stays false. Do not publish a ranking from this run.

## Gate 2

The frame harness matches the canvas buffer for one seed and changes it for another. The PNG screenshot does not match across two captures of the same seed. Details are in `simulator/gate2/finding.md`.

## Compute tonight

About 81 seconds of pokesim wall. S0 was 24.424 s. The killed smoke wrapper was about 14.3 s. Resume was 17.7 s. Ditto recall was 24.1 s. The later smoke wrapper skipped the cache and used under 1 s of pokesim time. Gate 2 is Playwright and is not in that total.

## Landing

The branch is `sim/funnel-runpod-2026-10-22`. CI on the pull request and the merge commit are recorded when they finish. The morning commands are in `docs/simulator/RUNPOD-MORNING.md`.
