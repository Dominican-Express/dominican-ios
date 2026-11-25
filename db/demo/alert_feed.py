#!/usr/bin/env python3
"""Un panel de fraude que lee las alertas de Kafka, no de SurrealDB.

    uv run --with confluent-kafka python3 db/demo/alert_feed.py [--group analyst-1]

Cada panel usa SU PROPIO grupo de consumidores, así que cada uno recibe todas
las alertas (difusión). Dos procesos con el MISMO grupo se las repartirían
(reparto de carga): es la diferencia entre un panel por analista y un equipo
de trabajadores que se reparte una cola.

Un panel nuevo empieza por el principio del topic: ve también las alertas de
antes de arrancar. Kafka las guarda aunque ya se hayan leído.
"""
import argparse
import json
import os
import sys
import uuid

from confluent_kafka import Consumer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stream_common import ALERTS, KAFKA  # noqa: E402

LABELS = {"mule_ring": "money-mule ring", "possible_ring": "possible ring",
          "velocity": "burst of charges", "impossible_travel": "impossible travel",
          "shared_device": "shared device", "structuring": "structuring",
          "low_balance": "low balance"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default=f"dashboard-{uuid.uuid4().hex[:6]}")
    a = ap.parse_args()
    c = Consumer({"bootstrap.servers": KAFKA, "group.id": a.group,
                  "auto.offset.reset": "earliest"})
    c.subscribe([ALERTS])
    print(f"fraud dashboard reading {ALERTS} as group {a.group}; Ctrl-C to stop", flush=True)
    shown = set()
    try:
        while True:
            msg = c.poll(0.5)
            if msg is None or msg.error():
                continue
            alert = json.loads(msg.value())
            if alert["id"] in shown:   # el puente pudo publicarla dos veces
                continue
            shown.add(alert["id"])
            kind = alert.get("kind", "?")
            print(f"[{alert.get('score', 0):>4.2f}]  {LABELS.get(kind, kind):<18} {msg.key().decode()}"
                  f"   (partition {msg.partition()}, offset {msg.offset()})", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        c.close()


if __name__ == "__main__":
    main()
