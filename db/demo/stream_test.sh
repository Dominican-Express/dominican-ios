#!/bin/zsh
# Prueba de la entrada por Kafka (stream_test.py) sobre un SurrealDB temporal
# propio (puerto 8097) que se apaga al final. Necesita Kafka encendido:
#   ./db/demo/demo.sh kafka-up && ./db/demo/stream_test.sh
# Va aparte de test_all.sh porque necesita Kafka; ~1 min.
set -e
DIR="${0:A:h}"
cd "$DIR"
: ${SURREAL_BIN:=surreal}
PORT=8097
export SURREAL_URL=http://127.0.0.1:$PORT

nc -z 127.0.0.1 9092 2>/dev/null || { echo "kafka is not running: ./db/demo/demo.sh kafka-up"; exit 1; }
if curl -s -o /dev/null --max-time 1 "$SURREAL_URL/health"; then
  echo "port $PORT is busy; stop whatever is running there first"; exit 1
fi
DATA=$(mktemp -d "${TMPDIR:-/tmp}/dx-stream.XXXXXX")
"$SURREAL_BIN" start --username root --password root --bind 127.0.0.1:$PORT \
  --no-banner --log warn "surrealkv://$DATA/kv" > "$DATA/server.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null; wait $SERVER 2>/dev/null; rm -rf "$DATA"' EXIT
for i in {1..40}; do curl -s -o /dev/null --max-time 1 "$SURREAL_URL/health" && break; sleep 0.25; done

uv run -q --with confluent-kafka python3 stream_test.py
