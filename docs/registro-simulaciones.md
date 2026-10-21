# Registro de simulaciones

Registro de todas las corridas del simulador (`pokesim`) y de `build/regen.py --sim` que tienen salida en el repositorio o que se han ejecutado en el trabajo de estos commits. Horas en UTC. Base de este registro: `origin/main` en `bdd490f`.

Fuentes: historial de git de `simulator/results/` (commit que publica cada archivo), mensajes de commit, logs `/tmp/work/build_sim.log` y `/tmp/work/build_refine.log`, y las ejecuciones de validación de la sesión del 2026-10-20 (no publicadas).

## Regla antes de relanzar cualquier etapa

1. Buscar la etapa en la tabla de [salidas vigentes](#salidas-vigentes) y en el [registro cronológico](#registro-cronológico). Si la salida existe con las mismas semillas, `seed0`, flags y commits, no se vuelve a ejecutar.
2. Relanzar solo con un cambio concreto que lo justifique: un commit del juego (`data/game_stats.json`, tabla de movimientos, `simulator/vendor`) o un cambio en el motor (`simulator/sim-rs/src`) que afecte a esa etapa. Citar el commit en la entrada nueva.
3. `regen.py` salta una etapa cuya salida ya existe. `--from ETAPA` la fuerza y además fuerza todas las posteriores. No usar `--from` sin listar antes las etapas afectadas.
4. `--only` y `--explicit` no producen datos equivalentes a la ruta del generador (ver [problemas abiertos](#problemas-abiertos)). Solo para validaciones pequeñas, nunca para publicar hasta resolverlo.
5. Toda corrida nueva que cambie `simulator/results/` se añade a este archivo en el mismo commit.

## Salidas vigentes

Filas y semillas según `build/regen.py` en `bdd490f`. El CSV de `group_screen`, `group_search`, `builds/screen_new.csv` y `builds/refine_new.csv` no incluye columna de semillas; se indica la configuración de la etapa.

| Archivo (`simulator/results/fixed_group/`) | Etapa | Semillas (seed0) | Filas | Último commit que lo cambia | Fecha (UTC) |
| --- | --- | --- | --- | --- | --- |
| `solo_screen.csv` | solo screen | 16 (0) | 13.910 | `7a499a4` | 2026-10-19 17:14 |
| `solo_refine.csv`, `solo_refine_only.txt` | solo refine | 128 (1000) | 2.898 | `3b6585e` | 2026-10-20 07:55 |
| `solo_contend.csv` | solo contend | 512 (3000) | 240 | `3b6585e` | 2026-10-20 07:55 |
| `solo_sweep.csv` | barrido solo fusionado | según etapas | 2.778 | `3b6585e` | 2026-10-20 07:55 |
| `g2p2/starter_sweep.csv` | start sweep | 16 (0) | 13.910 | `3b6585e` | 2026-10-20 07:55 |
| `g2p2/rank_200.csv`, `stage2/rank_b.csv`, `stage2/rank_c.csv` | start rank (3 bloques) | 16 cada uno (0, 100, 200) | 966 cada uno | `3b6585e` | 2026-10-20 07:55 |
| `group_screen.csv` | group screen | 16 (0) | 305.468 | `3b6585e` (primera versión con 24.320 filas en `8ce8d1d`) | 2026-10-20 07:55 |
| `group_search.csv` | group refine | 96 (1000) | 5.796 | `3b6585e` | 2026-10-20 07:55 |
| `builds/screen_new.csv` | build screen (explícito) | 16 (0) | 161.927 | `094a726` | 2026-10-20 13:08 |
| `builds/refine_new.csv` | build refine (explícito) | 96 (1000) | 4.336 | `094a726` | 2026-10-20 13:08 |
| `pasivas_rank_g2p2.csv` | pasivas | según commit | 4.050 | `9615695` | 2026-10-20 11:19 |
| `passives_coins_g2p2.csv` | pasivas (monedas) | según commit | 7.728 | `9615695` | 2026-10-20 11:19 |
| `counterfactuals_g2p2.csv` | contrafactuales | según commit | 7.308 | `afbb725` (primera versión `dd11ca8`) | 2026-10-19 01:53 |
| `counterfactuals_solo.csv` | contrafactuales solo | según commit | 4.303 | `df4762a` (primera versión `f8b5393`) | 2026-10-19 10:17 |
| `halving/sample_full16.csv` | muestra de halving | 16 | 3.076 | `8ce8d1d` | 2026-10-19 21:22 |
| `nasty_plot.csv`, `nasty_plot_from_t0.csv` | Nasty Plot | según commit | — | `df4762a` | 2026-10-19 10:17 |

Partidas por etapa en los archivos vigentes (filas × semillas, aproximado): group screen unas 4,9 millones, build screen unas 2,6 millones, group refine 0,56 millones, build refine 0,42 millones, solo screen y start sweep 0,22 millones cada uno, solo refine 0,37 millones, solo contend 0,12 millones, start rank 0,05 millones. Son las versiones vigentes; las versiones anteriores no están contadas.

## Registro cronológico

Cada entrada indica el commit que la registra; la fecha es la del commit salvo que se indique la de la corrida.

| # | Fecha (UTC) | Commit | Qué se simuló | Motivo y cambio que lo justifica | Estado |
| --- | --- | --- | --- | --- | --- |
| 1 | 2026-10-16 11:00–16:00 | `3c09174`, `22a7747` | Calibración fija inicial: `rank_200`, solo sweep, items, empoleon, fill | Primera calibración del motor | Justificada. Semillas no registradas en el commit. |
| 2 | 2026-10-16 19:10 | `3bd095b` | Ranking 2+2 con sinergias (`g2p2_swap`), `items_g2p2` | Modelo de sinergias de juego | Justificada |
| 3 | 2026-10-17 12:51–13:06 | `df5fec5`, `d588f22` | Pasivas (`passives_g2p2`, `passives_first`, `passives_kinds`) | Página de pasivas | Justificada |
| 4 | 2026-10-17 14:26 | `dd11ca8` | Contrafactuales: 7.498 corridas según el mensaje del commit | Nuevos overrides por tarea (`94b67e2`) | Justificada. Ver nota de conteo abajo. |
| 5 | 2026-10-18 (sin hora) | `df34b2b` | Escaneo Hex con 200 semillas | Revisión del grupo Hex | Justificada |
| 6 | 2026-10-18 12:40 | `999c4ac` | `synergy_baselines`, `synergy_changes`, `synergy_groups` | Peso de Hex con el movimiento que lo prepara | Justificada |
| 7 | 2026-10-18 12:42 | `cc4090c` | Pasivas: `pasivas_rank_g2p2`, `pasivas_zidra*`, `pasivas_kinds` | Ranking de pasivas por recompensa en monedas | Justificada |
| 8 | 2026-10-18 14:30 | `de5f36d` | Primer `group_search.csv` | Puntuar grupos fijos contra los mejores pares | Justificada |
| 9 | 2026-10-18 17:26 | `f8b5393` | `solo_rank_best`, `counterfactuals_solo`, `passives_coins_g2p2` | Barrido del mejor movimiento | Justificada |
| 10 | 2026-10-19 10:17 | `df4762a` | `nasty_plot*.csv` | Cambio de juego e868b5e (publicado) | Justificada |
| 11 | 2026-10-19 14:27 | `c932987` | `stage2/rank_b`, `stage2/rank_c` | Bot de órbita y puntuación con daño | Justificada |
| 12 | 2026-10-19 17:14 | `7a499a4` | Solo screen (16), refine (128, seed0 1000), contend (512, seed0 3000), barrido fusionado, con el juego en `5a23d49` | Primera versión tras el cambio de juego `5a23d49`. Un intento de group screen en `5a23d49` se abortó a unas 24.000 de 24.320 combinaciones sin salida (según `REGEN_RESUME.md`). | Justificada en su momento. Sustituida por la entrada 14: de las 2.560 filas comunes de `solo_refine`, 2.559 cambiaron. |
| 13 | 2026-10-19 21:22 | `8ce8d1d` | Group screen (24.320 filas, 16 semillas), `group_refine_only`, halving 3.076 filas | Cambio de reglas: sin factor al cuerpo a cuerpo, Sustituto es un ataque, grupos mixtos con todos los potenciadores | Justificada. Fecha de la corrida no registrada; el archivo aparece por primera vez en este commit. |
| 14 | 2026-10-20 07:55 | `3b6585e` | Rerun de solo refine (128), contend (512), barrido solo, group search (96), start sweep (16), start rank (3×16), y group screen ampliado a 305.468 filas | Cambio de tabla de movimientos (commit del juego). Justifica las filas que cambian (ver abajo). **Repetición:** 11.498 grupos de `group_screen` ya existían en `8ce8d1d` con medianas idénticas (0 cambios). Son unas 184.000 partidas (11.498 × 16) repetidas sin cambio de resultado. | Justificada en lo que cambió; repetición de 184.000 partidas detectada. Cambios: `solo_refine` 2.559/2.560, `solo_contend` 199 comunes (todas cambiaron), `group_search` 103 comunes (todas cambiaron), `rank_200` 966/966, `starter_sweep` 9.236/9.236 comunes. |
| 15 | 2026-10-20 11:19 | `9615695` / `e65e92a` | `pasivas_rank_g2p2` (4.050) y `passives_coins_g2p2` (7.728) | Regeneración de cartas pasivas tras 38 movimientos nuevos (commit del juego) | Justificada. Los 150 valores de `pasivas_rank_g2p2` cambiaron. |
| 16 | 2026-10-20 09:26–09:29 | sin commit (sesión de validación) | Validación del modo `--explicit`: 400 grupos de `group_screen` (16 semillas, comparados con `group_screen`); 20 grupos en 9 combinaciones de flags; 20 grupos por la ruta del generador con `--only`; 12 iniciales de `solo_refine` con 128 semillas y `--only` | Verificar `build_screen`. Motivo válido, pero se repitieron partidas que ya existían y no se guardó salida. | Verificación. Resultados: 4 de 400 idénticos (media de diferencia de puntuación −0,10, sd 6,50); 0 de 20 en cada combinación; 0 de 20 por la ruta del generador con `--only`; 0 de 9 y 0 de 12 en solo. Ningún dato publicado. Ver problemas 1 y 2. |
| 17 | 2026-10-20 09:32–~12:20 | `094a726` (publicado 13:08) | `build_screen`: 161.927 grupos constrained (ruta explícita) × 16 semillas, en 41 trozos (`screen_chunks/`, gitignored) | Grupos melee y ranged que no están en `group_screen` (`builds.missing_screen`) | Justificada. Solape con `group_screen`: 0. Sujeta al problema 1. |
| 18 | 2026-10-20 12:28–12:54 | `094a726` (publicado 13:08) | `build_refine`: 4.336 grupos × 96 semillas (seed0 1000), 1.556,7 s | Dos mejores grupos por forma y build | Justificada. Solape con `group_search`: 0. Sujeta al problema 1. El primer intento falló con `NameError` antes de simular, sin coste. |
| — | 2026-10-20 10:11 | `b6fef7a` | Solo código: modo `--explicit` y `parse_group` en `main.rs` | Añadir la ruta explícita | No ejecuta simulaciones. Cambia el motor; la ruta por defecto no cambia. |
| 19 | 2026-10-21 09:27–09:31 | sin commit (HEAD `eee94ff`, motor `bdd490f`) | Fase 1 del pipeline simplificado (`build/attack_tiers.py --sim`): 97 ataques solos × 6 referencias de su clase, en `tasks` con `--seconds 900 --status --terrain --xkinds`. Primero a 32 semillas (18.624 partidas, 27 s, descartada) y luego a 128 (74.496 partidas, 111 s) → `results/fase1/attacks_raw.csv`, `data/attack_tiers.csv` | Tier list de ataques que sustituye al barrido en solitario (salida sobrescrita por la 22). Con 32 semillas 31 de 97 ataques cambiaban de tier entre mitades; con 128, 16 (Spearman 0,97) | Justificada. Antes se comprobó que `tasks` da lo mismo que `sweep --no-synergy --only` (3 filas, 16 semillas) |
| 20 | 2026-10-21 (mañana) | sin commit (motor `bdd490f` + flag `--bonded`) | Fase 2 (`build/bond_tiers.py --sim`): 1.394 grupos (17 ataques físicos y 13 especiales de la fase 1, parejas con potenciador y Fortaleza o Agilidad, tríos con potenciador) × 6 referencias × 16 semillas = 133.824 partidas. Primero con vínculos de fisura (218 s, descartada), luego `--bonded` (436 s). Afinado: 210 grupos × 6 × 64 semillas (seed0 1000) = 80.640 partidas (285 s) → `results/fase2/`, `data/bond_tiers.csv` | Tier list de vínculos. Con fisuras el bot muere hacia los 140 s y el tercer ataque no se vincula nunca (5 grupos Bucle Arena + Magnitud + X con la misma partida), así que se añadió `--bonded` a `main.rs`/`engine.rs`: grupo entero desde t=0, con jefes; la ruta por defecto da lo mismo byte a byte (4 grupos comparados) y `cargo test` pasa | Sustituida por la 21 (salidas borradas). Estabilidad entre mitades, primera ronda: Spearman 0,96 melee, 0,90 distancia física, 0,75 especial |
| 21 | 2026-10-21 10:19–11:16 | sin commit (motor `bdd490f` + `--bonded`) | Fase 2 sin reglas de clase, potenciador ni forma (`build/bond_tiers.py --sim`): 24 ataques (8 mejores de cada categoría, cuerpo a cuerpo hasta 5, embestidas, Infortunio), 10.799 grupos (`builds.variants`: 2+atk+def, 3+atk, 3+def; Danza Espada, Danza Dragón o Maquinación si suben algún ataque), jugados por las 6 referencias de cada clase. Ronda 1: todos a 2 semillas (259.176 partidas, 2.447 s); ronda 2: 8 % mejor de cada clase y build más 100 de control al azar por clase, 16 semillas, seed0 100 (185.088, 603 s); ronda 3: 15 % mejor de la 2, 64 semillas, seed0 1000 (112.128, 384 s) → `results/fase2/r{1,2,3}_raw.csv`, `data/bond_tiers.csv` | Quitar las reglas 1 a 3 (petición de Felipe). La ronda 1 fue a 106 partidas/s; una muestra de 20.000 grupos de la misma ronda va a 328/s y escala lineal, así que la lentitud fue de la máquina (CPU media 620 %), no del motor | Sustituida por la 22 (salidas sobrescritas). 0 de los 100 grupos de control por clase llegaron a la ronda 3. Estabilidad ronda 3: Spearman 0,70–0,87 |
| 22 | 2026-10-21 (tarde) | sin commit (motor `bdd490f` + `--bonded`) | Fases 1 y 2 otra vez con las referencias elegidas también por el otro ataque (`attack_tiers.pick_refs`: pa y sa cerca de la mediana de la clase). Las físicas no cambian; las especiales pasan a Prinplup, Dedenne, Porygon, Charmeleon, Gloom y Swoobat (pa/sa medio 0,903, mediana de la clase 0,921; antes 0,94). Fase 1: 74.496 partidas, 107 s. Fase 2, mismas rondas que la 21: 259.176 (983 s), 185.088 (688 s) y 111.360 partidas (647 s) | Las referencias especiales de la 19 y la 21 tenían casi el mismo ataque físico que especial, y eso favorecía a los grupos físicos en los especiales | Justificada. Control del corte: 1 de 100 físicos llegó a la ronda 3 (puesto 67 de 71 en distancia), 0 de 100 especiales. Los especiales siguen rindiendo más con grupos físicos (1,65 frente a 1,35 del mejor especial puro) |
| 23 | 2026-10-21 12:35–14:55 | sin commit (motor `bdd490f` + `--bonded`) | Fase 3 (`build/species_builds.py --sim`): la build óptima melee y a distancia de cada una de las 966 especies, jugada por la propia especie. Lista corta por un modelo aditivo de la fase 2 (inicial, acompañantes, forma y potenciador), por especie, build y mezcla de categorías. Primera corrida con 10 por mezcla: ronda A 47.862 grupos × 4 semillas (191.448 partidas, 1.358 s), B 4 mejores por especie y build × 32 semillas, seed0 100 (247.296, 1.038 s), C el mejor × 128 semillas, seed0 1000 (247.296, 1.119 s). Segunda con 30 por mezcla, reutilizando las filas ya jugadas con la misma huella de motor, datos y semillas (`rX_raw.fingerprint`): A 140.905 grupos, 93.043 nuevos (372.172 partidas, 2.695 s); B 7.728, 4.020 nuevos (128.640, 436 s); C 1.932, 1.108 nuevos (141.824, 477 s) → `results/fase3/`, `data/species_builds.csv`, `data/ranking_fase3.csv` | Ranking y builds del pipeline simplificado. Con 10 por mezcla el ganador salía en cualquier puesto de la lista casi por igual; una muestra de 50 especies con 30 (semillas nuevas de la ronda C) mejoró 9 de ellas más de un 5 %, así que se pasó a 30. La ronda A de la segunda fue a 138 partidas/s por otros programas del usuario en la máquina (carga 55–80) | Justificada. Con 30: 1.108 de 1.932 builds cambian de grupo (mediana +3,2 %, 477 mejoran más de un 5 %, 191 empeoran más de un 5 % porque el ganador anterior cae en una ronda con más competidores). Estabilidad ronda C: Spearman 0,955 entre mitades, top 30 comparten 24; frente a la de 10, Spearman 0,962 y 28 de 30. Frente a `ranking_definitive.csv`: Spearman 0,83, top 30 comparten 15, top 100 58; suben los de tipo acero (Puño Meteoro), bajan los siniestros. Puño Meteoro comprobado contra `combat.js` (`meteors`, `blast`): mismo objetivo, retardo y área |

Nota de conteo: el mensaje de `dd11ca8` dice 7.498 corridas. Los dos CSV de contrafactuales suman 11.611 filas. No está reconciliado.

## Problemas abiertos

1. **La ruta explícita no es equivalente a la del generador.** La comparación de `group_search` (96 semillas, seed0 1000) con la misma clave en modo `--explicit` no coincidió en las 9 filas visibles de la salida, con diferencias de hasta 6 puntos. Con 16 semillas coincidieron 4 de 400. El modo explícito es determinista: dos ejecuciones dan el mismo resultado. La diferencia está en cómo se construye el trabajo: `parse_group` (kit, ataques, arranque) frente al generador. Como `builds.finals()` elige entre `group_search` (generador) y `refine_new` (explícito), los builds publicados comparan dos rutas. **Hay que decidir**: (a) entender la diferencia y recalcular todos los candidatos de build con una sola ruta, o (b) validar la equivalencia antes de usar esos datos. Cualquiera de las dos exige simulación nueva, así que no se lanza sin decisión.
2. **El binario actual no reproduce los CSV publicados en modo `--only`.** La ejecución completa de `3b6585e` reprodujo 11.498 filas idénticas de `8ce8d1d`; las 20 claves de prueba ejecutadas con `--only` no coinciden con `group_screen.csv`. Hipótesis sin comprobar: el filtro `--only` cambia algo del trabajo generado. No investigado. Mientras no se resuelva, no usar `--only` para comparar con datos publicados.
3. **`REGEN_RESUME.md` está obsoleto.** Dice que `group_screen` no tiene salida y que faltan etapas. Ambas cosas son falsas hoy (ver el registro). Se ha añadido una nota al inicio que remite a este archivo.
4. **Valores de `solo_refine` anteriores a `3b6585e`** (commit `7a499a4`) no se deben usar: todas las filas cambiaron o no son comparables.

## Procedimiento para una corrida nueva

1. Revisar las tablas de este archivo: ¿existe la salida con esas semillas y flags?
2. Identificar el commit que justifica la corrida (juego o motor) y anotarlo.
3. Ejecutar solo la etapa afectada, sin `--from` si no hace falta.
4. Añadir una fila al registro cronológico y actualizar la tabla de salidas vigentes en el mismo commit que publica los CSV.
5. Comprobar solape con las salidas existentes (`comm` sobre claves `dex|group` o `dex|start`) antes de dar por buena la corrida.
