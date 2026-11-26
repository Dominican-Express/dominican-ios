#!/usr/bin/env python3
"""Consume el topic `payments` y aplica cada pago en SurrealDB.

    uv run --with confluent-kafka python3 db/demo/stream_consumer.py [--sweep 2]

Orden de cada mensaje (modo `safe`, el bueno):
    1. fn::stream_apply en SurrealDB: pago + apunte del id, en una transacción
    2. solo con el OK, confirmar el offset en Kafka
Si el proceso muere entre 1 y 2, Kafka vuelve a entregar el mensaje y
fn::stream_apply lo reconoce por su id: no se cobra dos veces.

Dos modos MALOS, para que la prueba (stream_test.py) tenga algo que detectar:
    no-dedup      paga con fn::transfer sin apuntar el id → un fallo entre 1 y 2
                  cobra el pago dos veces
    commit-first  confirma el offset ANTES de pagar → un fallo entre medias
                  pierde el pago
--crash-after N simula ese fallo: el proceso muere en el mensaje N, en el
peor momento de cada modo.

Un mensaje que no se puede leer (no es JSON, le falta un campo, importe mal
escrito) va al topic `payments-dlq` con el motivo en una cabecera, se confirma
y se sigue: sin eso, al arrancar otra vez Kafka lo devolvería y el consumidor
se pararía en él para siempre, con toda la partición detrás.

--sweep S lanza el barrido de anillos (fn::detect_rings) cada S segundos. Es
idempotente (INSERT IGNORE): repetirlo no duplica alertas. Los detectores en
línea (ráfaga, viaje imposible) ya saltan dentro de cada pago.

Grupo de consumidores `ledger`: si arrancas dos, Kafka les reparte las
particiones. Como la clave es la cuenta de origen, los pagos de una misma
cuenta los procesa siempre el mismo consumidor y en orden.
"""
import argparse
import json
import os
import sys
import time

from confluent_kafka import Consumer, KafkaError, Producer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stream_common import DLQ, KAFKA, PAYMENTS, Surreal, acc, money, parse  # noqa: E402


def apply(db, mode, m, source):
    """Devuelve (estado, motivo, repetido)."""
    if mode == "no-dedup":
        try:
            db.last(f"RETURN fn::transfer({acc(m['from'])}, {acc(m['to'])}, "
                    f"{money(m['amount'])}, {json.dumps(m['kind'])});")
            return "done", None, False
        except RuntimeError as e:
            return "rejected", str(e)[:60], False
    r = db.last(f"RETURN fn::stream_apply({json.dumps(m['id'])}, {acc(m['from'])}, "
                f"{acc(m['to'])}, {money(m['amount'])}, {json.dumps(m['kind'])}, {json.dumps(source)});")
    return r["status"], r.get("reason"), r["duplicate"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default=PAYMENTS)
    ap.add_argument("--group", default="ledger")
    ap.add_argument("--mode", choices=["safe", "no-dedup", "commit-first"], default="safe")
    ap.add_argument("--crash-after", type=int, default=0)
    ap.add_argument("--until-idle", type=float, default=0,
                    help="salir tras S segundos sin mensajes (0: no salir nunca)")
    ap.add_argument("--sweep", type=float, default=0)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    db = Surreal()
    c = Consumer({"bootstrap.servers": KAFKA, "group.id": a.group,
                  # el offset se confirma a mano, después de pagar
                  "enable.auto.commit": False,
                  # un grupo nuevo empieza por el principio del topic
                  "auto.offset.reset": "earliest",
                  # si un consumidor muere sin despedirse, el grupo tarda esto
                  # en darlo por muerto y repartir sus particiones (45 s por
                  # defecto; 6 s es el mínimo del broker)
                  "session.timeout.ms": 6000, "heartbeat.interval.ms": 2000})
    # El reloj de inactividad empieza cuando el grupo nos da particiones. Tras
    # una caída, el grupo espera a dar por muerto al consumidor anterior
    # (session.timeout.ms) antes de repartir: hasta entonces no llega nada y
    # no por eso el topic está vacío.
    assigned = []
    c.subscribe([a.topic], on_assign=lambda _c, parts: assigned.append(time.time()))
    dlq = Producer({"bootstrap.servers": KAFKA, "acks": "all", "enable.idempotence": True})
    log = (lambda *_: None) if a.quiet else (lambda s: print(s, flush=True))
    log(f"consuming {a.topic} as group {a.group} ({a.mode}); Ctrl-C to stop")

    seen = rings = 0
    idle_since = last_sweep = time.time()
    try:
        while True:
            msg = c.poll(0.5)
            now = time.time()
            if a.sweep and now - last_sweep >= a.sweep:
                n = db.last("RETURN fn::detect_rings(5);")
                last_sweep = now
                if n != rings:
                    log(f"      ring sweep: {n} accounts in rings")
                    rings = n
            if msg is None:
                if a.until_idle and assigned and now - max(idle_since, assigned[-1]) >= a.until_idle:
                    break
                continue
            if msg.error():
                # Solo los errores fatales paran el consumidor; los demás
                # (broker caído un momento, topic que aún no existe) los
                # reintenta la propia librería.
                if msg.error().fatal():
                    raise RuntimeError(msg.error())
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    log(f"      kafka: {msg.error().str()}")
                continue
            idle_since = now
            seen += 1
            source = f"{msg.topic()}/{msg.partition()}@{msg.offset()}"
            try:
                m = parse(msg.value())
            except ValueError as e:
                dlq.produce(DLQ, key=msg.key(), value=msg.value(),
                            headers={"reason": str(e), "source": source})
                # Sin la copia en la cola no se confirma: el mensaje se perdería.
                if dlq.flush(10):
                    raise RuntimeError(f"could not write to {DLQ}")
                c.commit(message=msg, asynchronous=False)
                log(f"p{msg.partition()}@{msg.offset():<4} malformed ({e}), sent to {DLQ}")
                continue

            if a.mode == "commit-first":
                c.commit(message=msg, asynchronous=False)
                if seen == a.crash_after:
                    os._exit(3)          # confirmado y sin pagar: se pierde
            status, reason, dup = apply(db, a.mode, m, source)
            if a.mode != "commit-first":
                if seen == a.crash_after:
                    os._exit(3)          # pagado y sin confirmar: vuelve a llegar
                c.commit(message=msg, asynchronous=False)

            what = "duplicate, not charged again" if dup else status + (f" ({reason})" if reason else "")
            log(f"p{msg.partition()}@{msg.offset():<4} {m['id']:>16}  {m['from']:>5} -> {m['to']:<5} "
                f"{m['amount']:>8}  {what}")
    except KeyboardInterrupt:
        pass
    finally:
        c.close()
    log(f"stopped after {seen} messages")


if __name__ == "__main__":
    main()
