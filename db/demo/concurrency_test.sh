#!/bin/zsh
# Prueba de concurrencia: ¿aguanta el invariante de saldo bajo carrera?
#
# Lanza N transferencias simultáneas por el importe COMPLETO del saldo. Solo
# una debería poder cuajar. Se repite REPS veces y se cuenta cuántas rondas
# acaban con saldo negativo.
#
# Se ejecuta contra las dos implementaciones:
#   fn::transfer         -> escribe account.balance, crea conflicto write-write
#   fn::transfer_unsafe  -> ledger puro, sin punto de conflicto
#
# uso: ./db/demo/concurrency_test.sh [transfer|transfer_unsafe] [N] [REPS]
set -e
DIR="${0:A:h}"
FN=${1:-transfer}; N=${2:-10}; REPS=${3:-30}
export SURREAL_DB=${SURREAL_DB:-bank}

cat > /tmp/dx_reset_$$.surql <<'R'
DELETE entry; DELETE txn; DELETE transfer;
UPDATE account:ana SET balance = 0dec;
UPDATE account:luis SET balance = 0dec;
UPDATE account:ext SET balance = 0dec;
R
echo "RETURN fn::credit(account:ana, 100dec, 'payroll');" >> /tmp/dx_reset_$$.surql
printf "BEGIN;\nLET \$r = fn::%s(account:ana, account:luis, 100dec);\nCOMMIT;\n" "$FN" > /tmp/dx_one_$$.surql
echo 'RETURN fn::balance(account:ana);' > /tmp/dx_chk_$$.surql

BAD=0
for r in $(seq 1 $REPS); do
  "$DIR/surql.sh" /tmp/dx_reset_$$.surql > /dev/null
  for i in $(seq 1 $N); do "$DIR/surql.sh" /tmp/dx_one_$$.surql > /dev/null & done
  wait
  L=$("$DIR/surql.sh" /tmp/dx_chk_$$.surql | python3 -c "import sys,json;print(json.load(sys.stdin)[0]['result'])")
  if [[ "$L" != "0" ]]; then
    BAD=$((BAD+1)); echo "  ronda $r -> saldo $L   DESCUBIERTO"
  fi
done
if [[ "$DEMO_LANG" == "en" ]]; then
  echo "fn::$FN  ->  $BAD/$REPS rounds ended in an overdraft"
else
  echo "fn::$FN  ->  $BAD/$REPS rondas con descubierto  ($N transferencias simultáneas por ronda)"
fi
rm -f /tmp/dx_*_$$.surql
