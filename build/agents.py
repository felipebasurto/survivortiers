"""Lo que necesita un agente de IA (o un buscador) para usar el sitio sin leer el HTML:

- llms.txt: índice del sitio y de los datos, con enlaces absolutos (formato de llmstxt.org).
- llms-full.txt: diccionario de datos, unidades, método y ejemplos. Es la explicación que hace falta para usar bien los JSON.
- robots.txt y sitemap.xml: las páginas en los dos idiomas, incluidas las fichas estáticas /pokemon/<n>-<nombre>/.
- data/ranking.csv, data/meta.json y data/gachas.json: los datos que se describen (el CSV es data/ranking_fase3.csv
  tal cual sale de species_builds.py, sin la línea de comentario).
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
RANKING_SRC = ROOT / "data" / "ranking_fase3.csv"
PAGES = ["", "novedades.html", "ataques.html", "objetos.html", "pasivas.html", "habilidades.html", "naturalezas.html", "tipos.html", "coleccion.html", "metodo.html", "acerca.html"]
LANG_PREFIX = {"es": "", "en": "en/"}


def _url(rel: str) -> str:
    """URL absoluta de una página o archivo. Las páginas van sin .html: Workers y Pages redirigen las .html (307/308)."""
    if rel.endswith(".html") and rel != "404.html":
        rel = rel[: -len(".html")]
    return f"{legal.SITE_URL}/{rel}"


def _ranking_csv() -> str:
    """El CSV de species_builds.py sin las líneas de comentario de arriba (cada línea empieza por '#')."""
    lines = RANKING_SRC.read_text(encoding="utf8").splitlines(keepends=True)
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    return "".join(lines)


def dataset_jsonld(L: Lang, meta: dict) -> str:
    """JSON-LD schema.org Dataset para la portada de cada idioma. No nombra al autor del sitio."""
    base = _url("en/" if L.en else "")
    files = [("text/csv", "data/ranking.csv", "Ranking (CSV)"),
             ("application/json", "data/pokemon-index.json", "Pokémon index (JSON)"),
             ("application/json", "data/species.json", "Builds per Pokémon (JSON)"),
             ("application/json", "data/moves.json", "Moves (JSON)"),
             ("application/json", "data/gachas.json", "Gachas (JSON)"),
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


def _method_line(meta: dict) -> str:
    m = meta["method"]
    return (f"The rank comes only from simulated runs: {EN.num(m['games'])} runs of a bot using the game's code in the "
            f"bounded ranking (bounded-ranking-v2: moves, ability and nature searched per Pokémon and style). Each Pokémon "
            f"is ranked by the median survival seconds of its best 4-move no-TM build (no Tackle, Quick Attack or Body Slam unless Normal type). TM builds are "
            f"published but do not count for the rank. No hand-written rules.")


def llms_txt(meta: dict, index: list[dict]) -> str:
    u = legal.SITE_URL
    fresh = f"{legal.freshness_text(EN)}; site rebuilt on {EN.date(meta['generatedAt'][:10])}"
    fresh_es = f"{legal.freshness_text(ES)}; sitio reconstruido el {ES.date(meta['generatedAt'][:10])}"
    top_en, top_es = seo.top_names(EN, index), seo.top_names(ES, index)
    games_es = ES.num(meta["method"]["games"])
    return f"""# {legal.SITE_NAME}

> Unofficial fan tier list for {legal.GAME_NAME}, a survivor-style Pokémon game by {legal.GAME_AUTHOR}. It ranks all {meta['total']} Pokémon in five tiers (S, A, B, C, D). {fresh}. Best five right now: {top_en}. {_method_line(meta)} The code, the simulator and the data are open source on GitHub. It is not official and not affiliated with Nintendo, Creatures, GAME FREAK, The Pokémon Company or the game's author.

Resumen en español: tier list no oficial de {legal.GAME_NAME}. Los {meta['total']} Pokémon en tiers S a D. {fresh_es}. Los cinco mejores ahora: {top_es}. El ranking sale solo de {games_es} partidas simuladas con el código del juego: cada Pokémon se ordena por su mejor build. Código y datos abiertos en GitHub.

The site is static. Pages are in Spanish at `/` and in English at `/en/`. There is no API key, login or rate limit. Each Pokémon has its own HTML page, for example [Mewtwo]({u}/en/pokemon/150-mewtwo/). Field definitions, units and the method are in [llms-full.txt]({u}/llms-full.txt). The data files below are the best source for tables.

Base URL: {u}

## Data

- [Ranking (CSV)]({u}/data/ranking.csv): one row per Pokémon with rank, tier, best build, its score and interval, and survival seconds.
- [Pokémon index (JSON)]({u}/data/pokemon-index.json): all {meta['total']} Pokémon with rank, tier and sort values.
- [Builds per Pokémon (JSON)]({u}/data/species.json): the best melee and the best ranged build of each Pokémon, with their medians.
- [Moves (JSON)]({u}/data/moves.json): every attack, with its phase 1 tier, type, kind and game parameters. The six boosts are in [moves_unranked.json]({u}/data/moves_unranked.json).
- [Gachas (JSON)]({u}/data/gachas.json): the nine gachas, pool sizes, S and A rates and the chance of an S or A pull.
- [Method and metadata (JSON)]({u}/data/meta.json): tier cut-offs, tier counts, survival times, run counts per phase and the weights behind each page's "why".

## Docs

- [Full data dictionary, units and method]({u}/llms-full.txt): every field and rule, with examples.

## Pages

- [Tier list (EN)]({u}/en/): all Pokémon by tier, with search and sorting.
- [Best Pokémon (EN)]({_page_url(True, 'best')}): the top 30, tier S, in order.
- [Best legendaries (EN)]({_page_url(True, 'legendary')}): every legendary by rank.
- Best Pokémon by type (EN), one page per type: {_type_links(True)}.
- [Moves (EN)]({u}/en/ataques): phase 1 move tier list and the best phase 2 groups.
- [Items (EN)]({u}/en/objetos): what each item does, from the game code. Not ranked.
- [Abilities (EN)]({u}/en/habilidades): all 271 abilities with their exact in-game effect from the game code (js/data/ability-fx.js) and the species that have each one.
- [Passives (EN)]({u}/en/pasivas): the level-up cards, boosts and abilities as the game code defines them, plus the natures that raise each stat with their win counts in the bounded ranking.
- [Move types (EN)]({u}/en/tipos): how each move type hits the enemies that spawn, from the game's type chart, plus weather.
- [What's new (EN)]({u}/en/novedades): game updates and site changes.
- [Collection (EN)]({u}/en/coleccion): gachas, pull odds and your own collection.
- [Method (EN)]({u}/en/metodo): how the ranking is built, with the numbers.
- [About (EN)]({u}/en/acerca): fan-site notice, sprite credits and licences.
- [Type finder (EN)]({u}/en/type-finder/): pick one or two types and see which Pokémon have them, with their weaknesses.
- [Build planner (EN)]({u}/en/build-planner/): a Pokémon's bonded group, starting from its best simulated build, with a shareable link.
- [Sitemap]({u}/sitemap.xml)

## Optional

- [Tier list (ES)]({u}/): the same site in Spanish, with [Mejores Pokémon]({_page_url(False, 'best')}) and [Mejores legendarios]({_page_url(False, 'legendary')}), and per-type pages: {_type_links(False)}.
- [Source repository](https://github.com/felipebasurto/survivortiers): the generator that builds these files.
- [Game repository](https://github.com/JPTER78/pokesurvivor): PokéSurvivor. The site is updated to commit {legal.UPDATED_COMMIT}, the {EN.date(legal.UPDATED_DATE)} patch.
"""


def llms_full_txt(meta: dict) -> str:
    u = legal.SITE_URL
    m = meta["method"]
    p1, p2, p3 = m["p1"], m["p2"], m["p3"]
    t = meta["time"]
    weights = ", ".join(f"{k} {v:+.3f}" for k, v in meta["why"]["weights"].items())
    lines = [
        f"# {legal.SITE_NAME}: full data dictionary and method",
        "",
        f"Base URL: {u}",
        f"Generated: {meta['generatedAt']}. Ranking version: {meta['version']}. {legal.freshness_text(EN)}.",
        "Language of values: `name` is Spanish (the game's names), `nameEn` and `*En` fields are English.",
        "",
        "## What the ranking is",
        "",
        f"A fan-made ranking of the {meta['total']} Pokémon of {legal.GAME_NAME}. Rank 1 is the best. Tiers are fixed-size bands of ranks:",
        "",
        "| Tier | Ranks | Pokémon |",
        "| --- | --- | --- |",
        *[f"| {c['tier']} | {c['from']}–{c['to']} | {meta['tierCounts'][c['tier']]} |" for c in meta["tierCuts"]],
        "",
        "## How the rank is built",
        "",
        f"A bot plays runs of up to {m['seconds']} s in a simulator that follows the game's code (Rust engine checked against the game's JavaScript). Every move group is bonded from the start. The bot holds no item, there is no terrain or status conditions, and level-up cards follow a fixed priority, so the site does not rank items or cards. A run scores time alive × sqrt(dps / (dps + {EN.num(m['score']['dpsRef'])}) × kpm / (kpm + {EN.num(m['score']['kpmRef'])})), where dps is damage per second and kpm kills per minute; a run with no damage scores 0.",
        "",
        f"1. Moves. Each of the {p1['attacks']} attacks plays alone on {p1['refs']} reference Pokémon of its class (physical attackers for physical moves, special for special), {p1['seeds']} runs per reference ({EN.num(p1['games'])} runs). score = geometric mean over the references of the move's median score divided by the median of all moves of its class on that reference. 1.0 is a typical move of its class. Tiers within each class by position: S top 10 %, A next 20 %, B 30 %, C 25 %, D the rest.",
        f"2. Groups. The best moves are combined into four-slot groups (three attacks + an attack boost, three + a defence boost, or two + attack boost + defence boost), played by the same references. {EN.num(p2['groups'])} groups over three rounds of {p2['seeds'][0]}, {p2['seeds'][1]} and {p2['seeds'][2]} runs per reference with fresh seeds ({EN.num(p2['games'])} runs).",
        f"3. Builds (previous method, kept for reference). Each Pokémon tried its own groups (the moves it can learn). An additive model fitted on phase 2 preselects them: {EN.num(p3['groups'][0])} groups with {p3['seeds'][0]} runs, the best {EN.num(p3['groups'][1])} with {p3['seeds'][1]}, and the {EN.num(p3['groups'][2])} finalists with {p3['seeds'][2]}, each round with fresh seeds ({EN.num(p3['games'])} runs). Each Pokémon keeps its best melee build (at least one melee attack) and its best ranged build (none).",
        f"4. Rank (current). The rank no longer uses step 3: it comes from the bounded ranking (data/bounded_ranking.json, bounded-ranking-v2, 441,486 runs). Each Pokémon searched up to 12 groups per style with and without TMs, the neutral nature and four attack-raising natures, then confirmed the winner on 16 fresh seeds. The rank is the median survival seconds of the confirmed (16-run) no-TM build, the better of the two styles; 2- and 8-run builds do not count for the order. Builds shown on each page have 4 moves, Swords Dance or Nasty Plot (or Harden if it does better) and, except for Normal types, no Tackle, Quick Attack or Body Slam, preferring confirmed, then 8-run, then 2-run builds; if none passes, the best available build is shown. ranking.csv median_score and median_s hold that median, score_lo/score_hi the min/max of its runs. Survival across all Pokémon: median {t['median']} s, from {t['min']} s to {t['max']} s.",
        f"5. Why. Least squares over the {meta['total']} Pokémon of log(best build survival) on eight standardised factors (attack multiplier, group strength, HP, Defence, Sp. Def., speed, size, damage taken by type). R² {meta['why']['r2']}. Weights: {weights}. A factor's effect on a Pokémon is exp(weight × its standardised value) − 1, against an average Pokémon.",
        "",
        "## Files",
        "",
        "### data/ranking.csv",
        "",
        "One row per Pokémon, sorted by rank: rank, dex, name (Spanish), tier, build (`melee` or `ranged`, the one that ranks it), group (move ids joined by `+`, attacks first, the first one starts the run), median_score, score_lo and score_hi (min and max of the 16 confirmation runs), median_s (median seconds survived; the score is the same survival), other_build and other_score (the other build and its score).",
        "",
        "### data/pokemon-index.json",
        "",
        "Array of 966 objects, sorted by dex:",
        "",
        "- dex, name / nameEn, types, rarity (1–5), legendary, bannerId (1 Kanto … 9 Paldea), sh (can be shiny), bst (base stat total), w and h (sprite size).",
        "- r: `[rank, tier]`.",
        "- side: `phys`, `spec` or `mix`, from the attacks of the best build.",
        "- v: sort values. s (median seconds survived with the best build), pa and sa (physical and special attack multipliers), hp, spd, df, sd (game stats) and rad (collision radius in px).",
        "",
        "### data/species.json",
        "",
        "`builds`: object keyed by dex (string) with `melee`, `ranged` and `best` (which of the two ranks the Pokémon). Each build: `moves` (attacks then boosts; the first attack starts the run), `nBoost` (how many of the last ids are boosts), `mix` (physical, special or mixed attacks), `time` (median seconds), `kills`, `dealt` (median damage), `score` (median score) and `lo` / `hi` (its interval).",
        "",
        "### data/moves.json",
        "",
        "Array of every attack (no boosts): id, name (Spanish), en {name, evolvesTo, needsCard}, category (`physical` or `special`, the move's class), tier and rank within its class, score (phase 1, 1.0 = typical move of its class), type, kind (attack shape from js/data/moves.js), evolvesTo / needsCard, mech {homing, pierce, count} and damage.",
        "",
        "### data/moves_unranked.json",
        "",
        "The six boosts, with no tier: id, name, en, type, kind, damage (`status`) and `buff`: stat, amount per stack, stacks, dur and cd at level 1, cover, and `max` with every upgrade.",
        "",
        "### data/gachas.json",
        "",
        "Array of nine gachas (one per region): gen, name, poolSize, legendaryCount, tiers (Pokémon per tier), sCount, aCount, sPlusARate (percent of the pool in S or A), pullChance (percent chance that a single pull is S or A, ignoring pity guarantees).",
        "",
        "### data/meta.json",
        "",
        "Version, generation time, game commit, tier cut-offs and counts, `time` (survival median, min, max), `method` (runs per phase), `why` (R² and weights), sprite credits and sprite licence.",
        "",
        "## Query pages",
        "",
        "Lists built from the same data as the tier list. Each page repeats its list as an ItemList in JSON-LD. English paths; the Spanish path is the same page under `/`.",
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
        f"curl -s {u}/data/ranking.csv | python3 -c \"import csv,sys; rows=list(csv.DictReader(sys.stdin)); print(max(rows, key=lambda r: float(r['median_s']))['name'])\"   # longest survival",
        f"curl -s {u}/data/gachas.json | jq -r '.[] | \"\\(.name): \\(.sPlusARate) % S or A\"'",
        "```",
        "",
        "## Caveats",
        "",
        "- The sim is a bot, not a person. It holds no item and takes cards in a fixed order; statuses and terrain are off.",
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
