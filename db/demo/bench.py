#!/usr/bin/env python3
"""Mide los detectores sobre el banco de gen_volume.py: tiempo y acierto.

Para cada detector compara lo que marca con lo plantado (la verdad):
  aciertos   lo plantado que encuentra
  fallos     lo plantado que NO encuentra
  falsas     lo que marca sin haberse plantado (falsos positivos)

    python3 db/demo/bench.py --truth /tmp/dx_truth.json [--rings fn::detect_rings_v2]
"""
import argparse
import json
import time

from gen_volume import root_last_all


def flagged(kind, field):
    res = root_last_all(f"SELECT VALUE <string>{field} FROM fraud_alert WHERE kind = '{kind}';")
    return set(res[-1]["result"])


def timed(sql):
    t0 = time.time()
    res = root_last_all(sql)
    dt = time.time() - t0
    st = res[-1]
    return dt, st


def row(name, secs, truth, got, note=""):
    tp, fn, fp = len(truth & got), len(truth - got), len(got - truth)
    t = f"{secs:7.2f} s" if secs is not None else "  en línea"
    print(f"  {name:<24} {t}   aciertos {tp:>3}/{len(truth):<3}  fallos {fn:>3}  falsas {fp:>4}  {note}")
    return {"detector": name, "seconds": secs, "planted": len(truth), "hits": tp, "misses": fn,
            "false_positives": fp}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", default="/tmp/dx_truth.json")
    ap.add_argument("--rings", default="fn::detect_rings(5)")
    a = ap.parse_args()
    truth = json.load(open(a.truth))
    out = []
    print(f"banco: {truth['params']['customers']} clientes, {truth['stats']}")

    out.append(row("viaje imposible", None, set(truth["impossible_travel"]),
                   flagged("impossible_travel", "account")))
    out.append(row("ráfaga de cargos", None, set(truth["velocity"]), flagged("velocity", "account")))

    root_last_all("DELETE fraud_alert WHERE kind IN ['mule_ring','shared_device','structuring'];")
    dt, st = timed(f"RETURN {a.rings};")
    if st["status"] != "OK":
        print(f"  anillos: ERROR {str(st['result'])[:200]}")
    ring_truth = {acc for ring in truth["rings"] for acc in ring}
    out.append(row(f"anillos {a.rings.split('(')[0]}", dt, ring_truth, flagged("mule_ring", "account")))

    dt, _ = timed("RETURN fn::detect_shared_devices(3);")
    got = flagged("shared_device", "device")
    fam = len(got & set(truth["legit_households_of_3"]))
    out.append(row("dispositivo compartido", dt, set(truth["shared_devices"]), got,
                   f"({fam} de las falsas son familias de 3 con una tablet)"))

    dt, _ = timed("RETURN fn::detect_structuring(2700dec, 3000dec, 5);")
    out.append(row("estructuración", dt, set(truth["structuring"]), flagged("structuring", "account")))

    rec = root_last_all("RETURN fn::reconcile();")[-1]["result"]
    print(f"  reconciliación: {'VACÍA' if not rec else rec[:3]}")
    print(f"  throughput de la vida normal: {truth['money_ops'] / truth['money_ops_seconds']:.0f} operaciones/s "
          f"con todos los eventos en línea")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
