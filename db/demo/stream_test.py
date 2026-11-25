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
"""
import os
import subprocess
import sys
import time
from decimal import Decimal

from confluent_kafka.admin import AdminClient, NewTopic

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from stream_common import KAFKA, Surreal  # noqa: E402

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
    admin.create_topics([NewTopic(topic, 3, 1)])[topic].result()

    py = sys.executable
    env = {**os.environ, "SURREAL_DB": name}
    subprocess.run([py, "stream_producer.py", "test", "--topic", topic, "--count", str(M), "--run", mode],
                   cwd=HERE, env=env, check=True, capture_output=True)
    common = ["--topic", topic, "--group", f"g-{topic}", "--mode", mode, "--quiet"]
    crash = subprocess.run([py, "stream_consumer.py", *common, "--crash-after", str(CRASH),
                            "--until-idle", "5"], cwd=HERE, env=env)
    again = subprocess.run([py, "stream_consumer.py", *common, "--until-idle", "5"], cwd=HERE, env=env)
    after, total1, recon = state(db)
    admin.delete_topics([topic])

    applied = after - before
    ok = (applied == M) if EXPECT[mode] == "==" else (applied != M)
    clean = crash.returncode == 3 and again.returncode == 0 and total1 == total0 and recon == []
    print(f"{mode:<13} aplicadas {applied:>3} de {M}  "
          f"(se esperaba {'exactamente' if EXPECT[mode] == '==' else 'un número distinto de'} {M}); "
          f"saldo total {'igual' if total1 == total0 else 'DISTINTO'}, "
          f"reconciliación {'vacía' if recon == [] else 'CON DIFERENCIAS'}, "
          f"caída {'simulada' if crash.returncode == 3 else 'NO OCURRIÓ'}  "
          f"{'ok' if ok and clean else 'FALLO'}")
    if total1 != total0:
        print(f"  saldo total antes {total0}, después {total1}")
    return ok and clean


def main():
    admin = AdminClient({"bootstrap.servers": KAFKA})
    results = [run(mode, admin) for mode in EXPECT]
    print("TODO EN ORDEN" if all(results) else "ALGO FALLA")


if __name__ == "__main__":
    main()
