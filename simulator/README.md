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
`--full-cards` also offers Aprendizaje and Baya Zidra (levelup.js). `--stop N` limits a `--fill` priority to N copies. `--heal-below F` takes Baya Zidra only at or below that fraction of max HP. `--lock 2:4` starts with 4 Vigor and takes no more (index 7 is Aprendizaje).

### Fixed main group (Rust only)

`--group 2+2` or `--group 3+1` makes the bot aim for one fixed group, as players do mid/late game: the starting attack
plus 1 or 2 more attacks. The pool is searched for a Hex/status or two-dash pair first, then filled from
`--partners <solo starter_sweep.csv>` (best solo median, no orbits). Swords Dance + Harden (2+2) or Swords Dance (3+1).
Extra options: `--dd` (Dragon Dance instead of Swords Dance), `--agi` (Agility instead of Harden), `--swap` (second
slot, clamped to 35% of base cooldown; Choice Band blocks it), `--crit N` (permanent crit levels, 3% each; published
ranks use 0), `--item <id>` (choiceband, lifeorb, quickclaw, choicescarf, assaultvest, leftovers, luckyegg, shellbell,
rockyhelmet, focussash; items.js), `--fill a,b` (stat cards first, indices of `data::STATS`). `pokesim tasks <file>`
runs lines `dex,move[+companion...],item,fill[,buffs]` (buffs: `sd;hd;dd;agi`).

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
  Springs are not modelled. Baya Zidra (levelup.js:26, instant 45 % heal, no cap) and Aprendizaje
  (levelup.js:24, ×1.12 XP, max 8) are offered only with `--full-cards`.
- **All move kinds** (`--xkinds`, on by default in group mode): cone, meteor, chain, aura (drain heal capped at 6),
  dash, mine, trail and turret, following systems/combat.js. Life Orb costs HP only on a cast that actually fires, and
  never for orbit or trail, including companion casts (player.js:203). Without the flag these moves stay inert, as in the JS engine.
- **Synergies on the ranking path** (`--status` or `--xkinds`; both are on for a published group rank). The default
  run (neither flag) stays bit-exact with `parity.js`. Citations are the live game:
  - Hex ×1.7 while the target's burn, poison or slow factor is above 0 (data/moves.js `hex`, systems/combat.js:240).
    The factor is checked, not the timer. Burn lasts 3 s (stacks to 8, tick 0.5 s), poison 4 s (stacks to 8, tick 0.6 s),
    slow 1.2 s (enemy.js applyBurn/applyPoison/applySlow). There is no hit-chance roll. `sim/rules.js` applies the same
    numbers when `opts.status` is set; the default JS run still ignores them so `parity.js` stays bit-exact.
    Group search (`--synergy`, on for `--group`) simulates each status move with Hex (either one leading) and the
    three strongest status moves as two appliers + Hex + Swords Dance, and keeps the group with the higher median.
    `--no-synergy` restores the old partner sort (Hex/status or two dashes first, then solo order).
    The melee damage cut (×0.75, player.js:238) applies only while a melee move is in the active group: the starter
    always, a companion only after that bond. Orbit stays out of the bonded group (one shared orb list).
  - Dash invulnerability is `max(invuln, 0.3)` (systems/combat.js:311). Lava sets invuln to 0 and then hurts
    (entities/player.js:352). Cooldown cuts shorten the dash's own cooldown.
  - `--swap` is a second slot at level 1. Switching clamps that slot's timers to 35% of base cd and ignores cdMul
    (entities/player.js:148). Choice Band refuses the switch (player.js:141). It is a separate rank, not the published one.
  - Sand and snow chip the player for `max(1, 1.2% max HP)` only while weather level() > 0.5 and never KO
    (systems/weather.js:111–116). Other non-boss enemies lose `2% max HP + 1` directly (weather.js:117–124).
    Snow multiplies speed by `1 - 0.1*level()` (weather.js:67–70).
  - Crit is the permanent perk, +3% per level, ×1.5 (data/upgrades.js, combat.js hit). `--crit N` sets N levels.
    Published ranks pass 0. Its rng is separate from the effect stream.
  - Aqua Ring adds its regen only when that move is cast (moves.js aqua-ring, player.js addBuff). It is not bonded
    into every water group.
  - Knockback uses Enemy.hurt (entities/enemy.js:100) on the ranking path, including into lava. Direct hits round
    and the shield absorbs first.
  - Altars last 25 s (systems/interact.js POWER_TIME). Kind is `floor(hash(tx,ty,seed+910)*4)` (world.js:154):
    Furia ×2 atk, Rayo ×1.45 speed, Prisa ×0.6 cooldown, Imán unused. The bot triggers one it walks into; it does not path.
  - Shell Bell heals 4% of dealt damage, buffer cap 4 (player.js:295). Rocky Helmet is 15+4×level with knock 80 on
    body contact only (combat.js:668). Focus Sash saves at 1 HP once per 60 s (player.js:248).
  - Orbit rehit is `max(0.12, cd)` with no cooldown multiplier (combat.js:486). Turret rate and trail ticks ignore it too.
  - A bonded companion evolves after its max level once the needs card was taken (moves.js evolve). Coraza clamps
    inside the 0.7 cap on each card (levelup.js:19), and the 0.8 cap is applied after Harden (player.js:96). A vest
    equipped at the start sits in that same 0.7 bucket, so later Coraza cards eat it. Parity (no item) still stops at 0.7.
  - Leftovers adds 1.5 % of max HP once, at equip (items.js:14). The sim equips at t=0, so that is base HP, not HP after Vigor.
  - Vigor and Síntesis have no `max` in levelup.js. The ranking path allows 250, which a 900 s run does not reach.
    Parity keeps the old caps (HP 99, regen 10). Imán is offered but XP is granted on the kill, so the radius does nothing.

Numbers from this sim are estimates. The type chart (soft ×1.6/0.6/0.3, clamp [0.3, 2.4]) and the exported melee and
evolution rows match the game's own `evolve()`.

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
