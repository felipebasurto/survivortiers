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

# one game, with a position trace
./sim-rs/target/release/pokesim run 7 water-gun 1 --out trace.csv

# bit-exact parity against the JavaScript engine
node sim-rs/parity.js
```

Options: `--seeds N` (200), `--seconds S` (900), `--bot repulse|line`, `--lvl1`, `--terrain` (real map, not JS-parity), `--status` (slow, burn and poison, not JS-parity).

Any change to `sim/match.js` or `sim/rules.js` has to be mirrored in `sim-rs/src/engine.rs` and re-checked with `parity.js`.

## Credits

PokéSurvivor and its code are by JPTER78, under the MIT licence (see `../data/GAME_LICENSE.txt`). The game data in `v3/` is extracted from that code. This simulator is unofficial and not affiliated with the game or with the owners of Pokémon.
