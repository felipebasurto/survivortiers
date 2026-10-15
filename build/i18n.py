"""Textos del sitio en español e inglés y formato de números por idioma.

Cada texto es una pareja (es, en) con los mismos marcadores {nombre}. Las claves que terminan en _html llevan HTML
y se insertan tal cual. El resto es texto plano y quien lo usa lo escapa. Al importar este módulo se comprueba que
las dos versiones de cada texto tienen los mismos marcadores.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

NBSP = "\u00a0"

STR: dict[str, tuple[str, str]] = {
    # ------------------------------------------------------------ base
    "skip": ("Saltar al contenido", "Skip to content"),
    "nav_main": ("Principal", "Main"),
    "nav_foot": ("Pie", "Footer"),
    "nav_tiers": ("Tiers", "Tiers"),
    "nav_metodo": ("Método", "Method"),
    "nav_ataques": ("Ataques", "Moves"),
    "nav_gachas": ("Gacha", "Gacha"),
    "nav_coleccion": ("Colección", "Collection"),
    "nav_acerca": ("Info", "About"),
    "lang_label": ("Idioma", "Language"),
    "sprites_line_html": (
        'Sprites: <a href="{url}" rel="noopener">{source}</a>, <a href="{lic_url}" rel="noopener">{lic}</a>. '
        '<a href="{about}#creditos">Artistas</a>.',
        'Sprites: <a href="{url}" rel="noopener">{source}</a>, <a href="{lic_url}" rel="noopener">{lic}</a>. '
        '<a href="{about}#creditos">Artists</a>.'),
    "disclaimer": (
        "Sitio de fans, no oficial y no afiliado a Nintendo, Creatures, GAME FREAK, The Pokémon Company ni {game}. "
        "Pokémon y sus nombres son marcas de sus dueños.",
        "Fan site, unofficial and not affiliated with Nintendo, Creatures, GAME FREAK, The Pokémon Company or {game}. "
        "Pokémon and its names are trademarks of their owners."),
    "tier": ("Tier {t}", "Tier {t}"),

    # ------------------------------------------------------------ portada
    "index_title": ("{site} · Tier list de {game}", "{site} · {game} tier list"),
    "index_desc": ("Tier list no oficial de los {n} Pokémon de {game}.",
                   "Unofficial tier list of the {n} Pokémon in {game}."),
    "index_h1": ("Tier list de {game}", "{game} tier list"),
    "search_label": ("Buscar", "Search"),
    "search_ph": ("Nombre, tipo o nº", "Name, type or no."),
    "unsure_key": ("Tier dudoso", "Shaky tier"),
    "noscript": ("El buscador necesita JavaScript.", "Search needs JavaScript."),
    "card_title": ("{name} · nº {dex} · puesto {rank} · tier {tier}{hint}",
                   "{name} · no. {dex} · rank {rank} · tier {tier}{hint}"),
    "card_hint": (" · dudoso", " · shaky"),

    # ------------------------------------------------------------ ficha
    "crumb_home": ("Tier list", "Tier list"),
    "legendary": ("Legendario", "Legendary"),
    "stars_alt": ("{n} de 5 estrellas", "{n} of 5 stars"),
    "sprite_alt": ("Sprite de {name}", "Sprite of {name}"),
    "ficha_title": ("{name} · tier {tier} · {site}", "{name} · tier {tier} · {site}"),
    "ficha_desc": ("{label}: tier {tier}, puesto {rank} de {total} en {game}.",
                   "{label}: tier {tier}, rank {rank} of {total} in {game}."),
    "flag_status": ("Usa estados que la simulación no modela", "Uses status effects the simulation does not model"),
    "flag_melee": ("Empieza con un ataque cuerpo a cuerpo, que el bot juega peor",
                   "Starts with a melee move, which the bot plays worse"),
    "flag_capped": ("Sus estadísticas le limitan el tier", "Its stats cap its tier"),
    "pager_aria": ("Pokémon vecinos", "Neighbouring Pokémon"),
    "dex_no": ("nº {dex}", "no. {dex}"),
    "banner_of": ("Banner {name}", "{name} banner"),
    "noscript_ficha": ("Esta página necesita JavaScript.", "This page needs JavaScript."),
    "f_missing": ("Pokémon no encontrado", "Pokémon not found"),

    # ------------------------------------------------------------ gráficos de la ficha
    "t_band": ("Puesto", "Rank"),
    "t_pillars": ("Puntos fuertes", "Strengths"),
    "t_methods": ("Cada medida", "Each measure"),
    "t_sim": ("Aguante", "Survival"),
    "band_rank": ("puesto {rank}", "rank {rank}"),
    "band_range": ("{lo} a {hi}", "{lo} to {hi}"),
    "band_alt": ("{name}: puesto {rank} de {total}, tier {tier}. Suele quedar entre el {lo} y el {hi}.",
                 "{name}: rank {rank} of {total}, tier {tier}. Usually lands between {lo} and {hi}."),
    "pill_stats": ("Estadísticas", "Stats"),
    "pill_moves": ("Ataques", "Moves"),
    "pill_typedef": ("Defensa de tipos", "Type defense"),
    "pill_size": ("Tamaño pequeño", "Small size"),
    "pillars_alt_item": ("{label}, mejor que el {v} % de los Pokémon", "{label}, better than {v}% of Pokémon"),
    "median": ("mediana", "median"),
    "m_sheet": ("Ficha", "Sheet"),
    "m_simStart": ("Partida, ataque inicial", "Game, starting move"),
    "m_simBest": ("Partida, mejor ataque", "Game, best move"),
    "m_lateMax": ("Final, al máximo", "Late game, maxed"),
    "m_lateFresh": ("Final, sin mejoras", "Late game, fresh"),
    "methods_final": ("puesto final {rank}", "final rank {rank}"),
    "methods_alt": ("{name}: puesto final {rank}. ", "{name}: final rank {rank}. "),
    "methods_alt_item": ("{label}, puesto {v}", "{label}, rank {v}"),
    "sim_start": ("Inicial · {name}", "Starting · {name}"),
    "sim_best": ("Mejor · {name}", "Best · {name}"),
    "sim_median": ("mediana: {s} s", "median: {s} s"),
    "sim_alt": ("Segundos que aguanta, de mediana en 200 partidas: ", "Median seconds survived over 200 games: "),

    # ------------------------------------------------------------ ataques
    "ataques_title": ("Ataques · {site}", "Moves · {site}"),
    "ataques_desc": ("Tier list de los {n} ataques de {game}.", "Tier list of the {n} moves in {game}."),
    "ataques_h1": ("Ataques", "Moves"),
    "cat_melee": ("Cuerpo a cuerpo", "Melee"),
    "cat_ranged": ("Distancia", "Ranged"),
    "cat_stat": ("Potenciadores", "Boosts"),
    "mv_dps15": ("Daño, minuto 15", "Damage, minute 15"),
    "mv_ttd15": ("Aguante, minuto 15", "Survival, minute 15"),
    "mv_dps5": ("Daño, minuto 5", "Damage, minute 5"),
    "mv_cover": ("Activo", "Uptime"),
    "mv_fused": ("Fusionado, minuto {n}", "Fused, minute {n}"),
    "mv_typical": ("normal", "typical"),
    "mv_better": ("mejor", "better"),
    "mv_worse": ("peor", "worse"),
    "odds_title": ("Probabilidad por rareza", "Odds by rarity"),

    # ------------------------------------------------------------ gacha
    "gachas_title": ("Gacha · {site}", "Gacha · {site}"),
    "gachas_desc": ("Qué banner de gacha de {game} da más Pokémon top.",
                    "Which {game} gacha banner gives the most top Pokémon."),
    "gachas_h1": ("Gacha", "Gacha"),
    "g_one_in": ("1 de cada {n} es top", "1 in {n} is top"),
    "g_best": ("Mejor banner", "Best banner"),
    "g_worst": ("Mejor no", "Skip"),
    "g_pulls": ("Mejores Pokémon de {name}", "Best Pokémon in {name}"),

    # ------------------------------------------------------------ colección
    "col_title": ("Mi colección · {site}", "My collection · {site}"),
    "col_desc": ("Mira tu colección de {game} por tier.", "See your {game} collection by tier."),
    "col_h1": ("Mi colección", "My collection"),
    "col_step1_html": ("<strong>Abre el juego</strong> con tu cuenta. El modo invitado no guarda nada.",
                       "<strong>Open the game</strong> signed in. Guest mode saves nothing."),
    "col_step2_html": ("<strong>Pega esto en la consola</strong> (F12). Si te lo pide, escribe "
                       "<kbd>allow pasting</kbd>.",
                       "<strong>Paste this in the console</strong> (F12). If asked, type <kbd>allow pasting</kbd> first."),
    "col_copy": ("Copiar", "Copy"),
    "col_step3_html": ("<strong>Pega el resultado</strong> aquí. No sale de tu navegador.",
                       "<strong>Paste the result</strong> here. It never leaves your browser."),
    "col_json": ("Resultado", "Result"),
    "col_view": ("Ver", "Show"),
    "col_file": ("O un archivo .json", "Or a .json file"),

    # ------------------------------------------------------------ acerca
    "about_title": ("Info y aviso legal · {site}", "About and legal notice · {site}"),
    "about_desc": ("Aviso legal y créditos de {site}.", "Legal notice and credits for {site}."),
    "about_h1": ("Info", "About"),
    "about_credits_h": ("Créditos", "Credits"),
    "about_sprites_h": ("Sprites", "Sprites"),
    "about_sprites_html": (
        '<a href="{url}" rel="noopener">{source}</a>, licencia <a href="{lic_url}" rel="noopener">{lic}</a>.',
        '<a href="{url}" rel="noopener">{source}</a>, license <a href="{lic_url}" rel="noopener">{lic}</a>.'),
    "about_icons_h": ("Iconos y letra", "Icons and font"),
    "about_icons_html": (
        'Iconos: <a href="{url}" rel="noopener">{author}</a> ({title}), '
        '<a href="{lic_url}" rel="noopener">{lic}</a>. Glifos de tipo: del juego, licencia MIT.',
        'Icons: <a href="{url}" rel="noopener">{author}</a> ({title}), '
        '<a href="{lic_url}" rel="noopener">{lic}</a>. Type glyphs: from the game, MIT license.'),
    "about_font_html": (
        'Letra: <a href="https://github.com/eifetx/Pixelify-Sans" rel="noopener">Pixelify Sans</a>, '
        'SIL OFL 1.1 (<a href="{root}fonts/OFL.txt">licencia</a>).',
        'Font: <a href="https://github.com/eifetx/Pixelify-Sans" rel="noopener">Pixelify Sans</a>, '
        'SIL OFL 1.1 (<a href="{root}fonts/OFL.txt">license</a>).'),

    # ------------------------------------------------------------ 404
    "nf_title": ("Página no encontrada · {site}", "Page not found · {site}"),
    "nf_h1": ("Página no encontrada", "Page not found"),
    "nf_p_html": ('<a href="/index.html">Volver a la tier list</a> · <a href="/en/index.html">Back to the tier list</a>',
                  '<a href="/en/index.html">Back to the tier list</a> · <a href="/index.html">Volver a la tier list</a>'),

    # ------------------------------------------------------------ método
    "met_title": ("Método · {site}", "Method · {site}"),
    "met_desc": ("Cómo se calcula el ranking de {site}.", "How the {site} ranking is calculated."),
    "met_h1": ("Método", "Method"),
    "pipe_title": ("Del dato al tier", "From data to tier"),
    "pipe_1": ("Medir", "Measure"),
    "pipe_2": ("Percentil", "Percentile"),
    "pipe_3": ("Combinar", "Combine"),
    "pipe_4": ("Repetir ×2.000", "Repeat ×2,000"),
    "pipe_5": ("Puesto", "Rank"),
    "pipe_6": ("Tier", "Tier"),
    "pipe_alt": ("Pasos del cálculo: ", "Calculation steps: "),
    "w_sheet": ("Ficha", "Sheet"),
    "w_sim": ("Partidas", "Games"),
    "w_late": ("Final de partida", "Late game"),
    "weights_title": ("Peso de cada medida", "Weight of each measure"),
    "weights_alt": ("Peso de cada medida: ", "Weight of each measure: "),
    "pw_title": ("Peso dentro de la ficha", "Weight inside the sheet"),
    "pw_alt": ("Pesos de la ficha: ", "Sheet weights: "),
    "tiers_title": ("Tamaño de cada tier", "Size of each tier"),
    "tiers_alt": ("Pokémon por tier: ", "Pokémon per tier: "),
    "gate_title": ("Estadísticas mínimas por tier", "Minimum stats per tier"),
    "gate_name": ("Tier {t}", "Tier {t}"),
    "gate_val": ("top {top} %", "top {top}%"),
    "gate_worst": ("peor", "worst"),
    "gate_best": ("mejor", "best"),
    "gate_alt": ("Estadísticas mínimas para cada tier: ", "Minimum stats for each tier: "),
    "gate_alt_item": ("{t}, entre el {top} % mejor", "{t}, within the top {top}%"),
    "agree_title": ("Qué medida se parece más al ranking", "Which measure is closest to the ranking"),
    "agree_alt": ("Parecido con el puesto final: ", "Closeness to the final rank: "),
    "rib_title": ("Cuánto se mueve cada puesto", "How much each rank moves"),
    "rib_x": ("puesto final", "final rank"),
    "rib_y": ("puesto en las repeticiones", "rank in the repeats"),
    "rib_alt": ("Margen de puestos de cada Pokémon. Ancho típico por tier: ",
                "Rank range of each Pokémon. Typical width per tier: "),
    "rib_alt_item": ("{t} {m} puestos", "{t} {m} places"),
    "stab_title": ("Se queda en su tier", "Stays in its tier"),
    "stab_alt": ("Pokémon que se quedan en su tier: ", "Pokémon that stay in their tier: "),
    "demo_title": ("Un punto flojo hunde la nota", "One weak spot sinks the score"),
    "demo_geo": ("Nuestra media", "Our mean"),
    "demo_arith": ("Media simple", "Plain mean"),
    "demo_aria": ("Percentil en {name}", "Percentile in {name}"),
    "reps_title": ("2.000 repeticiones", "2,000 repeats"),
    "reps_pause": ("Pausa", "Pause"),
    "reps_play": ("Seguir", "Play"),
    "reps_count": ("{n} / {total}", "{n} / {total}"),
    "met_walk_h": ("Sigue a un Pokémon", "Follow one Pokémon"),
    "walk_prev": ("Anterior", "Previous"),
    "walk_next": ("Siguiente", "Next"),
    "walk_auto": ("Auto", "Auto"),
    "walk_stop": ("Parar", "Stop"),
    "walk_step": ("Paso {i} de {n}", "Step {i} of {n}"),
    "walk_1_h": ("Medidas", "Measures"),
    "walk_2_h": ("Pesos", "Weights"),
    "walk_3_h": ("Repeticiones", "Repeats"),
    "walk_4_h": ("Puesto", "Rank"),
    "walk_5_h": ("Tier", "Tier"),
    "walk_tier_alt": ("Puesto {rank} dentro de la tira de tiers", "Rank {rank} inside the tier strip"),
    "arena_title": ("Así se ve una partida simulada", "What a simulated game looks like"),
    "arena_time": ("tiempo", "time"),
    "arena_kills": ("derrotados", "defeated"),
    "arena_alt": ("Animación de una partida simulada. Un Pokémon esquiva y dispara a enemigos que se acercan.",
                  "Animation of a simulated game. A Pokémon dodges and fires at approaching enemies."),
    "met_limits_h": ("Límites", "Limits"),
    "met_lim_1": ("Sin jefes ni grietas.", "No bosses or rifts."),
    "met_lim_2": ("Sin quemadura, veneno ni ralentización.", "No burn, poison or slow."),
    "met_lim_3": ("El bot juega peor el cuerpo a cuerpo.", "The bot plays melee worse."),
    "met_lim_4": ("Estimación propia, sin contrastar con partidas reales.",
                  "Our own estimate, not checked against real games."),
}

TYPE_NAMES = {
    "es": {"normal": "Normal", "fire": "Fuego", "water": "Agua", "grass": "Planta", "electric": "Eléctrico",
           "ice": "Hielo", "fighting": "Lucha", "poison": "Veneno", "ground": "Tierra", "flying": "Volador",
           "psychic": "Psíquico", "bug": "Bicho", "rock": "Roca", "ghost": "Fantasma", "dragon": "Dragón",
           "dark": "Siniestro", "steel": "Acero", "fairy": "Hada"},
    "en": {"normal": "Normal", "fire": "Fire", "water": "Water", "grass": "Grass", "electric": "Electric",
           "ice": "Ice", "fighting": "Fighting", "poison": "Poison", "ground": "Ground", "flying": "Flying",
           "psychic": "Psychic", "bug": "Bug", "rock": "Rock", "ghost": "Ghost", "dragon": "Dragon",
           "dark": "Dark", "steel": "Steel", "fairy": "Fairy"},
}
BANNER_NAMES_EN = {"Teselia": "Unova"}

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _check() -> None:
    for key, (es, en) in STR.items():
        if set(PLACEHOLDER.findall(es)) != set(PLACEHOLDER.findall(en)):
            raise ValueError(f"i18n {key}: marcadores distintos entre es y en")


_check()


@dataclass(frozen=True)
class Lang:
    """Un idioma de salida. El español vive en la raíz del sitio y el inglés bajo /en/."""
    code: str

    @property
    def idx(self) -> int:
        return 0 if self.code == "es" else 1

    @property
    def en(self) -> bool:
        return self.code == "en"

    @property
    def prefix(self) -> str:
        return "en/" if self.en else ""

    def t(self, key: str, **kw) -> str:
        return STR[key][self.idx].format(**kw)

    def t_raw(self, key: str) -> str:
        """El texto con sus marcadores sin rellenar, para las plantillas que se completan en el navegador."""
        return STR[key][self.idx]

    def num(self, n: int | float) -> str:
        s = f"{n:,.0f}"
        return s if self.en else s.replace(",", ".")

    def dec(self, x: float, d: int = 1) -> str:
        s = f"{x:.{d}f}"
        return s if self.en else s.replace(".", ",")

    def pct(self, x: float) -> str:
        """0.968 -> '97 %' en español y '97%' en inglés."""
        v = round(x * 100)
        return f"{v}%" if self.en else f"{v}{NBSP}%"

    def pcts(self, v: float) -> str:
        """Un porcentaje ya en escala 0 a 100."""
        return f"{round(v)}%" if self.en else f"{round(v)}{NBSP}%"

    def type_name(self, t: str) -> str:
        return TYPE_NAMES[self.code][t]

    def banner(self, name: str) -> str:
        return BANNER_NAMES_EN.get(name, name) if self.en else name

    def mon(self, p: dict) -> str:
        """Nombre del Pokémon en este idioma."""
        return p["nameEn"] if self.en else p["name"]


ES, EN = Lang("es"), Lang("en")
LANGS = (ES, EN)
