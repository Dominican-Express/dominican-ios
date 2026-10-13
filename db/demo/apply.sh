#!/bin/zsh
# Aplica todo el esquema a una base limpia y falla si algo no entra.
# uso: ./db/demo/apply.sh
set -e
DIR="${0:A:h}"
: ${SURREAL_URL:=http://127.0.0.1:8099}
: ${SURREAL_USER:=root}
: ${SURREAL_PASS:=root}
: ${SURREAL_NS:=dx}
: ${SURREAL_DB:=bank}

# En 3.x el namespace y la base NO se crean solos al mandar las cabeceras:
# el endpoint responde "The database 'x' does not exist".
printf "%-28s " "namespace + base"
curl -sS -X POST "$SURREAL_URL/sql" -u "$SURREAL_USER:$SURREAL_PASS" \
  -H "Accept: application/json" \
  --data-binary "DEFINE NAMESPACE IF NOT EXISTS $SURREAL_NS; USE NS $SURREAL_NS; DEFINE DATABASE IF NOT EXISTS $SURREAL_DB;" > /dev/null
echo "ok"

for f in "$DIR"/../schema/*.surql; do
  printf "%-28s " "${f:t}"
  OUT=$("$DIR/surql.sh" "$f")
  ERRS=$(printf '%s' "$OUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print('RESPUESTA NO-JSON'); raise SystemExit(0)
if isinstance(d, dict):
    print(d.get('information', d)); raise SystemExit(0)
bad = [str(s.get('result'))[:160] for s in d if s.get('status') != 'OK']
for b in bad: print(b)
")
  if [[ -n "$ERRS" ]]; then echo "FALLO"; echo "$ERRS"; exit 1; else echo "ok"; fi
done
echo "esquema aplicado completo"
