"""Textos del sitio en español e inglés y formato de números por idioma.

Cada texto es una pareja (es, en) con los mismos marcadores {nombre}. Las claves que terminan en _html llevan HTML
y se insertan tal cual. El resto es texto plano y quien lo usa lo escapa. Al importar este módulo se comprueba que
las dos versiones de cada texto tienen los mismos marcadores.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

NBSP = "\u00a0"
GAME_NAME = "PokéSurvivor"
SITE_NAME = "SurvivorTiers"

STR: dict[str, tuple[str, str]] = {
    # ------------------------------------------------------------ base
    "skip": ("Saltar al contenido", "Skip to content"),
    "og_alt": ("Tier list no oficial de PokéSurvivor: cartas de las fichas S con sprites de pixel art.",
               "Unofficial PokéSurvivor tier list: S-tier cards with pixel-art sprites."),
    "follow_label": ("Sigue a {handle} en X", "Follow {handle} on X"),
    "nav_main": ("Principal", "Main"),
    "nav_foot": ("Pie", "Footer"),
    "nav_tiers": ("Tiers", "Tiers"),
    "nav_novedades": ("Novedades", "Updates"),
    "nav_metodo": ("Método", "Method"),
    "nav_ataques": ("Ataques", "Moves"),
    "nav_objetos": ("Objetos", "Items"),
    "nav_pasivas": ("Pasivas", "Passives"),
    "nav_gachas": ("Gacha", "Gacha"),
    "nav_coleccion": ("Colección", "Collection"),
    "nav_acerca": ("Info", "About"),
    "lang_label": ("Idioma", "Language"),
    "theme_btn": ("Tema claro u oscuro", "Light or dark theme"),
    "theme_to_dark": ("Cambiar a modo oscuro", "Switch to dark mode"),
    "theme_to_light": ("Cambiar a modo claro", "Switch to light mode"),
    "disclaimer": (
        "Sitio de fans, no oficial y no afiliado a Nintendo, Creatures, GAME FREAK, The Pokémon Company ni {game}. "
        "Pokémon y sus nombres son marcas de sus dueños.",
        "Fan site, unofficial and not affiliated with Nintendo, Creatures, GAME FREAK, The Pokémon Company or {game}. "
        "Pokémon and its names are trademarks of their owners."),
    "tier": ("Tier {t}", "Tier {t}"),

    # ------------------------------------------------------------ portada
    "index_title": ("{site} · Tier list de {game}", "{site} · {game} tier list"),
    "index_desc": ("Tier list de los {n} Pokémon de {game}, hecha simulando {sims} partidas por Pokémon. Código y datos abiertos en GitHub.",
                   "Tier list of the {n} Pokémon in {game}, built by simulating {sims} games per Pokémon. Code and data open on GitHub."),
    "fresh": ("Actualizado al parche del {date} ({sha})", "Updated to the {date} patch ({sha})"),
    "guides_h": ("Más listas", "More lists"),
    "guides_types": ("Por tipo", "By type"),
    "guide_best": ("Mejores Pokémon", "Best Pokémon"),
    "guide_starters": ("Mejores iniciales", "Best starters"),
    "guide_legendary": ("Legendarios", "Legendaries"),
    "guide_passives": ("Mejores pasivas", "Best passives"),
    "guide_tierlist": ("Tier list completa", "Full tier list"),
    "fh_game": ("en {game}", "in {game}"),
    "dataset_name": ("Ranking no oficial de los Pokémon de {game}", "Unofficial ranking of the Pokémon in {game}"),
    "agents_label": ("Para agentes de IA y datos:", "For AI agents and data:"),
    "index_h1": ("Tier list de {game}", "{game} tier list"),
    "search_label": ("Buscar", "Search"),
    "search_ph": ("Pikachu, fuego, #25…", "Pikachu, fire, #25…"),
    "search_clear": ("Borrar búsqueda", "Clear search"),
    "random_btn": ("Al azar", "Random"),
    "side_filter": ("Filtrar por ataque", "Filter by attack"),
    "side_all": ("Todos", "All"),
    "side_phys": ("Físico", "Physical"),
    "side_spec": ("Especial", "Special"),
    "side_mix": ("Mixto", "Mixed"),
    "group_by": ("Agrupar por", "Group by"),
    "group_tier": ("Tier", "Tier"),
    "group_type": ("Tipo", "Type"),
    "group_rar": ("Rareza", "Rarity"),
    "group_region": ("Región", "Region"),
    "group_leg": ("Legendarios", "Legendary"),
    "group_none": ("Sin agrupar", "No groups"),
    "no_match": ("Ningún Pokémon coincide. Prueba con otro nombre o tipo.",
                 "No Pokémon match. Try another name or type."),
    "noscript": ("El buscador y el filtro de ataque necesitan JavaScript.",
                 "Search and the attack filter need JavaScript."),
    "value_html": (
        'Los cinco primeros de {game}: {top}. Tier list de fans con {n} Pokémon, cada uno simulado en {sims} partidas. '
        'El ranking mide cuánto aguanta, cuánto daño hace y a cuántos enemigos derrota. '
        '<a href="{method}">Cómo se calcula</a> · <a href="{repo}" rel="noopener">código y datos en GitHub</a>.',
        'Top five in {game}: {top}. A fan-made tier list of {n} Pokémon, each simulated in {sims} games. '
        'The ranking measures how long they survive, how much damage they deal and how many enemies they defeat. '
        '<a href="{method}">How it is calculated</a> · <a href="{repo}" rel="noopener">code and data on GitHub</a>.'),
    "foot_html": (
        'Sitio de fans, no oficial y no afiliado a Nintendo ni The Pokémon Company. Sprites: SpriteCollab (CC BY-NC 4.0). '
        '<a href="{about}">Info y créditos</a>.',
        'Fan site, unofficial and not affiliated with Nintendo or The Pokémon Company. Sprites: SpriteCollab (CC BY-NC 4.0). '
        '<a href="{about}">Info and credits</a>.'),
    "filters_btn": ("Filtros y orden", "Filters and sorting"),
    "nav_more": ("Más", "More"),
    "about_value_html": (
        'Tier list de {game} hecha simulando {sims} partidas por Pokémon, no solo con fórmulas de stats. Código, simulador '
        'y datos abiertos en <a href="{repo}" rel="noopener">GitHub</a>, para que cualquiera lo compruebe.',
        'Tier list of {game} built by simulating {sims} games per Pokémon, not from stat formulas alone. Code, simulator '
        'and data open on <a href="{repo}" rel="noopener">GitHub</a>, so anyone can check it.'),
    "home_title": ("Mejores Pokémon de {game}: tier list de {n} | {site}",
                   "Best Pokémon in {game}: tier list of {n} | {site}"),
    "home_desc": ("Tier list de {game} con los {n} Pokémon ordenados por partidas simuladas, al día con el parche del {date}. "
                  "Ahora mismo en lo más alto: {top}.",
                  "{game} tier list with all {n} Pokémon ranked from simulated games, up to date with the {date} patch. "
                  "Right now at the top: {top}."),
    "top30_h": ("Los 30 mejores Pokémon de {game}", "The 30 best Pokémon in {game}"),
    "top30_lede": ("La misma lista en texto, por si no ves los dibujos. Cada nombre lleva a su ficha con la build y el cómo conseguirlo.",
                   "The same list as plain text, in case you can't see the pictures. Each name links to its page with the build and how to get it."),
    "top30_caption": ("Top 30 de la tier list de {game}", "Top 30 of the {game} tier list"),
    "top30_rank": ("Puesto", "Rank"),
    "top30_mon": ("Pokémon", "Pokémon"),
    "top30_tier": ("Tier", "Tier"),
    "top30_types": ("Tipos", "Types"),
    "top30_band": ("Rango habitual", "Usual range"),
    "top30_places": ("{lo} a {hi}", "{lo} to {hi}"),
    "card_title": ("{name} · nº {dex} · puesto {rank} · tier {tier}",
                   "{name} · no. {dex} · rank {rank} · tier {tier}"),

    # ------------------------------------------------------------ ficha
    "crumb_home": ("Tier list", "Tier list"),
    "legendary": ("Legendario", "Legendary"),
    "rar_1": ("Común", "Common"),
    "rar_2": ("Poco común", "Uncommon"),
    "rar_3": ("Rara", "Rare"),
    "rar_4": ("Épica", "Epic"),
    "rar_5": ("Legendaria", "Legendary"),
    "stars_alt": ("{n} de 5 estrellas", "{n} of 5 stars"),
    "sprite_alt": ("Sprite de {name}", "Sprite of {name}"),
    "ficha_title": ("{name} en {game} · tier {tier} · {site}", "{name} in {game} · tier {tier} · {site}"),
    "ficha_desc": ("{label}: tier {tier}, puesto {rank} de {total} en {game}.",
                   "{label}: tier {tier}, rank {rank} of {total} in {game}."),
    "sheet_title": ("{name} en {game}: tier, build y cómo conseguirlo",
                    "{name} in {game}: tier, build and how to get it"),
    "sheet_desc": ("{name} en {game}: tier {tier}, puesto {rank} de {total}. Grupo vinculado, estadísticas base y banner de gacha.",
                   "{name} in {game}: tier {tier}, rank {rank} of {total}. Bonded move group, base stats and gacha banner."),
    "fh_title": ("{name} en {game}: tier {tier}, mejor build y ataques | {site}",
                 "{name} in {game}: {tier} tier, best build and moves | {site}"),
    "fh_desc": ("{name} es tier {tier} en {game}: puesto {rank} de {total}. Mejor build: {attacks}. "
                "Con las cartas que conviene coger y el banner {banner} donde sale.",
                "{name} is {tier} tier in {game}: rank {rank} of {total}. Best build: {attacks}. "
                "With the cards worth taking and the {banner} banner it comes from."),
    "fh_desc_buffs": ("{name} es tier {tier} en {game}: puesto {rank} de {total}. Mejor build: {attacks}, con {buffs}. "
                      "Con las cartas que conviene coger y el banner {banner} donde sale.",
                      "{name} is {tier} tier in {game}: rank {rank} of {total}. Best build: {attacks}, with {buffs}. "
                      "With the cards worth taking and the {banner} banner it comes from."),
    "sheet_obtain_h": ("Cómo conseguirlo", "How to get it"),
    "sheet_faq_h": ("Preguntas", "Questions"),
    "faq_q_worth": ("¿Vale la pena?", "Is it worth it?"),
    "faq_a_S": ("Sí, está entre los mejores: tier S, puesto {rank} de {total}.",
                "Yes, it is one of the best: tier S, rank {rank} of {total}."),
    "faq_a_A": ("Sí, está entre los buenos: tier A, puesto {rank} de {total}.",
                "Yes, it is one of the good ones: tier A, rank {rank} of {total}."),
    "faq_a_B": ("Está en la media: tier B, puesto {rank} de {total}.",
                "It is about average: tier B, rank {rank} of {total}."),
    "faq_a_C": ("Tirando a flojo: tier C, puesto {rank} de {total}.",
                "It is pretty weak: tier C, rank {rank} of {total}."),
    "faq_a_D": ("No, está entre los peores: tier D, puesto {rank} de {total}.",
                "No, it is one of the worst: tier D, rank {rank} of {total}."),
    "faq_q_moves": ("¿Qué ataques le pongo?", "Which moves should I use?"),
    "faq_a_moves_plain": ("{attacks}.", "{attacks}."),
    "faq_a_moves_one": ("{attacks}, con {buffs} de potenciador.", "{attacks}, with {buffs} as the boost."),
    "faq_a_moves": ("{attacks}, con {buffs} de potenciadores.", "{attacks}, with {buffs} as boosts."),
    "faq_a_cover": ("Pega super efectivo al {super} de los enemigos.",
                    "Its moves are super effective against {super} of enemies."),
    "faq_a_cover_none": ("Ninguno de sus ataques es super efectivo contra los enemigos.",
                         "None of its moves is super effective against enemies."),
    "faq_q_cards": ("¿Qué cartas le conviene coger?", "Which upgrade cards should I take?"),
    "faq_a_cards": ("Según nuestra simulación, en este orden: {cards}.",
                    "Based on our simulation, in this order: {cards}."),
    "faq_a_cards_gate": ("Según nuestra simulación, en este orden: {cards}. {once} solo hace falta una vez, para evolucionar el ataque.",
                         "Based on our simulation, in this order: {cards}. {once} is only needed once, to evolve the move."),
    "faq_q_get": ("¿Cómo se consigue?", "How do you get it?"),
    "faq_get_where": ("Sale en el banner {banner}.", "It is on the {banner} banner."),
    "faq_get_where_leg": ("Es de los legendarios y sale en el banner {banner}.",
                          "It is a legendary and is on the {banner} banner."),
    "faq_get_odds": ("Cada tirada tiene un {pct}\u00a0% de probabilidad, así que de media hacen falta unas {n} tiradas, "
                     "sin contar las garantías.",
                     "Each pull has a {pct}% chance, so on average it takes about {n} pulls, not counting pity guarantees."),
    "sheet_a_build": ("El grupo vinculado es {attacks}. Potenciadores: {buffs}.",
                      "The bonded group is {attacks}. Boosts: {buffs}."),
    "sheet_a_build_plain": ("El grupo vinculado es {attacks}.", "The bonded group is {attacks}."),
    "sheet_a_cover": ("Esos ataques pegan super efectivo al {super} y no encuentran resistencia en el {neutral}.",
                      "Those attacks hit super-effectively on {super} and are never resisted on {neutral}."),
    "sheet_sim_line": ("Puesto simulado (mejor ataque): {rank}", "Simulated rank (best move): {rank}"),
    "sheet_open_line": ("Apertura con Repertorio: puesto {rank}", "Repertoire opening: rank {rank}"),
    "flag_status": ("Uno de sus ataques aplica un estado que esta pasada de la simulación no reproduce, "
                    "así que su aguante puede estar infravalorado.",
                    "One of its attacks applies a status this sim pass does not reproduce, "
                    "so its survival may be underrated."),
    "flag_melee": ("Sigue en cuerpo a cuerpo: aunque vete los peores ataques, el segundo no lo saca de ahí.",
                   "It stays melee: even after banning its worst moves, the second attack never gets it out."),
    "pager_aria": ("Pokémon vecinos", "Neighbouring Pokémon"),
    "dex_no": ("nº {dex}", "no. {dex}"),
    "tpl_title": ("Fichas de los Pokémon de {game} | {site}", "Pokémon pages of {game} | {site}"),
    "tpl_desc": ("Las {n} fichas de {game}, una por Pokémon: tier, build, cartas y cómo conseguirlo.",
                 "All {n} {game} pages, one per Pokémon: tier, build, cards and how to get it."),
    "tpl_h1": ("Fichas de los Pokémon de {game}", "Pokémon pages of {game}"),
    "tpl_lede": ("Cada uno de los {n} Pokémon tiene su ficha con el tier, el puesto, la build, las cartas que conviene coger y "
                 "cómo conseguirlo. Elige uno de la lista.",
                 "Each of the {n} Pokémon has its own page with its tier, rank, build, the cards worth taking and how to get "
                 "it. Pick one from the list."),
    "f_missing": ("Pokémon no encontrado", "Pokémon not found"),

    # ------------------------------------------------------------ gráficos de la ficha
    "t_band": ("Puesto", "Rank"),
    "t_pillars": ("Puntos fuertes", "Strengths"),
    "t_methods": ("Cada medida", "Each measure"),
    "t_base": ("Estadísticas base", "Base stats"),
    "bs_hp": ("PS", "HP"),
    "bs_atk": ("Ataque", "Attack"),
    "bs_def": ("Defensa", "Defense"),
    "bs_spa": ("Ataque especial", "Sp. Attack"),
    "bs_spd": ("Defensa especial", "Sp. Defense"),
    "bs_spe": ("Velocidad", "Speed"),
    "bs_total": ("Total", "Total"),
    "bs_s_hp": ("PS", "HP"),
    "bs_s_atk": ("Atq", "Atk"),
    "bs_s_def": ("Def", "Def"),
    "bs_s_spa": ("AtE", "SpA"),
    "bs_s_spd": ("DeE", "SpD"),
    "bs_s_spe": ("Vel", "Spe"),
    "bs_alt_item": ("{label} {v}", "{label} {v}"),
    "t_combat": ("Ataque y defensa", "Attack and defense"),
    "cb_pa": ("Ataque físico", "Physical attack"),
    "cb_sa": ("Ataque especial", "Special attack"),
    "cb_df": ("Defensa", "Defense"),
    "cb_sd": ("Def. Especial", "Sp. Def."),
    "cb_kind_phys": ("Atacante físico", "Physical attacker"),
    "cb_kind_spec": ("Atacante especial", "Special attacker"),
    "cb_kind_mix": ("Mixto", "Mixed"),
    "cb_note": ("Con 75 de defensa recibes daño normal: con mucha defensa, hasta un {less}\u00a0% menos; con poca, "
                "hasta un {more}\u00a0% más. Los golpes físicos los frena la Defensa y los especiales la Def. Especial.",
                "At 75 defense you take normal damage: high defense cuts up to {less}\u00a0% and low defense adds up to "
                "{more}\u00a0%. Physical hits are blocked by Defense, special hits by Sp. Def."),
    "t_sim": ("Aguante simulado", "Simulated survival"),
    "band_rank": ("puesto {rank}", "rank {rank}"),
    "band_range": ("{lo} a {hi}", "{lo} to {hi}"),
    "t_learn": ("Ataques que puede aprender", "Moves it can learn"),
    "learn_lede": ("{n} ataques: los de tipo normal y los de sus tipos, por tier general (la misma que en Ataques). "
                   "No los simula con este Pokémon.",
                   "{n} moves: normal-type ones and those of its types, by overall tier (the same as on Moves). "
                   "They are not simulated with this Pokémon."),
    "learn_start": ("inicial", "start"),
    "learn_boosts": ("Potenciadores", "Boosts"),
    "t_build": ("Build", "Build"),
    "build_start": ("Inicio", "Start"),
    "build_best": ("Mejor ataque", "Best move"),
    "build_boost": ("Potenciador", "Boost"),
    "build_alt": ("Opcionales", "Optional"),
    "build_items": ("Objetos", "Items"),
    "build_cards": ("Cartas por prioridad", "Cards by priority"),
    "build_card_hint": ("Si no te sale una, coge la siguiente de la lista.", "If one doesn't show up, take the next one on the list."),
    "build_card_n": ("Prioridad {n}", "Priority {n}"),
    "build_card_once": ("1× = cógela una vez, para evolucionar el ataque del grupo.",
                        "1× = take it once, to evolve the group move."),
    "build_card_more": ("Ver orden completo", "See full order"),
    "bp_cards_all": ("Orden completo", "Full order"),
    "build_super": ("Super efectivo", "Super effective"),
    "build_neutral": ("Sin resistencia", "Never resisted"),
    "build_share": ("Compartir esta build", "Share this build"),
    "build_copied": ("Enlace copiado", "Link copied"),
    "build_slot": ("Hueco {n}", "Slot {n}"),
    "build_brand": ("{site}", "{site}"),
    "build_group": ("Vínculo", "Bond"),
    "build_best_item": ("Mejor objeto", "Best item"),
    "build_more": ("Más", "More"),
    "t_rank": ("Ranking", "Ranking"),
    "rank_how": ("Cómo se calcula", "How it is calculated"),
    "ficha_rank": ("Puesto {rank} de {total}", "Rank {rank} of {total}"),
    "sort_by": ("Ordenar por", "Sort by"),
    "sort_rank": ("Puesto", "Rank"),
    "sort_name": ("Nombre", "Name"),
    "sort_dex": ("Nº Pokédex", "Pokédex no."),
    "sort_atk": ("Ataque máximo", "Top attack"),
    "sort_pa": ("Ataque físico", "Physical attack"),
    "sort_sa": ("Ataque especial", "Special attack"),
    "sort_df": ("Defensa", "Defense"),
    "sort_sd": ("Def. Especial", "Sp. Def."),
    "sort_hp": ("Vida", "HP"),
    "sort_spd": ("Velocidad", "Speed"),
    "sort_ehp": ("Vida efectiva", "Effective HP"),
    "sort_rad": ("Tamaño", "Size"),
    "sort_td": ("Defensa de tipos", "Type resistance"),
    "sort_mv": ("Movimientos", "Moves"),
    "sort_st": ("Estadísticas", "Stats"),
    "sort_rar": ("Rareza", "Rarity"),
    "dir_asc": ("Menor primero", "Lowest first"),
    "dir_desc": ("Mayor primero", "Highest first"),
    "band_zoom": ("Zoom · puestos {lo} a {hi} de {total}", "Zoom · ranks {lo} to {hi} of {total}"),
    "band_all": ("Todos los puestos · 1 a {total}", "All ranks · 1 to {total}"),
    "band_alt": ("{name}: puesto {rank} de {total}, tier {tier}. Suele quedar entre el {lo} y el {hi}.",
                 "{name}: rank {rank} of {total}, tier {tier}. Usually lands between {lo} and {hi}."),
    "pill_stats": ("Estadísticas", "Stats"),
    "pill_moves": ("Ataques", "Moves"),
    "pill_typedef": ("Defensa de tipos", "Type resistance"),
    "pill_size": ("Hitbox pequeño", "Small hitbox"),
    "pillars_alt_item": ("{label}, mejor que el {v} % de los Pokémon", "{label}, better than {v}% of Pokémon"),
    "median": ("mediana", "median"),
    "m_sheet": ("Ficha", "Sheet"),
    "m_simStart": ("Partida, apertura con Repertorio", "Game, Repertoire opening"),
    "m_simBest": ("Partida, mejor ataque", "Game, best move"),
    "m_lateMax": ("Final, todas las mejoras al máximo", "Late game, all shop upgrades maxed"),
    "m_lateFresh": ("Final, sin mejoras de tienda", "Late game, no shop upgrades"),
    "methods_lede": ("Cada punto es el puesto que daría esa medida: 1 es el mejor de 966, a la izquierda. "
                     "La escala se amplía hasta su peor puesto, así que un 24 parece lejos de 1, pero sigue siendo el 3 % superior. "
                     "«Apertura con Repertorio» es la partida empezando con dos ataques y hasta tres vetos. "
                     "«Final» estima cuánto aguanta al final de una partida, con la tienda de estadísticas sin comprar nada "
                     "o con todas sus mejoras permanentes al máximo; esa medida no es la apertura. La línea naranja es el puesto final, "
                     "que mezcla todas las medidas.",
                     "Each dot is the rank that measure would give: 1 is the best of 966, on the left. "
                     "The scale zooms in to its worst rank, so 24 looks far from 1 but is still the top 3%. "
                     "'Repertoire opening' is the run starting with two attacks and up to three bans. "
                     "'Late game' estimates how long a Pokémon lasts at the end of a run, with no stat-shop upgrades "
                     "bought or with all permanent upgrades maxed; that measure is not the opening. The orange line is the final rank, which mixes every measure."),
    "methods_final": ("puesto final {rank}", "final rank {rank}"),
    "methods_alt": ("{name}: puesto final {rank}. ", "{name}: final rank {rank}. "),
    "methods_alt_item": ("{label}, puesto {v}", "{label}, rank {v}"),
    "sim_start": ("Apertura con Repertorio: {name}", "Repertoire opening: {name}"),
    "sim_best": ("Mejor ataque: {name}", "Best move: {name}"),
    "sim_median": ("mediana de todos: {s} s", "median of all: {s} s"),
    "sim_alt": ("Segundos simulados que aguanta un bot con un grupo fijo (mediana de 200 partidas): ",
                "Simulated seconds a bot survives with one fixed group (median of 200 games): "),
    "sim_lede": ("Un bot juega con un grupo fijo (el ataque inicial, otro más, Danza Espada o Maquinación según el primer ataque, y Fortaleza). "
                 "La barra de apertura es una estimación: con Repertorio sale un segundo ataque al azar, con Veto se bloquean los 3 que más bajan esa media, y se juega el mejor de los dos. "
                 "Los vínculos llegan al ganar la grieta, no al empezar; hay jefes y orbes de curación, y se lanzan todos los tipos de ataque. "
                 "Hasta 900 s. El bot no esquiva como una persona.",
                 "A bot plays one fixed group (the starting move, one more attack, Swords Dance or Nasty Plot to match the first attack, and Harden). "
                 "The opening bar is an estimate: Repertoire deals a random second attack, Veto bans the 3 that pull that average down the most, and the better of the two is played. "
                 "Bonds arrive when a rift is won, not at the start; bosses and heal orbs are in, and every attack kind fires. "
                 "Up to 900 s. The bot does not dodge the way a person does."),
    "sim_scale": ("Escala: de {lo} s a {hi} s, lo que aguantan todos los Pokémon.",
                  "Scale: {lo} s to {hi} s, what all Pokémon last."),
    "sim_gain": ("Con el mejor ataque aguanta {d} s más que con esa apertura. Cifra simulada.",
                 "With the best move it lasts {d} s longer than with that opening. Simulated figure."),
    "sim_noshop": ("Sin Repertorio ni Veto, solo con {name}, la simulación aguanta {s} s.",
                   "With no Repertoire and no Veto, {name} alone lasts {s} s in the simulation."),

    # ------------------------------------------------------------ listas de consulta (landing.py)
    "lp_top_h": ("Ranking", "Ranking"),
    "lp_note": ("Cada puesto sale de {sims} partidas simuladas por Pokémon y {reps} repeticiones del cálculo. "
                "Cómo se calcula, en Método.",
                "Each rank comes from {sims} simulated games per Pokémon and {reps} repeats of the calculation. "
                "How it is calculated, on Method."),
    "lp_start_move": ("Ataque inicial: {move}", "Starting move: {move}"),
    "lp_best_title": ("Mejores Pokémon de {game} · {site}", "Best Pokémon in {game} · {site}"),
    "lp_best_h1": ("Mejores Pokémon de {game}", "Best Pokémon in {game}"),
    "lp_best_desc": ("Los {n} mejores Pokémon de {game} según la tier list simulada: {top}.",
                     "The {n} best Pokémon in {game} by the simulated tier list: {top}."),
    "lp_best_lede": ("Los mejores Pokémon de {game} son {top}. Los {n} primeros forman el tier S.",
                     "The best Pokémon in {game} are {top}. The first {n} make up tier S."),
    "lp_start_title": ("Mejores iniciales de {game} · {site}", "Best starters in {game} · {site}"),
    "lp_start_h1": ("Mejores iniciales de {game}", "Best starters in {game}"),
    "lp_start_desc": ("Los iniciales de {game} que más aguantan en la apertura con Repertorio: {top}.",
                      "The starters in {game} that last longest in the Repertoire opening: {top}."),
    "lp_start_lede": ("Los iniciales que más aguantan en la apertura de {game} son {top}.",
                      "The starters that last longest in the {game} opening are {top}."),
    "lp_start_note": ("Apertura: el ataque inicial con Repertorio (un segundo ataque al azar) y Veto (se bloquean los tres "
                      "que más bajan la media). Puesto por esa apertura, no por el final de la partida.",
                      "Opening: the starting move with Repertoire (a random second move) and Veto (the three moves that pull "
                      "the average down are banned). Rank by that opening, not the late game."),
    "lp_leg_title": ("Legendarios de {game} · {site}", "Legendaries in {game} · {site}"),
    "lp_leg_h1": ("Legendarios de {game}", "Legendaries in {game}"),
    "lp_leg_desc": ("Los {n} legendarios de {game} por puesto en la tier list simulada: {top}.",
                    "The {n} legendaries in {game} by rank in the simulated tier list: {top}."),
    "lp_leg_lede": ("Los legendarios de {game} por puesto son {top}. Hay {n} en total y {s} están en el tier S.",
                    "The legendaries in {game} by rank are {top}. There are {n} in total and {s} are in tier S."),
    "lp_type_title": ("Mejores Pokémon de tipo {type} en {game} · {site}", "Best {type} Pokémon in {game} · {site}"),
    "lp_type_h1": ("Mejores Pokémon de tipo {type} en {game}", "Best {type} Pokémon in {game}"),
    "lp_type_desc": ("Los mejores Pokémon de tipo {type} en {game}: {top}.",
                     "The best {type} Pokémon in {game}: {top}."),
    "lp_type_lede": ("Los mejores Pokémon de tipo {type} en {game} son {top}. De los {n} de ese tipo, {s} están en el tier S.",
                     "The best {type} Pokémon in {game} are {top}. Of the {n} of that type, {s} are in tier S."),
    "lp_pas_title": ("Mejores pasivas de {game} · {site}", "Best passives in {game} · {site}"),
    "lp_pas_h1": ("Mejores pasivas de {game}", "Best passives in {game}"),
    "lp_pas_desc": ("Las cartas de nivel de {game} que más monedas dan: {top}.",
                    "The level-up cards in {game} that earn the most coins: {top}."),
    "lp_pas_lede": ("En {game}, la carta que más monedas da es {best}. Después: {next}. Las demás no suben las monedas.",
                    "In {game}, the card that earns the most coins is {best}. Then: {next}. The rest do not raise coins."),
    "lp_pas_lede_tie": ("Priorizar una carta no mueve la mediana de monedas. Las ocho quedan empatadas.",
                        "Prioritizing a card does not move the median coins. All eight are tied."),
    "lp_pas_desc_tie": ("Ninguna carta de nivel de {game} mueve la mediana de monedas.",
                        "No level-up card in {game} moves the median coins."),
    "lp_pas_note": ("Monedas: subida al priorizar la carta. La tabla completa, con la baya Zidra y las combinaciones con objetos, está en Pasivas.",
                    "Coins: the rise from prioritizing the card. The full table, with the Sitrus Berry and item combinations, is on Passives."),
    "lp_pas_link": ("Tabla completa en Pasivas", "Full table on Passives"),

    # ------------------------------------------------------------ ataques
    "ataques_title": ("Ataques de {game} · {site}", "Moves in {game} · {site}"),
    "ataques_desc": ("Tier list de los {n} ataques de {game}.", "Tier list of the {n} moves in {game}."),
    "ataques_h1": ("Ataques de {game}", "Moves in {game}"),
    "ataques_lede": ("Tier list de los ataques de {game}. 1× es un ataque normal; cuanto más alto, mejor.",
                     "Tier list of the moves in {game}. 1× is a normal move; the higher, the better."),
    "cat_melee": ("Cuerpo a cuerpo", "Melee"),
    "cat_ranged": ("Distancia", "Ranged"),
    "cat_stat": ("Potenciadores", "Boosts"),
    "mv_value": ("Valor", "Value"),
    "mv_typical": ("normal", "typical"),
    "mv_better": ("mejor", "better"),
    "mv_worse": ("peor", "worse"),
    "mv_search": ("Buscar ataque o tipo…", "Search a move or type…"),
    "mv_none": ("Ningún ataque coincide con la búsqueda.", "No move matches the search."),
    "mv_example": ("Ejemplo: {name}", "Example: {name}"),
    "mv_evolves": ("Evoluciona a {move}", "Evolves into {move}"),
    "mv_evolves_card": ("Evoluciona a {move} con la carta {card}", "Evolves into {move} with the {card} card"),
    "mv_buff": ("Dura {dur} s, con recarga de {cd} s", "Lasts {dur} s, with a {cd} s cooldown"),
    "mv_kind_melee": ("Cuerpo a cuerpo", "Melee"),
    "mv_kind_projectile": ("Proyectil", "Projectile"),
    "mv_kind_aura": ("Aura", "Aura"),
    "mv_kind_nova": ("Onda", "Nova"),
    "mv_kind_beam": ("Rayo", "Beam"),
    "mv_kind_buff": ("Potenciador", "Boost"),
    "mv_kind_orbit": ("Órbita", "Orbit"),
    "mv_kind_boomerang": ("Bumerán", "Boomerang"),
    "mv_kind_meteor": ("Meteoro", "Meteor"),
    "mv_kind_mine": ("Mina", "Mine"),
    "mv_kind_dash": ("Embestida", "Dash"),
    "mv_kind_trail": ("Estela", "Trail"),
    "mv_kind_chain": ("Cadena", "Chain"),
    "mv_kind_homing": ("Teledirigido", "Homing"),
    "mv_kind_pierce": ("Perforante", "Piercing"),
    "mv_kind_cone": ("Cono", "Cone"),
    "mv_kind_turret": ("Torreta", "Turret"),
    "mv_kind_bounce": ("Rebote", "Bounce"),
    "mv_kind_charge": ("Rayo cargado", "Charged beam"),
    "mv_kind_spin": ("Giro", "Spin"),
    "mv_kind_quake": ("Onda por el suelo", "Ground wave"),
    "mv_kind_vortex": ("Remolino", "Vortex"),
    "mv_kind_shove": ("Empuje", "Shove"),
    "mv_kind_stun": ("Aturdimiento", "Stun"),
    "mv_new": ("Nuevo", "New"),
    "mv_unranked_h": ("Sin puesto", "Not ranked"),
    "mv_unranked": ("Sin puesto: no hace daño por sí solo y la tier list mide ataques. Sus cifras son las del juego.",
                    "Not ranked: it deals no damage on its own and the tier list measures attacks. Its numbers are the game's."),
    "mv_stacks": ("Cada acumulación: {amt} de {stat}, hasta {n}", "Each stack: {amt} {stat}, up to {n}"),
    "mv_buff_max": ("Con las {ups} mejoras: {amt} por acumulación, hasta {n}, y dura {dur} s",
                    "With all {ups} upgrades: {amt} per stack, up to {n}, lasting {dur} s"),
    "mv_damage_h": ("Tipo de daño de cada ataque", "Damage type of each move"),
    "dmg_physical": ("Físico", "Physical"),
    "dmg_special": ("Especial", "Special"),
    "dmg_status": ("Estado", "Status"),
    "dmg_tip_physical": ("Ataque físico: pega con el Ataque", "Physical attack: deals damage with Attack"),
    "dmg_tip_special": ("Ataque especial: pega con el Ataque Especial", "Special attack: deals damage with Sp. Attack"),
    "dmg_tip_status": ("Potenciador: no hace daño", "Boost: deals no damage"),
    "odds_title": ("Probabilidad por rareza", "Odds by rarity"),

    # ------------------------------------------------------------ objetos
    "obj_title": ("Objetos de {game} · {site}", "Items in {game} · {site}"),
    "obj_desc": ("Tier list de los objetos de {game} por fase de la partida.",
                 "Tier list of the {game} items by phase of the run."),
    "obj_h1": ("Objetos de {game}", "Items in {game}"),
    "obj_lede": ("En {game} solo se lleva uno por partida: los cofres los sueltan y puedes cambiarlo.",
                 "In {game} you carry one per run: chests drop them and you can swap it."),
    "obj_phases_h": ("Tier por fase", "Tier by phase"),
    "obj_table_h": ("Qué hace cada objeto", "What each item does"),

    # ------------------------------------------------------------ pasivas
    "pv_title": ("Pasivas de {game} · {site}", "Passives in {game} · {site}"),
    "pv_desc": ("Qué carta de nivel coger en {game}, en orden, y cuándo la baya Zidra.",
                "Which level-up card to take in {game}, in order, and when to take the Sitrus Berry."),
    "pv_h1": ("Pasivas de {game}", "Passives in {game}"),
    "pv_lede": ("Cartas de nivel de {game} ordenadas por las monedas que dan.", "Level-up cards in {game}, ranked by the coins they earn."),
    "pv_rank_h": ("Orden", "Order"),
    "pv_rank_note": ("Monedas: subida al priorizar la carta. Aguante y bajas/min: cómo cambia la partida.",
                     "Coins: the rise from prioritizing the card. Survival and kills/min: how the run changes."),
    "pv_surv": ("Aguante", "Survival"),
    "pv_kills": ("Bajas/min", "Kills/min"),
    "pv_take": ("Cógela", "Take it"),
    "pv_wait": ("Espera", "Wait"),
    "pv_items_h": ("Con objeto", "With an item"),
    "pv_items_note": ("Lo que suma la carta si ya llevas el objeto.", "What the card adds once you hold the item."),
    "pv_offers_h": ("Qué cartas salen", "Which cards come up"),
    "pv_except_h": ("Ataques que cambian el orden", "Moves that change the order"),
    "pv_method_sum": ("Cómo se calcula", "How it is calculated"),
    "pv_method_link": ("Método completo", "Full method"),

    # ------------------------------------------------------------ gacha
    "gachas_title": ("Gacha de {game} · {site}", "Gacha for {game} · {site}"),
    "gachas_desc": ("Qué banner de gacha de {game} da más Pokémon top.",
                    "Which {game} gacha banner gives the most top Pokémon."),
    "gachas_h1": ("Gacha de {game}", "Gacha for {game}"),
    "g_yours": ("Tu colección dice dónde tirar.", "Your collection says where to pull."),
    "g_one_in": ("1 de cada {n} es top", "1 in {n} is top"),
    "g_best": ("Mejor banner", "Best banner"),
    "g_worst": ("Mejor no", "Skip"),
    "g_pulls": ("Mejores Pokémon de {name}", "Best Pokémon in {name}"),

    # ------------------------------------------------------------ colección
    "col_title": ("Mi colección de {game} · {site}", "My {game} collection · {site}"),
    "col_desc": ("Mira tu colección de {game} por tier.", "See your {game} collection by tier."),
    "col_h1": ("Mi colección de {game}", "My {game} collection"),
    "col_step1_html": ("<strong>Abre el juego</strong> con tu cuenta. El modo invitado no guarda nada.",
                       "<strong>Open the game</strong> signed in. Guest mode saves nothing."),
    "col_step2_html": ("<strong>Pega esto en la consola</strong> (F12). Si te lo pide, escribe "
                       "<kbd>allow pasting</kbd>.",
                       "<strong>Paste this in the console</strong> (F12). If asked, type <kbd>allow pasting</kbd> first."),
    "col_copy": ("Copiar", "Copy"),
    "col_step3_html": ("<strong>Pega el resultado</strong> aquí. Se guarda en este navegador para la próxima vez "
                       "y no sale de él.",
                       "<strong>Paste the result</strong> here. It is kept in this browser for next time and never "
                       "leaves it."),
    "col_json": ("Resultado", "Result"),
    "col_view": ("Ver", "Show"),
    "col_file": ("O un archivo .json", "Or a .json file"),
    "col_drop": ("Arrastra aquí el .json o pulsa para elegirlo", "Drag the .json here or click to choose it"),

    # ------------------------------------------------------------ acerca
    "about_title": ("Info y aviso legal de {game} · {site}", "About and legal notice for {game} · {site}"),
    "about_desc": ("Aviso legal, créditos y licencias de {site}, tier list de {game}.",
                   "Legal notice, credits and licences for {site}, a {game} tier list."),
    "about_h1": ("Info de {game}", "About {game}"),
    "about_credits_h": ("Créditos", "Credits"),
    "about_sprites_h": ("Artistas de SpriteCollab", "SpriteCollab artists"),
    "about_sprites_html": (
        '<a href="{url}" rel="noopener">{source}</a>, licencia <a href="{lic_url}" rel="noopener">{lic}</a>.',
        '<a href="{url}" rel="noopener">{source}</a>, license <a href="{lic_url}" rel="noopener">{lic}</a>.'),
    "about_icons_h": ("Iconos y letras", "Icons and fonts"),
    "about_icons_html": (
        'Iconos: <a href="{url}" rel="noopener">{author}</a> ({title}), '
        '<a href="{lic_url}" rel="noopener">{lic}</a>. Glifos de tipo: del juego, licencia MIT.',
        'Icons: <a href="{url}" rel="noopener">{author}</a> ({title}), '
        '<a href="{lic_url}" rel="noopener">{lic}</a>. Type glyphs: from the game, MIT license.'),
    "about_font_html": (
        'Letras: <a href="https://github.com/eifetx/Pixelify-Sans" rel="noopener">Pixelify Sans</a> en títulos y '
        '<a href="https://github.com/googlefonts/zen-kakugothic" rel="noopener">Zen Kaku Gothic New</a> en el texto y los números, SIL OFL 1.1 '
        '(<a href="{root}fonts/OFL.txt">Pixelify</a>, <a href="{root}fonts/ZenKakuGothicNew-OFL.txt">Zen Kaku Gothic New</a>).',
        'Fonts: <a href="https://github.com/eifetx/Pixelify-Sans" rel="noopener">Pixelify Sans</a> for titles and '
        '<a href="https://github.com/googlefonts/zen-kakugothic" rel="noopener">Zen Kaku Gothic New</a> for text and numbers, SIL OFL 1.1 '
        '(<a href="{root}fonts/OFL.txt">Pixelify</a>, <a href="{root}fonts/ZenKakuGothicNew-OFL.txt">Zen Kaku Gothic New</a>).'),

    # ------------------------------------------------------------ 404
    "nf_title": ("Página no encontrada · {game} · {site}", "Page not found · {game} · {site}"),
    "nf_h1": ("Página no encontrada", "Page not found"),
    "nf_p_html": ('<a href="/index.html">Volver a la tier list</a> · <a href="/en/index.html">Back to the tier list</a>',
                  '<a href="/en/index.html">Back to the tier list</a> · <a href="/index.html">Volver a la tier list</a>'),

    # ------------------------------------------------------------ método
    "met_title": ("Método del ranking de {game} · {site}", "Ranking method for {game} · {site}"),
    "met_desc": ("Cómo se calcula el ranking de {game}: {sims} partidas simuladas por Pokémon con un bot, una nota de tiempo, daño y bajas, "
                 "repetida {reps} veces. Sin nota de ficha.",
                 "How the {game} ranking is calculated: {sims} simulated games per Pokémon with a bot, a score from time, damage and kills, "
                 "repeated {reps} times. No sheet score."),
    "met_h1": ("Método del ranking de {game}", "Ranking method for {game}"),
    "met_lede": ("Cada Pokémon de {game} recibe un puesto del 1 al 966 y un tier. Sale solo de partidas simuladas: "
                 "un bot juega partidas completas con cada uno y el puesto ordena sus notas. Como una nota sola puede engañar, "
                 "el orden se repite {reps} veces.",
                 "Each Pokémon in {game} gets a rank from 1 to 966 and a tier. It comes only from simulated games: "
                 "a bot plays full games with each one and the rank orders their scores. Since one score can mislead, "
                 "the order is repeated {reps} times."),
    "met_steps_aria": ("Pasos del cálculo", "Calculation steps"),
    "met_more": ("Pasos y gráficos detallados", "Detailed steps and charts"),
    "met_step_1_h": ("Simular", "Simulate"),
    "met_step_1": ("Un bot juega partidas completas con cada Pokémon en un simulador que sigue el código del juego. Da vueltas "
                   "alrededor de la horda para que los disparos, los golpes y los orbes den en el blanco, esquiva los ataques "
                   "avisados y recoge los orbes. Cada Pokémon juega {sims} partidas con semillas distintas, con un tope de "
                   "{cap} segundos.",
                   "A bot plays full games with each Pokémon in a simulator that follows the game's code. It circles the "
                   "horde so shots, hits and orbs connect, dodges telegraphed attacks and picks up orbs. Each Pokémon plays "
                   "{sims} games with different seeds, capped at {cap} seconds."),
    "met_step_2_h": ("Puntuar", "Score"),
    "met_step_2": ("Cada partida vale el tiempo que aguanta vivo, multiplicado por la raíz de dos cosas: el daño por segundo y las "
                   "bajas por minuto. Las dos se saturan: a unos {dps} de daño por segundo o {kpm} bajas por minuto ya se ha "
                   "llegado a la mitad, y a partir de ahí cada punto extra pesa menos. Una partida sin daño vale 0, así que "
                   "aguantar sin pelear no sube puestos.",
                   "A game is worth the time it stays alive, multiplied by the square root of two things: damage per second "
                   "and kills per minute. Both saturate: at about {dps} damage per second or {kpm} kills per minute you are "
                   "halfway there, and past that every extra point counts for less. A game with no damage is worth 0, so "
                   "surviving without fighting does not climb the ranking."),
    "met_step_3_h": ("Elegir el ataque", "Pick the move"),
    "met_step_3": ("Se prueba, uno por uno, cada ataque que el Pokémon puede aprender. El mejor ataque de daño es el que sale "
                   "en su ficha; si dos empatan dentro del margen de error, gana el que más sobrevive, luego el que más "
                   "derrota. El grupo de ataques sigue unas reglas fijas de build, que están más abajo.",
                   "Every move the Pokémon can learn is tried, one by one. The best damaging move is the one on its page; "
                   "if two tie within the margin of error, the one that survives longer wins, then the one with more "
                   "kills. The move group follows fixed build rules, listed below."),
    "met_step_4_h": ("Repetir {reps} veces", "Repeat {reps} times"),
    "met_step_4": ("Cada nota tiene un margen de error, que se mide con las propias partidas. En cada repetición, la nota "
                   "de cada Pokémon cae en un punto al azar dentro de su margen y se ordenan los 966. Si dos márgenes se "
                   "solapan, es un empate, no una diferencia.",
                   "Each score has a margin of error, measured from the games themselves. In every repeat, each Pokémon's "
                   "score lands on a random point inside its margin and all 966 are sorted. If two margins overlap, that "
                   "is a tie, not a difference."),
    "met_step_5_h": ("Puesto y rango", "Rank and range"),
    "met_step_5": ("El puesto final es la mediana de las posiciones de esas repeticiones. El rango habitual de cada ficha va "
                   "del percentil 10 al 90 de esas posiciones.",
                   "The final rank is the median of the positions across those repeats. The usual range on each page runs "
                   "from the 10th to the 90th percentile of those positions."),
    "met_step_6_h": ("Tier", "Tier"),
    "met_step_6": ("Los puestos se reparten en tiers de tamaño fijo, en orden: {sizes}. No hay requisitos de entrada: "
                   "ninguna ficha de estadísticas, de tipos o de tamaño mueve el puesto, solo cuenta el simulador.",
                   "Ranks are split, in order, into tiers of fixed size: {sizes}. There are no entry requirements: "
                   "no stats, type or size sheet moves the rank, only the simulator counts."),
    "pipe_title": ("Del dato al tier", "From data to tier"),
    "pipe_1": ("Simular", "Simulate"),
    "pipe_2": ("Puntuar", "Score"),
    "pipe_3": ("Elegir ataque", "Pick the move"),
    "pipe_4": ("Repetir ×{reps}", "Repeat ×{reps}"),
    "pipe_5": ("Puesto y rango", "Rank and range"),
    "pipe_6": ("Tier", "Tier"),
    "pipe_alt": ("Pasos del cálculo: ", "Calculation steps: "),
    "met_rules_h": ("Reglas de build", "Build rules"),
    "met_rules": ("No hay reglas a mano: ningún Pokémon tiene ataques prohibidos ni un factor contra el cuerpo a cuerpo. Un grupo "
                  "ocupa como máximo cuatro huecos y lleva al menos dos ataques; Sustituto cuenta como ataque. Los grupos pueden "
                  "mezclar ataques físicos y especiales con cualquier potenciador (Danza Espada, Danza Dragón, Maquinación, "
                  "Fortaleza, Agilidad). Gana el grupo con la nota más alta del simulador.",
                  "There are no hand-made rules: no Pokémon has banned moves or a factor against melee. A group takes at most "
                  "four slots and holds at least two attacks; Substitute counts as an attack. Groups can mix physical and "
                  "special attacks with any boost (Swords Dance, Dragon Dance, Nasty Plot, Harden, Agility). The group with "
                  "the highest simulator score wins."),
    "met_check_h": ("Cómo se comprueba", "How it is checked"),
    "met_check": ("El motor está escrito dos veces, en JavaScript y en Rust, y en su modo básico un test comprueba que dan el mismo "
                  "resultado paso a paso. Las fórmulas de daño, el modo de tipo único y otras reglas se comparan con las "
                  "funciones del propio juego, y los combates de prueba se repiten con el código del juego descargado "
                  "(commit {sha}). Todo está en el repositorio, junto a los datos.",
                  "The engine is written twice, in JavaScript and in Rust, and in its basic mode a test checks that they "
                  "give the same result step by step. Damage formulas, the single-type bonus and other rules are compared "
                  "against the game's own functions, and test fights are replayed with the game's downloaded code "
                  "(commit {sha}). It is all in the repository, next to the data."),
    "tiers_title": ("Tamaño de cada tier", "Size of each tier"),
    "tiers_alt": ("Pokémon por tier: ", "Pokémon per tier: "),
    "agree_title": ("Qué medida se parece más al ranking", "Which measure is closest to the ranking"),
    "agree_alt": ("Parecido con el puesto final: ", "Closeness to the final rank: "),
    "rib_title": ("Cuánto se mueve cada puesto", "How much each rank moves"),
    "rib_lede": ("Cada trazo es un Pokémon. Su posición horizontal es su puesto final, y el trazo marca dónde cayó "
                 "en las 2.000 repeticiones (entre el 10 % y el 90 % de los casos). Trazo corto: puesto firme. "
                 "El rango habitual mide unos {s} puestos en el tier S y {c} en el C.",
                 "Each stroke is a Pokémon. Its horizontal position is its final rank, and the stroke shows where it "
                 "landed across the 2,000 repeats (between the 10th and 90th percentile). Short stroke: firm rank. "
                 "The usual range is about {s} places in tier S and {c} in tier C."),
    "rib_x": ("puesto final", "final rank"),
    "rib_y": ("puesto en las repeticiones", "rank in the repeats"),
    "rib_alt": ("Margen de puestos de cada Pokémon. Ancho típico por tier: ",
                "Rank range of each Pokémon. Typical width per tier: "),
    "rib_alt_item": ("{t} {m} puestos", "{t} {m} places"),
    "stab_title": ("Se queda en su tier", "Stays in its tier"),
    "stab_alt": ("Pokémon que se quedan en su tier: ", "Pokémon that stay in their tier: "),
    "reps_title": ("2.000 repeticiones", "2,000 repeats"),
    "reps_lede": ("Cada punto es un Pokémon de ejemplo. La sombra es su rango habitual (del percentil 10 al 90) y la "
                  "raya roja, su puesto final. En cada repetición cae en un punto distinto de ese rango.",
                  "Each dot is an example Pokémon. The shade is its usual range (10th to 90th percentile) and the red "
                  "line its final rank. Each repeat lands it somewhere else within that range."),
    "reps_pause": ("Pausa", "Pause"),
    "reps_play": ("Seguir", "Play"),
    "reps_count": ("{n} / {total}", "{n} / {total}"),
    "arena_title": ("Así se ve una partida simulada", "What a simulated game looks like"),
    "arena_lede": ("Ilustración, no datos del ranking. Así juega cada Pokémon las partidas simuladas: esquiva, dispara "
                   "a los enemigos que se acercan y aguanta lo que puede.",
                   "Illustration, not ranking data. This is how each Pokémon plays the simulated games: it dodges, "
                   "shoots the enemies that come close, and survives as long as it can."),
    "arena_time": ("tiempo", "time"),
    "arena_kills": ("derrotados", "defeated"),
    "arena_alt": ("Animación de una partida simulada. Un Pokémon esquiva y dispara a enemigos que se acercan.",
                  "Animation of a simulated game. A Pokémon dodges and fires at approaching enemies."),
    "met_limits_h": ("Límites", "Limits"),
    "met_lim_1": ("Es un bot, no una persona: juega peor el cuerpo a cuerpo y no busca camino hasta las grietas, "
                  "solo cuenta el tiempo de ir andando.",
                  "It is a bot, not a person: it plays melee worse and does not path to rifts, it only counts the time "
                  "spent walking."),
    "met_lim_2": ("El grupo de ataques no se vincula hasta ganar una grieta, como en el juego, y un compañero de sinergia como "
                  "Hex no ataca antes.",
                  "The move group does not bond until a rift is won, as in the game, and a synergy partner such as Hex does "
                  "not attack before then."),
    "met_lim_3": ("Los números son estimaciones de {sims} partidas por Pokémon; por eso cada ficha lleva su rango habitual.",
                  "The numbers are estimates from {sims} games per Pokémon; that is why each page shows its usual range."),
    "met_lim_4": ("No se ha contrastado con partidas reales de jugadores, solo con las reglas y el código del juego.",
                  "It has not been checked against real player games, only against the game's rules and code."),
    # ------------------------------------------------------------ navegación de las herramientas
    "nav_planificador": ("Planificador", "Build planner"),
    "guide_finder": ("Buscador por tipos", "Type finder"),
    "guide_planner": ("Planificador de build", "Build planner"),
    "stat_atk": ("Ataque", "Attack"),
    "stat_spd": ("Velocidad", "Speed"),
    "stat_def": ("Defensa", "Defense"),
    "stat_regen": ("Regeneración", "Regeneration"),
    "tool_noscript": ("Esta herramienta necesita JavaScript.", "This tool needs JavaScript."),
    "tool_load": ("Cargando datos…", "Loading data…"),
    "tool_fail": ("No se pudieron cargar los datos. Recarga la página.", "The data did not load. Reload the page."),

    # ------------------------------------------------------------ nota del Repertorio
    "rep_note": ("Repertorio te da un segundo ataque al azar y no se puede deshacer.",
                 "Repertoire gives you a random second attack and can't be undone."),

    # ------------------------------------------------------------ potenciadores (pasivas)
    "pv_buff_h": ("Potenciadores: el tope de dos y la categoría", "Boosts: the two-boost cap and the category"),
    "pv_buff_lede": ("Un potenciador no hace daño: sube una estadística mientras dura. Con dos potenciadores en el grupo, "
                     "las cartas de movimiento nuevo ya no ofrecen más potenciadores. Las mejoras de los que ya tienes siguen saliendo.",
                     "A boost does no damage: it raises one stat while it lasts. With two boosts in your group, new-move cards "
                     "stop offering boosts. Upgrades for the boosts you already have still show up."),
    "pv_buff_th_boost": ("Potenciador", "Boost"),
    "pv_buff_th_stat": ("Sube", "Raises"),
    "pv_buff_th_cd": ("Recarga", "Cooldown"),
    "pv_buff_th_dur": ("Dura", "Lasts"),
    "pv_buff_th_max": ("Máximo sin mejoras", "Max, no upgrades"),
    "pv_buff_th_top": ("Con todas las mejoras", "Fully upgraded"),
    "pv_buff_top": ("{amt}, {dur} s", "{amt}, {dur} s"),
    "pv_buff_cat_phys": ("ataque físico", "physical attack"),
    "pv_buff_cat_spec": ("ataque especial", "special attack"),
    "pv_buff_stat_spd": ("velocidad", "speed"),
    "pv_buff_stat_def": ("defensa", "defense"),
    "pv_buff_stat_regen": ("regeneración", "regeneration"),
    "pv_buff_r1": ("Sin mejoras, cada potenciador dura 7 s (Acua Aro, 8 s); la mejora de duración lo alarga un 50 %. "
                   "Si vuelve a salir antes de que acabe, el tiempo empieza de nuevo.",
                   "Without upgrades each boost lasts 7 s (Aqua Ring, 8 s); the duration upgrade adds 50%. "
                   "If it fires again before it ends, the timer starts over."),
    "pv_buff_r2": ("Danza Espada y Danza Dragón solo suben el ataque físico y comparten el contador de acumulaciones. "
                   "El porcentaje por acumulación lo pone la última que se lanza: no se suman.",
                   "Swords Dance and Dragon Dance raise only physical attack and share the stack counter. The percentage per stack "
                   "is set by the last one to fire: they don't add up."),
    "pv_buff_r3": ("Maquinación sube solo el ataque especial y tiene su propio contador. En un grupo mixto puedes llevar una danza "
                   "física y Maquinación, y cada una sube su lado.",
                   "Maquinación raises only special attack and has its own counter. In a mixed group you can take a physical dance "
                   "and Maquinación, and each one raises its side."),
    "pv_buff_link": ("Arma tu grupo en el planificador de build", "Build your group in the build planner"),
    "pv_buff_cap_note": ("Valores del juego en el commit {commit}.", "Values from the game at commit {commit}."),

    # ------------------------------------------------------------ buscador por tipos
    "tf_title": ("Buscador por tipos de {game} · {site}", "Type finder for {game} · {site}"),
    "tf_desc": ("Qué Pokémon de {game} tienen cada combinación de tipos, a qué tipos son débiles y cuánto pega cada uno con físicos y especiales.",
                "Which {game} Pokémon have each type combination, which types they are weak to, and how hard each one hits with physical and special moves."),
    "tf_h1": ("Buscador por tipos", "Type finder"),
    "tf_lede": ("Elige uno o dos tipos. Te digo qué Pokémon los tienen y qué ataques les pegan fuerte.",
                "Pick one or two types. See which Pokémon have them and which attacks hit them hardest."),
    "tf_pick_h": ("Tipos", "Types"),
    "tf_rule": ("Con un tipo salen todos los que lo tienen. Con dos, solo los que tienen exactamente esos dos.",
                "With one type you get every Pokémon that has it. With two, only the ones with exactly those two."),
    "tf_clear": ("Quitar tipos", "Clear types"),
    "tf_start": ("Elige un tipo para ver sus debilidades.", "Pick a type to see its weaknesses."),
    "tf_weak_h": ("Debilidades", "Weaknesses"),
    "tf_g_x24": ("Doble debilidad", "Double weakness"),
    "tf_g_weak": ("Débil", "Weak"),
    "tf_g_res": ("Resiste", "Resists"),
    "tf_g_imm": ("Inmune", "Immune"),
    "tf_none": ("Ni debilidades ni resistencias.", "No weaknesses or resistances."),
    "tf_count": ("{n} Pokémon", "{n} Pokémon"),
    "tf_empty": ("Ningún Pokémon tiene esa combinación.", "No Pokémon has that combination."),
    "tf_card_pa": ("Físico ×{v}", "Physical ×{v}"),
    "tf_card_sa": ("Especial ×{v}", "Special ×{v}"),
    "tf_card_double": ("Doble debilidad: {types}", "Double weakness: {types}"),
    "tf_stats_note": ("pa y sa son el multiplicador de sus ataques físicos y especiales, sacado de sus estadísticas base. "
                      "Para el juego, su lado fuerte es el mayor de los dos.",
                      "pa and sa are the multipliers for its physical and special attacks, taken from its base stats. "
                      "For the game, its strong side is the higher of the two."),
    "tf_table_h": ("Tabla de tipos", "Type chart"),
    "tf_table_lede": ("Con un solo tipo: qué tipos le pegan fuerte y a cuáles resiste. Son los multiplicadores del juego.",
                      "One type at a time: which types hit it hard and which it resists. These are the game's multipliers."),
    "tf_col_type": ("Tipo", "Type"),
    "tf_col_weak": ("Débil a", "Weak to"),
    "tf_col_res": ("Resiste a", "Resists"),
    "tf_col_imm": ("Inmune a", "Immune to"),
    "tf_how_h": ("Cómo se calcula", "How it is calculated"),
    "tf_how": ("El juego suaviza la tabla de tipos: super efectivo es ×1,6 (no ×2), poco efectivo ×0,6 (no ×0,5) e inmune "
               "×0,3 (no ×0). Con dos tipos los multiplicadores se multiplican y el total se queda entre ×0,3 y ×2,4. "
               "Por eso una doble debilidad vale ×2,4 y no más.",
               "The game softens the type chart: super effective is ×1.6 (not ×2), not very effective ×0.6 (not ×0.5), "
               "and immune ×0.3 (not ×0). With two types the multipliers multiply, and the total stays between ×0.3 and "
               "×2.4. That is why a double weakness is ×2.4 and no more."),
    "tf_source": ("Tabla: <a href=\"{url}\" rel=\"noopener\">js/data/types.js</a> del juego. pa y sa: "
                  "<a href=\"{stats}\" rel=\"noopener\">js/data/pokedex.js</a>. Commit {sha}.",
                  "Chart: <a href=\"{url}\" rel=\"noopener\">js/data/types.js</a> in the game. pa and sa: "
                  "<a href=\"{stats}\" rel=\"noopener\">js/data/pokedex.js</a>. Commit {sha}."),

    # ------------------------------------------------------------ planificador de build
    "bp_title": ("Planificador de build de {game} · {site}", "Build planner for {game} · {site}"),
    "bp_desc": ("Arma el grupo vinculado, el objeto y las cartas de un Pokémon de {game}. Empieza con su build recomendada "
                "y comparte el enlace.",
                "Build the bonded group, item and cards for a {game} Pokémon. Starts from its recommended build and shares as a link."),
    "bp_h1": ("Planificador de build", "Build planner"),
    "bp_lede": ("Elige un Pokémon. Empieza con su build recomendada: cambia lo que quieras y copia el enlace.",
                "Pick a Pokémon. It starts on its recommended build: change anything you like and copy the link."),
    "bp_pick_h": ("Pokémon", "Pokémon"),
    "bp_pick_ph": ("Nombre o número", "Name or number"),
    "bp_side": ("Pega más con: {side}", "Hits harder with: {side}"),
    "bp_group_h": ("Grupo vinculado", "Bonded group"),
    "bp_group_note": ("Hasta 4 movimientos de su grupo: los normales y los de sus tipos.",
                      "Up to 4 moves from its pool: normal moves and moves of its types."),
    "bp_slot": ("Hueco {n}", "Slot {n}"),
    "bp_pick_move": ("Elige un movimiento", "Pick a move"),
    "bp_cat_phys": ("Físico", "Physical"),
    "bp_cat_spec": ("Especial", "Special"),
    "bp_cat_boost": ("Potenciador", "Boost"),
    "bp_cat_phys_adj": ("físicos", "physical"),
    "bp_cat_spec_adj": ("especiales", "special"),
    "bp_boost_count": ("Potenciadores: {n} de 2", "Boosts: {n} of 2"),
    "bp_boost_max": ("Máximo 2 potenciadores. Quita uno para cambiarlo.", "Max 2 boosts. Remove one to change it."),
    "bp_mismatch_none": ("{boost} solo sube ataques {cat}, y este grupo no tiene ninguno.",
                         "{boost} only raises {cat} attacks, and this group has none."),
    "bp_mismatch_some": ("{boost} solo sube {n} de tus {total} ataques.", "{boost} only raises {n} of your {total} attacks."),
    "bp_both": ("Danza Espada y Danza Dragón comparten el contador de ataque físico: no suman, y solo cuenta la última que se lanza. "
                "No las lleves juntas.",
                "Swords Dance and Dragon Dance share the physical attack counter: they don't add up, and only the last one to fire "
                "counts. Don't take both."),
    "bp_item_h": ("Objeto", "Item"),
    "bp_item_none": ("Sin objeto", "No item"),
    "bp_item_best": ("Recomendado", "Recommended"),
    "bp_cards_h": ("Cartas, en orden", "Cards, in order"),
    "bp_cards_note": ("Por orden de prioridad, sin repetir. Cómo se ordenan, en Pasivas.",
                      "In priority order, no repeats. How they are ranked is on Passives."),
    "bp_card_n": ("{n}.ª carta", "Card {n}"),
    "bp_card_none": ("—", "—"),
    "bp_result_h": ("Tu build", "Your build"),
    "bp_cover": ("Super efectivo contra el {super} de los Pokémon. Al menos neutral contra el {neutral}.",
                 "Super effective against {super} of Pokémon. At least neutral against {neutral}."),
    "bp_none_attack": ("Sin ataques elegidos.", "No attacks picked."),
    "bp_link": ("Enlace de esta build", "Link to this build"),
    "bp_copy": ("Copiar enlace", "Copy link"),
    "bp_copied": ("Enlace copiado", "Link copied"),
    "bp_reset": ("Restaurar la recomendada", "Restore recommended"),
    "bp_rank": ("Puesto {rank} de {total} · tier {tier}", "Rank {rank} of {total} · tier {tier}"),
    "bp_open_sheet": ("Ver su ficha", "See its sheet"),
    "bp_boost_guide": ("Cómo funcionan los potenciadores", "How boosts work"),
    "bp_how": ("Cada ataque es físico o especial, según la lista de movimientos del juego. Danza Espada y Danza Dragón suben "
               "solo el físico y comparten contador; Maquinación sube el especial. Cada potenciador dura 7 s. Con dos potenciadores, "
               "las cartas de movimiento nuevo ya no ofrecen más.",
               "Each attack is physical or special, according to the game's move list. Swords Dance and Dragon Dance raise only "
               "physical attack and share a counter; Maquinación raises special attack. Each boost lasts 7 s. With two boosts, "
               "new-move cards stop offering more."),
    "bp_source": ("Movimientos: <a href=\"{url}\" rel=\"noopener\">js/data/moves.js</a>. pa y sa: "
                  "<a href=\"{stats}\" rel=\"noopener\">js/data/pokedex.js</a>. Commit {sha}.",
                  "Moves: <a href=\"{url}\" rel=\"noopener\">js/data/moves.js</a> in the game. pa and sa: "
                  "<a href=\"{stats}\" rel=\"noopener\">js/data/pokedex.js</a>. Commit {sha}."),
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


MONTHS = (("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
          ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))


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
        return STR[key][self.idx].format(**{"game": GAME_NAME, "site": SITE_NAME, **kw})

    def t_raw(self, key: str) -> str:
        """El texto con sus marcadores sin rellenar, para las plantillas que se completan en el navegador."""
        return STR[key][self.idx]

    def num(self, n: int | float) -> str:
        s = f"{n:,.0f}"
        return s if self.en else s.replace(",", ".")

    def dec(self, x: float, d: int = 1) -> str:
        s = f"{x:.{d}f}"
        return s if self.en else s.replace(".", ",")

    def date(self, iso: str) -> str:
        """'2026-10-19' -> '19 oct 2026' en español y 'Oct 19, 2026' en inglés."""
        y, m, d = (int(x) for x in iso[:10].split("-"))
        month = MONTHS[self.idx][m - 1]
        return f"{month} {d}, {y}" if self.en else f"{d} {month} {y}"

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
