"""Motor común de las pruebas en rojo (*_redteam.py).

Un test que nunca has visto fallar no vigila nada. Cada caso aplica el esquema
REAL con un texto exacto sustituido (no una copia reescrita a mano, que se
desincroniza en cuanto cambia el fichero) sobre una base limpia, carga la
semilla, ejecuta la prueba y exige que caiga la comprobación que vigila esa
protección. Si el texto a romper ya no está en el fichero, el caso cuenta como
roto: así no puede quedar un caso que no rompe nada.
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = HERE.parent / "schema"


def _run(cmd, env):
    return subprocess.run(cmd, cwd=HERE, env=env, capture_output=True, text=True)


def run_cases(cases, test_script):
    """cases: (protección, fichero, texto original, texto roto, comprobación que DEBE caer)."""
    caught = 0
    for name, fname, old, new, must_fail in cases:
        src = (SCHEMA / fname).read_text()
        if old not in src:
            print(f"  [ROTO ] {name}\n          el texto a romper ya no está en {fname}: actualiza el caso")
            continue
        db = "rt_" + uuid.uuid4().hex[:8]
        env = {**os.environ, "SURREAL_DB": db}
        _run(["./apply.sh"], env)
        broken = HERE / f".rt_{db}.surql"
        broken.write_text(src.replace(old, new, 1))
        _run(["./surql.sh", str(broken)], env)
        broken.unlink()
        _run(["./surql.sh", "01_seed.surql"], env)
        out = _run([sys.executable, test_script], env).stdout
        line = next((l for l in out.splitlines() if must_fail in l), "")
        ok = "FALLA" in line
        caught += ok
        print(f"  [{'cae  ' if ok else 'NO CAE'}] {name}")
        if not ok:
            print(f"          «{must_fail}» siguió pasando (o no se ejecutó): no vigila esta rotura")
    print(f"\n{caught}/{len(cases)} roturas detectadas por su prueba")
    sys.exit(0 if caught == len(cases) else 1)
