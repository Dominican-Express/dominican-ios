#!/usr/bin/env python3
"""Prueba de permisos: actúa como usuarios de la app, nunca como root.

Un control de acceso no está puesto hasta que se intenta saltar. Por eso cada
permiso tiene su caso positivo, su caso negativo y su ataque.

    python3 db/demo/access_test.py            # rápido
    python3 db/demo/access_test.py --expiry   # espera 91 s y comprueba la caducidad

Requiere haber cargado 01_seed.surql. No modifica datos de negocio.
"""
import sys
import time

from session import last, root_last, signin

FAILS = []


def check(name, cond, got):
    mark = "ok   " if cond else "FALLA"
    print(f"  [{mark}] {name}")
    if not cond:
        print(f"          obtenido: {got}")
        FAILS.append(name)


def card(token, card_id):
    rows = last(token, f"SELECT pan, cvv, pan_last4 FROM {card_id};")
    return rows[0] if isinstance(rows, list) and rows else rows


print("ana — titular de account:ana (conjunta con luis), lleva card:ana")
ana = signin("ana@dominican.test", "demo-ana")

c = card(ana, "card:ana")
check("ve su tarjeta, pero sin PAN ni CVV", c.get("pan_last4") == "4242" and c.get("pan") is None, c)

r = last(ana, "RETURN fn::verify_step_up('0000');")
check("PIN incorrecto: la verificación se rechaza", str(r).startswith("ERROR") and "PIN" in str(r), r)
check("…y el PAN sigue oculto", card(ana, "card:ana").get("pan") is None, card(ana, "card:ana"))

r = last(ana, "RETURN fn::verify_step_up('1234');")
check("PIN correcto: la verificación se acepta", r is True, r)
c = card(ana, "card:ana")
check("ahora ve PAN y CVV", c.get("pan") == "4111111111114242" and c.get("cvv") == "123", c)

# Como root: ana no tiene permiso de lectura sobre step_up, así que vería []
# aunque la fila existiera. Ese test pasaría con el fallo puesto.
r = root_last("SELECT * FROM step_up;")
check("la petición con el PIN en claro no queda guardada", r == [], r)

u = last(ana, "SELECT * FROM app_user:ana;")[0]
check("no puede leer su propio hash de contraseña", "pass" not in u, u)
check("no puede leer su propio hash de PIN", "pin" not in u, u)

print("\nana — ataques")
last(ana, "UPDATE app_user:ana SET verified_until = d'3000-01-01T00:00:00Z';")
u = last(ana, "SELECT verified_until FROM app_user:ana;")[0]
check("no puede alargarse la ventana a mano", not str(u.get("verified_until", "")).startswith("3000"), u)

last(ana, "UPDATE app_user:ana SET customer = customer:marta;")
r = last(ana, "SELECT id FROM account:marta;")
check("no puede cambiarse de titular para ver otra cuenta", r == [], r)

r = last(ana, "SELECT id FROM account WHERE id = account:marta OR id = account:jose;")
check("no ve cuentas ajenas", r == [], r)

# ana conoce el PIN de luis e intenta abrirle la ventana a él. Lo que importa
# es el EFECTO, que se mira como root: si `user` fuera falsificable, el evento
# compararía el PIN de luis, acertaría y le abriría la ventana.
last(ana, "CREATE step_up SET user = app_user:luis, pin = '5678';")
r = root_last("SELECT VALUE verified_until FROM app_user:luis;")
check("no puede pedir la verificación de otro usuario", r == [None], r)

print("\nluis — cotitular de account:ana; lleva card:luis, NO card:ana")
luis = signin("luis@dominican.test", "demo-luis")

r = last(luis, "SELECT VALUE id FROM account ORDER BY id;")
check("ve la cuenta conjunta y la suya, nada más",
      sorted(r) == ["account:ana", "account:luis"], r)

c = card(luis, "card:ana")
check("ve que existe la tarjeta de la cuenta conjunta", c.get("pan_last4") == "4242", c)

last(luis, "RETURN fn::verify_step_up('5678');")
c = card(luis, "card:ana")
check("verificado, sigue SIN ver el PAN de la tarjeta de ana", c.get("pan") is None, c)
c = card(luis, "card:luis")
check("…pero sí el de la suya", c.get("pan") == "4111111111111010", c)

print("\nalertas — cada titular ve las suyas y solo las suyas")
# Se provoca un viaje imposible con la tarjeta de ana, como root (es el banco
# quien registra el pago, no el cliente).
root_last("""CREATE card_payment SET card = card:ana, amount = 10dec,
                 loc = (-3.7038, 40.4168), at = time::now() - 20m;
             CREATE card_payment SET card = card:ana, amount = 10dec,
                 loc = (-74.0060, 40.7128), at = time::now() - 10m;""")
r = last(ana, "SELECT VALUE kind FROM fraud_alert;")
check("ana ve la alerta de viaje imposible de su tarjeta", "impossible_travel" in r, r)
root_last("CREATE fraud_alert SET kind = 'structuring', score = 0.7, account = account:marta;")
r = last(ana, "SELECT VALUE account FROM fraud_alert;")
check("ana no ve alertas de cuentas ajenas", "account:marta" not in r, r)

if "--expiry" in sys.argv:
    print("\ncaducidad — esperando 91 s")
    time.sleep(91)
    check("pasada la ventana, el PAN vuelve a ocultarse",
          card(ana, "card:ana").get("pan") is None, card(ana, "card:ana"))

print(f"\n{'TODO EN ORDEN' if not FAILS else f'{len(FAILS)} FALLOS'}")
sys.exit(1 if FAILS else 0)
