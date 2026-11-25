#!/usr/bin/env python3
"""Lleva las alertas de fraude de SurrealDB al topic `fraud-alerts`.

    uv run --with confluent-kafka --with websockets python3 db/demo/alert_bridge.py

Por qué existe: un LIVE SELECT solo ve los cambios que pasan por SU nodo
(live_listener.py lo explica). En el clúster, un panel conectado al nodo A no
se entera de una alerta creada en el nodo B. El puente abre un LIVE SELECT en
CADA nodo (SURREAL_WS, separados por comas) y publica todo en un solo topic:
cualquier panel lee de Kafka y lo ve todo, venga de donde venga.

Un LIVE SELECT no guarda nada para quien no estaba escuchando: si el puente se
cae, las alertas de mientras no llegarían nunca. Por eso, al arrancar, el
puente abre primero el LIVE SELECT y DESPUÉS publica las alertas que ya están
guardadas en la tabla. En ese orden no queda hueco; a cambio, una alerta puede
publicarse dos veces, y el panel las reconoce por su id (al menos una vez,
como el resto de Kafka).

Clave = cuenta de la alerta: las de una cuenta llegan en orden.
"""
import asyncio
import json
import os
import sys

import websockets
from confluent_kafka import Producer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stream_common import ALERTS, DB, KAFKA, NS  # noqa: E402

NODES = os.environ.get("SURREAL_WS", "ws://127.0.0.1:8099/rpc").split(",")
USER = os.environ.get("SURREAL_USER", "root")
PASS = os.environ.get("SURREAL_PASS", "root")


def publish(producer, alert, how):
    key = str(alert.get("account") or alert.get("card") or alert.get("id"))
    producer.produce(ALERTS, key=key, value=json.dumps(alert, default=str))
    producer.poll(0)
    print(f"  -> {alert.get('kind'):<14} {key}{how}", flush=True)


async def bridge(url, producer):
    async with websockets.connect(url, subprotocols=["json"]) as ws:
        for i, (method, params) in enumerate([
                ("signin", [{"user": USER, "pass": PASS}]),
                ("use", [NS, DB]),
                ("query", ["LIVE SELECT * FROM fraud_alert;"]),
                ("query", ["SELECT * FROM fraud_alert ORDER BY at;"])]):
            await ws.send(json.dumps({"id": i + 1, "method": method, "params": params}))
        print(f"bridging {url} {NS}/{DB} fraud_alert -> {ALERTS}", flush=True)
        async for raw in ws:
            msg = json.loads(raw)
            res = msg.get("result")
            if msg.get("id") == 4:       # el relleno: lo que ya estaba guardado
                for alert in res[0]["result"]:
                    publish(producer, alert, "   (already stored)")
                continue
            # Solo las notificaciones en vivo traen 'action'. Solo CREATE: un
            # DELETE al reiniciar la demo no es una alerta nueva.
            if not isinstance(res, dict) or res.get("action") != "CREATE":
                continue
            publish(producer, res["result"], "")


async def main():
    p = Producer({"bootstrap.servers": KAFKA, "acks": "all", "enable.idempotence": True,
                  "linger.ms": 0})
    try:
        await asyncio.gather(*(bridge(u, p) for u in NODES))
    finally:
        p.flush(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
