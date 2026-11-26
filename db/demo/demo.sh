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
#   ./db/demo/demo.sh sdk          # CRUD desde Python con el SDK oficial, en su propia base `sdk`
#
#   ./db/demo/demo.sh cluster-up       # HAProxy + 2 nodos SurrealDB + 1 PD + 3 TiKV (CLUSTER.md)
#   ./db/demo/demo.sh cluster-status   # stores, líderes y nodos
#   ./db/demo/demo.sh cluster-write 40 # escrituras por el nodo A, cuenta por el B
#   ./db/demo/demo.sh cluster-kill     # mata el TiKV con más líderes
#   ./db/demo/demo.sh cluster-revive   # lo relanza; se pone al día solo
#   ./db/demo/demo.sh cluster-kill-node    # mata el nodo SurrealDB A (HAProxy lo saca)
#   ./db/demo/demo.sh cluster-revive-node  # lo relanza
#   ./db/demo/demo.sh cluster-down     # lo para todo y borra los datos del clúster
#
#   ./db/demo/demo.sh kafka-up         # broker de Kafka local, topics payments y fraud-alerts
#   ./db/demo/demo.sh stream-reset     # base `stream` limpia y topics vacíos (STREAMING.md)
#   ./db/demo/demo.sh stream-consume   # terminal 1: consumidor de pagos → SurrealDB
#   ./db/demo/demo.sh stream-bridge    # terminal 2: alertas de SurrealDB → Kafka
#   ./db/demo/demo.sh stream-alerts    # terminal 3: panel que lee las alertas de Kafka
#   ./db/demo/demo.sh stream-produce   # terminal 4: los pagos del guion
#   ./db/demo/demo.sh stream-test      # mata el consumidor a mitad: sin duplicados ni pérdidas
#   ./db/demo/demo.sh kafka-down       # para Kafka y borra los mensajes
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
# Kafka corre en local, como SurrealDB: sin Docker. 3.9.1 y no 4.x porque la
# 4 exige Java 17 y la 3.9 arranca con Java 11; el modo KRaft es el mismo.
KAFKA_VER=3.9.1
: ${KAFKA_HOME:=$HOME/.local/share/dominican-express/kafka_2.13-$KAFKA_VER}
KAFKA_DATA="${STUDIO_DATA:h}/kafka"
KAFKA_PID="$KAFKA_DATA/kafka.pid"
kt() { "$KAFKA_HOME/bin/kafka-topics.sh" --bootstrap-server 127.0.0.1:9092 "$@"; }
kafkapid() {
  local pid
  pid=$(cat "$KAFKA_PID" 2>/dev/null) || return 1
  ps -p "$pid" -o command= 2>/dev/null | grep -q "$KAFKA_DATA" && echo "$pid"
}
topics() {
  # 3 particiones: la clave (la cuenta) reparte los pagos y dos consumidores
  # del mismo grupo pueden trabajar a la vez.
  for t in payments fraud-alerts payments-dlq; do
    kt --create --if-not-exists --topic $t --partitions 3 --replication-factor 1 > /dev/null
  done
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
    SURREAL_URL=$URL DEMO_LANG=en python3 aml_load.py --data ../data/ibm-aml --set HI-Small-sample --db aml | tail -1
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
    echo "database ready: schema loaded, 5 customers, 2 cards, 3 app users"
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
    # Base propia y recién creada, como `race`: recargar la semilla en `bank`
    # borraba el ataque y las alertas de la parte A de DEMO.md.
    export SURREAL_DB=access
    curl -s -X POST "$URL/sql" -u root:root -H "surreal-ns: dx" \
         --data-binary "REMOVE DATABASE IF EXISTS access;" > /dev/null
    ./apply.sh > /dev/null && ./surql.sh 01_seed.surql > /dev/null
    DEMO_LANG=en python3 access_test.py
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
  sdk)
    # Base propia y recién creada: tras `attack`, Ana está congelada en `live`
    # y su pago desde Python saldría 423 en vez de enseñar el cobro único.
    curl -s -X POST "$URL/sql" -u root:root -H "surreal-ns: dx" \
         --data-binary "REMOVE DATABASE IF EXISTS sdk;" > /dev/null
    SURREAL_URL=$URL SURREAL_DB=sdk ./apply.sh > /dev/null
    SURREAL_URL=$URL SURREAL_DB=sdk ./surql.sh 01_seed.surql > /dev/null
    exec uv run -q --with-requirements requirements.txt python demo_client.py \
         --url "ws://${URL#http://}/rpc" --db sdk
    ;;
  kafka-up)
    if kafkapid > /dev/null; then echo "kafka already running"; exit 0; fi
    if nc -z 127.0.0.1 9092 2> /dev/null; then
      echo "port 9092 is busy with another process; stop it first"; exit 1
    fi
    if [[ ! -x "$KAFKA_HOME/bin/kafka-server-start.sh" ]]; then
      echo "first start: downloading Kafka $KAFKA_VER (~120 MB)…"
      tgz="${KAFKA_HOME:h}/kafka.tgz"
      base="https://archive.apache.org/dist/kafka/$KAFKA_VER/kafka_2.13-$KAFKA_VER.tgz"
      mkdir -p "${KAFKA_HOME:h}"
      curl -sSfL -o "$tgz" "$base"
      want=$(curl -sSfL "$base.sha512" | python3 -c "import sys; print(''.join(sys.stdin.read().split(':',1)[1].split()).lower())")
      [[ "$(shasum -a 512 "$tgz" | cut -d' ' -f1)" == "$want" ]] || { rm -f "$tgz"; echo "checksum mismatch"; exit 1; }
      tar -xzf "$tgz" -C "${KAFKA_HOME:h}" && rm -f "$tgz"
    fi
    mkdir -p "$KAFKA_DATA"
    { cat ../stream/server.properties; echo "log.dirs=$KAFKA_DATA/log"; } > "$KAFKA_DATA/server.properties"
    if [[ ! -f "$KAFKA_DATA/log/meta.properties" ]]; then
      "$KAFKA_HOME/bin/kafka-storage.sh" format -t "$("$KAFKA_HOME/bin/kafka-storage.sh" random-uuid)" \
          -c "$KAFKA_DATA/server.properties" > /dev/null
    fi
    # 512 MB de memoria: el MacBook Air de la demo no tiene RAM de sobra.
    KAFKA_HEAP_OPTS="-Xmx512m -Xms256m" nohup "$KAFKA_HOME/bin/kafka-server-start.sh" \
        "$KAFKA_DATA/server.properties" > "$KAFKA_DATA/kafka.log" 2>&1 &!
    echo $! > "$KAFKA_PID"
    for i in {1..60}; do kafkapid > /dev/null && kt --list > /dev/null 2>&1 && break; sleep 1; done
    kafkapid > /dev/null && kt --list > /dev/null 2>&1 \
      || { echo "kafka did not start; see $KAFKA_DATA/kafka.log"; exit 1; }
    topics
    echo "kafka on 127.0.0.1:9092, topics payments, fraud-alerts and payments-dlq (3 partitions each)"
    echo "remember: ./db/demo/demo.sh kafka-down when you finish"
    ;;
  kafka-down)
    pid=$(kafkapid) || pid=""
    if [[ -n "$pid" ]]; then
      kill "$pid"
      for i in {1..80}; do ps -p "$pid" > /dev/null || break; sleep 0.25; done
      if ps -p "$pid" > /dev/null; then
        echo "kafka (PID $pid) is still stopping; run kafka-down again in a moment"; exit 1
      fi
    fi
    rm -rf "$KAFKA_DATA"
    echo "kafka stopped, messages deleted"
    ;;
  stream-reset)
    # Base y topics nuevos: un mensaje que se quedó en el topic de una prueba
    # anterior se volvería a aplicar al arrancar el consumidor.
    kt --list > /dev/null 2>&1 || { echo "kafka is not running: ./db/demo/demo.sh kafka-up"; exit 1; }
    curl -s -X POST "$URL/sql" -u root:root -H "surreal-ns: dx" \
         --data-binary "REMOVE DATABASE IF EXISTS stream;" > /dev/null
    SURREAL_URL=$URL SURREAL_DB=stream ./apply.sh > /dev/null
    SURREAL_URL=$URL SURREAL_DB=stream ./surql.sh 01_seed.surql > /dev/null
    for t in payments fraud-alerts payments-dlq; do
      kt --delete --if-exists --topic $t > /dev/null 2>&1 || true
    done
    # El borrado de un topic termina después de que responda el comando: si
    # se crea antes, --if-not-exists no hace nada y el topic desaparece luego.
    for i in {1..30}; do
      kt --list 2> /dev/null | grep -qxE 'payments|fraud-alerts|payments-dlq' || break
      sleep 0.5
    done
    topics
    echo "stream: 5 customers, empty topics"
    ;;
  stream-consume)
    SURREAL_URL=$URL exec uv run -q --with confluent-kafka python3 stream_consumer.py --sweep 2
    ;;
  stream-bridge)
    SURREAL_WS=${SURREAL_WS:-ws://${URL#http://}/rpc} \
      exec uv run -q --with confluent-kafka --with websockets python3 alert_bridge.py
    ;;
  stream-alerts)
    exec uv run -q --with confluent-kafka python3 alert_feed.py
    ;;
  stream-produce)
    exec uv run -q --with confluent-kafka python3 stream_producer.py demo
    ;;
  stream-test)
    exec ./stream_test.sh
    ;;
  cluster-*)
    exec ../cluster/cluster.sh "${1#cluster-}" "${@:2}"
    ;;
  *)
    sed -n '2,43p' "$SELF" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
