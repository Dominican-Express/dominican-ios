#!/usr/bin/env python3
"""Prueba de la máquina del tiempo (09_time_travel): tras el encubrimiento,
la investigación de una alerta recupera lo que se borró, y los dos relojes
(libro de apuntes y versionado) dan el mismo saldo.

    python3 db/demo/time_travel_test.py

Requiere un servidor CON versionado sobre SurrealKV (`demo.sh server`,
`demo.sh studio` o `domex up`) y haber cargado 01_seed.surql. Lanza el ataque, el barrido y el
encubrimiento, y lo deja ensuciado.
"""
import subprocess
import sys
from pathlib import Path

from session import last, root_last, signin

FAILS = []
HERE = Path(__file__).resolve().parent


def check(name, cond, got):
    print(f"  [{'ok   ' if cond else 'FALLA'}] {name}")
    if not cond:
        print(f"          obtenido: {got}")
        FAILS.append(name)


def run(script):
    subprocess.run(["./surql.sh", script], cwd=HERE, capture_output=True, check=True)


def one(sql):
    r = root_last(sql)
    return r[0] if isinstance(r, list) and r else r


def num(v):
    return float(v) if v is not None else None


probe = root_last("SELECT id FROM account VERSION time::now();")
if not isinstance(probe, list):
    print(f"  [FALLA] el servidor tiene versionado\n          obtenido: {probe}")
    print("\n1 FALLOS")
    sys.exit(1)

# Trampas para el fallo surrealdb#7601: relaciones que se deshicieron ANTES de la
# alerta. Un recorrido con VERSION las sigue devolviendo; cada una vigila uno de
# los cuatro sitios donde la investigación confirma por id.
root_last("CREATE device:old SET fingerprint = 'old'; "
          "RELATE customer:jose->uses->device:old; "                         # aparatos de una persona
          "RELATE customer:sara->uses->device:movil_ana; "                   # usuarios de un aparato
          "RELATE customer:sara->owns->account:jose SET role = 'cotitular'; "   # titulares de una cuenta
          "RELATE customer:marta->owns->account:sara SET role = 'cotitular'; "  # cuentas de una persona
          "DELETE uses WHERE in = customer:jose AND out = device:old; "
          "DELETE uses WHERE in = customer:sara AND out = device:movil_ana; "
          "DELETE owns WHERE in = customer:sara AND out = account:jose; "
          "DELETE owns WHERE in = customer:marta AND out = account:sara;")
run("02_attack.surql")
run("03_detect.surql")
ring = one("SELECT VALUE id FROM fraud_alert WHERE kind = 'mule_ring' AND account = account:marta;")
dev = one("SELECT VALUE id FROM fraud_alert WHERE kind = 'shared_device';")
at = one(f"SELECT VALUE at FROM {ring};")
run("04_coverup.surql")

print("El encubrimiento borra el rastro del grafo actual")
check("el móvil compartido ya no existe", root_last("SELECT id FROM device:mula;") == [],
      root_last("SELECT id FROM device:mula;"))
check("luis ya no figura como titular de la cuenta de ana",
      "customer:luis" not in (one("SELECT VALUE <-owns<-customer FROM account:ana;") or []),
      one("SELECT VALUE <-owns<-customer FROM account:ana;"))

print("La investigación lo recupera")
inv_dev = one(f"RETURN fn::investigate({dev});")
inv_ring = one(f"RETURN fn::investigate({ring});")
gone = [c for c in (inv_dev or {}).get("changes", []) if c.get("change") == "device_deleted"]
check("el móvil borrado reaparece, con sus 4 usuarios",
      len(gone) == 1 and gone[0]["device"] == "device:mula" and len(gone[0]["used_by"]) == 4, inv_dev)
print("Sin pruebas falsas: lo deshecho ANTES de la alerta no aparece")
# ¿Este motor reproduce el fallo? Si no, las trampas no tienen nada que cazar y
# la prueba en rojo de la confirmación por id no puede caer (medido: en memoria).
dat0 = one(f"SELECT VALUE at FROM {dev};")
raw = root_last(f"SELECT VALUE <-owns<-customer FROM ONLY account:jose VERSION d'{dat0}';")
if "customer:sara" not in (raw or []):
    print("  [aviso] este motor no reproduce surrealdb#7601: usa SurrealKV (demo.sh server)")
devs = {d["id"]: d for d in (inv_dev or {}).get("devices", [])}
check("el aparato que jose dejó antes no sale en su investigación", "device:old" not in devs, list(devs))
check("sara, que dejó el móvil de ana antes, no figura como usuaria",
      devs.get("device:movil_ana", {}).get("users_then") == ["customer:ana"], devs.get("device:movil_ana"))
dev_accs = {a["id"]: a for a in (inv_dev or {}).get("accounts", [])}
check("sara, que dejó de ser cotitular de jose antes, no figura como titular",
      dev_accs.get("account:jose", {}).get("owners_then") == ["customer:jose"], dev_accs.get("account:jose"))
check("la cuenta de sara, de la que marta salió antes, no entra en la investigación",
      "account:sara" not in dev_accs, list(dev_accs))
# El fallo depende del camino de ejecución: dentro de un `.map` no aparece y en
# una llamada directa sí (medido). Por eso los ayudantes se prueban directamente.
dat = one(f"SELECT VALUE at FROM {dev};")
r = root_last(f"RETURN fn::owners_at(account:jose, d'{dat}');")
check("fn::owners_at, llamada directa: tampoco pone a sara como titular de jose", r == ["customer:jose"], r)
r = root_last(f"RETURN fn::users_at(device:movil_ana, d'{dat}');")
check("fn::users_at, llamada directa: tampoco pone a sara en el móvil de ana", r == ["customer:ana"], r)
accs = {a["id"]: a for a in (inv_ring or {}).get("accounts", [])}
ana = accs.get("account:ana", {})
check("luis era cotitular de la cuenta de ana cuando saltó la alerta…",
      "customer:luis" in ana.get("owners_then", []), ana)
check("…y ya no lo es", "customer:luis" not in ana.get("owners_now", ["customer:luis"]), ana)
marta = accs.get("account:marta", {})
check("marta tenía dinero entonces y ahora 0",
      (num(marta.get("balance_then")) or 0) > 0 and num(marta.get("balance_now")) == 0, marta)
changes = (inv_ring or {}).get("changes", [])
check("los cambios no acusan a una cuenta que no se tocó (jose)",
      all("account:jose" not in str(c) for c in changes if c.get("change") != "device_deleted"), changes)

print("Dos relojes, un mismo saldo")
for acc, a in accs.items():
    ledger = num(one(f"RETURN fn::balance_at({acc}, d'{at}');"))
    check(f"{acc}: el libro a la hora de la alerta = lo que guardaba el versionado",
          ledger == num(a.get("balance_then")), (ledger, a.get("balance_then")))
now = [root_last(f"RETURN [fn::balance_at({x}, time::now()), fn::balance({x})];") for x in accs]
check("el saldo de hoy desde el libro = fn::balance", all(num(a) == num(b) for a, b in now), now)
check("antes de existir, la cuenta tenía 0",
      num(one("RETURN fn::balance_at(account:ana, d'2000-01-01T00:00:00Z');")) == 0,
      one("RETURN fn::balance_at(account:ana, d'2000-01-01T00:00:00Z');"))

print("Solo el equipo antifraude")
t = signin("ana@dominican.test", "demo-ana")
# Con una alerta de SU cuenta: la de marta ya se la tapan los permisos de
# fraud_alert, y el test no vigilaría el permiso de la función.
own = one("SELECT VALUE id FROM fraud_alert WHERE kind = 'mule_ring' AND account = account:ana;")
r = last(t, f"RETURN fn::investigate({own});")
# El rechazo tiene que ser en la PUERTA de fn::investigate: si la abriera, los
# ayudantes de dentro también la frenan, y el test no distinguiría las capas.
check("ana no puede investigar alertas, ni las de su cuenta",
      isinstance(r, str) and "fn::investigate" in r, r)
r = last(t, "RETURN fn::balance_at(account:marta, time::now());")
check("ana no puede consultar el saldo histórico de otra cuenta", r in (None, []) or isinstance(r, str), r)

print(f"\n{'TODO EN ORDEN' if not FAILS else f'{len(FAILS)} FALLOS'}")
sys.exit(1 if FAILS else 0)
