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
    "unofficial": ("no oficial", "unofficial"),
    "nav_main": ("Principal", "Main"),
    "nav_foot": ("Pie", "Footer"),
    "nav_tiers": ("Tier list", "Tier list"),
    "nav_metodo": ("Método", "Method"),
    "nav_ataques": ("Ataques", "Moves"),
    "nav_gachas": ("Gachas", "Gacha"),
    "nav_coleccion": ("Mi colección", "My collection"),
    "nav_acerca": ("Acerca", "About"),
    "lang_label": ("Idioma", "Language"),
    "sprites_line_html": (
        'Sprites de <a href="{url}" rel="noopener">{source}</a>, <a href="{lic_url}" rel="noopener">{lic}</a>. '
        'Artistas en <a href="{about}#creditos">Acerca</a>.',
        'Sprites from <a href="{url}" rel="noopener">{source}</a>, <a href="{lic_url}" rel="noopener">{lic}</a>. '
        'Artists on <a href="{about}#creditos">About</a>.'),
    "model_line": (
        "Los tiers son una estimación propia con un modelo, no un dato oficial, y no están contrastados con partidas "
        "reales. Datos de {game} en el commit {commit}, ranking {version}, generado el {date}.",
        "The tiers are our own model estimate, not official data, and have not been checked against real games. "
        "Data from {game} at commit {commit}, {version} ranking, generated on {date}."),
    "version_name": ("definitivo", "final"),
    "disclaimer": (
        "Sitio de fans, sin ánimo de lucro, no oficial y no afiliado. Pokémon y todos sus nombres y personajes son "
        "marcas de Nintendo, Creatures Inc., GAME FREAK y The Pokémon Company, que no han creado, revisado ni "
        "aprobado este sitio. Esto tampoco es parte del juego {game} ni lo respalda su autor. Es un análisis "
        "independiente.",
        "Fan site, non-profit, unofficial and not affiliated. Pokémon and all related names and characters are "
        "trademarks of Nintendo, Creatures Inc., GAME FREAK and The Pokémon Company, which did not create, review "
        "or approve this site. It is also not part of the game {game} and its author does not endorse it. It is an "
        "independent analysis."),
    "no_tracking": (
        "Sin cookies, analítica, anuncios ni donaciones. La colección que importas se procesa solo en tu navegador.",
        "No cookies, analytics, ads or donations. The collection you import is processed only in your browser."),
    "tier": ("Tier {t}", "Tier {t}"),

    # ------------------------------------------------------------ portada
    "index_title": ("{site} · Tier list de {game}", "{site} · {game} tier list"),
    "index_desc": ("Tier list no oficial de los {n} Pokémon de {game}, con ficha, movimientos y gachas.",
                   "Unofficial tier list of the {n} Pokémon in {game}, with a page for each, moves and gacha banners."),
    "index_h1": ("Tier list de {game}", "{game} tier list"),
    "index_lead_html": (
        "{a}, {b} y {c} encabezan el ranking de los {n} Pokémon del juego. Cinco tiers de tamaño fijo, calculados "
        'con partidas simuladas en el mapa real, la ficha de cada especie y una estimación del final de partida, '
        'repetido 2.000 veces. <a href="{method}">Cómo se calcula</a>, con gráficos.',
        "{a}, {b} and {c} lead the ranking of the {n} Pokémon in the game. Five tiers of fixed size, calculated "
        'from simulated games on the real map, each species sheet and an end-of-game estimate, repeated 2,000 '
        'times. <a href="{method}">How it is calculated</a>, with charts.'),
    "search_label": ("Buscar por nombre, tipo o número", "Search by name, type or number"),
    "search_ph": ("Keldeo, fuego, 25…", "Keldeo, fire, 25…"),
    "unsure_key": (
        "Puesto dudoso. En menos de la mitad de las repeticiones queda en su tier. El número bajo cada nombre es su "
        "puesto.",
        "Uncertain rank. It stays in its tier in fewer than half of the repeats. The number under each name is its "
        "rank."),
    "noscript": ("El buscador necesita JavaScript.", "Search needs JavaScript."),
    "tier_head": ("puestos {a} a {b} · {n} Pokémon", "ranks {a} to {b} · {n} Pokémon"),
    "card_title": ("{name} · nº {dex} · puesto {rank} · tier {tier}{hint}",
                   "{name} · no. {dex} · rank {rank} · tier {tier}{hint}"),
    "card_hint": (" · tier dudoso ({share} % en {tier})", " · uncertain tier ({share}% in {tier})"),

    # ------------------------------------------------------------ ficha
    "crumb_home": ("Tier list", "Tier list"),
    "legendary": ("Legendario", "Legendary"),
    "gacha_banner": ("Banner de gacha: {name}", "Gacha banner: {name}"),
    "stars_alt": ("{n} de 5 estrellas", "{n} of 5 stars"),
    "sprite_alt": ("Sprite de {name}", "Sprite of {name}"),
    "ficha_title": ("{name} · tier {tier} · {site}", "{name} · tier {tier} · {site}"),
    "ficha_desc": ("{label}. Tier {tier}, puesto {rank} de {total} en {game}, con el desglose de cómo se calcula.",
                   "{label}. Tier {tier}, rank {rank} of {total} in {game}, with a breakdown of how it is calculated."),
    "verdict_rank": ("Puesto {rank} de {total}.", "Rank {rank} of {total}."),
    "verdict_firm": ("En el {share} % de las 2.000 repeticiones del modelo queda en tier {t}.",
                     "In {share}% of the model's 2,000 repeats it lands in tier {t}."),
    "verdict_mid": ("Queda en tier {t} en el {share} % de las repeticiones y el resto cae en un tier vecino.",
                    "It lands in tier {t} in {share}% of the repeats and the rest fall in a neighbouring tier."),
    "verdict_low": ("Su tier es dudoso. Solo en el {share} % de las repeticiones queda en {t}.",
                    "Its tier is uncertain. It lands in {t} in only {share}% of the repeats."),
    "pair_html": ("La mejor pareja de ataques según la ficha: {pair}.", "Best move pair according to its sheet: {pair}."),
    "notes_h": ("Qué tener en cuenta", "Worth knowing"),
    "note_status": (
        "Usa quemadura, veneno o ralentización, que la simulación no modela. Probablemente el ranking la infravalora.",
        "It uses burn, poison or slow, which the simulation does not model. The ranking probably underrates it."),
    "note_melee": (
        "Empieza con un ataque cuerpo a cuerpo, que el bot de la simulación maneja peor que una persona.",
        "It starts with a melee move, which the simulation bot handles worse than a person does."),
    "note_capped": (
        "La regla de estadísticas le limita el tier. Sus estadísticas quedan por debajo del mínimo del tier que su "
        "rendimiento merecería.",
        "The stats rule caps its tier. Its stats fall below the minimum for the tier its performance would earn."),
    "ficha_foot_html": ('Estimación propia, sin jefes ni grietas y con un bot que esquiva. '
                        '<a href="{href}">Cómo se calcula</a>.',
                        'Our own estimate, with no bosses or rifts and a bot that dodges. '
                        '<a href="{href}">How it is calculated</a>.'),
    "pager_aria": ("Pokémon vecinos", "Neighbouring Pokémon"),
    "dex_no": ("nº {dex}", "no. {dex}"),

    # ------------------------------------------------------------ gráficos de la ficha
    "band_firm": ("{name} está muy asentado y casi siempre queda entre el {lo} y el {hi}",
                  "{name} is well settled and almost always lands between {lo} and {hi}"),
    "band_mid": ("El puesto de {name} varía entre el {lo} y el {hi} según cómo se repita el modelo",
                 "The rank of {name} ranges from {lo} to {hi} depending on how the model repeats"),
    "band_wide": ("El puesto de {name} es incierto y va del {lo} al {hi}",
                  "The rank of {name} is uncertain and goes from {lo} to {hi}"),
    "band_sub": ("Puesto entre los {total} Pokémon. La banda marca el rango del 10 % al 90 % de las repeticiones",
                 "Rank among the {total} Pokémon. The band covers the 10% to 90% range of the repeats"),
    "band_rank": ("puesto {rank}", "rank {rank}"),
    "band_range": ("rango habitual {lo} a {hi}", "usual range {lo} to {hi}"),
    "band_alt": ("{name}: puesto {rank} de {total}, tier {tier}. El rango habitual va del puesto {lo} al {hi}.",
                 "{name}: rank {rank} of {total}, tier {tier}. The usual range goes from rank {lo} to {hi}."),
    "pill_stats": ("Estadísticas", "Stats"),
    "pill_moves": ("Ataques que puede aprender", "Moves it can learn"),
    "pill_typedef": ("Defensa de tipos", "Type defense"),
    "pill_size": ("Hitbox pequeña", "Small hitbox"),
    "pill_stats_p": ("sus estadísticas", "its stats"),
    "pill_moves_p": ("sus ataques", "its moves"),
    "pill_typedef_p": ("su defensa de tipos", "its type defense"),
    "pill_size_p": ("su tamaño", "its size"),
    "pillars_even": ("{name} rinde parejo en las cuatro piezas de la ficha",
                     "{name} is even across the four parts of its sheet"),
    "pillars_title": ("Lo mejor de {name} son {best} ({bv}) y lo peor, {worst} ({wv})",
                      "The best thing about {name} is {best} ({bv}) and the worst is {worst} ({wv})"),
    "pillars_sub": (
        "Mejor que el X % de los 966 Pokémon (100 % = el mejor). La línea discontinua es la mediana",
        "Better than X% of the 966 Pokémon (100% = the best). The dashed line is the median"),
    "pillars_alt_item": ("{label} mejor que el {v} % de los Pokémon", "{label} better than {v}% of Pokémon"),
    "median": ("mediana", "median"),
    "m_sheet": ("Ficha de la especie", "Species sheet"),
    "m_simStart": ("Partida simulada, ataque inicial", "Simulated game, starting move"),
    "m_simBest": ("Partida simulada, mejor ataque", "Simulated game, best move"),
    "m_lateMax": ("Final de partida, mejoras al máximo", "End game, upgrades maxed"),
    "m_lateFresh": ("Final de partida, cuenta nueva", "End game, fresh account"),
    "methods_same": ("Los cinco métodos coinciden en el puesto {lo}", "All five methods agree on rank {lo}"),
    "methods_title": ("Según el método, {name} queda entre el puesto {lo} y el {hi}",
                      "Depending on the method, {name} lands between rank {lo} and {hi}"),
    "methods_sub": ("Cada método ordena por separado los 966 Pokémon. ",
                    "Each method ranks all 966 Pokémon separately. "),
    "methods_far": ("El que más se aleja del puesto final es «{label}» ({v}).",
                    "The one furthest from the final rank is \"{label}\" ({v})."),
    "methods_all": ("Todos acaban en el mismo puesto.", "All end at the same rank."),
    "methods_final": ("puesto final {rank}", "final rank {rank}"),
    "methods_alt": ("{name}: puesto final {rank}. ", "{name}: final rank {rank}. "),
    "methods_alt_item": ("{label}, puesto {v}", "{label}, rank {v}"),
    "sim_start": ("Inicial · {name}", "Starting · {name}"),
    "sim_best": ("Mejor · {name}", "Best · {name}"),
    "sim_median": ("mediana de todos: {s} s", "median of all: {s} s"),
    "sim_title_up": ("Con su mejor ataque aguanta {s} s, {d} s más que la mediana",
                     "With its best move it lasts {s} s, {d} s more than the median"),
    "sim_title_down": ("Con su mejor ataque aguanta {s} s, {d} s menos que la mediana",
                       "With its best move it lasts {s} s, {d} s less than the median"),
    "sim_title_one": ("Aguanta {s} s con su ataque inicial, que ya es el mejor que puede aprender",
                      "It lasts {s} s with its starting move, which is already the best it can learn"),
    "sim_sub": ("Segundos que sobrevive de mediana en 200 partidas. La línea marca la mediana de los {total} Pokémon",
                "Median seconds survived over 200 games. The line marks the median of the {total} Pokémon"),
    "sim_alt": ("Segundos de mediana en 200 partidas simuladas: ", "Median seconds over 200 simulated games: "),

    # ------------------------------------------------------------ ataques
    "ataques_title": ("Ataques · {site}", "Moves · {site}"),
    "ataques_desc": ("Tier list de los {n} movimientos de {game}, con el motivo de cada tier.",
                     "Tier list of the {n} moves in {game}, with the reason for each tier."),
    "ataques_h1": ("Tier list de ataques", "Move tier list"),
    "ataques_lead": (
        "Los {n} ataques del juego. Cada uno se prueba en un Pokémon de referencia con estadísticas medianas. Los tres "
        "grupos se ordenan por separado, así que un S de cuerpo a cuerpo y un S de estadística no se pueden comparar.",
        "The game's {n} moves. Each one is tested on a reference Pokémon with median stats. The three groups are "
        "ranked separately, so a melee S and a boost S cannot be compared."),
    "cat_melee": ("Cuerpo a cuerpo", "Melee"),
    "cat_ranged": ("Distancia", "Ranged"),
    "cat_stat": ("Estadística", "Boosts"),
    "cat_melee_text": ("Golpean a corta distancia. Más daño medio, pero te obligan a meterte en el enjambre.",
                       "They hit at close range. More average damage, but they force you into the swarm."),
    "cat_ranged_text": ("Golpean desde lejos. El daño que recibes depende menos del movimiento.",
                        "They hit from afar. The damage you take depends less on movement."),
    "cat_stat_text": ("No hacen daño. Potencian al Pokémon y se fusionan o alternan con los ataques.",
                      "They deal no damage. They boost the Pokémon and fuse or alternate with attacks."),

    "mk_melee": ("golpe en arco", "arc swing"), "mk_aura": ("aura continua", "continuous aura"),
    "mk_dash": ("carga que atraviesa", "piercing charge"), "mk_trail": ("estela de charcos", "puddle trail"),
    "mk_orbit": ("orbes que giran", "orbiting orbs"), "mk_projectile": ("proyectiles", "projectiles"),
    "mk_nova": ("ráfaga radial", "radial burst"), "mk_beam": ("rayo recto", "straight beam"),
    "mk_boomerang": ("bumerán", "boomerang"), "mk_chain": ("cadena de saltos", "chain jumps"),
    "mk_mine": ("minas", "mines"), "mk_meteor": ("meteoros", "meteors"), "mk_turret": ("torreta", "turret"),
    "mk_cone": ("abanico de disparos", "spread shot"), "mk_buff": ("potenciador", "boost"),
    "mv_dps15": ("Daño, minuto 15", "Damage, minute 15"),
    "mv_ttd15": ("Aguante, minuto 15", "Survival, minute 15"),
    "mv_dps5": ("Daño, minuto 5", "Damage, minute 5"),
    "mv_cover": ("Activo", "Uptime"),
    "mv_cover_w": ("del tiempo", "of the time"),
    "mv_fused": ("Fusionado, minuto {n}", "Fused, minute {n}"),
    "mv_up": ("sube {v} %", "up {v}%"),
    "mv_down": ("baja {v} %", "down {v}%"),
    "mv_same": ("sin cambio", "no change"),
    "mv_typical": ("lo normal", "typical"),
    "mv_evo": ("Evoluciona a {evo} con la carta {card}.", "Evolves into {evo} with the {card} card."),
    "mv_buff_text": ("Sube {stat} hasta +{amount}. Dura {dur} s y se recarga en {cd} s.",
                     "Raises {stat} by up to +{amount}. Lasts {dur} s and recharges in {cd} s."),
    "mv_weave": ("En otro hueco, sin fusionar, vale ×{w} al minuto 15.",
                 "In another slot, not fused, it is worth ×{w} at minute 15."),
    "st_atk": ("el ataque", "attack"), "st_spd": ("la velocidad", "speed"), "st_def": ("la defensa", "defense"),
    "st_regen": ("la regeneración", "regeneration"), "st_hp": ("la vida", "health"),
    "lv_dps_0": ("mucho más daño", "much more damage"), "lv_dps_1": ("más daño", "more damage"),
    "lv_dps_2": ("daño normal", "average damage"), "lv_dps_3": ("menos daño", "less damage"),
    "lv_dps_4": ("mucho menos daño", "much less damage"),
    "lv_ttd_0": ("te mantiene vivo mucho más", "keeps you alive much longer"),
    "lv_ttd_1": ("te mantiene vivo más", "keeps you alive longer"),
    "lv_ttd_2": ("aguante normal", "average survival"), "lv_ttd_3": ("te expone más", "exposes you more"),
    "lv_ttd_4": ("te expone mucho", "exposes you a lot"),
    "mv_howto_h": ("Cómo leer un ataque", "How to read a move"),
    "mv_howto_p": (
        "Cada barra compara el ataque con el ataque típico. El ataque típico es la mediana de los {n} ataques que hacen "
        "daño. La raya vertical marca ese valor, que es ×1. Si la barra pasa la raya, el ataque es mejor que lo normal "
        "y la barra va en color. Si no llega, es peor. Por ejemplo, ×2 es el doble de lo normal y ×0,5 es la mitad.",
        "Each bar compares the move with the typical move. The typical move is the median of the {n} moves that deal "
        "damage. The vertical line marks that value, which is ×1. If the bar passes the line, the move is better than "
        "typical and the bar is colored. If it falls short, it is worse. For example, ×2 is double the typical value "
        "and ×0.5 is half."),
    "mv_howto_ex": ("Un ejemplo real", "A real example"),
    "mv_g_dps15": ("Daño, minuto 15", "Damage, minute 15"),
    "mv_g_dps15_d": ("Daño por segundo a los 15 minutos de partida, frente al ataque típico.",
                     "Damage per second 15 minutes into a run, against the typical move."),
    "mv_g_ttd15": ("Aguante, minuto 15", "Survival, minute 15"),
    "mv_g_ttd15_d": ("Cuánto sobrevive el Pokémon con este ataque, frente al típico. Un ataque que te obliga a acercarte "
                     "a los enemigos te hace perder vida antes y la barra queda corta.",
                     "How long the Pokémon survives with this move, against the typical one. A move that forces you "
                     "close to enemies makes you lose health sooner, so the bar is short."),
    "mv_g_dps5": ("Daño, minuto 5", "Damage, minute 5"),
    "mv_g_dps5_d": ("Lo mismo a los 5 minutos. Una barra larga aquí significa que el ataque funciona pronto. Una barra "
                    "corta significa que rinde sobre todo cuando subes de nivel.",
                    "The same at minute 5. A long bar here means the move works early. A short bar means it pays off "
                    "mostly once you level up."),
    "mv_g_buff": ("Potenciador", "Boost"),
    "mv_g_buff_d": ("No hace daño. Sube una estadística durante unos segundos. Sus barras muestran cuánto cambia el valor "
                    "de tus ataques al fusionarlo con ellos, y «activo» es el porcentaje del tiempo que dura el efecto.",
                    "It deals no damage. It raises a stat for a few seconds. Its bars show how much the value of "
                    "your attacks changes when fused with them, and \"uptime\" is the share of time the effect lasts."),
    "mv_g_tier": ("Tier", "Tier"),
    "mv_g_tier_d": ("Dentro de cada grupo, el 15 % mejor es S, hasta el 40 % es A, hasta el 70 % es B y el resto es C.",
                    "Within each group, the best 15% is S, up to 40% is A, up to 70% is B and the rest is C."),
    "odds_title": ("Solo 8 de cada 100 tiradas dan un 4★ o un 5★", "Only 8 in every 100 pulls give a 4★ or 5★"),
    "odds_sub": ("Probabilidad de cada rareza en una tirada. Casi todos los Pokémon de tier S y A son 4★ o 5★.",
                 "Chance of each rarity in one pull. Almost every tier S and A Pokémon is 4★ or 5★."),
    "odds_alt": ("Probabilidad por rareza: ", "Chance by rarity: "),
    "gachas_read_h": ("Cómo leer la tabla", "How to read the table"),
    "gl2_pool": ("Pool", "Pool"),
    "gl2_pool_d": ("Cuántos Pokémon puede dar el banner. Incluye a los legendarios.",
                   "How many Pokémon the banner can give. It includes legendaries."),
    "gl2_sa": ("Tier S y A", "Tier S and A"),
    "gl2_sa_d": ("Cuántos Pokémon del pool son de esos dos tiers, los mejores del ranking.",
                 "How many Pokémon in the pool belong to those two tiers, the best in the ranking."),
    "gl2_rate": ("S + A en el pool", "S + A in the pool"),
    "gl2_rate_d": ("Esa suma dividida por el tamaño del pool. Cuenta cada Pokémon por igual.",
                   "That sum divided by the pool size. Every Pokémon counts the same."),
    "gl2_pull": ("S + A por tirada", "S + A per pull"),
    "gl2_pull_d": ("Probabilidad de sacar un S o un A en una tirada, contando que los 4★ y 5★ salen poco.",
                   "Chance of getting an S or an A in one pull, counting that 4★ and 5★ are rare."),
    "ficha_how": ("Qué significan estos números", "What these numbers mean"),
    "gl_rank": ("Puesto", "Rank"),
    "gl_rank_d": ("Posición entre los {total} Pokémon. El 1 es el mejor.", "Position among the {total} Pokémon. 1 is the best."),

    # ------------------------------------------------------------ gachas
    "gachas_title": ("Gachas · {site}", "Gacha · {site}"),
    "gachas_desc": ("Qué banner de gacha de {game} trae más Pokémon de tier S y A.",
                    "Which {game} gacha banner brings the most tier S and A Pokémon."),
    "gachas_h1": ("Gachas. Qué banner compensa", "Gacha. Which banner is worth it"),
    "gachas_lead_html": (
        "El juego tiene 9 banners, uno por generación. El pool incluye a los legendarios, como lo lee "
        "<code>gacha.js</code>.",
        "The game has 9 banners, one per generation. The pool includes legendaries, as <code>gacha.js</code> reads it."),
    "comp_title": ("En {a} uno de cada {x} Pokémon es S o A y en {b}, uno de cada {y}",
                   "In {a}, one in {x} Pokémon is S or A, and in {b}, one in {y}"),
    "comp_sub": ("Pool de cada banner repartido por tier. A la derecha, la parte que es S o A",
                 "Pool of each banner split by tier. On the right, the share that is S or A"),
    "comp_alt": ("Pokémon por tier en cada banner. ", "Pokémon per tier in each banner. "),
    "comp_alt_item": ("{n} de tier {t}", "{n} in tier {t}"),
    "th_banner": ("Banner", "Banner"),
    "th_pool": ("Pool", "Pool"),
    "th_leg": ("Legendarios", "Legendaries"),
    "th_s": ("Tier S", "Tier S"),
    "th_a": ("Tier A", "Tier A"),
    "th_pool_rate": ("S + A en el pool", "S + A in pool"),
    "th_pull_rate": ("S + A por tirada", "S + A per pull"),
    "gachas_two_h": ("Por qué hay dos porcentajes", "Why there are two percentages"),
    "gachas_two_html": (
        "«S + A en el pool» cuenta cuántos de los Pokémon del banner son buenos, sin pesar su rareza. «S + A por "
        "tirada» sí la pesa con las probabilidades de <code>gacha.js</code> (1★ 45 %, 2★ 30 %, 3★ 17 %, 4★ 6,5 %, 5★ "
        "1,5 %) y con cuántos Pokémon hay de cada rareza, y por eso sale menor. La mayoría de los S y A son 4★ o 5★, "
        "que juntos solo salen en el 8 % de las tiradas. No cuenta las garantías (un 4★ o más en cada ×10 y un 5★ a "
        "las 70 tiradas sin ninguno).",
        "\"S + A in pool\" counts how many of the banner's Pokémon are good, ignoring rarity. \"S + A per pull\" "
        "weights rarity with the odds from <code>gacha.js</code> (1★ 45%, 2★ 30%, 3★ 17%, 4★ 6.5%, 5★ 1.5%) and with "
        "how many Pokémon exist at each rarity, which is why it comes out lower. Most S and A Pokémon are 4★ or 5★, "
        "which together appear in only 8% of pulls. It ignores the guarantees (a 4★ or better in every ×10 and a 5★ "
        "after 70 pulls without one)."),
    "gachas_pools": ("Pools: {pools} (suman {total}).", "Pools: {pools} (total {total})."),

    # ------------------------------------------------------------ colección
    "col_title": ("Mi colección · {site}", "My collection · {site}"),
    "col_desc": ("Importa tu colección de {game} y mira tus Pokémon por tier.",
                 "Import your {game} collection and see your Pokémon by tier."),
    "col_h1": ("Mi colección", "My collection"),
    "col_lead": (
        "Pega aquí el resultado de un comando de la consola del juego y verás cuántos Pokémon tienes de cada tier. "
        "Todo ocurre en tu navegador. El JSON no se envía ni se guarda.",
        "Paste the result of a command from the game's console here and you will see how many Pokémon you have in "
        "each tier. It all happens in your browser. The JSON is not sent or stored."),
    "col_step1_html": ("<strong>Abre el juego</strong> en el navegador, con tu sesión iniciada, y no cierres esa pestaña.",
                       "<strong>Open the game</strong> in your browser, signed in, and keep that tab open."),
    "col_step2_html": (
        "<strong>Abre la consola</strong> (F12, pestaña Consola; en Mac, ⌥⌘J) y pega este comando. Si el navegador te "
        "lo pide, escribe antes <kbd>allow pasting</kbd>. Lee <code>localStorage</code> del propio navegador y no "
        "hace peticiones de red.",
        "<strong>Open the console</strong> (F12, Console tab; on Mac, ⌥⌘J) and paste this command. If the browser asks, "
        "type <kbd>allow pasting</kbd> first. It reads your browser's own <code>localStorage</code> and makes no "
        "network requests."),
    "col_copy": ("Copiar comando", "Copy command"),
    "col_step3_html": (
        "<strong>Copia el JSON</strong> que devuelve (también se copia al portapapeles o se descarga como archivo) y "
        "pégalo aquí abajo, o elige el archivo.",
        "<strong>Copy the JSON</strong> it returns (it is also copied to the clipboard or downloaded as a file) and "
        "paste it below, or choose the file."),
    "col_json": ("JSON de la colección", "Collection JSON"),
    "col_view": ("Ver mi colección", "Show my collection"),
    "col_file": ("…o un archivo .json", "…or a .json file"),
    "col_limits": ("Límites", "Limits"),
    "col_l1_html": ("<strong>Invitado.</strong> El modo invitado no guarda nada, así que no hay colección que leer. "
                    "Entra con tu cuenta.",
                    "<strong>Guest.</strong> Guest mode saves nothing, so there is no collection to read. Sign in."),
    "col_l2_html": ("<strong>Nube.</strong> La copia en la nube puede ir por detrás de la local, y el comando coge la "
                    "que tiene la fecha de modificación más reciente.",
                    "<strong>Cloud.</strong> The cloud copy can lag behind the local one, and the command takes the "
                    "one with the most recent modification date."),
    "col_l3_html": ("<strong>Otro dispositivo.</strong> La colección guardada allí no se ve hasta que abras tu cuenta "
                    "en este navegador.",
                    "<strong>Another device.</strong> A collection saved there does not show up until you open your "
                    "account in this browser."),
    "col_l4_html": ("<strong>Cambios del juego.</strong> Si el juego cambia las claves de <code>localStorage</code> "
                    "(<code>ps.save.&lt;nombre&gt;</code> y <code>ps.cloud.&lt;uid&gt;</code>, verificadas en "
                    "<code>{commit}</code>), el comando dejará de funcionar.",
                    "<strong>Game changes.</strong> If the game changes its <code>localStorage</code> keys "
                    "(<code>ps.save.&lt;name&gt;</code> and <code>ps.cloud.&lt;uid&gt;</code>, checked at "
                    "<code>{commit}</code>), the command will stop working."),
    "col_l5": ("Los shiny se cuentan aparte. El tier depende solo del número de Pokédex.",
               "Shinies are counted separately. The tier depends only on the Pokédex number."),

    # ------------------------------------------------------------ acerca
    "about_title": ("Acerca y aviso legal · {site}", "About and legal notice · {site}"),
    "about_desc": ("Aviso legal y créditos de {site}.", "Legal notice and credits for {site}."),
    "about_h1": ("Acerca y aviso legal", "About and legal notice"),
    "about_toc_legal": ("Aviso legal", "Legal notice"),
    "about_toc_credits": ("Créditos", "Credits"),
    "about_p_html": (
        'Ranking <code>{version}</code> sobre {game} en el commit <code>{commit}</code> '
        '(<a href="{repo}" rel="noopener">código del juego</a>, <a href="{url}" rel="noopener">el juego</a>). '
        'Generado el {date}. Para actualizarlo hay que regenerar el CSV y publicar de nuevo. El método está '
        'explicado en <a href="{method}">Cómo se calcula</a>.',
        '<code>{version}</code> ranking on {game} at commit <code>{commit}</code> '
        '(<a href="{repo}" rel="noopener">game code</a>, <a href="{url}" rel="noopener">the game</a>). '
        'Generated on {date}. To update it, regenerate the CSV and publish again. The method is explained in '
        '<a href="{method}">How it is calculated</a>.'),
    "about_credits_h": ("Créditos", "Credits"),
    "about_sprites_h": ("Sprites de Pokémon", "Pokémon sprites"),
    "about_sprites_html": (
        'Dibujos de <a href="{url}" rel="noopener">{source}</a>, licencia <a href="{lic_url}" rel="noopener">{lic}</a>. '
        'Entre paréntesis, cuántos números de Pokédex del sitio incluyen alguna aportación de cada artista:',
        'Artwork from <a href="{url}" rel="noopener">{source}</a>, license <a href="{lic_url}" rel="noopener">{lic}</a>. '
        'In brackets, how many Pokédex numbers on the site include some work by each artist:'),
    "about_icons_h": ("Iconos y fuente", "Icons and font"),
    "about_icons_html": (
        'Iconos de interfaz de <a href="{url}" rel="noopener">{author}</a> ({title}), licencia '
        '<a href="{lic_url}" rel="noopener">{lic}</a>, recoloreados. Los iconos de tipo son los glifos del propio juego, '
        'con licencia MIT.',
        'Interface icons by <a href="{url}" rel="noopener">{author}</a> ({title}), license '
        '<a href="{lic_url}" rel="noopener">{lic}</a>, recolored. The type icons are the game\'s own glyphs, '
        'under the MIT license.'),
    "about_font_html": (
        'Tipografía <a href="https://github.com/eifetx/Pixelify-Sans" rel="noopener">Pixelify Sans</a>, '
        'SIL Open Font License 1.1, copiada del repositorio de {game}. La licencia está en '
        '<a href="{root}fonts/OFL.txt">fonts/OFL.txt</a>.',
        'The <a href="https://github.com/eifetx/Pixelify-Sans" rel="noopener">Pixelify Sans</a> typeface, '
        'SIL Open Font License 1.1, copied from the {game} repository. The license is at '
        '<a href="{root}fonts/OFL.txt">fonts/OFL.txt</a>.'),

    # ------------------------------------------------------------ 404
    "nf_title": ("Página no encontrada · {site}", "Page not found · {site}"),
    "nf_h1": ("No encuentro esa página · Page not found", "Page not found · No encuentro esa página"),
    "nf_p_html": ('Puede que el enlace sea antiguo. <a href="/index.html">Vuelve a la tier list</a> o '
                  '<a href="/en/index.html">go back to the tier list</a>.',
                  'The link may be old. <a href="/en/index.html">Go back to the tier list</a> or '
                  '<a href="/index.html">vuelve a la tier list</a>.'),

    # ------------------------------------------------------------ método: gráficos
    "pipe_title": ("Seis pasos de la medida al tier", "Six steps from measurement to tier"),
    "pipe_sub": ("El mismo recorrido para los {total} Pokémon", "The same route for all {total} Pokémon"),
    "pipe_1": ("Se miden tres cosas", "Three things are measured"),
    "pipe_1t": ("Ficha de la especie, partidas simuladas y estimación de final de partida",
                "Species sheet, simulated games and an end-of-game estimate"),
    "pipe_2": ("Cada medida pasa a percentil", "Each measure becomes a percentile"),
    "pipe_2t": ("Cada Pokémon queda entre 0 y 100 % frente a los {total}",
                "Each Pokémon lands between 0 and 100% against the {total}"),
    "pipe_3": ("Se combinan", "They are combined"),
    "pipe_3t": ("Con una media geométrica y pesos de 45, 30 y 25", "With a geometric mean and weights of 45, 30 and 25"),
    "pipe_4": ("Se repite 2.000 veces", "It repeats 2,000 times"),
    "pipe_4t": ("Cada medida con su propio ruido", "Each measure with its own noise"),
    "pipe_5": ("Puesto final", "Final rank"),
    "pipe_5t": ("La mediana de las 2.000 repeticiones", "The median of the 2,000 repeats"),
    "pipe_6": ("Tiers", "Tiers"),
    "pipe_6t": ("Cortes fijos, con un mínimo de estadísticas para S, A y B",
                "Fixed cuts, with a stats minimum for S, A and B"),
    "pipe_alt": ("Pasos del cálculo: ", "Calculation steps: "),
    "w_sheet": ("Ficha de la especie", "Species sheet"),
    "w_sim": ("Partidas simuladas", "Simulated games"),
    "w_late": ("Estimación de final de partida", "End-of-game estimate"),
    "w_sheet_t": (
        "Estadísticas del juego, la mejor pareja de ataques que puede aprender, su defensa de tipos contra los "
        "enemigos reales y el tamaño de su hitbox.",
        "The game stats, the best move pair it can learn, its type defense against the real enemies and the size of "
        "its hitbox."),
    "w_sim_t": (
        "200 partidas en el mapa real, con paredes, agua y obstáculos, y un bot que esquiva. Mide cuánto aguanta con "
        "su ataque inicial y con el mejor ataque que puede aprender.",
        "200 games on the real map, with walls, water and obstacles, and a bot that dodges. It measures how long the "
        "Pokémon lasts with its starting move and with the best move it can learn."),
    "w_late_t": ("Daño y aguante estimados a los minutos 5, 10 y 15, con y sin mejoras permanentes.",
                 "Damage and survivability estimated at minutes 5, 10 and 15, with and without permanent upgrades."),
    "weights_title": ("La ficha pesa casi la mitad de la nota ({w} %)", "The sheet is almost half of the score ({w}%)"),
    "weights_sub": ("Peso de cada medida en la nota combinada", "Weight of each measure in the combined score"),
    "weights_alt": ("Peso de cada pieza en la nota: ", "Weight of each part in the score: "),
    "pw_title": (
        "Dentro de la ficha, las estadísticas pesan más que los ataques, la defensa y el tamaño juntos",
        "Inside the sheet, stats weigh more than moves, defense and size combined"),
    "pw_sub": ("Peso de cada parte en la pieza «ficha de la especie».", "Weight of each part inside the \"species sheet\"."),
    "pw_detail": (" Las estadísticas se reparten en ataque 40, vida 35, velocidad 25.",
                  " Stats split into attack 40, HP 35, speed 25."),
    "pw_alt": ("Pesos de la ficha: ", "Sheet weights: "),
    "tiers_title": ("Los tiers tienen tamaño fijo, con {s} Pokémon en S y {d} en D",
                    "Tiers have a fixed size, with {s} Pokémon in S and {d} in D"),
    "tiers_sub": ("Cada tier ocupa una franja del ranking. El ancho es proporcional a su número de Pokémon",
                  "Each tier takes a slice of the ranking. Width is proportional to its number of Pokémon"),
    "tiers_alt": ("Pokémon por tier: ", "Pokémon per tier: "),
    "gate_title": ("Para llegar a S no basta con rendir, hay que estar en el 40 % superior en estadísticas",
                   "Performing well is not enough to reach S, its stats must be in the top 40%"),
    "gate_sub": ("Zona de percentil de estadísticas que permite cada tier. Esta regla limita a {n} Pokémon",
                 "Stats percentile zone that each tier allows. This rule caps {n} Pokémon"),
    "gate_name": ("Tier {t}", "Tier {t}"),
    "gate_val": ("top {top} %", "top {top}%"),
    "gate_worst": ("peor", "worst"),
    "gate_best": ("mejor", "best"),
    "gate_alt": ("Estadísticas mínimas para cada tier: ", "Minimum stats for each tier: "),
    "gate_alt_item": ("{t}, dentro del {top} % superior", "{t}, within the top {top}%"),
    "agree_title": (
        "Todas las medidas apuntan en la misma dirección: «{hi}» es la que más se parece al ranking final ({hv}) y "
        "«{lo}» la que menos ({lv})",
        "All measures point the same way: \"{hi}\" is the closest to the final ranking ({hv}) and \"{lo}\" is the "
        "furthest ({lv})"),
    "agree_sub": ("Correlación entre el puesto de cada medida y el puesto final. 1 es el mismo orden",
                  "Correlation between each measure's rank and the final rank. 1 means the same order"),
    "agree_alt": ("Correlación con el puesto final: ", "Correlation with the final rank: "),
    "rib_title": ("El puesto es más firme en los extremos. En S la banda típica es de {s} puestos y en {w}, de {m}",
                  "Rank is firmest at the extremes. In S the typical band is {s} places wide and in {w}, {m}"),
    "rib_sub": ("Los 966 Pokémon en orden de puesto final, de mejor a peor",
                "The 966 Pokémon in order of final rank, best to worst"),
    "rib_note1": ("Cada trazo es un Pokémon y cubre el 80 % central de sus 2.000 repeticiones.",
                  "Each stroke is one Pokémon and covers the central 80% of its 2,000 repeats."),
    "rib_note2": ("Los trazos más largos están en el tier {t}: {m} puestos de ancho típico.",
                  "The longest strokes are in tier {t}: {m} places wide on average."),
    "rib_x": ("puesto final", "final rank"),
    "rib_y": ("puesto en las repeticiones", "rank in the repeats"),
    "rib_alt": ("Banda de puestos de cada Pokémon entre las repeticiones. Ancho típico por tier: ",
                "Rank band of each Pokémon across the repeats. Typical width per tier: "),
    "rib_alt_item": ("{t} {m} puestos", "{t} {m} places"),
    "stab_title": ("En {w}, el {wv} % de los Pokémon conserva su tier de forma firme y en {b}, el {bv} %",
                   "In {w}, {wv}% of Pokémon keep their tier firmly, and in {b}, {bv}%"),
    "stab_sub": ("Parte de los Pokémon de cada tier que cae en él en al menos el {share} % de las repeticiones",
                 "Share of each tier's Pokémon that land in it in at least {share}% of the repeats"),
    "stab_alt": ("Tier firme por tier: ", "Firm tier share per tier: "),
    "demo_title": ("Una pieza muy floja arrastra la nota", "One very weak part drags the score down"),
    "demo_sub": (
        "Mueve los deslizadores o elige un Pokémon. La media geométrica castiga a quien falla en una pieza más que "
        "la media normal",
        "Move the sliders or pick a Pokémon. The geometric mean punishes a weak part more than the usual average"),
    "demo_try": ("Prueba con", "Try"),
    "demo_geo": ("Media geométrica (la que usamos)", "Geometric mean (the one we use)"),
    "demo_arith": ("Media aritmética (la de toda la vida)", "Arithmetic mean (the usual one)"),
    "demo_aria": ("Percentil en {name}", "Percentile in {name}"),
    "reps_title": ("Cada repetición mueve un poco a todos y el puesto final es la mediana",
                   "Each repeat nudges everyone a little and the final rank is the median"),
    "reps_sub": (
        "Ilustración. Cada punto salta al azar dentro de su rango real (percentiles 10 a 90). No son las "
        "repeticiones reales. La marca vertical es el puesto final",
        "Illustration. Each dot jumps at random inside its real range (10th to 90th percentile). These are not the "
        "real repeats. The vertical mark is the final rank"),
    "reps_pause": ("Pausa", "Pause"),
    "reps_play": ("Reproducir", "Play"),
    "reps_count": ("repetición {n} de {total}", "repeat {n} of {total}"),

    # ------------------------------------------------------------ método: página
    "met_title": ("Cómo se calcula · {site}", "How it is calculated · {site}"),
    "met_desc": ("Cómo se calcula el ranking de {site}: medidas, pesos, repeticiones y tiers, con gráficos.",
                 "How the {site} ranking is calculated. Measures, weights, repeats and tiers, with charts."),
    "met_h1": ("Cómo se calcula el ranking", "How the ranking is calculated"),
    "met_lead": (
        "Hay {total} Pokémon y una pregunta. Cuáles aguantan mejor en {game}. La respondemos de tres formas, "
        "mezclamos las respuestas y repetimos el cálculo 2.000 veces para saber cuánto nos fiamos del resultado. "
        "Todos los gráficos de esta página usan datos reales del ranking.",
        "There are {total} Pokémon and one question. Which ones survive best in {game}. We answer it three ways, mix "
        "the answers and repeat the calculation 2,000 times to see how far we can trust the result. Every chart on "
        "this page uses real ranking data."),
    "met_walk_h": ("Sigue a un Pokémon", "Follow one Pokémon"),
    "met_walk_p": ("Elige un Pokémon y recorre los cinco pasos con los botones. Los números son suyos.",
                   "Pick a Pokémon and step through the five stages with the buttons. The numbers are its own."),
    "walk_prev": ("Anterior", "Previous"),
    "walk_next": ("Siguiente", "Next"),
    "walk_auto": ("Reproducir solo", "Autoplay"),
    "walk_stop": ("Parar", "Stop"),
    "walk_step": ("Paso {i} de {n}", "Step {i} of {n}"),
    "walk_1_h": ("Se mide de tres formas", "Three measurements"),
    "walk_1_p": (
        "{name} se mide con la ficha de su especie, con partidas simuladas y con una estimación del final de partida. "
        "Cada medida ordena por separado a los {total} Pokémon. El gráfico muestra el puesto de {name} en cada una.",
        "{name} is measured with its species sheet, with simulated games and with an end-of-game estimate. Each "
        "measure ranks all {total} Pokémon separately. The chart shows where {name} lands in each."),
    "walk_2_h": ("Se mezclan con pesos", "They are mixed with weights"),
    "walk_2_p": (
        "La ficha pesa un 45 %, las partidas simuladas un 30 % y el final de partida un 25 %. La mezcla es una media "
        "geométrica, así que una medida muy baja arrastra la nota hacia abajo.",
        "The sheet counts for 45%, simulated games for 30% and the end-game estimate for 25%. The mix is a geometric "
        "mean, so one very low measure pulls the score down."),
    "walk_3_h": ("Se repite 2.000 veces", "It repeats 2,000 times"),
    "walk_3_p": (
        "Ninguna medida es exacta. En cada repetición se sortea otra vez el ruido de las medidas y {name} cambia un "
        "poco de puesto. Aquí salta dentro de su rango habitual, del {lo} al {hi}.",
        "No measure is exact. Each repeat draws the noise of the measures again and {name} shifts a little. Here it "
        "jumps inside its usual range, from {lo} to {hi}."),
    "walk_4_h": ("El puesto es la mediana", "The rank is the median"),
    "walk_4_p": (
        "El puesto final es la mediana de las 2.000 repeticiones. El {rank} de {total}. La banda muestra cuánto se "
        "movió en el 80 % central de ellas.",
        "The final rank is the median of the 2,000 repeats. {rank} of {total}. The band shows how far it moved in the "
        "central 80% of them."),
    "walk_5_h": ("Se asigna el tier", "The tier is assigned"),
    "walk_5_p": (
        "Los tiers tienen tamaño fijo y el puesto {rank} cae en el tier {tier}. En el {share} % de las repeticiones "
        "{name} queda en ese tier.",
        "Tiers have a fixed size and rank {rank} falls in tier {tier}. In {share}% of the repeats {name} lands in "
        "that tier."),
    "walk_tier_alt": ("Puesto {rank} dentro de la tira de tiers", "Rank {rank} inside the tier strip"),
    "met_1_h": ("1. Tres medidas", "1. Three measures"),
    "met_sim_h": ("Una partida simulada", "A simulated game"),
    "met_sim_p": (
        "Cada Pokémon juega 200 partidas en el mapa real del juego, con paredes, agua y obstáculos. Un bot lo mueve "
        "para esquivar y dispara con su ataque. Se anota cuántos segundos aguanta antes de caer, con su ataque "
        "inicial y con el mejor que puede aprender. La mediana de los {total} es de {s} s.",
        "Each Pokémon plays 200 games on the game's real map, with walls, water and obstacles. A bot moves it to "
        "dodge and fires its move. We record how many seconds it lasts before falling, with its starting move and "
        "with the best one it can learn. The median of the {total} is {s} s."),
    "arena_title": ("Así se ve una partida simulada", "What a simulated game looks like"),
    "arena_sub": (
        "Ilustración con {name}: el bot esquiva y dispara mientras los enemigos se acercan. No es una partida "
        "grabada de las 200 que se miden.",
        "Illustration with {name}: the bot dodges and fires while enemies close in. It is not a recording of the 200 "
        "games that are measured."),
    "arena_time": ("tiempo", "time"),
    "arena_kills": ("derrotados", "defeated"),
    "arena_alt": ("Animación de una partida simulada. Un Pokémon esquiva y dispara a enemigos que se acercan.",
                  "Animation of a simulated game. A Pokémon dodges and fires at approaching enemies."),
    "met_2_h": ("2. Una media que castiga los fallos", "2. An average that punishes weak spots"),
    "met_2_p": (
        "Las medidas se combinan con una media geométrica. Un Pokémon con una pieza muy mala no se salva por ser "
        "bueno en las demás. Compara las dos medias con los ejemplos.",
        "The measures are combined with a geometric mean. A Pokémon with one very bad part is not rescued by being "
        "good at the rest. Compare the two averages with the examples."),
    "met_3_h": ("3. Repetir 2.000 veces", "3. Repeating 2,000 times"),
    "met_3_p": (
        "Ninguna medida es exacta, así que se repite todo el cálculo 2.000 veces. En cada repetición se vuelve a "
        "sortear el ruido de las medidas y el peso de las partidas simuladas. El puesto final es la mediana y la "
        "banda del 10 % al 90 % indica cuánto se mueve.",
        "No measure is exact, so the whole calculation repeats 2,000 times. Each repeat draws the noise of the "
        "measures and the weight of the simulated games again. The final rank is the median and the 10% to 90% band "
        "shows how much it moves."),
    "met_3b_p": (
        "«Tier firme» es la parte de los Pokémon de ese tier que cae en él en al menos el {share} % de las "
        "repeticiones. Cuanto más ancha es la banda de un Pokémon, más cerca está del corte con el tier vecino. Por "
        "eso la ficha de cada uno muestra su banda y marca como dudosos los tiers que se repiten en menos de la mitad "
        "de los casos.",
        "\"Firm tier\" is the share of a tier's Pokémon that land in it in at least {share}% of the repeats. The wider "
        "a Pokémon's band, the closer it is to the cut with the neighbouring tier. That is why each Pokémon's page "
        "shows its band and marks tiers that repeat in fewer than half the cases as uncertain."),
    "met_4_h": ("4. Tiers de tamaño fijo", "4. Fixed-size tiers"),
    "met_4_p": (
        "Los tiers cortan el ranking en puestos fijos: {cuts}. Además, las estadísticas limitan el tier máximo.",
        "The tiers cut the ranking at fixed places: {cuts}. In addition, stats limit the maximum tier."),
    "met_cut": ("{t} del {a} al {b}", "{t} from {a} to {b}"),
    "met_5_h": ("5. Cuánto coinciden las medidas", "5. How much the measures agree"),
    "met_5_p": (
        "La ficha sola ya ordena casi como el ranking final. Las partidas simuladas y el final de partida corrigen "
        "los casos en que la ficha engaña, por ejemplo un Pokémon con buenas estadísticas pero un ataque inicial "
        "pobre.",
        "The sheet alone already orders almost like the final ranking. Simulated games and the end-game estimate "
        "fix the cases where the sheet misleads, for example a Pokémon with good stats but a poor starting move."),
    "met_limits_h": ("Límites", "Limits"),
    "met_lim_1": (
        "Cada medida lleva su propio ruido. El ranking se repite 2.000 veces volviendo a sortear ese ruido y el peso "
        "de las partidas simuladas, y el puesto final es la mediana de esas repeticiones.",
        "Each measure carries its own noise. The ranking repeats 2,000 times, drawing that noise and the weight of "
        "the simulated games again, and the final rank is the median of those repeats."),
    "met_lim_2": (
        "Los tiers tienen tamaño fijo. Para entrar en S hacen falta estadísticas dentro del 40 % superior, para A del "
        "60 % y para B del 80 %.",
        "Tiers have a fixed size. To enter S a Pokémon needs stats in the top 40%, for A the top 60% and for B the "
        "top 80%."),
    "met_lim_3": (
        "La simulación no modela quemaduras, veneno ni ralentización, y su bot maneja peor los ataques cuerpo a "
        "cuerpo que una persona. Los Pokémon afectados se marcan en su ficha.",
        "The simulation does not model burn, poison or slow, and its bot handles melee moves worse than a person. "
        "Affected Pokémon are flagged on their page."),
    "met_lim_4": ("Los jefes y las grietas no se modelan.", "Bosses and rifts are not modelled."),
    "met_lim_5": ("Es una estimación propia y no está contrastada con partidas reales.",
                  "It is our own estimate and has not been checked against real games."),
    "met_gloss_h": ("Glosario", "Glossary"),
    "gl_pct": ("Percentil", "Percentile"),
    "gl_pct_d": ("Posición entre los {total} Pokémon. Un 90 % significa mejor que el 90 % de ellos.",
                 "Position among the {total} Pokémon. 90% means better than 90% of them."),
    "gl_med": ("Mediana", "Median"),
    "gl_med_d": ("El valor del medio de una lista ordenada. Un valor extremo no la mueve, a diferencia de la media.",
                 "The middle value of a sorted list. An extreme value does not move it, unlike the mean."),
    "gl_geo": ("Media geométrica", "Geometric mean"),
    "gl_geo_d": ("Una media que multiplica en vez de sumar. Si una pieza es casi cero, toda la nota baja mucho.",
                 "An average that multiplies instead of adding. If one part is close to zero, the whole score drops."),
    "gl_hit": ("Hitbox", "Hitbox"),
    "gl_hit_d": ("La zona donde te pueden golpear. Cuanto más grande es el Pokémon, más golpes recibe.",
                 "The area where you can be hit. The bigger the Pokémon, the more hits it takes."),
    "gl_band": ("Rango habitual", "Usual range"),
    "gl_band_d": ("Los puestos entre los percentiles 10 y 90 de las repeticiones, es decir, el 80 % central.",
                  "The ranks between the 10th and 90th percentile of the repeats, meaning the central 80%."),
    "gl_firm": ("Tier firme", "Firm tier"),
    "gl_firm_d": ("Un Pokémon cuyo tier se repite en al menos el 80 % de las repeticiones.",
                  "A Pokémon whose tier repeats in at least 80% of the repeats."),
    "met_foot_html": ("Ranking <code>{version}</code> sobre {game} en el commit <code>{commit}</code>, generado el {date}.",
                      "<code>{version}</code> ranking on {game} at commit <code>{commit}</code>, generated on {date}."),
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
