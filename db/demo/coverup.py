#!/usr/bin/env python3
"""Las mulas intentan borrar el rastro, COMO CLIENTES, después del aviso.

Para la demo en directo, tras `demo.sh attack`. Marta (una mula del anillo)
prueba lo que haría con la app y con consultas directas. Imprime en inglés lo
que consigue y lo que no. Comprueba el efecto como root, no como Marta: lo que
ella no puede leer no demuestra que no exista.

    python3 db/demo/coverup.py
"""
from session import api, last, root_last, signin


def say(ok, text):
    print(f"  {'DONE   ' if ok else 'BLOCKED'}  {text}", flush=True)


marta = signin("marta@dominican.test", "demo-marta")
print("Marta (one of the mules) tries to cover her tracks:\n")

last(marta, "DELETE uses WHERE in = customer:marta; DELETE device:mula;")
alive = root_last("SELECT VALUE id FROM device:mula;")
say(not alive, "delete the shared phone straight from the database"
    + ("" if not alive else "  → no permission, the phone is still there"))

st, body = api(marta, "/transfers", {"id": "coverup-drain-0001", "from": "account:marta",
                                     "to_iban": "ES5555555555555555555555", "amount": "500"})
say(st == 201, f"move her money out  → HTTP {st} {body.get('reason', '')}".rstrip())

st, _ = api(marta, "/devices/unlink", {"device": "device:mula"})
ended = root_last("SELECT VALUE ended_at FROM uses WHERE in = customer:marta AND out = device:mula;")
say(False, f"unlink the phone in the app  → HTTP {st}, but it is only marked as ended "
    f"({'kept' if ended else 'missing'}), not deleted")

who = root_last("SELECT VALUE actor FROM audit_log WHERE tbl = 'uses' AND actor != NONE;")
print(f"\nThe audit log recorded it: {', '.join(who) or 'nothing'}")
