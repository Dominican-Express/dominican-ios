#!/usr/bin/env python3
"""Prueba de los controles de banco (10_controls): congelar al detectar, no
borrar sino terminar, y auditoría con quién.

    python3 db/demo/controls_test.py

Requiere haber cargado 01_seed.surql; lanza el ataque y el barrido y lo deja
ensuciado. Como en las demás pruebas, el EFECTO se mira como root.
"""
import subprocess
import sys
from pathlib import Path

from session import api, last, root_last, signin

FAILS = []
HERE = Path(__file__).resolve().parent


def check(name, cond, got):
    print(f"  [{'ok   ' if cond else 'FALLA'}] {name}")
    if not cond:
        print(f"          obtenido: {got}")
        FAILS.append(name)


def one(sql):
    # Sin filas = None, no []: una prueba que revienta no dice QUÉ ha fallado.
    r = root_last(sql)
    if isinstance(r, list):
        return r[0] if r else None
    return r


def audit_rows():
    return one("SELECT VALUE count() FROM audit_log GROUP ALL;") or 0


for script in ("02_attack.surql", "03_detect.surql"):
    subprocess.run(["./surql.sh", script], cwd=HERE, capture_output=True, check=True)
state = {r["id"]: r for r in root_last(
    "SELECT id, frozen_at != NONE AS frozen, review_at != NONE AS review FROM account;")}
marta = signin("marta@dominican.test", "demo-marta")

print("Congelar al detectar, en proporción")
check("el anillo congela la cuenta de marta",
      state["account:marta"]["frozen"]
      and str(one("SELECT VALUE frozen_by FROM account:marta;")).startswith("fraud_alert:['mule_ring'"),
      state["account:marta"])
check("…y las de ana y luis, del mismo anillo",
      state["account:ana"]["frozen"] and state["account:luis"]["frozen"], state)
check("…y bloquea sus tarjetas (luis no tenía viaje imposible)",
      one("SELECT VALUE blocked FROM card:luis;") is True, one("SELECT * FROM card:luis;"))
check("la estructuración NO congela a jose: lo manda a revisión",
      not state["account:jose"]["frozen"] and state["account:jose"]["review"], state["account:jose"])
check("sara, sin alerta, ni congelada ni en revisión",
      not state["account:sara"]["frozen"] and not state["account:sara"]["review"], state["account:sara"])

before = float(one("SELECT VALUE balance FROM account:marta;"))
st, body = api(marta, "/transfers", {"id": "ctl-drain-00001", "from": "account:marta",
                                     "to_iban": "ES5555555555555555555555", "amount": "100"})
check("marta no puede sacar dinero: 423 account_frozen", (st, body.get("reason")) == (423, "account_frozen"),
      (st, body))
check("…su saldo no se mueve", float(one("SELECT VALUE balance FROM account:marta;")) == before,
      one("SELECT VALUE balance FROM account:marta;"))
check("…y el intento queda registrado como orden rechazada",
      one("SELECT VALUE status FROM payment_order:`ctl-drain-00001`;") == "rejected",
      one("SELECT * FROM payment_order:`ctl-drain-00001`;"))
check("…sin decirle por qué (prohibido avisar al sospechoso)",
      "mule" not in str(body) and "ring" not in str(body) and "fraud" not in str(body), body)
r = root_last("RETURN fn::transfer(account:marta, account:sara, 10dec);")
check("tampoco llamando a fn::transfer directamente (segunda capa)",
      isinstance(r, str) and "account_frozen" in r, r)
root_last("RETURN fn::transfer(account:sara, account:marta, 10dec);")
after_in = float(one("SELECT VALUE balance FROM account:marta;"))
check("el dinero que ENTRA en una cuenta congelada sí llega", after_in == before + 10, (before, after_in))

print("No se borra, se termina")
last(marta, "DELETE uses WHERE in = customer:marta; DELETE device:mula;")
check("marta no puede borrar su relación con el móvil compartido",
      len(root_last("SELECT id FROM uses WHERE in = customer:marta AND out = device:mula;")) == 1,
      root_last("SELECT * FROM uses WHERE in = customer:marta AND out = device:mula;"))
check("…ni el móvil", root_last("SELECT VALUE id FROM device:mula;") == ["device:mula"],
      root_last("SELECT * FROM device:mula;"))
st, _ = api(marta, "/devices/unlink", {"device": "device:movil_ana"})
check("marta no puede desvincular el móvil de ana: 404", st == 404, st)
st, body = api(marta, "/devices/unlink", {"device": "device:mula"})
check("marta desvincula su móvil por la app: 200", st == 200, (st, body))
edge = one("SELECT * FROM uses WHERE in = customer:marta AND out = device:mula;")
check("…y la relación se QUEDA, con fecha de fin", edge is not None and edge.get("ended_at"), edge)
r = one("RETURN fn::detect_shared_devices(3);")
check("…y el detector la sigue contando: desvincularse no esconde",
      r == 1, r)
st, _ = api(marta, "/devices/unlink", {"device": "device:mula"})
check("desvincular dos veces da 404", st == 404, st)

print("Auditoría con quién")
row = one("SELECT * FROM audit_log WHERE tbl = 'uses' AND actor = app_user:marta;")
check("el desvínculo queda con quién (marta, desde la app)",
      row is not None and row.get("via") == "banca" and row.get("action") == "UPDATE", row)
check("…con el antes y el después",
      row is not None and "ended_at" not in (row.get("before") or {}) and (row.get("after") or {}).get("ended_at"),
      row)
# La TRANSICIÓN a congelada, no cualquier fila que la lleve: el paso a revisión
# de después también trae frozen_at en el «después».
fr = one("SELECT * FROM audit_log WHERE rec = account:marta "
         "AND before.frozen_at = NONE AND after.frozen_at != NONE;")
check("la congelación queda auditada, hecha por el barrido del banco (root)",
      fr is not None and fr.get("actor") is None and fr.get("via") == "root", fr)
n0 = audit_rows()
root_last("RETURN fn::transfer(account:sara, account:jose, 5dec);")
check("un pago normal NO llena la auditoría (los saldos ya están en el libro)", audit_rows() == n0,
      (n0, audit_rows()))
root_last("RETURN fn::charge_card(card:luis, 1dec, 'Bench', (-3.70, 40.41));")
check("…ni un cobro con tarjeta", audit_rows() == n0, (n0, audit_rows()))
text = str(root_last("SELECT * FROM audit_log;"))
pan = one("SELECT VALUE pan FROM card:ana;")
check("la auditoría no guarda el PAN ni el CVV", pan and pan not in text and "cvv" not in text, pan)
check("marta no puede leer la auditoría", last(marta, "SELECT * FROM audit_log;") == [],
      last(marta, "SELECT * FROM audit_log;"))
n0 = audit_rows()
last(marta, "CREATE audit_log SET tbl = 'x', rec = account:marta, action = 'FAKE', via = 'banca';")
last(marta, "DELETE audit_log;")
check("…ni escribir ni borrar en ella", audit_rows() == n0, (n0, audit_rows()))

print("Liberar")
root_last("RETURN fn::release_account(account:marta, 'falso positivo revisado');")
check("liberar devuelve la cuenta a la normalidad",
      one("SELECT VALUE frozen_at FROM account:marta;") is None, one("SELECT * FROM account:marta;"))
rel = one("SELECT * FROM audit_log WHERE rec = account:marta AND after.released_note != NONE;")
check("…y queda auditado, con la nota", rel is not None and "falso positivo" in str(rel.get("after")), rel)
st, body = api(marta, "/transfers", {"id": "ctl-after-00001", "from": "account:marta",
                                     "to_iban": "ES5555555555555555555555", "amount": "10"})
check("…marta vuelve a poder enviar", st == 201, (st, body))
r = last(marta, "RETURN fn::release_account(account:marta, 'yo mismo');")
check("un cliente no puede liberarse a sí mismo", isinstance(r, str) and "permission" in r, r)

rec = root_last("RETURN fn::reconcile();")
check("al final, el saldo materializado cuadra con el libro", rec == [], rec)

print(f"\n{'TODO EN ORDEN' if not FAILS else f'{len(FAILS)} FALLOS'}")
sys.exit(1 if FAILS else 0)
