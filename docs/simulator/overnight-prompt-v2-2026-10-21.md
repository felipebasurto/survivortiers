# Prompt: embudo local del simulador (v2, 2026-10-21)

/pstack:poteto-mode

Trabajo nocturno y desatendido. El humano lo revisa por la mañana. Según poteto-mode, esto va al skill figure-it-out, con la disciplina del playbook Autonomous run. Los pasos P0 a P8 de abajo son tu fase B ya diseñada. No la rediseñes. Ejecútala con el bucle de la fase C y el registro de la fase D. Modo autónomo completo: "run until done".

Repo: /Users/felipe/Downloads/survivortiers, main en 3fae073, origin github.com/felipebasurto/survivortiers.
Crea un worktree desde main con la rama sim/funnel-local-2026-10-21 y trabaja solo ahí.
docs/simulator/overnight-prompt-*.md no tienen seguimiento en git. No los añadas. Nunca uses git add -A.

## Predicado de terminado

Se cumple cuando todo lo siguiente es verdad y está comprobado sobre el artefacto real:

1. cargo test --release y los tests de Python están en verde. También pasan los --check de attack_tiers, bond_tiers, species_builds y why.
2. pokesim production plan acepta simulator/runpod/production.json con el fingerprint del último commit.
3. Hay un fichero de builds con 4 ramas por especie: las 966, o un subconjunto documentado según P2.
4. Las especies de P1 cumplen el criterio de recall de P2, o el informe dice con cifras por qué no.
5. El PR está abierto y listo, sin fusionar, con el registro de decisiones commiteado.

No relajes el predicado para declarar victoria. Si un punto no se cumple, el informe dice NO VERIFICADO o INCONCLUSO, nunca "hecho".

## Restricciones

- Solo local. Máquina Apple M4 con 4 núcleos de rendimiento y 6 de eficiencia. Nada de Runpod ni gasto.
- Sin deploy, sin build/indexnow.py y sin cambios en data/*.csv. site/ no está en git. Puedes renderizarlo para los tests, pero no lo publiques.
- rankingReady queda en false en todo lo que generes.
- Push solo de tu rama. Nunca a main ni force-push.
- No leas ni imprimas ~/.runpod/* ni claves SSH.
- Salidas grandes en /Users/felipe/Downloads/sim-funnel-2026-10-21/, fuera del repo. Commitea solo resúmenes de menos de 1 MB.
- Pausa solo ante push a main, force-push, deploy, publicar datos, borrar datos o gasto. Todo lo demás procede y se registra.

Lectura previa: docs/simulator/status-2026-10-21.md, readiness-2026-10-21.md, production-policy.md y web-contract.md.

## Entorno

- Python: /Users/felipe/.local/bin/python3.13. No uses el 3.9 del sistema.
- Rust: cargo test --release --manifest-path simulator/sim-rs/Cargo.toml. El binario se recompila aparte con cargo build --release --locked --manifest-path simulator/sim-rs/Cargo.toml --bin pokesim. cargo test no lo actualiza.
- Fingerprint: lo definen los ficheros de research::fingerprint(), que incluyen game.json, terrain.rs, rng.rs y Cargo.lock. Tras cada cambio en ellos, recompila y ejecuta pokesim fingerprint. Después actualiza engineFingerprint en simulator/runpod/production.json y valida con pokesim production plan runpod/production.json /tmp/plan.json desde simulator/. Cada fichero de resultados guarda el fingerprint con el que se produjo.
- Límites del runner: production run para tras maxWallSeconds (máximo 900) por invocación. Reanuda con resume. benchmark y run solo admiten escenas de 15 s o menos, que no son partidas.
- Resultados antiguos de Runpod, solo lectura: ~/Downloads/runpod-results-2026-10-21/runpod-results.json.
- En zsh, no uses echo con "===".
- Tiradas largas: lánzalas en segundo plano y espera la notificación. Usa un latido de reserva cada 30 min.

## Reglas de poteto-mode para esta noche

- Registro de decisiones con el skill show-me-your-work en docs/simulator/overnight-2026-10-22/decisions.tsv. Commitéalo. Escribe una fila por decisión, pivote, reversión o paso verificado.
- Cada número sigue el principio explain-the-number. Lleva la etiqueta medido o inferido, el número de corridas, la dispersión y el factor que lo limita. Para throughput, aplica el skill benchmark-checklist.
- Un commit por unidad verificada (sequence-verifiable-units). Mensajes en formato Conventional Commits, por ejemplo feat(sim): add tmCost to production roster.
- Construye la palanca (build-the-lever). Cada medición y comparación es un script o un subcomando commiteado que el revisor puede volver a ejecutar, no un cálculo a mano.
- Antes de cambiar código que cruza funciones (P1, P2 y P3), nombra la forma de los datos y aplica el skill architect.
- Antes de cada commit, aplica no-comments y unslop. deslop no está instalado. Anótalo una vez en el registro y sigue.
- No bloquees al humano (never-block-on-the-human). Lo reversible lo decides tú y lo registras.
- No midas mientras otra cosa use CPU. P5 se puede delegar a un subagente en su propio worktree, pero solo mientras escribes código, nunca durante P0, P1 o las tiradas de P2.

## Decisiones ya tomadas (no las reabras sin datos)

- D1. Por especie salen 4 builds: melee y ranged, cada una con y sin MT. La rama con MT exige al menos una MT. Si no mejora a la sin MT, se reporta igual con su diferencia pareada e IC.
- D2. El objetivo primario es la supervivencia media pareada frente al control. La exposición se reporta y filtra según P4.
- D3. Aggro × Coverage queda fuera de la búsqueda y es un control de la web.
- D4. tmCost suma solo las MT que hay que enseñar. Un movimiento que ya está en el pool natural cuesta 0.
- D5. tmBudget es opcional y no tiene valor por defecto. Se aplica al generar el roster, para no gastar tareas, y se comprueba otra vez en analyze_winners.
- D6. Semillas. Cribado y ronda A: 1001–1004. Ronda B: 1101–1132. Ronda C: 1201–1328. Barrido de naturaleza y habilidad: 1001–1004. Verdad de P1 e intervalo final de P2: 3001–3032. Ninguna de estas semillas se usa a la vez para elegir y para el intervalo final.
- D7. Criterio de recall. Para cada especie de P1 y cada rama, compara el mejor del embudo con el mejor real usando las semillas 3001–3032. La cota superior del IC95 pareado de (real − embudo) debe ser como máximo el 5 % de la supervivencia media del mejor real.
- D8. Márgenes de exposición provisionales: 10 % relativo al valor del control en cada medida, y 0 s en supervivencia. Hasta el gate 2, el informe también da la tasa de no_safe_candidate con márgenes de 0 %, 5 % y 10 %.
- D9. PR listo (no borrador), sin fusionar.

## Pasos

Cada paso termina con una comprobación. Si algo lo bloquea, regístralo y pasa al siguiente paso independiente.

Presupuesto orientativo: unas 8 h. Si falta tiempo, la prioridad es P0, P3, P1, P4, P2, P6, P5, P7 y P8.

**P0. Línea base (30 min como máximo).**
- Tests Rust y Python en verde. Anota el fingerprint.
- Mide el throughput con un manifiesto mínimo de unas 200 tareas de partida completa (production plan + run). Hazlo con 4 y con 10 hilos, 5 corridas alternas de cada uno. Reporta la mediana y el rango en partidas/s y en segundos simulados por segundo, más la cuenta de fallos.
- Confirma que las tareas se ejecutaron y no salieron de la caché.
- Nombra el limitante (núcleos de rendimiento frente a eficiencia).
- El ~340/s es inferido de Runpod (540/s en 16 vCPU × 10/16). No lo uses.

**P3. Coste de MT.** Va antes que P1 y P2 porque cambia el fingerprint.
- Carga tmPrices en Data.
- Añade tmCost al roster y a la fila ganadora. candidate_value(data, c) devuelve Result.
- Aplica searchPolicy.tmBudget según D5.
- Tests de comportamiento con valores literales:
  - la suma de precios;
  - un movimiento natural no suma;
  - el tope excluye candidatos;
  - sin tope, el plan es idéntico (mismo planHash).

**P1. Recall del embudo actual (1,5 h de cómputo como máximo).**
- Crea un subcomando que evalúe todos los grupos de una especie con el perfil por defecto (hardy, habilidad slot-1) y las semillas 1001–1004. Compara por (estilo, rama) con rol base.
- El mejor real es el mejor de los 50 primeros del barrido tras reevaluarlos con 3001–3032.
- Especies:
  - Psyduck (54): 22 016 grupos, unas 88k partidas (inferido).
  - La especie con 1 000 a 2 000 grupos y menor dex.
  - Mewtwo (150): 156 594 grupos, unas 626k partidas (inferido). Hazla solo si P0 deja el tiempo por debajo de 40 min.
- Tabla por especie y rama con estas columnas:
  - posición del mejor real en el embudo actual, o "ausente" si no lo propuso;
  - diferencia en segundos con IC95;
  - partidas usadas.
  Cada cifra lleva la etiqueta medido o inferido.

**P2. Embudo de 4 ramas en Rust.**
- Porta attack_tiers.py (fase 1, 128 semillas) y el modelo aditivo de species_builds.py (TOP_A=30 por mezcla de categorías, TOP_B=4, rondas 4→32→128).
- Ese modelo se ajusta con datos de la fase 2 (bond_tiers.py) del motor antiguo. Regenera la fase 1 y la ronda 1 de la fase 2 con el motor actual. Saca de las referencias de entrenamiento las especies de P1, para que el recall se mida fuera de muestra.
- Las 4 MT de potenciador (Agilidad, Danza Dragón, Maquinación, Danza Espada) se tratan como potenciadores, no como ataques.
- Barre naturaleza y habilidad solo sobre los 4 mejores grupos. Aqua Ring no está soportado. Anótalo.
- Usa data/*.csv solo como referencia. No los sobrescribas.
- Antes de ejecutar, haz un registro de tareas en seco con el total de partidas y las horas (inferido con el throughput de P0).
- Si pasa de 5 h, ejecuta primero las especies de P1. Después sigue con las demás en un orden aleatorio fijo (semilla 20261021) hasta agotar las 5 h. Documenta dónde se cortó.
- Checkpoints reanudables. Una segunda ejecución reutiliza la caché y no repite partidas.
- Comprobaciones:
  - D7 se cumple en las especies de P1;
  - cero fallos;
  - el fichero tiene estas columnas: dex, estilo, rama, grupo, naturaleza, habilidad, MT, tmCost, supervivencia media, IC95, semillas y fingerprint.

**P4. Política.**
- Documenta D2, D5 y D8 en production-policy.md como provisionales hasta el gate 2.
- Incluye la tasa de no_safe_candidate con 0/5/10 % medida sobre la salida de P2.
- Dato medido (Runpod, fingerprint 6f53…): 4 903 de 11 058 estratos dieron no_safe_candidate con margen 0.
- Escribe DECISIÓN PENDIENTE solo en lo que requiera al humano.

**P5. Gate 2, solo viabilidad (2 h como máximo).**
- Usa /tmp/pokesurvivor-pinned en ce5785313b0205af8b9477423f64b0a7b7039dcd. Verifica que el checkout está limpio.
- Instala playwright para python3.13. Puedes descargar Chromium.
- Controla requestAnimationFrame, performance.now, Date.now, setTimeout, setInterval y Math.random con semilla.
- Comprobación: el mismo hash de estado tras 3 600 fotogramas en dos corridas con la misma semilla, y otro hash con otra semilla. Si no lo consigues, documenta por qué.
- Sin bot ni paridad.

**P6. Web.**
- Escribe un adaptador de la salida de P2 al schema_version 1 de build/sim_results.py.
- Ejecuta validate_results. Deja el documento en el directorio de salidas y la lista de errores en el informe.
- No publiques.

**P7. Documentación.**
- Actualiza status-2026-10-21.md. Marca el beam anterior como descartado (6 155 best_observed y 4 903 no_safe_candidate, medido).
- Escribe docs/simulator/overnight-2026-10-22/report.md. Por cada paso, pon VERIFICADO, NO VERIFICADO o INCONCLUSO, con el comando, la cifra y la ruta.

**P8. Cierre.**
- Comprueba el predicado completo.
- Audita el registro contra lo que pasó de verdad.
- Revisión cruzada del registro. Consulta orchestrator_capabilities y lanza delegate_task con un proveedor que no sea Anthropic. Si no hay ninguno, escribe en "Atención" que no hubo revisión cruzada.
- Abre el PR con el playbook Opening a PR y regístralo con link_pull_request. Usa las secciones Why, What changed, Scope, Blast Radius y Verification, con una cifra principal. Las tablas van en report.md.
- Respuesta final:
  - el estado del predicado;
  - qué se verificó y qué no;
  - las decisiones pendientes;
  - la sección Atención.
