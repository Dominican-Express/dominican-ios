"""Piezas comunes de los scripts del dataset de IBM (aml_*.py). Sin
dependencias: el cargador tiene que funcionar con el Python de serie."""
import csv
import json
import os
import statistics
from collections import defaultdict


def key(bank, acct):
    # El CSV de transacciones escribe el banco con ceros a la izquierda (021174)
    # y el de cuentas sin ellos: sin normalizar no casa ni una cuenta.
    return f"{int(bank)}_{acct}"


def eur_rates(trans_path):
    """{divisa: euros por unidad}. Si junto al CSV hay <set>_rates.json (la
    muestra del repo lo trae) se usa ese: los tipos salen de las ~72.000
    transacciones entre divisas del conjunto COMPLETO, y recalcularlos con una
    muestra cambiaría los importes y con ellos los anillos."""
    saved = trans_path.replace("_Trans.csv", "_rates.json")
    if os.path.exists(saved):
        return json.load(open(saved))
    pair = defaultdict(list)
    with open(trans_path, newline="") as f:
        r = csv.reader(f)
        next(r)
        for t in r:
            if t[8] != t[6] and float(t[7]) > 0:
                pair[(t[8], t[6])].append(float(t[5]) / float(t[7]))
    usd = {"US Dollar": 1.0}  # mediana de lo recibido por unidad pagada
    for (paid, recv), v in pair.items():
        if recv == "US Dollar":
            usd.setdefault(paid, statistics.median(v))
    for (paid, recv), v in pair.items():
        if paid == "US Dollar" and recv not in usd:
            usd[recv] = 1 / statistics.median(v)
    return {c: x / usd["Euro"] for c, x in usd.items()}


def read_patterns(path):
    """{(timestamp, origen, destino, importe pagado): (tipo, nº de intento)}"""
    out, kind, n = {}, None, 0
    for line in open(path):
        line = line.strip()
        if line.startswith("BEGIN"):
            n += 1
            kind = line.split(" - ")[1].split(":")[0]
        elif line.startswith("END"):
            kind = None
        elif line and kind:
            t = line.split(",")
            out[(t[0], key(t[1], t[2]), key(t[3], t[4]), t[7])] = (kind, n)
    return out
