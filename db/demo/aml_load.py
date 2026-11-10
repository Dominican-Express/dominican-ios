#!/usr/bin/env python3
"""Carga el dataset de IBM "Transactions for Anti Money Laundering" en una base
aparte (por defecto dx/aml) para medir el detector de anillos contra datos con
la respuesta conocida.

    python3 db/demo/aml_load.py --data DIR [--set HI-Small] [--db aml] [--limit N]

DIR contiene <set>_Trans.csv, <set>_accounts.csv y <set>_Patterns.txt
(ver db/demo/aml_fetch.sh). Datos de IBM bajo CDLA-Sharing-1.0.

Qué se carga y por qué:
  - Solo el núcleo, el grafo y los detectores (01, 02, 05): es una copia
    analítica, sin API, permisos ni auditoría. Importar 5 millones de filas por
    la API de pagos dispararía la auditoría y las alertas de cada operación.
  - Importes en EUR con tipos de cambio sacados del propio dataset (mediana de
    las transacciones entre dos divisas): la regla de reenvío compara importes
    de saltos que van en divisas distintas.
  - Sin autotransferencias (misma cuenta a misma cuenta): no son un movimiento
    entre cuentas y en un grafo serían bucles sin significado.
  - La etiqueta va en `aml_truth`, no en la transferencia: el detector no
    puede verla ni por accidente.
  - IDs deterministas (fila del CSV): recargar no duplica nada.
"""
import argparse
import csv
import hashlib
import http.client
import json
import os
import sys
import time
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aml_common import eur_rates, key, read_patterns  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, "..", "schema")
URL = os.environ.get("SURREAL_URL", "http://127.0.0.1:8099")
NS = os.environ.get("SURREAL_NS", "dx")
AUTH = "Basic " + __import__("base64").b64encode(
    f"{os.environ.get('SURREAL_USER', 'root')}:{os.environ.get('SURREAL_PASS', 'root')}".encode()).decode()

_u = urlparse(URL)
_conn = http.client.HTTPConnection(_u.hostname, _u.port, timeout=600)


def sql(text, db=None):
    headers = {"Accept": "application/json", "Authorization": AUTH, "surreal-ns": NS}
    if db:
        headers["surreal-db"] = db
    _conn.request("POST", "/sql", body=text.encode(), headers=headers)
    out = json.loads(_conn.getresponse().read())
    if isinstance(out, dict):
        raise SystemExit(f"error del servidor: {out}")
    bad = [s for s in out if s.get("status") != "OK"]
    if bad:
        raise SystemExit(f"sentencia fallida: {str(bad[0].get('result'))[:300]}")
    return out


def rec(table, k):
    return f"{table}:⟨{k}⟩"


def iban(k):
    # IBAN sintético y estable: el esquema exige ^ES[0-9]{22}$ y unicidad.
    return "ES" + str(int(hashlib.sha1(k.encode()).hexdigest(), 16) % 10**22).zfill(22)


def ts(s):  # 2022/09/01 00:06 -> d'2022-09-01T00:06:00Z'
    return f"d'{s[:4]}-{s[5:7]}-{s[8:10]}T{s[11:16]}:00Z'"


def batches(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--set", default="HI-Small")
    ap.add_argument("--db", default="aml")
    ap.add_argument("--limit", type=int, default=0, help="solo las N primeras filas (pruebas)")
    ap.add_argument("--batch", type=int, default=2000)
    ap.add_argument("--rows", help="cargar solo estas filas (salida de aml_prefilter.py) "
                                   "+ las de los patrones de IBM + --background de fondo")
    ap.add_argument("--background", type=int, default=20000,
                    help="con --rows: nº aproximado de transferencias normales de fondo")
    a = ap.parse_args()
    trans = os.path.join(a.data, f"{a.set}_Trans.csv")
    pats = read_patterns(os.path.join(a.data, f"{a.set}_Patterns.txt"))
    chosen = {int(x) for x in open(a.rows).read().split()} if a.rows else None
    total = sum(1 for _ in open(trans)) - 1 if a.rows else 0

    def wanted(n, t):
        """Sin --rows, todo. Con --rows: candidatas, filas de patrones y una
        muestra fija de fondo (misma fila → misma decisión en cada carga)."""
        if chosen is None or n in chosen:
            return True
        if (t[0], key(t[1], t[2]), key(t[3], t[4]), t[7]) in pats:
            return True
        return (n * 2654435761) % 2**32 < a.background / total * 2**32

    # 1.ª pasada: tipos de cambio, cuentas usadas y divisa de cada cuenta
    t0 = time.time()
    acc_cur = {}
    rows = selfx = 0
    with open(trans, newline="") as f:
        r = csv.reader(f)
        next(r)
        for t in r:
            if a.limit and rows >= a.limit:
                continue
            rows += 1
            if not wanted(rows, t):
                continue
            src, dst = key(t[1], t[2]), key(t[3], t[4])
            if src == dst:
                selfx += 1
                continue
            acc_cur.setdefault(src, t[8])
            acc_cur.setdefault(dst, t[6])
    # los tipos de cambio salen siempre del conjunto entero, también con --limit
    to_eur = eur_rates(trans)
    missing = {c for c in acc_cur.values()} - set(to_eur)
    if missing:
        raise SystemExit(f"sin tipo de cambio para {missing}")
    print(f"1.ª pasada: {rows} filas, {selfx} autotransferencias fuera, "
          f"{len(acc_cur)} cuentas, {time.time() - t0:.0f} s")

    # esquema
    sql(f"DEFINE NAMESPACE IF NOT EXISTS {NS}; USE NS {NS}; DEFINE DATABASE IF NOT EXISTS {a.db};")
    for f in ("01_core.surql", "02_graph.surql", "05_detectors.surql"):
        sql(open(os.path.join(SCHEMA, f)).read(), a.db)
    sql("DEFINE TABLE OVERWRITE aml_truth SCHEMALESS; "
        "DEFINE TABLE OVERWRITE aml_meta SCHEMALESS;", a.db)
    sql(f"UPSERT aml_meta:load CONTENT {json.dumps({'set': a.set, 'rows': rows, 'self_skipped': selfx, 'to_eur': to_eur})};", a.db)

    # clientes, cuentas y titularidad
    t1 = time.time()
    owner = {}
    names = {}
    with open(os.path.join(a.data, f"{a.set}_accounts.csv"), newline="") as f:
        r = csv.reader(f)
        next(r)
        for bank_name, bank_id, acct, ent_id, ent_name in r:
            k = key(bank_id, acct)
            if k in acc_cur:
                owner[k] = ent_id
                names[ent_id] = ent_name
    for chunk in batches(list(names.items()), a.batch):
        body = ",".join(f"{{id:{json.dumps(e)},name:{json.dumps(n)},nif:{json.dumps(e)}}}" for e, n in chunk)
        sql(f"INSERT IGNORE INTO customer [{body}];", a.db)
    for chunk in batches(list(acc_cur.items()), a.batch):
        body = ",".join(f"{{id:{json.dumps(k)},iban:'{iban(k)}',currency:{json.dumps(c)},kind:'customer'}}" for k, c in chunk)
        sql(f"INSERT IGNORE INTO account [{body}];", a.db)
    for chunk in batches(list(owner.items()), a.batch):
        body = ",".join(f"{{id:{json.dumps(k)},in:{rec('customer', e)},out:{rec('account', k)},role:'titular'}}" for k, e in chunk)
        sql(f"INSERT RELATION IGNORE INTO owns [{body}];", a.db)
    print(f"{len(names)} clientes, {len(acc_cur)} cuentas, {len(owner)} titularidades, {time.time() - t1:.0f} s")

    # 2.ª pasada: transferencias y verdad
    t2 = time.time()
    buf, truth = [], []
    n = loaded = laund = in_pat = 0
    with open(trans, newline="") as f:
        r = csv.reader(f)
        next(r)
        for t in r:
            n += 1
            if a.limit and n > a.limit:
                break
            src, dst = key(t[1], t[2]), key(t[3], t[4])
            if src == dst or not wanted(n, t):
                continue
            eur = float(t[7]) * to_eur[t[8]]
            buf.append(f"{{id:'r{n}',in:{rec('account', src)},out:{rec('account', dst)},"
                       f"amount:{eur:.2f}dec,at:{ts(t[0])}}}")
            if t[10] == "1":
                laund += 1
                p = pats.get((t[0], src, dst, t[7]))
                in_pat += p is not None
                truth.append(json.dumps({"id": f"r{n}", "transfer": f"r{n}", "src": src, "dst": dst,
                                         "pattern": p[0] if p else None, "attempt": p[1] if p else None}))
            if len(buf) >= a.batch:
                sql(f"INSERT RELATION IGNORE INTO transfer [{','.join(buf)}];", a.db)
                loaded += len(buf)
                buf = []
                if loaded % 200000 < a.batch:
                    rate = loaded / (time.time() - t2)
                    print(f"  {loaded} transferencias, {rate:.0f}/s", flush=True)
    if buf:
        sql(f"INSERT RELATION IGNORE INTO transfer [{','.join(buf)}];", a.db)
        loaded += len(buf)
    for chunk in batches(truth, a.batch):
        sql(f"INSERT IGNORE INTO aml_truth [{','.join(chunk)}];", a.db)
    # la verdad guarda claves de texto; se enlazan a registros aquí para poder cruzar
    sql("UPDATE aml_truth SET src = type::record('account', src), dst = type::record('account', dst), "
        "transfer = type::record('transfer', transfer) WHERE type::is_string(src);", a.db)
    dt = time.time() - t2
    print(f"{loaded} transferencias en {dt:.0f} s ({loaded / dt:.0f}/s); "
          f"blanqueo {laund} (en patrones {in_pat}, {len(pats)} filas de patrones)")


if __name__ == "__main__":
    sys.exit(main())
