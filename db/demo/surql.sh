#!/bin/zsh
# Envía un fichero SurrealQL entero por HTTP y muestra los errores.
#
# Por qué HTTP y no `surreal sql`: la CLI procesa el script línea a línea, así
# que revienta cualquier sentencia multilínea (DEFINE FUNCTION, DEFINE EVENT)
# con errores de parseo falsos. El endpoint /sql recibe el fichero completo.
#
# uso: ./surql.sh fichero.surql
set -e
: ${SURREAL_URL:=http://127.0.0.1:8099}
: ${SURREAL_USER:=root}
: ${SURREAL_PASS:=root}
: ${SURREAL_NS:=dx}
: ${SURREAL_DB:=bank}

curl -sS -X POST "$SURREAL_URL/sql" \
  -u "$SURREAL_USER:$SURREAL_PASS" \
  -H "Accept: application/json" \
  -H "surreal-ns: $SURREAL_NS" \
  -H "surreal-db: $SURREAL_DB" \
  --data-binary @"$1"
