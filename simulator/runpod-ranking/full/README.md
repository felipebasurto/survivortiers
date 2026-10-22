# Ranking full con búsqueda de naturalezas (bounded-ranking-v2)

Run: Runpod cpu3c 32 vCPU, rama `feat/ranking-nature-search` (aa98123), juego ce5785313b0205af8b9477423f64b0a7b7039dcd,
engine fingerprint eb7b50a4…, 441.486 partidas (416.370 candidatas + 25.116 control), 1.717 s. 3.010 builds
`confirmed`, 966 especies. Ver `.cursor/skills/runpod-sim-ranking/reference.md`.

`sim-results.json.gz` (sim-results.json comprimido; sha256 del JSON en SHA256SUMS) es la entrada de `build/bounded_export.py` (→ `data/bounded_ranking.json`, lo que lee la web).
`plan.json` (102 MB), `attacks.json`, `lab*.json` y `results.json` (417 MB, sha256 en SHA256SUMS) no
está en git: vive en la copia del repo del Mac de Felipe (`~/Downloads/survivortiers/simulator/runpod-ranking/full/`)
y puede subirse como asset de una GitHub Release. La caché de partidas tampoco se sube.

Publicado el 22-10-2026 por decisión de Felipe, antes de cerrar Gate 2: es diagnóstico, no un óptimo global.

`candidates.json.gz` (4,5 MB) es un extracto de `results.json`: por cada build simulada (etapas A, B y ganadoras
confirmadas) su configuración y, por partida, [supervivencia s, bajas, daño]. Lo lee `build/bounded_tables.py`, que
aplica las reglas de publicación (4 movimientos; sin Placaje, Ataque Rápido ni Golpe Cuerpo salvo tipo Normal) y
reescribe las builds de `data/bounded_ranking.json`. Orden: `bounded_export.py` y después `bounded_tables.py`.
