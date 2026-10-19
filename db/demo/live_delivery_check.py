"""Mide si LIVE SELECT entrega cada notificación a su suscriptor.

Respalda la decisión de 08_cards.surql: la notificación es una fila y LIVE solo
la adelanta. Medido en 3.2.4: solo 30/30; dos clientes 23/30 y 24/30; dos root 28/30.
Requiere la tabla notification (08_cards) y la semilla.

    uv run --with websockets python3 db/demo/live_delivery_check.py dos 30

uso: live_delivery_check.py <modo> <rondas>
  modo = solo      -> marta sola, usuario de registro
         dos       -> marta y ana a la vez, usuarios de registro
         root      -> dos suscriptores root (sin permisos)
"""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import websockets
from session import root_last

NS, DB = "dx", os.environ.get("SURREAL_DB", "bank")


async def sub(creds, tag, got, ready):
    async with websockets.connect("ws://127.0.0.1:8099/rpc", subprotocols=["json"]) as ws:
        await ws.send(json.dumps({"id": 1, "method": "signin", "params": [creds]}))
        await ws.recv()
        if "ac" not in creds:
            await ws.send(json.dumps({"id": 9, "method": "use", "params": [NS, DB]}))
            await ws.recv()
        await ws.send(json.dumps({"id": 2, "method": "query",
                                  "params": [f"LIVE SELECT * FROM notification WHERE concept = '{tag}';"]}))
        await ws.recv()
        ready.set()
        try:
            while True:
                m = json.loads(await asyncio.wait_for(ws.recv(), 1.5))
                r = m.get("result")
                if isinstance(r, dict) and r.get("action") == "CREATE":
                    got.append(r["result"]["concept"])
        except asyncio.TimeoutError:
            pass


async def round_(mode, n):
    marta = {"ns": NS, "db": DB, "ac": "banca", "email": "marta@dominican.test", "pass": "demo-marta"}
    ana = {"ns": NS, "db": DB, "ac": "banca", "email": "ana@dominican.test", "pass": "demo-ana"}
    root = {"user": "root", "pass": "root"}
    tag_m, tag_a = f"m{n}", f"a{n}"
    gm, ga = [], []
    rm, ra = asyncio.Event(), asyncio.Event()
    tasks = [sub(root if mode == "root" else marta, tag_m, gm, rm)]
    if mode in ("dos", "root"):
        tasks.append(sub(root if mode == "root" else ana, tag_a, ga, ra))
    else:
        ra.set()
    t = asyncio.gather(*tasks)
    await rm.wait(); await ra.wait()
    await asyncio.sleep(0.2)
    root_last(f"CREATE notification SET customer = customer:ana, kind = 'incoming', amount = 1dec, concept = '{tag_a}';"
              f"CREATE notification SET customer = customer:marta, kind = 'incoming', amount = 1dec, concept = '{tag_m}';")
    await t
    return bool(gm)


async def main():
    mode, rounds = sys.argv[1], int(sys.argv[2])
    ok = 0
    for n in range(rounds):
        ok += await round_(mode, n)
    print(f"{mode}: marta recibió su notificación en {ok}/{rounds} rondas")

asyncio.run(main())
