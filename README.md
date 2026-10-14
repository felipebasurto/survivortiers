# SurvivorTiers

Tier list de fans (no oficial) de [PokéSurvivor](https://pokesurvivor.com). Sitio estático en español (raíz) e inglés (`/en/`). Un generador en Python (solo biblioteca estándar, 3.9+) emite HTML y JSON, y el navegador usa JS sin dependencias.

Web: https://survivortiers.felipe99basurto.workers.dev

## Estructura

| Ruta | Qué hay |
| --- | --- |
| `data/` | Entradas: ranking definitivo (`ranking_definitive.csv`), `pokedex_export.json`, nombres y textos de ataques en inglés (`species_names_en.csv`, `lang_en_moves.json`), `CREDITS.md` y licencia del juego (copiados del commit `a9b21f0`), y `move_tierlist_v4.csv` |
| `build/catalog.py` | Valida y genera `site/data/*.json`. **Falla** si falta artista o licencia de algún sprite, si los conteos por tier no son 30/90/200/300/346 o si los pools de gacha no suman 966 |
| `build/render.py` | Genera en `site/` y `site/en/` las 6 páginas y las 966 fichas de cada idioma |
| `build/i18n.py` | Todos los textos en español e inglés, validados al importar |
| `build/charts.py` | Gráficos HTML, CSS y SVG |
| `build/move_tierlist_v4.py` | Regenera `data/move_tierlist_v4.csv` (necesita el análisis y una copia del juego) |
| `build/check_site.py` | Comprobaciones de aceptación sobre un sitio servido |
| `console/coleccion.js`, `coleccion.en.js` | Comando que el jugador pega en la consola del juego |
| `site/` | Estáticos a mano (`style.css`, `app.js`, `sprites/`) y salida generada |

## Uso

```sh
python3 build/catalog.py && python3 build/render.py   # genera site/
python3 -m http.server 8765 --directory site          # ver en local
python3 build/check_site.py http://127.0.0.1:8765/    # 966 fichas, atribución, enlaces, conteos
python3 build/check_site.py http://127.0.0.1:8765/ --external   # además, enlaces externos (red)
```

`site/*.html`, `site/pokemon/`, `site/data/` y `site/en/` son salida generada y no se versionan. Para publicar, genera el sitio y ejecuta `npx wrangler deploy` (Cloudflare Workers, ver `wrangler.jsonc`). `vercel.json` queda por si se despliega allí.

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
