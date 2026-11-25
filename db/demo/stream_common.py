"""Piezas comunes de la entrada por Kafka (stream_*.py, alert_*.py).

Kafka: un broker local (db/stream/server.properties, `demo.sh kafka-up`). SurrealDB: por HTTP,
como el resto de scripts. El consumidor es un servicio del banco, no un
cliente de la app: entra como root, igual que aml_load.py.
"""
import base64
import http.client
import json
import os
import re
import time
from urllib.parse import urlparse

KAFKA = os.environ.get("KAFKA_BOOTSTRAP", "127.0.0.1:9092")
PAYMENTS = os.environ.get("KAFKA_PAYMENTS", "payments")
ALERTS = os.environ.get("KAFKA_ALERTS", "fraud-alerts")
# Cola de mensajes muertos: lo que no se puede ni leer va aquí, para que un
# solo mensaje roto no pare la partición entera.
DLQ = os.environ.get("KAFKA_DLQ", "payments-dlq")

URL = os.environ.get("SURREAL_URL", "http://127.0.0.1:8099")
NS = os.environ.get("SURREAL_NS", "dx")
DB = os.environ.get("SURREAL_DB", "stream")
_AUTH = "Basic " + base64.b64encode(
    f"{os.environ.get('SURREAL_USER', 'root')}:{os.environ.get('SURREAL_PASS', 'root')}".encode()).decode()


class Surreal:
    """Una conexión HTTP que se reutiliza: abrir una por mensaje costaba más
    que el propio pago."""

    def __init__(self, db=DB):
        u = urlparse(URL)
        self.host, self.port, self.db = u.hostname, u.port, db
        self.conn = http.client.HTTPConnection(self.host, self.port, timeout=60)

    def sql(self, text):
        headers = {"Accept": "application/json", "Authorization": _AUTH,
                   "surreal-ns": NS, "surreal-db": self.db}
        # Un reintento si la conexión se cortó (el servidor cierra las que
        # llevan rato quietas). Repetir es seguro: fn::stream_apply es
        # idempotente. Si vuelve a fallar, el consumidor se para SIN confirmar
        # el offset, y al arrancar otra vez Kafka le devuelve el mismo mensaje.
        for attempt in (1, 2):
            try:
                self.conn.request("POST", "/sql", body=text.encode(), headers=headers)
                raw = self.conn.getresponse().read()
                break
            except (http.client.HTTPException, ConnectionError):
                self.conn = http.client.HTTPConnection(self.host, self.port, timeout=60)
                if attempt == 2:
                    raise
        try:
            out = json.loads(raw)
        except ValueError:
            raise RuntimeError(f"respuesta que no es JSON: {raw[:120]!r}")
        if isinstance(out, dict):
            raise RuntimeError(f"error del servidor: {out}")
        return out

    def last(self, text, retries=8):
        """Resultado de la última sentencia. Reintenta solo los conflictos de
        escritura (dos transacciones tocaron el mismo registro y una se deshizo
        entera): repetir es seguro porque fn::stream_apply es idempotente.
        Cualquier otro error se lanza."""
        for attempt in range(retries + 1):
            st = self.sql(text)[-1]
            if st["status"] == "OK":
                return st["result"]
            msg = str(st["result"])
            if "conflict" in msg.lower() and attempt < retries:
                time.sleep(0.01 * (2 ** attempt))
                continue
            raise RuntimeError(msg)


def acc(name):
    """Referencia a una cuenta a partir de su clave (`ana` → account:⟨ana⟩).
    La clave viene de un mensaje externo: se escapa como texto, nunca se pega
    en la consulta tal cual."""
    return f"type::record('account', {json.dumps(name)})"


_KEY = re.compile(r"[A-Za-z0-9_-]{1,64}")
_AMOUNT = re.compile(r"[0-9]{1,9}(\.[0-9]{1,2})?")


def money(s):
    """El importe viaja como TEXTO en el JSON (un número JSON es coma flotante
    y el dinero no lo es). Solo dígitos ASCII: `str.isdigit()` aceptaría
    también «²» o cifras árabes, que SurrealDB no entiende."""
    if not isinstance(s, str) or not _AMOUNT.fullmatch(s):
        raise ValueError(f"importe no válido: {s!r}")
    return f"{s}dec"


def parse(raw):
    """Lee un mensaje de `payments`. Lanza ValueError con el motivo si no es
    un pago bien formado: entonces va a la cola de mensajes muertos."""
    try:
        m = json.loads(raw) if raw is not None else None
    except ValueError:
        raise ValueError("not_json")
    if not isinstance(m, dict):
        raise ValueError("not_an_object")
    for field in ("id", "from", "to"):
        if not isinstance(m.get(field), str) or not _KEY.fullmatch(m[field]):
            raise ValueError(f"bad_{field}")
    try:
        money(m.get("amount"))
    except ValueError:
        raise ValueError("bad_amount")
    return m
