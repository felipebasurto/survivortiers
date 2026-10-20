# Regenerar todos los datos

Todo el pipeline de simulación está en `build/regen.py`. Es reanudable, comprueba sus propias salidas
y deja un `MANIFEST.json` con el commit, el hash del binario, la máquina, los tiempos y el hash de cada salida.

## 1. Máquina

- **64 vCPU** (32 da unas 3,5 h; 96 da unas 1 h). Ubuntu 22.04 o 24.04. 150 GB de disco. RAM de sobra (menos de 4 GB).
- Medido en 4 vCPU con el horizonte antiguo (900 s): 26 ms de CPU por partida con el bot Play, y unas
  **12,5 millones de partidas, unas 90 horas de CPU**. El horizonte ahora es 1800 s (minuto 30), así que cada partida
  dura más y esa cifra ya no vale. La prueba de humo de abajo mide el coste nuevo; apúntalo aquí antes de alquilar.
- El resultado no depende del número de hilos (comprobado: 1 hilo y 4 hilos dan los mismos bytes).

```sh
# Rust estable, Node 22, Python 3.12
curl https://sh.rustup.rs -sSf | sh -s -- -y && . "$HOME/.cargo/env"
sudo apt-get install -y nodejs npm git   # o Node 22 desde nodesource
python3 -m pip install numpy pyarrow duckdb pandas
```

## 2. Código

```sh
git clone https://github.com/felipebasurto/survivortiers.git && cd survivortiers
git checkout gengar-build-fix            # o main, cuando el PR esté fusionado
git status --short                       # tiene que estar vacío: el manifiesto lo exige
cargo build --release --manifest-path simulator/sim-rs/Cargo.toml
```

## 3. Prueba de humo (unos 15 minutos en 4 vCPU)

Medida en `4a6a85b`, horizonte de 1800 s: solo screen 91 s, solo refine 226 s, solo contend 497 s, start sweep 87 s, start rank 22 s, resto menos de 5 s cada uno; 13 etapas, unos 16 minutos. Con 1 semilla y 3 especies, así que no sirve para estimar la corrida completa.

No publica nada. Escribe en una carpeta aparte, con 1 semilla por partida y 3 especies (Bulbasaur, Gengar y Pikachu):

```sh
SURVIVOR_FIXED=/tmp/smoke/fixed python3 build/regen.py --sim --quick 16 --scope 1,94,25
```

Tiene que acabar con `simulation stages done`. Si no, el fallo está en el log, no en la máquina.
Cuenta también la etapa `items`: sin ella, la corrida no prueba los objetos.

## 4. La corrida real

```sh
nohup python3 build/regen.py --sim > run.log 2>&1 &
tail -f run.log            # por etapa: "== nombre", después "nombre: N s"
```

Si se corta, **vuelve a lanzar el mismo comando**: las etapas terminadas se saltan, y la criba de grupos
y las builds se reanudan por trozos de 25.000 grupos.

Etapas, en orden (`python3 build/regen.py --sim` las lista al fallar):
`solo_screen`, `solo_refine`, `solo_contend`, `group_gate`, `group_screen`, `group_refine`,
`start_sweep`, `start_rank`, `build_screen`, `build_refine`, `rank`, `counterfactuals`, `items`.

`items` prueba cada objeto que el motor modela (`choiceband`, `lifeorb`, `quickclaw`, `choicescarf`, `assaultvest`,
`leftovers`, `luckyegg`, `shellbell`, `rockyhelmet`, `focussash`) en cada build que muestra el ranking, contra la misma
build sin objeto. Salida: `items/delta.csv` y un CSV por objeto. `amuletcoin` existe en el juego pero el motor no lo
modela (su efecto son monedas, que la puntuación no cuenta): no se prueba, y así se dice en el informe.

`group_gate` es la compuerta: 300 grupos por la ruta del generador y por la explícita, con los mismos bytes.
Si no coinciden, la corrida se para antes de simular nada más.

## 5. Publicar

```sh
python3 build/regen.py                   # reescribe data/ranking_definitive.csv y data/builds.csv
python3 build/regen.py --check           # tiene que pasar
```

Se niega a publicar desde cualquier carpeta que no sea la oficial (`SURVIVOR_FIXED` no debe estar puesto).

## 6. Comprobaciones, en paralelo

```sh
python3 build/checks.py --site           # rust, paridad con el juego, python, datos, sitio
```

Cada carril tiene su log en `.cache/checks/`. Los cuatro primeros carriles son independientes.

## 7. Resúmenes de las fichas (obligatorio antes de construir el sitio)

`catalog.py` se niega a construir si `data/summaries.json` no cuadra con los datos. Después de publicar, muchas
fichas no cuadran. `facts_export.py` necesita `counterfactuals_g2p2.csv`, así que esto solo corre con la corrida
completa (no con la de humo):

```sh
python3 build/regen.py --facts           # facts.parquet y refresh_summaries.py (plantilla determinista)
python3 build/summary_pipeline.py check  # tiene que pasar
python3 build/checks.py --site           # y ahora el sitio
```

`refresh_summaries.py` reescribe **todas** las fichas desde las afirmaciones permitidas (plantilla determinista; no conserva texto antiguo). La versión con subagentes
(`summary_pipeline.py plan / validate / assemble`) da mejor prosa, pero necesita que alguien la ejecute.

## 8. Qué guardar

- `simulator/results/fixed_group/*.csv` que leen la publicación y los datos (las tablas de la etapa `rank`, las de
  `counterfactuals` y `items/delta.csv`), `data/*`, y `MANIFEST.json`: van a git.
- Lo demás (`*_out/`, trozos, `gate/`, ficheros `_only.txt`) lo ignora `.gitignore`. Se regenera.
- El manifiesto dice qué código y qué binario produjo cada dato. Guárdalo con los datos.
- El directorio completo pesa unos cientos de MB. Si no quieres meterlo en git, copia `simulator/results/`
  a donde quieras (y el `MANIFEST.json` con él).

## Qué no regenera este pipeline

- Los resúmenes de texto: ver el paso 7.
- Las pasivas. Se quitaron del simulador, de los datos y de la web: cada jugador decide cómo juega.
- `amuletcoin`: el motor no lo modela (ver la etapa `items`).
