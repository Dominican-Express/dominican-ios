#!/usr/bin/env python3
"""Generador de volumen con fraude plantado, para medir los detectores.

Crea un banco con vida normal y, encima, fraude conocido. Escribe la VERDAD
(qué se plantó) en un JSON para que bench.py pueda medir, por detector, no solo
cuánto tarda sino cuánto acierta: lo plantado que encuentra y lo que marca sin
haberse plantado.

Vida normal (lo que un detector NO debería marcar):
  - nómina mensual; transferencias a 1-3 contactos frecuentes, y el 40 % de
    esas relaciones son de ida y vuelta (amigos que se devuelven dinero);
  - pagos con tarjeta en su ciudad, separados por horas, y algún viaje en tren;
  - un 10 % de cuentas conjuntas; un 6 % de clientes en familias de 2 o 3 que
    comparten una tablet.
Fraude plantado (lo que SÍ debería marcar):
  - anillos de mulas de 3 a 5 cuentas: el dinero da la vuelta en horas y cada
    salto se queda una comisión del 1-5 %;
  - dispositivos usados por 5 clientes sin relación;
  - estructuración: 8 envíos de 2.850-2.990 € en las últimas 24 h;
  - viaje imposible: Madrid y, 10 minutos después, Nueva York;
  - ráfagas: 6 cargos de tarjeta en 4 minutos.

Todo pasa por las funciones del esquema (fn::transfer, fn::credit,
fn::charge_card), así que los eventos en línea se ejecutan como en producción.
Reproducible: la misma semilla da el mismo banco.

    python3 db/demo/gen_volume.py --customers 300 --days 60
"""
import argparse
import json
import random
import time
from datetime import datetime, timedelta, timezone

from session import root_last

CITIES = {"madrid": (-3.7038, 40.4168), "barcelona": (2.1734, 41.3851),
          "valencia": (-0.3763, 39.4699), "sevilla": (-5.9845, 37.3891)}
NYC = (-74.0060, 40.7128)


def ts(dt):
    return "d'" + dt.strftime("%Y-%m-%dT%H:%M:%SZ") + "'"


def money(x):
    return f"{x:.2f}dec"


def run_batches(stmts, size, label):
    """Ejecuta sentencias en lotes. Cada sentencia es su propia transacción:
    si una falla (p. ej. saldo insuficiente), las demás siguen."""
    errors = 0
    t0 = time.time()
    for i in range(0, len(stmts), size):
        res = root_last_all("\n".join(stmts[i:i + size]))
        errors += sum(1 for s in res if s.get("status") != "OK")
    dt = time.time() - t0
    print(f"  {label:<22} {len(stmts):>6} operaciones en {dt:6.1f} s "
          f"({len(stmts) / dt if dt else 0:7.0f}/s), {errors} rechazadas")
    return dt, errors


def root_last_all(sql):
    """Como root_last pero devuelve el estado de TODAS las sentencias."""
    import base64
    import os
    import urllib.request
    from session import URL, NS, DB
    cred = base64.b64encode(f"{os.environ.get('SURREAL_USER', 'root')}:"
                            f"{os.environ.get('SURREAL_PASS', 'root')}".encode()).decode()
    req = urllib.request.Request(URL + "/sql", data=sql.encode(), method="POST",
                                 headers={"Accept": "application/json", "Authorization": f"Basic {cred}",
                                          "surreal-ns": NS, "surreal-db": DB})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--customers", type=int, default=300)
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--truth", default="/tmp/dx_truth.json")
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    n = a.customers
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now - timedelta(days=a.days)
    truth = {"rings": [], "shared_devices": [], "structuring": [], "impossible_travel": [],
             "velocity": [], "legit_households_of_3": [], "params": vars(a)}

    print(f"generando un banco de {n} clientes y {a.days} días (semilla {a.seed})")
    root_last_all("DELETE fraud_alert; DELETE card_payment; DELETE transfer; DELETE uses; DELETE owns; "
                  "DELETE favorite; DELETE entry; DELETE txn; DELETE app_user; DELETE payment_order; "
                  "DELETE notification; DELETE card; DELETE device; DELETE account; DELETE customer;"
                  "CREATE account:ext SET iban = 'ES0000000000000000000000', kind = 'external';")

    city = {i: rnd.choices(list(CITIES), weights=[50, 25, 15, 10])[0] for i in range(n)}
    setup = []
    for i in range(n):
        setup.append(f"CREATE customer:c{i} SET name = 'Cliente {i}', nif = '{i:08d}X', "
                     f"phone = '+346{i:08d}', bizum_account = account:c{i};")
        setup.append(f"CREATE account:c{i} SET iban = 'ES{i + 1:022d}';  # +1: la 0 es de account:ext")
        setup.append(f"RELATE customer:c{i}->owns->account:c{i} SET role = 'titular';")
        setup.append(f"CREATE card:c{i} SET account = account:c{i}, holder = customer:c{i}, "
                     f"pan_last4 = '{i % 10000:04d}';")
        setup.append(f"CREATE device:d{i} SET fingerprint = 'dev-{i}';")
        setup.append(f"RELATE customer:c{i}->uses->device:d{i};")
    people = list(range(n))
    rnd.shuffle(people)
    # cuentas conjuntas: el 10 % se hace cotitular de la cuenta de otro
    for i in people[: n // 10]:
        setup.append(f"RELATE customer:c{i}->owns->account:c{rnd.randrange(n)} SET role = 'cotitular';")
    # familias que comparten tablet: legítimo, y con 3 miembros cruza el umbral
    fam_pool = people[n // 10: n // 10 + int(n * 0.06)]
    k = 0
    while k + 1 < len(fam_pool):
        size = 3 if rnd.random() < 0.4 and k + 2 < len(fam_pool) else 2
        members = fam_pool[k:k + size]
        dev = f"device:fam{k}"
        setup.append(f"CREATE {dev} SET fingerprint = 'tablet-{k}';")
        for m in members:
            setup.append(f"RELATE customer:c{m}->uses->{dev};")
        # Supuesto: un hogar que comparte aparato comparte también una cuenta.
        # Es el mismo supuesto que declara fn::detect_shared_devices.
        for m in members[1:]:
            setup.append(f"RELATE customer:c{m}->owns->account:c{members[0]} SET role = 'cotitular';")
        if size == 3:
            truth["legit_households_of_3"].append(dev)
        k += size
    run_batches(setup, 600, "clientes y cuentas")

    # contactos frecuentes, con relaciones de ida y vuelta
    contacts = {i: set() for i in range(n)}
    for i in range(n):
        for _ in range(rnd.randint(1, 3)):
            j = rnd.randrange(n)
            if j != i:
                contacts[i].add(j)
                if rnd.random() < 0.4:
                    contacts[j].add(i)

    ops = []   # (fecha, sentencia)
    months = max(1, a.days // 30 + 1)
    for i in range(n):
        for mth in range(months):
            d = start + timedelta(days=30 * mth + rnd.randint(0, 4), hours=rnd.randint(6, 10))
            if d < now - timedelta(days=2):
                ops.append((d, f"RETURN fn::credit(account:c{i}, {money(rnd.uniform(1200, 3200))}, 'payroll', {ts(d)});"))
        for j in contacts[i]:
            for _ in range(rnd.randint(1, 2 * months)):
                d = start + timedelta(minutes=rnd.randint(60 * 24 * 3, a.days * 24 * 60 - 60 * 24 * 3))
                ops.append((d, f"RETURN fn::transfer(account:c{i}, account:c{j}, {money(rnd.uniform(5, 150))}, "
                               f"'transfer', NONE, {ts(d)});"))
        # pagos con tarjeta: en su ciudad, separados por horas; a veces un viaje en tren
        d = start + timedelta(days=3, hours=rnd.randint(0, 12))
        here = city[i]
        while d < now - timedelta(days=2):
            if rnd.random() < 0.05:
                here = rnd.choice(list(CITIES))
                d += timedelta(hours=8)          # un viaje real lleva horas
            lon, lat = CITIES[here]
            ops.append((d, f"RETURN fn::charge_card(card:c{i}, {money(rnd.uniform(3, 120))}, 'Comercio', "
                           f"({lon + rnd.uniform(-0.05, 0.05):.4f}, {lat + rnd.uniform(-0.05, 0.05):.4f}), {ts(d)});"))
            d += timedelta(hours=rnd.randint(4, 120))
    ops.sort(key=lambda x: x[0])
    t_money, _ = run_batches([s for _, s in ops], 400, "vida normal")

    # ---------------------------------------------------------------- fraude plantado
    planted = []
    mule_pool = people[n // 10 + int(n * 0.06):]
    rnd.shuffle(mule_pool)
    p = 0
    for r in range(max(3, n // 50)):
        size = rnd.randint(3, 5)
        ring = mule_pool[p:p + size]
        p += size
        truth["rings"].append([f"account:c{x}" for x in ring])
        amount = rnd.uniform(800, 3000)
        d = now - timedelta(hours=rnd.randint(30, 60))
        for idx, x in enumerate(ring):
            y = ring[(idx + 1) % len(ring)]
            planted.append(f"RETURN fn::credit(account:c{x}, {money(amount * 1.2)}, 'transfer', {ts(d - timedelta(hours=2))});")
            planted.append(f"RETURN fn::transfer(account:c{x}, account:c{y}, {money(amount)}, 'transfer', NONE, {ts(d)});")
            amount *= rnd.uniform(0.95, 0.99)
            d += timedelta(minutes=rnd.randint(20, 90))
    for s in range(max(2, n // 100)):
        dev = f"device:mule{s}"
        planted.append(f"CREATE {dev} SET fingerprint = 'burner-{s}';")
        for x in mule_pool[p:p + 5]:
            planted.append(f"RELATE customer:c{x}->uses->{dev};")
        p += 5
        truth["shared_devices"].append(dev)
    for s in range(max(2, n // 100)):
        x = mule_pool[p]
        p += 1
        truth["structuring"].append(f"account:c{x}")
        planted.append(f"RETURN fn::credit(account:c{x}, 30000dec, 'payroll', {ts(now - timedelta(hours=30))});")
        for h in range(8):
            planted.append(f"RETURN fn::debit_at(account:c{x}, {money(rnd.uniform(2850, 2990))}, "
                           f"{ts(now - timedelta(hours=h + 1))});")
    for s in range(max(2, n // 100)):
        x = mule_pool[p]
        p += 1
        truth["impossible_travel"].append(f"account:c{x}")
        lon, lat = CITIES["madrid"]
        planted.append(f"RETURN fn::credit(account:c{x}, 5000dec, 'payroll', {ts(now - timedelta(hours=3))});")
        planted.append(f"RETURN fn::charge_card(card:c{x}, 30dec, 'Café', ({lon}, {lat}), {ts(now - timedelta(minutes=40))});")
        planted.append(f"RETURN fn::charge_card(card:c{x}, 1800dec, 'Electronics', ({NYC[0]}, {NYC[1]}), {ts(now - timedelta(minutes=30))});")
    t_plant, _ = run_batches(planted, 400, "fraude plantado")

    # ráfagas al final y con la hora real: el detector mira los últimos 5 minutos
    burst = []
    for s in range(max(2, n // 100)):
        x = mule_pool[p]
        p += 1
        truth["velocity"].append(f"account:c{x}")
        burst.append(f"RETURN fn::credit(account:c{x}, 2000dec, 'payroll');")
        lon, lat = CITIES[city[x]]
        for _ in range(6):
            burst.append(f"RETURN fn::charge_card(card:c{x}, {money(rnd.uniform(20, 60))}, 'Tienda', ({lon}, {lat}));")
    run_batches(burst, 400, "ráfagas")

    stats = root_last("RETURN { entries: count(SELECT id FROM entry), transfers: count(SELECT id FROM transfer), "
                      "card_payments: count(SELECT id FROM card_payment), notifications: count(SELECT id FROM notification) };")
    truth["stats"] = stats
    truth["money_ops_seconds"] = t_money
    truth["money_ops"] = len(ops)
    with open(a.truth, "w") as f:
        json.dump(truth, f, indent=1)
    print(f"  base: {stats}")
    print(f"  verdad en {a.truth}")


if __name__ == "__main__":
    main()
