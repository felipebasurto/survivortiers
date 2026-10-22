# Bounded laboratory ranking

Status: implemented; local verification complete, Runpod timing unmeasured

## Product contract

This is a practical ranking for a fangame. A result is the best observed build in a small, reproducible candidate set, not a global optimum. The target is roughly 30 minutes on the intended Runpod CPU host, measured end to end. There is no automatic elapsed-time or spend cutoff, calibration rejection, or relaunch loop. An unexpectedly slow run continues while a human or supervising agent examines minute-by-minute progress. This change does not create or rent a Pod.

## Search

1. Run each damaging move alone with a synthetic, balanced, neutral attacker and no ability. Measure initial and maximum move levels on the same enemy fixtures: one resistant target, line/surround/approach at 3 and 12 targets. Default duration is 60 simulated seconds, with two deterministic seeds. Line and surround hold their placement; approach moves. Finite-HP targets replenish. Hostile effects cannot kill or displace the attacker.
2. Measure at most 24 selected attack/status and attack/buff interactions with the same laboratory fixtures. Use measured damage and per-scenario strengths to construct a diverse set of at most 12 legal groups per species, melee/ranged style, and natural/taught-TM branch. Four slots include any buff. Reserve alternatives for complementary attacks, category-compatible offensive buffs, and supported status/Hex interactions. Never enumerate all four-move combinations. Nature is neutral; ability selection uses an explicit group-dependent prior. These choices are heuristics.
3. Screen all proposals on two shared seeds. Re-measure the best three on eight new seeds. Measure the winner on sixteen independent confirmation seeds. Use a fixed stock/no-TM control for comparison. Survival selects builds. DPS, kills, contact damage and exposure remain separate observations; exposure cannot veto a surviving winner.
4. Export attack fixture measurements and independently checked survival observations. Retain provenance, unavailable cohorts and disjoint seed sets. Do not replace published historical rankings with fabricated or smoke-test numbers.

The candidate ceiling is a deliberate search policy. It is distinct from an elapsed-time limit, which the user explicitly rejected.

## Reuse and monitoring

Cache match identities depend on combat code/data, the actual configured species, moves, nature, ability, seed and simulated duration. Stage names, plan identity, roster order and reporting edits must not invalidate reusable matches. Enemy roster/mechanics and global combat changes may invalidate all survival results: other species can occur as enemies, so per-species invalidation is not universally safe. Laboratory fixtures avoid those encounter dependencies and can reuse measurements independently.

Writes are atomic and a writer lock prevents overlapping runs in a cache directory. Progress must remain observable at least every minute, including a process heartbeat when no batch has finished. A heartbeat is not a promise that a remote supervising agent has been scheduled; that supervision is arranged when a Pod is actually started.

## Verification before PR

- Actual CLI smoke from laboratory through plan, survival rounds and Python export.
- All-roster planning without playing matches: <=12 legal candidates in every stratum, real TM requirements, valid openers, and useful four-slot/buff/status alternatives.
- Deterministic fixtures, target replenishment and initial/max level damage behavior.
- Resume reuses completed observations; independent confirmation seeds remain independent.
- The normal wrapper cannot launch the archived exhaustive funnel.
- Site can display measured laboratory DPS with explicit fixture labels, separately from historical ranking data.

A full Runpod runtime/cost claim requires a later run on the selected host. No desktop smoke establishes that claim.
