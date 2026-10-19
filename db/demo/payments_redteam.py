#!/usr/bin/env python3
"""Prueba en rojo de payments_test.py.

Para cada protección de la API de pagos, aplica el esquema REAL con esa línea
cambiada (texto exacto sobre el fichero, no una copia reescrita a mano) sobre
una base limpia, y exige que la comprobación que la vigila caiga. Si la
sustitución no encuentra el texto, el caso falla: así no puede quedar un caso
que no rompe nada porque el fichero cambió.

    python3 db/demo/payments_redteam.py
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = HERE.parent / "schema"

# (protección, fichero, texto original, texto roto, comprobación que DEBE caer)
CASES = [
    ("comprobar que la cuenta de origen es tuya",
     "07_api.surql",
     "IF $from = NONE OR $from NOTINSIDE $auth.customer->owns->account {",
     "IF $from = NONE {",
     "ana no puede pagar desde la cuenta de marta (403)"),

    ("una clave de orden de otro usuario no se reutiliza",
     "07_api.surql",
     "IF $prev.requester != $auth.id { RETURN { status: 409, body: { error: 'order_id_in_use' } } };",
     "",
     "reutilizar el id de una orden de OTRO usuario: 409 sin revelar nada"),

    ("idempotencia: el id de la orden lo elige el cliente",
     "07_api.surql",
     "LET $id = type::record('payment_order', $key);",
     "LET $id = type::record('payment_order', rand::uuid::v4());",
     "…sin pagar dos veces"),

    ("comprobar el saldo antes de ejecutar",
     "07_api.surql",
     "} ELSE IF fn::balance($from) < $amount {\n            [422, 'insufficient_funds']",
     "} ELSE IF false {\n            [422, 'insufficient_funds']",
     "sin saldo: 422 insufficient_funds"),

    ("límite de Bizum",
     "07_api.surql",
     "($amount < $limits.bizum_min OR $amount > $limits.bizum_max)",
     "false",
     "bizum por encima del límite: 422"),

    ("leer el cuerpo sin que se altere el texto",
     "07_api.surql",
     'DEFINE API OVERWRITE "/transfers" FOR post\n    MIDDLEWARE api::res::body("json")',
     'DEFINE API OVERWRITE "/transfers" FOR post\n    MIDDLEWARE api::req::body("json"), api::res::body("json")',
     "el concepto llega intacto, con su espacio"),

    ("fn::transfer cerrada a los clientes",
     "03_functions.surql",
     "    RELATE $from->transfer->$to SET amount = $amount, txn = $tx.id;\n    RETURN $tx.id;\n} PERMISSIONS NONE;",
     "    RELATE $from->transfer->$to SET amount = $amount, txn = $tx.id;\n    RETURN $tx.id;\n} PERMISSIONS FULL;",
     "un cliente no puede llamar a fn::transfer directamente"),

    ("las órdenes solo las lee quien las hizo",
     "07_api.surql",
     "PERMISSIONS FOR select WHERE requester = $auth.id;",
     "PERMISSIONS FOR select FULL;",
     "marta no puede leer las órdenes de ana"),

    ("el NIF de un contacto no se ve",
     "01_core.surql",
     "DEFINE FIELD OVERWRITE nif   ON customer TYPE string\n    PERMISSIONS FOR select WHERE id = $auth.customer;",
     "DEFINE FIELD OVERWRITE nif   ON customer TYPE string;",
     "…pero no su NIF ni su cuenta"),

    ("solo ves a quien es contacto o cotitular",
     "01_core.surql",
     "PERMISSIONS FOR select WHERE id = $auth.customer\n                              OR id IN $auth.customer->favorite->customer",
     "PERMISSIONS FOR select WHERE true\n                              OR id IN $auth.customer->favorite->customer",
     "marta no ve a ana: no son contactos ni cotitulares"),

    ("sin sesión no se entra",
     "07_api.surql",
     'DEFINE API OVERWRITE "/transfers" FOR post\n    MIDDLEWARE api::res::body("json")\n    PERMISSIONS WHERE $auth.id != NONE',
     'DEFINE API OVERWRITE "/transfers" FOR post\n    MIDDLEWARE api::res::body("json")\n    PERMISSIONS FULL',
     "sin sesión: 403 antes de ejecutar nada"),
]


def run(cmd, env):
    return subprocess.run(cmd, cwd=HERE, env=env, capture_output=True, text=True)


def main():
    caught = 0
    for name, fname, old, new, must_fail in CASES:
        src = (SCHEMA / fname).read_text()
        if old not in src:
            print(f"  [ROTO ] {name}\n          el texto a romper ya no está en {fname}: actualiza el caso")
            continue
        db = "rt_" + uuid.uuid4().hex[:8]
        env = {**os.environ, "SURREAL_DB": db}
        run(["./apply.sh"], env)
        broken = HERE / f".rt_{db}.surql"
        broken.write_text(src.replace(old, new, 1))
        run(["./surql.sh", str(broken)], env)
        broken.unlink()
        run(["./surql.sh", "01_seed.surql"], env)
        out = run([sys.executable, "payments_test.py"], env).stdout
        line = next((l for l in out.splitlines() if must_fail in l), "")
        ok = "FALLA" in line
        caught += ok
        print(f"  [{'cae  ' if ok else 'NO CAE'}] {name}")
        if not ok:
            print(f"          «{must_fail}» siguió pasando (o no se ejecutó): no vigila esta rotura")
    print(f"\n{caught}/{len(CASES)} roturas detectadas por su prueba")
    sys.exit(0 if caught == len(CASES) else 1)


if __name__ == "__main__":
    main()
