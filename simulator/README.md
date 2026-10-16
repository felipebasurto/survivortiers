# Simulator

The headless PokéSurvivor simulator behind the SurvivorTiers ranks. A bot plays full games and the median survival time feeds the "Simulated games" score.

- `sim/`: the first engine, in JavaScript, like the game. `batch.js` runs every Pokémon with its starting attack, `sweep_starters.js` tries every attack it can learn.
- `sim-rs/`: the same engine rewritten in Rust (about 4,000 lines, games run in parallel with rayon). With V8's math functions replayed it matches `sim/` bit for bit; `parity.js` checks that.
- `v3/v3_data.json`: Pokédex, moves, enemy tiers and type chart, extracted from the game's code by `v3/extract_v3.js`.

## Run

Run everything from this folder.

```sh
cargo build --release --manifest-path sim-rs/Cargo.toml

# every Pokémon with its starting attack, 200 seeds
./sim-rs/target/release/pokesim rank --out sim/out/rank_200.csv

# every attack it can learn as a start
./sim-rs/target/release/pokesim sweep

# one game, with a trace: CSV of positions, or JSON with enemy species and shots for a replay
./sim-rs/target/release/pokesim run 7 water-gun 17 --out trace.json

# bit-exact parity against the JavaScript engine
node sim-rs/parity.js
```

Options: `--seeds N` (200), `--seconds S` (900), `--bot repulse|line`, `--lvl1`, `--terrain` (real map, not JS-parity), `--status` (slow, burn and poison, not JS-parity).

### Fixed main group (Rust only)

`--group 2+2` or `--group 3+1` makes the bot play one fixed bonded group, as players do mid/late game: the starting
attack plus 1 or 2 more attacks cast together on their own cooldowns (picked from `--partners <solo starter_sweep.csv>`,
best solo median first, no orbits), and Swords Dance + Harden (2+2) or Swords Dance (3+1) held from t=0. Extra options:
`--dd` (Dragon Dance instead of Swords Dance), `--agi` (Agility instead of Harden), `--item <id>` (choiceband, lifeorb,
quickclaw, choicescarf, assaultvest, leftovers, luckyegg; items.js), `--fill a,b` (stat cards first, indices of
`data::STATS`). `pokesim tasks <file>` runs lines `dex,move[+companion...],item,fill[,buffs]` (buffs: `sd;hd;dd;agi`).
Default runs (no `--group`) are unchanged and still pass `parity.js`; the JS engine does not have this mode.
Results used for the site are in `results/fixed_group/`.

Any change to `sim/match.js` or `sim/rules.js` has to be mirrored in `sim-rs/src/engine.rs` and re-checked with `parity.js`.

## Credits

PokéSurvivor and its code are by JPTER78, under the MIT licence (see `../data/GAME_LICENSE.txt`). The game data in `v3/` is extracted from that code. This simulator is unofficial and not affiliated with the game or with the owners of Pokémon.
