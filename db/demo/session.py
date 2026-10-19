"""Cliente mínimo de SurrealDB por HTTP, solo biblioteca estándar.

Permite actuar como un usuario de la app (no como root) para comprobar que
los permisos se cumplen de verdad.
"""
import json
import os
import urllib.error
import urllib.request

URL = os.environ.get("SURREAL_URL", "http://127.0.0.1:8099")
NS = os.environ.get("SURREAL_NS", "dx")
DB = os.environ.get("SURREAL_DB", "bank")


def _post(path, body, headers):
    req = urllib.request.Request(URL + path, data=body.encode(), method="POST",
                                 headers={"Accept": "application/json", **headers})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode()[:300]}


def signin(email, password):
    """Inicia sesión con el acceso de registro `banca` y devuelve el token."""
    res = _post("/signin", json.dumps({"ns": NS, "db": DB, "ac": "banca",
                                       "email": email, "pass": password}),
                {"Content-Type": "application/json"})
    if "http_error" in res:
        raise RuntimeError(f"signin rechazado: {res}")
    tok = res.get("token")
    return tok["access"] if isinstance(tok, dict) else tok


def query(token, sql):
    """Ejecuta SurrealQL con la sesión del usuario. Devuelve la lista de resultados."""
    res = _post("/sql", sql, {"Authorization": f"Bearer {token}",
                              "surreal-ns": NS, "surreal-db": DB})
    if isinstance(res, dict):
        raise RuntimeError(f"consulta rechazada: {res}")
    return res


def last(token, sql):
    """Resultado de la última sentencia, o su error."""
    st = query(token, sql)[-1]
    return st["result"] if st["status"] == "OK" else f"ERROR: {st['result']}"


def api(token, path, body, retries=5):
    """POST a un endpoint de 07_api.surql. Devuelve (código HTTP, cuerpo JSON).

    Reintenta solo los CONFLICTOS de escritura: dos transacciones han tocado el
    mismo registro y una se ha deshecho entera. Repetir es seguro porque la
    orden lleva su propio id: si la primera llegó a confirmarse, el reintento
    recibe esa misma respuesta en vez de pagar otra vez. Cualquier otro error
    se devuelve tal cual, sin reintentar."""
    import time
    req_body = json.dumps(body).encode()
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(retries + 1):
        req = urllib.request.Request(f"{URL}/api/{NS}/{DB}{path}", data=req_body,
                                     method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, _as_obj(json.loads(r.read() or b"null"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            # OJO: SurrealDB 3.2 devuelve el conflicto como 400 («Transaction
            # conflict: Write conflict, retry the transaction»), no como 5xx.
            # Por el código parece un error del cliente; se reconoce por el texto.
            if _is_conflict(raw) and attempt < retries:
                time.sleep(0.01 * (2 ** attempt))   # espera creciente
                continue
            try:
                return e.code, _as_obj(json.loads(raw))
            except ValueError:
                return e.code, {"raw": raw[:300]}


def _as_obj(v):
    # Un error lanzado dentro de un endpoint llega como un TEXTO JSON, no como
    # objeto. Se envuelve para que quien lo lea con .get() no reviente: una
    # prueba que se cae a medias no dice qué ha fallado.
    return v if isinstance(v, dict) else {"raw": v}


def _is_conflict(raw):
    low = raw.lower()
    return "transaction conflict" in low and "can be retried" in low


def root_last(sql):
    """Lo mismo, como root. Solo para OBSERVAR el efecto real de un ataque:
    lo que un usuario no puede leer no demuestra que no exista."""
    import base64
    cred = base64.b64encode(
        f"{os.environ.get('SURREAL_USER', 'root')}:{os.environ.get('SURREAL_PASS', 'root')}".encode()
    ).decode()
    res = _post("/sql", sql, {"Authorization": f"Basic {cred}",
                              "surreal-ns": NS, "surreal-db": DB})
    st = res[-1]
    return st["result"] if st["status"] == "OK" else f"ERROR: {st['result']}"
