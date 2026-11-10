#!/usr/bin/env python3
"""Prueba de los detectores por barrido (05_detectors): repetir el barrido no
duplica alertas, y un fraude NUEVO sigue avisando.

    python3 db/demo/detect_test.py

Requiere haber cargado 01_seed.surql; lanza 02_attack.surql y lo deja ensuciado.
"""
import subprocess
import sys
from pathlib import Path

from session import root_last

FAILS = []
HERE = Path(__file__).resolve().parent


def check(name, cond, got):
    print(f"  [{'ok   ' if cond else 'FALLA'}] {name}")
    if not cond:
        print(f"          obtenido: {got}")
        FAILS.append(name)


def sweep():
    root_last("RETURN fn::detect_rings(5);")
    root_last("RETURN fn::detect_shared_devices(3);")
    root_last("RETURN fn::detect_structuring(2700dec, 3000dec, 5);")


def counts():
    rows = root_last("SELECT kind, count() AS n FROM fraud_alert GROUP BY kind;")
    return {r["kind"]: r["n"] for r in rows}


subprocess.run(["./surql.sh", "02_attack.surql"], cwd=HERE, capture_output=True, check=True)

print("Barrido")
sweep()
first = counts()
check("el primer barrido avisa: 3 cuentas del anillo, 1 aparato, 1 estructuración",
      (first.get("mule_ring"), first.get("shared_device"), first.get("structuring")) == (3, 1, 1), first)
sweep()
again = counts()
check("repetir el barrido no duplica los anillos", again.get("mule_ring") == first.get("mule_ring"), again)
check("…ni el aparato compartido", again.get("shared_device") == first.get("shared_device"), again)
check("…ni la estructuración", again.get("structuring") == first.get("structuring"), again)

# Un anillo NUEVO (jose -> sara -> ana -> jose) tiene que seguir saltando aunque
# ana ya tenga alerta: si el id de la alerta fuera solo la cuenta, se tragaría.
# La cuenta de ana quedó congelada por el primer anillo (10_controls): el equipo
# antifraude la libera antes, como haría al cerrar el caso.
root_last("RETURN fn::release_account(account:ana, 'caso cerrado');")
for a, b, amt in [("jose", "sara", 100), ("sara", "ana", 95), ("ana", "jose", 90)]:
    root_last(f"RETURN fn::transfer(account:{a}, account:{b}, {amt}dec);")
sweep()
new = counts()
check("un anillo nuevo sigue avisando (jose, sara y ana otra vez)",
      new.get("mule_ring") == first.get("mule_ring") + 3, new)

print("Segundo nivel: anillo que solo ve la regla amplia")
check("el escenario no da posibles anillos por sí solo (lo de arriba ya es anillo estricto)",
      new.get("possible_ring") is None, new)
# Como en los datos de IBM: el importe CRECE en cada salto (+10 %). La regla
# estricta no lo ve; la amplia sí, y eso va a revisión, no a congelar.
for i, w in enumerate(("w1", "w2", "w3"), 1):
    root_last(f"CREATE account:{w} SET iban = 'ES{i:022d}';")
    root_last(f"RETURN fn::credit(account:{w}, 1000dec, 'payroll');")
for a, b, amt in [("w1", "w2", 200), ("w2", "w3", 220), ("w3", "w1", 240)]:
    root_last(f"RETURN fn::transfer(account:{a}, account:{b}, {amt}dec);")
sweep()
wide = counts()
w = {r["id"]: r for r in root_last(
    "SELECT id, frozen_at != NONE AS frozen, review_at != NONE AS review FROM [account:w1, account:w2, account:w3];")}
check("el anillo que crece da posible anillo a sus 3 cuentas…", wide.get("possible_ring") == 3, wide)
check("…y no anillo estricto", wide.get("mule_ring") == new.get("mule_ring"), wide)
check("…las manda a revisión", all(r["review"] for r in w.values()), w)
check("…sin congelarlas", not any(r["frozen"] for r in w.values()), w)
both = root_last("SELECT VALUE account FROM fraud_alert WHERE kind = 'possible_ring' "
                 "AND account IN (SELECT VALUE account FROM fraud_alert WHERE kind = 'mule_ring');")
check("ninguna cuenta con anillo estricto recibe además posible anillo", both == [], both)
sweep()
check("repetir el barrido no duplica los posibles anillos", counts().get("possible_ring") == 3, counts())

print(f"\n{'TODO EN ORDEN' if not FAILS else f'{len(FAILS)} FALLOS'}")
sys.exit(1 if FAILS else 0)
