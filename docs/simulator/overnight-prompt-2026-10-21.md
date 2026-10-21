# Prompt: trabajo nocturno local del simulador

Eres un agente que trabaja solo, de noche, en el repo git `survivortiers`. Trabaja en una rama nueva `sim/overnight-2026-10-21`. Nunca cambies `main`.

Lee antes: `docs/simulator/status-2026-10-21.md`, `docs/simulator/readiness-2026-10-21.md`, `docs/simulator/web-contract.md`, `docs/simulator/production-policy.md`.

## Restricciones

- Todo en local. Nada de Runpod, pods ni gasto. Máquina local: 10 núcleos.
- Nada de deploy. No ejecutes `wrangler pages deploy`, `build/indexnow.py` ni nada que toque Cloudflare.
- No publiques rankings. No cambies `site/`. No regeneres `data/` público sin marcarlo como provisional. `rankingReady` queda en `false`.
- No hagas `git push`. Deja la rama lista para revisión.
- No imprimas ni comitees secretos de `~/.runpod/`.
- Python: usa `/Users/felipe/.local/bin/python3.13` (CI usa 3.12; el Python del sistema, 3.9, falla). Tiene Pillow y numpy.
- Rust: el binario de equivalencias requiere `cargo build --locked --release --manifest-path simulator/sim-rs/Cargo.toml --bin pokesim`. `cargo test` no lo actualiza.
- El engine fingerprint lo calcula `production.rs`, `data.rs`, `engine.rs` y otros ficheros listados en `simulator/sim-rs/src/research.rs`. Cualquier cambio en ellos cambia el fingerprint. Tras cada cambio: `cd simulator && ./sim-rs/target/release/pokesim fingerprint`, actualiza `engineFingerprint` en `simulator/runpod/production.json` y valida con `./sim-rs/target/release/pokesim production plan runpod/production.json /tmp/plan.json`.
- Pausa y pregunta solo ante: push, deploy, publicar datos, borrar datos, gasto. Lo demás procede y se reporta.

## Estado de partida

- `main` en `3fae073`, subido a origin. Sitio desplegado (Cloudflare Pages, 2026-10-21), sin simulador.
- Motor Rust en `simulator/sim-rs`: 79 tests unitarios y 2 de importador, verdes.
- Runner: `pokesim production plan|run|resume|benchmark`. Plan "all": 966 especies, 11 058 candidatos. Es un beam acotado: 8 a 16 configuraciones por especie frente a más de 1,36 M propuestas de movimientos.
- Un run anterior de 240 480 tareas dio 0 fallos. Sus resultados no están en el repo ni son accesibles para ti. Tratalos como histórico, con fingerprint anterior `6f53…`. No son un resultado validado.
- Partidas: media 125 s de supervivencia, máximo 780 s. No hay calibración contra el juego.
- Pipeline antiguo en Python (fases 1 a 3): `data/attack_tiers.csv` (97 ataques), `data/bond_tiers.csv`, `data/species_builds.csv` (1 932 filas, solo sin MT), `data/species_why.csv`. Se regeneran con `--sim` y se validan con `--check`. Su código de simulación (`pokesim synergy`) ya no existe.
- `data/attack_tiers.csv` cubre 54 de las 58 MT. Faltan Agilidad, Danza Dragón, Plan Nasty y Danza Espada, que son potenciadores y deben tratarse como tales.
- `simulator/data/game.json` tiene `tmPrices` (58 MT con precio). Ninguna parte de la selección los usa todavía.
- Juego fuente: `https://github.com/JPTER78/pokesurvivor`, commit `ce5785313b0205af8b9477423f64b0a7b7039dcd`. Los 123 usos de `Math.random` no son reproducibles. El bucle usa `requestAnimationFrame` con tiempo real. El juego no tiene bot de jugabilidad.
- Contrato web: `build/sim_results.py` (`validate_results`), `build/sim_export.py`, `build/sim_cards.py`. Ninguno está conectado a resultados Rust.

## Decisiones tomadas

1. Salida por especie: cuatro builds. Melee sin MT, melee con MT, a distancia sin MT y a distancia con MT. La build con MT muestra su coste total en monedas.
2. Política provisional: supervivencia primaria (media pareada frente al control). Exposición no inferior con margen 0. El coste de MT se reporta. Un tope opcional (`searchPolicy.tmBudget`) queda sin valor por defecto. Documenta todo como provisional hasta el gate 2.
3. Aggro × Coverage no entra en la búsqueda. Lo documentas como control de la web, a menos que encuentres una razón para no hacerlo, que anotarás.

## Trabajo, en orden

Cada paso termina con un criterio verificable. Si un paso falla, lo registras y sigues con el siguiente cuando sea independiente.

**W0. Línea base.** Ejecuta `cargo test --release` en `simulator/sim-rs` y los tests Python con 3.13. Criterio: todo verde. Anota el fingerprint actual.

**W1. Coste MT en el ranking.** En `data.rs`, carga `tmPrices` de `game.json` en `Data`. En `production.rs`, añade `tmCost` (suma de precios de `tms`) a cada candidato del roster; `candidate_value` pasa a devolver `Result`. Añade `tmCost` a la fila ganadora. Añade `searchPolicy.tmBudget` opcional, parseado en `parse_manifest_value`. Si existe, `analyze_winners` excluye candidatos de la rama `optimized_tm` con coste mayor. Criterio: tests nuevos para suma de precios, exclusión por tope y ausencia de cambio sin tope. Los tests existentes siguen verdes.

**W2. Política documentada.** Actualiza `docs/simulator/production-policy.md` con las decisiones de la sección anterior, marcadas como provisionales. Criterio: el documento dice qué se mide, qué decide y qué queda pendiente de gate 2.

**W3. Cuatro builds por especie.** Comprueba que el plan genera estratos `melee|ranged × optimized_no_tm|optimized_tm` para las 966 especies, con el rol base. Mide el recuento. Criterio: recuento y ejemplos de Bulbasaur (dex 1), Pikachu (25) y Psyduck (54) en un informe.

**W4. Recall del embudo, en local.** Para Psyduck (dex 54), Pikachu (25), Bulbasaur (1) y dos especies más pequeñas que elijas: enumera todos los grupos con el perfil por defecto (natura `hardy`, habilidad por defecto), simula con 4 semillas de cribado y compara el mejor exhaustivo con el mejor del beam. Mide primero el throughput local con 2 000 partidas. Psyduck son unas 88 000 partidas. Criterio: tabla por especie con el mejor exhaustivo, su posición en el beam y el coste en minutos. Si el beam nunca contiene al mejor, dilo.

**W5. Embudo por rondas, solo si W4 lo justifica.** Implementa en Rust la fase 1 (prior por ataque), la fase 2 y la fase 3 con successive halving (4, luego 32, luego 128 semillas) y perfiles solo para los 4 mejores grupos. Criterio: en las mismas especies de W4, el mejor del embudo queda dentro de un margen que defines y justificas frente al exhaustivo. Mide el número de partidas total.

**W6. Viabilidad del gate 2 (solo viabilidad).** Clona el juego en el commit indicado. Con Playwright para python3.13 (Chromium cacheado en `~/Library/Caches/ms-playwright`), sirve el juego en local. Sustituye `requestAnimationFrame` por un bucle manual de paso fijo y `Math.random` por un PRNG con semilla. Criterio: dos ejecuciones con la misma semilla producen el mismo hash de estado tras N fotogramas. No afirmes validación de mecánicas. Anota qué falta para una comparación real, sobre todo el bot equivalente.

**W7. Conexión web, solo validación.** Escribe un adaptador de resultados Rust al esquema versión 1 de `build/sim_results.py`. Ejecuta `validate_results` sobre un documento de prueba generado localmente. Criterio: se acepta o se lista exactamente qué falta. No publiques nada, no toques `site/`.

**W8. Informe final.** Escribe `docs/simulator/overnight-report-2026-10-22.md`. Por cada paso: hecho, no hecho o bloqueado. Evidencia: comando, número y ruta. Cada afirmación lleva su etiqueta: medido, inferido o estimado. Termina con una lista de decisiones que necesitas tomar.

## Formato de salida

Trabaja en commits pequeños, uno por paso verificado. Al final, deja un resumen de 10 líneas máximo en el informe. No añadas prosa de adorno.
