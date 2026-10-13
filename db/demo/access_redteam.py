#!/usr/bin/env python3
"""Prueba en rojo de access_test.py.

Un test que nunca has visto fallar no vigila nada. Para cada protección, este
script la ROMPE a propósito sobre una base limpia y comprueba que el test que
la vigila cae. Si una rotura no tumba su test, ese test es decorativo.

    python3 db/demo/access_redteam.py
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent

# (protección rota, SurrealQL que la rompe, test que DEBE fallar)
CASES = [
    ("PAN sin exigir que seas quien lleva la tarjeta",
     "DEFINE FIELD OVERWRITE pan ON card TYPE option<string> "
     "PERMISSIONS FOR select WHERE $auth.verified_until > time::now();",
     "verificado, sigue SIN ver el PAN de la tarjeta de ana"),

    ("hash de contraseña legible",
     "DEFINE FIELD OVERWRITE pass ON app_user TYPE string PERMISSIONS FULL;",
     "no puede leer su propio hash de contraseña"),

    ("hash de PIN legible",
     "DEFINE FIELD OVERWRITE pin ON app_user TYPE string PERMISSIONS FULL;",
     "no puede leer su propio hash de PIN"),

    ("`step_up.user` lo puede fijar el cliente",
     "DEFINE FIELD OVERWRITE user ON step_up TYPE record<app_user> DEFAULT $auth.id;",
     "no puede pedir la verificación de otro usuario"),

    ("el evento no borra la petición con el PIN",
     """DEFINE EVENT OVERWRITE step_up_check ON step_up WHEN $event = "CREATE" THEN {
            LET $ok = crypto::argon2::compare($after.user.pin, $after.pin);
            IF !$ok { THROW "PIN incorrecto" };
            UPDATE $after.user SET verified_until = time::now() + 90s;
        };""",
     "la petición con el PIN en claro no queda guardada"),

    ("el usuario puede editar su propia ficha",
     "DEFINE TABLE OVERWRITE app_user SCHEMAFULL TYPE NORMAL "
     "PERMISSIONS FOR select, update WHERE id = $auth.id;",
     "no puede alargarse la ventana a mano"),

    ("cuentas legibles por cualquiera",
     "DEFINE TABLE OVERWRITE account SCHEMAFULL TYPE NORMAL PERMISSIONS FOR select FULL;",
     "no ve cuentas ajenas"),

    ("la alerta de viaje imposible sin `account`",
     """DEFINE EVENT OVERWRITE impossible_travel ON card_payment WHEN $event = "CREATE" THEN {
            LET $prev = (SELECT * FROM card_payment WHERE card = $after.card AND at < $after.at
                         ORDER BY at DESC LIMIT 1)[0];
            IF $prev != NONE {
                LET $m = geo::distance($prev.loc, $after.loc);
                LET $s = duration::secs($after.at - $prev.at);
                IF $s > 0 AND ($m / $s) > 250 {
                    CREATE fraud_alert SET kind = 'impossible_travel', score = 0.9, card = $after.card;
                };
            };
        };""",
     "ana ve la alerta de viaje imposible de su tarjeta"),

    ("alertas legibles por cualquiera",
     "DEFINE TABLE OVERWRITE fraud_alert SCHEMALESS TYPE NORMAL PERMISSIONS FOR select FULL;",
     "ana no ve alertas de cuentas ajenas"),
]


def run(cmd, env):
    return subprocess.run(cmd, cwd=HERE, env=env, capture_output=True, text=True)


def main():
    caught = 0
    for name, breakage, must_fail in CASES:
        db = "rt_" + uuid.uuid4().hex[:8]
        env = {**os.environ, "SURREAL_DB": db}
        run(["./apply.sh"], env)
        run(["./surql.sh", "01_seed.surql"], env)
        brk = HERE / f".rt_{db}.surql"
        brk.write_text(breakage)
        run(["./surql.sh", str(brk)], env)
        brk.unlink()
        out = run([sys.executable, "access_test.py"], env).stdout
        line = next((l for l in out.splitlines() if must_fail in l), "")
        ok = "FALLA" in line
        caught += ok
        print(f"  [{'cae  ' if ok else 'NO CAE'}] {name}")
        if not ok:
            print(f"          el test «{must_fail}» siguió pasando: no vigila esta rotura")
    print(f"\n{caught}/{len(CASES)} roturas detectadas por su test")
    sys.exit(0 if caught == len(CASES) else 1)


if __name__ == "__main__":
    main()
