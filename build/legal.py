"""Constantes del sitio y textos legales en español e inglés. Un solo sitio donde cambiarlos."""
from __future__ import annotations

import os

from i18n import GAME_NAME, SITE_NAME, Lang


def method_counts(L: Lang, meta: dict) -> dict[str, str]:
    """Partidas simuladas por Pokémon y repeticiones del cálculo, con el formato de idioma. Los textos los citan."""
    return {"sims": L.num(meta["simSeeds"]), "reps": L.num(meta["method"]["repeats"])}


def freshness_text(L: Lang, meta: dict) -> str:
    """Línea «Datos del juego»: el commit con que se calculó el ranking, el de las mecánicas y la fecha del build."""
    return L.t("fresh", sha=meta["gameCommit"][:7], combat=COMBAT_COMMIT[:7], date=meta["generatedAt"][:10])


X_HANDLE = "@fildotai"
# Token público del sitio de Cloudflare Web Analytics para survivortiers.pages.dev (aparece en el HTML).
WEB_ANALYTICS_TOKEN = "b25b980b4c074c92883d29239edc0bea"
X_URL = "https://x.com/fildotai"
GAME_URL = "https://pokesurvivor.com"   # CNAME del repositorio del juego en a9b21f0
GAME_REPO_URL = "https://github.com/JPTER78/pokesurvivor"
# LICENSE del juego en main: MIT hasta b297089 (14 oct 2026); el código posterior es PolyForm Noncommercial 1.0.0.
GAME_LICENSE_URL = GAME_REPO_URL + "/blob/main/LICENSE"
REPO_URL = "https://github.com/felipebasurto/survivortiers"
# Full upstream commit: e868b5eb3cd55499cd41de543ee032b48a344e71 (18 Oct 2026).
# The ranking and the combat fields (pa/sa/df/sd) both come from that commit.
GAME_COMMIT = "e868b5e"
COMBAT_COMMIT = "e868b5e"
GAME_AUTHOR = "JPTER78"

# URL pública del sitio, para los enlaces absolutos de llms.txt, llms-full.txt y sitemap.xml (build/agents.py).
SITE_URL = os.environ.get("SITE_URL", "https://survivortiers.pages.dev").rstrip("/")

# Los sprites no viajan en site/ (presupuesto de 50 archivos). Salen de este repositorio (sprites/) a través de jsDelivr,
# que los sirve con CORS abierto y caché, como WebP sin pérdida (sprites/*.webp, ~270 KB los 966 frente a 3,8 MB en PNG;
# los genera build/webp.py). SPRITE_BASE en el entorno lo cambia, por ejemplo para ver el sitio en local con build/serve.py.
SPRITE_CDN = "https://cdn.jsdelivr.net/gh/felipebasurto/survivortiers@main/sprites/"
SPRITE_BASE = os.environ.get("SPRITE_BASE", SPRITE_CDN)
SPRITE_EXT = os.environ.get("SPRITE_EXT", ".webp")
# Respaldo si jsDelivr falla (lo hace app.js): el mismo archivo directamente desde GitHub. Solo con el CDN por defecto.
SPRITE_ALT = os.environ.get(
    "SPRITE_ALT", "https://raw.githubusercontent.com/felipebasurto/survivortiers/main/sprites/" if SPRITE_BASE == SPRITE_CDN else "")

MIT_NOTICE = (
    "Colores y glifos de tipo adaptados de js/core/util.js y js/ui/icons.js de PokéSurvivor, "
    "MIT License, Copyright (c) 2026 JPTER78.",
    "Type colors and glyphs adapted from js/core/util.js and js/ui/icons.js of PokéSurvivor, "
    "MIT License, Copyright (c) 2026 JPTER78.",
)

POKEAPI_NOTICE = (
    "Nombres y estadísticas base: PokéAPI (https://pokeapi.co/).",
    "Base names and stats: PokéAPI (https://pokeapi.co/).",
)


def legal_sections(L: Lang) -> list[dict]:
    """Bloques de la sección 'Aviso legal' de acerca.html. Cada uno: id, title, html."""
    i = L.idx
    pick = lambda es, en: (es, en)[i]  # noqa: E731
    return [
        {
            "id": "no-oficial",
            "title": pick("Sitio de fans", "Fan site"),
            "html": pick(
                f"<p>{SITE_NAME} es un proyecto de fans, gratuito y sin ánimo de lucro. Pokémon, sus personajes y "
                "sus nombres son marcas de Nintendo, Creatures Inc., GAME FREAK y The Pokémon Company. Ninguna de "
                "ellas ha creado, revisado ni aprobado este sitio. Tampoco forma parte de "
                f"{GAME_NAME}: es un análisis independiente de ese juego de fans, creado por {GAME_AUTHOR}.</p>"
                "<p>Este aviso lo ha escrito el autor del sitio, no un abogado. Si eres titular de derechos y "
                "quieres que cambie o retire algo, escribe al autor del repositorio.</p>",
                f"<p>{SITE_NAME} is a free, non-profit fan project. Pokémon, its characters and its names are "
                "trademarks of Nintendo, Creatures Inc., GAME FREAK and The Pokémon Company. None of them created, "
                f"reviewed or approved this site. It is also not part of {GAME_NAME}: it is an independent analysis "
                f"of that fan game, created by {GAME_AUTHOR}.</p>"
                "<p>The author of the site wrote this notice, not a lawyer. If you hold rights and want something "
                "changed or removed, write to the repository's author.</p>"),
        },
        {
            "id": "sprites",
            "title": pick("Sprites", "Sprites"),
            "html": pick(
                "<p>Dibujos de SpriteCollab, <strong>solo para uso no comercial</strong> (CC BY-NC 4.0), con sus "
                "artistas en <a href=\"#creditos\">Créditos</a>. Sin cambios: primer fotograma de «Idle» mirando "
                "hacia abajo, recortado y ampliado sin suavizado.</p>",
                "<p>Artwork from SpriteCollab, <strong>for non-commercial use only</strong> (CC BY-NC 4.0), with its "
                "artists under <a href=\"#creditos\">Credits</a>. Unmodified: first frame of \"Idle\" facing down, "
                "cropped and enlarged without smoothing.</p>"),
        },
        {
            "id": "datos",
            "title": pick("Datos y código", "Data and code"),
            "html": pick(
                f"<p>Datos de {GAME_NAME} (Copyright © 2026 {GAME_AUTHOR}), de código "
                f'<a href="{GAME_LICENSE_URL}" rel="noopener">MIT hasta el commit b297089; desde el 14 oct 2026 '
                f"el código nuevo es PolyForm Noncommercial 1.0.0</a>. No se copia su código. "
                f"{POKEAPI_NOTICE[0]}</p><p>{MIT_NOTICE[0]}</p>",
                f"<p>Data from {GAME_NAME} (Copyright © 2026 {GAME_AUTHOR}), whose code is "
                f'<a href="{GAME_LICENSE_URL}" rel="noopener">MIT up to commit b297089; from 14 Oct 2026 '
                f"new code is PolyForm Noncommercial 1.0.0</a>. Its code is not copied. "
                f"{POKEAPI_NOTICE[1]}</p><p>{MIT_NOTICE[1]}</p>"),
        },
        {
            "id": "privacidad",
            "title": pick("Privacidad", "Privacy"),
            "html": pick(
                "<p>Sin cookies, analítica, anuncios ni donaciones. «Mi colección» guarda tu colección solo en el "
                "almacenamiento local de este navegador (localStorage): no se envía a ningún servidor y puedes borrarla "
                "con el botón de la propia página. El hosting (Cloudflare) puede registrar peticiones HTTP de forma "
                "estándar.</p>",
                "<p>No cookies, analytics, ads or donations. \"My collection\" keeps your collection only in this "
                "browser's local storage (localStorage): it is never sent to a server, and you can delete it with the "
                "button on the page. The host (Cloudflare) may log HTTP requests as usual.</p>"),
        },
    ]
