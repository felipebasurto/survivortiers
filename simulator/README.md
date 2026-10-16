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

`--group 2+2` or `--group 3+1` makes the bot aim for one fixed group, as players do mid/late game: the starting attack
plus 1 or 2 more attacks (picked from `--partners <solo starter_sweep.csv>`, best solo median first, no orbits) and
Swords Dance + Harden (2+2) or Swords Dance (3+1). Extra options: `--dd` (Dragon Dance instead of Swords Dance), `--agi`
(Agility instead of Harden), `--item <id>` (choiceband, lifeorb, quickclaw, choicescarf, assaultvest, leftovers,
luckyegg; items.js), `--fill a,b` (stat cards first, indices of `data::STATS`). `pokesim tasks <file>` runs lines
`dex,move[+companion...],item,fill[,buffs]` (buffs: `sd;hd;dd;agi`).

Group mode also models, from the game source (`js/` in JPTER78/pokesurvivor):

- **Bond timing.** Members are not bonded at t=0. Only the starting attack fires until a rift legendary is beaten
  (`pl.bonds++` in systems/rift.js:199, after the legendary dies). Rifts roll every 30 s from t=75 until t=1680
  (Judgment.AT − 120, judgment.js:32) with chance 0.2·(1+misses). A check while a boss is alive does not count
  (rift.js:47). The rift opens 380–560 px away, y·0.85, on a free tile, and lasts 45 s (rift.js:55–66). The bot walks
  there in (distance − 30) / current speed — an estimate, it does not path. Entering stashes map enemies and clears
  shots (rift.js begin, 112–120). The legendary uses spawnLegend's stats (rift.js:138–155): HP round(3200+9t), and the
  arena lasts 120 s. Dying in the arena does not end the run; a loss revives at 30 % (player.js:387–389, rift.js:229).
  Each win bonds one more member. The real game lets the player choose the fusion (player.js bondOptions); the sim
  assumes attacks, then the attack buff, then Harden/Agility, at most 3 bonds (BOND_MAX is 4 including the start move).
  Buff cards for members not bonded yet are not offered.
- **Bosses** (data/enemies.js:44–50, rollRun 156–169, bossScale 184): at 180/360/540/720/900 s, a non-legendary in that
  BST band, HP and damage ×1.35 and ×1.2 then ×(1+t/600). Behavior is ranged only when behaviorOf would say so, else
  charger if base speed > 90, else chase. Spawns drop to ×0.25 and surges stop while one is alive (systems/spawner.js:114–137).
  The boss still spawns at the cap (EnemyMgr.add does not check it).
- **Heal orbs.** A boss or legendary always drops one (entities/pickup.js:81) and any other kill does so 1.2 % of the
  time (entities/pickup.js:93). Each heals 30 % of max HP (game.js:496–497). The bot is assumed to pick every one up.
  Springs and the Baya Zidra card (levelup.js, the instant 45 % heal) are not modelled.
- **All move kinds** (`--xkinds`, on by default in group mode): cone, meteor, chain, aura (drain heal capped at 6),
  dash, mine, trail and turret, following systems/combat.js. Life Orb costs HP only on a cast that actually fires, and
  never for orbit or trail (player.js:203). Without the flag these moves stay inert, as in the JS engine.

`--legacy-group` restores the old behaviour (bonded from t=0, no rifts, bosses, heal orbs or extra kinds). Default runs
(no `--group`) are unchanged and still pass `parity.js`; the JS engine does not have group mode.

Known bias (estimates): the bot does not dodge, so sustain (Synthesis `rgn`, Vigor `hp`, Leftovers) still looks strong;
build/passives.py keeps at most one of `rgn`/`hp` in the Build card. The rift walk is time-at-current-speed, not pathing.
Boss and legendary hit radius ×2 stands in for sprite bossScale when the idle anchor is the default (enemy.js:15–22, sprites.js:127–130); huge sprites would be closer to ×1. Boss personalities other
than ranged/charger/chase are collapsed. The arena is fought in open space at the map position (no Distortion World
columns or arena weather). Judgment / Arceus (minute 30) is outside the 900 s sim.
Results used for the site are in `results/fixed_group/`.

Any change to `sim/match.js` or `sim/rules.js` has to be mirrored in `sim-rs/src/engine.rs` and re-checked with `parity.js`.

## Credits

PokéSurvivor and its code are by JPTER78, under the MIT licence (see `../data/GAME_LICENSE.txt`). The game data in `v3/` is extracted from that code. This simulator is unofficial and not affiliated with the game or with the owners of Pokémon.
