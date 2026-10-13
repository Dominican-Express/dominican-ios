-- Dominican Express — detectores POR BARRIDO (análisis de red)
--
-- Caros: travesías de grafo y agregaciones por ventana. Se lanzan desde el
-- guion de demo o por tarea programada, NUNCA dentro de la transacción de
-- un pago. Todos escriben en `fraud_alert`, que es la única tabla que
-- escucha el LIVE SELECT del panel.

-- ---------------------------------------------------------------------------
-- 1. ANILLOS DE MULAS: el dinero sale de una cuenta y vuelve a ella.
--
-- OJO con la sintaxis: `+path` NO incluye el nodo de origen en el camino, y
-- el ciclo no queda necesariamente al final. Con las aristas
--   a->b, b->c, c->a, a->d, d->e
-- los caminos desde `a` son:
--   [d, e]  /  [b, c, a, d, e]  /  [b, c, a, b, c, a]
-- El segundo contiene el ciclo pero TERMINA en `e`. Por eso el filtro
-- correcto es "el origen reaparece en el camino", no "el camino acaba en el
-- origen". Verificado: marca a, b, c y deja fuera d, e.
DEFINE FUNCTION OVERWRITE fn::detect_rings($max_hops: int) {
    LET $found = (SELECT id,
             id.{2..5+path}(->transfer->account)[WHERE $parent.id IN $this] AS anillos
      FROM account
      WHERE kind = 'customer'
        AND count(id.{2..5+path}(->transfer->account)[WHERE $parent.id IN $this]) > 0);
    FOR $r IN $found {
        CREATE fraud_alert SET kind = 'mule_ring', score = 0.85,
            account = $r.id, detail = { paths: $r.anillos };
    };
    RETURN count($found);
};

-- ---------------------------------------------------------------------------
-- 2. DISPOSITIVO COMPARTIDO: varias identidades desde el mismo aparato.
DEFINE FUNCTION OVERWRITE fn::detect_shared_devices($min: int) {
    LET $found = (SELECT id, fingerprint, <-uses<-customer AS holders
                  FROM device WHERE count(<-uses<-customer) >= $min);
    FOR $d IN $found {
        CREATE fraud_alert SET kind = 'shared_device', score = 0.75,
            device = $d.id,
            detail = { fingerprint: $d.fingerprint, holders: $d.holders };
    };
    RETURN count($found);
};

-- ---------------------------------------------------------------------------
-- 3. ESTRUCTURACIÓN (smurfing): muchos envíos justo por debajo del umbral
-- de reporte obligatorio, para no cruzarlo nunca.
DEFINE FUNCTION OVERWRITE fn::detect_structuring($floor: decimal, $ceil: decimal, $min_ops: int) {
    LET $found = (SELECT account, count() AS n,
                         math::sum(math::abs(amount)) AS total
                  FROM entry
                  WHERE amount < 0dec
                    AND account.kind = 'customer'
                    AND math::abs(amount) >= $floor
                    AND math::abs(amount) <  $ceil
                    AND at > time::now() - 24h
                  GROUP BY account);
    FOR $s IN $found {
        IF $s.n >= $min_ops {
            CREATE fraud_alert SET kind = 'structuring', score = 0.7,
                account = $s.account,
                detail = { ops: $s.n, total: $s.total, window: '24h' };
        };
    };
    RETURN count($found);
};

-- ---------------------------------------------------------------------------
-- 4. RECONCILIACIÓN: el saldo materializado contra el libro de apuntes.
-- Debe devolver SIEMPRE vacío. Es la prueba de que ACID sostiene el invariante.
--
-- Dos trampas aquí, las dos encontradas ejecutando:
--  1. `SELECT VALUE math::sum(amount) FROM entry` aplica la suma POR FILA y
--     falla con "Expected array<number> but found -900dec". La forma correcta
--     es `math::sum(SELECT VALUE amount FROM entry ...)`, que es justamente lo
--     que ya hace fn::balance, así que se reutiliza.
--  2. El alias de un SELECT no puede usarse en su propio WHERE, de ahí que la
--     llamada se repita. Y `math::sum` de un conjunto vacío devuelve el entero
--     0, no 0dec: se usa `!=` (tolerante al tipo), nunca `!==`.
DEFINE FUNCTION OVERWRITE fn::reconcile() {
    RETURN SELECT id, balance, fn::balance(id) AS ledger
           FROM account
           WHERE balance != fn::balance(id);
};
