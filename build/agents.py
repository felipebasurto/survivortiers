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
from i18n import EN, ES, TYPE_NAMES, Lang

ROOT = Path(__file__).resolve().parent.parent
RANKING_SRC = ROOT / "data" / "ranking_definitive.csv"
PAGES = ["", "ataques.html", "objetos.html", "pasivas.html", "gachas.html", "coleccion.html", "metodo.html", "acerca.html"]
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


def _weight(meta: dict, key: str) -> int:
    return next(p["weight"] for p in meta["method"]["pieces"] if p["key"] == key)


def _page_url(en: bool, key: str) -> str:
    return landing.url(EN if en else ES, landing.page_for(key))


def _type_links(en: bool) -> str:
    names = TYPE_NAMES["en" if en else "es"]
    return ", ".join(f"[{names[t]}]({_page_url(en, f'type:{t}')})" for t in landing.TYPE_KEYS)


def llms_txt(meta: dict) -> str:
    u = legal.SITE_URL
    counts = legal.method_counts(EN, meta)
    es_counts = legal.method_counts(ES, meta)
    pieces = (f"sheet percentiles of stats, moves, type defence and size ({_weight(meta, 'sheet')} %), "
              f"the simulation ({_weight(meta, 'sim')} %) and a late-game formula ({_weight(meta, 'late')} %)")
    return f"""# {legal.SITE_NAME}

> Unofficial fan tier list for {legal.GAME_NAME}, a survivor-style Pokémon game by {legal.GAME_AUTHOR}. It ranks all {meta['total']} Pokémon in five tiers (S, A, B, C, D). The rank is built by simulating runs: a bot plays {counts['sims']} simulated games per Pokémon, combined with {pieces}. The whole calculation is repeated {counts['reps']} times and the median rank is published. The code, the simulator and the data are open source on GitHub. It is not official and not affiliated with Nintendo, Creatures, GAME FREAK, The Pokémon Company or the game's author.

Resumen en español: tier list no oficial de {legal.GAME_NAME}. Los {meta['total']} Pokémon en tiers S a D, con un ranking hecho simulando {es_counts['sims']} partidas por Pokémon y repitiendo el cálculo {es_counts['reps']} veces. Código y datos abiertos en GitHub.

The site is static. Pages are in Spanish at `/` and in English at `/en/`. There is no API key, login or rate limit. Each Pokémon has its own HTML page, for example [Mewtwo]({u}/en/pokemon/150-mewtwo/). Field definitions, units and the method are in [llms-full.txt]({u}/llms-full.txt). The data files below are the best source for tables.

Base URL: {u}

## Data

- [Ranking (CSV)]({u}/data/ranking.csv): one row per Pokémon with rank, tier, rank range, method ranks and model columns. Best starting point for tables and analysis.
- [Pokémon index (JSON)]({u}/data/pokemon-index.json): all {meta['total']} Pokémon with rank, tier, rank range and sort values.
- [Species details (JSON)]({u}/data/species.json): per-Pokémon sheet data (starting and best move, simulated survival, move pair, coverage trio, official base stats).
- [Moves (JSON)]({u}/data/moves.json): the 64 attacks and boosts, with tier, type, kind and game parameters.
- [Gacha banners (JSON)]({u}/data/gachas.json): the nine banners, pool sizes, S and A rates and the chance of an S or A pull.
- [Method and metadata (JSON)]({u}/data/meta.json): tier cut-offs, weights, gates, stability and method agreement numbers.

## Docs

- [Full data dictionary, units and method]({u}/llms-full.txt): every field and rule, with examples.

## Pages

- [Tier list (EN)]({u}/en/): all Pokémon by tier, with search and sorting.
- [Best Pokémon (EN)]({_page_url(True, 'best')}): the top 30, tier S, in order.
- [Best starters (EN)]({_page_url(True, 'starters')}): the starting picks that last longest in the simulated opening.
- [Best legendaries (EN)]({_page_url(True, 'legendary')}): every legendary by rank.
- [Best passives (EN)]({_page_url(True, 'passives')}): level-up cards ranked by coin reward, with the Sitrus Berry rule.
- Best Pokémon by type (EN), one page per type: {_type_links(True)}.
- [Moves (EN)]({u}/en/ataques): attack tier list.
- [Items (EN)]({u}/en/objetos): item tier list.
- [Gacha (EN)]({u}/en/gachas): banners and pull odds.
- [Collection (EN)]({u}/en/coleccion): collection helper.
- [Method (EN)]({u}/en/metodo): how the ranking is built, with the numbers.
- [About (EN)]({u}/en/acerca): fan-site notice, sprite credits and licences.
- [Sitemap]({u}/sitemap.xml)

## Optional

- [Tier list (ES)]({u}/): the same site in Spanish, with [Mejores Pokémon]({_page_url(False, 'best')}), [Mejores iniciales]({_page_url(False, 'starters')}), [Mejores legendarios]({_page_url(False, 'legendary')}) and [Mejores pasivas]({_page_url(False, 'passives')}), and per-type pages: {_type_links(False)}.
- [Source repository](https://github.com/felipebasurto/survivortiers): the generator that builds these files.
- [Game repository](https://github.com/JPTER78/pokesurvivor): PokéSurvivor, at commit {meta['gameCommit']}, the commit the data was built from.
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
    pieces = ", ".join(f"{p['key']} {p['weight']} %" for p in m["pieces"])
    pillars = ", ".join(f"{p['key']} {p['weight']} %" for p in m["pillars"])
    gates = "; ".join(f"{g['tier']} needs the top {g['top']} % on stats" for g in m["gates"])
    types_min = "; ".join(f"{t} needs attacks of at least {n} different types" for t, n in m["typesMin"].items())
    no_melee = ", ".join(m["noMeleeTiers"])
    sim_lo, sim_hi = meta["simRange"]
    agree = ", ".join(f"{a['key']} {a['corr']}" for a in meta["agreement"])
    lines = [
        f"# {legal.SITE_NAME}: full data dictionary and method",
        "",
        f"Base URL: {u}",
        f"Generated: {meta['generatedAt']}. Ranking version: {meta['version']}. Game commit the data was built from: {meta['gameCommit']}.",
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
        f"1. Three pieces, each a rank: {pieces}.",
        f"   - sheet: a species score from percentiles of four pillars ({pillars}). Stats are the base stats, moves are the attacks it can learn, type defence is how it takes type-based damage, size is its hitbox.",
        f"   - sim: a bot plays one fixed group (starting attack, one more attack, Swords Dance and Harden). Bonds arrive when a rift legendary is beaten, not at t=0; bosses, heal orbs and every attack kind are modelled. Up to {SIM_CAP_S} s. It is an estimate: the bot does not dodge. The opening measure is the expected survival with Repertoire (a random second non-buff attack) and Veto (ban the 3 pool moves that pull that expectation down), playing the better of the two. The best-move measure is the best attack it can learn, played alone. Median seconds give the rank. The starter with no shop is start_noshop_s and is not weighted. Seconds scale used on the site: {sim_lo:.0f} s to {sim_hi:.0f} s, median {meta['simMedianSeconds']} s. All of these seconds are simulated.",
        "   - late: a late-game formula (v4) in two variants: all shop stat upgrades maxed, and no shop upgrades. This is not the Repertoire opening.",
        f"2. Repeats: {m['repeats']} runs of the whole method. Each one shifts the data within its error margin, changes the weight between the sim and late-game pieces, and uses one of 80 assumptions of the late-game model. Final rank = median of the {m['repeats']} resulting ranks.",
        f"3. Tiers are filled in order of final rank, with fixed sizes. A Pokémon that misses a gate is skipped and waits for the next tier it qualifies for. Gates: {gates}; {types_min}; a Pokémon that still plays a melee move on every Repertoire draw (melee_locked) stays out of {no_melee}.",
        f"4. Agreement: rank correlation of each piece with the final rank: {agree}.",
        f"5. Flags (bit values in `species.json` `d[7]`): 1 = an attack applies a status this sim pass does not reproduce; burn, poison, slow, Hex and the extra attack kinds are simulated; confusion is not a game status and is ignored; 2 = still melee on every Repertoire draw; 4 = stats kept it out of its tier; 8 = fewer than three attack types kept it out of S.",
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
        "- rank_sim_start, rank_sim_best, rank_v4_max, rank_v4_fresh, rank_sheet: the rank of each single piece. rank_sim_start ranks the Repertoire opening. rank_early combines that rank with rank_sim_best; rank_late combines the two late-game ranks. phase_gap = rank_late − rank_early (positive means better late than early).",
        "- pct_stats, pct_moves, pct_typedef, pct_size: pillar percentiles (0–1).",
        "- move_pair: the two attacks used for the coverage trio in the sheet.",
        "- shot_dmg_taken, radius, map_reach: model inputs (damage taken from an enemy shot, body radius, reach on the map).",
        "- stats_capped, types_capped, status_unmodelled, melee_start: flags as 0/1. melee_start is 1 when the game starter is melee. attack_types: distinct types among the attacks the species can learn.",
        "- start_noshop_s, rank_sim_noshop: simulated survival and rank with the starter alone, no Repertoire and no Veto. Not weighted.",
        "- melee_locked: 1 when every remaining Repertoire draw still plays a melee move. That is the S-tier melee gate.",
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
        "- v: sort values. atk (in-game attack multiplier), hp, spd (speed), ehp (effective HP), rad (body radius) come from the game's Pokédex export. td (type defence), mv (moves), st (stats) are 0–100 percentile scores where 100 is best.",
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
        "  - d[9]: fixed group `[super %, neutral %, move ids, attack types 1–2, optional move ids, number of boosts]`. Move ids are the two attacks (the first is the best fixed-group simulated attack) followed by the boosts (Dragon Dance or Swords Dance, and Harden). super % = share of the 966 species that the attacks hit super effectively (multiplier above 1.05). neutral % = share they never resist (multiplier at least 0.95).",
        "  - d[10]: cards the sim takes over a run `[card ids, n]` (atk, spd, hp, cd, def, rgn, mag, xp). The first n are taken once to evolve the lead attack and then not again; the last id is the stat the policy keeps stacking (the coin-best fill). A companion's evolution card is listed only when that stat is the fill. Estimate.",
        "  - d[11]: simulated seconds with the starter alone, no Repertoire and no Veto.",
        "",
        "### data/moves.json",
        "",
        "Array of 64 attacks and boosts. Fields:",
        "",
        "- id: move id (kebab-case, English name). name: Spanish name. en: `{name, evolvesTo, needsCard}` in English.",
        "- category: Spanish label, one of `cuerpo a cuerpo` (melee), `distancia` (ranged), `estadística` (boost).",
        "- tier and rank: move tier (S–D) and position in the move list. score: relative score from the move tier list (higher is better), for moves that have one.",
        "- type: type key. kind: attack shape (melee, projectile, beam, nova, aura, orbit, boomerang, mine, meteor, dash, cone, chain, trail, turret, or buff).",
        "- evolvesTo / needsCard: level-up card mechanics (a move that evolves into another, and the boost card it needs), or null.",
        "- mech: game parameters: `homing` (follows targets), `pierce` (goes through enemies), `count` (number of projectiles).",
        "",
        "### data/gachas.json",
        "",
        "Array of nine banners: gen, name, poolSize, legendaryCount, tiers (Pokémon per tier), sCount, aCount, sPlusARate (percent of the pool in S or A), pullChance (percent chance that a single pull is S or A, ignoring pity guarantees).",
        "",
        "### data/meta.json",
        "",
        "Version, generation time, game commit, tier cut-offs, tier counts, stability per tier, the method weights and gates (`method`), method agreement, the seconds scale, the number of species capped by stats, sprite credits and sprite licence.",
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
        "- Tiers are a model with stated assumptions. The sim is a bot that does not dodge; rift bonds, bosses and heal orbs are estimates, and confusion is not modelled. Read the flags before trusting a single Pokémon.",
        "- The game changes. Check `gameCommit` in `data/meta.json` against the game you care about.",
        "- Fan site, not official. Pokémon and its names are trademarks of their owners.",
        "",
    ]
    return "\n".join(lines)


def robots_txt() -> str:
    return f"User-agent: *\nAllow: /\n\nSitemap: {legal.SITE_URL}/sitemap.xml\n"


def sitemap_xml(meta: dict, sheets: list[str] | None = None, landing_pairs: list[tuple[str, str]] | None = None) -> str:
    """Una entrada por página y por idioma, cada una con sus alternativas hreflang (es, en) y x-default (es).
    Las rutas son sin prefijo de idioma: sheets como pokemon/150-mewtwo/ y landing_pairs como (es, en) de cada
    página de consulta, con barra final. Las páginas fijas del menú comparten nombre en los dos idiomas."""
    lastmod = meta["generatedAt"][:10]
    pairs = [(p, p) for p in [*PAGES, *(sheets or [])]] + list(landing_pairs or [])
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


def write_all(site: Path, meta: dict, gachas: list[dict], sheets: list[str] | None = None) -> int:
    """Escribe los archivos para agentes en site/ y devuelve cuántos son."""
    data = site / "data"
    data.mkdir(parents=True, exist_ok=True)
    files = {
        site / "llms.txt": llms_txt(meta),
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
