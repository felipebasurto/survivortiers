# Audit B: scoring, statistics, build search, bot, tiers, data pipeline

Report only. No sim or site change. Companion to A-fidelity (mechanics vs the game).
Scripts and the one scratch patch I used are in `docs/audit/scripts/`.

Refs read: `main` (afbb725), PR #35 `cursor/phys-special-split-08c8` (af25ebb), PR #40
`cursor/e868b5e-run-rules-ebb5` (c48d6ad, read-only; another agent is still working on it).
Unless a ref is named, `file:line` is on #40, which contains #35. Lines on main differ; I say so where it matters.

## 0. Verdict

The sim itself is deterministic and bit-exact against the JS engine, and the 200-seed medians are tight enough
(per-group seed noise sigma about 2 s). The drift is above it:

1. The published "best move" and "best group" come from a **score formula that a turret wins by construction**, then a
   hand-written filter hides the turret. The formula is also 4x noisier than survival time.
2. The **published group is not a stable result**: 4 independent 200-seed blocks gave 3, 2, 4 and 3 different
   "best" groups for the four searched species (none gave the same group every time). Nothing in the sim or the
   site says so.
3. **45% of the final rank is not simulated at all** (the frozen "sheet": stats, moves, type defence, size), and the
   weights, jitter and gates are hand-set constants repeated in several files.
4. The **bot decides which move types look good**: 27 of 29 attack starters I probed survive 8 to 31 s *less than a
   player who fires nothing* (section 5).
5. The owner's rules (Danza Espada / Maquinación, 4th slot, never melee for Gengar) are **hardcoded in about 25
   places** across Rust, Python and JS, with three different implementations of the buff choice.

Severity scale: **Critical** changes the published answer for many species and is not disclosed; **High** changes
it for some or hides noise; **Medium** will bite on the next patch; **Low** cleanup.

## 1. How I measured

| What | How | Where |
|---|---|---|
| Score sensitivity | recompute winners from the committed `solo_sweep.csv` of main, #35, #40 | `scripts/score_sensitivity.py` |
| Seed noise and group stability | `pokesim synergy --seeds 200 --seed0 {0,200,400,600}` for the six species, through the real publish rule `combos._search_picks` | `scripts/replicate_stability.py`, `scripts/sim-only-seed0-dump.patch` (scratch patch for #40: adds `--only`, `--seed0`, `--dump-runs`; not applied to the repo) |
| Starter rerun on two disjoint seed blocks | `pokesim sweep ... --group 2+2 --terrain --status`, seeds 1-200 (A) and 201-400 (B), #40 engine | same patch |
| Do-nothing baseline | `pokesim tasks` with Sustituto (inert in this mode, fires nothing) vs real starters | section 5 |
| Rank noise | re-draw `start_median_s`/`best_median_s` with sigma 2 s and 4 s and re-rank with the make_definitive formula | `scripts/rank_noise_inject.py` |
| Selection bias of "best" | parametric bootstrap on the sweep CIs | `scripts/winners_curse.py` |
| Published rank spread | `rank_p10/p90`, `p_tier` of the committed CSV | `scripts/rank_noise.py` |
| Rebuild check | `build/make_definitive.py` with default and with explicit flags | section 8, P1 |

Not verified: ficha vs planner vs tier list vs pasivas numbers on the rendered site. #40 does not render
(`build/catalog.py` raises 2320 summary-fingerprint errors; WIP, not a finding against main). I compared data
sources, not pages.

## 2. Scoring

### S1 [Critical] The multiplicative score hands 195 to 299 species to Sustituto

`stats.rs:150` (#40; `stats.rs:138` on #35):

```
run_score = time * dealt * (1 + kills)
```

`cmp_run` (`main.rs:976`) ranks by median of that, then mean of that, then median time. On the committed
`solo_sweep.csv` (966 species, 9236 starter rows):

| winner picked by | #35: species where Sustituto wins | #40 |
|---|---|---|
| time alone (median_s) | 78 | 49 |
| time x dealt x (1+kills), median (#35 formula) | **299** | **195** |
| same, mean | 221 | 157 |
| time x dealt | 258 | 172 |
| time x sqrt(dealt x (1+kills)) | 253 | 184 |
| dealt alone | 325 | 204 |

The winner differs from the time winner in 329 species on #35 (251 on #40). Median dealt for Sustituto starters is
3537 vs 1555 for the rest, kills 44 vs 19, survival 70.9 s vs 61.2 s. The three factors are correlated and all
favour the same move, so the product multiplies one advantage three times: 1.16 (time) x 2.3 (dealt) x 2.3 (kills)
is roughly 6x on score, against 1.16x on time.

**Root cause.** Sustituto is a real damage turret in the game (`moves.js:388`, kind `turret`, dmg 14, rate 0.4 s,
range 280). In the sim a field of kind 8 fires at the nearest enemy every 0.4 s whether or not the player is in
danger (`engine.rs:2509-2523` on #35), so it adds damage and kills with no positioning cost, and the kite bot
survives longer with it. It is also strong on time alone (49 to 78 species), so some of this is a true sim result.
The formula then multiplies it. The patch (S3) does not fix the cause.

**Fix.** Pick the "best move" by survival time (median, bootstrap CI), as before #35. If damage and kills must
count, add them as a tiebreak among candidates whose CIs overlap on time, never as a product. If Sustituto should
not be a "best attack", that is a data fact about the move (it is a turret), keep it as a per-move property
(`publishable`) in one place.

### S2 [High] `dealt` is potential damage, not damage

`hit_one` returns `amount = dmg * atk * type * weather * taken` (`engine.rs:917-922`) with no clamp to the enemy's
remaining HP, no shield soak, and it is summed per hit (`engine.rs:2336, 2353, 2482, 2573`). The doc comment on
`run_score` calls it "post-guard, pre-shield". Overkill on 1-HP swarm enemies and multi-hit pierce count in
full. A move that hits many small enemies many times (turret, chain) gains over a single heavy hit.

**Fix.** Credit `min(amount, hp + shield)` or drop `dealt` from the ranking and keep it as a report column.

### S3 [High] The Sustituto patch lives in three unconnected places

- `main.rs:438` `publishable_attack` (turret and buff excluded) used at `main.rs:465` and elsewhere.
- `build/make_definitive.py:117-130` `_attacking_row`, a second copy of the same rule on the Python side.
- `read_partners` skip of orbit, buff and turret kinds (`main.rs:204-208`), a third copy with a slightly different
  list (the Python one also drops `orbit` and zero-`dealt` rows).

On #35 none of them exists and 221 to 299 species publish Sustituto. On main it is still published: Landorus
`move_pair` is `bonemerang + substitute + aerial-ace` (`data/ranking_definitive.csv`). The filter hides the symptom;
the 195 species whose score winner is Sustituto on #40 are re-resolved to the next move by the same score. The
publisher overrides its own formula by hand in 195 species and trusts it in the other 771.

**Fix.** One `Move.publishable` flag in the exported move data, read by Rust and Python. Delete the three copies.

### S4 [High] Score is 4x noisier than time, and median and mean disagree

Median relative 90% bootstrap width: time 0.086, score 0.363 (0.374 on #40). Winner vs runner-up median margin: 9.2%
on time, 79.6% on score. Winner interval disjoint from the runner-up's: 532 species on time, 616 on score. So the
score does not *look* noisy: it separates winners more often, because the turret wins by large factors. Where it
does not, the winner flips with the statistic: median_score and mean_score pick a different move in 182 species
(56 with time). `stats.rs:28` uses one fixed rng (0xB007, 400 reps) for every bootstrap, so all intervals share the
same resampling stream; fine for reproducibility, but the CIs are correlated and 400 reps is thin for the 5th and
95th percentiles.

**Fix.** Report time CI and rank on it; use at least 2000 reps and a per-row seed.

### S5 [Medium] "Best" is chosen and reported on the same seeds

Best-of-N on seeds 1-200, then reported on seeds 1-200 (`winner_by_dex`, `make_definitive.py:132-150`). Measured
optimism is small on time (parametric bootstrap: +0.15 s, a different move wins in 8% of redraws,
`winners_curse.py`), so this is not the main problem, but the clean fix is cheap: select on seeds 1-200, report on
201-400.

## 3. Statistics

### T1 [Critical] The published group changes with the seed block

`replicate_stability.py` feeds four independent 200-seed blocks (seed0 0, 200, 400, 600; #40 engine) through
#40's real publish rule (`combos._search_picks`, `combos.py:167-226`, run with `BUILD_DIR=<#40 checkout>/build`) for
the four species the search covers:

| species | distinct published groups over 4 blocks |
|---|---|
| Gengar (94) | 3 (`hex+quick-attack+shadow-ball` x2, `hex+hyper-voice+shadow-ball`, `hex+poison-sting+shadow-ball`) |
| Marshadow (802) | 2 (`aura-sphere+hex+shadow-ball` x3, and once a **melee** group `karate-chop+shadow-ball+harden`) |
| Gholdengo (1000) | 4 (Flash Cannon / Hyper Voice / Hex as second or third attack, Harden or not) |
| Landorus (645) | 3 (`aerial-ace+bonemerang` plus Quick Attack x2, Harden, or Spikes) |

0 of 4 species gave the same group in every block. Same group, different seed block: median range of `median_s` is
4.2 s, p90 7.9 s (284 groups), so sigma is about 2 s, the same size as the gaps between the top groups of a species.
Run without `BUILD_DIR` (main's rule: median time, then mean, then group string) it also changes (4, 3, 3, 4 distinct
groups). Exact ties resolve by the group *string*.

Because `move_pair` is the visible "build", it changes for a coin-flip reason on every rerun. It does not feed the
rank (rank uses `start_median_s` and `best_median_s`), so the damage is to the build advice and to the "best group"
claims, not to tiers.

**Fix.** Run the search on 600+ seeds, keep every group within one CI of the best, and publish the cheapest or most
robust of those (fewest moves to unlock, fewest buffs). State "equal within noise" on the page when that set has
more than one member.

### T2 [High] `group_search.csv` does not reproduce

For the 107 identical `(dex, group-string)` pairs shared between the committed `group_search.csv` (main) and my
rerun on #40 with seeds 1-200, **0 have the same median** and the mean |difference| is 4.5 s (5.4 s against block
201-400). Across the engine change main to #35, 9236 solo-sweep rows shift by a mean 4.85 s (p90 10.2 s) on the
*same* seeds; #35 to #40 shifts 1.5 s (p90 5.8 s). The absolute seconds on the site are tied to one engine commit
and the CSVs are not regenerated together (nothing records which engine produced `group_search.csv`).

**Fix.** Stamp every results CSV with the sim git hash, seed range, flags; refuse to build if a CSV hash differs
from the engine hash in `catalog.py`.

### T3 [High] Rank noise is under-reported and the intervals miss most of it

The site's `rank_p10..p90` (median width 56 ranks, p90 133, max 275) only jitters `start_median_s` and
`best_median_s` uniformly inside their bootstrap CI (`make_definitive.py:228-236`, `draw`). It excludes sheet,
v4, the weights (`SIM_AMP` 22, `LATE_SPAN` 0.15) and winner re-selection. Tier S: 47% of the 30 S species have
`p_tier < 0.8` by that narrow measure.

Re-drawing the two sim columns with sigma 2 s (`rank_noise_inject.py`, baseline reproduces published ranks within a
median 3 places; 75 of 966 exactly because tier gates and stored v4 weights are not replicated): mean |rank shift|
**9.5** (p90 22), 4% of species change tier band per draw, and **11% of the S membership** changes per draw (17%
at sigma 4 s). The A/B reruns show the same: Marshadow's best starter is Shadow Ball on seeds 1-200 and Hex on
201-400, Garchomp is 2nd of the six in A and 4th in B.

#31 decided "A/B/C/E tied on the median, decided on a 0.1 s mean difference". 0.1 s is 1/20 of sigma. That decision
is not supported by this data.

**Fix.** Treat anything under ~2 s as a tie everywhere (starter pick, group pick, tier cut). Publish the tier as
"S or A" for the species whose `p_tier` is below 0.8.

### T4 [Medium] 45% of the rank is a frozen sheet, not sim output

`build/make_definitive.py:223` weights: sheet 45, early sim 30, late v4 25. The sheet (`pct_stats`, `pct_moves`,
`pct_typedef`, `pct_size` in `data/ranking_definitive.csv`) is carried forward as frozen columns; the rebuild
only reads them. `facts_export.py:60` `PILLAR_W = stats 45, moves 25, typedef 15, size 15`. `pct_size` still
rewards a small hitbox (Gengar 0.539, Garchomp 0.105) although the sim caps collision radius at 18
(`facts_export.py:210`, game `min(18, r)`) and #35 removed the "big hitbox holds it back" wording
(`e941b28`, `build/prompts/summary.md`). The size pillar is 15% of 45%, 6.75% of the final score, for an effect the
game does not have. Garchomp ranks 179 (B) against Gengar 12; the sim gap is 10-15 s (start 86 vs 101, best 96 vs 107) but the
size pillar alone is 0.105 vs 0.539.

**Fix.** Drop the size pillar from the sheet and reweight; document the sheet as an opinion, not a measurement.

### T5 [Medium] Hand-set numbers inside the ranking

`make_definitive.py:46-49` (REPEATS 2000, SEED 20261014, LATE_SPAN 0.15, SIM_AMP 22), `:72` CUTS, `:73` BANDS,
`:74` STAT_MIN `{S .6, A .4, B .2}`, and the S gate "3 attack types". Rank cuts also live in `catalog.py:40-41`
(`TIER_CUTS`, `EXPECTED_COUNTS`) and the A:90 / B:200 sizes in `CUTS`: three definitions of the same tiers.

**Fix.** One `tiers.json`, read by both.

## 4. Build search

### B1 [High] Only 160 of 966 species are searched

`group_search.csv` has rows for 160 dex numbers. Keldeo and Garchomp have none: their published pair
(`aura-sphere + water-gun`, `bonemerang + dragon-rage`) comes from the coverage heuristic
`combos.py:229` `pick_attacks` (type coverage, `NORMAL_MIN_GAIN` 0.02 at `combos.py:69`), not from the sim. The
README says the search "runs for every species that learns a synergy". So two mechanisms produce what looks like
one kind of recommendation, and the page does not say which.

**Fix.** Search every species (322 candidates took 123 s for 6 species; the full set is hours, not days), or label
the others "coverage heuristic, not simulated".

### B2 [High] The buff choice is implemented three times

- sim: `synergy_specs` always puts Swords Dance in the group on main (README: "Every searched group holds Swords
  Dance"); #35 adds Maquinación by lead-attack category.
- `combos.py:141-157` `_attack_buff`, plus `combos.py:292-294` force-appending `nasty-plot` because "the exported
  pool predates it" (stale `v3_data.json`/move pool).
- planner `src/tools.js:127-139` swaps `patk` buffs for Nasty Plot at runtime for a special majority and shows a
  "swap" notice.

Main publishes Swords Dance for special attackers (Gengar's published group on main is
`shadow-ball+sludge+hex+swords-dance`). The three can disagree.

**Fix.** Choose the buff in the sim from the move category of the lead, write it to the CSV, and delete the Python
and JS logic.

### B3 [Medium] "Never melee for Gengar" is a patch in 11 places

Rust `main.rs:246, 257, 465, 577, 789, 798, 806`; Python `combos.py:196, 290, 300`, `facts_export.py:200`. It
is a data rule typed as `dex == 94`. In the sim it is probably redundant: Gengar's melee starters survive 30-34 s,
below the 63 s do-nothing baseline (section 5), so they never win. I could not test removing the guard without
editing the sim.

**Fix.** A `forbid_melee: [94]` entry in one data file; test that the search never picks melee for those species
*without* the entry; delete it if so.

### B4 [Medium] The "melee-risk penalty (x0.75)" is a bonus, and the sim invents extra cost

The game's `player.js:254` is `close = activeGroup().some(melee) ? 0.75 : 1`, multiplied into damage *taken*: the
player takes 25% **less** with a melee move active. The sim implements it as `st.melee = 0.75` (`engine.rs:1637,
1651`) and the README cites `player.js:238`, a stale line. The sim then adds its own cost the game does not have:
`tick_melee_risk` (`engine.rs:3554-3581`) charges one synthetic contact hit per touch cadence on the last 90 px of
the approach of a bonded melee companion, and `decide` (`engine.rs:3583-3597`) turns repulse off to walk in.

**Fix.** Rename to "melee damage reduction", fix the line reference, and have A-fidelity decide whether
`tick_melee_risk` mirrors something in the game; if not, delete it.

### B5 [Medium] The bonded group rarely exists in the median run

Rift bonds roll after t > 75 s, once per 30 s, at p = 0.2 x (1 + misses), then the player must reach the rift and
beat a legendary (`engine.rs:2786-2830` on #40 and the rift comment in `tick_rift`). The median run ends at 90 to
100 s (`median_s` of the six species, section 7). So most of the median run is played with the starter, and the group
search ranks the 2+2 group on the minority of runs where bonds arrive early (I did not measure bond time per run;
this follows from the rule and the median).

**Fix.** Report the starter and the group as two different questions; weight the group by the bond arrival
probability or run the search with bonds forced early and say so.

### B6 [Low] Search shape constants

`PAIR_TOP = 6` (`main.rs:460`), partner sort by synergy then solo rank then id (`main.rs:~230-265`), the melee
floor rule `boot_lo > best ranged median and mean >=` (`combos.py:213-222`), `ALT_SLOTS`, `ATTACK_SLOTS`. Each is
defensible alone, none is tested against a wider search. `let _ = n;` at `main.rs:199` is dead.

## 5. The bot

Policy ("repulse", `engine.rs:3583-3680`): flee every enemy within a 160 px gap, weight 1/max(8, gap); approach the
nearest enemy only while the gap exceeds `keep`. `keep` is `0.55 x radius` for melee and `0.75 x reach` otherwise
(`engine.rs:358-364`; 135 for Inert kinds, reach 180).

Do-nothing baseline (`pokesim tasks`, no group; Sustituto fires nothing in this mode), median survival, seeds 1-200:

| species | do-nothing | tackle | body-slam | other starter probed |
|---|---|---|---|---|
| Venusaur | 63.3 | 41.5 | 41.7 | vine-whip 67.1 |
| Charizard | 55.5 | 35.1 | 33.8 | wing-attack 47.3 |
| Gengar | 62.9 | 31.8 | 34.0 | lick 30.0 |
| Garchomp | 63.1 | 40.5 | 40.0 | |
| Landorus | 56.3 | 36.8 | 36.2 | wing-attack 57.2 |
| Keldeo | 64.9 | 36.8 | 34.4 | karate-chop 46.6 |
| Marshadow | 66.4 | 47.5 | 48.0 | karate-chop 58.5 |
| Gholdengo | 72.8 | 47.5 | 51.8 | metal-claw 49.6 |

### K1 [High] The measure is "survive while attacking", and the bot makes attacking costly

In this probe 27 of 29 attack starters survive less than doing nothing (8 to 31 s less). The only two that beat the
baseline are Venusaur's Vine Whip (+3.8 s) and Landorus's Wing Attack (+0.9 s). The probe has no clearly ranged
starters and runs the default mode (no group, terrain or status; turret kinds inert); I did not repeat it on the
ranking path, so treat the size of the gap as indicative. What it does show: ranking by survival time ranks **how
well a move lets a flee-first bot deal damage without being touched**, more than how strong the Pokémon is.
`melee_locked` (S excluded) in `make_definitive.py` and the Gengar rule are then patches on top of a bias the bot
already applies.

On the owner's question (does the bot keep distance so melee never connects): for melee the bot walks in (keep
0.55 x radius) while repulse (gap < 160) pushes it out with weight at most 1/8 per enemy, so melee does connect and
the result depends on crowd size, not on the move. For ranged kinds `keep` is 0.75 x reach, so melee enemies rarely
connect.

**Fix.** Report two numbers per move: survival with a damage-first policy and with a flee-first policy, with the
do-nothing baseline next to them. Rank on the min or show both. Do not add melee rules until you know how much of
the melee gap is policy.

### K2 [Medium] Policy knobs are literals

160 px (`engine.rs:3616-3618`), 240 px for Kite, 8.0 floor, 0.25 s reaction, +28 px strafe margin, 0.35 pull, 90 px
close, `hold * 0.75` (`engine.rs:4264`). None is calibrated against a recorded human run.

## 6. Tiers and ranks

### R1 [Medium] Cuts, gates and ties

Tiers are rank counts 30/90/200/300/346 (`make_definitive.py:72`, `catalog.py:40-41`), then stat gates
(`STAT_MIN`) and a type gate move species across the cut (`qualifies`, `fill_tiers`: `:153, :165`). Within rank
noise (T3) the S/A line is not a stable partition: 11% of S slots change per redraw. The p10-p90 band on each
page is narrower than the real uncertainty (T3).

**Fix.** Publish tiers with a confidence label; stop moving species across cuts by hand-set stat gates, put them into
the sheet instead.

## 7. Reproduction on six species (#40 engine, `--group 2+2 --terrain --status`, 200 seeds)

Published on main (`data/ranking_definitive.csv`) vs two disjoint reruns (A seeds 1-200, B seeds 201-400):

| species | main: rank, tier, best (best_median_s), pair | A best starter (median s) | B best starter (median s) |
|---|---|---|---|
| Keldeo 647 | 1, S, aura-sphere (117.4), aura-sphere + water-gun | aura-sphere (102.1) | aura-sphere (102.2) |
| Marshadow 802 | 2, S, shadow-ball (118.4), shadow-ball + hex + aura-sphere | shadow-ball (104.0) | hex (101.1) |
| Gholdengo 1000 | 3, S, meteor-mash (128.6), shadow-ball + flash-cannon + meteor-mash | meteor-mash (111.4) | meteor-mash (109.6) |
| Gengar 94 | 12, S, shadow-ball (106.9), shadow-ball + sludge + hex | hex (91.4) | hex (90.4) |
| Garchomp 445 | 179, B, bonemerang (96.4), bonemerang + dragon-rage | bonemerang (96.7) | bonemerang (94.8) |
| Landorus 645 | 244, B, bonemerang (91.9), bonemerang + substitute + aerial-ace | bonemerang (91.3) | bonemerang (89.9) |

- Keldeo, Gholdengo, Garchomp, Landorus agree on the best starter in A and B. Marshadow flips (Shadow Ball vs Hex,
  3 s apart on time). Gengar's best starter is Hex on #40; main publishes Shadow Ball, 15 s higher.
- Published best_median_s on main is 13 to 17 s above both reruns for Keldeo, Marshadow, Gholdengo, Gengar, and
  within 2 s for the two Bonemerang species. That gap is engine drift (T2), not seed noise: A and B agree within
  3 s of each other.
- The six species' final order in A is Gholdengo, Garchomp, Keldeo, Marshadow, Gengar, Landorus; in B Gholdengo,
  Marshadow, Keldeo, Garchomp, Gengar, Landorus. Time gaps between positions 2 and 5 are 5-11 s.
- Landorus's published pair includes Sustituto (S3).
- Group search for Keldeo and Garchomp: no rows (B1). For the other four, 4, 3, 3, 4 distinct groups across four
  blocks (T1).

## 8. Data pipeline

### P1 [High] The rebuild does not reproduce the committed ranking by default

`python3 build/make_definitive.py` with default flags changes **919 of 966 ranks**, 40 tiers, 125 best moves and
102 `move_pair` on main. With `--best-sweep simulator/results/fixed_group/solo_sweep.csv` it reproduces all four
columns exactly (0 differences). The README does not say so; #35 reproduces with the defaults. A
`--use-stored-best` escape hatch (`make_definitive.py:249`) also exists.

**Fix.** Make the reproducing flags the defaults and add a CI job that runs the rebuild and diffs the CSV.

### P2 [High] Hand-typed numbers that look like measurements

`build/pasivas.py:25-34` `CARDS` hardcodes `coin`, `surv`, `kpm` per card (Síntesis +6.1 coins, Vigor +1.6, Imán -3.1).
From `passives_coins_g2p2.csv` (966 species, same protocol) the means are +5.7, +2.5, -2.8; Carrera 0.0 vs -1.4,
Aprendizaje -0.7 vs -2.1, Coraza 0.0 vs -0.7. The order matches, the numbers do not, and the shipped numbers have no
file they come from. `ZIDRA`, `COMBOS` ("+2%", "+1%", `lift`) and `EXCEPTIONS` are also literals.

### P3 [High] Per-species card priority is mostly ties

`simulator/card_priority.py` orders cards by median coins (integers; median 21 at fill 0), 100 seeds. In 421 of
966 species the top two cards tie on coins and the order falls to survival then fill index. The median spread
across all eight cards is 2 coins, with 4 distinct values among 8 cards. The "card priority" shown on each build card
is noise except for Síntesis and Vigor, which lift by 5.7% and 2.5% on average.

**Fix.** Publish the global order plus per-species only where the gap exceeds the CI; run 400+ seeds.

### P4 [Medium] Dead and duplicated code

- `build/charts.py:104-157` (`rank_band`, `pillars`, `methods`, `sim_dots`, `_band_body`, `_band_alt`,
  `_methods_plot` partly) have no caller; the docstring says `src/ficha.js` draws them. Delete after confirming no
  template uses them.
- `main.rs:199` `let _ = n;`.
- `build/i18n.py:255` `pill_size` ("Small hitbox") is still a user-visible pillar; `build/summary_facts.py:91-95`
  ranks "smaller hitbox higher" from the capped radius, so most species with a large sprite share one value.
- Three tier definitions (R1/T5), three buff implementations (B2), three Sustituto filters (S3), eleven Gengar
  guards (B3).

### P5 [Medium] Frozen inputs with no provenance

`pct_stats`, `pct_moves`, `pct_typedef`, `pct_size`, `rank_sheet`, `rank_v4_max`, `rank_v4_fresh` in
`data/ranking_definitive.csv` are inputs, not outputs, and nothing regenerates them. `data/move_tierlist_v4.csv`,
`data/passive_sim.json` and `data/pokedex_export.json` likewise. The comment header of the CSV describes the group
protocol but not the date, engine hash or seed range.

### P6 [Low] The rebuild path touches many languages

Rust sim, JS parity engine, Python builders, JS planner (`src/tools.js`). The parity JS is the only bit-exact
reference; the ranking path (`--group --terrain --status --xkinds`) is not covered by `parity.js`
(it runs the default mode; `sim/rules.js` carries only part of the ranking-path rules). I did not check how much of
the ranking path the JS replicates.

## 9. Recommended cleanup order

1. **Stop the bleeding (small, no code change in the sim).** Rank "best move" on survival time only; keep the score
   column as information. Revert `cmp_run` to time and drop Sustituto filters once the winner stops being Sustituto
   (S1, S3). Fix P1 defaults.
2. **Measure noise and say so.** Put seed range, engine hash and sigma in every CSV; replace the rank band with
   "tier S or A" when `p_tier < 0.8`; treat gaps under 2 s as ties (T1, T3).
3. **One source for each rule.** `forbid_melee`, `buff by category`, `publishable`, tiers in a single data file;
   delete the Python and JS duplicates (B2, B3, S3, T5, R1).
4. **Fix the inputs.** Remove `pct_size`; recompute CARDS from the CSV; regenerate group search on 600+ seeds; search
   all species or label the heuristic ones (T4, P2, P3, B1).
5. **Decide the policy question.** Run flee-first and damage-first bots and publish both before changing melee rules
   (K1); then decide whether `tick_melee_risk` stays (B4).
6. **Delete.** `charts.py:104-157`, `main.rs:199`, the three Sustituto filters, the 11 Gengar guards if B3's test
   passes, the stale `README` line references, `--use-stored-best`, and the frozen `pct_size`.

## 10. Top 10 problems in plain words

1. **The "best move" score multiplies time x damage x kills, and a stationary turret (Sustituto) wins it** in 195 to
   299 of 966 species; a hand-written filter then hides it instead of fixing it.
2. **The "best group" you see is a coin flip.** Four separate 200-run tests gave 2 to 4 different "best" groups for
   each of Gengar, Marshadow, Gholdengo and Landorus; the differences are smaller than the noise.
3. **Results are tied to one engine commit and the files are not regenerated together.** The same group on the same
   seeds moves by 5 s (up to 10 s) between main and #35, and the committed group file cannot be reproduced.
4. **Nearly half the rank (45%) is a frozen spreadsheet score that nothing re-computes**, including a hitbox size
   penalty the game does not have.
5. **The site's rank bands are too narrow.** They only wiggle two of the inputs; with realistic noise, about 11% of
   S slots change on every rerun.
6. **The bot decides what looks good.** In my probe 27 of 29 attack starters live 8 to 31 s shorter than a player
   who does nothing, so "melee is bad" is partly the bot, and the manual melee rules sit on top of that.
7. **Only 160 of 966 Pokémon get a real group search;** the rest get a type-coverage guess that looks the same on
   the page.
8. **The same rule is written many times:** Gengar-no-melee in 11 places, the buff choice in 3, Sustituto in 3,
   tiers in 3. Each patch fixed one copy.
9. **The rebuild with default flags changes 919 of 966 ranks.** You have to know the right flag; nothing checks it.
10. **Hand-typed numbers and ties pass as data:** pasivas card gains are typed in (and a few do not match the CSV), and
    in 421 species the "top two cards" tie on the metric used.
