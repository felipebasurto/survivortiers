# SurvivorTiers

Tier list de fans (no oficial) de [PokéSurvivor](https://pokesurvivor.com). Sitio estático en español (raíz) e inglés (`/en/`). Un generador en Python (solo biblioteca estándar, 3.9+) emite HTML y JSON, y el navegador usa JS sin dependencias.

Web: https://survivortiers.pages.dev

## Estructura

| Ruta | Qué hay |
| --- | --- |
| `data/` | Entradas: ranking definitivo (`ranking_definitive.csv`), `pokedex_export.json`, nombres y textos de ataques en inglés (`species_names_en.csv`, `lang_en_moves.json`), `CREDITS.md` y licencia del juego (copiados del commit `a9b21f0`), y `move_tierlist_v4.csv` |
| `sprites/` | Los 966 sprites (SpriteCollab, CC BY-NC 4.0). **No van en `site/`**: las páginas los piden a jsDelivr, que sirve este repositorio (`legal.SPRITE_CDN`) |
| `src/` | Estáticos escritos a mano: `style.css`, `app.js` (tier list, colección, demos), `ficha.js` (dibuja la ficha), `fonts/`, `img/` (iconos de interfaz y créditos) y `_headers` |
| `build/catalog.py` | Valida y genera `build/out/` (datos intermedios y `public/`, los JSON del navegador). **Falla** si falta artista o licencia de algún sprite, si los conteos por tier no son 30/90/200/300/346 o si los pools de gacha no suman 966 |
| `build/render.py` | Genera `site/` entero: 6 páginas por idioma, la plantilla `pokemon/index.html` de cada idioma, `404.html`, `style.css`, `app.js`, la letra, `data/` y `_headers`. Unos 25 archivos y menos de 2 MB |
| `build/pack.py` | Empaqueta `src/` en `site/`: iconos dentro del CSS, CSS y JS minificados, JSON copiados |
| `build/i18n.py` | Todos los textos en español e inglés, validados al importar |
| `build/agents.py` | Archivos para agentes de IA y buscadores: `llms.txt`, `llms-full.txt` (diccionario de datos y método), `robots.txt`, `sitemap.xml`, `data/ranking.csv`, `data/meta.json`, `data/gachas.json` y el JSON-LD `Dataset` de la portada |
| `build/charts.py` | Gráficos HTML, CSS y SVG (la ficha usa las mismas fórmulas en `src/ficha.js`) |
| `build/regions.py` | Insignias de región de la página Gacha (SVG propio y sprites de los legendarios de portada) |
| `build/serve.py` | Servidor local con el mismo comportamiento que el hosting: 404.html con estado 404 y `/_sprites/` |
| `build/move_tierlist_v4.py` | Regenera `data/move_tierlist_v4.csv` (necesita el análisis y una copia del juego) |
| `build/check_site.py` | Comprobaciones de aceptación sobre un sitio servido |
| `console/coleccion.js`, `coleccion.en.js` | Comando que el jugador pega en la consola del juego |

## Uso

```sh
export SPRITE_BASE=http://127.0.0.1:8765/_sprites/    # solo en local: sprites desde sprites/ en vez de jsDelivr
python3 build/catalog.py && python3 build/render.py   # genera site/
python3 build/serve.py                                # ver en local, http://127.0.0.1:8765/
python3 build/check_site.py http://127.0.0.1:8765/    # enlaces, atribución, datos de las 966 fichas, presupuesto de site/
python3 build/check_site.py http://127.0.0.1:8765/ --external   # además, enlaces externos (red)
```

`check_site.py` dibuja una muestra de fichas en un navegador si tienes Playwright (`pip install playwright`); con `--all-species` dibuja las 966 de cada idioma.

`site/` y `build/out/` son salida generada y no se versionan. Para publicar, genera el sitio **sin** `SPRITE_BASE` y ejecuta `npx wrangler deploy` (Cloudflare Workers, ver `wrangler.jsonc`). `vercel.json` queda por si se despliega allí.

### Fichas y sprites

- Cada idioma tiene una sola plantilla de ficha, `/pokemon/?id=25` y `/en/pokemon/?id=25`. `src/ficha.js` la dibuja con `data/pokemon-index.json`, `data/species.json` y `data/moves.json`. Los enlaces viejos `/pokemon/25.html` caen en `404.html` (el hosting la sirve para lo que no existe), y `app.js` los reenvía a la ficha.
- Los sprites salen de `https://cdn.jsdelivr.net/gh/felipebasurto/survivortiers@main/sprites/<n>.png`. Si cambias el repositorio, el usuario o la rama, ajusta `SPRITE_CDN` en `build/legal.py` y el `img-src` de `src/_headers` y `vercel.json` (`check_site.py` comprueba que coincidan). jsDelivr guarda `@main` unas horas: un sprite nuevo tarda en verse.

## Para agentes de IA

El sitio es estático y no tiene API: los datos son JSON y CSV en `/data/`, sin clave de acceso. La documentación para agentes sale del build:

- `/llms.txt`: índice del sitio y de los datos, con enlaces absolutos.
- `/llms-full.txt`: qué significa cada campo, las unidades, el método completo y ejemplos (`curl`, `jq`).
- `/data/ranking.csv` es el ranking tal cual lo genera `make_definitive.py` (sin la línea de comentario), y `/data/meta.json` tiene los pesos, los tiers y los requisitos de entrada.
- Las fichas (`/pokemon/?id=N`) se dibujan con JavaScript; para un agente son más útiles los JSON.

`build/check_site.py` comprueba que estos archivos existan, que los enlaces de `llms.txt` respondan, que el sitemap tenga una entrada por página y que cada página enlace los archivos. La URL base de los enlaces absolutos está en `build/legal.py` (`SITE_URL`, o la variable de entorno `SITE_URL`).

## Actualizar el ranking

1. Regenera `ranking_definitive.csv` con el análisis y cópialo a `data/`.
2. Si cambia el juego: actualiza `data/pokedex_export.json`, `data/CREDITS.md` y `data/GAME_LICENSE.txt`, y el commit en `build/legal.py` (`GAME_COMMIT`).
3. `python3 build/move_tierlist_v4.py --game /ruta/al/juego` para los ataques.
4. `python3 build/catalog.py && python3 build/render.py && python3 build/check_site.py …`.

Si cambian los tamaños de tier (`TIER_CUTS`) o los conteos esperados, ajusta `build/catalog.py`.

## Licencias

- Código de este sitio: ver el repositorio. Código adaptado del juego (colores y glifos de tipo): MIT, © 2026 JPTER78 (aviso en `data/GAME_LICENSE.txt` y en la página Acerca).
- Sprites: SpriteCollab, CC BY-NC 4.0 (uso no comercial). Por eso el sitio no puede llevar anuncios, donaciones ni ninguna monetización.
- Pokémon y sus nombres son marcas de Nintendo, Creatures Inc., GAME FREAK y The Pokémon Company; el sitio es de fans y no está afiliado.
- El texto legal lo ha redactado el autor del sitio, no un abogado.
