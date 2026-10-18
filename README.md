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
| `build/theme.py` | Tema claro u oscuro: el script de `<head>` que aplica la elección antes del primer pintado, y su huella sha256 para la CSP de `src/_headers` y `vercel.json` |
| `build/agents.py` | Archivos para agentes de IA y buscadores: `llms.txt`, `llms-full.txt` (diccionario de datos y método), `robots.txt`, `sitemap.xml`, `data/ranking.csv`, `data/meta.json`, `data/gachas.json` y el JSON-LD `Dataset` de la portada |
| `build/combos.py` | La build de cada Pokémon: el mejor ataque de la simulación, dos de cobertura, el potenciador y tres ataques opcionales (`species.json`, posición 9). Los objetos recomendados salen de `build/objetos.py` y son los mismos para todos |
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
- El script en línea del tema (`build/theme.py`) va permitido por huella sha256 en `script-src` de `src/_headers` y `vercel.json`. Si cambias ese script, `render.py` se niega a generar el sitio hasta que pongas la huella que imprime (`python3 -c "import sys; sys.path.insert(0,'build'); import theme; print(theme.csp_hash())"`).
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
4. Rehaz los resúmenes de las fichas que cambiaron (ver «Resúmenes de la ficha»).
5. `python3 build/catalog.py && python3 build/render.py && python3 build/check_site.py …`.

Si cambian los tamaños de tier (`TIER_CUTS`) o los conteos esperados, ajusta `build/catalog.py`.

## Resúmenes de la ficha

Las tres líneas bajo el nombre de cada ficha (perfil, build y por qué ese puesto) salen de `data/summaries.json`. Las escriben subagentes Grok a partir de los datos, y un comprobador rechaza cualquier afirmación que no respalde un dato. Hay que repetirlo cuando cambie el ranking, la build o la simulación; si no, `catalog.py` falla. Para estas etapas necesitas `pip install numpy "pyarrow<17" duckdb pandas` (el build del sitio sigue usando solo la biblioteca estándar).

| Etapa | Comando | Qué hace |
| --- | --- | --- |
| 1. Datos | `python3 build/facts_export.py` | Escribe `data/facts.parquet`, una fila por Pokémon: percentiles de estadísticas, hitbox, tipos y emparejamientos, ataque inicial y grupo de 4, objeto, cartas, tier y puesto, y los factores del puesto (contrafactuales de `simulator/counterfactual_bench.py`). Es determinista: `--check` falla si el archivo no es el que dan los datos de hoy |
| 2. Lotes | `python3 build/summary_pipeline.py plan` | Elige los Pokémon cuya fila cambió, que no tienen texto o cuyo texto ya no pasa (`--all`: los 966), los parte en lotes de unos 40 y escribe un prompt por lote en `.cache/summaries/` a partir de `build/prompts/summary.md` |
| 3. Escritura | un subagente por prompt | Un agente Grok 4.7 por lote, todos en paralelo. Cada uno lee su parte del parquet con duckdb y escribe `.cache/summaries/out/<ronda>-<lote>.jsonl`, una línea `{"dex", "es", "en"}` por Pokémon |
| 4. Comprobación | `python3 build/summary_pipeline.py validate` | Pasa el comprobador (`build/summaries.py`) a cada salida. Para lo que falla escribe prompts de reintento con el error concreto; tras 2 reintentos el Pokémon queda marcado |
| 5. Montaje | `python3 build/summary_pipeline.py assemble` | Escribe `data/summaries.json`, con la huella `fp` de la fila de datos de cada texto. Esa huella hace de caché: la próxima vez solo se reescriben las filas que cambiaron |

`python3 build/summary_pipeline.py check` valida `data/summaries.json` contra el parquet, y `python3 -m unittest build/test_summaries.py` prueba el comprobador. `catalog.py` repite la comprobación con la biblioteca estándar (todo menos los factores del puesto, que necesitan numpy) y para el build si un texto ya no cuadra con los datos actuales.

## Licencias

- Código de este sitio: ver el repositorio. Código adaptado del juego (colores y glifos de tipo): MIT, © 2026 JPTER78 (aviso en `data/GAME_LICENSE.txt` y en la página Acerca).
- Sprites: SpriteCollab, CC BY-NC 4.0 (uso no comercial). Por eso el sitio no puede llevar anuncios, donaciones ni ninguna monetización.
- Letras: Pixelify Sans (títulos y tiers) y Zen Kaku Gothic New (texto y números), SIL OFL 1.1. Zen Kaku Gothic New va recortada a latino en `src/fonts/ZenKakuGothicNew-400.woff2`, `ZenKakuGothicNew-500.woff2` y `ZenKakuGothicNew-700.woff2`; las licencias están en `src/fonts/`.
- Pokémon y sus nombres son marcas de Nintendo, Creatures Inc., GAME FREAK y The Pokémon Company; el sitio es de fans y no está afiliado.
- El texto legal lo ha redactado el autor del sitio, no un abogado.
