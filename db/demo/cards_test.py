#!/usr/bin/env python3
"""Prueba de PIN, tarjetas y notificaciones (06_access, 08_cards), como clientes.

Como en payments_test.py, cada comprobación mira el EFECTO real como root.

    python3 db/demo/cards_test.py

Requiere haber cargado 01_seed.surql y lo deja ensuciado.
"""
import sys

from session import api, last, root_last, signin

FAILS = []


def check(name, cond, got):
    print(f"  [{'ok   ' if cond else 'FALLA'}] {name}")
    if not cond:
        print(f"          obtenido: {got}")
        FAILS.append(name)


def one(sql):
    r = root_last(sql)
    return r[0] if isinstance(r, list) and r else r


def bal(acc):
    return float(one(f"SELECT VALUE balance FROM {acc};"))


def charge(card, amount, merchant="Tienda"):
    return one(f"RETURN fn::charge_card({card}, {amount}dec, '{merchant}', (-3.70, 40.41));")


ana = signin("ana@dominican.test", "demo-ana")
luis = signin("luis@dominican.test", "demo-luis")
marta = signin("marta@dominican.test", "demo-marta")

print("PIN")
st, b = api(ana, "/verify-pin", {"pin": "0000"})
check("PIN incorrecto: 401 y quedan 2 intentos", (st, b.get("attempts_left")) == (401, 2), (st, b))
check("…y el fallo queda GUARDADO aunque se rechace", one("SELECT VALUE pin_failures FROM app_user:ana;") == 1,
      one("SELECT VALUE pin_failures FROM app_user:ana;"))
last(ana, "UPDATE app_user:ana SET pin_failures = 0;")
check("ana no puede borrarse los fallos a mano", one("SELECT VALUE pin_failures FROM app_user:ana;") == 1,
      one("SELECT VALUE pin_failures FROM app_user:ana;"))
st, b = api(ana, "/verify-pin", {"pin": "1234"})
check("PIN correcto: 200 con la ventana", st == 200 and "verified_until" in b, (st, b))
check("…y pone los fallos a cero", one("SELECT VALUE pin_failures FROM app_user:ana;") == 0,
      one("SELECT VALUE pin_failures FROM app_user:ana;"))
r = last(ana, "SELECT VALUE pan FROM card:ana;")
check("verificada, ana ve el PAN", r == ["4111111111114242"], r)

for _ in range(2):
    api(ana, "/verify-pin", {"pin": "9999"})
st, b = api(ana, "/verify-pin", {"pin": "9999"})
check("al tercer fallo seguido: 423 bloqueado", (st, b.get("error")) == (423, "pin_locked"), (st, b))
st, b = api(ana, "/verify-pin", {"pin": "1234"})
check("bloqueado, ni el PIN correcto abre la ventana", st == 423, (st, b))
check("el bloqueo está guardado y es futuro",
      one("RETURN (SELECT VALUE pin_locked_until FROM ONLY app_user:ana) > time::now();") is True,
      one("SELECT VALUE pin_locked_until FROM app_user:ana;"))
root_last("UPDATE app_user:ana SET pin_locked_until = time::now() - 1s;")
st, b = api(ana, "/verify-pin", {"pin": "1234"})
check("pasado el bloqueo, el PIN correcto vuelve a funcionar", st == 200, (st, b))
st, b = api(ana, "/verify-pin", {"pin": "12345"})
check("PIN que no son 4 cifras: 400", st == 400, (st, b))
st, b = api(None, "/verify-pin", {"pin": "1234"})
check("sin sesión: 403", st == 403, (st, b))

print("\ncobro con tarjeta")
a0, e0 = bal("account:ana"), bal("account:ext")
p = charge("card:ana", 30, "Café")
check("un cobro normal se aprueba", p.get("status") == "approved", p)
check("…y mueve el dinero de verdad (antes no movía nada)",
      bal("account:ana") == a0 - 30 and bal("account:ext") == e0 + 30, (bal("account:ana"), bal("account:ext")))

print("\nbloqueo")
st, b = api(ana, "/cards/block", {"card": "card:ana", "blocked": True})
check("ana bloquea su tarjeta (200)", (st, b.get("blocked")) == (200, True), (st, b))
a1 = bal("account:ana")
p = charge("card:ana", 20, "Gasolinera")
check("con la tarjeta bloqueada el cobro se deniega", (p.get("status"), p.get("reason")) == ("declined", "card_blocked"), p)
check("…sin mover dinero", bal("account:ana") == a1, bal("account:ana"))
check("…y el intento queda registrado", one("SELECT VALUE count() FROM card_payment WHERE card = card:ana AND reason = 'card_blocked' GROUP ALL;") == 1,
      root_last("SELECT * FROM card_payment WHERE card = card:ana;"))
r = last(ana, "SELECT VALUE [kind, reason] FROM notification WHERE kind = 'card_declined';")
check("…y ana recibe el aviso de pago denegado", r == [["card_declined", "card_blocked"]], r)
api(ana, "/cards/block", {"card": "card:ana", "blocked": False})
check("desbloqueada, vuelve a cobrar", charge("card:ana", 5).get("status") == "approved", None)

st, b = api(luis, "/cards/block", {"card": "card:ana", "blocked": True})
check("luis, cotitular de la cuenta, NO puede bloquear la tarjeta de ana (404)", st == 404, (st, b))
st, b = api(marta, "/cards/block", {"card": "card:ana", "blocked": True})
check("marta tampoco, y recibe lo mismo que si no existiera", (st, b) == (404, {"error": "card_not_found"}), (st, b))
check("…la tarjeta sigue desbloqueada", one("SELECT VALUE blocked FROM card:ana;") is False,
      one("SELECT VALUE blocked FROM card:ana;"))
r = last(ana, "UPDATE card:ana SET blocked = true;")
check("ana no puede tocar la tarjeta salvo por el endpoint", one("SELECT VALUE blocked FROM card:ana;") is False, r)

print("\nlímite mensual")
st, b = api(luis, "/cards/limit", {"card": "card:luis", "monthly_limit": "100.00"})
check("luis pone su límite en 100 € (200)", (st, b.get("monthly_limit")) == (200, "100"), (st, b))
check("cobro de 60 € dentro del límite: aprobado", charge("card:luis", 60).get("status") == "approved", None)
p = charge("card:luis", 50)
check("50 € más superan los 100: denegado", (p.get("status"), p.get("reason")) == ("declined", "monthly_limit_exceeded"), p)
check("40 € más lo dejan justo en 100: aprobado", charge("card:luis", 40).get("status") == "approved", None)
st, b = api(luis, "/cards/limit", {"card": "card:luis", "monthly_limit": "10000.01"})
check("límite por encima del máximo del banco: 422", st == 422, (st, b))
st, b = api(luis, "/cards/limit", {"card": "card:luis", "monthly_limit": "0"})
check("límite cero: 422", st == 422, (st, b))
st, b = api(luis, "/cards/limit", {"card": "card:luis", "monthly_limit": 500})
check("límite como número JSON: 400", st == 400, (st, b))

p = charge("card:luis", 999999)
check("sin saldo suficiente: denegado", p.get("status") == "declined", p)

print("\nnotificaciones")
root_last("DELETE notification;")
api(ana, "/transfers", {"id": "n-transfer-01", "from": "account:ana",
                        "to_iban": "ES3333333333333333333333", "amount": "12.00", "concept": "regalo"})
r = last(marta, "SELECT VALUE [kind, <string>amount, concept] FROM notification;")
check("marta recibe el aviso de ingreso con su concepto", r == [["incoming", "12", "regalo"]], r)
r = last(ana, "SELECT VALUE kind FROM notification;")
check("ana, que paga, recibe el aviso de gasto", r == ["expense"], r)
r = last(luis, "SELECT VALUE kind FROM notification;")
check("luis también: es cotitular de la cuenta que paga", r == ["expense"], r)
root_last("RETURN fn::credit(account:marta, 2300dec, 'payroll');")
r = last(marta, "SELECT VALUE kind FROM notification ORDER BY at;")
check("la nómina llega como aviso de nómina", r == ["incoming", "payroll"], r)
r = last(ana, "SELECT VALUE kind FROM notification WHERE customer = customer:marta;")
check("ana no ve los avisos de marta", r == [], r)

n = one("SELECT VALUE id FROM notification WHERE customer = customer:ana;")
last(ana, f"UPDATE {n} SET read = true;")
check("ana marca su aviso como leído", one(f"SELECT VALUE read FROM {n};") is True, one(f"SELECT * FROM {n};"))
last(ana, f"UPDATE {n} SET amount = 999999dec, customer = customer:marta;")
r = one(f"SELECT VALUE [<string>amount, customer] FROM {n};")
check("…pero no puede cambiar el importe ni pasárselo a otro", r == ["12", "customer:ana"], r)
before = one("SELECT VALUE count() FROM notification GROUP ALL;")
last(ana, "CREATE notification SET customer = customer:ana, kind = 'payroll', amount = 1000000dec;")
check("ana no puede fabricarse avisos", one("SELECT VALUE count() FROM notification GROUP ALL;") == before,
      one("SELECT VALUE count() FROM notification GROUP ALL;"))

rec = root_last("RETURN fn::reconcile();")
check("al final, el saldo materializado cuadra con el libro de apuntes", rec == [], rec)

print(f"\n{'TODO EN ORDEN' if not FAILS else f'{len(FAILS)} FALLOS'}")
sys.exit(1 if FAILS else 0)
