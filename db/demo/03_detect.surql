-- Dominican Express — barrido de análisis de red
-- Se lanza fuera de la ruta crítica de los pagos.

RETURN fn::detect_rings(5);
RETURN fn::detect_shared_devices(3);
RETURN fn::detect_structuring(2700dec, 3000dec, 5);

-- La reconciliación debe salir VACÍA: el saldo materializado cuadra con el
-- libro de apuntes.
RETURN fn::reconcile();

SELECT kind, score, account, device, card, detail FROM fraud_alert ORDER BY score DESC;
