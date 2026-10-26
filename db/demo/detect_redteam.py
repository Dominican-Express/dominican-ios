#!/usr/bin/env python3
"""Prueba en rojo de detect_test.py: barridos que no duplican alertas.

    python3 db/demo/detect_redteam.py
"""
from redteam import run_cases

CASES = [
    ("el barrido de anillos no duplica",
     "05_detectors.surql",
     "        INSERT IGNORE INTO fraud_alert {\n            id: ['mule_ring', $a, $members],",
     "        CREATE fraud_alert CONTENT {\n            mule: ['mule_ring', $a, $members],",
     "repetir el barrido no duplica los anillos"),

    ("el barrido de aparatos no duplica",
     "05_detectors.surql",
     "INSERT IGNORE INTO fraud_alert {\n            id: ['shared_device',",
     "CREATE fraud_alert CONTENT {\n            dev: ['shared_device',",
     "…ni el aparato compartido"),

    ("el barrido de estructuración no duplica",
     "05_detectors.surql",
     "INSERT IGNORE INTO fraud_alert {\n                id: ['structuring',",
     "CREATE fraud_alert CONTENT {\n                st: ['structuring',",
     "…ni la estructuración"),

    ("el id distingue anillos: uno nuevo no se traga",
     "05_detectors.surql",
     "id: ['mule_ring', $a, $members],",
     "id: ['mule_ring', $a],",
     "un anillo nuevo sigue avisando"),
]

if __name__ == "__main__":
    run_cases(CASES, "detect_test.py")
