#!/bin/zsh
# Clúster local: 1 PD + 3 TiKV (TiUP playground) y 2 nodos SurrealDB sin estado
# encima. Se llama desde `demo.sh cluster-*`; la explicación está en CLUSTER.md.
#
#   up       arranca todo y carga esquema y semilla en la base `cluster`
#   status   stores de TiKV (estado, líderes) y nodos SurrealDB
#   write N  N escrituras por el nodo A (una cada 0,25 s); al final cuenta por el B
#   kill     mata con SIGKILL el TiKV con más líderes (el caso duro: hay elección)
#   revive   relanza el TiKV muerto con sus mismos datos
#   down     lo para todo, solo lo nuestro, y borra los datos del clúster
#
# TIUP_BIN apunta a tiup si no está en el PATH (el instalador lo deja en ~/.tiup/bin).
set -e
DIR="${0:A:h}"
cd "$DIR/../demo"
: ${SURREAL_BIN:=surreal}
: ${TIUP_BIN:=$(command -v tiup || echo $HOME/.tiup/bin/tiup)}
TIKV_VERSION=v8.5.8
TAG=dominican-express
STATE=$HOME/.local/share/dominican-express/cluster
DATA=${TIUP_HOME:-$HOME/.tiup}/data/$TAG
PD=http://127.0.0.1:2379/pd/api/v1
NODE_A=8101
NODE_B=8102
# Los nodos no versionan: el versionado (09_time_travel) es solo de SurrealKV.
unset SURREAL_DATASTORE_VERSIONED SURREAL_DATASTORE_RETENTION

pd_alive() { curl -s -o /dev/null --max-time 1 "$PD/health"; }
node_alive() { curl -s -o /dev/null --max-time 1 "http://127.0.0.1:$1/health"; }
stores() {
  # una línea por store: id dirección estado líderes regiones
  curl -s --max-time 2 "$PD/stores" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except ValueError:
    data = {}  # PD todavía arrancando
for s in data.get("stores", []) if isinstance(data, dict) else []:
    st = s["status"]
    print(s["store"]["id"], s["store"]["address"], s["store"]["state_name"],
          st.get("leader_count", 0), st.get("region_count", 0))'
}
sql() {
  curl -s -X POST "http://127.0.0.1:$1/sql" -u root:root -H "Accept: application/json" \
       -H "surreal-ns: dx" -H "surreal-db: cluster" --data-binary "$2"
}
now_ms() { perl -MTime::HiRes=time -e 'printf "%.0f", time*1000'; }
# Solo procesos NUESTROS: los de TiKV y PD llevan la carpeta de datos del tag
# en sus argumentos; los surreal, su PID guardado y tikv:// en la orden.
our_tiup_pids() {
  ps -axo pid=,command= | grep -E -- "$DATA/|tiup-playground .*--tag $TAG( |\$)" | grep -v grep | awk '{print $1}'
}
our_node_pid() {
  local pid
  pid=$(cat "$STATE/node-$1.pid" 2>/dev/null) || return 1
  ps -p "$pid" -o command= 2>/dev/null | grep -q "127.0.0.1:$1 .*tikv://" && echo "$pid"
}

case "$1" in
  up)
    [[ -x "$TIUP_BIN" ]] || { echo "tiup not found: install it first (CLUSTER.md, step 1)"; exit 1; }
    if pd_alive; then echo "a PD is already running on 127.0.0.1:2379; stop it first"; exit 1; fi
    mkdir -p "$STATE"
    echo "starting 1 PD + 3 TiKV $TIKV_VERSION (the first time downloads ~110 MB)…"
    nohup "$TIUP_BIN" playground $TIKV_VERSION --mode tikv-slim --pd 1 --kv 3 \
          --without-monitor --tag $TAG --kv.config "$DIR/tikv.toml" \
          > "$STATE/playground.log" 2>&1 &!
    echo $! > "$STATE/playground.pid"
    for i in {1..360}; do [[ $(stores | grep -c ' Up ') == 3 ]] && break; sleep 0.5; done
    [[ $(stores | grep -c ' Up ') == 3 ]] || { echo "TiKV did not come up; see $STATE/playground.log"; exit 1; }
    # Tres copias de cada dato. Playground lo pone según los TiKV con que
    # arranca (con 1 deja 1 y no lo sube al añadir más): se fija aquí.
    curl -s -X POST "$PD/config/replicate" -d '{"max-replicas":3}' > /dev/null
    for port in $NODE_A $NODE_B; do
      nohup "$SURREAL_BIN" start --username root --password root --bind 127.0.0.1:$port \
            --no-banner --log warn tikv://127.0.0.1:2379 > "$STATE/node-$port.log" 2>&1 &!
      echo $! > "$STATE/node-$port.pid"
    done
    for i in {1..40}; do node_alive $NODE_A && node_alive $NODE_B && break; sleep 0.5; done
    node_alive $NODE_A && node_alive $NODE_B || { echo "SurrealDB nodes did not start; see $STATE/node-*.log"; exit 1; }
    SURREAL_URL=http://127.0.0.1:$NODE_A SURREAL_DB=cluster ./apply.sh > /dev/null
    SURREAL_URL=http://127.0.0.1:$NODE_A SURREAL_DB=cluster ./surql.sh 01_seed.surql > /dev/null
    echo "cluster up: PD 127.0.0.1:2379, 3 TiKV, SurrealDB nodes on :$NODE_A (A) and :$NODE_B (B)"
    echo "schema and seed loaded in dx/cluster through node A"
    echo "remember: ./db/demo/demo.sh cluster-down when you finish"
    ;;
  status)
    pd_alive || { echo "stopped"; exit 0; }
    printf "%-6s %-18s %-13s %7s %7s\n" store address state leaders regions
    stores | while read id addr state lead reg; do
      printf "%-6s %-18s %-13s %7s %7s\n" $id $addr $state $lead $reg
    done
    for port in $NODE_A $NODE_B; do
      node_alive $port && echo "surreal :$port up" || echo "surreal :$port down"
    done
    ;;
  write)
    n=${2:-40}
    for i in {1..$n}; do
      t0=$(now_ms)
      r=$(sql $NODE_A "CREATE beat SET n = $i, at = time::now();" | grep -o '"status":"[A-Z]*"' | head -1)
      t1=$(now_ms)
      r=${${r#*:}//\"/}
      echo "$(date +%T)  write $i through A: ${r:-ERROR} $((t1 - t0)) ms"
      sleep 0.25
    done
    for i in {1..40}; do  # si aún hay elección en curso, reintentar
      c=$(sql $NODE_B 'RETURN count(SELECT id FROM beat);' | grep -o '"result":[0-9]*' | cut -d: -f2)
      [[ -n "$c" ]] && break; sleep 0.5
    done
    echo "node B now sees: ${c:-?} beats in total"
    ;;
  kill)
    read id addr state lead reg <<< "$(stores | grep ' Up ' | sort -k4 -nr | head -1)"
    [[ -n "$addr" ]] || { echo "no TiKV up"; exit 1; }
    pid=$(ps -axo pid=,command= | grep -F "tikv-server --addr=$addr " | grep -F "$DATA/" | grep -v grep | awk '{print $1}')
    [[ -n "$pid" ]] || { echo "TiKV $addr is not ours"; exit 1; }
    ps -o command= -p $pid > "$STATE/killed.args"
    kill -9 $pid
    echo "killed TiKV store $id ($addr, PID $pid), leader of $lead of $reg regions"
    ;;
  revive)
    [[ -s "$STATE/killed.args" ]] || { echo "nothing to revive"; exit 1; }
    nohup ${=$(cat "$STATE/killed.args")} > "$STATE/revived.log" 2>&1 &!
    addr=$(grep -o -- '--addr=[^ ]*' "$STATE/killed.args" | cut -d= -f2)
    for i in {1..60}; do stores | grep -q "$addr Up " && break; sleep 0.5; done
    stores | grep -q "$addr Up " && echo "TiKV $addr is back; it catches up from the other two" \
                                 || echo "TiKV $addr not up yet; check ./db/demo/demo.sh cluster-status"
    rm -f "$STATE/killed.args"
    ;;
  down)
    for port in $NODE_A $NODE_B; do
      pid=$(our_node_pid $port) && kill $pid
    done
    pid=$(cat "$STATE/playground.pid" 2>/dev/null) && kill -INT $pid 2>/dev/null || true
    # Playground no siempre reenvía la parada (p. ej. si un TiKV se quedó sin
    # mayoría): se para cada TiKV y PD nuestro por su PID.
    for i in {1..20}; do [[ -z "$(our_tiup_pids)" ]] && break; sleep 0.5; done
    pids=($(our_tiup_pids)); (( ${#pids} )) && kill $pids 2>/dev/null
    for i in {1..60}; do [[ -z "$(our_tiup_pids)" ]] && break; sleep 0.5; done
    pids=($(our_tiup_pids)); (( ${#pids} )) && kill -9 $pids 2>/dev/null
    pid=$(cat "$STATE/playground.pid" 2>/dev/null) && kill $pid 2>/dev/null || true
    rm -rf "$DATA" "$STATE"
    echo "cluster stopped and its data removed"
    ;;
  *)
    sed -n '2,12p' "${0:A}" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
