#!/usr/bin/env python3
"""Publica pagos en el topic `payments`: hace de red de tarjetas, otros bancos
y pasarela de Bizum, que es por donde llegan los pagos que no salen de la app.

    uv run --with confluent-kafka python3 db/demo/stream_producer.py demo
    uv run --with confluent-kafka python3 db/demo/stream_producer.py test --count 60

Cada mensaje:
    clave  = cuenta de origen   → todos los pagos de una cuenta van a la misma
                                  partición y llegan en el orden en que salieron
    valor  = {"id", "from", "to", "amount", "kind"}, con el importe como texto

`demo`: un guion fijo con pagos normales, un anillo de mulas (ana → luis →
marta → ana), una ráfaga de sara, un pago repetido por el emisor y dos
intentos de las cuentas ya congeladas. Va despacio a propósito, para verse en
directo.
`test`: N pagos normales sin anillos (stream_test.py).

Los pagos normales solo salen de jose y sara y nadie les paga a ellos, así que
no pueden cerrar un ciclo por azar: el único anillo es el del guion.
"""
import argparse
import json
import os
import random
import sys
import time

from confluent_kafka import Producer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stream_common import KAFKA, PAYMENTS  # noqa: E402

SENDERS = {"jose": ["sara", "luis", "marta", "ana"], "sara": ["luis", "marta", "ana"]}


def background(rng):
    src = rng.choice(list(SENDERS))
    return src, rng.choice(SENDERS[src]), f"{rng.randint(1, 20)}.{rng.randint(0, 99):02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", choices=["demo", "test"])
    ap.add_argument("--topic", default=PAYMENTS)
    ap.add_argument("--count", type=int, default=60, help="test: número de pagos")
    ap.add_argument("--run", default=str(int(time.time())), help="prefijo de los ids")
    ap.add_argument("--pause", type=float, default=0.5, help="demo: segundos entre mensajes")
    a = ap.parse_args()

    # acks=all + idempotencia del productor: si el broker no confirma y el
    # productor reintenta, el broker descarta la copia. Eso cubre el tramo
    # productor → Kafka. El tramo Kafka → SurrealDB lo cubre fn::stream_apply.
    p = Producer({"bootstrap.servers": KAFKA, "acks": "all", "enable.idempotence": True})
    rng = random.Random(7)
    n = 0

    def send(src, dst, amount, pause=0.0, msg_id=None, note=""):
        nonlocal n
        if msg_id is None:
            n += 1
            msg_id = f"{a.run}-{n:04d}"
        body = {"id": msg_id, "from": src, "to": dst, "amount": amount, "kind": "transfer"}
        p.produce(a.topic, key=src, value=json.dumps(body))
        p.poll(0)
        if a.scenario == "demo":
            print(f"sent  {msg_id}  {src:>5} -> {dst:<5} {amount:>8}  {note}", flush=True)
            p.flush()
            time.sleep(pause)
        return msg_id

    if a.scenario == "test":
        for _ in range(a.count):
            send(*background(rng))
        p.flush()
        print(f"{a.count} pagos publicados en {a.topic}")
        return

    # Guion fijo. La alerta de ráfaga salta con 5 cargos de una cuenta en 5
    # minutos (04_events): jose se queda en 3 y sara llega a 5 dentro de la ráfaga.
    for src, dst, amount in [("jose", "sara", "18.12"), ("sara", "ana", "12.64"),
                             ("jose", "luis", "9.55")]:
        send(src, dst, amount, a.pause)
    send("ana", "luis", "900.00", a.pause, note="ring 1/3")
    send("luis", "marta", "880.00", a.pause, note="ring 2/3")
    send("marta", "ana", "860.00", a.pause, note="ring 3/3")
    send("jose", "ana", "19.73", a.pause)
    send("sara", "marta", "7.30", a.pause * 4)
    first = None
    for i in range(5):
        mid = send("sara", "luis", f"{40 + i}.00", 0.3, note="burst")
        first = first or mid
    send("sara", "luis", "40.00", a.pause, msg_id=first, note="same id again (sender retried)")
    send("ana", "jose", "50.00", a.pause, note="from a ring account")
    send("luis", "jose", "40.00", a.pause, note="from a ring account")
    p.flush()
    print(f"done: {n} payments and 1 repeated message on {a.topic}", flush=True)


if __name__ == "__main__":
    main()
