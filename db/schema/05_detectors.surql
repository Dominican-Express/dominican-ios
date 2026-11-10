-- Dominican Express — detectores POR BARRIDO (análisis de red)
--
-- Caros: travesías de grafo y agregaciones por ventana. Se lanzan desde el
-- guion de demo o por tarea programada, NUNCA dentro de la transacción de
-- un pago. Todos escriben en `fraud_alert`, que es la única tabla que
-- escucha el LIVE SELECT del panel.

-- ---------------------------------------------------------------------------
-- 1. ANILLOS DE MULAS: el dinero se REENVÍA y vuelve a su origen.
--
-- Lo que define un anillo no es que haya un ciclo en el grafo, sino que el
-- MISMO dinero da la vuelta: cada salto sale de la cuenta poco después de que
-- entrara (menos de 48 h), por un importe algo menor (la comisión de la mula,
-- entre el 85 y el 100 % del salto anterior), pasa por al menos 3 cuentas
-- distintas y acaba donde empezó. Solo se mira la última semana.
--
-- Por qué así, medido con demo/gen_volume.py + demo/bench.py: la versión
-- ingenua (cualquier ciclo de 2 a 5 saltos, fn::detect_rings_naive) tardó 53 s
-- con solo 100 clientes y marcó 75 cuentas inocentes. Dos amigos que se
-- devuelven dinero ya forman un «ciclo» A→B→A, y cada transferencia repetida
-- es una arista más, así que los caminos crecen de forma exponencial.
--
-- Algoritmo: se parte de cada transferencia reciente y se extiende la cadena
-- solo con transferencias que cumplen la regla de reenvío desde el último
-- salto. La regla poda casi todo, así que el coste deja de ser exponencial.
-- Está escrito como función recursiva porque en SurrealQL un LET dentro de un
-- FOR crea una variable nueva en vez de reasignar la de fuera: un acumulador
-- en un bucle se queda en su valor inicial, sin ningún error.
-- La regla vive en un solo sitio y se puede pasar otra para calibrarla
-- contra datos con la respuesta conocida (demo/aml_eval.py, dataset de IBM).
DEFINE PARAM OVERWRITE $ring_rule VALUE { lo: 0.85dec, hi: 1dec, gap: 48h };

DEFINE FUNCTION OVERWRITE fn::ring_from($chain: array, $left: int, $rule: object) {
    LET $last = $chain[array::len($chain) - 1];
    LET $origin = $chain[0].in;
    LET $seen = $chain.map(|$e| $e.in);
    -- Se recorren las aristas que SALEN de la cuenta (grafo), no la tabla
    -- `transfer` con un WHERE, y con variables simples: ver la nota del índice
    -- en fn::transfer. Por eso la regla se copia a variables antes del SELECT.
    LET $node = $last.out;
    LET $t0 = $last.at;
    LET $t1 = $last.at + $rule.gap;
    LET $hi = $last.amount * $rule.hi;
    LET $lo = $last.amount * $rule.lo;
    LET $next = (SELECT id, in, out, at, amount FROM $node->transfer
                 WHERE at > $t0 AND at <= $t1 AND amount <= $hi AND amount >= $lo);
    LET $closed = $next.filter(|$e| $e.out = $origin AND array::len($chain) >= 2)
                       .map(|$e| array::append($chain, $e));
    IF $left <= 1 { RETURN $closed };
    LET $open = $next.filter(|$e| $e.out != $origin AND $e.out NOTINSIDE $seen);
    RETURN array::concat($closed,
        array::flatten($open.map(|$e| fn::ring_from(array::append($chain, $e), $left - 1, $rule))));
} PERMISSIONS NONE;

-- Los anillos que empiezan entre $from y $to, sin escribir nada.
DEFINE FUNCTION OVERWRITE fn::find_rings($from: datetime, $to: datetime, $max_hops: int, $rule: object) {
    LET $starts = (SELECT id, in, out, at, amount FROM transfer
                   WHERE at > $from AND at <= $to AND in.kind = 'customer');
    RETURN array::flatten($starts.map(|$e| fn::ring_from([$e], $max_hops - 1, $rule)));
} PERMISSIONS NONE;

DEFINE FUNCTION OVERWRITE fn::detect_rings($max_hops: int) {
    LET $rings = fn::find_rings(time::now() - 7d, time::now(), $max_hops, $ring_rule);
    -- cada anillo aparece una vez por cada cuenta desde la que se empieza
    LET $accounts = array::distinct(array::flatten($rings.map(|$r| $r.map(|$e| $e.in))));
    -- El id dice QUÉ se ha visto (cuenta + miembros de sus anillos) e INSERT
    -- IGNORE no repite lo ya avisado: repetir el barrido no duplica alertas.
    -- Antes era CREATE y cada pasada añadía otras tantas (medido: 22 → 44 → 66).
    FOR $a IN $accounts {
        LET $mine = $rings.filter(|$r| $a INSIDE $r.map(|$e| $e.in));
        LET $members = array::sort(array::distinct(array::flatten($mine.map(|$r| $r.map(|$e| $e.in)))));
        INSERT IGNORE INTO fraud_alert {
            id: ['mule_ring', $a, $members],
            kind: 'mule_ring', score: 0.85, account: $a,
            detail: { rings: $mine.map(|$r| $r.map(|$e| <string>$e.in)) }
        };
    };
    RETURN count($accounts);
} PERMISSIONS NONE;

-- La versión ingenua, conservada solo para que bench.py pueda medir la
-- diferencia. No usar.
--
-- OJO con la sintaxis: `+path` NO incluye el nodo de origen en el camino, y
-- el ciclo no queda necesariamente al final. Con a->b, b->c, c->a, a->d, d->e
-- los caminos desde `a` son [d, e] / [b, c, a, d, e] / [b, c, a, b, c, a]: el
-- segundo contiene el ciclo pero TERMINA en `e`. Por eso el filtro es «el
-- origen reaparece en el camino».
DEFINE FUNCTION OVERWRITE fn::detect_rings_naive($max_hops: int) {
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
} PERMISSIONS NONE;

-- ---------------------------------------------------------------------------
-- 2. DISPOSITIVO COMPARTIDO: varias identidades SIN RELACIÓN en el mismo aparato.
--
-- Medido: con un umbral simple de 3 personas por aparato, las dos falsas
-- alarmas a 100 clientes eran familias de 3 con una tablet común. Ahora solo
-- cuentan los hogares distintos que lo usan (personas unidas por una cuenta
-- común): una familia con cuenta conjunta cuenta como un único hogar.
-- Supuesto declarado: los hogares que comparten aparato comparten también
-- alguna cuenta. Una familia sin ninguna cuenta común seguiría saltando.
DEFINE FUNCTION OVERWRITE fn::detect_shared_devices($min: int) {
    LET $devices = (SELECT id, fingerprint, <-uses<-customer AS holders
                    FROM device WHERE count(<-uses<-customer) >= $min);
    -- Se cuentan HOGARES, no personas aisladas: cada titular se representa por
    -- el menor de los del aparato con quien comparte cuenta (él incluido). La
    -- primera versión contaba personas sin cuenta común y la demo la cazó: una
    -- pareja con cuenta conjunta y dos desconocidos son 3 hogares, y no saltaba.
    -- Aproximación declarada: una cadena A–B–C sin cuenta A–C cuenta como 2.
    LET $found = $devices.filter(|$d|
        count(array::distinct($d.holders.map(|$c|
            array::min(array::intersect($c->owns->account<-owns<-customer, $d.holders)
                       .map(|$x| <string>$x))))) >= $min);
    FOR $d IN $found {
        -- Mismo aparato y mismos titulares = la misma alerta (ver detect_rings).
        INSERT IGNORE INTO fraud_alert {
            id: ['shared_device', $d.id, array::sort($d.holders)],
            kind: 'shared_device', score: 0.75, device: $d.id,
            detail: { fingerprint: $d.fingerprint, holders: $d.holders }
        };
    };
    RETURN count($found);
} PERMISSIONS NONE;

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
            -- Una alerta por cuenta y día (ver detect_rings). Supuesto declarado:
            -- una ráfaga que cruza la medianoche puede avisar dos días seguidos.
            INSERT IGNORE INTO fraud_alert {
                id: ['structuring', $s.account, time::floor(time::now(), 1d)],
                kind: 'structuring', score: 0.7, account: $s.account,
                detail: { ops: $s.n, total: $s.total, window: '24h' }
            };
        };
    };
    RETURN count($found);
} PERMISSIONS NONE;

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
} PERMISSIONS NONE;
