#!/usr/bin/env python3
"""Prueba de la entrada por Kafka: el consumidor muere a mitad y al volver no
hay ni pagos repetidos ni pagos perdidos. La lanza stream_test.sh.

Para cada modo del consumidor (stream_consumer.py):
  1. base nueva con la semilla y topic nuevo de 3 particiones
  2. 60 pagos publicados
  3. consumidor con --crash-after 25: muere en el peor momento de su modo
  4. consumidor otra vez, hasta vaciar el topic
  5. se cuentan las transferencias aplicadas, el saldo total y la reconciliación

Lo correcto es exactamente 60. El modo bueno debe dar 60; los dos malos deben
salirse (61 el que no apunta el id, 59 el que confirma antes de pagar). Si un
modo malo diera 60, la prueba no estaría viendo el fallo que dice vigilar.

Delante de los 60 van 2 mensajes rotos (no JSON; importe «1.»): deben acabar
en la cola de mensajes muertos sin parar el consumidor.

Al final, sin Kafka, sobre la base del modo bueno: 8 copias del mismo mensaje
a la vez deben cobrarse una sola vez, y un mensaje distinto con un id ya
usado debe rechazarse (id_reused).
"""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from confluent_kafka import Consumer, Producer
from confluent_kafka.admin import AdminClient, NewTopic

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from stream_common import KAFKA, Surreal, acc  # noqa: E402

M, CRASH = 60, 25
EXPECT = {"safe": "==", "no-dedup": "!=", "commit-first": "!="}


def fresh_db(name):
    env = {**os.environ, "SURREAL_DB": name}
    subprocess.run(["./apply.sh"], cwd=HERE, env=env, check=True, capture_output=True)
    subprocess.run(["./surql.sh", "01_seed.surql"], cwd=HERE, env=env, check=True, capture_output=True)


def state(db):
    return (db.last("RETURN count(SELECT id FROM txn WHERE kind = 'transfer');"),
            # el decimal llega como texto, y '59625.6' y '59625.60' son la misma cantidad
            Decimal(str(db.last("RETURN math::sum(SELECT VALUE balance FROM account WHERE kind = 'customer');"))),
            db.last("RETURN fn::reconcile();"))


def run(mode, admin):
    name = f"t_stream_{mode.replace('-', '_')}"
    topic = f"t-payments-{mode}-{int(time.time())}"
    fresh_db(name)
    db = Surreal(name)
    before, total0, _ = state(db)
    dlq = f"t-dlq-{mode}-{int(time.time())}"
    for t in (topic, dlq):
        admin.create_topics([NewTopic(t, 3, 1)])[t].result()
    bad = Producer({"bootstrap.servers": KAFKA})
    bad.produce(topic, key="jose", value=b"not json")
    bad.produce(topic, key="jose", value=json.dumps(
        {"id": "bad-amount", "from": "jose", "to": "sara", "amount": "1."}))
    bad.flush()

    py = sys.executable
    env = {**os.environ, "SURREAL_DB": name, "KAFKA_DLQ": dlq}
    subprocess.run([py, "stream_producer.py", "test", "--topic", topic, "--count", str(M), "--run", mode],
                   cwd=HERE, env=env, check=True, capture_output=True)
    common = ["--topic", topic, "--group", f"g-{topic}", "--mode", mode, "--quiet"]
    crash = subprocess.run([py, "stream_consumer.py", *common, "--crash-after", str(CRASH),
                            "--until-idle", "5"], cwd=HERE, env=env)
    again = subprocess.run([py, "stream_consumer.py", *common, "--until-idle", "5"], cwd=HERE, env=env)
    after, total1, recon = state(db)
    dead = count_messages(dlq)
    admin.delete_topics([topic, dlq])

    applied = after - before
    ok = (applied == M) if EXPECT[mode] == "==" else (applied != M)
    clean = (crash.returncode == 3 and again.returncode == 0 and total1 == total0
             and recon == [] and dead == 2)
    print(f"{mode:<13} aplicadas {applied:>3} de {M}  "
          f"(se esperaba {'exactamente' if EXPECT[mode] == '==' else 'un número distinto de'} {M}); "
          f"saldo total {'igual' if total1 == total0 else 'DISTINTO'}, "
          f"reconciliación {'vacía' if recon == [] else 'CON DIFERENCIAS'}, "
          f"caída {'simulada' if crash.returncode == 3 else 'NO OCURRIÓ'}, "
          f"{dead} de 2 rotos en la cola  "
          f"{'ok' if ok and clean else 'FALLO'}")
    if total1 != total0:
        print(f"  saldo total antes {total0}, después {total1}")
    return ok and clean


def count_messages(topic):
    """Cuántos mensajes hay en un topic, leyéndolo entero con un grupo nuevo."""
    c = Consumer({"bootstrap.servers": KAFKA, "group.id": f"count-{topic}",
                  "auto.offset.reset": "earliest", "enable.auto.commit": False})
    c.subscribe([topic])
    n, quiet = 0, 0
    while quiet < 6:
        msg = c.poll(0.5)
        if msg is None or msg.error():
            quiet += 1
            continue
        n, quiet = n + 1, 0
    c.close()
    return n


def concurrent_copies():
    """8 copias del mismo mensaje a la vez, directamente contra SurrealDB."""
    name = "t_stream_safe"
    db = Surreal(name)
    before = db.last("RETURN count(SELECT id FROM txn WHERE kind = 'transfer');")
    call = (f"RETURN fn::stream_apply('same-copy', {acc('jose')}, {acc('sara')}, "
            f"5.00dec, 'transfer', 'test');")
    with ThreadPoolExecutor(8) as pool:
        replies = list(pool.map(lambda _: Surreal(name).last(call), range(8)))
    paid = db.last("RETURN count(SELECT id FROM txn WHERE kind = 'transfer');") - before
    firsts = sum(1 for r in replies if not r["duplicate"])
    reused = db.last(f"RETURN fn::stream_apply('same-copy', {acc('jose')}, {acc('sara')}, "
                     f"7.00dec, 'transfer', 'test');")
    kind_only = db.last(f"RETURN fn::stream_apply('same-copy', {acc('jose')}, {acc('sara')}, "
                        f"5.00dec, 'bizum', 'test');")
    card = db.last(f"RETURN fn::stream_apply('as-card', {acc('jose')}, {acc('sara')}, "
                   f"5.00dec, 'card', 'test');")
    ok = (paid == 1 and firsts == 1 and reused["reason"] == "id_reused"
          and kind_only["reason"] == "id_reused" and card["reason"] == "invalid_kind")
    print(f"copias a la vez cobradas {paid} vez de 8 llamadas; id reutilizado con otro importe: "
          f"{reused['reason']}, solo con otro tipo: {kind_only['reason']}; tipo `card` desde fuera: "
          f"{card['reason']}  {'ok' if ok else 'FALLO'}")
    return ok


def main():
    admin = AdminClient({"bootstrap.servers": KAFKA})
    results = [run(mode, admin) for mode in EXPECT] + [concurrent_copies()]
    print("TODO EN ORDEN" if all(results) else "ALGO FALLA")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
