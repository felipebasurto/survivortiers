"""Página Novedades: la actualización de PokéSurvivor del 18-10-2026 (commit e868b5e de JPTER78/pokesurvivor).

Cada cifra y cada regla sale del código del commit (js/systems/stats.js, levelup.js, judgment.js, enemy.js, spawner.js,
gamepad.js, settings.js) o de su changelog. Si cambia el juego, cambia esta página a mano.
"""
from __future__ import annotations

from html import escape

from i18n import Lang

PATCH_COMMIT = "e868b5e"
GAME_REPO = "https://github.com/JPTER78/pokesurvivor"
BANNER_KEY = "survivortiers.novedades.20261018"

LEDE = (
    "Actualización obligatoria del 18 de octubre de 2026. Todos los rankings empiezan de cero: los puestos de antes "
    "ya no cuentan.",
    "Mandatory update from October 18, 2026. Every leaderboard starts from zero: old positions no longer count.",
)

H1 = ("Novedades", "What's new")

PHYS_SPECIAL = {
    "head": (("Físico", "Physical"), ("Especial", "Special")),
    "rows": [
        (("Ataque que usa", "Attack used"), ("Ataque", "Attack"), ("Ataque Especial", "Special Attack")),
        (("Defensa que te protege", "Defense that protects you"), ("Defensa", "Defense"),
         ("Defensa Especial", "Special Defense")),
        (("Danzas que lo suben", "Dances that raise it"), ("Danza Espada, Danza Dragón", "Swords Dance, Dragon Dance"),
         ("Maquinación (nueva)", "Nasty Plot (new)")),
        (("Ejemplo", "Example"), ("Golpe Kárate", "Karate Chop"), ("Bola Sombra", "Shadow Ball")),
    ],
}

JUDGMENT_FACTS = [
    (("25 %", "25%"), ("Velocidad por encima de 130", "Speed above 130"),
     ("Lo que pasa de 130 cuenta solo un 25 %.", "Anything above 130 counts only 25%.")),
    (("40 → 100 %", "40 → 100%"), ("Toque de Arceus", "Arceus touch"),
     ("Cada toque quita un porcentaje de tu vida máxima: un 40 % al principio de la Sentencia. Desde el minuto 37 "
      "sube hasta el 100 % hacia el minuto 40.",
      "Each touch takes a share of your max HP: 40% at the start of the Judgment. From minute 37 it climbs to 100% "
      "around minute 40.")),
    (("80 %", "80%"), ("Velocidad de los legendarios", "Legendary speed"),
     ("Los legendarios de la Sentencia van al menos al 80 % de la velocidad del más rápido de la partida.",
      "Judgment legendaries run at least 80% of the speed of the fastest player in the run.")),
]

SECTIONS = [
    {
        "id": "fisico-especial",
        "h": ("Ataques físicos y especiales", "Physical and special moves"),
        "body": [
            ("Como en los juegos, cada ataque es físico o especial, y cada Pokémon tiene su Ataque, su Ataque Especial, "
             "su Defensa y su Defensa Especial. Con los ataques de su lado bueno, un Pokémon pega igual que antes.",
             "As in the games, every move is physical or special, and every Pokémon has its own Attack, Special Attack, "
             "Defense and Special Defense. With the moves on its strong side, a Pokémon hits as hard as it did before."),
            ("Las defensas cuentan, pero poco. Con 75 de Defensa recibes lo normal; con mucha, hasta un 22 % menos de "
             "daño; con poca, hasta un 25 % más. Cada enemigo te pega con su lado fuerte, y lo paras con la defensa "
             "de ese lado.",
             "Defenses count, but not by much. At 75 Defense you take normal damage; with a lot, up to 22% less; with "
             "little, up to 25% more. Each enemy hits with its strong side, and you block it with the defense on that side."),
        ],
        "table": PHYS_SPECIAL,
        "after": [
            ("Al subir de nivel, cada carta dice si el ataque es físico o especial. En las cartas de movimiento nuevo, "
             "los de tu lado bueno salen el doble de a menudo, y si un ataque rinde menos del 95 % con tu Pokémon, la carta lo avisa.",
             "Level-up cards say whether a move is physical or special. Among new-move cards, moves on your strong side "
             "show up twice as often, and if a move does less than 95% with your Pokémon, the card says so."),
        ],
    },
    {
        "id": "danzas",
        "h": ("Danzas y Maquinación", "Dances and Nasty Plot"),
        "body": [
            ("Danza Espada y Danza Dragón solo suben el ataque físico. Maquinación, nueva, sube solo el especial y "
             "la puede aprender cualquier Pokémon. Las tres son potenciadores: no hacen daño y duran 7 s. Las dos danzas "
             "comparten contador, así que no se suman. Con dos potenciadores, las cartas de movimiento nuevo ya no "
             "ofrecen más. Los detalles están en Pasivas.",
             "Swords Dance and Dragon Dance now raise only physical attack. Nasty Plot, new, raises only special attack, "
             "and any Pokémon can learn it. All three are boosts: they deal no damage and last 7 s. The two dances share "
             "a counter, so they don't add up. With two boosts, new-move cards stop offering more. Details are in Passives."),
        ],
    },
    {
        "id": "jefes",
        "h": ("Jefes, curanderos y veneno", "Bosses, healers and poison"),
        "list": [
            ("Como mucho hay 3 curanderos, 3 escuderos y 3 invocadores vivos a la vez.",
             "There are at most 3 healers, 3 shielders and 3 summoners alive at a time."),
            ("Los jefes se curan y se protegen según el daño que les haces. Lo que curan o protegen sale de lo que les "
             "has quitado hace poco, y un escudo nuevo llega como mucho cada 6 segundos. Ya no pueden volverse inmatables.",
             "Bosses heal and shield in proportion to the damage you deal them. What they heal or protect comes from "
             "what you took off them recently, and a new shield arrives at most every 6 seconds. They can no longer "
             "become unkillable."),
            ("El veneno sigue quitando un porcentaje de la vida, pero contra enemigos con más de 60.000 PV ese "
             "porcentaje es menor: el daño sube con la raíz de su vida.",
             "Poison still takes a percentage of HP, but against enemies with more than 60,000 HP that percentage is "
             "smaller: the damage grows with the square root of their HP."),
        ],
    },
    {
        "id": "sentencia",
        "h": ("Sentencia de Arceus", "Judgment of Arceus"),
        "body": [
            ("La Sentencia empieza en el minuto 30. Correr ya no basta para alejarse de Arceus: estas son las reglas nuevas.",
             "The Judgment starts at minute 30. Running no longer gets you away from Arceus: these are the new rules."),
        ],
        "facts": JUDGMENT_FACTS,
    },
    {
        "id": "otras",
        "h": ("Mando, apuntado y colección", "Controller, aiming and collection"),
        "list": [
            ("Mando: se puede jugar con Xbox, PlayStation, Switch y la mayoría de mandos USB o Bluetooth. A confirma, B "
             "vuelve, Start pausa, LB y RB cambian de ataque, Y tira las cartas otra vez, y el mando vibra al recibir "
             "daño. Se activa en Ajustes > Controles.",
             "Controller: works with Xbox, PlayStation, Switch and most USB or Bluetooth pads. A confirms, B goes back, "
             "Start pauses, LB and RB switch attacks, Y rerolls the cards, and the pad vibrates when you take damage. "
             "Turn it on in Settings > Controls."),
            ("Apuntar a mano (Ajustes > Accesibilidad, desactivado por defecto): tus ataques de contacto, rayo, proyectil, "
             "bumerán, embestida y cono salen hacia donde apuntas, con el ratón o con el stick derecho, en vez de hacia el "
             "enemigo más cercano.",
             "Manual aim (Settings > Accessibility, off by default): your melee, beam, projectile, boomerang, dash and cone "
             "attacks go where you point, with the mouse or the right stick, instead of at the nearest enemy."),
            ("Cartas que no se eligen sin querer: las de nivel, vínculo y objeto se ven apagadas 0,6 segundos al aparecer. "
             "Pulsar 1-4 o tocar la pantalla para cambiar de ataque en plena pelea ya no elige una carta por error.",
             "Cards you cannot pick by accident: level-up, bond and item cards look dimmed for 0.6 seconds when they "
             "appear. Pressing 1-4 or tapping to switch attacks mid-fight no longer picks a card by mistake."),
            ("Pokémon grandes jugables: Onix, Gyarados, Wailord, Eternatus y los legendarios se dibujan algo más pequeños "
             "y chocan como uno normal, así que caben por los pasillos.",
             "Big Pokémon are playable: Onix, Gyarados, Wailord, Eternatus and the legendaries are drawn a bit smaller and "
             "collide like a normal one, so they fit through the corridors."),
            ("Pausa: el resumen de la partida enseña cada ataque con su categoría, su daño y su daño por segundo, y tus "
             "estadísticas con todo lo que has subido.",
             "Pause: the run summary lists each move with its category, its damage and its damage per second, plus your "
             "stats with everything you have raised."),
            ("Colección: buscador por nombre o número, pestaña con todas las generaciones, filtros que se combinan y orden "
             "por número, nombre, rareza, recién conseguidos o más usados. Los favoritos se marcan en la ficha y van con "
             "tu cuenta.",
             "Collection: search by name or number, a tab with every generation, filters that combine, and sorting by "
             "number, name, rarity, latest catch or most used. Favorites are set on each Pokémon's card and follow your "
             "account."),
            ("Guardado: la partida se sube a la nube cada 10 minutos, y hay un botón Guardar arriba a la derecha.",
             "Saving: your game uploads to the cloud every 10 minutes, and there is a Save button at the top right."),
        ],
    },
    {
        "id": "ranking",
        "h": ("Ranking", "Leaderboards"),
        "list": [
            ("Todos los rankings empiezan de cero: hoy, semana, mes, año e histórico. Los récords de huir de Arceus ya no "
             "se podrían alcanzar, por eso también empiezan de cero.",
             "Every leaderboard starts from zero: daily, weekly, monthly, yearly and all-time. Records from running away "
             "from Arceus could no longer be reached, which is why they start from zero too."),
            ("Seguridad: se cerró un agujero por el que alguien podía meter código en su fila del ranking y ejecutarlo en "
             "el navegador de quien la abriera. Ahora todo lo que viene de otros jugadores se limpia al leerlo.",
             "Security: a hole let someone put code in their leaderboard row and run it in the browser of whoever opened "
             "it. Everything that comes from other players is now cleaned when it is read."),
        ],
    },
]

FOOT = (
    'El texto sale del changelog del juego en el commit {commit}. La tier list se recalcula con esta versión; los puestos '
    'de las fichas pueden cambiar hasta que termine. <a href="{repo}" rel="noopener">Código del juego en GitHub</a>.',
    'The text comes from the game changelog at commit {commit}. The tier list is being recalculated for this version, so '
    'positions on the pages may change until it finishes. <a href="{repo}" rel="noopener">Game code on GitHub</a>.',
)

BANNER = {
    "text": ("El ranking se está recalculando por la actualización del 18 de octubre. Los puestos pueden cambiar.",
             "The ranking is being recalculated for the October 18 update, so positions may change."),
    "link": ("Qué ha cambiado", "What changed"),
    "close": ("Cerrar aviso", "Dismiss notice"),
    "title": ("Novedades de {game} · {site}", "What's new in {game} · {site}"),
    "desc": ("Qué cambia en {game} con la actualización del 18 de octubre de 2026: ataques físicos y especiales, "
             "Maquinación, jefes, la Sentencia de Arceus y el mando.",
             "What changes in {game} with the October 18, 2026 update: physical and special moves, Nasty Plot, bosses, "
             "Arceus' Judgment and the controller."),
}


def _pick(L: Lang, pair: tuple[str, str]) -> str:
    return pair[1] if L.en else pair[0]


def _li(L: Lang, items) -> str:
    return "".join(f"<li>{escape(_pick(L, it))}</li>" for it in items)


def _table(L: Lang, t: dict) -> str:
    head = "<td></td>" + "".join(f'<th scope="col">{escape(_pick(L, h))}</th>' for h in t["head"])
    rows = "".join(
        f'<tr><th scope="row">{escape(_pick(L, r[0]))}</th><td>{escape(_pick(L, r[1]))}</td>'
        f'<td>{escape(_pick(L, r[2]))}</td></tr>'
        for r in t["rows"])
    return (f'<div class="nv-table-wrap"><table class="nv-table"><thead><tr>{head}</tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def _facts(L: Lang, facts) -> str:
    cards = "".join(
        f'<article class="nv-fact"><b class="nv-num">{escape(_pick(L, num))}</b>'
        f'<h3>{escape(_pick(L, title))}</h3><p>{escape(_pick(L, text))}</p></article>'
        for num, title, text in facts)
    return f'<div class="nv-facts">{cards}</div>'


def _section(L: Lang, i: int, s: dict) -> str:
    parts = [f'<section class="nv-sec" id="{s["id"]}" aria-labelledby="{s["id"]}-h">',
             f'<header class="nv-sec-head"><span class="nv-idx" aria-hidden="true">{i:02d}</span>'
             f'<h2 id="{s["id"]}-h">{escape(_pick(L, s["h"]))}</h2></header>']
    for text in s.get("body", []):
        parts.append(f"<p>{escape(_pick(L, text))}</p>")
    if "table" in s:
        parts.append(_table(L, s["table"]))
    for text in s.get("after", []):
        parts.append(f"<p>{escape(_pick(L, text))}</p>")
    if "facts" in s:
        parts.append(_facts(L, s["facts"]))
    if "list" in s:
        parts.append(f'<ul class="nv-list">{_li(L, s["list"])}</ul>')
    parts.append("</section>")
    return "".join(parts)


def content(L: Lang) -> str:
    sections = "".join(_section(L, i, s) for i, s in enumerate(SECTIONS, 1))
    foot = _pick(L, FOOT).format(commit=PATCH_COMMIT, repo=escape(GAME_REPO, quote=True))
    return f"""
<div class="nv">
<h1>{escape(_pick(L, H1))}</h1>
<p class="lede nv-lede">{escape(_pick(L, LEDE))}</p>
{sections}
<p class="nv-foot">{foot}</p>
</div>
"""


def patch_note(L: Lang, home: str) -> str:
    """Aviso del tablero. Empieza oculto: app.js lo muestra si no lo han cerrado antes."""
    text = escape(_pick(L, BANNER["text"]))
    link = escape(_pick(L, BANNER["link"]))
    close = escape(_pick(L, BANNER["close"]), quote=True)
    return (f'<aside class="patch-note" id="patch-note" hidden>'
            f'<p>{text} <a href="{home}novedades.html">{link}</a></p>'
            f'<button class="patch-note-x" type="button" id="patch-note-close" aria-label="{close}" title="{close}">'
            f'&times;</button></aside>')


def title(L: Lang, site: str, game: str) -> str:
    return _pick(L, BANNER["title"]).format(game=game, site=site)


def desc(L: Lang, game: str) -> str:
    return _pick(L, BANNER["desc"]).format(game=game)
