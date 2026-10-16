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
    "og_alt": ("Tier list no oficial de PokéSurvivor: cartas de las fichas S con sprites de pixel art.",
               "Unofficial PokéSurvivor tier list: S-tier cards with pixel-art sprites."),
    "follow_label": ("Sigue a {handle} en X", "Follow {handle} on X"),
    "nav_main": ("Principal", "Main"),
    "nav_foot": ("Pie", "Footer"),
    "nav_tiers": ("Tiers", "Tiers"),
    "nav_metodo": ("Método", "Method"),
    "nav_ataques": ("Ataques", "Moves"),
    "nav_objetos": ("Objetos", "Items"),
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
    "dataset_name": ("Ranking no oficial de los Pokémon de {game}", "Unofficial ranking of the Pokémon in {game}"),
    "agents_label": ("Para agentes de IA y datos:", "For AI agents and data:"),
    "index_h1": ("Tier list de {game}", "{game} tier list"),
    "search_label": ("Buscar", "Search"),
    "search_ph": ("Pikachu, fuego, #25…", "Pikachu, fire, #25…"),
    "search_hint": ("Pulsa / para escribir en el buscador. Prueba «dragón», «#149» o «pikachu».",
                    "Press / to type in the search. Try “dragon”, “#149” or “pikachu”."),
    "search_clear": ("Borrar búsqueda", "Clear search"),
    "random_btn": ("Al azar", "Random"),
    "group_by": ("Agrupar por", "Group by"),
    "group_tier": ("Tier", "Tier"),
    "group_type": ("Tipo", "Type"),
    "group_rar": ("Rareza", "Rarity"),
    "group_region": ("Región", "Region"),
    "group_leg": ("Legendarios", "Legendary"),
    "group_none": ("Sin agrupar", "No groups"),
    "no_match": ("Ningún Pokémon coincide. Prueba con otro nombre o tipo.",
                 "No Pokémon match. Try another name or type."),
    "noscript": ("El buscador necesita JavaScript.", "Search needs JavaScript."),
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
    "ficha_title": ("{name} · tier {tier} · {site}", "{name} · tier {tier} · {site}"),
    "ficha_desc": ("{label}: tier {tier}, puesto {rank} de {total} en {game}.",
                   "{label}: tier {tier}, rank {rank} of {total} in {game}."),
    "flag_status": ("Uno de sus ataques aplica un estado que esta pasada de la simulación no reproduce, "
                    "así que su aguante puede estar infravalorado.",
                    "One of its attacks applies a status this sim pass does not reproduce, "
                    "so its survival may be underrated."),
    "flag_melee": ("Empieza con un ataque cuerpo a cuerpo, que es objetivamente peor para empezar.",
                   "It starts with a melee move, which is objectively worse to start with."),
    "flag_capped": ("Sus estadísticas son bajas para el tier que le darían sus otras medidas, "
                    "y por eso le frenan el tier.",
                    "Its stats are too low for the tier its other measures would give, "
                    "so they hold its tier back."),
    "flag_types": ("Solo tiene un tipo de ataque además del normal, que aprenden todos. Para S hacen falta dos; "
                   "por eso no sube a S.",
                   "It has only one attack type besides normal, which everyone learns. S needs two; that keeps it out of S."),
    "pager_aria": ("Pokémon vecinos", "Neighbouring Pokémon"),
    "dex_no": ("nº {dex}", "no. {dex}"),
    "noscript_ficha": ("Esta página necesita JavaScript.", "This page needs JavaScript."),
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
    "t_sim": ("Aguante simulado", "Simulated survival"),
    "band_rank": ("puesto {rank}", "rank {rank}"),
    "band_range": ("{lo} a {hi}", "{lo} to {hi}"),
    "t_learn": ("Ataques que puede aprender", "Moves it can learn"),
    "learn_lede": ("{n} ataques: los de tipo normal y los de sus tipos, por tier general (la misma que en Ataques). "
                   "No los simula con este Pokémon.",
                   "{n} moves: normal-type ones and those of its types, by overall tier (the same as on Moves). "
                   "They are not simulated with this Pokémon."),
    "learn_start": ("inicial", "start"),
    "t_build": ("Build", "Build"),
    "build_start": ("Inicio", "Start"),
    "build_best": ("Mejor ataque", "Best move"),
    "build_boost": ("Potenciador", "Boost"),
    "build_alt": ("Opcionales", "Optional"),
    "build_items": ("Objetos", "Items"),
    "build_cards": ("Cartas a priorizar", "Cards to prioritize"),
    "build_card_evo": ("Evoluciona un ataque del grupo", "Evolves a group move"),
    "build_super": ("Super efectivo", "Super effective"),
    "build_neutral": ("Sin resistencia", "Never resisted"),
    "build_share": ("Compartir esta build", "Share this build"),
    "build_copied": ("Enlace copiado", "Link copied"),
    "build_slot": ("Hueco {n}", "Slot {n}"),
    "build_brand": ("{site}", "{site}"),
    "sort_by": ("Ordenar por", "Sort by"),
    "sort_rank": ("Puesto", "Rank"),
    "sort_name": ("Nombre", "Name"),
    "sort_dex": ("Nº Pokédex", "Pokédex no."),
    "sort_atk": ("Ataque", "Attack"),
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
    "m_simStart": ("Partida, ataque inicial", "Game, starting move"),
    "m_simBest": ("Partida, mejor ataque", "Game, best move"),
    "m_lateMax": ("Final, todas las mejoras al máximo", "Late game, all shop upgrades maxed"),
    "m_lateFresh": ("Final, sin mejoras de tienda", "Late game, no shop upgrades"),
    "methods_lede": ("Cada punto es el puesto que daría esa medida: 1 es el mejor de 966, a la izquierda. "
                     "La escala se amplía hasta su peor puesto, así que un 24 parece lejos de 1, pero sigue siendo el 3 % superior. "
                     "«Final» estima cuánto aguanta al final de una partida, con la tienda sin comprar nada "
                     "o con todas sus mejoras permanentes al máximo. La línea naranja es el puesto final, "
                     "que mezcla todas las medidas.",
                     "Each dot is the rank that measure would give: 1 is the best of 966, on the left. "
                     "The scale zooms in to its worst rank, so 24 looks far from 1 but is still the top 3%. "
                     "“Late game” estimates how long a Pokémon lasts at the end of a run, with no shop upgrades "
                     "bought or with all permanent upgrades maxed. The orange line is the final rank, which mixes every measure."),
    "methods_final": ("puesto final {rank}", "final rank {rank}"),
    "methods_alt": ("{name}: puesto final {rank}. ", "{name}: final rank {rank}. "),
    "methods_alt_item": ("{label}, puesto {v}", "{label}, rank {v}"),
    "sim_start": ("Ataque inicial: {name}", "Starting move: {name}"),
    "sim_best": ("Mejor ataque: {name}", "Best move: {name}"),
    "sim_median": ("mediana de todos: {s} s", "median of all: {s} s"),
    "sim_alt": ("Segundos simulados que aguanta un bot con un grupo fijo (mediana de 200 partidas): ",
                "Simulated seconds a bot survives with one fixed group (median of 200 games): "),
    "sim_lede": ("Un bot juega con un grupo fijo (el ataque inicial, otro más, Danza Espada y Fortaleza). "
                 "Los vínculos llegan al ganar la grieta, no al empezar; hay jefes y orbes de curación, y se lanzan todos los tipos de ataque. "
                 "Hasta 900 s, sin mejoras permanentes. Es una estimación: el bot no esquiva como una persona.",
                 "A bot plays one fixed group (the starting move, one more attack, Swords Dance and Harden). "
                 "Bonds arrive when a rift is won, not at the start; bosses and heal orbs are in, and every attack kind fires. "
                 "Up to 900 s, with no permanent upgrades. It is an estimate: the bot does not dodge the way a person does."),
    "sim_scale": ("Escala: de {lo} s a {hi} s, lo que aguantan todos los Pokémon.",
                  "Scale: {lo} s to {hi} s, what all Pokémon last."),
    "sim_gain": ("Con el mejor ataque aguanta {d} s más que con el inicial.",
                 "With the best move it lasts {d} s longer than with the starting move."),

    # ------------------------------------------------------------ ataques
    "ataques_title": ("Ataques · {site}", "Moves · {site}"),
    "ataques_desc": ("Tier list de los {n} ataques de {game}.", "Tier list of the {n} moves in {game}."),
    "ataques_h1": ("Ataques", "Moves"),
    "ataques_lede": ("1× es un movimiento normal (la mediana de todos). Cuanto más alto el valor, mejor. "
                     "Los potenciadores muestran además el tiempo que están activos.",
                     "1× is a normal move (the median of all). The higher the value, the better. "
                     "Boosts also show how much of the time they are active."),
    "cat_melee": ("Cuerpo a cuerpo", "Melee"),
    "cat_ranged": ("Distancia", "Ranged"),
    "cat_stat": ("Potenciadores", "Boosts"),
    "mv_value": ("Valor", "Value"),
    "mv_cover": ("Tiempo activo", "Time active"),
    "mv_typical": ("normal", "typical"),
    "mv_better": ("mejor", "better"),
    "mv_worse": ("peor", "worse"),
    "ataques_how1": ("Cada tarjeta es un ataque. La animación muestra cómo lo usa un Pokémon de su tipo: el de mejor puesto de ese tipo.",
                     "Each card is a move. The animation shows how a Pokémon of its type uses it: the best-ranked one of that type."),
    "ataques_how2": ("El valor compara su daño y su ritmo con un ataque normal. 1× es la mediana; la raya vertical marca ese 1×.",
                     "The value compares its damage and pace with a normal move. 1× is the median; the vertical line marks that 1×."),
    "ataques_how3": ("Los grupos van por tier: S es lo mejor. Dentro de cada tier, de mejor a peor.",
                     "Groups go by tier: S is the best. Within each tier, from best to worst."),
    "mv_search": ("Buscar ataque o tipo…", "Search a move or type…"),
    "mv_none": ("Ningún ataque coincide con la búsqueda.", "No move matches the search."),
    "mv_example": ("Ejemplo: {name} →", "Example: {name} →"),
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
    "odds_title": ("Probabilidad por rareza", "Odds by rarity"),

    # ------------------------------------------------------------ objetos
    "obj_title": ("Objetos · {site}", "Items · {site}"),
    "obj_desc": ("Tier list de los objetos de {game} por fase de la partida.",
                 "Tier list of the {game} items by phase of the run."),
    "obj_h1": ("Objetos", "Items"),
    "obj_lede": ("Solo se lleva uno por partida: los cofres los sueltan y puedes cambiar el que tienes. Esta tier "
                 "list sale del código del juego, no de partidas simuladas.",
                 "You carry one per run: chests drop them and you can swap the one you have. This tier list comes from "
                 "the game's code, not from simulated games."),
    "obj_phases_h": ("Tier por fase", "Tier by phase"),
    "obj_table_h": ("Qué hace cada objeto", "What each item does"),

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
    "col_step3_html": ("<strong>Pega el resultado</strong> aquí. Se guarda en este navegador para la próxima vez "
                       "y no sale de él.",
                       "<strong>Paste the result</strong> here. It is kept in this browser for next time and never "
                       "leaves it."),
    "col_json": ("Resultado", "Result"),
    "col_view": ("Ver", "Show"),
    "col_file": ("O un archivo .json", "Or a .json file"),
    "col_drop": ("Arrastra aquí el .json o pulsa para elegirlo", "Drag the .json here or click to choose it"),
    "col_reimport": ("Reimportar", "Re-import"),

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
    "met_lede": ("Cada Pokémon recibe un puesto del 1 al 966 y un tier. El puesto mezcla su ficha, cómo juega "
                 "en partidas simuladas y cómo rinde al final de la partida. Como una sola cifra puede engañar, "
                 "el cálculo se repite 2.000 veces.",
                 "Each Pokémon gets a rank from 1 to 966 and a tier. The rank mixes its sheet, how it plays in "
                 "simulated games and how it performs late in the game. Since one number can mislead, the "
                 "calculation is repeated 2,000 times."),
    "met_steps_aria": ("Pasos del cálculo", "Calculation steps"),
    "met_step_1_h": ("Medir", "Measure"),
    "met_step_1": ("Para cada Pokémon se miden su ficha (estadísticas, ataques, defensa de tipos y tamaño), su "
                   "aguante en 200 partidas simuladas con el ataque inicial y con el mejor que puede aprender, y su "
                   "rendimiento al final de la partida.",
                   "For each Pokémon we measure its sheet (stats, moves, type resistance and size), how long it survives "
                   "in 200 simulated games with its starting move and with the best move it can learn, and how it "
                   "performs late in the game."),
    "met_step_2_h": ("Percentil", "Percentile"),
    "met_step_2": ("Cada medida se convierte en percentil: 90 quiere decir que es mejor que el 90 % de los Pokémon "
                   "en esa medida. Así se pueden comparar cosas distintas, como segundos de partida y estadísticas.",
                   "Each measure becomes a percentile: 90 means better than 90% of Pokémon on that measure. That lets "
                   "us compare different things, like seconds survived and stats."),
    "met_step_3_h": ("Combinar", "Combine"),
    "met_step_3": ("La ficha pesa {sheet}, las partidas {sim} y el final de la partida {late}. Cada medida entra "
                   "como percentil en escala logarítmica, así que las diferencias entre los primeros puestos apenas "
                   "cuentan y una pieza muy floja sí baja la nota. Pruébalo abajo.",
                   "The sheet weighs {sheet}, games {sim} and late game {late}. Each measure enters as a percentile on "
                   "a log scale, so differences between the top ranks barely count, while one very weak piece does "
                   "drag the score down. Try it below."),
    "met_step_4_h": ("Repetir 2.000 veces", "Repeat 2,000 times"),
    "met_step_4": ("Cada repetición cambia los datos un poco, dentro de su margen de error; también el peso entre "
                   "partidas y final, y una de las 80 suposiciones del modelo de final de partida. Así salen 2.000 "
                   "ordenaciones.",
                   "Each repeat shifts the data within its error margin, the weight between games and late game, and "
                   "one of the 80 assumptions of the late-game model. That gives 2,000 orderings."),
    "met_step_5_h": ("Puesto", "Rank"),
    "met_step_5": ("El puesto final es la mediana de esas 2.000 posiciones. El rango habitual, la banda de cada "
                   "ficha, va del percentil 10 al 90 de esas posiciones.",
                   "The final rank is the median of those 2,000 positions. The usual range, the band on each sheet, "
                   "runs from the 10th to the 90th percentile of those positions."),
    "met_step_6_h": ("Tier", "Tier"),
    "met_step_6": ("Los puestos se reparten en tiers de tamaño fijo: {sizes}. Para entrar en S hace falta estar "
                   "entre el {s} mejor en estadísticas, tener ataques de tres tipos distintos contando el normal "
                   "(que aprenden todos: son dos tipos además del normal) y no empezar con un "
                   "ataque cuerpo a cuerpo; en A, entre el {a}; en B, entre el {b}. Quien no cumple el mínimo espera "
                   "al siguiente tier en el que sí entre.",
                   "Ranks are split into tiers of fixed size: {sizes}. To enter S you must be in the top {s} for "
                   "stats, have attacks of three different types counting normal (everyone learns it: that is two "
                   "types besides normal), and not start with a melee attack; A, top {a}; "
                   "B, top {b}. Whoever misses the minimum waits for the next tier they qualify for."),
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
    "demo_title": ("Un punto flojo hunde la nota", "One weak spot sinks the score"),
    "demo_lede": ("Baja una pieza con el deslizador y mira las dos notas. La media simple deja que el resto compense; "
                  "la nuestra no: una pieza floja hunde la nota.",
                  "Lower one piece with its slider and watch both scores. A plain mean lets the others make up for "
                  "it; ours does not: one weak piece sinks the score."),
    "demo_geo": ("Nuestra media (geométrica)", "Our mean (geometric)"),
    "demo_arith": ("Media simple (aritmética)", "Plain mean (arithmetic)"),
    "demo_how": ("Naranja: nuestra media. Gris: la media simple. Cuanto más se separan, más castiga la nuestra un punto flojo.",
                 "Orange: our mean. Grey: plain mean. The further apart they are, the harder ours punishes a weak spot."),
    "demo_weight": ("peso {w}", "weight {w}"),
    "demo_aria": ("Percentil en {name}", "Percentile in {name}"),
    "reps_title": ("2.000 repeticiones", "2,000 repeats"),
    "reps_lede": ("Cada punto es un Pokémon de ejemplo. La sombra es su rango habitual (del percentil 10 al 90) y la "
                  "raya roja, su puesto final. En cada repetición cae en un punto distinto de ese rango.",
                  "Each dot is an example Pokémon. The shade is its usual range (10th to 90th percentile) and the red "
                  "line its final rank. Each repeat lands it somewhere else within that range."),
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
    "arena_lede": ("Ilustración, no datos del ranking. Así juega cada Pokémon las partidas simuladas: esquiva, dispara "
                   "a los enemigos que se acercan y aguanta lo que puede.",
                   "Illustration, not ranking data. This is how each Pokémon plays the simulated games: it dodges, "
                   "shoots the enemies that come close, and survives as long as it can."),
    "arena_time": ("tiempo", "time"),
    "arena_kills": ("derrotados", "defeated"),
    "arena_alt": ("Animación de una partida simulada. Un Pokémon esquiva y dispara a enemigos que se acercan.",
                  "Animation of a simulated game. A Pokémon dodges and fires at approaching enemies."),
    "met_limits_h": ("Límites", "Limits"),
    "met_lim_1": ("La caminata a la grieta es tiempo a la velocidad actual, sin buscar camino, y el bot no va a por los altares.",
                  "The walk to a rift is time at current speed, with no pathing, and the bot does not go looking for altars."),
    "met_lim_2": ("El compañero de sinergia, como Hex, no ataca hasta ganar la grieta.",
                  "A synergy partner, such as Hex, does not attack until a rift is won."),
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
