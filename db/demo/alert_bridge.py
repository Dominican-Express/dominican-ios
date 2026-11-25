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


def live_alert(msg):
    """La alerta nueva si `msg` es una notificación en vivo de CREATE. Solo
    CREATE: un DELETE al reiniciar la demo no es una alerta nueva."""
    res = msg.get("result")
    if msg.get("id") is None and isinstance(res, dict) and res.get("action") == "CREATE":
        return res["result"]
    return None


async def bridge(url, producer):
    async with websockets.connect(url, subprotocols=["json"]) as ws:
        counter = 0

        async def call(method, params):
            """Una petición y su respuesta, en orden: SurrealDB puede atender a
            la vez varias peticiones del mismo WebSocket, y sin esperar, el
            relleno podría ejecutarse antes de que el LIVE SELECT exista. Lo que
            llegue en vivo mientras tanto se publica igual."""
            nonlocal counter
            counter += 1
            await ws.send(json.dumps({"id": counter, "method": method, "params": params}))
            async for raw in ws:
                msg = json.loads(raw)
                if (alert := live_alert(msg)) is not None:
                    publish(producer, alert, "")
                elif msg.get("id") == counter:
                    if "error" in msg:
                        raise RuntimeError(f"{method}: {msg['error']}")
                    res = msg.get("result")
                    if method == "query" and res[0]["status"] != "OK":
                        raise RuntimeError(f"{params[0]} {res[0]['result']}")
                    return res
            raise RuntimeError("connection closed")

        await call("signin", [{"user": USER, "pass": PASS}])
        await call("use", [NS, DB])
        await call("query", ["LIVE SELECT * FROM fraud_alert;"])
        print(f"bridging {url} {NS}/{DB} fraud_alert -> {ALERTS}", flush=True)
        # El relleno, DESPUÉS de que el LIVE SELECT exista: lo ya guardado.
        for alert in (await call("query", ["SELECT * FROM fraud_alert ORDER BY at;"]))[0]["result"]:
            publish(producer, alert, "   (already stored)")
        async for raw in ws:
            if (alert := live_alert(json.loads(raw))) is not None:
                publish(producer, alert, "")


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
