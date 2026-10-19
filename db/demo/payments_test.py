#!/usr/bin/env python3
"""Prueba de la API de pagos (07_api.surql), actuando como clientes.

Cada comprobación mira el EFECTO real como root (saldos, apuntes, órdenes), no
solo la respuesta: un endpoint que dijera «rechazado» y moviera el dinero
igualmente pasaría si solo se mirara lo que contesta.

    python3 db/demo/payments_test.py            # funcional + ataques
    python3 db/demo/payments_test.py --race     # + concurrencia (≈20 s)

Requiere haber cargado 01_seed.surql. Lo deja ensuciado: recarga la semilla
después si vas a enseñar otra cosa.
"""
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

from session import api, last, root_last, signin

FAILS = []


def check(name, cond, got):
    print(f"  [{'ok   ' if cond else 'FALLA'}] {name}")
    if not cond:
        print(f"          obtenido: {got}")
        FAILS.append(name)


def bal(acc):
    return float(root_last(f"SELECT VALUE balance FROM ONLY {acc};"))


def oid():
    return "o-" + uuid.uuid4().hex[:16]


IBAN = {"ana": "ES1111111111111111111111", "luis": "ES2222222222222222222222",
        "marta": "ES3333333333333333333333", "jose": "ES4444444444444444444444"}

ana = signin("ana@dominican.test", "demo-ana")
luis = signin("luis@dominican.test", "demo-luis")
marta = signin("marta@dominican.test", "demo-marta")

print("transferencias")
a0, m0 = bal("account:ana"), bal("account:marta")
k = oid()
st, b = api(ana, "/transfers", {"id": k, "from": "account:ana", "to_iban": IBAN["marta"],
                                "amount": "25.00", "concept": "Cena: viernes"})
check("una transferencia válida se hace (201)", st == 201 and b["status"] == "done", (st, b))
check("…y mueve exactamente 25 € de ana a marta",
      bal("account:ana") == a0 - 25 and bal("account:marta") == m0 + 25,
      (bal("account:ana"), bal("account:marta")))
check("el concepto llega intacto, con su espacio",
      root_last(f"SELECT VALUE txn.concept FROM ONLY payment_order:`{k}`;") == "Cena: viernes",
      root_last(f"SELECT VALUE txn.concept FROM ONLY payment_order:`{k}`;"))

st2, b2 = api(ana, "/transfers", {"id": k, "from": "account:ana", "to_iban": IBAN["marta"], "amount": "25.00"})
check("repetir la MISMA orden devuelve la respuesta original…", (st2, b2) == (st, b), (st2, b2))
check("…sin pagar dos veces", bal("account:ana") == a0 - 25, bal("account:ana"))

st, b = api(ana, "/transfers", {"id": oid(), "from": "account:ana", "to_iban": IBAN["luis"],
                                "amount": "49999.00"})
check("sin saldo: 422 insufficient_funds", (st, b.get("reason")) == (422, "insufficient_funds"), (st, b))

st, b = api(ana, "/transfers", {"id": oid(), "from": "account:ana", "to_iban": IBAN["luis"],
                                "amount": "50000.01"})
check("por encima del límite por transferencia: 422", (st, b.get("reason")) == (422, "amount_over_limit"), (st, b))

st, b = api(ana, "/transfers", {"id": oid(), "from": "account:ana", "to_iban": "ES9999999999999999999999",
                                "amount": "5.00"})
check("IBAN que no es del banco: 404", (st, b.get("reason")) == (404, "destination_not_found"), (st, b))

st, b = api(ana, "/transfers", {"id": oid(), "from": "account:ana", "to_iban": IBAN["luis"], "amount": 5})
check("importe como número JSON (coma flotante): 400", (st, b.get("error")) == (400, "invalid_amount"), (st, b))

st, b = api(ana, "/transfers", {"id": oid(), "from": "account:ana", "to_iban": IBAN["luis"], "amount": "5.001"})
check("más de dos decimales: 400", st == 400, (st, b))

print("\ncotitularidad")
a1 = bal("account:ana")
st, b = api(luis, "/transfers", {"id": oid(), "from": "account:ana", "to_iban": IBAN["marta"], "amount": "10.00"})
check("luis, cotitular, puede pagar desde la cuenta conjunta", st == 201 and bal("account:ana") == a1 - 10, (st, b))

print("\nataques")
m1, a2 = bal("account:marta"), bal("account:ana")
k_attack = oid()
st, b = api(ana, "/transfers", {"id": k_attack, "from": "account:marta", "to_iban": IBAN["ana"], "amount": "50.00"})
check("ana no puede pagar desde la cuenta de marta (403)", (st, b.get("reason")) == (403, "not_your_account"), (st, b))
check("…y el dinero de marta no se mueve", bal("account:marta") == m1 and bal("account:ana") == a2,
      (bal("account:marta"), bal("account:ana")))
check("…y el intento queda registrado para auditoría",
      root_last(f"SELECT VALUE [status, reason] FROM ONLY payment_order:`{k_attack}`;") == ["rejected", "not_your_account"],
      root_last(f"SELECT * FROM ONLY payment_order:`{k_attack}`;"))

st, b = api(marta, "/transfers", {"id": k, "from": "account:marta", "to_iban": IBAN["ana"], "amount": "1.00"})
check("reutilizar el id de una orden de OTRO usuario: 409 sin revelar nada",
      st == 409 and set(b) == {"error"}, (st, b))

r = last(marta, f"SELECT * FROM payment_order:`{k}`;")
check("marta no puede leer las órdenes de ana", r == [], r)

r = last(ana, "RETURN fn::transfer(account:marta, account:ana, 100dec);")
check("un cliente no puede llamar a fn::transfer directamente",
      "permission" in str(r).lower(), r)

r = last(ana, "RETURN fn::credit(account:ana, 1000000dec, 'payroll');")
check("ni a fn::credit (darse dinero)", "permission" in str(r).lower(), r)

st, b = api(None, "/transfers", {"id": oid(), "from": "account:ana", "to_iban": IBAN["luis"], "amount": "1.00"})
check("sin sesión: 403 antes de ejecutar nada", st == 403, (st, b))

print("\nbizum")
a3, l3 = bal("account:ana"), bal("account:luis")
st, b = api(ana, "/bizum", {"id": oid(), "to_phone": "+34600000002", "amount": "10.50", "concept": "café"})
check("bizum a luis por teléfono (201)", st == 201 and b["status"] == "done", (st, b))
check("…sale de la cuenta de bizum de ana y llega a la de luis",
      bal("account:ana") == a3 - 10.5 and bal("account:luis") == l3 + 10.5,
      (bal("account:ana"), bal("account:luis")))
st, b = api(ana, "/bizum", {"id": oid(), "to_phone": "+34600000002", "amount": "1500.00"})
check("bizum por encima del límite: 422", (st, b.get("reason")) == (422, "bizum_amount_out_of_range"), (st, b))
st, b = api(ana, "/bizum", {"id": oid(), "to_phone": "+34699999999", "amount": "5.00"})
check("teléfono que no es cliente: 404", (st, b.get("reason")) == (404, "destination_not_found"), (st, b))
st, b = api(ana, "/bizum", {"id": oid(), "to_phone": "+34600000001", "amount": "5.00"})
check("bizum a uno mismo: 422", (st, b.get("reason")) == (422, "same_account"), (st, b))

print("\ncontactos")
r = last(ana, "SELECT name FROM customer:jose;")
check("antes de añadirlo, ana no ve a jose", r == [], r)
st, b = api(ana, "/contacts", {"phone": "+34600000004"})
check("añadir a jose por teléfono (201)", st == 201 and b.get("name") == "José Iglesias", (st, b))
st, b = api(ana, "/contacts", {"phone": "+34600000004"})
check("añadirlo otra vez no duplica (200)", st == 200, (st, b))
check("…una sola arista", root_last("SELECT VALUE count() FROM favorite WHERE in = customer:ana AND out = customer:jose GROUP ALL;") == [{"count": 1}],
      root_last("SELECT * FROM favorite WHERE in = customer:ana;"))
r = last(ana, "SELECT name, phone, nif, bizum_account FROM customer:jose;")[0]
check("ahora ve su nombre y su teléfono…", r.get("name") == "José Iglesias" and r.get("phone") == "+34600000004", r)
check("…pero no su NIF ni su cuenta", r.get("nif") is None and r.get("bizum_account") is None, r)
r = last(ana, "SELECT VALUE name FROM customer:luis;")
check("ve a luis sin añadirlo: es cotitular de su cuenta", r == ["Luis Romero"], r)
r = last(marta, "SELECT name FROM customer:ana;")
check("marta no ve a ana: no son contactos ni cotitulares", r == [], r)

if "--race" in sys.argv:
    print("\nconcurrencia por la API")

    def reset_ana(amount):
        root_last(f"""UPDATE account:ana SET balance = 0dec;
                      DELETE entry WHERE account = account:ana;""")
        root_last(f"RETURN fn::credit(account:ana, {amount}dec, 'payroll');")

    worst = 0
    for rnd in range(10):
        reset_ana(100)
        with ThreadPoolExecutor(10) as ex:
            res = list(ex.map(lambda _: api(ana, "/transfers", {
                "id": oid(), "from": "account:ana", "to_iban": IBAN["jose"], "amount": "100.00"}), range(10)))
        codes = sorted(s for s, _ in res)
        reasons = sorted(b.get("reason") or "" for s, b in res if s == 422)
        if bal("account:ana") != 0 or codes != [201] + [422] * 9 or set(reasons) != {"insufficient_funds"}:
            check(f"ronda {rnd}: una cuaja y las otras nueve, reintentadas, se rechazan por saldo", False,
                  (bal("account:ana"), res))
            break
    else:
        check("10 rondas × 10 órdenes distintas por todo el saldo: una 201 y nueve 422, sin conflictos sueltos",
              True, None)

    for rnd in range(10):
        reset_ana(100)
        k = oid()
        with ThreadPoolExecutor(10) as ex:
            res = list(ex.map(lambda _: api(ana, "/transfers", {
                "id": k, "from": "account:ana", "to_iban": IBAN["jose"], "amount": "30.00"}), range(10)))
        codes = {s for s, _ in res}
        if bal("account:ana") != 70 or codes != {201}:
            check(f"ronda {rnd}: 10 copias de la misma orden pagan una sola vez", False, (bal("account:ana"), res))
            break
    else:
        check("10 rondas × 10 copias simultáneas de la misma orden: se paga una vez y todas reciben 201", True, None)

    reset_ana(100)
    with ThreadPoolExecutor(10) as ex:
        res = list(ex.map(lambda _: api(ana, "/transfers", {
            "id": oid(), "from": "account:ana", "to_iban": IBAN["jose"], "amount": "100.00"}, retries=0), range(10)))
    conflicts = sum(1 for s, b in res if "conflict" in str(b).lower())
    print(f"  (sin reintento, en esa misma carrera {conflicts}/10 órdenes acaban en conflicto: "
          f"por eso el cliente reintenta)")

    rec = root_last("RETURN fn::reconcile();")
    check("al final, el saldo materializado cuadra con el libro de apuntes", rec == [], rec)

print(f"\n{'TODO EN ORDEN' if not FAILS else f'{len(FAILS)} FALLOS'}")
sys.exit(1 if FAILS else 0)
