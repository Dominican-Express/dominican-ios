-- Dominican Express — detectores EN LÍNEA
--
-- Estos corren DENTRO de la transacción que los dispara (DEFINE EVENT es
-- síncrono salvo que se marque ASYNC). Por eso solo viven aquí detectores de
-- coste acotado, apoyados en índice. Los detectores de grafo, que son caros,
-- van por barrido: ver 05_detectors.surql.
--
-- Consecuencia a asumir: si el cuerpo del evento lanza, la transacción entera
-- se deshace. Un detector con un bug tumbaría los pagos. De ahí que sean
-- deliberadamente simples.

-- VELOCIDAD: ráfaga de cargos en una misma cuenta.
-- La cláusula de deduplicación es necesaria: sin ella el evento emite una
-- alerta por CADA apunte una vez pasado el umbral (medido: 2 alertas con
-- 6 cargos). Eso es spam, no detección.
--
-- El filtro `account.kind = 'customer'` tampoco es cosmético: sin él, la
-- contrapartida externa dispara velocidad en cuanto se pagan cinco nóminas
-- seguidas. Falso positivo encontrado ejecutando la demo, no leyendo el código.
DEFINE EVENT OVERWRITE velocity ON entry
WHEN $event = "CREATE" AND $after.amount < 0dec
     AND $after.account.kind = 'customer' THEN {
    LET $n = count(SELECT id FROM entry
                   WHERE account = $after.account AND amount < 0dec
                     AND at > time::now() - 5m);
    LET $ya = count(SELECT id FROM fraud_alert
                    WHERE kind = 'velocity' AND account = $after.account
                      AND at > time::now() - 5m);
    IF $n >= 5 AND $ya = 0 {
        CREATE fraud_alert SET kind = 'velocity', score = 0.6,
            account = $after.account, detail = { count: $n, window: '5m' };
    };
};

-- VIAJE IMPOSIBLE: dos pagos de la misma tarjeta a velocidad no física.
-- geo::distance devuelve METROS (haversine). 250 m/s ~ 900 km/h, techo de
-- un avión comercial.
DEFINE EVENT OVERWRITE impossible_travel ON card_payment
WHEN $event = "CREATE" THEN {
    LET $prev = (SELECT * FROM card_payment
                 WHERE card = $after.card AND at < $after.at
                 ORDER BY at DESC LIMIT 1)[0];
    IF $prev != NONE {
        LET $m = geo::distance($prev.loc, $after.loc);
        LET $s = duration::secs($after.at - $prev.at);
        IF $s > 0 AND ($m / $s) > 250 {
            CREATE fraud_alert SET kind = 'impossible_travel', score = 0.9,
                card = $after.card,
                detail = { km: $m / 1000, secs: $s, kmh: ($m / $s) * 3.6 };
        };
    };
};

-- SALDO BAJO tras un cargo. Coste constante, sin consultas extra.
DEFINE EVENT OVERWRITE low_balance ON account
WHEN $event = "UPDATE" AND $after.balance < 50dec AND $before.balance >= 50dec
     AND $after.kind = 'customer' THEN {
    CREATE fraud_alert SET kind = 'low_balance', score = 0.2,
        account = $after.id, detail = { balance: $after.balance };
};
