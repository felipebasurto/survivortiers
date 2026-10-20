# SurvivorTiers ficha summaries: writer prompt

You write the short summary shown under the name on each Pokémon page (ficha) of SurvivorTiers, a fan tier list
for the browser game PokéSurvivor (a Vampire-Survivors-like: you dodge waves of enemies, your attacks fire on
their own, you pick a start move, bond up to 4 moves in a group and carry an item).

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

1. What it is: its stat profile (fast, tanky, hits hard, small hitbox, good types...). Pick the 1-3
   clearest traits from the claims. Do not mention a big or huge hitbox.
2. How to build it: start with the start move of its best build (`m.start`), bond the group moves (`m.group`; you may skip
   the buff moves if the sentence gets long), carry the item (`i.best`). There are no alternatives (`m.alt`).
3. Why it sits at that rank: the main reason from the `up:` / `down:` claims (one up and/or one down). If a
   claim with a tier letter exists (for example `down:stats:S`), prefer it. If there is no `down:` claim you may
   say `nodown`; if there are none at all, `calm`.

Mind the grammar: the verb agrees with the reason ("lo frenan sus estadísticas", "lo frena su mejor ataque";
"its stats hold it back", "its best move holds it back").

Example of the voice (Spanish): "Rápido y con mucha vida, pero pega poco. Úsalo con Ascuas y Danza Espada. Lo
que más lo sube es Ascuas."

## Marks (required)

Every claim goes inside a mark: `[key|visible text]`. The page turns marks into small icons and the checker uses
the key to verify the claim. The visible text is yours, but keep it close to the claim's wording.

- Trait: `[spd+|Rápido]`, `[hb+|hitbox pequeño]`, `[td+|aguanta bien los tipos rivales]`
- Names, written exactly as given in that language: `[m.start:ember|Ascuas]`, `[m.group:swords-dance|Danza Espada]`,
  `[m.alt:hex|Infortunio]`, `[i.best:luckyegg|Huevo Suerte]`
- Rank reason: `[up:stats|sus estadísticas]`, `[down:stats:S|sus estadísticas lo dejan fuera del S]`,
  `[nodown|nada lo frena]`. For `up:best_move` the visible text is the move name, exactly. Never `hb-`, `hb--`
  or `down:hitbox`: collision radius is capped, so a big sprite is not what holds a Pokémon back.

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
4. Move and item names only inside their mark, spelled exactly as in the claim for that language
   (Spanish names in `es`, English names in `en`).
5. Spanish and English must use exactly the same marks (same keys, same number of times).
6. 2 or 3 sentences per language, each ending with a full stop; no "!" or "?" or abbreviations with dots.
   At most 240 characters per language, counting only the visible text.
7. Every sentence starts with a capital letter, also when it starts with a mark (`[hb+|Hitbox pequeño]`,
   `[up:typedef|Its types]`).
8. Do not say a big or huge hitbox holds the Pokémon back, and do not use the words grande, enorme, big or
   huge for a hitbox. A small hitbox (`hb+` or `up:hitbox`) is still fine when that claim is listed.
9. Every summary must include at least one trait key, the `m.start` key, the `i.best` key and one rank key
   (`up:...`, `down:...`, `nodown` or `calm`).
10. Spanish verb agreement with the reason is checked: plural reasons ("sus estadísticas", "sus tipos", "los
   ataques que aprende") take "lo suben / lo bajan / lo frenan"; singular ones ("su hitbox", "su mejor ataque",
   "tener un solo tipo de ataque", "cómo aguanta...") take "lo sube / lo baja / lo frena".

## Example (Kommo-o, dex 784; its claims include atk+, td+, m.start:dragon-claw, m.group:rapid-spin,
## m.group:swords-dance, m.group:harden, i.best:luckyegg, up:best_move, nodown)

```json
{"dex": 784, "es": "[atk+|Pega fuerte] y [td+|aguanta bien los tipos rivales]. Empieza con [m.start:dragon-claw|Garra Dragón] y vincula [m.group:rapid-spin|Giro Rápido], [m.group:swords-dance|Danza Espada] y [m.group:harden|Fortaleza]; lleva [i.best:luckyegg|Huevo Suerte]. En el ranking, lo que más lo sube es [up:best_move|Furia Dragón], y [nodown|nada lo frena] de verdad.", "en": "[atk+|Hits hard] and [td+|shrugs off enemy types]. Start with [m.start:dragon-claw|Dragon Claw], bond [m.group:rapid-spin|Rapid Spin], [m.group:swords-dance|Swords Dance] and [m.group:harden|Harden]; carry [i.best:luckyegg|Lucky Egg]. In the ranking, what lifts it most is [up:best_move|Dragon Rage], and [nodown|nothing holds it back] much."}
```

Vary the sentence shapes between species; do not copy this example's wording for every one.

## Output

Write `{{OUT}}` with exactly one JSON object per line, one line per species in your batch, nothing else:
`{"dex": <number>, "es": "<marked Spanish text>", "en": "<marked English text>"}`. Use a script (for example
`json.dumps(..., ensure_ascii=False)`) so the file is valid JSONL. Do not edit any other file in the repository.
When done, reply with only: the output path and how many lines you wrote.

{{RETRY_NOTES}}
