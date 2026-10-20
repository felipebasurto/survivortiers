"""Lo que necesita un agente de IA (o un buscador) para usar el sitio sin leer el HTML:

- llms.txt: índice del sitio y de los datos, con enlaces absolutos (formato de llmstxt.org).
- llms-full.txt: diccionario de datos, unidades, método y ejemplos. Es la explicación que hace falta para usar bien los JSON.
- robots.txt y sitemap.xml: las páginas en los dos idiomas, incluidas las fichas estáticas /pokemon/<n>-<nombre>/.
- data/ranking.csv, data/meta.json y data/gachas.json: los datos que se describen (el CSV es el ranking tal cual sale de
  make_definitive.py, sin la línea de comentario).
- JSON-LD Dataset en la portada (dataset_jsonld), para buscadores y agentes que leen el HTML.

render.py llama a write_all() al final de main(). Todo sale de build/out/ y de data/; no se edita a mano.
"""
from __future__ import annotations

import json
from pathlib import Path

import landing
import legal
import seo
import toolpages
from i18n import EN, ES, TYPE_NAMES, Lang

ROOT = Path(__file__).resolve().parent.parent
RANKING_SRC = ROOT / "data" / "ranking_definitive.csv"
PAGES = ["", "novedades.html", "ataques.html", "objetos.html", "pasivas.html", "gachas.html", "coleccion.html", "metodo.html", "acerca.html"]
LANG_PREFIX = {"es": "", "en": "en/"}
SIM_CAP_S = 900  # tope de la simulación de supervivencia (sim_lede en build/i18n.py)


def _url(rel: str) -> str:
    """URL absoluta de una página o archivo. Las páginas van sin .html: Workers y Pages redirigen las .html (307/308)."""
    if rel.endswith(".html") and rel != "404.html":
        rel = rel[: -len(".html")]
    return f"{legal.SITE_URL}/{rel}"


def _ranking_csv() -> str:
    """El CSV de make_definitive.py sin las líneas de comentario de arriba (cada línea empieza por '#')."""
    lines = RANKING_SRC.read_text(encoding="utf8").splitlines(keepends=True)
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    return "".join(lines)


def dataset_jsonld(L: Lang, meta: dict) -> str:
    """JSON-LD schema.org Dataset para la portada de cada idioma. No nombra al autor del sitio."""
    base = _url("en/" if L.en else "")
    files = [("text/csv", "data/ranking.csv", "Ranking (CSV)"),
             ("application/json", "data/pokemon-index.json", "Pokémon index (JSON)"),
             ("application/json", "data/species.json", "Species details (JSON)"),
             ("application/json", "data/moves.json", "Moves (JSON)"),
             ("application/json", "data/gachas.json", "Gacha banners (JSON)"),
             ("application/json", "data/meta.json", "Method and metadata (JSON)")]
    doc = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": L.t("dataset_name", game=legal.GAME_NAME),
        "description": L.t("index_desc", n=meta["total"], **legal.method_counts(L, meta)),
        "url": base,
        "inLanguage": "en" if L.en else "es",
        "isAccessibleForFree": True,
        "dateModified": meta["generatedAt"][:10],
        "keywords": ["Pokémon", legal.GAME_NAME, "tier list", "ranking", "fan site"],
        "distribution": [{"@type": "DataDownload", "encodingFormat": fmt,
                          "contentUrl": _url(path), "name": label} for fmt, path, label in files],
    }
    text = json.dumps(doc, ensure_ascii=False, indent=1).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{text}\n</script>'


def _page_url(en: bool, key: str) -> str:
    return landing.url(EN if en else ES, landing.page_for(key))


def _type_links(en: bool) -> str:
    names = TYPE_NAMES["en" if en else "es"]
    return ", ".join(f"[{names[t]}]({_page_url(en, f'type:{t}')})" for t in landing.TYPE_KEYS)


def llms_txt(meta: dict, index: list[dict]) -> str:
    u = legal.SITE_URL
    counts = legal.method_counts(EN, meta)
    es_counts = legal.method_counts(ES, meta)
    fresh = f"{legal.freshness_text(EN)}; site rebuilt on {EN.date(meta['generatedAt'][:10])}"
    fresh_es = f"{legal.freshness_text(ES)}; sitio reconstruido el {ES.date(meta['generatedAt'][:10])}"
    top_en, top_es = seo.top_names(EN, index), seo.top_names(ES, index)
    return f"""# {legal.SITE_NAME}

> Unofficial fan tier list for {legal.GAME_NAME}, a survivor-style Pokémon game by {legal.GAME_AUTHOR}. It ranks all {meta['total']} Pokémon in five tiers (S, A, B, C, D). {fresh}. Best five right now: {top_en}. The rank comes only from simulated games: a bot plays {counts['sims']} full games per Pokémon, each game is scored on time alive, damage dealt and kills, and the order is repeated {counts['reps']} times; the median rank is published. The code, the simulator and the data are open source on GitHub. It is not official and not affiliated with Nintendo, Creatures, GAME FREAK, The Pokémon Company or the game's author.

Resumen en español: tier list no oficial de {legal.GAME_NAME}. Los {meta['total']} Pokémon en tiers S a D. {fresh_es}. Los cinco mejores ahora: {top_es}. El ranking sale solo de partidas simuladas ({es_counts['sims']} por Pokémon, puntuadas por tiempo, daño y bajas) y el orden se repite {es_counts['reps']} veces. Código y datos abiertos en GitHub.

The site is static. Pages are in Spanish at `/` and in English at `/en/`. There is no API key, login or rate limit. Each Pokémon has its own HTML page, for example [Mewtwo]({u}/en/pokemon/150-mewtwo/). Field definitions, units and the method are in [llms-full.txt]({u}/llms-full.txt). The data files below are the best source for tables.

Base URL: {u}

## Data

- [Ranking (CSV)]({u}/data/ranking.csv): one row per Pokémon with rank, tier, rank range, method ranks and model columns. Best starting point for tables and analysis.
- [Pokémon index (JSON)]({u}/data/pokemon-index.json): all {meta['total']} Pokémon with rank, tier, rank range and sort values.
- [Species details (JSON)]({u}/data/species.json): per-Pokémon sheet data (starting and best move, simulated survival, move pair, coverage trio, official base stats) and the two builds per Pokémon: the best melee and the best ranged bonded group (`builds`).
- [Moves (JSON)]({u}/data/moves.json): every attack, with tier, type, kind and game parameters. The six boosts are in [moves_unranked.json]({u}/data/moves_unranked.json).
- [Gacha banners (JSON)]({u}/data/gachas.json): the nine banners, pool sizes, S and A rates and the chance of an S or A pull.
- [Method and metadata (JSON)]({u}/data/meta.json): tier cut-offs, tier counts, stability per tier and the method constants.

## Docs

- [Full data dictionary, units and method]({u}/llms-full.txt): every field and rule, with examples.

## Pages

- [Tier list (EN)]({u}/en/): all Pokémon by tier, with search and sorting.
- [Best Pokémon (EN)]({_page_url(True, 'best')}): the top 30, tier S, in order.
- [Best starters (EN)]({_page_url(True, 'starters')}): the starting picks that last longest in the simulated opening.
- [Best legendaries (EN)]({_page_url(True, 'legendary')}): every legendary by rank.
- [Best passives (EN)]({_page_url(True, 'passives')}): level-up cards ranked by coin reward. The Sitrus Berry at 70% HP is a simulation rule, not a game rule.
- Best Pokémon by type (EN), one page per type: {_type_links(True)}.
- [Passives (EN)]({u}/en/pasivas.html): what each level-up card does, how boosts stack and the two-boost cap.
- [What's new (EN)]({u}/en/novedades): the October 18, 2026 update: physical and special moves, bosses, Arceus' Judgment and the controller.
- [Moves (EN)]({u}/en/ataques): attack tier list.
- [Items (EN)]({u}/en/objetos): item tier list.
- [Gacha (EN)]({u}/en/gachas): banners and pull odds.
- [Collection (EN)]({u}/en/coleccion): collection helper.
- [Method (EN)]({u}/en/metodo): how the ranking is built, with the numbers.
- [About (EN)]({u}/en/acerca): fan-site notice, sprite credits and licences.
- [Type finder (EN)]({u}/en/type-finder/): pick one or two types and see which Pokémon have them, with their weaknesses.
- [Build planner (EN)]({u}/en/build-planner/): the bonded group, item and cards of a Pokémon, with a shareable link.
- [Sitemap]({u}/sitemap.xml)

## Optional

- [Tier list (ES)]({u}/): the same site in Spanish, with [Mejores Pokémon]({_page_url(False, 'best')}), [Mejores iniciales]({_page_url(False, 'starters')}), [Mejores legendarios]({_page_url(False, 'legendary')}) and [Mejores pasivas]({_page_url(False, 'passives')}), and per-type pages: {_type_links(False)}.
- [Source repository](https://github.com/felipebasurto/survivortiers): the generator that builds these files.
- [Game repository](https://github.com/JPTER78/pokesurvivor): PokéSurvivor. The site is updated to commit {legal.UPDATED_COMMIT}, the {EN.date(legal.UPDATED_DATE)} patch.
"""


def _tier_table(meta: dict) -> list[str]:
    stab = {s["tier"]: s for s in meta["stability"]}
    rows = ["| Tier | Ranks | Pokémon | Firm Pokémon (≥ 80 % of repeats in this tier) | Median width of the p10–p90 rank range |",
            "| --- | --- | --- | --- | --- |"]
    for cut in meta["tierCuts"]:
        t = cut["tier"]
        s = stab[t]
        rows.append(f"| {t} | {cut['from']}–{cut['to']} | {meta['tierCounts'][t]} | {s['firm']} % | {s['bandWidth']} |")
    return rows


def llms_full_txt(meta: dict) -> str:
    u = legal.SITE_URL
    m = meta["method"]
    score = m["score"]
    sim_lo, sim_hi = meta["simRange"]
    counts = legal.method_counts(EN, meta)
    lines = [
        f"# {legal.SITE_NAME}: full data dictionary and method",
        "",
        f"Base URL: {u}",
        f"Generated: {meta['generatedAt']}. Ranking version: {meta['version']}. {legal.freshness_text(EN)}. Combat fields (pa, sa, df, sd) come from game commit {legal.COMBAT_COMMIT}.",
        "Language of values: `name` is Spanish (the game's names), `nameEn` and `*En` fields are English.",
        "",
        "## What the ranking is",
        "",
        f"A fan-made ranking of the {meta['total']} Pokémon of {legal.GAME_NAME}. Rank 1 is the best. Tiers are fixed-size bands of ranks (table below). It is a model of how well each Pokémon does in the game as the fan site built it, not an official tier list and not a balance statement from the game's author.",
        "",
        "## Tiers",
        "",
        *_tier_table(meta),
        "",
        f"Firmness: the share of the {m['repeats']} repeats in which a Pokémon lands in its own tier. A tier is firm when that share is at least {meta['firmShare']} %.",
        "",
        "## How the rank is built",
        "",
        f"1. Simulate. A bot plays full games of {legal.GAME_NAME} with each Pokémon in a simulator that follows the game's code (Rust engine, with a JavaScript twin that matches it in its basic mode). The bot circles the horde inside pickup range so shots, melee hits and orbs connect, dodges telegraphed attacks and collects orbs. Each Pokémon plays {counts['sims']} games with different seeds, capped at {score['capSeconds']} s. Bonds arrive when a rift legendary is beaten, not at t=0; bosses, heal orbs and every attack kind are modelled. The opening measure is the Repertoire opening (a random second non-buff attack, with Veto bans). Simulated seconds on the site run from {sim_lo:.0f} s to {sim_hi:.0f} s, median {meta['simMedianSeconds']} s; all of them are simulated.",
        f"2. Score. A game is worth time alive × sqrt(saturated damage rate × saturated kill rate). The damage rate is dps / (dps + {score['dpsRef']}) and the kill rate is kpm / (kpm + {score['kpmRef']}), so about {score['dpsRef']} damage per second or {score['kpmRef']} kills per minute is halfway to saturated. A game that deals no damage scores 0. The score of a Pokémon is the median over its games, with a bootstrap interval.",
        "3. Best move. Every move the Pokémon can learn is tried as the starting attack. The best move is the best attacking move (buffs and moves that deal nothing do not count). If intervals overlap, ties go to longer survival, then kills, then move id. The move group follows the owner's build rules: Swords Dance for a physical lead and Nasty Plot for a special lead (a mixed group follows the lead attack's side), a fourth slot of Harden or a third attack (whichever scores higher), and Gengar never keeps a melee move.",
        f"4. Repeat. {m['repeats']} repeats (seed 20261014) draw each Pokémon's score uniformly inside its interval and sort all {meta['total']}. Overlapping intervals are ties. Final rank = median of the {m['repeats']} resulting ranks; rank_p10 and rank_p90 are the 10th and 90th percentile of those ranks.",
        f"5. Tiers are filled in order of final rank, with fixed sizes and no entry requirements. melee_locked is reported only. No stats, move, type or size sheet moves the rank: only the simulator counts.",
        "6. Checks. The engine is compared against the game's own JavaScript (damage formulas, single-type bonus, combat scenes, vendored game source), and the Rust and JavaScript engines are compared with each other. Code, data and tests are in the repository.",
        "7. Flags (bit values in `species.json` `d[7]`): 1 = an attack applies a status this sim pass does not reproduce (burn, poison, slow, Hex and the extra attack kinds are simulated; confusion is not a game status and is ignored); 2 = still melee on every Repertoire draw (melee_locked); 4 and 8 (stats cap, fewer than three attack types) are legacy values from the old sheet gates and no longer change a tier.",
        "",
        "## Files",
        "",
        "### data/ranking.csv",
        "",
        "One row per Pokémon, sorted by rank. Columns ending in `_s` are seconds, `pct_*` and `p_*` columns are 0–1 fractions, the rest are ranks, ids or 0/1 flags:",
        "",
        "- rank, dex, name (English), tier: final rank 1–966, national Pokédex number, English name, tier.",
        "- rank_p10, rank_p90: 10th and 90th percentile of the rank over the repeats. p_tier: share of repeats in the tier. p_S: share of repeats in S.",
        "- start_move, start_kind, start_median_s: starting attack id, its kind (melee, projectile, beam, nova, ...), and the simulated Repertoire + Veto opening in seconds (expected value, not the starter alone).",
        "- best_move, best_median_s: best attack the bot can learn and its median simulated survival; equal to the starting attack when no better one exists.",
        "- rank_sim_start, rank_sim_best: rank of the Repertoire opening and of the best move by simulated score. The other rank columns (rank_v4_max, rank_v4_fresh, rank_sheet, rank_early, rank_late, phase_gap, pct_*) are kept for old readers and do not move the published rank.",
        "- pct_stats, pct_moves, pct_typedef, pct_size: sheet percentiles (0–1), informational only.",
        "- move_pair: the two attacks used for the coverage trio in the sheet.",
        "- shot_dmg_taken, radius, map_reach: model inputs (damage taken from an enemy shot, body radius, reach on the map).",
        "- status_unmodelled, melee_start: flags as 0/1. melee_start is 1 when the game starter is melee. attack_types: distinct types among the attacks the species can learn.",
        "- start_noshop_s, rank_sim_noshop: simulated survival and rank with the starter alone, no Repertoire and no Veto. Not weighted.",
        "- melee_locked: 1 when every remaining Repertoire draw still plays a melee move. Reported only; it does not move the rank or the tier.",
        "- repertoire_bans: up to three move ids the opening bans, separated by `|`.",
        "",
        "### data/pokemon-index.json",
        "",
        "Array of 966 objects, sorted by dex. Fields:",
        "",
        "- dex: national Pokédex number. name / nameEn: Spanish and English names. types: type keys, e.g. `[\"grass\",\"poison\"]`.",
        "- rarity: gacha star rating 1–5. legendary: boolean. bannerId: gacha banner 1–9 (1 Kanto … 9 Paldea).",
        "- sh: boolean, true if the species can be shiny in the game (it has a shiny sprite in the game's sprite data).",
        "- w, h: sprite size in pixels.",
        "- r: `[rank, tier, p10, p90, firm]`. firm is the percentage of repeats in the tier (0–100, not a fraction).",
        "- side: `phys`, `spec`, or `mix`, from the attacks in the best simulated group (the group the sheet shows, taken from `group_search.csv`). Mixed when that group has both a physical and a special attack. Each attack's damage class comes from the ported game move data. The ranking filter uses this field.",
        "- v: sort values. atk (in-game attack multiplier), hp, spd (speed), ehp (effective HP), rad (body radius) come from the game's Pokédex export. td (type defence), mv (moves), st (stats) are 0–100 percentile scores where 100 is best.",
        "- v.pa, v.sa: physical and special attack multipliers (damage of its physical / special moves; atk is the larger of the two). v.df, v.sd: base Defence and Special Defence. Taken from js/data/pokedex.js of the game at commit 5a23d49.",
        "- v.ak: the stronger side from base stats, `phys`, `spec`, or `mix` (mix when pa and sa differ by 0.05 or less). Kept for compatibility. It is not the group's attack mix: use `side` for that.",
        "",
        "### data/species.json",
        "",
        "Object with three keys:",
        "",
        f"- sim: `[lo, hi, median]`, the seconds scale and the median of the Repertoire opening (simulated seconds). Here: {sim_lo:.0f}, {sim_hi:.0f}, {meta['simMedianSeconds']}.",
        "- statMedian: median of each base stat across the 966 species, in order HP, Attack, Defence, Sp. Atk, Sp. Def, Speed.",
        "- d: object keyed by dex (string). Each value is an array:",
        "  - d[0]: `[stats, moves, typedef, size]` percentiles 0–1.",
        "  - d[1]: `[sheet, simStart, simBest, lateMax, lateFresh]` ranks.",
        "  - d[2], d[3]: starting attack id and the simulated Repertoire opening in seconds.",
        "  - d[4], d[5]: best attack id and its median simulated survival seconds.",
        "  - d[6]: `[move, move]`, the two attacks of the coverage pair.",
        "  - d[7]: flags bitmask (see flags above).",
        "  - d[8]: official base stats `[HP, Attack, Defence, Sp. Atk, Sp. Def, Speed]`.",
        "  - d[9]: fixed group `[super %, neutral %, move ids, attack types 1–2, optional move ids, number of boosts]`. Move ids are the attacks (two or three, either category; the first leads the group) followed by the boosts the group search picked (Swords Dance, Dragon Dance or Nasty Plot, and/or Harden or Agility). super % = share of the 966 species that the attacks hit super effectively (multiplier above 1.05). neutral % = share they never resist (multiplier at least 0.95).",
        "  - d[10]: level-up cards by priority `[8 card ids, best first, gate card id or null]` (atk, spd, hp, cd, def, rgn, mag, xp). The order is the fixed-group sim's coin ranking for this Pokémon. The gate is the card the lead attack needs to evolve: take it once, wherever it sits in the order. Estimate.",
        "  - d[11]: simulated seconds with the starter alone, no Repertoire and no Veto.",
        "- builds: object keyed by dex (string), with `melee` and/or `ranged`. A missing key means no build of that kind meets the rules. Each build: `moves` (attacks, then boosts), `nBoost` (how many of the last ids are boosts), `time` (median simulated seconds survived), `dealt` (median damage), `kills` (median kills), `score` (median score, the value the build is picked by), `cards` (`[8 card ids best first, gate card id or null]`, as d[10]). The class boost is Swords Dance for a physical attacker (physical attack above special) and Nasty Plot for a special one (ties count as special). Quick Attack, Tackle and Body Slam are never used. A melee build has at least one attack of kind melee; a ranged build has none.",
        "",
        "### data/moves.json",
        "",
        "Array of every attack in the game (no boosts). Fields:",
        "",
        "- id: move id (kebab-case, English name). name: Spanish name. en: `{name, evolvesTo, needsCard}` in English.",
        "- category: Spanish label: `cuerpo a cuerpo` for the melee kind (the only kind the game treats apart: +20 % damage and range, and 25 % less damage taken while it is in the active slot), `distancia` for every other attack.",
        "- tier and rank: move tier (S–C) and position within its category. score: the move's effect on the solo sim score with the species factored out (1 is the median attack, higher is better).",
        "- type: type key. kind: attack shape as the game names it in js/data/moves.js.",
        "- evolvesTo / needsCard: level-up card mechanics (a move that evolves into another, and the boost card it needs), or null.",
        "- mech: game parameters: `homing` (follows targets), `pierce` (goes through enemies), `count` (number of projectiles).",
        "- damage: `physical` or `special`. Physical is the game's fixed list (js/data/moves.js at 5a23d49); the rest are special.",
        "",
        "### data/moves_unranked.json",
        "",
        "The six boosts, with no tier or score: the tier list ranks attacks. Same id, name, en, type, kind and damage (`status`) fields, plus `buff`: `stat` (patk, satk, spd, def, regen), `amount` per stack, `stacks`, `dur` and `cd` at level 1, `cover` (percent of the time it can be up), and `max` with the same numbers at the top level with every upgrade. `note` is an `{es, en}` text for the attack boosts, or absent.",
        "",
        "### data/gachas.json",
        "",
        "Array of nine banners: gen, name, poolSize, legendaryCount, tiers (Pokémon per tier), sCount, aCount, sPlusARate (percent of the pool in S or A), pullChance (percent chance that a single pull is S or A, ignoring pity guarantees).",
        "",
        "### data/meta.json",
        "",
        "Version, generation time, game commit, tier cut-offs, tier counts, stability per tier, the method constants (`method`: score references, repeats, tiers), the seconds scale, the number of species capped by stats, sprite credits and sprite licence.",
        "",
        "## Query pages",
        "",
        "Lists built from the same data as the tier list, one per question. Each page repeats its list as an ItemList in JSON-LD. English paths; the Spanish path is the same page under `/`.",
        "",
        *[f"- {p.key}: {u}/en/{p.en} (ES: {u}/{p.es})" for p in landing.pages()],
        "",
        "## Sprites",
        "",
        f"Sprites are not in the data files. They are served as WebP from jsDelivr: `https://cdn.jsdelivr.net/gh/felipebasurto/survivortiers@main/sprites/<dex>.webp`. Each one is credited to its artist; the list is in `data/meta.json` (`credits`) and on the About page. Licence: {meta['spriteLicense']['name']} ({meta['spriteLicense']['url']}), from {meta['spriteLicense']['source']} ({meta['spriteLicense']['sourceUrl']}). Non-commercial use with attribution only.",
        "",
        "## Examples",
        "",
        "```sh",
        f"curl -s {u}/data/pokemon-index.json | jq -r '.[] | select(.r[1] == \"S\") | .name'   # the 30 S tier names",
        f"curl -s {u}/data/ranking.csv | python3 -c \"import csv,sys; rows=list(csv.DictReader(sys.stdin)); print(sorted(rows, key=lambda r: float(r['start_median_s']))[-1]['name'])\"   # best starting-attack survival",
        f"curl -s {u}/data/gachas.json | jq -r '.[] | \"\\(.name): \\(.sPlusARate) % S or A\"'",
        "```",
        "",
        "## Caveats",
        "",
        "- Tiers are a model with stated assumptions. The sim is a bot, not a person (it plays melee worse); rift walks, bonds, bosses and heal orbs are estimates, and confusion is not modelled. Read the flags before trusting a single Pokémon.",
        "- The game changes. The site states the patch it is updated to (see `llms.txt`); compare it with the game you care about.",
        "- Fan site, not official. Pokémon and its names are trademarks of their owners.",
        "",
    ]
    return "\n".join(lines)


# Rastreadores de buscadores y de asistentes de IA a los que se permite todo de forma explícita.
ALLOWED_BOTS = ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "ClaudeBot", "Google-Extended", "Bingbot")


def robots_txt() -> str:
    groups = "".join(f"User-agent: {bot}\nAllow: /\n\n" for bot in ALLOWED_BOTS)
    return f"User-agent: *\nAllow: /\n\n{groups}Sitemap: {legal.SITE_URL}/sitemap.xml\n"


def sitemap_xml(meta: dict, sheets: list[str] | None = None, landing_pairs: list[tuple[str, str]] | None = None) -> str:
    """Una entrada por página y por idioma, cada una con sus alternativas hreflang (es, en) y x-default (es).
    Las rutas son sin prefijo de idioma: sheets como pokemon/150-mewtwo/ y landing_pairs como (es, en) de cada
    página de consulta, con barra final. Las páginas fijas del menú comparten nombre en los dos idiomas."""
    lastmod = meta["generatedAt"][:10]
    pairs = [(p, p) for p in [*PAGES, *(sheets or [])]] + list(landing_pairs or []) + toolpages.pairs()
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for es_path, en_path in pairs:
        alts = (f'<xhtml:link rel="alternate" hreflang="es" href="{_url(es_path)}"/>'
                f'<xhtml:link rel="alternate" hreflang="en" href="{_url(LANG_PREFIX["en"] + en_path)}"/>'
                f'<xhtml:link rel="alternate" hreflang="x-default" href="{_url(es_path)}"/>')
        out.append(f"  <url><loc>{_url(es_path)}</loc><lastmod>{lastmod}</lastmod>{alts}</url>")
        out.append(f"  <url><loc>{_url(LANG_PREFIX['en'] + en_path)}</loc><lastmod>{lastmod}</lastmod>{alts}</url>")
    out.append("</urlset>")
    return "\n".join(out) + "\n"


def landing_pairs() -> list[tuple[str, str]]:
    return [(p.es, p.en) for p in landing.pages()]


def write_all(site: Path, meta: dict, gachas: list[dict], index: list[dict], sheets: list[str] | None = None) -> int:
    """Escribe los archivos para agentes en site/ y devuelve cuántos son."""
    data = site / "data"
    data.mkdir(parents=True, exist_ok=True)
    files = {
        site / "llms.txt": llms_txt(meta, index),
        site / "llms-full.txt": llms_full_txt(meta),
        site / "robots.txt": robots_txt(),
        site / "sitemap.xml": sitemap_xml(meta, sheets, landing_pairs()),
        data / "ranking.csv": _ranking_csv(),
        data / "meta.json": json.dumps(meta, ensure_ascii=False, indent=1) + "\n",
        data / "gachas.json": json.dumps(gachas, ensure_ascii=False, separators=(",", ":")) + "\n",
    }
    for path, text in files.items():
        path.write_text(text, encoding="utf8")
    return len(files)
