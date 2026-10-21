# Simulator

The headless PokéSurvivor simulator behind the SurvivorTiers ranks. A bot plays full games and the median survival time feeds the "Simulated games" score.

- `sim-rs/`: the engine, in Rust (games run in parallel with rayon). It is the only simulator.
- `v3/v3_data.json`: Pokédex, moves, enemy tiers and type chart, extracted from the game's code by `v3/extract_v3.js`.
- `validate/`: the vendored game's own functions run on the same formulas and scenes as the Rust tests.

The "parity path" below is a run without `--status`, `--xkinds` or `--terrain`. It is the behaviour of the
retired JavaScript engine and is not used for published ranks.

## Run

Run everything from this folder.

```sh
cargo build --release --manifest-path sim-rs/Cargo.toml

# every Pokémon with its starting attack, 200 seeds
./sim-rs/target/release/pokesim rank --out out/rank_200.csv

# every attack it can learn as a start
./sim-rs/target/release/pokesim sweep

# one game, with a trace: CSV of positions, or JSON with enemy species and shots for a replay
./sim-rs/target/release/pokesim run 7 water-gun 17 --out trace.json

# Repertoire + Veto opening per species, JSON on stdout (build/make_definitive.py reads it)
./sim-rs/target/release/pokesim repertorio results/fixed_group/g2p2/starter_sweep.csv
```

Options: `--seeds N` (200), `--seconds S` (900), `--bot repulse|line|kite`, `--lvl1`, `--terrain` (real map), `--status` (slow, burn and poison).
`--bonded` (group mode) bonds the whole group from t=0 instead of one member per rift win; bosses and every kind stay on. `build/bond_tiers.py` uses it, because with rift bonds the bot dies before the third member is bonded.
`--full-cards` also offers Aprendizaje and Baya Zidra (levelup.js). `--stop N` limits a `--fill` priority to N copies. `--heal-below F` takes Baya Zidra when HP is at or below that fraction, ahead of the stat cards (0 = only if the fill list prefers it). `--dodge F` ignores that fraction of contact and shot damage (lava and weather still hit). `--lock 2:4` starts with 4 Vigor and takes no more (index 7 is Aprendizaje).
`tasks` also writes `median_kills`, `median_bosses`, `median_kpm` and `median_coins`. Coins are game.js:295-301 with coinMul 1 (upgrades.js:41, no Fortuna): `floor(time/5) + floor(kills*0.25) + bosses*80 + picked`, rounded. Picked coins are the boss shower (enemy.js:174, 10×5) and the rift-legend shower (enemy.js:191, 10×8). A rift legend counts as a boss (rift.js spawnLegend, enemy.js:910).

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
  dash, mine, trail and turret, plus the eight kinds of the 66610d9 update (homing, bounce, charge, spin, quake, vortex,
  shove, stun; see below), following systems/combat.js. Life Orb costs HP only on a cast that actually fires, and
  never for orbit or trail, including companion casts (player.js:203). Without the flag these moves stay inert.
- **Synergies on the ranking path** (`--status` or `--xkinds`; both are on for a published group rank). The default
  run (neither flag) is the parity path. Citations are the live game:
  - Hex ×1.7 while the target's burn, poison or slow factor is above 0 (data/moves.js `hex`, systems/combat.js:240).
    The factor is checked, not the timer. Burn lasts 3 s (stacks to 8, tick 0.5 s), poison 4 s (stacks to 8, tick 0.6 s),
    slow 1.2 s (enemy.js applyBurn/applyPoison/applySlow). There is no hit-chance roll. The parity path ignores them.
    Group search (`--synergy`, on for `--group`) runs for every species that learns a synergy
    (Hex plus a burn, poison or slow, or two dashes), not a shortlist. It simulates each status
    move with Hex (either one leading) and the three strongest status moves as two appliers + Hex,
    every ordered pair and trio among the top 6 attacks, and every ordered pair of dashes
    even when one of them sits outside that top 6. That top 6 is the better of the species'
    solo-sweep rank and the move-tier rank (`data/move_tierlist_v4.csv`), so a plain pair such as
    Shadow Ball + Aura Sphere is scored against Hex + Lick, and Aerial Ace + Quick Attack is
    scored against a higher-tier lead. The higher composite score wins (mean score, then survival
    time, breaks a tie).
    `results/fixed_group/group_search.csv` is that run.
    `build/combos.py` shows the winning attacks; it does not force the status partner.
    Hex is the only move with a status-conditional damage multiplier (`moves.js` `hex`).
    `--no-synergy` restores the old partner sort (Hex/status or two dashes first, then solo order)
    and skips the extra groups.
    The melee damage cut (×0.75, player.js:254) applies whenever a melee move is in the active group: the starter
    always, a companion only after that bond. It is not gated on an enemy standing in the swing. There is no extra
    contact hit while closing in; body overlap already uses the game's touch cooldown (combat.js:666). A bonded melee
    companion still pulls the bot in to the melee keep (repulse stays off until that gap). That hold is the bot's
    policy, not a game rule. Casts outside the arc still spend the cooldown and hit nothing. Orbit stays out of the
    bonded group because `step_orbs` keeps a single orb list for the active move (combat.js does allow an orbit in
    any slot). Lengüetazo and every other `kind === 'melee'` move goes through the ×0.75 cut.
    No score is adjusted after the sim: melee, turrets (Sustituto) and every other attack are ranked on the score as
    measured, and an attack is any non-buff move with damage (`data::Move::is_attack`). Picotazo Veneno is a projectile
    (speed 420, life 1.0) and is not melee. Pairs and trios may mix categories. Each attack set is simulated with every
    buff fill of the four bond slots (`kits` in `main.rs`): two attacks with Danza Espada, Danza Dragón (species that
    learn it) or Maquinación plus Harden or Agility, and three attacks with one of those attack buffs or with Harden or
    Agility. An attack buff that raises none of the group's attacks is not tried (`patk` buffs only raise physical
    moves, `satk` only special). The best row by score (then mean score, then survival time) is published, and each
    shape (`build/picks.py` `shape_of`) keeps its own shortlist into the refine. Not searched: four attacks with no buff
    (the engine reads `buffs == 0` as "no fixed group") and Acua Aro.
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
    Furia ×2 atk, Rayo ×1.45 speed, Prisa ×0.6 cooldown, Imán ×4 magnet (interact.js:22). The bot triggers one it walks into; it does not path.
  - Shell Bell heals 4% of dealt damage, buffer cap 4 (player.js:295). Rocky Helmet is 15+4×level with knock 80 on
    body contact only (combat.js:668). Focus Sash saves at 1 HP once per 60 s (player.js:248).
  - Orbit rehit is `max(0.12, cd)` with no cooldown multiplier (combat.js:486). Turret rate and trail ticks ignore it too.
  - A bonded companion evolves after its max level once the needs card was taken (moves.js evolve). Coraza clamps
    inside the 0.7 cap on each card (levelup.js:19), and the 0.8 cap is applied after Harden (player.js:96). A vest
    equipped at the start sits in that same 0.7 bucket, so later Coraza cards eat it. Parity (no item) still stops at 0.7.
  - Leftovers adds 1.5 % of max HP once, at equip (items.js:14). The sim equips at t=0, so that is base HP, not HP after Vigor.
  - Vigor and Síntesis have no `max` in levelup.js. The ranking path allows 250, which a 900 s run does not reach.
    Parity keeps the old caps (HP 99, regen 10). On the faithful path a kill drops an orb (pickup.js). The magnet starts at 78 and collects inside 15px. Parity still grants the XP on the kill.

Numbers from this sim are estimates. The type chart (soft ×1.6/0.6/0.3, clamp [0.3, 2.4]) and the exported melee and
evolution rows match the game's own `evolve()`.

`--legacy-group` restores the old behaviour (bonded from t=0, no rifts, bosses, heal orbs or extra kinds). Default runs
(no `--group`) are unchanged.

Physical and special split, from PokéSurvivor `5a23d49a99a795f9262d2fb24a9842f0858a0b50` (19 Oct 2026).

- `stats.js:17-43`. `guard(def) = clamp((75 / max(5, def || 75))^0.35, 0.78, 1.25)`. Damage taken is `guard(sd)` for a special hit and `guard(df)` for a physical one. `sideOf` is special when `sa > pa`, otherwise physical. `fit` is that side's multiplier over `atk` (`atk` is still `max(pa, sa)`). On-side moves hit as hard as before this commit. Pure damage and traps skip the guard.
- `moves.js`. Non-buff moves have `cat` physical or special. Danza Espada and Danza Dragón buff `patk` only. Maquinación (`nasty-plot`) buffs `satk` (0.13, 5 stacks, 7 s) and is a normal-pool move. A published group bonds Maquinación when the lead attack is special, and Danza Espada when that lead is physical. A mixed pair follows the lead. `--dd` is Danza Dragón and only applies to a physical lead. `--np` forces Maquinación. Sustituto is a turret (`dmg` 14, `rate` 0.4, `moves.js`): its shots count as dealt damage, and the published best move skips turrets, buffs and rows that dealt nothing.
- `player.js` `atkFor` and `combat.js` hits. Outgoing damage is `atk * fit(mon, cat) * (1 + the matching side buff)`, then `typeK * guard(enemy)`. Incoming combat damage, including hazards, is multiplied by the player's guard before the type chart. Weather chip and lava are not combat hits.
- `enemy.js`. Enemies strike with `sideOf`. A boss heal is at most `0.4 * rd / 6` and a boss shield at most `1.2 * rd / 6` (one shield while `shieldT > 2`). Poison percent HP uses `maxHp` up to 60,000 and `60000 * sqrt(maxHp / 60000)` above that. Normal enemies and the 900 s bosses stay under that line.
- `spawner.js:79-90` and `enemy.js:620-650`. At most 3 alive healers, shielders and summoners. A healer restores `7% * min(2.5, (atk/baseAtk)^0.35)`, and a boss heals at most `0.4 * rd / 6`. A shielder refreshes the nearest 6: normal enemies to `max(shield, 35%)` with `shieldT = 8`, and a boss is skipped while `shieldT > 2` and otherwise shielded by at most `1.2 * rd / 6`.
- `enemies.js:129-153` and `:203-215`. On the faithful path each tier rolls 7 species once per run: one support, one warning attacker from the second tier on, then the fastest plain becomes the runner (`spd × 1.6`, `hp × 0.7`). Old tiers weigh 3, new ones 10. Parity still draws from the whole tier and turns a random 1/7 of the plain enemies into a runner.
- `spawner.js:25,107-108,159`. The first surge is at 32 s; later surges are `rand(38, 56)`. Wild XP is `round(xp * 5.6)`, then `round(that * 1.6)` for an elite. Parity keeps the 10–30 s opening surge and the unrounded product.
- `pickup.js:73-95` and `enemy.js:967-978`, faithful path only. Kills drop orbs (boss: 14 XP orbs plus heal and magnet; wild: 1.2% heal, 0.8% magnet, 0.6% bomb). A bomb hits everything on screen for `60 + 14 * level` (`game.js:525`). An enemy that is unseen and behind for 2.5 s, or farther than 1400px, respawns ahead of the player.
- `sprites.js:144-151` `playerRadius`. Collision radius is `min(18, bodyRadius(dex, playerScale))`. The faithful path uses that radius, including the 13 species whose idle frame shrinks them 0.9–2.2px under the raw body. Parity keeps `min(18, body radius)`. Enemy radii are the uncapped body. Boss and legendary radius is `body * bossScale(dex)` (`enemy.js:16-22`: 1, 1.5 or 2 from the idle anchor). Parity keeps ×2.
- `levelup.js:42-144` `offer`. A new move weighs 10 (up to 6, on-side weight 2). A ready evolution weighs 40 and is shown first. Each upgradable move weighs 8. Five of the nine stat cards weigh 4 while a move slot is open (20 together) and 7 when the four slots are full; a stat that unlocks an evolution weighs 14 and is always offered. A missing bond member that shows up is learned and that level is spent. The sim does not learn a move outside the fixed group, so a missed offer spends the level on a second weighted draw of upgrades and those stat cards. Two buffs already known drop further buffs. Parity keeps the uniform three-card shuffle.
- `judgment.js`. At t ≥ 1800 in a rift run, Sentencia caps speed (`capSpd`), Arceus pursues (`chase k`) and his touch and hazards are pure damage (`touchPct`, ignoring guard and reduction). A legendary arrives every 5 s at double the previous HP and damage. The published rank is 900 s, so this does not move the tier list. Map-side judgment legends do not grant rift bonds.

The ranking score of a run is `time * sqrt(dps / (dps + 80) * kpm / (kpm + 40))` (`sim-rs/src/stats.rs` `run_score`; 80 and 40 are scale constants of the score, not game numbers). Damage dealt is the post-type, post-guard, post-crit amount before the shield, and it does not include burn or poison damage over time (the game does not add those to `dmgDealt`). A run that survives without dealing damage scores 0, so surviving alone never ranks. Displayed medians stay in seconds. Order, bootstrap jitter and the sim piece of the ensemble use the score.

Known bias (estimates): the bot does not dodge, so sustain (Synthesis `rgn`, Vigor `hp`, Leftovers) still looks strong. Incoming damage is ×0.75 whenever a melee move is in the active group (player.js:254). A melee group is published only when its bootstrap floor is strictly above the best ranged group's median and its mean is not worse. The step is `1/20` s (`game.js:610` steps at about `1/60`, clamped at `1/30`). An audit measurement at `DT = 1/60` moved mean median survival from 77.1–77.4 s to 80.3 s (+3 s, +4%) and shuffled ranks by 38, inside the 42.6-rank seed noise of a 40-seed block. A published 200-seed resim at `1/60` is about three times the runtime and was not run. A check that ignores half of each combat hit (`--dodge 0.5`) lengthens runs and does not move Power or Reflexes ahead of Synthesis. The pasivas page ranks cards by the game's coin reward (game.js:295-301, coinMul 1) and takes Baya Zidra only at or below 70% HP.
build/passives.py `priority` lists the eight stat cards in this coin order on the Build card and marks the lead attack's evolution card; `compute` (the policy's pick sequence) only feeds the summaries. The rift walk is time-at-current-speed, not pathing.
Boss personalities other
than ranged/charger/chase are collapsed. The arena is fought in open space at the map position (no Distortion World
columns or arena weather). The published 900 s window ends before Sentencia; a longer run uses the judgment path above.
Results used for the site are in `results/fixed_group/`.

### PokéSurvivor update (66610d9, 5a23d49)

Game data, the vendored sources in `vendor/pokesurvivor-5a23d49/` and `v3/v3_data.json` (`v3/extract_v3.js`) are pinned to
`5a23d49`. `tmult` and `upgrades_src_ok` in `v3_data.json` are carried over from the previous extract; the rest is re-read
from the game (103 moves, 38 of them new; dragon has 4 attacks in the game, every other type has 5 or more).

- New kinds run on the faithful path only (`--xkinds`, always on for group ranks), as `Kind::Inert` with `xk` 9-16, in
  `sim-rs/src/engine/kinds.rs`. The parity path never fires them. The step is 1/20 s, so spin and vortex carry the
  remainder of their 0.13 s / 0.4 s timers (the game resets at 1/60 s); the first spin hit lands on the cast frame.
- Monotype: single-type Pokémon hit 20 % harder with moves of their own type (`player.js` `MONO_K`).
- Starting move: `Mon::start_choices` is `starters.js` `startChoices` (the pool without buffs plus the stock start, even when
  off-type). Learning a move leaves the move in use active (`player.js` `addMove`); the sim already kept the starter.
- Pools: the card pool is `moves.js` `poolFor` (normal plus own types). Attack pools went from 5-15 (mean 9.6) to 7-21
  (mean 14.4); `levelup.js` itself did not change, so a new-move card is drawn from a bigger pool.
- Tests: `cargo test --release` (`engine/kind_tests.rs`), `node --test v3/game_update.test.js` (v3_data.json against the game),
  `node validate/game_formulas.js` (mono, damp and the older formulas against the game's own functions) and
  `node validate/game_scenarios.js` (the vendored `combat.js` and `projectile.js` on the same scenes as the Rust tests).
- Not modelled: boss-priority targeting, manual aim, coop ghost casts, prop damage, lava ticks while stunned, the ±0.03
  projectile jitter, homing toward `cy()` (the sim has no heights), wall cuts for the plain beam kind (charge and quake do cut).
- Regeneration order (`build/regen.py --sim`): solo screen, solo refine, solo contend, group screen, group refine, start
  sweep, start rank. Group search takes its partners from the solo screen, so it always runs after it.

## Repertoire opening

The published "run with the starting move" is not a second physics run. `pokesim repertorio`
(`sim-rs/src/repertorio.rs`) reads the starter sweep and returns the expected survival of a Repertoire + Veto
opening: ban up to 3 non-buff pool moves that pull the average down, draw the second attack at random from
what remains, play the better of the two. `sim-rs/src/repertorio_cases.json` holds the expected cases. The starter
alone stays in the ranking as `start_noshop_s`. Shop stat upgrades (`rank_v4_max`) are a different measure.

## Credits

PokéSurvivor and its code are by JPTER78: [MIT up to commit b297089; from 14 Oct 2026 new code is PolyForm Noncommercial 1.0.0](https://github.com/JPTER78/pokesurvivor/blob/main/LICENSE). The game data in `v3/` is extracted from that code. This simulator is unofficial and not affiliated with the game or with the owners of Pokémon.
