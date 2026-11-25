#!/usr/bin/env python3
"""Mide qué pasa con los líderes de Raft cuando muere un TiKV.

    ./db/demo/demo.sh cluster-up
    python3 db/cluster/leaders_trace.py [--out presentation/assets/data/leaders.csv]

Durante 30 s, a la vez:
  - escribe por HAProxy cada 0,25 s (`CREATE beat`, base `cluster`);
  - cada 0,5 s pregunta a PD cuántos líderes tiene cada TiKV y si está vivo;
  - a los 8 s mata el TiKV con más líderes (`cluster.sh kill`).
Guarda un CSV: t (s desde el inicio), tipo (leaders | write | kill) y datos.
La diapositiva «Raft in action» se dibuja con él (presentation/charts.py).
Solo biblioteca estándar. Después: `demo.sh cluster-revive` o `cluster-down`.
"""
import argparse
import base64
import csv
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PD = "http://127.0.0.1:2379/pd/api/v1/stores"
LB = "http://127.0.0.1:8100/sql"
AUTH = "Basic " + base64.b64encode(b"root:root").decode()


def stores():
    with urllib.request.urlopen(PD, timeout=2) as r:
        data = json.loads(r.read())
    return {s["store"]["id"]: (s["store"]["state_name"], s["status"].get("leader_count", 0))
            for s in data.get("stores", [])}


def write(i):
    req = urllib.request.Request(LB, method="POST", data=f"CREATE beat SET n = {i}, at = time::now();".encode(),
                                 headers={"Accept": "application/json", "Authorization": AUTH,
                                          "surreal-ns": "dx", "surreal-db": "cluster"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())[0]["status"] == "OK"
    except (urllib.error.URLError, ValueError, KeyError, IndexError, TimeoutError):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "..", "presentation", "assets", "data", "leaders.csv"))
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--kill-at", type=float, default=8)
    a = ap.parse_args()

    rows, lock = [], threading.Lock()
    t0 = time.time()
    stop = threading.Event()

    def add(*row):
        with lock:
            rows.append((round(time.time() - t0, 2), *row))

    def poll():
        while not stop.is_set():
            try:
                for sid, (state, leaders) in stores().items():
                    add("leaders", sid, state, leaders)
            except (urllib.error.URLError, ValueError, TimeoutError):
                add("leaders", "pd", "unreachable", "")
            time.sleep(0.5)

    def writes():
        i = 0
        while not stop.is_set():
            i += 1
            start = time.time()
            ok = write(i)
            add("write", i, "ok" if ok else "error", round((time.time() - start) * 1000))
            time.sleep(0.25)

    threads = [threading.Thread(target=poll), threading.Thread(target=writes)]
    for t in threads:
        t.start()
    time.sleep(a.kill_at)
    out = subprocess.run([os.path.join(HERE, "cluster.sh"), "kill"], capture_output=True, text=True)
    add("kill", "", out.stdout.strip(), "")
    time.sleep(max(0, a.seconds - a.kill_at))
    stop.set()
    for t in threads:
        t.join()

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "kind", "id", "state", "value"])
        w.writerows(sorted(rows))
    ok = sum(1 for r in rows if r[1] == "write" and r[3] == "ok")
    bad = sum(1 for r in rows if r[1] == "write" and r[3] == "error")
    print(f"{out.stdout.strip()}\nwrites: {ok} ok, {bad} errors; trace in {os.path.relpath(a.out)}")


if __name__ == "__main__":
    main()
