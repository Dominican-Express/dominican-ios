#!/usr/bin/env python3
"""Oyente de alertas de fraude en tiempo real vía LIVE SELECT.

Se suscribe a `fraud_alert` por WebSocket y pinta cada alerta según llega.
Para la demo: se deja corriendo en una terminal y se lanza el ataque en otra.

    uv run --with websockets python3 db/demo/live_listener.py
    DEMO_LANG=en uv run --with websockets python3 db/demo/live_listener.py   # en inglés

Limitación real de SurrealDB: LIVE SELECT solo funciona en despliegue de UN
nodo. No se puede tener a la vez la escalabilidad distribuida y las consultas
en vivo. Conviene decirlo en la memoria en lugar de esconderlo.
"""
import asyncio
import json
import os
import sys

try:
    import websockets
except ImportError:
    sys.exit("Falta el paquete `websockets`. Instálalo con: pip install websockets")

URL = os.environ.get("SURREAL_WS", "ws://127.0.0.1:8099/rpc")
USER = os.environ.get("SURREAL_USER", "root")
PASS = os.environ.get("SURREAL_PASS", "root")
NS = os.environ.get("SURREAL_NS", "dx")
DB = os.environ.get("SURREAL_DB", "bank")

# Umbral: por debajo de esto no se molesta al usuario.
MIN_SCORE = float(os.environ.get("MIN_SCORE", "0.5"))

# DEMO_LANG=en para presentar en inglés.
LANG = os.environ.get("DEMO_LANG", "es")
LABELS = {
    "es": {
        "mule_ring": "anillo de mulas",
        "shared_device": "dispositivo compartido",
        "structuring": "estructuración",
        "impossible_travel": "viaje imposible",
        "velocity": "ráfaga de cargos",
        "low_balance": "saldo bajo",
        "listening": "escuchando alertas en {ns}/{db} con score >= {min} … (Ctrl-C para salir)",
        "bye": "fin",
    },
    "en": {
        "mule_ring": "money-mule ring",
        "shared_device": "shared device",
        "structuring": "structuring",
        "impossible_travel": "impossible travel",
        "velocity": "burst of charges",
        "low_balance": "low balance",
        "listening": "listening for fraud alerts in {ns}/{db} with score >= {min} … (Ctrl-C to stop)",
        "bye": "done",
    },
}
ICONS = LABELS.get(LANG, LABELS["es"])


async def main() -> None:
    async with websockets.connect(URL, subprotocols=["json"]) as ws:
        counter = {"id": 0}

        async def rpc(method, params):
            counter["id"] += 1
            await ws.send(json.dumps({"id": counter["id"], "method": method, "params": params}))

        await rpc("signin", [{"user": USER, "pass": PASS}])
        await rpc("use", [NS, DB])
        await rpc("query", [f"LIVE SELECT * FROM fraud_alert WHERE score >= {MIN_SCORE};"])

        # flush en cada línea: sin esto, al redirigir la salida Python la
        # retiene en el buffer y la demo parece muerta.
        print(ICONS["listening"].format(ns=NS, db=DB, min=MIN_SCORE) + "\n", flush=True)
        async for raw in ws:
            msg = json.loads(raw)
            res = msg.get("result")
            # Una notificación en vivo trae 'action'; una respuesta normal, no.
            # Solo CREATE: LIVE SELECT también avisa de los DELETE, y al reiniciar
            # la demo cada alerta borrada se pintaba otra vez como si fuera nueva.
            if not isinstance(res, dict) or res.get("action") != "CREATE":
                continue
            alert = res.get("result", {})
            kind = alert.get("kind", "?")
            score = alert.get("score", 0)
            target = alert.get("account") or alert.get("card") or alert.get("device") or ""
            detail = alert.get("detail", {})
            print(f"[{score:>4.2f}]  {ICONS.get(kind, kind):<24} {target}", flush=True)
            if detail:
                print(f"         {json.dumps(detail, ensure_ascii=False)}", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n" + ICONS["bye"])
