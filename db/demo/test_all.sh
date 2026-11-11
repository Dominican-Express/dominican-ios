#!/bin/zsh
# Todas las pruebas: las 6 suites y sus pruebas en rojo, sobre un servidor
# temporal propio (SurrealKV con versionado, puerto 8098), que se apaga al final.
#
# uso: ./db/demo/test_all.sh            # ~10 min, sobre todo las pruebas en rojo
#      ./db/demo/test_all.sh --quick    # solo las suites (~1 min)
#
# SurrealKV y no memoria: es el motor de la demo, y el fallo surrealdb#7601
# (09_time_travel) solo aparece en él.
# Una prueba en rojo rompe el esquema a propósito (redteam.py) y comprueba que
# su suite lo detecta: una prueba que nunca se ha visto fallar no vigila nada.
set -e
DIR="${0:A:h}"
cd "$DIR"
: ${SURREAL_BIN:=surreal}
PORT=8098
DATA=$(mktemp -d "${TMPDIR:-/tmp}/dx-tests.XXXXXX")
export SURREAL_URL=http://127.0.0.1:$PORT

if curl -s -o /dev/null --max-time 1 "$SURREAL_URL/health"; then
  echo "port $PORT is busy; stop whatever is running there first"; exit 1
fi
SURREAL_DATASTORE_VERSIONED=true SURREAL_DATASTORE_RETENTION=30d \
  "$SURREAL_BIN" start --username root --password root --bind 127.0.0.1:$PORT \
  --no-banner --log warn "surrealkv://$DATA/kv" > "$DATA/server.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null; wait $SERVER 2>/dev/null; rm -rf "$DATA"' EXIT
for i in {1..40}; do curl -s -o /dev/null --max-time 1 "$SURREAL_URL/health" && break; sleep 0.25; done

FAILED=0
SUITES=(access payments cards detect time_travel controls)
for s in $SUITES; do
  export SURREAL_DB=t_$s
  ./apply.sh > /dev/null && ./surql.sh 01_seed.surql > /dev/null
  r=$(python3 ${s}_test.py 2>&1 | tail -1)
  printf "%-12s test     %s\n" $s "$r"
  [[ "$r" == "TODO EN ORDEN" ]] || FAILED=1
done
if [[ "$1" != "--quick" ]]; then
  for s in $SUITES; do
    r=$(python3 ${s}_redteam.py 2>&1 | tail -1)
    printf "%-12s red-team %s\n" $s "$r"
    n=${r%%/*}; m=${${r#*/}%% *}   # «9/9 roturas…» → 9 y 9
    [[ $n == <-> && $n == $m ]] || FAILED=1
  done
fi
[[ $FAILED == 0 ]] && echo "ALL PASSED" || { echo "SOMETHING FAILED"; exit 1; }
