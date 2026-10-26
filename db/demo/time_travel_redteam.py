#!/usr/bin/env python3
"""Prueba en rojo de time_travel_test.py: la máquina del tiempo.

    python3 db/demo/time_travel_redteam.py

Como el test, requiere un servidor CON versionado.
"""
from redteam import run_cases

CASES = [
    ("las cuentas se leen como estaban, no como están",
     "09_time_travel.surql",
     "(SELECT id, balance FROM $accs VERSION $at)",
     "(SELECT id, balance FROM $accs)",
     "marta tenía dinero entonces"),

    ("los aparatos se leen como estaban",
     "09_time_travel.surql",
     "(SELECT id, fingerprint FROM $devs VERSION $at)",
     "(SELECT id, fingerprint FROM $devs)",
     "el móvil borrado reaparece"),

    ("los titulares se buscan en el pasado",
     "09_time_travel.surql",
     "<-owns FROM ONLY $acc VERSION $at) ?? [];",
     "<-owns FROM ONLY $acc) ?? [];",
     "luis era cotitular de la cuenta de ana"),

    # Los cuatro sitios donde se confirma por id (fallo surrealdb#7601): se
    # sustituye la confirmación por el recorrido directo, que es lo que falla.
    ("titulares confirmados por id",
     "09_time_travel.surql",
     "<-owns FROM ONLY $acc VERSION $at) ?? [];\n    RETURN SELECT VALUE in FROM $cand VERSION $at;",
     "<-owns FROM ONLY $acc VERSION $at) ?? [];\n    RETURN (SELECT VALUE <-owns<-customer FROM ONLY $acc VERSION $at) ?? [];",
     "fn::owners_at, llamada directa"),

    ("usuarios de un aparato confirmados por id",
     "09_time_travel.surql",
     "<-uses FROM ONLY $dev VERSION $at) ?? [];\n    RETURN SELECT VALUE in FROM $cand VERSION $at;",
     "<-uses FROM ONLY $dev VERSION $at) ?? [];\n    RETURN (SELECT VALUE <-uses<-customer FROM ONLY $dev VERSION $at) ?? [];",
     "fn::users_at, llamada directa"),

    ("aparatos de una persona confirmados por id",
     "09_time_travel.surql",
     "LET $devs = array::distinct(SELECT VALUE out FROM $use_cand VERSION $at);",
     "LET $devs = array::distinct(array::flatten(SELECT VALUE ->uses->device FROM $people VERSION $at));",
     "el aparato que jose dejó antes"),

    ("cuentas de una persona confirmadas por id",
     "09_time_travel.surql",
     "LET $holder_accs = (SELECT VALUE out FROM $own_cand VERSION $at);",
     "LET $holder_accs = array::flatten(SELECT VALUE ->owns->account FROM $holders VERSION $at);",
     "la cuenta de sara, de la que marta salió antes"),

    ("el saldo histórico corta en la fecha pedida",
     "09_time_travel.surql",
     "WHERE account = $acc AND at <= $when);",
     "WHERE account = $acc);",
     "account:marta: el libro a la hora de la alerta"),

    ("un cliente no puede investigar",
     "09_time_travel.surql",
     "changes: array::flatten($changes)\n    };\n} PERMISSIONS NONE;",
     "changes: array::flatten($changes)\n    };\n} PERMISSIONS FULL;",
     "ana no puede investigar alertas"),

    ("un cliente no puede pedir saldos históricos ajenos",
     "09_time_travel.surql",
     "AND at <= $when);\n} PERMISSIONS NONE;",
     "AND at <= $when);\n} PERMISSIONS FULL;",
     "ana no puede consultar el saldo histórico"),
]

if __name__ == "__main__":
    run_cases(CASES, "time_travel_test.py")
