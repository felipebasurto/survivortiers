# Correr el cálculo en Runpod

La hoja de la mañana está en `docs/simulator/RUNPOD-MORNING.md`. El comando es `bash simulator/runpod/run.sh funnel full`. Antes, `funnel full --dry-run` imprime el número de partidas, la ETA y el coste, y no simula.

Máquina: un Pod CPU `cpu5c`, 32 vCPU, 64 GB. Unos 1,12 USD/hora. Este binario no usa GPU. El estudio está en `docs/simulator/runpod-hardware-2026-10-21.md`.

No crees el Pod desde este repo. Cuando esté alquilado, clona este árbol (tiene que incluir el embudo `production`, no un `main` anterior), entra en el repo y:

```sh
bash simulator/runpod/run.sh prepare
bash simulator/runpod/run.sh benchmark 25 7 15 30 32 4 mature
bash simulator/runpod/run.sh plan
bash simulator/runpod/run.sh cost
bash simulator/runpod/run.sh run
```

`prepare` compila y pasa los tests. `benchmark` mide una escena madura de 15 segundos; no es el ranking. `plan` escribe el listado de partidas y no simula ninguna. `run` reanuda solo hasta acabar el listado o hasta el tope de unos 4 USD (dos horas como máximo). Para el Pod:

```sh
POKESIM_HOURLY_USD=1.12 POKESIM_BUDGET_USD=4 bash simulator/runpod/run.sh run
```

Al terminar, copia `simulator/runpod-results.json` y `simulator/runpod-cache`. Después apaga el Pod en Runpod. Este script no lo apaga y, si lo dejas encendido, sigue cobrando.

`prepare`, `plan`, `benchmark`, `cost`, `run` y `resume` siguen siendo el haz de producción anterior. El haz medido el 21 de octubre queda descartado como búsqueda a publicar. No lo relances para el ranking.

`funnel smoke` corre tres especies y escribe `simulator/runpod-funnel/smoke/`. `funnel full` calibra, hace el recall, recorre las especies y empaqueta `simulator/runpod-funnel/funnel-results.tar.gz`. Si el recall falla, el embudo sigue y la primera línea de `report.md` lo dice.

Los resultados miden un shortlist, no un óptimo global. `rankingReady` sigue en false. No los publiques en la web hasta revisarlos.
