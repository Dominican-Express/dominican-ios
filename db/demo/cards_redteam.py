#!/usr/bin/env python3
"""Prueba en rojo de cards_test.py: PIN, tarjetas y notificaciones.

    python3 db/demo/cards_redteam.py
"""
from redteam import run_cases

CASES = [
    ("el fallo de PIN se guarda aunque se rechace",
     "06_access.surql",
     "UPDATE $u.id SET pin_failures = $fails;\n            RETURN { status: 401",
     "THROW 'wrong_pin';\n            RETURN { status: 401",
     "…y el fallo queda GUARDADO aunque se rechace"),

    ("bloqueo tras 3 fallos",
     "06_access.surql",
     "IF $fails >= 3 {",
     "IF false {",
     "al tercer fallo seguido: 423 bloqueado"),

    ("el bloqueo rechaza incluso el PIN correcto",
     "06_access.surql",
     "IF $u.pin_locked_until != NONE AND $u.pin_locked_until > time::now() {",
     "IF false {",
     "bloqueado, ni el PIN correcto abre la ventana"),

    ("el cobro mueve el dinero",
     "08_cards.surql",
     "    UPDATE $c.account  SET balance -= $amount;\n",
     "",
     "…y mueve el dinero de verdad (antes no movía nada)"),

    ("tarjeta bloqueada no cobra",
     "08_cards.surql",
     "LET $reason = IF $c.blocked {",
     "LET $reason = IF false {",
     "con la tarjeta bloqueada el cobro se deniega"),

    ("solo quien LLEVA la tarjeta la gestiona, no cualquier cotitular",
     "08_cards.surql",
     "IF $c = NONE OR $c.holder != $auth.customer {",
     "IF $c = NONE OR $c.account NOTINSIDE $auth.customer->owns->account {",
     "luis, cotitular de la cuenta, NO puede bloquear la tarjeta de ana (404)"),

    ("límite mensual",
     "08_cards.surql",
     "} ELSE IF $spent + $amount > $c.monthly_limit {",
     "} ELSE IF false {",
     "50 € más superan los 100: denegado"),

    ("tope del banco para el límite",
     "08_cards.surql",
     "IF $limit <= 0dec OR $limit > $max {",
     "IF $limit <= 0dec {",
     "límite por encima del máximo del banco: 422"),

    ("el aviso llega a TODOS los titulares",
     "08_cards.surql",
     "FOR $who IN (SELECT VALUE in FROM owns WHERE out = $after.account) {",
     "FOR $who IN (SELECT VALUE in FROM owns WHERE out = $after.account AND role = 'titular') {",
     "luis también: es cotitular de la cuenta que paga"),

    ("el importe de un aviso no se puede cambiar",
     "08_cards.surql",
     "DEFINE FIELD OVERWRITE amount   ON notification TYPE decimal              PERMISSIONS FOR update NONE;",
     "DEFINE FIELD OVERWRITE amount   ON notification TYPE decimal;",
     "…pero no puede cambiar el importe ni pasárselo a otro"),

    ("cada uno ve solo sus avisos",
     "08_cards.surql",
     "PERMISSIONS FOR select, update WHERE customer = $auth.customer;",
     "PERMISSIONS FOR select, update FULL;",
     "ana no ve los avisos de marta"),

    ("nadie se fabrica avisos",
     "08_cards.surql",
     "PERMISSIONS FOR select, update WHERE customer = $auth.customer;",
     "PERMISSIONS FOR select, update WHERE customer = $auth.customer FOR create FULL;",
     "ana no puede fabricarse avisos"),
]

if __name__ == "__main__":
    run_cases(CASES, "cards_test.py")
