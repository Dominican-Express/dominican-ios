#!/usr/bin/env python3
"""Prueba en rojo de controls_test.py: congelar, no borrar, auditoría.

    python3 db/demo/controls_redteam.py
"""
from redteam import run_cases

C = "10_controls.surql"
CASES = [
    # --- congelar, en proporción
    ("el anillo congela la cuenta", C,
     "UPDATE $acc SET frozen_at = time::now(), frozen_by = $after.id WHERE frozen_at = NONE;", "",
     "el anillo congela la cuenta de marta"),
    ("el anillo bloquea las tarjetas", C,
     "UPDATE card SET blocked = true WHERE account = $acc AND blocked = false;", "",
     "…y bloquea sus tarjetas"),
    ("respuesta proporcional: la estructuración no congela", C,
     "IF $kind = 'mule_ring' {", "IF $kind IN ['mule_ring', 'structuring'] {",
     "la estructuración NO congela a jose"),
    ("lo dudoso va a revisión", C,
     "UPDATE $accs SET review_at = time::now() WHERE review_at = NONE;", "",
     "la estructuración NO congela a jose"),
    ("la API rechaza con 423", "07_api.surql",
     "} ELSE IF $from.frozen_at != NONE {", "} ELSE IF false {",
     "marta no puede sacar dinero: 423"),
    ("sin decir por qué", "07_api.surql",
     "[423, 'account_frozen']", "[423, 'account_frozen_mule_ring']",
     "…sin decirle por qué"),
    ("segunda capa en fn::transfer", "03_functions.surql",
     'IF $f.frozen_at != NONE { THROW "account_frozen" };', "",
     "tampoco llamando a fn::transfer directamente"),
    ("congelar no bloquea lo que entra", "03_functions.surql",
     'IF $f.frozen_at != NONE { THROW "account_frozen" };',
     'IF $f.frozen_at != NONE OR $t.frozen_at != NONE { THROW "account_frozen" };',
     "el dinero que ENTRA en una cuenta congelada sí llega"),

    # --- no se borra, se termina
    ("un cliente no borra relaciones con aparatos", "02_graph.surql",
     "DEFINE TABLE OVERWRITE uses TYPE RELATION IN customer OUT device ENFORCED;",
     "DEFINE TABLE OVERWRITE uses TYPE RELATION IN customer OUT device ENFORCED PERMISSIONS FULL;",
     "marta no puede borrar su relación con el móvil compartido"),
    ("un cliente no borra aparatos", "02_graph.surql",
     "DEFINE TABLE OVERWRITE device SCHEMAFULL TYPE NORMAL;",
     "DEFINE TABLE OVERWRITE device SCHEMAFULL TYPE NORMAL PERMISSIONS FULL;",
     "…ni el móvil"),
    ("solo desvinculas lo tuyo", C,
     "WHERE in = $me AND out = $dev AND ended_at = NONE", "WHERE out = $dev AND ended_at = NONE",
     "marta no puede desvincular el móvil de ana"),
    ("desvincular marca, no borra", C,
     "UPDATE $edge SET ended_at = time::now();", "DELETE $edge;",
     "…y la relación se QUEDA"),
    ("el detector cuenta también lo desvinculado", "05_detectors.surql",
     "LET $devices = (SELECT id, fingerprint, <-uses<-customer AS holders",
     "LET $devices = (SELECT id, fingerprint, <-uses[WHERE ended_at = NONE]<-customer AS holders",
     "…y el detector la sigue contando"),

    # --- auditoría
    ("la auditoría guarda quién", C,
     "actor = $auth.id,", "actor = NONE,",
     "el desvínculo queda con quién"),
    ("la auditoría guarda antes y después", C,
     "$before.{in, out, ended_at}, $after.{in, out, ended_at}", "NONE, NONE",
     "…con el antes y el después"),
    ("la congelación se audita", C,
     "      OR $before.frozen_at != $after.frozen_at\n      OR $before.review_at", "      OR $before.review_at",
     "la congelación queda auditada"),
    ("los saldos no inundan la auditoría", C,
     "DEFINE EVENT OVERWRITE audit_account ON account\n    WHEN $event != 'UPDATE'",
     "DEFINE EVENT OVERWRITE audit_account ON account\n    WHEN true OR $event != 'UPDATE'",
     "un pago normal NO llena la auditoría"),
    ("los cobros no inundan la auditoría", C,
     "DEFINE EVENT OVERWRITE audit_card ON card\n    WHEN $event != 'UPDATE'",
     "DEFINE EVENT OVERWRITE audit_card ON card\n    WHEN true OR $event != 'UPDATE'",
     "…ni un cobro con tarjeta"),
    ("la auditoría no guarda PAN ni CVV", C,
     "$before.{account, holder, blocked, monthly_limit},\n              $after.{account, holder, blocked, monthly_limit});",
     "$before, $after);",
     "la auditoría no guarda el PAN ni el CVV"),
    ("un cliente no lee la auditoría", C,
     "DEFINE TABLE OVERWRITE audit_log SCHEMAFULL TYPE NORMAL PERMISSIONS NONE;",
     "DEFINE TABLE OVERWRITE audit_log SCHEMAFULL TYPE NORMAL PERMISSIONS FOR select FULL;",
     "marta no puede leer la auditoría"),
    ("un cliente no escribe ni borra la auditoría", C,
     "DEFINE TABLE OVERWRITE audit_log SCHEMAFULL TYPE NORMAL PERMISSIONS NONE;",
     "DEFINE TABLE OVERWRITE audit_log SCHEMAFULL TYPE NORMAL PERMISSIONS FOR create, delete FULL;",
     "…ni escribir ni borrar en ella"),

    # --- liberar
    ("liberar queda auditado con la nota", C,
     "$after.{iban, kind, frozen_at, frozen_by, review_at, released_note});",
     "$after.{iban, kind, frozen_at, frozen_by, review_at});",
     "…y queda auditado, con la nota"),
    ("solo el equipo antifraude libera", C,
     "RETURN (SELECT VALUE id FROM ONLY $acc);\n} PERMISSIONS NONE;",
     "RETURN (SELECT VALUE id FROM ONLY $acc);\n} PERMISSIONS FULL;",
     "un cliente no puede liberarse a sí mismo"),
]

if __name__ == "__main__":
    run_cases(CASES, "controls_test.py")
