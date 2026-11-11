#!/usr/bin/env python3
"""Dominican Express desde Python con el SDK oficial (surrealdb 3.0.0).

    uv run --with-requirements db/demo/requirements.txt python db/demo/demo_client.py \
        [--url ws://127.0.0.1:8099/rpc] [--db live]

Requiere el esquema y la semilla cargados en esa base (`domex up`, o
apply.sh + 01_seed.surql). Cada ejecución usa ids nuevos, así que se puede
repetir. La salida va en inglés: es lo que se enseña en clase.

Por qué el SDK aquí y urllib en los tests: los tests no deben depender de
nada que no venga con Python; este script es lo que usaría una aplicación
de verdad (tipos de Python, WebSocket, LIVE).
"""
import argparse
import asyncio
import json
import time

from surrealdb import AsyncSurreal, RecordID, Surreal

ROOT = {"username": "root", "password": "root"}  # solo en local


def title(t):
    print(f"\n== {t} " + "=" * max(0, 60 - len(t)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://127.0.0.1:8099/rpc")
    ap.add_argument("--ns", default="dx")
    ap.add_argument("--db", default="live")
    a = ap.parse_args()
    run = str(int(time.time()))[-8:]  # ids nuevos en cada ejecución
    cust, acc = RecordID("customer", f"py{run}"), RecordID("account", f"py{run}")

    with Surreal(a.url) as db:
        db.signin(ROOT)
        db.use(a.ns, a.db)

        title("1. CREATE: onboard a customer (document + graph edge)")
        db.create(cust, {"name": "Pablo Python", "nif": f"PY{run}"})
        db.create(acc, {"iban": f"ES99{run}{run}{run[:4]}"})
        db.query("RELATE $c->owns->$a SET role = 'titular'", {"c": cust, "a": acc}).execute()
        print("created", cust, "and", acc, "linked by an owns edge")

        title("2. READ: the record, then a graph traversal")
        print(db.select(cust).execute())
        print(db.query("SELECT name, ->owns->account.iban AS ibans FROM ONLY $c", {"c": cust}).first())

        title("3. UPDATE: the schema validates, the app does not have to")
        db.update(cust).merge({"phone": f"+34600{run[-6:]}"})
        print("phone set:", db.select(cust).execute()["phone"])
        try:
            db.update(cust).merge({"phone": "600 12 34 56"})
            print("UNEXPECTED: invalid phone accepted")
        except Exception as e:  # el ASSERT del esquema lo rechaza en el servidor
            print("invalid phone rejected by the database:", str(e).splitlines()[0][:100])

    title("4. A customer session: Ana signs in with record access")
    with Surreal(a.url) as ana:
        ana.signin({"namespace": a.ns, "database": a.db, "access": "banca",
                    "variables": {"email": "ana@dominican.test", "pass": "demo-ana"}})
        print("accounts Ana can see:", ana.query("SELECT VALUE id FROM account").first())
        order = json.dumps({"id": f"py-pay-{run}", "from": "account:ana",
                            "to_iban": "ES2222222222222222222222", "amount": "12.50"}).encode()
        pay = "RETURN api::invoke('/transfers', { method: 'post', body: $b })"
        r1 = ana.query(pay, {"b": order}).first()
        r2 = ana.query(pay, {"b": order}).first()  # la app reintenta: misma orden
        print("pay 12.50 :", r1["status"], r1["body"].decode())
        print("retry same:", r2["status"], r2["body"].decode(), "-> charged once")
        gone = ana.query("DELETE entry WHERE account = account:ana RETURN BEFORE").first()
        print("Ana tries to delete her ledger entries ->", gone)

    with Surreal(a.url) as db:
        db.signin(ROOT)
        db.use(a.ns, a.db)
        n = db.query("SELECT VALUE count() FROM entry WHERE account = account:ana GROUP ALL").first()
        print("checked as root: Ana's entries are all still there:", n[0])

        title("5. DELETE: staff removes the test onboarding, and it is audited")
        db.query("DELETE owns WHERE in = $c; DELETE $a; DELETE $c", {"c": cust, "a": acc}).execute()
        print("customer now:", db.select(cust).execute())
        audit = db.query("SELECT at, action, tbl FROM audit_log WHERE rec = $c ORDER BY at", {"c": cust}).first()
        print("audit trail of", cust, "->", [f"{x['tbl']}:{x['action']}" for x in audit])

    title("6. LIVE: alerts pushed by the database while a ring forms")
    asyncio.run(live_ring(a, run))


async def live_ring(a, run):
    ring = [RecordID("account", f"r{run}{i}") for i in range(3)]
    async with AsyncSurreal(a.url) as watcher:
        await watcher.signin(ROOT)
        await watcher.use(a.ns, a.db)
        live_id = await watcher.live("fraud_alert")
        sub = await watcher.subscribe_live(live_id)
        # Las escrituras van por OTRA conexión (la del LIVE está escuchando).
        async with AsyncSurreal(a.url) as w:
            await w.signin(ROOT)
            await w.use(a.ns, a.db)
            for i, r in enumerate(ring):
                await w.create(r, {"iban": f"ES98{run}{run}{i:04d}"})
                await w.query("RETURN fn::credit($r, 1000dec, 'payroll')", {"r": r})
            for (src, dst), amt in zip(zip(ring, ring[1:] + ring[:1]), (500, 470, 445)):
                await w.query("RETURN fn::transfer($s, $d, $m)", {"s": src, "d": dst, "m": amt})
                print(f"  transfer {src} -> {dst}: {amt}")
            print("  sweep: fn::detect_rings(5)")
            await w.query("RETURN fn::detect_rings(5)")
        seen = 0
        while seen < len(ring):
            try:
                note = await asyncio.wait_for(sub.__anext__(), timeout=10)
            except asyncio.TimeoutError:
                break
            alert = note["result"]
            if alert.get("account") in ring:
                seen += 1
                print(f"  LIVE {note['action']}: {alert['kind']} on {alert['account']} (score {alert['score']})")
        await watcher.kill(live_id)
        frozen = await watcher.query("SELECT VALUE id FROM account WHERE id IN $r AND frozen_at != NONE", {"r": ring}).first()
        print("  frozen by the database itself:", frozen)


if __name__ == "__main__":
    main()
