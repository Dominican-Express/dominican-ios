#!/usr/bin/env python3
"""Prueba en rojo de payments_test.py: rompe cada protección de la API de pagos.

    python3 db/demo/payments_redteam.py
"""
from redteam import run_cases

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


if __name__ == "__main__":
    run_cases(CASES, "payments_test.py")
