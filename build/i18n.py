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
    "nav_tiers": ("Tiers", "Tiers"),
    "nav_novedades": ("Novedades", "Updates"),
    "nav_metodo": ("Método", "Method"),
    "nav_ataques": ("Ataques", "Moves"),
    "nav_objetos": ("Objetos", "Items"),
    "nav_pasivas": ("Pasivas", "Passives"),
    "nav_gachas": ("Gacha", "Gacha"),
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
    "index_desc": ("Tier list de los {n} Pokémon de {game}, hecha con {games} partidas simuladas con el código del juego. Código y datos abiertos en GitHub.",
                   "Tier list of the {n} Pokémon in {game}, built from {games} runs simulated with the game's code. Code and data open on GitHub."),
    "fresh": ("Actualizado al parche del {date} ({sha})", "Updated to the {date} patch ({sha})"),
    "guides_h": ("Más listas", "More lists"),
    "guide_best": ("Mejores Pokémon", "Best Pokémon"),
    "guide_legendary": ("Legendarios", "Legendaries"),
    "guide_tierlist": ("Tier list completa", "Full tier list"),
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
    "filters_btn": ("Filtros y orden", "Filters and sorting"),
    "nav_more": ("Más", "More"),
    "about_value_html": (
        'Tier list de {game} hecha con {games} partidas simuladas con el código del juego, no con fórmulas de stats. Código, '
        'simulador y datos abiertos en <a href="{repo}" rel="noopener">GitHub</a>, para que cualquiera lo compruebe.',
        'Tier list of {game} built from {games} runs simulated with the game\'s code, not from stat formulas. Code, simulator '
        'and data open on <a href="{repo}" rel="noopener">GitHub</a>, so anyone can check it.'),
    "home_title": ("Mejores Pokémon de {game}: tier list de {n} | {site}",
                   "Best Pokémon in {game}: tier list of {n} | {site}"),
    "home_desc": ("Tier list de {game} con los {n} Pokémon ordenados por partidas simuladas, al día con el parche del {date}. "
                  "Ahora mismo en lo más alto: {top}.",
                  "{game} tier list with all {n} Pokémon ranked from simulated games, up to date with the {date} patch. "
                  "Right now at the top: {top}."),
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
    "fh_title": ("{name} en {game}: tier {tier}, mejor build y ataques | {site}",
                 "{name} in {game}: {tier} tier, best build and moves | {site}"),
    "fh_desc_buffs": ("{name} es tier {tier} en {game}: puesto {rank} de {total}. Mejor build: {attacks}, con {buffs}. "
                      "Sale en el banner {banner}.",
                      "{name} is {tier} tier in {game}: rank {rank} of {total}. Best build: {attacks}, with {buffs}. "
                      "It is on the {banner} banner."),
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
    "pager_aria": ("Pokémon vecinos", "Neighbouring Pokémon"),
    "dex_no": ("nº {dex}", "no. {dex}"),
    "tpl_title": ("Fichas de los Pokémon de {game} | {site}", "Pokémon pages of {game} | {site}"),
    "tpl_desc": ("Las {n} fichas de {game}, una por Pokémon: tier, por qué, builds y cómo conseguirlo.",
                 "All {n} {game} pages, one per Pokémon: tier, why, builds and how to get it."),
    "tpl_h1": ("Fichas de los Pokémon de {game}", "Pokémon pages of {game}"),
    "tpl_lede": ("Cada uno de los {n} Pokémon tiene su ficha con el tier, el puesto, por qué está ahí, sus "
                 "builds y cómo conseguirlo. Elige uno de la lista.",
                 "Each of the {n} Pokémon has its own page with its tier, rank, why it is there, its "
                 "builds and how to get it. Pick one from the list."),

    # ------------------------------------------------------------ gráficos de la ficha
    "cb_pa": ("Ataque físico", "Physical attack"),
    "cb_sa": ("Ataque especial", "Special attack"),
    "cb_df": ("Defensa", "Defense"),
    "cb_sd": ("Def. Especial", "Sp. Def."),
    "cb_kind_phys": ("Atacante físico", "Physical attacker"),
    "cb_kind_spec": ("Atacante especial", "Special attacker"),
    "bd_start_with": ("Empieza con", "Start with"),
    "build_default_start": ("De serie: {move}; cámbialo con Movimiento inicial (400 monedas)",
                            "Default: {move}; change it with Starting Move (400 coins)"),
    "bd_melee": ("Cuerpo a cuerpo", "Melee"),
    "bd_ranged": ("A distancia", "Ranged"),
    "bd_time": ("Tiempo", "Time"),
    "bd_dealt": ("Daño", "Damage"),
    "bd_kills": ("Bajas", "Kills"),
    "bd_score": ("Puntuación", "Score"),
    "bd_best": ("Puntúa más", "Scores higher"),
    "bd_tie": ("Puntúan igual.", "Both score the same."),
    "bd_gap_small": ("Solo un {pct} peor que la build {other}.", "Only {pct} below the {other} build."),
    "bd_gap": ("Un {pct} peor que la build {other}.", "{pct} below the {other} build."),
    "bd_other_melee": ("cuerpo a cuerpo", "melee"),
    "bd_other_ranged": ("a distancia", "ranged"),
    "bd_melee_note": ("Mientras un ataque cuerpo a cuerpo está activo, recibes un 25\u00a0% menos de daño.",
                      "While a melee move is active, you take 25% less damage."),
    "faq_a_build": ("{kind}: {attacks}, con {buffs}. Empieza con {start}.", "{kind}: {attacks}, with {buffs}. Start with {start}."),
    "faq_a_build_best": ("Puntúa más la build {kind}.", "The {kind} build scores higher."),
    "t_builds": ("Builds", "Builds"),
    "mv_tier_tip": ("Tier {t} en la tier list de ataques", "Tier {t} on the move tier list"),
    "pct_alt": ("Percentil {pct} de 100", "Percentile {pct} of 100"),
    "why_h": ("Por qué está en el puesto {rank}", "Why it ranks {rank}"),
    "why_note": ("Cuánto sube o baja su puntuación cada factor frente a un Pokémon en la media. La barra es su percentil.",
                 "How much each factor raises or lowers its score against an average Pokémon. The bar is its percentile."),
    "why_flat": ("Está cerca de la media en todo: ningún factor le mueve la puntuación más de un 2\u00a0%.",
                 "It is close to average in everything: no factor moves its score by more than 2%."),
    "why_atk_phys": ("Ataque físico ×{v}", "Physical attack ×{v}"),
    "why_atk_spec": ("Ataque especial ×{v}", "Special attack ×{v}"),
    "why_atk_mix": ("Ataque físico y especial ×{v} de media", "Physical and special attack ×{v} on average"),
    "why_group": ("Sus ataques: {moves}", "Its moves: {moves}"),
    "why_hp": ("PS {v}", "HP {v}"),
    "why_df": ("Defensa {v}", "Defense {v}"),
    "why_sd": ("Def. Especial {v}", "Sp. Def. {v}"),
    "why_spd": ("Velocidad {v}", "Speed {v}"),
    "why_size": ("Tamaño: radio de {v} px", "Size: {v} px radius"),
    "why_types": ("Por sus tipos recibe ×{v} de daño", "Its types take ×{v} damage"),
    "surv_h": ("En la simulación", "In the simulation"),
    "surv_text": ("Un bot juega partidas de hasta {minutes} minutos sin objetos. Con la build {kind} aguanta {t} de "
                  "mediana; la mediana de los 966 es {med}. Sirve para comparar Pokémon, no es lo que durará tu partida.",
                  "A bot plays runs of up to {minutes} minutes with no items. With the {kind} build it lasts {t} on "
                  "median; the median of all 966 is {med}. It is for comparing Pokémon, not how long your run will last."),
    "surv_alt": ("{t}; la mediana de los 966 es {med} y el que más aguanta llega a {max}",
                 "{t}; the median of all 966 is {med} and the longest reaches {max}"),
    "st_h": ("Estadísticas en el juego", "In-game stats"),
    "st_hp": ("PS", "HP"),
    "st_spd": ("Velocidad", "Speed"),
    "st_size": ("Radio (px)", "Radius (px)"),
    "st_types": ("Daño recibido por tipos", "Damage taken by type"),
    "st_note": ("Valores del código del juego. La barra es el percentil entre los {n}: más larga, mejor.",
                "Values from the game code. The bar is the percentile among all {n}: longer is better."),
    "sort_by": ("Ordenar por", "Sort by"),
    "sort_rank": ("Puesto", "Rank"),
    "sort_name": ("Nombre", "Name"),
    "sort_dex": ("Nº Pokédex", "Pokédex no."),
    "sort_s": ("Tiempo que aguanta", "Survival time"),
    "sort_pa": ("Ataque físico", "Physical attack"),
    "sort_sa": ("Ataque especial", "Special attack"),
    "sort_df": ("Defensa", "Defense"),
    "sort_sd": ("Def. Especial", "Sp. Def."),
    "sort_hp": ("Vida", "HP"),
    "sort_spd": ("Velocidad", "Speed"),
    "sort_rad": ("Tamaño", "Size"),
    "sort_rar": ("Rareza", "Rarity"),
    "dir_asc": ("Menor primero", "Lowest first"),
    "dir_desc": ("Mayor primero", "Highest first"),
    "median": ("mediana", "median"),

    # ------------------------------------------------------------ listas de consulta (landing.py)
    "lp_top_h": ("Ranking", "Ranking"),
    "lp_best_title": ("Mejores Pokémon de {game} · {site}", "Best Pokémon in {game} · {site}"),
    "lp_best_h1": ("Mejores Pokémon de {game}", "Best Pokémon in {game}"),
    "lp_best_desc": ("Los {n} mejores Pokémon de {game} según la tier list simulada: {top}.",
                     "The {n} best Pokémon in {game} by the simulated tier list: {top}."),
    "lp_best_lede": ("Los mejores Pokémon de {game} son {top}. Los {n} primeros forman el tier S.",
                     "The best Pokémon in {game} are {top}. The first {n} make up tier S."),
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

    # ------------------------------------------------------------ ataques
    "ataques_title": ("Ataques de {game} · {site}", "Moves in {game} · {site}"),
    "ataques_desc": ("Tier list de los {n} ataques de {game}.", "Tier list of the {n} moves in {game}."),
    "ataques_h1": ("Ataques de {game}", "Moves in {game}"),
    "cat_physical": ("Ataques físicos", "Physical moves"),
    "cat_special": ("Ataques especiales", "Special moves"),
    "cat_groups": ("Mejores grupos", "Best groups"),
    "mv_lede": ("Cada ataque jugado solo por {refs} Pokémon de referencia de su clase, {seeds} partidas cada uno. "
                "1× es un ataque normal de su clase; 1,5× rinde un 50\u00a0% más.",
                "Each move played alone by {refs} reference Pokémon of its class, {seeds} runs each. "
                "1× is a typical move of its class; 1.5× does 50% better."),
    "mv_groups_lede": ("Los {n} mejores grupos de cuatro huecos por clase de atacante y build, jugados por las mismas "
                       "referencias. 1× es el grupo normal de su clase.",
                       "The top {n} four-slot groups per attacker class and build, played by the same reference "
                       "Pokémon. 1× is a typical group of its class."),
    "cat_stat": ("Potenciadores", "Boosts"),
    "mv_value": ("Valor", "Value"),
    "mv_typical": ("normal", "typical"),
    "mv_better": ("mejor", "better"),
    "mv_worse": ("peor", "worse"),
    "mv_search": ("Buscar ataque o tipo…", "Search a move or type…"),
    "mv_none": ("Ningún ataque coincide con la búsqueda.", "No move matches the search."),
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
    "mv_unranked": ("No hacen daño por sí solos, así que no tienen tier: cuentan dentro de los grupos.",
                    "They deal no damage on their own, so they have no tier: they count inside the groups."),
    "mv_read_h": ("Cómo leer las tarjetas", "How to read the cards"),
    "mv_stacks": ("Cada acumulación: {amt} de {stat}, hasta {n}", "Each stack: {amt} {stat}, up to {n}"),
    "mv_buff_max": ("Con las {ups} mejoras: {amt} por acumulación, hasta {n}, y dura {dur} s",
                    "With all {ups} upgrades: {amt} per stack, up to {n}, lasting {dur} s"),
    "mv_damage_h": ("Tipo de daño de cada ataque", "Damage type of each move"),
    "dmg_physical": ("Físico", "Physical"),
    "dmg_special": ("Especial", "Special"),
    "dmg_status": ("Estado", "Status"),
    "dmg_mix": ("Mixto", "Mixed"),
    "dmg_tip_physical": ("Ataque físico: pega con el Ataque", "Physical attack: deals damage with Attack"),
    "dmg_tip_special": ("Ataque especial: pega con el Ataque Especial", "Special attack: deals damage with Sp. Attack"),
    "dmg_tip_status": ("Potenciador: no hace daño", "Boost: deals no damage"),
    "rng_tip_melee": ("Cuerpo a cuerpo: el ataque te obliga a acercarte al enemigo",
                      "Melee: the attack makes you get close to the enemy"),
    "rng_tip_ranged": ("A distancia: el ataque pega desde lejos", "Ranged: the attack hits from far away"),
    "mv_range_h": ("Distancia de cada ataque", "Range of each move"),

    # ------------------------------------------------------------ objetos
    "obj_title": ("Objetos de {game} · {site}", "Items in {game} · {site}"),
    "obj_desc": ("Los objetos de {game} y qué hace cada uno según el código del juego.",
                 "The {game} items and what each one does according to the game code."),
    "obj_h1": ("Objetos de {game}", "Items in {game}"),
    "obj_lede": ("En {game} solo se lleva uno por partida: los cofres los sueltan y puedes cambiarlo. Aquí va lo que hace "
                 "cada uno según el código del juego; no los ordenamos porque la simulación no los usa.",
                 "In {game} you carry one per run: chests drop them and you can swap it. This is what each one does "
                 "according to the game code; we do not rank them because the simulation does not use them."),

    # ------------------------------------------------------------ pasivas
    "pv_title": ("Pasivas de {game} · {site}", "Passives in {game} · {site}"),
    "pv_desc": ("Las cartas de subida de nivel y los potenciadores de {game}: efecto, máximo y valores del juego.",
                "The level-up cards and boosts in {game}: effect, cap and game values."),
    "pv_h1": ("Pasivas de {game}", "Passives in {game}"),
    "pv_lede": ("Las cartas de subida de nivel y los potenciadores de {game}, tal como los define el código del juego.",
                "The level-up cards and boosts in {game}, as the game code defines them."),
    "pv_cards_h": ("Cartas de subida de nivel", "Level-up cards"),
    "pv_th_card": ("Carta", "Card"),
    "pv_th_effect": ("Efecto", "Effect"),
    "pv_th_max": ("Máximo", "Max"),
    "pv_no_max": ("sin tope", "no cap"),
    "pv_cards_note": ("Efecto y máximo de veces de levelup.js, en el orden del juego. La reducción de daño de Coraza no pasa "
                      "del 70\u00a0%. No las ordenamos: la simulación las coge con una prioridad fija y no mide cuál conviene.",
                      "Effect and max picks from levelup.js, in the game's order. Armor's damage reduction stops at 70%. "
                      "We do not rank them: the simulation takes them in a fixed order and does not measure which is better."),

    # ------------------------------------------------------------ gacha
    "gachas_title": ("Gacha de {game} · {site}", "Gacha for {game} · {site}"),
    "gachas_desc": ("Qué banner de gacha de {game} da más Pokémon top.",
                    "Which {game} gacha banner gives the most top Pokémon."),
    "gachas_h1": ("Gacha y colección de {game}", "Gacha and collection for {game}"),
    "gc_tabs": ("Gacha o colección", "Gacha or collection"),
    "tab_gacha": ("Gacha", "Gacha"),
    "tab_coleccion": ("Mi colección", "My collection"),
    "g_yours": ("Ver qué te falta en cada banner", "See what you're missing in each banner"),
    "g_one_in": ("1 de cada {n} es top", "1 in {n} is top"),
    "g_best": ("Mejor banner", "Best banner"),
    "g_worst": ("Mejor no", "Skip"),
    "g_pulls": ("Mejores Pokémon de {name}", "Best Pokémon in {name}"),

    # ------------------------------------------------------------ colección
    "col_title": ("Mi colección de {game} · {site}", "My {game} collection · {site}"),
    "col_desc": ("Mira tu colección de {game} por tier.", "See your {game} collection by tier."),
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
    "m3_desc": ("Cómo se hace el ranking de {game}: {games} partidas simuladas con el código del juego, en tres fases y sin reglas a mano.",
                "How the {game} ranking is made: {games} simulated runs with the game's code, in three phases and with no hand-made rules."),
    "m3_notice_h": ("Hemos mejorado el ranking.", "We have improved the ranking."),
    "m3_notice": ("Ahora todo sale de simular partidas: cada Pokémon juega con la mejor build que encontró la simulación, "
                  "sin reglas escritas a mano. Muchos puestos han cambiado.",
                  "Everything now comes from simulated runs: each Pokémon plays with the best build the simulation found, "
                  "with no hand-written rules. Many ranks have changed."),
    "m3_notice_link": ("Cómo lo hacemos", "How we do it"),
    "m3_lede": ("{games} partidas de un bot con el código del juego, de hasta {minutes} minutos cada una, en tres fases.",
                "{games} runs by a bot using the game's code, up to {minutes} minutes each, in three phases."),
    "m3_k_games": ("Partidas", "Runs"),
    "m3_k_attacks": ("Ataques", "Moves"),
    "m3_k_groups": ("Grupos probados", "Groups tried"),
    "m3_k_mons": ("Pokémon", "Pokémon"),
    "m3_p1_h": ("1. Tier list de ataques", "1. Move tier list"),
    "m3_p1": ("Cada uno de los {attacks} ataques juega solo en {refs} Pokémon de referencia de su clase (físicos o especiales, "
              "con vida, defensas, tamaño y velocidad variados), {seeds} partidas por referencia: {games} partidas. "
              "Su cifra compara con un ataque normal de su clase, así que no pesa qué Pokémon lo usa.",
              "Each of the {attacks} moves plays alone on {refs} reference Pokémon of its class (physical or special, "
              "with varied HP, defenses, size and speed), {seeds} runs per reference: {games} runs. "
              "Its figure compares it with a typical move of its class, so it does not depend on who uses it."),
    "m3_p2_h": ("2. Grupos de ataques", "2. Move groups"),
    "m3_p2": ("Los mejores ataques se combinan en grupos de cuatro huecos (tres ataques y un potenciador, o dos y dos), "
              "vinculados desde el principio y jugados por las mismas referencias. {groups} grupos en tres rondas de "
              "{s1}, {s2} y {s3} partidas por referencia, con semillas nuevas en cada ronda: {games} partidas.",
              "The best moves are combined into four-slot groups (three moves and a boost, or two and two), bonded from "
              "the start and played by the same reference Pokémon. {groups} groups over three rounds of {s1}, {s2} and "
              "{s3} runs per reference, with new seeds each round: {games} runs."),
    "m3_p3_h": ("3. La build de cada Pokémon", "3. Each Pokémon's build"),
    "m3_p3": ("Cada Pokémon prueba sus propios grupos, con los ataques que puede aprender. Lo que se aprendió en la fase 2 "
              "elige los más prometedores: {g1} grupos con {s1} partidas, los {g2} mejores con {s2} y los {g3} finalistas "
              "con {s3}, siempre con semillas nuevas. Se queda con su mejor build cuerpo a cuerpo y su mejor a distancia. "
              "{games} partidas.",
              "Each Pokémon tries its own groups, with the moves it can learn. What phase 2 learned picks the most "
              "promising ones: {g1} groups with {s1} runs, the best {g2} with {s2} and the {g3} finalists with {s3}, "
              "always with new seeds. It keeps its best melee build and its best ranged one. {games} runs."),
    "m3_rank_h": ("Puesto y tiers", "Rank and tiers"),
    "m3_rank": ("El puesto ordena la mejor de sus dos builds por la mediana de sus {seeds} partidas finales. Cada partida "
                "vale el tiempo que aguanta × la raíz de su ritmo de daño por su ritmo de bajas, los dos con techo: {dps} de "
                "daño por segundo o {kpm} bajas por minuto ya cuentan la mitad. Sin daño vale 0. Tiers por puesto: {sizes}.",
                "The rank sorts the better of its two builds by the median of its {seeds} final runs. Each run is worth the "
                "time it survives × the square root of its damage rate times its kill rate, both capped: {dps} damage per "
                "second or {kpm} kills per minute already count half. No damage is worth 0. Tiers by rank: {sizes}."),
    "m3_why_h": ("El porqué de cada ficha", "The why on each page"),
    "m3_why": ("Un ajuste sobre los 966 dice cuánto pesa cada factor en la puntuación: el ataque del Pokémon, lo bueno que es "
               "su grupo, PS, Defensa, Def. Especial, velocidad, tamaño y el daño que le hacen por sus tipos. Explica el "
               "{r2} de las diferencias (R²). La ficha nombra los factores que más le suman y le restan.",
               "A fit over all 966 says how much each factor weighs on the score: the Pokémon's attack, how good its group "
               "is, HP, Defense, Sp. Def., speed, size and the damage its types take. It explains {r2} of the differences "
               "(R²). Each page names the factors that add and subtract the most."),
    "m3_limits_h": ("Lo que no simulamos", "What we do not simulate"),
    "m3_limits": ("El bot no lleva objetos, no hay terreno ni estados alterados, y coge las cartas de subida de nivel con una "
                  "prioridad fija. Por eso la web no recomienda cartas ni objetos: de eso solo enseña lo que dice el código "
                  "del juego.",
                  "The bot holds no item, there is no terrain or status conditions, and it takes level-up cards in a fixed "
                  "order. That is why the site does not recommend cards or items: for those it only shows what the game "
                  "code says."),
    "met_h1": ("Método del ranking de {game}", "Ranking method for {game}"),
    "met_check": ("El motor está escrito dos veces, en JavaScript y en Rust, y en su modo básico un test comprueba que dan el mismo "
                  "resultado paso a paso. Las fórmulas de daño, el modo de tipo único y otras reglas se comparan con las "
                  "funciones del propio juego, y los combates de prueba se repiten con el código del juego descargado "
                  "(commit {sha}). Todo está en el repositorio, junto a los datos.",
                  "The engine is written twice, in JavaScript and in Rust, and in its basic mode a test checks that they "
                  "give the same result step by step. Damage formulas, the single-type bonus and other rules are compared "
                  "against the game's own functions, and test fights are replayed with the game's downloaded code "
                  "(commit {sha}). It is all in the repository, next to the data."),
    # ------------------------------------------------------------ navegación de las herramientas
    "nav_planificador": ("Planificador", "Build planner"),
    "guide_finder": ("Buscador por tipos", "Type finder"),
    "tool_noscript": ("Esta herramienta necesita JavaScript.", "This tool needs JavaScript."),
    "tool_load": ("Cargando datos…", "Loading data…"),
    "tool_fail": ("No se pudieron cargar los datos. Recarga la página.", "The data did not load. Reload the page."),

    # ------------------------------------------------------------ nota del Repertorio

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
    "bp_desc": ("Arma el grupo vinculado de un Pokémon de {game}. Empieza con su mejor build de la simulación y comparte el enlace.",
                "Build the bonded group for a {game} Pokémon. Starts from its best simulated build and shares as a link."),
    "bp_h1": ("Planificador de build", "Build planner"),
    "bp_lede": ("Elige un Pokémon. Empieza con su mejor build de la simulación: cambia lo que quieras y copia el enlace.",
                "Pick a Pokémon. It starts on its best simulated build: change anything you like and copy the link."),
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
    "bp_both": ("Danza Espada y Danza Dragón comparten el contador de ataque físico: no se suman. Elige solo una.",
                "Swords Dance and Dragon Dance share the physical attack counter, so they don't add up. Pick one."),
    "bp_result_h": ("Tu build", "Your build"),
    "bp_cover": ("Super efectivo contra el {super} de los Pokémon. Al menos neutral contra el {neutral}.",
                 "Super effective against {super} of Pokémon. At least neutral against {neutral}."),
    "bp_none_attack": ("Sin ataques elegidos.", "No attacks picked."),
    "bp_link": ("Enlace de esta build", "Link to this build"),
    "bp_copy": ("Copiar enlace", "Copy link"),
    "bp_copied": ("Enlace copiado", "Link copied"),
    "bp_reset": ("Volver a su mejor build", "Back to its best build"),
    "bp_rank": ("Puesto {rank} de {total} · tier {tier}", "Rank {rank} of {total} · tier {tier}"),
    "bp_open_sheet": ("Ver su ficha", "See its sheet"),
    "bp_boost_guide": ("Cómo funcionan los potenciadores", "How boosts work"),
    "bp_how": ("Danza Espada y Danza Dragón suben solo el ataque físico y comparten contador. Maquinación sube el especial. "
               "Cada potenciador dura 7 s. Con 2 potenciadores, las cartas de movimiento nuevo dejan de ofrecer potenciadores.",
               "Swords Dance and Dragon Dance raise only physical attack and share a counter. Maquinación raises special attack. "
               "Each boost lasts 7 s. With 2 boosts, new-move cards stop offering boosts."),
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
