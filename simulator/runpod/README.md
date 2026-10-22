# Correr el cálculo en Runpod

El ranking acotado se lanza con `bash simulator/runpod/run.sh ranking smoke|pilot|full`. `--dry-run` imprime el número de partidas y no simula. La guía completa está en `docs/simulator/laboratory-runner.md`.

Máquina: un Pod CPU `cpu5c`, 32 vCPU, 64 GB. Unos 1,12 USD/hora. Este binario no usa GPU. El estudio está en `docs/simulator/runpod-hardware-2026-10-21.md`.

No crees el Pod desde este repo. Cuando esté alquilado, clona la rama que contiene el ranking acotado, entra en el repo y:

```sh
bash simulator/runpod/run.sh prepare              # compila y pasa los tests
bash simulator/runpod/run.sh ranking smoke        # 2 especies, partidas de 15 s: comprueba que todo funciona
bash simulator/runpod/run.sh ranking pilot        # 41 especies repartidas, partidas de 900 s: mide el tiempo real
bash simulator/runpod/run.sh ranking full         # las 966 especies
```

`pilot` usa la misma configuración que `full` sobre una de cada 24 especies, así que `full` tarda aproximadamente `tiempo del pilot × 966 / 41` más el laboratorio. No hay tope automático de tiempo ni de gasto: el script avisa cada minuto con la etapa, las configuraciones hechas y las etapas pendientes, y si se corta la caché permite reanudar. Al terminar, copia `simulator/runpod-ranking/<preset>/` (en especial `results.json`, `sim-results.json` y `attacks.json`). Después apaga el Pod en Runpod. Este script no lo apaga y, si lo dejas encendido, sigue cobrando.

`prepare`, `plan`, `benchmark`, `cost`, `run` y `resume` siguen siendo el haz de producción anterior. El haz medido el 21 de octubre queda descartado como búsqueda a publicar. No lo relances para el ranking.

Los resultados miden un shortlist, no un óptimo global. `rankingReady` sigue en false. No los publiques en la web hasta revisarlos.
