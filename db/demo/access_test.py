#!/usr/bin/env python3
"""Prueba de permisos: actúa como usuarios de la app, nunca como root.

Un control de acceso no está puesto hasta que se intenta saltar. Por eso cada
permiso tiene su caso positivo, su caso negativo y su ataque.

    python3 db/demo/access_test.py            # rápido
    python3 db/demo/access_test.py --expiry   # espera 91 s y comprueba la caducidad

Requiere haber cargado 01_seed.surql. No modifica datos de negocio.
"""
import json
import os
import sys
import threading
import time

from session import DB, NS, _post, api, last, root_last, signin

FAILS = []

# DEMO_LANG=en para presentar en inglés (lo usa `demo.sh access`).
EN = {
    "ana — titular de account:ana (conjunta con luis), lleva card:ana":
        "ana: holder of account:ana (joint with luis), carries card:ana",
    "ve su tarjeta, pero sin PAN ni CVV": "sees her card, but no card number or CVV",
    "PIN incorrecto: la verificación se rechaza": "wrong PIN: verification refused",
    "…y el PAN sigue oculto": "and the card number stays hidden",
    "PIN correcto: la verificación se acepta": "right PIN: verification accepted",
    "ahora ve PAN y CVV": "now she sees card number and CVV",
    "el PIN se guarda solo como hash argon2, nunca en claro": "the PIN is stored only as an argon2 hash, never in clear",
    "no puede leer su propio hash de contraseña": "cannot read her own password hash",
    "no puede leer su propio hash de PIN": "cannot read her own PIN hash",
    "ana — ataques": "ana: attacks",
    "no puede alargarse la ventana a mano": "cannot extend her PIN window by hand",
    "no puede cambiarse de titular para ver otra cuenta": "cannot change her customer to see another account",
    "no ve cuentas ajenas": "does not see other people's accounts",
    "no puede pedir la verificación de otro usuario": "cannot verify the PIN of another user",
    "luis — cotitular de account:ana; lleva card:luis, NO card:ana":
        "luis: co-holder of account:ana; carries card:luis, NOT card:ana",
    "ve la cuenta conjunta y la suya, nada más": "sees the joint account and his own, nothing else",
    "ve que existe la tarjeta de la cuenta conjunta": "sees that the joint account has a card",
    "verificado, sigue SIN ver el PAN de la tarjeta de ana": "after his PIN, still NO card number for ana's card",
    "…pero sí el de la suya": "but he does see his own",
    "alertas — cada titular ve las suyas y solo las suyas": "alerts: each holder sees their own, and only their own",
    "ana ve la alerta de viaje imposible de su tarjeta": "ana sees the impossible travel alert on her card",
    "ana no ve alertas de cuentas ajenas": "ana does not see alerts on other accounts",
    "inicio de sesión — límite de intentos": "sign-in: attempt limit",
    "4 contraseñas incorrectas: la cuenta sigue abierta": "4 wrong passwords: the account stays open",
    "un acierto pone el contador a cero": "a correct one resets the counter",
    "5 incorrectas seguidas bloquean la cuenta": "5 wrong in a row lock the account",
    "bloqueada, rechaza incluso la contraseña correcta": "locked, it refuses even the right password",
    "un acierto deja constancia en la ficha (last_login_at)": "a correct one is recorded (last_login_at)",
    "10 intentos a la vez: cada «incorrecta» que recibe el cliente queda contada":
        "10 attempts at once: every 'wrong' the client receives is counted",
    "un email que no existe se rechaza igual": "an unknown email is refused the same way",
    "caducidad — esperando 91 s": "expiry: waiting 91 s",
    "pasada la ventana, el PAN vuelve a ocultarse": "after the window, the card number is hidden again",
    "TODO EN ORDEN": "ALL CORRECT",
}


def T(s):
    return EN.get(s, s) if os.environ.get("DEMO_LANG") == "en" else s


def check(name, cond, got):
    mark = "ok   " if cond else "FALLA"
    print(f"  [{mark}] {T(name)}")
    if not cond:
        print(f"          obtenido: {got}")
        FAILS.append(name)


def card(token, card_id):
    rows = last(token, f"SELECT pan, cvv, pan_last4 FROM {card_id};")
    return rows[0] if isinstance(rows, list) and rows else rows


print("" + T("ana — titular de account:ana (conjunta con luis), lleva card:ana"))
ana = signin("ana@dominican.test", "demo-ana")

c = card(ana, "card:ana")
check("ve su tarjeta, pero sin PAN ni CVV", c.get("pan_last4") == "4242" and c.get("pan") is None, c)

st, r = api(ana, "/verify-pin", {"pin": "0000"})
check("PIN incorrecto: la verificación se rechaza", st == 401, (st, r))
check("…y el PAN sigue oculto", card(ana, "card:ana").get("pan") is None, card(ana, "card:ana"))

st, r = api(ana, "/verify-pin", {"pin": "1234"})
check("PIN correcto: la verificación se acepta", st == 200, (st, r))
c = card(ana, "card:ana")
check("ahora ve PAN y CVV", c.get("pan") == "4111111111114242" and c.get("cvv") == "123", c)

# El PIN viaja en el cuerpo de la petición y no se escribe en ninguna tabla.
# Lo único guardado es su hash, y se comprueba como root.
r = root_last("SELECT VALUE [string::starts_with(pin, '$argon2'), pin = '1234'] FROM app_user:ana;")
check("el PIN se guarda solo como hash argon2, nunca en claro", r == [[True, False]], r)

u = last(ana, "SELECT * FROM app_user:ana;")[0]
check("no puede leer su propio hash de contraseña", "pass" not in u, u)
check("no puede leer su propio hash de PIN", "pin" not in u, u)

print("\n" + T("ana — ataques"))
last(ana, "UPDATE app_user:ana SET verified_until = d'3000-01-01T00:00:00Z';")
u = last(ana, "SELECT verified_until FROM app_user:ana;")[0]
check("no puede alargarse la ventana a mano", not str(u.get("verified_until", "")).startswith("3000"), u)

last(ana, "UPDATE app_user:ana SET customer = customer:marta;")
r = last(ana, "SELECT id FROM account:marta;")
check("no puede cambiarse de titular para ver otra cuenta", r == [], r)

r = last(ana, "SELECT id FROM account WHERE id = account:marta OR id = account:jose;")
check("no ve cuentas ajenas", r == [], r)

# ana conoce el PIN de luis e intenta abrirle la ventana a él. Lo que importa
# es el EFECTO, que se mira como root: si el endpoint hiciera caso a un `user`
# del cuerpo, compararía el PIN de luis, acertaría y le abriría la ventana.
api(ana, "/verify-pin", {"pin": "5678", "user": "app_user:luis"})
r = root_last("SELECT VALUE verified_until FROM app_user:luis;")
check("no puede pedir la verificación de otro usuario", r == [None], r)

print("\n" + T("luis — cotitular de account:ana; lleva card:luis, NO card:ana"))
luis = signin("luis@dominican.test", "demo-luis")

r = last(luis, "SELECT VALUE id FROM account ORDER BY id;")
check("ve la cuenta conjunta y la suya, nada más",
      sorted(r) == ["account:ana", "account:luis"], r)

c = card(luis, "card:ana")
check("ve que existe la tarjeta de la cuenta conjunta", c.get("pan_last4") == "4242", c)

api(luis, "/verify-pin", {"pin": "5678"})
c = card(luis, "card:ana")
check("verificado, sigue SIN ver el PAN de la tarjeta de ana", c.get("pan") is None, c)
c = card(luis, "card:luis")
check("…pero sí el de la suya", c.get("pan") == "4111111111111010", c)

print("\n" + T("alertas — cada titular ve las suyas y solo las suyas"))
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

print("\n" + T("inicio de sesión — límite de intentos"))


def signin_status(email, password):
    res = _post("/signin", json.dumps({"ns": NS, "db": DB, "ac": "banca",
                                       "email": email, "pass": password}),
                {"Content-Type": "application/json"})
    return res.get("http_error", 200) if isinstance(res, dict) else res


def try_signin(email, password):
    try:
        return signin(email, password) is not None
    except RuntimeError:
        return False


fails = [try_signin("marta@dominican.test", "mal") for _ in range(4)]
check("4 contraseñas incorrectas: la cuenta sigue abierta",
      not any(fails) and try_signin("marta@dominican.test", "demo-marta"), fails)
# Si el acierto no pusiera el contador a cero, estos 4 harían 8 y bloquearían.
fails = [try_signin("marta@dominican.test", "mal") for _ in range(4)]
check("un acierto pone el contador a cero", try_signin("marta@dominican.test", "demo-marta"), fails)
fails = [try_signin("marta@dominican.test", "mal") for _ in range(5)]
r = root_last("SELECT VALUE login_locked_until FROM ONLY app_user:marta;")
check("5 incorrectas seguidas bloquean la cuenta", not any(fails) and r is not None, r)
check("bloqueada, rechaza incluso la contraseña correcta",
      not try_signin("marta@dominican.test", "demo-marta"), "aceptada")
# Intentos a la vez: el aislamiento deshace los que chocan (400). Lo que no
# puede pasar es que el cliente reciba un «incorrecta» (404) que no se cuente.
ok = root_last("SELECT VALUE last_login_at FROM ONLY app_user:luis;")
check("un acierto deja constancia en la ficha (last_login_at)", ok is not None, ok)
answers = []


def burst(pw):
    answers.append(signin_status("luis@dominican.test", pw))


threads = [threading.Thread(target=burst, args=("mal",)) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()
r = root_last("SELECT VALUE login_failures FROM ONLY app_user:luis;")
check("10 intentos a la vez: cada «incorrecta» que recibe el cliente queda contada",
      answers.count(404) == r and r >= 1, (sorted(answers), r))
check("un email que no existe se rechaza igual", not try_signin("nadie@dominican.test", "x"), "aceptado")
root_last("UPDATE app_user SET login_failures = 0, login_locked_until = NONE;")

if "--expiry" in sys.argv:
    print("\n" + T("caducidad — esperando 91 s"))
    time.sleep(91)
    check("pasada la ventana, el PAN vuelve a ocultarse",
          card(ana, "card:ana").get("pan") is None, card(ana, "card:ana"))

print("\n" + (T("TODO EN ORDEN") if not FAILS else f"{len(FAILS)} FALLOS"))
sys.exit(1 if FAILS else 0)
