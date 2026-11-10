#!/usr/bin/env python3
"""Genera la muestra del dataset de IBM que va en el repo (db/data/ibm-aml/),
para reproducir todo sin descargar 500 MB ni pasar 3 minutos filtrando.

    python3 db/demo/aml_sample.py --data DIR --rows HI-Small_candidates_0.8_1.2_72h.txt \
        [--set HI-Small] [--background 20000] [--out db/data/ibm-aml]

Qué lleva, en el mismo formato que el original:
  - las candidatas de aml_prefilter.py (todo lo que puede ser anillo);
  - todas las filas de los patrones de blanqueo (verdad conocida);
  - ~20.000 transferencias normales de fondo, elegidas por un hash fijo de la
    fila (la misma muestra cada vez);
  - las cuentas que aparecen, el fichero de patrones entero y los tipos de
    cambio del conjunto COMPLETO (<set>_rates.json): recalcularlos con la
    muestra cambiaría los importes.

Por qué no se pierde nada: las candidatas del conjunto completo son el mayor
conjunto estable del filtro; la muestra las contiene, así que filtrar la
muestra da las mismas candidatas y los mismos anillos (se comprueba en
DATASET.md).
"""
import argparse
import csv
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aml_common import eur_rates, key, read_patterns  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--set", default="HI-Small")
    ap.add_argument("--rows", required=True)
    ap.add_argument("--background", type=int, default=20000)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "ibm-aml"))
    a = ap.parse_args()
    src = os.path.join(a.data, a.set)
    dst = os.path.join(a.out, f"{a.set}-sample")
    os.makedirs(a.out, exist_ok=True)
    rows = a.rows if os.path.isabs(a.rows) else os.path.join(a.data, a.rows)
    chosen = {int(x) for x in open(rows).read().split()}
    pats = read_patterns(src + "_Patterns.txt")
    total = sum(1 for _ in open(src + "_Trans.csv")) - 1

    accts, kept = set(), 0
    with open(src + "_Trans.csv", newline="") as f, open(dst + "_Trans.csv", "w", newline="") as g:
        r, w = csv.reader(f), csv.writer(g, lineterminator="\n")
        w.writerow(next(r))
        for n, t in enumerate(r, 1):
            if (n in chosen or (t[0], key(t[1], t[2]), key(t[3], t[4]), t[7]) in pats
                    or (n * 2654435761) % 2**32 < a.background / total * 2**32):
                w.writerow(t)
                kept += 1
                accts.update((key(t[1], t[2]), key(t[3], t[4])))
    with open(src + "_accounts.csv", newline="") as f, open(dst + "_accounts.csv", "w", newline="") as g:
        r, w = csv.reader(f), csv.writer(g, lineterminator="\n")
        w.writerow(next(r))
        for t in r:
            if key(t[1], t[2]) in accts:
                w.writerow(t)
    shutil.copy(src + "_Patterns.txt", dst + "_Patterns.txt")
    json.dump(eur_rates(src + "_Trans.csv"), open(dst + "_rates.json", "w"), indent=1, sort_keys=True)
    print(f"{kept} de {total} transferencias, {len(accts)} cuentas → {dst}_*")


if __name__ == "__main__":
    sys.exit(main())
