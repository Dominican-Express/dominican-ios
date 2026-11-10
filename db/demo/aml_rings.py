#!/usr/bin/env python3
"""Versión de referencia en Python de fn::ring_from / fn::find_rings
(schema/05_detectors.surql), para dos cosas:
  - comprobar que aml_prefilter.py no pierde anillos (mismos anillos con
    todas las transferencias que solo con las candidatas);
  - cruzar el resultado de SurrealDB con uno calculado por otro camino.

    uv run --with numpy python db/demo/aml_rings.py --data DIR [--limit N]
        [--rows candidatas.txt] [--lo 0.85 --hi 1.0 --gap-h 48 --hops 5]

Imprime el número de anillos y de cuentas, y la huella (conjunto de anillos)
para poder comparar dos ejecuciones con --dump.
"""
import argparse
import os
import sys
from bisect import bisect_right
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aml_prefilter import load  # noqa: E402


def find_rings(edges, lo, hi, gap, hops):
    """edges: lista de (fila, src, dst, t, amt). Misma lógica que fn::ring_from:
    siguiente salto sale de la última cuenta, t0 < t <= t0+gap,
    lo*amt <= amt' <= hi*amt; cierra si vuelve al origen con >= 3 saltos;
    no repite cuentas."""
    out = defaultdict(list)
    for e in edges:
        out[e[1]].append(e)
    times = {}
    for u in out:
        out[u].sort(key=lambda e: e[3])
        times[u] = [e[3] for e in out[u]]
    rings = []

    def step(chain, left):
        last = chain[-1]
        origin = chain[0][1]
        node, t0 = last[2], last[3]
        if node not in out:
            return
        lst, ts = out[node], times[node]
        i, j = bisect_right(ts, t0), bisect_right(ts, t0 + gap)
        seen = {e[1] for e in chain}
        for f in lst[i:j]:
            if not (last[4] * lo <= f[4] <= last[4] * hi):
                continue
            if f[2] == origin:
                if len(chain) >= 2:
                    rings.append(chain + [f])
            elif left > 1 and f[2] not in seen:
                step(chain + [f], left - 1)

    for e in edges:
        step([e], hops - 1)
    return rings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--set", default="HI-Small")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--rows", help="solo estas filas del CSV (salida de aml_prefilter)")
    ap.add_argument("--lo", type=float, default=0.85)
    ap.add_argument("--hi", type=float, default=1.0)
    ap.add_argument("--gap-h", type=float, default=48)
    ap.add_argument("--hops", type=int, default=5)
    ap.add_argument("--dump", help="guardar los anillos (filas) en este fichero")
    a = ap.parse_args()
    row, src, dst, tm, amt, ids = load(os.path.join(a.data, f"{a.set}_Trans.csv"), a.limit)
    keep = None
    if a.rows:
        keep = {int(x) for x in open(a.rows).read().split()}
    edges = [(r, s, d, t, m) for r, s, d, t, m in zip(row.tolist(), src.tolist(), dst.tolist(), tm.tolist(), amt.tolist())
             if keep is None or r in keep]
    rings = find_rings(edges, a.lo, a.hi, int(a.gap_h * 60), a.hops)
    accts = {e[1] for r in rings for e in r}
    print(f"{len(edges)} transferencias → {len(rings)} anillos, {len(accts)} cuentas")
    if a.dump:
        with open(a.dump, "w") as f:
            for r in sorted(tuple(e[0] for e in r) for r in rings):
                f.write(" ".join(map(str, r)) + "\n")


if __name__ == "__main__":
    sys.exit(main())
