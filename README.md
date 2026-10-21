# SurvivorTiers

Tier list de fans (no oficial) de [PokéSurvivor](https://pokesurvivor.com). Sitio estático en español (raíz) e inglés (`/en/`). Un generador en Python (solo biblioteca estándar, 3.9+) emite HTML y JSON, y el navegador usa JS sin dependencias.

Web: https://survivortiers.pages.dev

## Estructura

| Ruta | Qué hay |
| --- | --- |
| `data/` | Entradas: las tablas de las tres fases (`attack_tiers.csv`, `bond_tiers.csv`, `species_builds.csv`, `ranking_fase3.csv`, variantes en `species_variants.csv`) y el porqué (`species_why.csv`), `pokedex_export.json`, nombres y textos de ataques en inglés (`species_names_en.csv`, `lang_en_moves.json`), `CREDITS.md` y licencia del juego (copiados del commit `a9b21f0`), y `move_tierlist_v4.csv` |
| `sprites/` | Los 966 sprites (SpriteCollab, CC BY-NC 4.0). **No van en `site/`**: las páginas los piden a jsDelivr, que sirve este repositorio (`legal.SPRITE_CDN`). `sprites/shiny/` tiene los 958 sprites shiny (ver `build/shiny_sprites.py`) |
| `src/` | Estáticos escritos a mano: `style.css`, `app.js` (tier list, colección, vista shiny), `collection.js` (lee el comando de la consola y las filas shiny, sin DOM), `share.js` (codec del enlace `#c=`, v1 y v2), `ficha.js` (redirige `/pokemon/?id=N` a la ficha estática), `fonts/`, `img/` (iconos de interfaz y créditos), `_headers` y `_redirects` |
| `build/catalog.py` | Valida y genera `build/out/` (datos intermedios y `public/`, los JSON del navegador). **Falla** si falta artista o licencia de algún sprite, si los conteos por tier no son los de `data/tiers.json` o si los pools de gacha no suman 966 |
| `build/game_moves.py` | Datos de movimientos copiados del juego en `GAME_REF` (5a23d49): la lista física (`js/data/moves.js:620-630`) y las notas de los potenciadores. Las cifras de los 6 potenciadores salen de `data/game_stats.json` y no tienen puesto: la tier list solo ordena ataques. `test_game_moves.py` los compara con el juego si `POKESURVIVOR_DIR` apunta a una copia |
| `build/picks.py` | La única lógica de selección: mejor ataque de cada especie (la nota más alta del simulador, sin ajustes), grupos válidos (al menos 2 ataques y como máximo 4 huecos), forma del grupo, intervalos. La usan `builds.py`, `bond_tiers.py` y `species_builds.py` |
| `data/tiers.json`, `build/tiers.py` | Tamaño de cada tier y bandas: el único sitio donde viven los cortes |
| `build/attack_tiers.py` | Fase 1: tier list de ataques. Cada ataque juega solo en 6 Pokémon de referencia de su clase |
| `build/bond_tiers.py` | Fase 2: tier list de vínculos. Grupos de cuatro huecos con los mejores ataques de la fase 1 |
| `build/species_builds.py` | Fase 3: la mejor build cuerpo a cuerpo y la mejor a distancia de cada Pokémon, el ranking que sale de ellas y, con `--variants`, la variante agresiva (sin potenciador de defensa) y la de más cobertura de tipos de cada build |
| `build/coverage.py` | Cobertura de tipos de una build contra las especies que salen como enemigos (tabla de tipos del juego). La usan la ficha, la página Tipos (`build/tipos.py`) y las variantes |
| `build/builds.py` | Los grupos posibles de cada Pokémon (su pool, su ataque inicial y las tres formas de cuatro huecos), sin reglas a mano |
| `build/why.py` | Por qué cada Pokémon está donde está: mínimos cuadrados de la puntuación frente a ocho factores del juego (necesita numpy) |
| `build/sitefixture.py` | Las pruebas que necesitan el sitio generado lo generan primero (o se saltan con un aviso claro) |
| `build/sync_lang_en.py` | Completa `data/lang_en_moves.json` con los nombres de ataques del juego |
| `build/render.py` | Genera `site/` entero: las páginas de cada idioma, las 966 fichas estáticas (`build/static_ficha.py`), `404.html`, `style.css`, `app.js`, la letra, `data/`, `_headers` y `_redirects` |
| `build/pack.py` | Empaqueta `src/` en `site/`: iconos dentro del CSS, CSS y JS minificados, JSON copiados |
| `build/i18n.py` | Todos los textos en español e inglés, validados al importar |
| `build/theme.py` | Tema claro u oscuro: el script de `<head>` que aplica la elección antes del primer pintado, y su huella sha256 para la CSP de `src/_headers` y `vercel.json` |
| `build/agents.py` | Archivos para agentes de IA y buscadores: `llms.txt`, `llms-full.txt` (diccionario de datos y método), `robots.txt`, `sitemap.xml`, `data/ranking.csv`, `data/meta.json`, `data/gachas.json` y el JSON-LD `Dataset` de la portada |
| `build/static_ficha.py` | La ficha de cada Pokémon: por qué está ahí, cuánto aguanta, sus dos builds, sus stats del juego y cómo conseguirlo |
| `build/objetos.py`, `build/pasivas.py` | Objetos y cartas de nivel tal cual los define el código del juego, sin tiers: no se han simulado |
| `build/regions.py` | Insignias de región de la página Gacha (SVG propio y sprites de los legendarios de portada) |
| `build/serve.py` | Servidor local con el mismo comportamiento que el hosting: 404.html con estado 404 y `/_sprites/` |
| `build/shiny_sprites.py` | Deriva qué especies pueden ser shiny (`data/shiny_species.json`) desde los metadatos de sprites del juego, en un commit fijo, y recorta sus sprites shiny a `sprites/shiny/`. Sin argumentos comprueba el repositorio del juego en caché; `--fetch` lo descarga |
| `build/import_game_combat.py` | Añade a `data/pokedex_export.json` `pa`, `sa`, `df` y `sd` (ataque físico y especial, Defensa y Def. Especial) desde `js/data/pokedex.js` del juego en el commit `5a23d49`. Comprueba que hp, spd, atk, tipos, rareza y generación no hayan cambiado |
| `build/landing.py` | Las 20 páginas de consulta por idioma (mejores Pokémon, legendarios y uno por tipo), generadas solo desde los datos del build. Ver «Páginas de consulta» |
| `build/export_game_stats.js` | Lee `js/data/moves.js`, `pokedex.js` y `lang-en.js` de una copia del juego (`node build/export_game_stats.js /ruta/al/juego`) y escribe `data/game_stats.json`: ataques con su categoría física o especial, potenciadores a nivel 1 y con todas las mejoras, y pa/sa, df/sd de cada Pokémon, y el commit |
| `build/gamestats.py` | Carga `data/game_stats.json`, `data/move_icons.json` y `data/type_matrix.json`. Da el orden de potenciadores, la categoría de cada ataque y el lado fuerte de cada Pokémon (`side_of`) |
| `build/toolpages.py` | Rutas de las herramientas en cada idioma (`buscador-tipos/`, `planificador-build/`), sus enlaces y los datos del navegador (`#i18n`) |
| `build/finder.py`, `build/planner.py` | Páginas de Buscador por tipos y Planificador de build. La lógica está en `src/tools.js` (sin dependencias, con exports para pruebas) |
| `build/dupcheck.py` | Similitud (Jaccard sobre trozos de 5 palabras del texto visible) entre las fichas de un idioma |
| `build/indexnow.py` | Avisa a IndexNow de las URL de `sitemap.xml`. Se ejecuta a mano después de cada deploy |
| `build/check_site.py` | Comprobaciones de aceptación sobre un sitio servido |
| `console/coleccion.js`, `coleccion.en.js` | Comando que el jugador pega en la consola del juego. Exporta cada shiny con su origen y fecha en `shinyInfo` (`{dex: [origen, día]}`; origen 0 salvaje, 1 gacha, 2 desconocido). El JSON antiguo sin `shinyInfo` sigue valiendo, con origen desconocido |
| `build/test_tools.js`, `build/test_tools.py` | Pruebas de la lógica de las herramientas (la build recomendada es la mejor publicada, codec de la URL, avisos de potenciadores). `python3 -m unittest build/test_tools.py` las ejecuta |
| `build/test_share.js`, `build/test_collection.js` | Pruebas del codec del enlace (v1 y v2) y del lector del comando. `python3 -m unittest build/test_share.py build/test_collection.py` las ejecuta |

## Uso

```sh
export SPRITE_BASE=http://127.0.0.1:8765/_sprites/    # solo en local: sprites desde sprites/ en vez de jsDelivr
python3 build/catalog.py && python3 build/render.py   # genera site/
python3 build/serve.py                                # ver en local, http://127.0.0.1:8765/
python3 build/check_site.py http://127.0.0.1:8765/    # enlaces, atribución, datos de las 966 fichas, presupuesto de site/
python3 build/check_site.py http://127.0.0.1:8765/ --external   # además, enlaces externos (red)
```

`check_site.py` dibuja una muestra de fichas en un navegador si tienes Playwright (`pip install playwright`); con `--all-species` dibuja las 966 de cada idioma. También recorre las 20 páginas de consulta a 390 px y comprueba que su lista visible sea la del JSON-LD, en el mismo orden.

`site/` y `build/out/` son salida generada y no se versionan. Para publicar, genera el sitio **sin** `SPRITE_BASE` y ejecuta `npx wrangler pages deploy site --project-name survivortiers --branch main` (Cloudflare Pages, sirve `survivortiers.pages.dev`). `npx wrangler deploy` sube un Worker sin rutas y no publica nada. `vercel.json` queda por si se despliega allí.

### Fichas y sprites

- Cada Pokémon tiene una página HTML en `/pokemon/150-mewtwo/` y `/en/pokemon/150-mewtwo/` (número de Pokédex y el nombre inglés en ASCII). Es estática y completa sin JavaScript: tier, puesto, por qué, tiempo que aguanta, sus dos builds, stats del juego, cómo conseguirlo y las preguntas. `/pokemon/?id=150` sigue funcionando: esa plantilla redirige a la URL estática. Los enlaces viejos `/pokemon/25.html` caen en `404.html` y `app.js` los manda a `?id=25`, que sigue el mismo camino.
- El script en línea del tema (`build/theme.py`) va permitido por huella sha256 en `script-src` de `src/_headers` y `vercel.json`. Si cambias ese script, `render.py` se niega a generar el sitio hasta que pongas la huella que imprime (`python3 -c "import sys; sys.path.insert(0,'build'); import theme; print(theme.csp_hash())"`).
- Los sprites salen de `https://cdn.jsdelivr.net/gh/felipebasurto/survivortiers@main/sprites/<n>.png`. Si cambias el repositorio, el usuario o la rama, ajusta `SPRITE_CDN` en `build/legal.py` y el `img-src` de `src/_headers` y `vercel.json` (`check_site.py` comprueba que coincidan). jsDelivr guarda `@main` unas horas: un sprite nuevo tarda en verse.

## Para agentes de IA

El sitio es estático y no tiene API: los datos son JSON y CSV en `/data/`, sin clave de acceso. La documentación para agentes sale del build:

- `/llms.txt`: índice del sitio y de los datos, con enlaces absolutos.
- `/llms-full.txt`: qué significa cada campo, las unidades, el método completo y ejemplos (`curl`, `jq`).
- `/data/ranking.csv` es `data/ranking_fase3.csv` sin la línea de comentario, y `/data/meta.json` tiene los tiers, las cifras del método y los pesos del porqué.
- Las fichas son HTML estático (`/pokemon/150-mewtwo/`, `/en/pokemon/150-mewtwo/`). Para tablas siguen siendo más útiles los JSON.

`build/check_site.py` comprueba que estos archivos existan, que los enlaces de `llms.txt` respondan, que el sitemap tenga una entrada por página y que cada página enlace los archivos. La URL base de los enlaces absolutos está en `build/legal.py` (`SITE_URL`, o la variable de entorno `SITE_URL`).

## Actualizar el ranking

1. Si cambia el juego: sube `GAME_COMMIT` en `build/legal.py` y `GAME_REF` en `build/game_moves.py`, y regenera `data/pokedex_export.json` (`build/import_game_combat.py`), `data/game_stats.json` (`node build/export_game_stats.js /ruta/al/juego`), `data/move_pool.json`, `data/move_mechanics.json` y `data/move_icons.json`.
2. `python3 build/attack_tiers.py --sim` (fase 1, ~2 min), `python3 build/bond_tiers.py --sim` (fase 2, ~30 min) y `python3 build/species_builds.py --sim` (fase 3, ~2 h; después `--variants`, ~25 min). Cada fase lee la anterior.
3. `python3 build/why.py` rehace el porqué de cada Pokémon (necesita numpy).
4. `python3 build/catalog.py && python3 build/render.py && python3 build/check_site.py …`. Las cuatro órdenes con `--check` y los tests corren también en GitHub Actions (`.github/workflows/tests.yml`).

Todas las partidas se puntúan igual (`run_score` en `simulator/sim-rs/src/stats.rs`): tiempo que aguanta × √(dps/(dps+80) × kpm/(kpm+40)); sin daño, 0. El bot no lleva objeto y coge las cartas de nivel por una prioridad fija, así que el sitio no ordena objetos ni cartas.

Los cortes de tier están en `data/tiers.json`; no los repitas en otro sitio.

## Páginas de consulta

`build/landing.py` genera, en cada idioma, 20 páginas de respuesta corta:

| Página (ES / EN) | Lista |
| --- | --- |
| `/mejores-pokemon/` · `/en/best-pokemon/` | los 30 primeros del ranking (tier S) |
| `/mejores-legendarios/` · `/en/best-legendaries/` | todos los legendarios, por puesto |
| `/mejores-tipo/<tipo>/` · `/en/best-type/<type>/` | los 20 mejores de cada uno de los 18 tipos |

Cada página responde en sus dos primeras líneas (el título de la lista y una frase con los primeros nombres) y luego enseña la lista. El JSON-LD `CollectionPage` con `ItemList` repite exactamente esa lista, en el mismo orden; `check_site.py` lo comprueba. Las antiguas `/mejores-iniciales/` y `/mejores-pasivas/` redirigen (301, `src/_redirects`) a `/mejores-pokemon/` y `/pasivas`. Todas están en `sitemap.xml`, enlazadas desde la portada y desde cada ficha, y con `hreflang` es/en y `x-default`. No hay texto escrito a mano por Pokémon: si cambian los datos, cambian las listas.

## Frescura

Cada página muestra en el pie «Actualizado al parche del <fecha> (<sha>)» (en inglés, «Updated to the <date> patch (<sha>)»). El commit y la fecha salen de `UPDATED_COMMIT` y `UPDATED_DATE` en `build/legal.py`; es el único sitio donde se compone la línea (`freshness_text`). La portada añade la fecha de reconstrucción (`generatedAt` en `meta.json`), que también es el `dateModified` del JSON-LD y el `lastmod` del sitemap.

## SEO

`build/seo.py` genera lo que ve un rastreador sin JavaScript en la portada: el párrafo con los cinco primeros, la tabla de los 30 primeros con enlaces a las fichas y el JSON-LD (WebSite + ItemList). Cada ficha lleva título y descripción desde los datos, canonical, hreflang es/en/x-default y Open Graph/Twitter. `build/agents.py` escribe `robots.txt`, `sitemap.xml` y `llms.txt`. `python3 build/check_site.py` comprueba todo esto (ver `seo_check` y `sitemap_check`).

## Similitud entre fichas

```sh
python3 build/dupcheck.py --lang es   # o --lang en
```

Compara las fichas por el texto visible: trozos de 5 palabras, Jaccard entre pares, y aparte los trozos que están en más de la mitad de las fichas (la plantilla). Sirve para medir si una ficha se parece demasiado a otra.

## IndexNow

`src/<clave>.txt` es la clave de IndexNow (32 caracteres hexadecimales dentro del archivo). `pack.py` la copia a la raíz del sitio. **Ejecuta `build/indexnow.py` a mano después de cada deploy**, cuando la clave ya responda en `https://survivortiers.pages.dev/<clave>.txt`:

```sh
python3 build/indexnow.py --dry-run   # cuántas URL y en cuántos lotes, sin red
python3 build/indexnow.py             # envía las URL de sitemap.xml a api.indexnow.org
```

El script no corre en el build ni en CI. Solo envía URL del host de `SITE_URL`, en lotes de 10.000 como máximo.

## Licencias

- Código de este sitio: ver el repositorio. Código del juego: [MIT hasta el commit b297089; desde el 14 oct 2026 el código nuevo es PolyForm Noncommercial 1.0.0](https://github.com/JPTER78/pokesurvivor/blob/main/LICENSE). Código adaptado del juego (colores y glifos de tipo): MIT, © 2026 JPTER78 (aviso en `data/GAME_LICENSE.txt` y en la página Acerca).
- Sprites: SpriteCollab, CC BY-NC 4.0 (uso no comercial). Por eso el sitio no puede llevar anuncios, donaciones ni ninguna monetización.
- Letras: Pixelify Sans (títulos y tiers) y Zen Kaku Gothic New (texto y números), SIL OFL 1.1. Zen Kaku Gothic New va recortada a latino en `src/fonts/ZenKakuGothicNew-400.woff2`, `ZenKakuGothicNew-500.woff2` y `ZenKakuGothicNew-700.woff2`; las licencias están en `src/fonts/`.
- Pokémon y sus nombres son marcas de Nintendo, Creatures Inc., GAME FREAK y The Pokémon Company; el sitio es de fans y no está afiliado.
- El texto legal lo ha redactado el autor del sitio, no un abogado.
