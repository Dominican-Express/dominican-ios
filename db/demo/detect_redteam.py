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

    ("la regla amplia no es más amplia que la estricta",
     "05_detectors.surql",
     "$ring_rule_wide VALUE { lo: 0.90dec, hi: 1.20dec, gap: 72h }",
     "$ring_rule_wide VALUE { lo: 0.90dec, hi: 1dec, gap: 72h }",
     "el anillo que crece da posible anillo"),

    ("un posible anillo congela",
     "10_controls.surql",
     "IF $kind = 'mule_ring' {",
     "IF $kind IN ['mule_ring', 'possible_ring'] {",
     "…sin congelarlas"),

    ("un posible anillo no va a revisión",
     "10_controls.surql",
     "IN ['possible_ring', 'shared_device', 'structuring', 'velocity']",
     "IN ['shared_device', 'structuring', 'velocity']",
     "…las manda a revisión"),

    ("la cuenta del anillo estricto recibe también posible anillo",
     "05_detectors.surql",
     "\n                              .filter(|$a| $a NOTINSIDE $accounts);",
     ";",
     "ninguna cuenta con anillo estricto recibe además posible anillo"),

    ("el barrido amplio duplica",
     "05_detectors.surql",
     "INSERT IGNORE INTO fraud_alert {\n            id: ['possible_ring',",
     "CREATE fraud_alert CONTENT {\n            pr: ['possible_ring',",
     "repetir el barrido no duplica los posibles anillos"),
]

if __name__ == "__main__":
    run_cases(CASES, "detect_test.py")
