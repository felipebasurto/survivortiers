# Regen: resume on the 8-core machine

The code is final; the data is half regenerated. Stages 1-3 of `build/regen.py --sim` finished on the 4-core VM (game commit `5a23d49`). The group screen was killed at about 24,000 of 24,320 groups and left no output. Everything from the group search on is still the old data, so `data/ranking_definitive.csv`, the summaries and the site are **not** regenerated and several tests fail until the steps below are done.

## Reusable outputs (do not rerun)

| Stage | Output (under `simulator/results/fixed_group/`) | Seeds |
| --- | --- | --- |
| solo screen | `solo_screen.csv` (13,910 starts) | 16 |
| solo refine | `solo_refine.csv`, `solo_refine_only.txt` (best 3 attacks per species) | 128, seed0 1000 |
| solo contend | `solo_contend.csv`, `solo_contend_only.txt` (120 species, best 2 attacks) and the merged `solo_sweep.csv` | 512, seed0 3000 |

`solo_sweep.csv` is the new merged sweep. `group_search.csv`, `g2p2/starter_sweep.csv`, `g2p2/rank_200.csv` and `stage2/rank_{b,c}.csv` are still the **old** files from before the rules change. `regen.py` skips a stage whose output exists, so use `--from` (below).

## Remaining stages, in order

```sh
git checkout cursor/sim-fixes-regen-supersede-de67
git clone https://github.com/JPTER78/pokesurvivor /tmp/pokesurvivor && git -C /tmp/pokesurvivor checkout 5a23d49   # read-only, only for step 2 below
cargo build --release --manifest-path simulator/sim-rs/Cargo.toml

# 1. engine: group screen -> group refine -> start sweep -> start rank (--from now forces every stage after it)
python3 build/regen.py --sim --from group_screen
```

Stage by stage, if you prefer to run them separately (same commands `regen.py` runs, from `simulator/`):

1. `group_screen`: `pokesim synergy --seeds 16 --seconds 900 --partners results/fixed_group/solo_screen.csv --out results/fixed_group/group_screen.csv` (24,320 groups; about 40 min on 4 cores)
2. `group_refine`: `python3 build/regen.py --sim --from group_refine` (writes `group_refine_only.txt`, then `pokesim synergy --seeds 96 --seed0 1000 ... --out results/fixed_group/group_search.csv`)
3. `start_sweep`: `python3 build/regen.py --sim --from start_sweep` (16 seeds, `--group 2+2`, writes `g2p2/starter_sweep.csv`)
4. `start_rank`: `python3 build/regen.py --sim --from start_rank` (three disjoint 16-seed blocks: `g2p2/rank_200.csv`, `stage2/rank_b.csv`, `stage2/rank_c.csv`)

Note that `--from X` also reruns every stage after X.

## Then, in order

```sh
python3 build/regen.py                                   # data/ranking_definitive.csv
python3 build/move_tierlist_v4.py --game /tmp/pokesurvivor
python3 build/stability.py                               # top-30 overlap between seed blocks, for the PR body
python3 build/regen.py --facts                           # facts.parquet + summaries; READ the rewritten ES/EN texts (Marshadow 802, any group that changed)
python3 build/catalog.py && python3 build/render.py
python3 build/serve.py &                                 # SPRITE_BASE=http://127.0.0.1:8765/_sprites/
python3 build/check_site.py http://127.0.0.1:8765/       # includes the ficha h1 / sprite alt check
python3 build/regen.py --check
python3 build/facts_export.py --check
python3 build/summary_pipeline.py check
python3 -m unittest discover -s build -p "test_*.py"
node --test simulator/v3/game_update.test.js
cargo test --release --manifest-path simulator/sim-rs/Cargo.toml
```

Also still to regenerate (not touched yet): the passive rank (`simulator/pasivas_rank.py`, `results/fixed_group/pasivas_rank_g2p2.csv`, 150 species with their new best moves, 100 seeds) and `data/passive_sim.json` if the passive bench input changed. Check `build/novedades.py` text against the final top 30 before merging.

## Expected failures until the sim is done

`test_game_moves` (physical set vs the old CSV), `test_combos` / `test_best_move` (they read the stale group search and sweep), `test_repertorio`-style checks that read the old starter sweep, and the rendered-site tests that depend on them. `test_combos` also asserts that some species choose a third attack and some choose Fortaleza; check both hold on the new data.

## PR body numbers still to fill in

Sustituto in groups (must be 0), melee in groups, mixed-category groups (must be 0), groups choosing a third attack over Fortaleza, seed counts and top-30 overlap, the new top 30 with rank bands, and Gengar, Marshadow, Gholdengo, Keldeo, Garchomp and Landorus (tier, rank, group, buff).
