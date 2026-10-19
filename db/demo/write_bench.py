#!/usr/bin/env python3
"""Mide cuántos pagos por segundo aguanta la ruta de escritura, con todos los
eventos en línea, sobre el banco que haya cargado gen_volume.py.

    python3 db/demo/write_bench.py --customers 1000 --ops 300
"""
import argparse
import random
import time

from gen_volume import root_last_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--customers", type=int, required=True)
    ap.add_argument("--ops", type=int, default=300)
    a = ap.parse_args()
    rnd = random.Random(1)
    stmts = []
    for _ in range(a.ops):
        i, j = rnd.randrange(a.customers), rnd.randrange(a.customers)
        if rnd.random() < 0.5:
            stmts.append(f"RETURN fn::charge_card(card:c{i}, 1.00dec, 'Bench', (-3.70, 40.41));")
        elif i != j:
            stmts.append(f"RETURN fn::transfer(account:c{i}, account:c{j}, 1.00dec);")
    t0 = time.time()
    for k in range(0, len(stmts), 100):
        root_last_all("\n".join(stmts[k:k + 100]))
    dt = time.time() - t0
    print(f"{len(stmts)} pagos en {dt:.1f} s: {len(stmts) / dt:.0f} pagos/s")


if __name__ == "__main__":
    main()
