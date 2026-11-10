#!/usr/bin/env python3
"""Filtro previo SIN PÉRDIDA del dataset de IBM: quita las transferencias que
no pueden formar parte de ningún anillo según la regla de reenvío, para que
SurrealDB solo reciba lo que puede ser sospechoso.

    uv run --with numpy python db/demo/aml_prefilter.py --data DIR [--set HI-Small]
        [--lo 0.80 --hi 1.20 --gap-h 72] [--out FICHERO]

Por qué hace falta: el detector de SurrealDB arranca una búsqueda desde cada
transferencia. Con 4,5 millones (un solo día ya son 200.000) se pasa minutos
con la CPU al máximo. Un banco haría lo mismo: filtro barato primero, análisis
de grafo caro solo sobre lo sospechoso.

Por qué no se pierde ningún anillo. En un anillo e0 → e1 → … → ek que cumple
la regla (fn::ring_from en schema/05_detectors.surql):
  1. cada transferencia tiene una SIGUIENTE (la reenvía) o una ANTERIOR (es el
     reenvío de otra); e0 no tiene anterior y ek no tiene siguiente, pero
     todas tienen al menos una de las dos;
  2. sus cuentas forman un ciclo, luego están en la misma componente
     fuertemente conexa, de al menos 3 cuentas (el detector exige 3).
Se aplican 1 y 2 hasta que no cambia nada. Con la regla más permisiva que se
vaya a probar, el resultado contiene todos los anillos de cualquier regla más
estricta, así que medir sobre él es medir sobre el dataset entero.
"""
import argparse
import csv
import os
import statistics
import sys
import time
from bisect import bisect_left, insort
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

EPS = 1e-9  # los importes van redondeados al céntimo; ensanchar no quita anillos


def minutes(s):
    return int(datetime.strptime(s, "%Y/%m/%d %H:%M").replace(tzinfo=timezone.utc).timestamp() // 60)


def key(bank, acct):
    return f"{int(bank)}_{acct}"


def load(path, limit=0):
    pair = defaultdict(list)
    with open(path, newline="") as f:
        r = csv.reader(f)
        next(r)
        for t in r:
            if t[8] != t[6] and float(t[7]) > 0:
                pair[(t[8], t[6])].append(float(t[5]) / float(t[7]))
    usd = {"US Dollar": 1.0}
    for (paid, recv), v in pair.items():
        if recv == "US Dollar":
            usd.setdefault(paid, statistics.median(v))
    for (paid, recv), v in pair.items():
        if paid == "US Dollar" and recv not in usd:
            usd[recv] = 1 / statistics.median(v)
    to_eur = {c: x / usd["Euro"] for c, x in usd.items()}

    ids = {}
    row, src, dst, tm, amt = [], [], [], [], []
    with open(path, newline="") as f:
        r = csv.reader(f)
        next(r)
        for n, t in enumerate(r, 1):
            if limit and n > limit:
                break
            a, b = key(t[1], t[2]), key(t[3], t[4])
            if a == b:
                continue
            row.append(n)
            src.append(ids.setdefault(a, len(ids)))
            dst.append(ids.setdefault(b, len(ids)))
            tm.append(minutes(t[0]))
            amt.append(round(float(t[7]) * to_eur[t[8]], 2))
    return (np.array(row, np.int32), np.array(src, np.int32), np.array(dst, np.int32),
            np.array(tm, np.int32), np.array(amt, np.float64), ids)


def has_next(alive, src, dst, tm, amt, lo, hi, gap):
    """Para cada transferencia viva e (u→v): ¿sale de v otra viva f con
    e.t < f.t <= e.t+gap y lo·e.amt <= f.amt <= hi·e.amt?"""
    out = np.zeros(len(src), bool)
    idx = np.flatnonzero(alive)
    # llegadas a v y salidas de v, ambas por (cuenta, tiempo)
    inc = idx[np.lexsort((tm[idx], dst[idx]))]
    outg = idx[np.lexsort((tm[idx], src[idx]))]
    acc_out = src[outg]
    starts = np.searchsorted(acc_out, np.arange(acc_out.max() + 2 if len(acc_out) else 1)).tolist()
    inc, outg = inc.tolist(), outg.tolist()
    src, dst, tm, amt = src.tolist(), dst.tolist(), tm.tolist(), amt.tolist()
    i = 0
    n = len(inc)
    while i < n:
        v = dst[inc[i]]
        j = i
        while j < n and dst[inc[j]] == v:
            j += 1
        if v + 1 < len(starts):
            o0, o1 = starts[v], starts[v + 1]
        else:
            o0 = o1 = 0
        if o1 > o0:
            # ventana deslizante: importes de las salidas con tiempo en (t, t+gap]
            window = []
            p = q = o0  # [p, q) = salidas dentro de la ventana
            for k in range(i, j):
                e = inc[k]
                t = tm[e]
                while q < o1 and tm[outg[q]] <= t + gap:
                    insort(window, amt[outg[q]])
                    q += 1
                while p < q and tm[outg[p]] <= t:
                    window.pop(bisect_left(window, amt[outg[p]]))
                    p += 1
                lo_a = amt[e] * lo - EPS
                pos = bisect_left(window, lo_a)
                if pos < len(window) and window[pos] <= amt[e] * hi + EPS:
                    out[e] = True
        i = j
    return out


def has_prev(alive, src, dst, tm, amt, lo, hi, gap):
    """Simétrico: ¿llega a u otra viva g con g.t < f.t <= g.t+gap y
    lo·g.amt <= f.amt <= hi·g.amt?  ⇔  f.amt/hi <= g.amt <= f.amt/lo."""
    out = np.zeros(len(src), bool)
    idx = np.flatnonzero(alive)
    outg = idx[np.lexsort((tm[idx], src[idx]))]
    inc = idx[np.lexsort((tm[idx], dst[idx]))]
    acc_in = dst[inc]
    starts = np.searchsorted(acc_in, np.arange(acc_in.max() + 2 if len(acc_in) else 1)).tolist()
    inc, outg = inc.tolist(), outg.tolist()
    src, dst, tm, amt = src.tolist(), dst.tolist(), tm.tolist(), amt.tolist()
    i = 0
    n = len(outg)
    while i < n:
        u = src[outg[i]]
        j = i
        while j < n and src[outg[j]] == u:
            j += 1
        if u + 1 < len(starts):
            g0, g1 = starts[u], starts[u + 1]
        else:
            g0 = g1 = 0
        if g1 > g0:
            window = []
            p = q = g0  # llegadas con tiempo en [t-gap, t)
            for k in range(i, j):
                f = outg[k]
                t = tm[f]
                while q < g1 and tm[inc[q]] < t:
                    insort(window, amt[inc[q]])
                    q += 1
                while p < q and tm[inc[p]] < t - gap:
                    window.pop(bisect_left(window, amt[inc[p]]))
                    p += 1
                pos = bisect_left(window, amt[f] / hi - EPS)
                if pos < len(window) and window[pos] <= amt[f] / lo + EPS:
                    out[f] = True
        i = j
    return out


def scc_keep(alive, src, dst, nacc, min_size=3):
    """Tarjan iterativo sobre las cuentas con aristas vivas; devuelve la
    máscara de aristas cuyos dos extremos están en la misma componente
    fuertemente conexa de al menos min_size cuentas."""
    idx = np.flatnonzero(alive)
    order = idx[np.argsort(src[idx], kind="stable")]
    s = src[order]
    starts = np.searchsorted(s, np.arange(nacc + 1))
    nbr = dst[order]
    index = np.full(nacc, -1, np.int64)
    low = np.zeros(nacc, np.int64)
    onstack = np.zeros(nacc, bool)
    comp = np.full(nacc, -1, np.int64)
    stack, counter, ncomp = [], 0, 0
    nodes = np.unique(np.concatenate([src[idx], dst[idx]]))
    for root in nodes:
        if index[root] != -1:
            continue
        work = [(root, starts[root])]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        onstack[root] = True
        while work:
            v, it = work[-1]
            if it < starts[v + 1]:
                work[-1] = (v, it + 1)
                w = nbr[it]
                if index[w] == -1:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    onstack[w] = True
                    work.append((w, starts[w]))
                elif onstack[w]:
                    low[v] = min(low[v], index[w])
            else:
                work.pop()
                if work:
                    u = work[-1][0]
                    low[u] = min(low[u], low[v])
                if low[v] == index[v]:
                    while True:
                        w = stack.pop()
                        onstack[w] = False
                        comp[w] = ncomp
                        if w == v:
                            break
                    ncomp += 1
    size = np.bincount(comp[comp >= 0], minlength=ncomp)
    same = (comp[src] == comp[dst]) & (comp[src] >= 0)
    big = np.zeros(len(src), bool)
    big[same] = size[comp[src[same]]] >= min_size
    return alive & big


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--set", default="HI-Small")
    ap.add_argument("--lo", type=float, default=0.80)
    ap.add_argument("--hi", type=float, default=1.20)
    ap.add_argument("--gap-h", type=float, default=72)
    ap.add_argument("--out")
    ap.add_argument("--limit", type=int, default=0, help="solo las N primeras filas (pruebas)")
    a = ap.parse_args()
    t0 = time.time()
    row, src, dst, tm, amt, ids = load(os.path.join(a.data, f"{a.set}_Trans.csv"), a.limit)
    print(f"leído: {len(row)} transferencias, {len(ids)} cuentas, {time.time() - t0:.0f} s", flush=True)
    gap = int(a.gap_h * 60)
    alive = np.ones(len(row), bool)
    for rnd in range(1, 20):
        before = int(alive.sum())
        alive &= has_next(alive, src, dst, tm, amt, a.lo, a.hi, gap) | has_prev(alive, src, dst, tm, amt, a.lo, a.hi, gap)
        mid = int(alive.sum())
        alive = scc_keep(alive, src, dst, len(ids))
        after = int(alive.sum())
        print(f"ronda {rnd}: {before} → reenvío {mid} → componentes {after}  ({time.time() - t0:.0f} s)", flush=True)
        if after == before:
            break
    accts = np.unique(np.concatenate([src[alive], dst[alive]]))
    print(f"candidatas: {int(alive.sum())} transferencias, {len(accts)} cuentas")
    out = a.out or os.path.join(a.data, f"{a.set}_candidates_{a.lo}_{a.hi}_{a.gap_h:g}h.txt")
    np.savetxt(out, row[alive], fmt="%d")
    print(f"filas del CSV guardadas en {out}")


if __name__ == "__main__":
    sys.exit(main())
