# SurvivorTiers ficha summaries: writer prompt

You write the short summary shown under the name on each Pokémon page (ficha) of SurvivorTiers, a fan tier list
for the browser game PokéSurvivor (a Vampire-Survivors-like: you dodge waves of enemies, your attacks fire on
their own, you pick a start move, bond up to 4 moves in a group, carry an item and pick level-up cards).

Write from the facts below and nothing else. Do not use what you know about Pokémon from other games.

## Your batch

- Repository root: `{{ROOT}}` (run commands from there)
- Facts: `{{PARQUET}}` (parquet, one row per species)
- Species (dex numbers): {{IDS}}
- Write your output to: `{{OUT}}`

Load your slice with Python (duckdb and pandas are installed):

```python
import duckdb, json
rows = duckdb.sql("""
  select dex, name, name_en, types, tier, rank, speed_pct, hp_pct, attack_pct,
         hitbox_r, hitbox_median, typedef_pct, drivers_up, drivers_down, claims
  from '{{PARQUET}}' where dex in ({{IDS}}) order by dex
""").fetchall()
for r in rows:
    print(r[:14])
    for c in json.loads(r[14]):
        print("   ", c)
```

`claims` is the list of everything you may say about that species. Each claim has a `key`, what it `means`, and
plain wording in Spanish (`es`) and English (`en`). The other columns are context; do not quote numbers.

## What to write

For every species: 2 or 3 short sentences in Spanish and the same in English. Player-to-player tone, plain words,
like a friend giving a tip. No marketing, no "este Pokémon", no exclamation marks.

1. What it is: its stat profile (fast, tanky, hits hard, big or small hitbox, good types...). Pick the 1-3
   clearest traits from the claims.
2. How to build it: start with its start move (`m.start`), bond the group moves (`m.group`; you may skip the
   buff moves if the sentence gets long, and you may offer one `m.alt` in brackets), carry the item (`i.best`).
3. Why it sits at that rank: the main reason from the `up:` / `down:` claims (one up and/or one down). If a
   claim with a tier letter exists (for example `down:hitbox:S`), prefer it. If there is no `down:` claim you may
   say `nodown`; if there are none at all, `calm`.

Mind the grammar: the verb agrees with the reason ("lo frenan sus estadísticas", "lo frena su hitbox grande";
"its stats hold it back", "its hitbox holds it back").

Example of the voice (Spanish): "Rápido y con mucha vida, pero pega poco. Úsalo con Ascuas y Danza Espada. Su
hitbox grande es lo que lo baja del S."

## Marks (required)

Every claim goes inside a mark: `[key|visible text]`. The page turns marks into small icons and the checker uses
the key to verify the claim. The visible text is yours, but keep it close to the claim's wording.

- Trait: `[spd+|Rápido]`, `[hb-|hitbox grande]`, `[td+|aguanta bien los tipos rivales]`
- Names, written exactly as given in that language: `[m.start:ember|Ascuas]`, `[m.group:swords-dance|Danza Espada]`,
  `[m.alt:hex|Infortunio]`, `[i.best:luckyegg|Huevo Suerte]`
- Rank reason: `[up:stats|sus estadísticas]`, `[down:hitbox:S|su hitbox grande lo deja fuera del S]`,
  `[nodown|nada lo frena]`. For `up:best_move` the visible text is the move name, exactly.

## Hard rules (an automatic checker rejects the text otherwise)

1. Use only keys listed in that species' `claims`. Never invent a key or use another species' key.
2. These words state facts, so they may appear ONLY inside a mark whose key covers them:
   - Spanish: rápido, lento, velocidad, vida, pega, daño, hitbox, pequeño, grande, enorme, normal, tipo, tipos,
     ataque inicial, mejor ataque, ataques que aprende, estadísticas, final de partida, partidas largas, tope,
     cuerpo a cuerpo, del montón, normalito, nada lo frena, nada lo baja, ningún factor
   - English: fast, slow, speed, HP, hits, damage, hitbox, small, big, huge, normal, type, types, start move,
     best move, moves it learns, stats, late game, long runs, cap, melee, average, nothing holds it back,
     no single factor
   For example "pega fuerte" must be `[atk+|pega fuerte]`, and "su vida" outside a mark is rejected. Write the
   connecting words around the marks without these words ("Empieza con", "vincula", "lleva", "lo que más lo
   sube es", "Start with", "bond", "carry", "what lifts it most is").
3. No digits anywhere. No tier letters S, A, B, C or D as words except inside a mark whose key ends in that
   letter. In English never start a sentence with the article "A" (it reads as tier A): write "Has a big
   hitbox", not "A big hitbox".
4. Move, item and card names only inside their mark, spelled exactly as in the claim for that language
   (Spanish names in `es`, English names in `en`).
5. Spanish and English must use exactly the same marks (same keys, same number of times).
6. 2 or 3 sentences per language, each ending with a full stop; no "!" or "?" or abbreviations with dots.
   At most 240 characters per language, counting only the visible text.
7. Every sentence starts with a capital letter, also when it starts with a mark (`[hb+|Hitbox pequeño]`,
   `[up:typedef|Its types]`).
8. Say the hitbox the same way everywhere: if the species has `hb--` (huge), a `down:hitbox` reason says
   "hitbox enorme" / "huge hitbox", never "grande" / "big"; otherwise never "enorme" / "huge".
9. Every summary must include at least one trait key, the `m.start` key, the `i.best` key and one rank key
   (`up:...`, `down:...`, `nodown` or `calm`).
10. Spanish verb agreement with the reason is checked: plural reasons ("sus estadísticas", "sus tipos", "los
   ataques que aprende") take "lo suben / lo bajan / lo frenan"; singular ones ("su hitbox", "su mejor ataque",
   "tener un solo tipo de ataque", "cómo aguanta...") take "lo sube / lo baja / lo frena".

## Example (Kommo-o, dex 784; its claims include atk+, hb-, td+, m.start:dragon-rage, m.group:aura-sphere,
## m.group:dragon-dance, m.alt:hyper-voice, i.best:luckyegg, up:best_move, up:stats, nodown)

```json
{"dex": 784, "es": "[atk+|Pega fuerte] y [td+|aguanta bien los tipos rivales], pero tiene [hb-|hitbox grande]. Empieza con [m.start:dragon-rage|Furia Dragón] y vincula [m.group:aura-sphere|Esfera Aural] (o [m.alt:hyper-voice|Vozarrón]) y [m.group:dragon-dance|Danza Dragón]; lleva [i.best:luckyegg|Huevo Suerte]. Lo que más lo sube es [up:best_move|Esfera Aural], y [nodown|nada lo frena] de verdad.", "en": "[atk+|Hits hard] and [td+|shrugs off enemy types], but has a [hb-|big hitbox]. Start with [m.start:dragon-rage|Dragon Rage], bond [m.group:aura-sphere|Aura Sphere] (or [m.alt:hyper-voice|Hyper Voice]) and [m.group:dragon-dance|Dragon Dance]; carry [i.best:luckyegg|Lucky Egg]. What lifts it most is [up:best_move|Aura Sphere], and [nodown|nothing holds it back] much."}
```

Vary the sentence shapes between species; do not copy this example's wording for every one.

## Output

Write `{{OUT}}` with exactly one JSON object per line, one line per species in your batch, nothing else:
`{"dex": <number>, "es": "<marked Spanish text>", "en": "<marked English text>"}`. Use a script (for example
`json.dumps(..., ensure_ascii=False)`) so the file is valid JSONL. Do not edit any other file in the repository.
When done, reply with only: the output path and how many lines you wrote.

{{RETRY_NOTES}}
