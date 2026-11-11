#!/bin/zsh
# Guion de la demo en clase. Un subcomando por paso, para no teclear en directo.
#
#   ./db/demo/demo.sh up       # enciende la base EN DISCO en segundo plano (carga los datos la 1.ª vez)
#   ./db/demo/demo.sh status   # ¿está encendida?
#   ./db/demo/demo.sh down     # la apaga (solo la que encendió `up`)
#   ./db/demo/demo.sh aml      # carga la muestra del dataset de IBM en la base `aml` y la barre
#
#   ./db/demo/demo.sh server   # terminal 1: arranca SurrealDB de pruebas (SurrealKV temporal)
#   ./db/demo/demo.sh reset    # deja la base limpia, con esquema y datos
#   ./db/demo/demo.sh listen   # terminal 2: alertas en vivo (en inglés)
#   ./db/demo/demo.sh attack   # terminal 3: lanza el ataque y el barrido
#   ./db/demo/demo.sh race     # concurrencia: versión buena frente a insegura
#   ./db/demo/demo.sh access   # permisos, actuando como clientes
#   ./db/demo/demo.sh studio       # SurrealDB EN DISCO, para abrirlo con Surrealist
#   ./db/demo/demo.sh studio-load  # carga las bases `bank` (historia) y `volume` (300 clientes)
#   ./db/demo/demo.sh stage        # base `live` limpia, sin ataque, para la demo en directo
#   ./db/demo/demo.sh coverup      # las mulas, como clientes, intentan borrar el rastro (tras `attack`)
#   ./db/demo/demo.sh insider      # un empleado con root sí borra; la auditoría lo recoge
#
#   ./db/demo/demo.sh cluster-up       # 1 PD + 3 TiKV + 2 nodos SurrealDB (CLUSTER.md)
#   ./db/demo/demo.sh cluster-status   # stores, líderes y nodos
#   ./db/demo/demo.sh cluster-write 40 # escrituras por el nodo A, cuenta por el B
#   ./db/demo/demo.sh cluster-kill     # mata el TiKV con más líderes
#   ./db/demo/demo.sh cluster-revive   # lo relanza; se pone al día solo
#   ./db/demo/demo.sh cluster-down     # lo para todo y borra los datos del clúster
#
# El servidor arranca CON versionado (máquina del tiempo, 09_time_travel): cada
# estado anterior se guarda 30 días. SURREAL_DB elige la base de attack/coverup.
#
# SURREAL_BIN apunta al binario si `surreal` no está en el PATH.
set -e
SELF="${0:A}"
DIR="${0:A:h}"
cd "$DIR"
: ${SURREAL_BIN:=surreal}
# 20 rondas y no 10: con 10, la versión insegura puede salir limpia por azar
# (~0,7 % medido) y la demo no demostraría nada. Con 20, ~0,005 %; tarda ~5 s.
: ${ROUNDS:=20}
# Fuera del repo: un worktree borrado no se lleva los datos de la presentación.
: ${STUDIO_DATA:=$HOME/.local/share/dominican-express/surrealkv}
# Versionado: SurrealKV (beta) y, en 3.2.4, también el motor en memoria (la 3.3
# lo quita de memoria). 30 días: la investigación de una alerta es cosa de
# días; la historia larga es el libro de apuntes, que no caduca.
export SURREAL_DATASTORE_VERSIONED=true SURREAL_DATASTORE_RETENTION=30d

URL=${SURREAL_URL:-http://127.0.0.1:8099}
PIDFILE="${STUDIO_DATA:h}/surreal.pid"
alive() { curl -s -o /dev/null --max-time 1 "$URL/health"; }
# Solo vale si ese PID sigue siendo NUESTRO surreal (los PID se reutilizan).
ourpid() {
  local pid
  pid=$(cat "$PIDFILE" 2>/dev/null) || return 1
  ps -p "$pid" -o command= 2>/dev/null | grep -q "surrealkv://$STUDIO_DATA" && echo "$pid"
}
has_data() {
  curl -s -X POST "$URL/sql" -u root:root -H "Accept: application/json" -H "surreal-ns: dx" \
       --data-binary "INFO FOR NS;" 2>/dev/null | grep -q '"bank"'
}

case "$1" in
  up)
    if alive; then echo "already running on $URL"; exit 0; fi
    mkdir -p "${STUDIO_DATA:h}"
    nohup "$SURREAL_BIN" start --username root --password root --bind 127.0.0.1:8099 \
          --no-banner --log warn "surrealkv://$STUDIO_DATA" > "${STUDIO_DATA:h}/surreal.log" 2>&1 &!
    echo $! > "$PIDFILE"
    for i in {1..20}; do alive && break; sleep 0.5; done
    alive || { echo "did not start; see ${STUDIO_DATA:h}/surreal.log"; exit 1; }
    echo "running on $URL (data in ${STUDIO_DATA:h})"
    if ! has_data; then
      echo "first start: loading data (~1 min)…"
      "$SELF" studio-load && "$SELF" stage
    fi
    echo "connect Surrealist over WebSocket: ws://127.0.0.1:8099, root / root, namespace dx"
    echo "remember: ./db/demo/demo.sh down when you finish"
    ;;
  status)
    if alive; then echo "running (PID $(ourpid || echo '?'))"; else echo "stopped"; fi
    ;;
  down)
    pid=$(ourpid) || pid=""
    if [[ -z "$pid" ]]; then
      alive && echo "something on port 8099 was not started by 'up'; leaving it alone" \
            || echo "already stopped"
      exit 0
    fi
    kill "$pid"
    for i in {1..20}; do ps -p "$pid" >/dev/null || break; sleep 0.25; done
    rm -f "$PIDFILE"
    echo "stopped"
    ;;
  aml)
    # Muestra del dataset de IBM (DATASET.md): base `aml`, solo núcleo, grafo y detectores.
    SURREAL_URL=$URL python3 aml_load.py --data ../data/ibm-aml --set HI-Small-sample --db aml | tail -1
    curl -s -X POST "$URL/sql" -u root:root -H "Accept: application/json" -H "surreal-ns: dx" -H "surreal-db: aml" \
         --data-binary "RETURN fn::detect_rings_between(d'2022-08-31T00:00:00Z', d'2022-09-20T00:00:00Z', 12);" > /dev/null
    echo "aml: IBM sample loaded and swept (expected: 20 mule_ring, 191 possible_ring)"
    ;;
  server)
    # SurrealKV y NO memoria: es el motor de `studio` y de `domex`, y el fallo
    # surrealdb#7601 (09_time_travel) solo aparece en él. Medido: en memoria la
    # prueba en rojo de la máquina del tiempo bajaba a 6/10, porque no había
    # fallo que cazar. Además la 3.3 quita el versionado del motor en memoria.
    # Carpeta temporal, nueva en cada arranque.
    rm -rf "${TMPDIR:-/tmp}/dominican-express-server"
    exec "$SURREAL_BIN" start --username root --password root \
         --bind 127.0.0.1:8099 --no-banner "surrealkv://${TMPDIR:-/tmp}/dominican-express-server"
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
    # Base propia y recién creada: la prueba borra los apuntes, y en `bank` el
    # ataque ya congeló a ana (no saldría ninguna transferencia).
    export SURREAL_DB=race
    curl -s -X POST "$URL/sql" -u root:root -H "surreal-ns: dx" \
         --data-binary "REMOVE DATABASE IF EXISTS race;" > /dev/null
    ./apply.sh > /dev/null && ./surql.sh 01_seed.surql > /dev/null
    echo "10 simultaneous transfers of the full balance, $ROUNDS rounds each"
    echo
    DEMO_LANG=en ./concurrency_test.sh transfer 10 "$ROUNDS" | grep -E 'rounds|OJO'
    DEMO_LANG=en ./concurrency_test.sh transfer_unsafe 10 "$ROUNDS" | grep -E 'rounds|OJO'
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
  stage)
    # Base aparte para la demo en directo: `bank` se queda como está.
    curl -s -X POST "${SURREAL_URL:-http://127.0.0.1:8099}/sql" -u root:root -H "surreal-ns: dx" \
         --data-binary "REMOVE DATABASE IF EXISTS live;" > /dev/null
    SURREAL_DB=live ./apply.sh > /dev/null
    SURREAL_DB=live ./surql.sh 01_seed.surql > /dev/null
    echo "live: 5 customers, no attack yet"
    ;;
  coverup)
    python3 coverup.py
    ;;
  insider)
    ./surql.sh 04_coverup.surql > /dev/null
    echo "an insider with root deleted the shared phone, removed a co-holder and drained an account"
    echo "every step is in audit_log; fn::investigate rebuilds the alert as it was"
    ;;
  cluster-*)
    exec ../cluster/cluster.sh "${1#cluster-}" "${@:2}"
    ;;
  *)
    sed -n '2,31p' "$SELF" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
