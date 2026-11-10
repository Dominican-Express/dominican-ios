#!/usr/bin/env python3
"""Calibra y valida la regla de anillos contra las etiquetas de IBM.

    uv run --with numpy python db/demo/aml_eval.py --data DIR --set HI-Small \
        --rows HI-Small_candidates_0.8_1.2_72h.txt [--only LO,HI,GAP_H]

Trabaja sobre las candidatas de aml_prefilter.py (filtro sin pérdida con la
regla más permisiva de la rejilla), así que cada regla se mide como si fuera
sobre el dataset entero, en milisegundos.

Método, fijado ANTES de mirar resultados:
  - rejilla: lo ∈ {0.80, 0.85, 0.90}, hi ∈ {1.00 … 1.20}, gap ∈ {24, 48, 72} h,
    hasta 12 saltos (el ciclo más largo de IBM);
  - precisión = cuentas marcadas que aparecen en alguna transferencia
    etiquetada como blanqueo / cuentas marcadas;
  - ciclos encontrados = intentos CYCLE de IBM de los que el detector recupera
    un anillo hecho SOLO de transferencias de ese intento;
  - elegida: la que más ciclos encuentra con precisión >= 95 %; si empatan,
    la más estricta (rango de importe más estrecho, luego plazo más corto);
  - la elegida se aplica sin tocar a otro conjunto (--only) para validarla.
"""
import argparse
import csv
import os
import sys
from itertools import product

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aml_common import key, read_patterns  # noqa: E402
from aml_prefilter import load  # noqa: E402
from aml_rings import find_rings  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--set", default="HI-Small")
    ap.add_argument("--rows", required=True)
    ap.add_argument("--only", help="evaluar solo estas reglas: LO,HI,GAP_H[;LO,HI,GAP_H…]")
    ap.add_argument("--min-precision", type=float, default=0.95)
    a = ap.parse_args()
    base = os.path.join(a.data, a.set)
    cand = {int(x) for x in open(a.rows if os.path.isabs(a.rows) else os.path.join(a.data, a.rows)).read().split()}

    # etiquetas: cuentas que tocan blanqueo y fila -> intento de patrón
    pats = read_patterns(base + "_Patterns.txt")
    laund_accts, attempt_of, cycle_attempts = set(), {}, set()
    with open(base + "_Trans.csv", newline="") as f:
        r = csv.reader(f)
        next(r)
        for n, t in enumerate(r, 1):
            if t[10] != "1":
                continue
            s, d = key(t[1], t[2]), key(t[3], t[4])
            laund_accts.update((s, d))
            p = pats.get((t[0], s, d, t[7]))
            if p:
                attempt_of[n] = p
                if p[0] == "CYCLE":
                    cycle_attempts.add(p[1])

    row, src, dst, tm, amt, ids = load(base + "_Trans.csv")
    name = {v: k for k, v in ids.items()}
    edges = [(r_, s, d, t, m) for r_, s, d, t, m in
             zip(row.tolist(), src.tolist(), dst.tolist(), tm.tolist(), amt.tolist()) if r_ in cand]
    print(f"{a.set}: {len(edges)} candidatas, {len(cycle_attempts)} intentos CYCLE, "
          f"{len(laund_accts)} cuentas que tocan blanqueo")

    if a.only:
        grid = [tuple(float(x) for x in r.split(",")) for r in a.only.split(";")]
    else:
        grid = list(product((0.80, 0.85, 0.90), (1.00, 1.05, 1.10, 1.15, 1.20), (24, 48, 72)))
    results = []
    for lo, hi, gap_h in grid:
        rings = find_rings(edges, lo, hi, int(gap_h * 60), 12)
        flagged = {name[e[1]] for rg in rings for e in rg}
        tp = len(flagged & laund_accts)
        prec = tp / len(flagged) if flagged else 0.0
        found = set()
        for rg in rings:
            at = {attempt_of.get(e[0]) for e in rg}
            if len(at) == 1 and None not in at:
                k, n = at.pop()
                if k == "CYCLE":
                    found.add(n)
        results.append((lo, hi, gap_h, len(rings), len(flagged), tp, prec, len(found)))

    print(f"{'lo':>5} {'hi':>5} {'gap':>4} {'anillos':>8} {'cuentas':>8} {'aciertos':>9} {'precisión':>10} {'ciclos':>7}")
    for lo, hi, g, nr, nf, tp, p, c in results:
        print(f"{lo:5.2f} {hi:5.2f} {g:4.0f} {nr:8} {nf:8} {tp:9} {p:10.1%} {c:4}/{len(cycle_attempts)}")
    ok = [x for x in results if x[6] >= a.min_precision]
    if ok and not a.only:
        best = max(ok, key=lambda x: (x[7], -(x[1] - x[0]), -x[2]))
        print(f"\nelegida: lo={best[0]:.2f} hi={best[1]:.2f} gap={best[2]:.0f} h  →  "
              f"{best[7]}/{len(cycle_attempts)} ciclos, precisión {best[6]:.1%}")


if __name__ == "__main__":
    sys.exit(main())
