"""Constantes del sitio y textos legales en español e inglés. Un solo sitio donde cambiarlos."""
from __future__ import annotations

from i18n import Lang

SITE_NAME = "SurvivorTiers"

GAME_NAME = "PokéSurvivor"
GAME_URL = "https://pokesurvivor.com"   # CNAME del repositorio del juego en a9b21f0
GAME_REPO_URL = "https://github.com/JPTER78/pokesurvivor"
GAME_COMMIT = "a9b21f0"
GAME_AUTHOR = "JPTER78"

MIT_NOTICE = (
    "Colores y glifos de tipo adaptados de js/core/util.js y js/ui/icons.js de PokéSurvivor, "
    "MIT License, Copyright (c) 2026 JPTER78.",
    "Type colors and glyphs adapted from js/core/util.js and js/ui/icons.js of PokéSurvivor, "
    "MIT License, Copyright (c) 2026 JPTER78.",
)

POKEAPI_NOTICE = (
    "Nombres base y estadísticas: PokéAPI and the community (https://pokeapi.co/), fijados en el momento de generar "
    "el sitio.",
    "Base names and stats: PokéAPI and the community (https://pokeapi.co/), frozen when the site is generated.",
)


def legal_sections(L: Lang) -> list[dict]:
    """Bloques de la sección 'Aviso legal' de acerca.html. Cada uno: id, title, html."""
    i = L.idx
    pick = lambda es, en: (es, en)[i]  # noqa: E731
    return [
        {
            "id": "no-oficial",
            "title": pick("Sitio de fans, no oficial", "Fan site, unofficial"),
            "html": pick(
                f"<p>{SITE_NAME} es un proyecto de fans, gratuito y sin ánimo de lucro. "
                "Pokémon, sus personajes y sus nombres son propiedad de Nintendo, Creatures Inc. y GAME FREAK, "
                "y The Pokémon Company gestiona la marca. Ninguna de esas empresas ha creado, revisado ni "
                "aprobado este sitio, y The Pokémon Company no autoriza sitios de fans con su nombre: "
                "por eso el sitio no usa logos oficiales y no lleva «Pokémon» en su nombre.</p>"
                f"<p>Tampoco es parte de {GAME_NAME}: es un análisis independiente de los datos de ese juego "
                f"de fans, creado por {GAME_AUTHOR}.</p>",
                f"<p>{SITE_NAME} is a fan project, free and non-profit. "
                "Pokémon, its characters and its names belong to Nintendo, Creatures Inc. and GAME FREAK, "
                "and The Pokémon Company manages the brand. None of those companies created, reviewed or "
                "approved this site, and The Pokémon Company does not authorize fan sites that use its name: "
                "that is why the site uses no official logos and does not carry \"Pokémon\" in its name.</p>"
                f"<p>It is also not part of {GAME_NAME}: it is an independent analysis of the data of that fan "
                f"game, created by {GAME_AUTHOR}.</p>"),
        },
        {
            "id": "sprites",
            "title": pick("Sprites", "Sprites"),
            "html": pick(
                "<p>Los dibujos son de SpriteCollab, <strong>solo para uso no comercial</strong> y con atribución a sus "
                "artistas, que figuran en <a href=\"#creditos\">Créditos</a>. No se han modificado: son el primer "
                "fotograma de la animación «Idle» mirando hacia abajo, recortado y ampliado sin suavizado. De los "
                "créditos solo se copian nombres y enlaces web.</p>",
                "<p>The artwork is from SpriteCollab, <strong>for non-commercial use only</strong> and credited to its "
                "artists, who are listed under <a href=\"#creditos\">Credits</a>. It is unmodified: each sprite is "
                "the first frame of the \"Idle\" animation facing down, cropped and enlarged without smoothing. Only "
                "names and web links are copied from the credits.</p>"),
        },
        {
            "id": "datos",
            "title": pick("Datos y código", "Data and code"),
            "html": pick(
                f"<p>El sitio lee datos de {GAME_NAME} (<code>{GAME_COMMIT}</code>), cuyo código es MIT "
                f"(Copyright © 2026 {GAME_AUTHOR}), pero no copia su código. "
                f"{POKEAPI_NOTICE[0]} La web no llama a ninguna API: todo está fijado al generar el sitio.</p>"
                f"<p>{MIT_NOTICE[0]}</p>",
                f"<p>The site reads data from {GAME_NAME} (<code>{GAME_COMMIT}</code>), whose code is MIT "
                f"(Copyright © 2026 {GAME_AUTHOR}), but does not copy its code. "
                f"{POKEAPI_NOTICE[1]} The site calls no API: everything is frozen when the site is generated.</p>"
                f"<p>{MIT_NOTICE[1]}</p>"),
        },
        {
            "id": "privacidad",
            "title": pick("Privacidad y dinero", "Privacy and money"),
            "html": pick(
                "<p>No hay cookies, analítica, anuncios, donaciones ni productos, y ninguna criptomoneda, token o NFT "
                "asociado a este sitio ni al juego. "
                "La página «Mi colección» lee el JSON que pegas y lo muestra en tu navegador; no se envía a ningún "
                "servidor y no se guarda. El hosting (Cloudflare) puede registrar peticiones HTTP de forma estándar "
                "fuera de nuestro control.</p>",
                "<p>There are no cookies, analytics, ads, donations or products, and no cryptocurrency, token or NFT "
                "tied to this site or to the game. "
                "The \"My collection\" page reads the JSON you paste and shows it in your browser; it is not sent to "
                "any server and is not stored. The host (Cloudflare) may log HTTP requests in the standard way, "
                "outside our control.</p>"),
        },
        {
            "id": "revision",
            "title": pick("Revisión legal", "Legal review"),
            "html": pick(
                "<p>Este aviso lo ha redactado el autor del sitio, no un abogado. "
                "Si eres titular de derechos y quieres que cambie o retire algo, escribe al autor del repositorio "
                "y se hará.</p>",
                "<p>This notice was written by the site's author, not by a lawyer. "
                "If you hold rights and want something changed or removed, write to the repository's author and it "
                "will be done.</p>"),
        },
    ]
