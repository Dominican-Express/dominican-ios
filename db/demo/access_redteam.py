#!/usr/bin/env python3
"""Prueba en rojo de access_test.py: rompe cada permiso y exige que su prueba caiga.

    python3 db/demo/access_redteam.py
"""
from redteam import run_cases

CASES = [
    ("PAN sin exigir verificación",
     "01_core.surql",
     "PERMISSIONS FOR select WHERE holder = $auth.customer AND $auth.verified_until > time::now();",
     "PERMISSIONS FOR select WHERE holder = $auth.customer;",
     "ve su tarjeta, pero sin PAN ni CVV"),

    ("PAN sin exigir que seas quien lleva la tarjeta",
     "01_core.surql",
     "PERMISSIONS FOR select WHERE holder = $auth.customer AND $auth.verified_until > time::now();",
     "PERMISSIONS FOR select WHERE $auth.verified_until > time::now();",
     "verificado, sigue SIN ver el PAN de la tarjeta de ana"),

    ("hash de contraseña legible",
     "06_access.surql",
     "DEFINE FIELD OVERWRITE pass ON app_user TYPE string PERMISSIONS FOR select NONE;",
     "DEFINE FIELD OVERWRITE pass ON app_user TYPE string PERMISSIONS FULL;",
     "no puede leer su propio hash de contraseña"),

    ("hash de PIN legible",
     "06_access.surql",
     "DEFINE FIELD OVERWRITE pin  ON app_user TYPE string PERMISSIONS FOR select NONE;",
     "DEFINE FIELD OVERWRITE pin  ON app_user TYPE string PERMISSIONS FULL;",
     "no puede leer su propio hash de PIN"),

    ("/verify-pin hace caso a un `user` del cuerpo",
     "06_access.surql",
     "LET $u = (SELECT * FROM ONLY $auth.id);",
     "LET $u = (SELECT * FROM ONLY (IF $b.user != NONE { type::record($b.user) } ELSE { $auth.id }));",
     "no puede pedir la verificación de otro usuario"),

    ("el usuario puede editar su propia ficha",
     "06_access.surql",
     "DEFINE TABLE OVERWRITE app_user SCHEMAFULL TYPE NORMAL\n    PERMISSIONS FOR select WHERE id = $auth.id;",
     "DEFINE TABLE OVERWRITE app_user SCHEMAFULL TYPE NORMAL\n    PERMISSIONS FOR select, update WHERE id = $auth.id;",
     "no puede alargarse la ventana a mano"),

    ("cuentas legibles por cualquiera",
     "01_core.surql",
     "DEFINE TABLE OVERWRITE account SCHEMAFULL TYPE NORMAL\n    PERMISSIONS FOR select WHERE id IN $auth.customer->owns->account;",
     "DEFINE TABLE OVERWRITE account SCHEMAFULL TYPE NORMAL\n    PERMISSIONS FOR select FULL;",
     "no ve cuentas ajenas"),

    ("la alerta de viaje imposible sin `account`",
     "04_events.surql",
     "card = $after.card, account = $after.card.account,",
     "card = $after.card,",
     "ana ve la alerta de viaje imposible de su tarjeta"),

    ("alertas legibles por cualquiera",
     "02_graph.surql",
     "DEFINE TABLE OVERWRITE fraud_alert SCHEMALESS TYPE NORMAL\n    PERMISSIONS FOR select WHERE account IN $auth.customer->owns->account;",
     "DEFINE TABLE OVERWRITE fraud_alert SCHEMALESS TYPE NORMAL\n    PERMISSIONS FOR select FULL;",
     "ana no ve alertas de cuentas ajenas"),
]

if __name__ == "__main__":
    run_cases(CASES, "access_test.py")
