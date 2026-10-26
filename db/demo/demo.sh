#!/bin/zsh
# Guion de la demo en clase. Un subcomando por paso, para no teclear en directo.
#
#   ./db/demo/demo.sh server   # terminal 1: arranca SurrealDB en memoria
#   ./db/demo/demo.sh reset    # deja la base limpia, con esquema y datos
#   ./db/demo/demo.sh listen   # terminal 2: alertas en vivo (en inglés)
#   ./db/demo/demo.sh attack   # terminal 3: lanza el ataque y el barrido
#   ./db/demo/demo.sh race     # concurrencia: versión buena frente a insegura
#   ./db/demo/demo.sh access   # permisos, actuando como clientes
#   ./db/demo/demo.sh studio       # SurrealDB EN DISCO, para abrirlo con Surrealist
#   ./db/demo/demo.sh studio-load  # carga las bases `bank` (historia) y `volume` (300 clientes)
#
# SURREAL_BIN apunta al binario si `surreal` no está en el PATH.
set -e
DIR="${0:A:h}"
cd "$DIR"
: ${SURREAL_BIN:=surreal}
# 20 rondas y no 10: con 10, la versión insegura puede salir limpia por azar
# (~0,7 % medido) y la demo no demostraría nada. Con 20, ~0,005 %; tarda ~5 s.
: ${ROUNDS:=20}
# Fuera del repo: un worktree borrado no se lleva los datos de la presentación.
: ${STUDIO_DATA:=$HOME/.local/share/dominican-express/surrealkv}

case "$1" in
  server)
    exec "$SURREAL_BIN" start --username root --password root \
         --bind 127.0.0.1:8099 --no-banner memory
    ;;
  reset)
    ./apply.sh > /dev/null
    ./surql.sh 01_seed.surql > /dev/null
    echo "database ready: schema loaded, 5 customers, 2 cards, 2 app users"
    ;;
  listen)
    DEMO_LANG=en exec uv run --quiet --with websockets python3 live_listener.py
    ;;
  attack)
    echo "running the attack: mule ring, shared device, structuring, impossible travel…"
    ./surql.sh 02_attack.surql > /dev/null
    echo "running the background sweep…"
    ./surql.sh 03_detect.surql > /dev/null
    echo "done. alerts are in the other terminal."
    ;;
  race)
    echo "10 simultaneous transfers of the full balance, $ROUNDS rounds each"
    echo
    DEMO_LANG=en ./concurrency_test.sh transfer 10 "$ROUNDS" | tail -1
    DEMO_LANG=en ./concurrency_test.sh transfer_unsafe 10 "$ROUNDS" | tail -1
    ./surql.sh 01_seed.surql > /dev/null   # la prueba ensucia los saldos: se restaura
    ;;
  access)
    ./surql.sh 01_seed.surql > /dev/null
    python3 access_test.py
    ;;
  studio)
    mkdir -p "${STUDIO_DATA:h}"
    exec "$SURREAL_BIN" start --username root --password root \
         --bind 127.0.0.1:8099 --no-banner "surrealkv://$STUDIO_DATA"
    ;;
  studio-load)
    # `bank`: los 5 clientes de la semilla con el ataque y el barrido ya hechos,
    # pequeña para que el grafo se lea en pantalla.
    SURREAL_DB=bank ./apply.sh > /dev/null
    SURREAL_DB=bank ./surql.sh 01_seed.surql > /dev/null
    SURREAL_DB=bank ./surql.sh 02_attack.surql > /dev/null
    SURREAL_DB=bank ./surql.sh 03_detect.surql > /dev/null
    echo "bank:   5 customers, attack + sweep done"
    # `volume`: banco generado con vida normal y fraude plantado.
    SURREAL_DB=volume ./apply.sh > /dev/null
    SURREAL_DB=volume python3 gen_volume.py --customers 300 --days 60 \
        --truth "${STUDIO_DATA:h}/volume_truth.json" > /dev/null
    SURREAL_DB=volume ./surql.sh 03_detect.surql > /dev/null
    echo "volume: 300 customers, 60 days, planted fraud, sweep done"
    ;;
  *)
    sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
