# A. Fidelity audit: SurvivorTiers simulator vs PokéSurvivor

Read-only audit. No code was changed. Nothing was pushed to the game repo, PR #40's branch, or any Firebase.

## 0. What was compared

| Thing | Ref |
|---|---|
| Game | `JPTER78/pokesurvivor` @ `e4ba0e1`. Combat is defined by `e868b5e`; `b8e843f` and `e4ba0e1` touch only ranking and Firebase. Paths below are `js/...` in that repo. |
| Sim, **main** | this repo @ `afbb725`. Cited as `engine.rs:N` = `simulator/sim-rs/src/engine.rs`. These are the lines that produced the published ranks. |
| Sim, **#35** | `cursor/phys-special-split-08c8` (physical/special split). It is 8 commits behind main. Cited as `#35 engine.rs:N`. |
| Sim, **#40** | `cursor/e868b5e-run-rules-ebb5` (#35 plus run rules, level-up offers, Judgment). It is based on current main. Cited as `#40 engine.rs:N`. |

Where the sim lives. `simulator/sim-rs/src/engine.rs` (~4,200 lines, Rust) is the engine that makes the published ranks. `simulator/sim/match.js` + `rules.js` is the JS twin. Rust matches it bit for bit with V8 math replayed (`sim-rs/parity.js`), but only on the non-"faithful" path. `simulator/v3/v3_data.json` is game data dumped by `v3/extract_v3.js`, which was written for game commit `a9b21f0`. `simulator/sim-rs/src/main.rs` is the CLI, the group search and the ranking policy. `build/make_definitive.py` + `data/ranking_definitive.csv` are the site pipeline.

Two rule sets live inside the engine. **Parity path** is the default, with no status effects and no extra move kinds. **Faithful path** is `faith() = status || xkinds` (`engine.rs:1419`). Every published group rank uses the faithful path. Parity tests never run it.

How the audit was done:
- I read the game files for every mechanic in the brief and the matching sim code.
- I re-extracted the game data and diffed it against each branch's `v3_data.json`.
- I ran three empirical checks with the Rust build (section 4).

Impact column = how much the item can move a published rank (high / med / low). "Unsure" marks anything I could not verify from source alone.

---

## 1. Headline findings (read this first)

**H1. The published ranks measure the first ~100 seconds of a run, not the game.**
- In `results/fixed_group/g2p2/rank_200.csv` (the 2+2 rank on the site), the median species dies at **71 s** and the best at **112 s**.
- No species has even a p90 above 180 s. Median kills is 27 and median level is 5.
- 450 of 966 species have a median above 75 s. None is above 180 s.
- Rifts cannot open before t=105 s (`rift.js:25-26,29,43-46`; the sim copies this at `engine.rs:2473-2481`). Bosses start at 180 s (`enemies.js:45`).
- So for most species the "2+2 fixed group" never forms. The run is the starter attack only. Boss, rift, bond, Swords Dance and Harden code (3,000+ lines) is dormant for the median run.
- The game designs every run to reach Arceus at minute 30 (`judgment.js:32`, `enemies.js:174-175`).
- I cannot prove from source what a human gets, because nothing in the repo is calibrated against real play. The README admits "the bot does not dodge". The gap is still ~16x in time. That makes the ranking a "who tanks and kills in the opening" score.

**H2. Nothing checks the sim against the game.**
- `parity.js` checks Rust against JS. Both were written from the same reading of the game.
- `rules.test.js` asserts hand-typed numbers. The shield test (`a second shield does not stack`) passes under both the game's rule and main's wrong one, because both end at 35% (`enemy.js:650` uses `max`). It never checks the timer refresh or the slot count that differ (`enemy.js:642-650`).
- `import_game_combat.py` and `test_combat.py` check the Python data export, not the engine.
- No test executes the game's own JS (`combat.js`, `enemy.js`, `levelup.js`) against the sim for a seed or a scripted scenario.

**H3. Main predates the game's `e868b5e` combat.**
- Main has no physical/special split, no `pa/sa/df/sd`, no def clamp, no Maquinación (`nasty-plot` is missing from `v3_data.json`), and Swords Dance boosts all attacks.
- #35 and #40 fix the split. The data in #35/#40 matches the game for all 966 species on `pa/sa/df/sd`. I checked this programmatically.
- Every currently published rank is pre-split.

**H4. The level-up offers are not the game's.**
- Main picks 3 cards uniformly from a pre-filtered legal list (`engine.rs:1863-1873`). The game uses weighted offers: new move w10, evolution w40 and always shown first, upgrade w8, 5 of 9 stat cards at w4 (`levelup.js:42-144`).
- #40 reproduces the new-move draw with `pickWeighted` and the 2-buff cap, but folds all non-move cards into one constant weight of 28 (`#40 engine.rs:2205-2235`). The game's weight is 8 per upgradable move plus 20.
- Pool size and card weights decide how fast a group forms, so this matters most for group ranks.

**H5. Three invented rules shape melee rankings.**
- The melee ×0.75 cut is only applied while a foe is inside the swing (`engine.rs:1472-1476`). The game applies it whenever a melee move is in the active group (`player.js:254`).
- `tick_melee_risk` (`engine.rs:3000-3027`) hits the player with a phantom contact hit while closing on a bonded melee move. No enemy is touching.
- Gengar (dex 94) is hard-banned from melee bonds (`main.rs:242,531`).
- The first two hurt melee species. Together they can move a melee species by tens of ranks. I did not quantify this.

---

## 2. Mechanic table

Verdicts: OK / WRONG / MISSING / HACK. "Main/#35/#40" lists status per branch when it differs.

### 2.1 Damage pipeline, stats, types

| Mechanic | Game file:line + value | Sim file:line + value | Verdict | Impact |
|---|---|---|---|---|
| Player→enemy hit | `combat.js:532-543`: `dmg = m.dmg*atkFor(m)*typeK*taken(e.mon,m.cat)*(crit?1.5:1)` | main `engine.rs:723-775,795-841`: `dmg*atk*type*weather`. No `taken` | main WRONG (no def); #35 `strike/hit_one` add `taken_of` (OK) | high |
| Physical/special split | `stats.js:34-42`, `player.js:98-102`: `atkFor = atk*fit(pa or sa / atk)*patk or satk buff` | main: none; `Mon` has only `atk`. #35 `engine.rs:1587` `atk_for` (OK) | main MISSING; #35/#40 OK | high |
| `atk = max(pa,sa)` | `stats.js:3-4` | main `v3_data.json` lacks `pa/sa/df/sd`; #35/#40 data match game on 966/966 | main MISSING; #35/#40 OK | high |
| Def clamp | `stats.js:17,21`: REF 75, EXP 0.35, clamp [0.78, 1.25], `def\|\|75`, `max(5,def)` | #35 `guard()` (diff ~l.739): same constants | main MISSING; #35/#40 OK | high |
| Enemy→player damage | `player.js:243-255`: `amount*taken(player,cat)*typeK*weather*(1-reduction)*close`, min 1. `enemy.cat = sideOf(mon)` (`enemy.js:69`) | main `engine.rs:1530-1541`: no def, no `max(1,…)`. #35 adds `g` by enemy cat; still no `max(1)` | main WRONG; #35/#40 mostly OK (no min 1: low) | high |
| Type chart | `types.js:34-43`: soft 2→1.6, 0.5→0.6, 0→0.3, clamp [0.3, 2.4] | `extract_v3.js:20-28` builds the table by calling the game's own `G.Types.mult`. Lookup at `engine.rs:687` | OK | – |
| Weather type factor | `combat.js:87` `typeK = Types.mult * Weather.mult` | `engine.rs:315` `weather_factor` | OK (unsure: not line-verified vs weather.js) | low |
| STAB | none in the game | none in the sim | OK | – |
| Crit | `combat.js:529-536`, `player.js:59`, `upgrades.js:16,43`: perk only, 3% per level, ×1.5 | `engine.rs:101,830` perk only; published uses 0 | OK | – |
| Hex ×1.7 | `combat.js:243`: chain only, while burn/poison/slow > 0 | `engine.rs:714,2246`: chain only; factor checked, not timer | OK | low |
| Burn / poison / slow | `enemy.js` applyBurn/applyPoison/applySlow; pctHp `enemy.js:42-43` | `engine.rs:14-20` (1.2 s/3 s/4 s, max 8, ticks 0.5/0.6). pctHp sqrt rule only in #35 `~l.3485` | OK; main WRONG for HP above 60k (bosses only, low) | low |
| Min damage 1, rounding | `Enemy.hurt` rounds, min 1 (via `hurt_dot`/`raw_hurt`) | `engine.rs:773-841`: `strike` on the parity path does not round | parity-path WRONG (low); faithful path OK | low |
| Melee ×0.75 | `player.js:254`: any melee in `activeGroup()` | main `engine.rs:1472-1476`: starter always, companion once bonded, **and (ranking path) only while a foe is in the swing** | HACK | high for melee species |
| Phantom close-tax | none | main `engine.rs:3000-3027` + `bonded_melee_radius` 2951 | HACK | med-high for melee |
| Dash invulnerability | `combat.js:314` `invuln = max(invuln, 0.3)` | `engine.rs:2324` | OK | – |
| Contact: touch cooldown, knock | `combat.js:666-676`: touchCd 0.55, knock 150, thief skips | `engine.rs:27` TOUCH 0.55, `INV` 0.45 at 26 | OK | – |

### 2.2 Moves

| Mechanic | Game file:line + value | Sim file:line + value | Verdict | Impact |
|---|---|---|---|---|
| Move base values (dmg, cd, speed, life, radius, arc, pierce, knock, count) | `moves.js` via `Moves.instance` | `v3_data.json`; fresh extraction diff: numbers match on main and #40. #40 differs only in descriptions and a null cat | OK | – |
| Move kinds simulated | `combat.js:47-64` 14 kinds | `data.rs:53` parity path simulates 6 (melee, beam, orbit, nova, projectile, boomerang). The rest are inert unless `xkinds`; `xkinds` is on for published group ranks (`engine.rs:2185-2390`) | OK on the faithful path; parity path HACK-by-omission | med |
| Targeting / reach | `combat.js:66-80`: melee r+30, beam r+20, boomerang r+40, chain 280, meteor 340, dash r+60, cone speed*life+30; else 520 | `engine.rs:2190-2230` comments cite the same numbers for cone/meteor/chain; `engine.rs:355` keep distance | OK (unsure: projectile/beam/melee paths read earlier, not re-verified line by line) | low |
| Which moves count as melee | `player.js:254` `kind === 'melee'` only | `engine.rs:1472`; dash is not melee | OK | – |
| Orbit companion | `combat.js:28` orbit in any group | main `main.rs:229-235`, README: orbit never bonded ("one shared orb list") | WRONG (omits a real option) | med for orbit species |
| Turret (Sustituto) | normal move | `main.rs:438` (#40) excluded from "publishable attack" | HACK | low-med |
| Move evolution | `moves.js` `evolve`, `evoInfo` | `engine.rs:1700-1720` same gate (max level + needs card). Data from game | OK | – |
| Projectile pierce/AoE | `projectile.js`, `combat.js:109-` | `engine.rs:2745-2878` | OK (unsure: collision radius `r+e.r` vs game `queryCircle`, lightly checked) | low |
| Hitbox of tall enemies for ranged shots | n/a (no terrain culling in the dump) | no terrain on the published path (`--terrain` is not the default) | note | low |

### 2.3 Buffs (Danza Espada, Danza Dragón, Maquinación, Fortaleza)

| Mechanic | Game file:line + value | Sim file:line + value | Verdict | Impact |
|---|---|---|---|---|
| Stack/overwrite | `player.js:323-329`: amount is overwritten by the latest cast, `n=min(max,n+1)`, `t=dur`; `player.js:336-342`: all stacks drop together at `t<=0` | main `engine.rs:3339-3385` same (stacks +1, refresh duration, all stacks expire together) | OK | – |
| Which attacks Swords/Dragon Dance boost | `player.js:98-102`: physical only (`patk`); Nasty Plot = `satk` | main `engine.rs:1451-1452`: all attacks. #35 `~l.1500` OK | main WRONG; #35/#40 OK | high for special attackers |
| Maquinación | exists at `e868b5e` | main: move missing from the data; #40 patches it into pools in code (`#40` data.rs comment: "missing from `pool` until here") because `v3_data.json` was not re-extracted | main MISSING; #40 HACK (code patch over stale export) | med |
| Fortaleza | `def` buff, `reduction = min(0.8, dmgReduce + n*amount)`, `player.js:109` | `engine.rs:1478-1488` cap 0.8 | OK | – |
| Buff cast cadence | `combat.js:27-45` cd = `max(0.05, cd*cdMul)`, no target needed | `engine.rs:3377-3380` `cd*cd_mul`, no 0.05 floor | OK (low) | low |
| Inactive slot freeze | `combat.js:24` | `engine.rs:3370-3373` | OK (only `--swap`, not published) | – |

### 2.4 Level-ups, cards, items

| Mechanic | Game file:line + value | Sim file:line + value | Verdict | Impact |
|---|---|---|---|---|
| Offer structure | `levelup.js:126-144`: evo card first, then weighted pick of 3 from {new w10, evo w40, up w8, stat w4 or w7 or w14} | main `engine.rs:1863-1873`: shuffle the legal list, take 3, uniform | WRONG | high (timing of every evolution and group move) |
| `poolFor` + dilution | `levelup.js:55-59`, `moves.js:442-446`: species pool, `pickWeighted(pool, 6, w)` with w=2 on-side/1 off-side | main: none (group moves are the "Sd/Hd/Up2" cards, always legal once bonded). #40 `offer_weight 2184`, `pick_weighted 764`, `try_learn ~2205` | main MISSING; #40 OK | high |
| 2-buff cap | `levelup.js:47-49,56`: no new buff once 2 are known | main none. #40 `try_learn` `buffs_known >= 2` | main MISSING; #40 OK | med |
| Stat subset | `levelup.js:110`: 5 of 9 random stat cards shown, plus any that unlock an evo | main: all legal stat cards in the pool | WRONG | med |
| Stat values | `levelup.js:10-27` hp +20, atk ×1.1 (max 40), spd ×1.07 (8), cd ×0.92 (10), def +0.06 clamped 0.7 (12), rgn +0.9, mag ×1.3 (6), xp ×1.12 (8), heal 45% | `data.rs:70` CAPS `[40,8,99,12,10,10,6]`, tables in `main.rs:482-492`, regen `engine.rs:1495` | OK (Vigor/Síntesis cap differs: 99/10 parity, 250 faithful, none in game; not reachable in 100 s) | low |
| Baya Zidra, Aprendizaje | `levelup.js:24-27` | only with `--full-cards`; the published runs exclude them (README) | MISSING from published pool | low-med |
| XP curve | `player.js:87-90`: `floor((8+6L+L^1.75*1.6)*4)` | `engine.rs:1382-1385` | OK | – |
| XP delivery | `pickup.js:73-96`, `game.js:495-498`: orbs must be collected (magnet radius, pull), boss = 14 orbs | `engine.rs:1910-1940` instant global grant at the kill, Imán does nothing | WRONG (unsure of size) | med |
| XP per enemy | `spawner.js:107` `round(def.xp*5.6)`; elite ×1.6 `:108` | `engine.rs:1919` `raw*5.6` unrounded (tier 0: 19.6 vs 20); elite xp ×1.6 absent | WRONG (small); elite xp MISSING | low |
| Heal orb | `pickup.js:81,93` boss always, 1.2% per kill; `game.js:515-518` 30% max HP | `engine.rs:1925-1930` same, always collected instantly, only when `ext.bosses` | OK in value, WRONG in pickup assumption | low-med |
| Magnet / bomb orbs | `pickup.js:94-95` 0.8% magnet, 0.6% bomb (`game.js:525-533` hits everything on screen for 60+14*lvl) | absent | MISSING | low |
| Huevo Suerte | `items.js:26-27` ×1.3 xp | `main.rs` item table; `engine.rs:1892` | OK | – |
| Cinta Elección, Vidasfera, Garra Rápida, Pañuelo, Chaleco, Restos | `items.js:13-35`: ×1.4 atk, ×1.3 atk, cd ×0.8, spd ×1.35, +0.2 reduce, 1.5% regen | `main.rs:157-162` same values | OK (published ranks use no item) | – |
| Focus Sash, Shell Bell, Rocky Helmet | `player.js:264-270`, `:289`, `combat.js:673` | `engine.rs:1544-1560`, bell 4%/cap 4 | OK | – |

### 2.5 Enemies, spawns, caps

| Mechanic | Game file:line + value | Sim file:line + value | Verdict | Impact |
|---|---|---|---|---|
| Spawn rate | `spawner.js:36` `(1.6+t*0.028+(t/60)^1.6*0.5)*0.24` | `engine.rs:1387-1389` | OK | – |
| HP / dmg / speed scale | `enemies.js:176-178` hp `1+t/95`, dmg `1+t/420`, spd `1+min(0.35,t/1400)`; `spawner.js:23` hpK `3.3+min(1.7,t/210)`; `DMG_K 2.4` | `engine.rs:3183-3190,3203,3210` | OK (hp not rounded; game `Math.round`, negligible) | – |
| Cap / elite | `spawner.js:17`: CAP 64, elite from 0.85 (hp ×1.6, dmg ×1.25, xp ×1.6) | `engine.rs:21-22,3266-3271` hp, dmg, shot ×1.25; **no xp ×1.6** | WRONG (small) | low |
| Per-run enemy cast | `enemies.js:129-153`: each run rolls **7 species per tier** (1 support, +1 attacker-with-warning from tier 2); old tiers weight 3, new ones 10 (`:203-215`); one fastest plain enemy per tier becomes the runner | main `engine.rs:3135-3169`: draws from **every candidate** of the tier at random. Runner = random 1/7 of chase/charger/tank, not one per tier | WRONG | med-high |
| Support cap | `spawner.js:79-90,95-101`: max 3 live healers / shielders / summoners; re-pick if full | main: absent. #35 `support_full ~3133`, #40 `:3689` | main MISSING; #35/#40 OK | med |
| Healer on bosses | `enemy.js:620-632`: boss heal ≤ `rd/6*0.4` | main `engine.rs:848` full `heal_fraction` | main WRONG; #35/#40 OK | low (bosses almost never occur, H1) |
| Shielder semantics | `enemy.js:642-650`: nearest 6, normal enemies refresh `max(shield, 35%)`, only boss with `shieldT>2` skipped, boss shield ≤ `rd/6*1.2` | main `engine.rs:859`: skips any enemy with `shield_t > 0`, no refresh. #35 OK | main WRONG; #35/#40 OK | med |
| Elite / thief / golden / events | `events.js` (hordes, golden, lost, thieves from t≥120/240) | absent | MISSING | low (they start at 240 s+ for events) |
| First surge | `spawner.js:25` `surgeT = 32`, then `rand(38,56)` | `engine.rs:3848` `world.next()*20+10` (10-30 s) | WRONG | low-med (in the window that decides ranks) |
| Surge size | `spawner.js:164` `round((14+floor(t/22))*0.4)` | `engine.rs:4022` same | OK | – |
| Drip accumulator | `spawner.js:151-155`: only while count<CAP | `engine.rs:4008-4015`: accumulates always, `roll_spawn` drops at the cap | OK in effect | – |
| Straggler respawn (anti-kiting) | `enemy.js:967-978`, `spawner.js:181-190`: unseen+behind for LAG_T, or >1400 px, re-spawn ahead of the player | absent. Stragglers stay alive and fill the cap | MISSING | low for the published Repulse bot; high if any bot kites |
| Enemy radius | `enemy.js:55` `bodyRadius(dex, scale)` | `extract_v3.js:8` same formula | OK | – |
| Enemy AI (chase, charger, runner, bomber, jumper, ranged, fan, beamer, zoner) | `enemy.js` | `engine.rs:3390-3770` | unsure (read, not line-verified for every constant) | med |
| Weather | `weather.js:67-70,111-124` | `engine.rs:3275-3335` faithful path cites the same | OK (parity path simplified) | low |

### 2.6 Bosses, rifts, Judgment, overtime

| Mechanic | Game file:line + value | Sim file:line + value | Verdict | Impact |
|---|---|---|---|---|
| Boss slots | `enemies.js:44-50`, `:156-170`: 180/360/540/720/900 s, hp ×1.35, dmg ×1.2, `bossScale = 1+t/600` | `engine.rs:2647-2745` same numbers | OK | low (H1) |
| Boss hit radius | `enemy.js:15-22`: `bossScale(dex)` is 1 / 1.5 / 2 from sprite height. Of boss-eligible species: 109 are ×2, 136 are ×1.5, 9 are ×1 | `engine.rs:1168` always ×2 ("estimate") | WRONG (bosses ~33% too big for 54% of picks) | low |
| Boss behaviours | `enemies.js:167` ranged / charger / chase; the game has no further behaviours | `engine.rs:2678` same | OK | – |
| Wave drop while a boss is up | `spawner.js:146-152` ×0.25, no surge | `engine.rs:4009,4016` | OK | – |
| Rift timing | `rift.js:25-26,43-48`: FROM 75, CHECK 30, CHANCE 0.2*(1+misses), TTL 45, arena 120 s, `time < Judgment.AT-120` | `engine.rs:2453-2491` same | OK | – |
| Rift placement and walk | `rift.js:51-60`: 24 tries, d in [380,560], y×0.85, player walks | `engine.rs:2496-2525`: `walk = (dist-30)/speed`, no pathing | HACK (estimate) | low-med |
| Legendary stats | `rift.js:138-155` | `engine.rs:2546-2592` hp `round(3200+9t)`, dmg `36+t/20` etc. | OK (unsure: not diffed numerically vs rift.js:138-155) | low |
| Bond choice | `player.js:174-181` `bondOptions`: the player chooses the fusion | sim assumes attacks, then the attack buff, then Fortaleza, max 3 bonds (`engine.rs:3870-3880`) | HACK (policy) | med |
| Arceus Sentencia (min 30, min 40, anti-kiting) | `judgment.js:32` AT 1800 s, `:46-48` speed cap 130 (25% above), `:48` touchPct 40% to 100% at arena sec 600, `:259` chase factor | main: absent (sim ends at 900 s). #40 `engine.rs:787-796` ports the three formulas | main MISSING; #40 present but unreachable at 900 s | none for published ranks |
| Overtime after min 60 | removed (`enemies.js:174-175`) | none | OK | – |
| Run length | game: until death or Judgment at 1800 s | `--seconds 900` default | note (H1 makes it moot) | – |

### 2.7 Player: hitbox, speed, bot

| Mechanic | Game file:line + value | Sim file:line + value | Verdict | Impact |
|---|---|---|---|---|
| Player hitbox | `sprites.js:127-151`: `min(18, bodyRadius(dex, playerScale))`, scale shrinks tall sprites | main `extract_v3.js:8,19`: raw `bodyRadius` up to 52 px. 142 of 966 species are above 18. #35 `r.min(18.0)`: leaves 13 species 0.9-2.2 px too big (shrink not modelled) | main WRONG; #35/#40 mostly OK | med (big species were penalised on main) |
| Player speed | `player.js:103-108`, Judgment cap `judgment.js:47` | `engine.rs:1462-1476`; Judgment cap only in #40 | OK | – |
| Weather speed | `weather.js:67-70` | `engine.rs:1393-1409` | OK | – |
| Movement | `Input.axis()` human | `engine.rs:3029-3130`: Repulse (inverse-gap push from all enemies within 160 px), Line, Kite. 0.25 s reaction. No dodging of telegraphed attacks, shots or hazards | HACK (bot policy) | high (this decides who survives) |
| Bot melee hold | none | main `engine.rs:3030-3039`: hold at `0.55*radius` for bonded melee | HACK | med |
| Altars | `interact.js` | `engine.rs:1612-1645` "bot does not path", walk-in only | HACK | low |

### 2.8 Time step and RNG

| Mechanic | Game file:line + value | Sim file:line + value | Verdict | Impact |
|---|---|---|---|---|
| Step | `game.js:610` `dt = min(1/30, real dt)` (about 1/60) | `engine.rs:11` `DT = 1/20` | WRONG | low (measured, section 4) |
| Cooldown reset | `combat.js:37` `m.t = max(0.05, cd*cdMul)` | `engine.rs:4073-4075` | OK in shape. At DT 1/20 each cast waits up to 0.05 s extra (+0.025 s on average) | low-med for short-cooldown moves |

---

## 3. Hard-coded overrides and special cases

| Where | What | Verdict |
|---|---|---|
| `main.rs:242,531` (#40 also `:246,465,577,789,798,806`) | Gengar (dex 94) can never bond or lead with a melee move. The game offers it all of them. | HACK |
| `main.rs` group search ("melee published only when its bootstrap floor beats the best ranged median", README) | Melee groups need a statistical margin that ranged groups do not. | HACK (policy) |
| `main.rs:438` (#40) | Turret moves (Sustituto) are never counted as a species' attack. | HACK |
| `main.rs:229-235` | Orbit moves are never bonded as companions. | WRONG |
| `engine.rs:2583` | Boss and legend radius ×2. | WRONG (estimate) |
| `engine.rs:3000-3027` | Phantom contact hit for melee bonds. | HACK |
| `engine.rs:1472-1476` | Melee cut gated on a foe in the swing. | HACK |
| `engine.rs:3848` | First surge randomised in 10-30 s. | WRONG |
| `engine.rs:3162` | Runner = random 1/7 of plain enemies. | WRONG |
| #40 `data.rs` / `engine.rs` | Maquinación patched into every pool in code. | HACK |
| #35/#40 `stats.rs` (`run_score`) | New rank metric `time * dealt * (1+kills)`. That is a design choice, not a game mechanic. | note: not game-faithful by construction |
| `engine.rs:1655-1657` | Vigor/Síntesis caps differ between paths (99/10 vs 250). | low |

Jumpluff, Honchkrow, Rowlet and Dartrix are named in a #40 comment (`main.rs:629`) as cases for the dash-pair search. I found no per-species code branch for them. The commit title "Expect Jumpluff's vine whip" is a test expectation, not an engine override.

**Double-applied effects.** I found none in the damage arithmetic. #35's `atk_for` multiplies `st.atk` by `fit` and the side buff, and `stats()` puts a patk/satk buff in the side term only, so it is not counted twice. The phantom close-tax is not a double count but an effect with no game counterpart.

---

## 4. Empirical checks I ran (Rust build of main, all 966 species, solo starter, default flags)

1. **Time-step bias.** I rebuilt with `DT = 1/60` and ran 40 seeds. Mean median survival went from 77.1-77.4 s to 80.3 s (+3 s, +4%). It is systematic and benign for the ordering at this resolution.
2. **Seed noise.** Two runs at `DT = 1/20` with different seeds (1-40 vs 1001-1040) shuffle species by a mean of **42.6 ranks** (272 species move by 50 or more). The `DT = 1/60` change shuffled by 38 ranks against the same seeds, which is within noise. At 200 seeds I expect ~19 ranks of noise (scaled by √(40/200), not measured).
3. **Resolution of the published rank.** In `g2p2/rank_200.csv` the bootstrap interval is ~5.3 s wide. Rank 100 (Gyarados) has 149 other species inside its interval; rank 50 has 80; rank 300 has 176. Positions 40-400 are effectively tied. The site prints individual ranks.

The engines and the rank noise do not hide the structural issues above; they are separate from them.

---

## 5. Do the tests compare the right things?

| Test | What it compares | Verdict |
|---|---|---|
| `sim-rs/parity.js` | JS `match.js` vs Rust, bit-exact, parity path only (status and xkinds off) | Verifies the port, not the game. The published path is untested. |
| `sim/test/rules.test.js` | Hand-written expectations (xp 62, 7% heal, shield no-stack, Hex ×1.7) | The shield test cannot tell main's rule (skip while `shield_t > 0`, no timer refresh) from the game's (`enemy.js:648-650`: refresh `shieldT = 8` and take `max`), since both leave 35%. |
| `sim/test/match.test.js`, `rank.test.js`, `repertorio*.test.js` | Engine invariants and ranking arithmetic | No game reference. |
| `build/test_combat.py`, `import_game_combat.py` | Python export of `pa/sa/df/sd` vs `pokedex.js` | Good: it refuses a changed base stat. It covers data, not engine behaviour. |
| `engine.rs` unit tests (`coin_tests`, `hex_tests`) | Coin formula `game.js:311-316`, Hex factor | Fine, but small. |

Not covered by any test: level-up offers, spawn bag, elite scaling, support caps, the first-surge time, XP delivery, the melee cut, and any total-run outcome.

---

## 6. Prioritized fixes

1. **Ground-truth the run length and kill count (H1).**
   - Run the real game's JS headless with a scripted bot for ~20 seeds, or record a few human runs, and compare time of death, kills and level against the sim for the same species.
   - Until the medians are in the same order of magnitude, the group, boss and rift machinery does not drive the rank.
   - Likely culprits: bot dodge, enemy cast (below), XP pickup, level-up weights.
2. **Merge #35 and #40's data work, then re-extract `v3_data.json` from `e4ba0e1`.** Main still ranks pre-split. The extractor header targets `a9b21f0`. Have it emit `pa/sa/df/sd`, `cat`, `patk/satk` and `nasty-plot`, so no code patch is needed.
3. **Replace the uniform level-up with the game's offer (`levelup.js:42-144`).** Include the evolution card first, 5-of-9 stat subsets, the up cards, and the real non-move weight (8 per upgradable move + 20). #40 has about 70% of this. The constant 28 is the gap.
4. **Build the per-run enemy cast (`enemies.js:129-153,203-215`).** Draw 7 species per tier once per run, with one support and one warning attacker from tier 2, and one fastest-plain runner per tier. Today every candidate in the tier is equally likely.
5. **Remove the melee rules that are not in the game.** Apply ×0.75 whenever a melee move is in the group (`player.js:254`) and delete `tick_melee_risk`. If melee is overrated after that, the cause is elsewhere (likely the bot). Drop the Gengar ban and the melee-only bootstrap floor.
6. **Shield and healer semantics (`enemy.js:620-650`)** and the live support cap of 3. #35/#40 have them. Extend `rules.test.js` to check the timer refresh and slot count.
7. **First surge at 32 s, elite xp ×1.6, `round(xp*5.6)`, `max(1,dmg)`.** All are one-line changes.
8. **Model XP and heal orbs as pickups** (magnet radius, `pullAll`, bomb, boss 14 orbs), or document the instant grant as a known optimistic bias and measure its size.
9. **Port the straggler respawn (`enemy.js:967-978`)** before using the Kite bot for anything.
10. **Run the game step (`DT = 1/60`).** The cost is ~3x runtime. It removes a +4% bias and the quantisation of short cooldowns.
11. **Use the exact boss scale (`bossScale(dex)`, needs sprite `ay`).** The data is already in `sprites-meta.js`.
12. **Include orbit and turret moves in the companion search**, or state the exclusion on the site.
13. **Add a game-vs-sim test.** Evaluate the real `combat.js hit`/`player.js hurt` formulas on a fixed table of (move, enemy, buff) cases and assert equality with the Rust functions on the faithful path. Cheap, and catches the "patched until it drifted" failure.
14. **Print rank bands, not ranks.** Rank 100 is tied with ~150 other species.

---

## 7. What I did not verify

- Enemy AI constants for each behaviour in `enemy.js` (bomber, jumper, fan, beamer, zoner) against `engine.rs:3390-3770`. I read them and saw no mismatch, but did not check every number.
- Legendary arena stats against `rift.js:138-155`, and the arena geometry (the sim fights in open space).
- Weather numbers beyond the sand/snow chip and the speed factor.
- Hit-collision radii for projectiles, boomerangs and orbits on the faithful path.
- The size of the effect of each WRONG/HACK row. Only the time step, noise and rank resolution were measured.
- `starters.js`, `progress.js`, and shop perks. The published ranks use no permanent perks.
