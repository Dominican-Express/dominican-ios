-- Dominican Express — tarjetas y notificaciones
--
--   fn::charge_card        cobro con tarjeta: bloqueo, límite mensual y saldo
--   POST /cards/block      quien lleva la tarjeta la bloquea o desbloquea
--   POST /cards/limit      quien lleva la tarjeta cambia su límite mensual
--   notification           avisos de ingreso, nómina, gasto y pago denegado

UPSERT setting:limits MERGE { card_limit_max: 10000dec };

DEFINE FIELD OVERWRITE last_used_at ON card TYPE option<datetime>;

-- ---------------------------------------------------------------------------
-- COBRO CON TARJETA. Lo llama la red de pagos (root en las pruebas), nunca un
-- cliente. Hasta este bloque un pago con tarjeta creaba su registro pero NO
-- movía dinero, y el campo `blocked` existía sin que nada lo mirara.
--
-- El pago denegado también se guarda, con su motivo: un intento con una
-- tarjeta bloqueada es exactamente lo que interesa al análisis de fraude.
--
-- Concurrencia: el cobro escribe la tarjeta (`last_used_at`) además del saldo.
-- Así, un cobro y un bloqueo simultáneos escriben el mismo registro y chocan;
-- uno se deshace y se reintenta. Sin esa escritura, el cobro podría leer
-- «desbloqueada» de su instantánea mientras otro bloqueo se confirma: es el
-- mismo mecanismo que evita los descubiertos, aplicado a la tarjeta.
DEFINE FUNCTION OVERWRITE fn::charge_card($card: record<card>, $amount: decimal,
        $merchant: string, $loc: geometry<point>, $at: option<datetime>) {
    IF $amount <= 0dec { THROW "El importe debe ser positivo" };
    LET $c = (SELECT * FROM ONLY $card);
    IF $c = NONE { THROW "Tarjeta inexistente" };
    LET $when = $at ?? time::now();
    LET $spent = math::sum(SELECT VALUE amount FROM card_payment
                           WHERE card = $card AND status = 'approved'
                             AND at >= time::group($when, 'month') AND at <= $when);
    LET $reason = IF $c.blocked {
            'card_blocked'
        } ELSE IF $spent + $amount > $c.monthly_limit {
            'monthly_limit_exceeded'
        } ELSE IF fn::balance($c.account) < $amount {
            'insufficient_funds'
        } ELSE {
            NONE
        };
    UPDATE $card SET last_used_at = $when;

    IF $reason != NONE {
        LET $p = (CREATE ONLY card_payment SET card = $card, amount = $amount, merchant = $merchant,
                  loc = $loc, at = $when, status = 'declined', reason = $reason);
        CREATE notification SET customer = $c.holder, kind = 'card_declined',
            account = $c.account, amount = $amount, concept = $merchant, reason = $reason;
        RETURN $p;
    };

    LET $tx = (CREATE ONLY txn SET kind = 'card', concept = $merchant);
    CREATE entry SET account = $c.account, txn = $tx.id, amount = -$amount, at = $when;
    CREATE entry SET account = account:ext, txn = $tx.id, amount =  $amount, at = $when;
    UPDATE $c.account  SET balance -= $amount;
    UPDATE account:ext SET balance += $amount;
    RETURN (CREATE ONLY card_payment SET card = $card, amount = $amount, merchant = $merchant,
            loc = $loc, at = $when, status = 'approved', txn = $tx.id);
} PERMISSIONS NONE;

-- Comprobación común a /cards/block y /cards/limit: la tarjeta existe y la
-- lleva quien llama. Ser cotitular de la cuenta NO basta: cada tarjeta es de
-- su titular, también en una cuenta conjunta. Devuelve la tarjeta, o una
-- respuesta de error con `status`.
DEFINE FUNCTION OVERWRITE fn::own_card($b: any) {
    IF type::is_object($b) = false OR type::is_string($b.card)
       = false OR !string::matches($b.card, "^card:[A-Za-z0-9_]{1,64}$") {
        RETURN { status: 400, body: { error: 'invalid_card' } }
    };
    LET $c = (SELECT * FROM ONLY type::record($b.card));
    IF $c = NONE OR $c.holder != $auth.customer {
        -- Mismo código si no existe y si es ajena: no se revela cuál de las dos.
        RETURN { status: 404, body: { error: 'card_not_found' } }
    };
    RETURN $c;
} PERMISSIONS NONE;

-- POST /cards/block   { card, blocked: true|false }
DEFINE API OVERWRITE "/cards/block" FOR post
    MIDDLEWARE api::res::body("json")
    PERMISSIONS WHERE $auth.id != NONE
    THEN {
        LET $b = fn::read_json($request.body);
        LET $c = fn::own_card($b);
        IF $c.status != NONE { RETURN $c };
        IF type::is_bool($b.blocked) = false { RETURN fn::bad_request('invalid_blocked') };
        UPDATE $c.id SET blocked = $b.blocked;
        RETURN { status: 200, body: { card: record::id($c.id), blocked: $b.blocked } };
    };

-- POST /cards/limit   { card, monthly_limit: "3000.00" }
DEFINE API OVERWRITE "/cards/limit" FOR post
    MIDDLEWARE api::res::body("json")
    PERMISSIONS WHERE $auth.id != NONE
    THEN {
        LET $b = fn::read_json($request.body);
        LET $c = fn::own_card($b);
        IF $c.status != NONE { RETURN $c };
        IF type::is_string($b.monthly_limit) = false
           OR !string::matches($b.monthly_limit, "^[0-9]{1,9}([.][0-9]{1,2})?$") {
            RETURN fn::bad_request('invalid_limit')
        };
        LET $limit = <decimal>$b.monthly_limit;
        LET $max = (SELECT VALUE card_limit_max FROM ONLY setting:limits);
        IF $limit <= 0dec OR $limit > $max {
            RETURN { status: 422, body: { error: 'limit_out_of_range', max: <string>$max } }
        };
        UPDATE $c.id SET monthly_limit = $limit;
        RETURN { status: 200, body: { card: record::id($c.id), monthly_limit: <string>$limit } };
    };

-- ---------------------------------------------------------------------------
-- NOTIFICACIONES
--
-- La notificación es una FILA, con su marca de leída, y esa fila es la fuente
-- de verdad. LIVE SELECT solo sirve para que llegue al instante. Motivo,
-- medido en la 3.2.4: con un único suscriptor llegaron 30/30, pero con dos
-- suscriptores a la vez se perdieron entregas (23/30 y 24/30 como clientes en
-- dos mediciones, 28/30 como
-- root), sin ningún error, aunque la fila estaba guardada. Así que la app pide
-- las no leídas al abrir y al reconectar: un aviso perdido por el camino llega
-- tarde, pero no se pierde.
--
-- Se guarda el dato, no el texto: el idioma y el formato del importe son cosa
-- de la app.
DEFINE TABLE OVERWRITE notification SCHEMAFULL TYPE NORMAL
    PERMISSIONS FOR select, update WHERE customer = $auth.customer;
-- Con permiso de escritura sobre la fila, el cliente solo puede cambiar `read`:
-- todos los demás campos lo prohíben uno a uno.
DEFINE FIELD OVERWRITE customer ON notification TYPE record<customer>      PERMISSIONS FOR update NONE;
DEFINE FIELD OVERWRITE kind     ON notification TYPE string               PERMISSIONS FOR update NONE
    ASSERT $value IN ['incoming','payroll','expense','card_declined'];
DEFINE FIELD OVERWRITE account  ON notification TYPE option<record<account>> PERMISSIONS FOR update NONE;
DEFINE FIELD OVERWRITE amount   ON notification TYPE decimal              PERMISSIONS FOR update NONE;
DEFINE FIELD OVERWRITE concept  ON notification TYPE option<string>       PERMISSIONS FOR update NONE;
DEFINE FIELD OVERWRITE reason   ON notification TYPE option<string>       PERMISSIONS FOR update NONE;
DEFINE FIELD OVERWRITE txn      ON notification TYPE option<record<txn>>  PERMISSIONS FOR update NONE;
DEFINE FIELD OVERWRITE at       ON notification TYPE datetime VALUE time::now() READONLY;
DEFINE FIELD OVERWRITE read     ON notification TYPE bool DEFAULT false;
DEFINE INDEX OVERWRITE notification_by_customer ON notification FIELDS customer, read, at;

-- Cada apunte en una cuenta de cliente avisa a TODOS sus titulares: en una
-- cuenta conjunta, los dos se enteran de que ha entrado la nómina.
DEFINE EVENT OVERWRITE notify_movement ON entry
WHEN $event = "CREATE" AND $after.account.kind = 'customer' THEN {
    LET $kind = IF $after.amount < 0dec { 'expense' }
                ELSE IF $after.txn.kind = 'payroll' { 'payroll' }
                ELSE { 'incoming' };
    -- Recorrido de grafo, NO `SELECT … FROM owns WHERE out = …`: esa consulta
    -- recorría la tabla de aristas entera en cada apunte (EXPLAIN: TableScan)
    -- y era lo único de la ruta de pago que crecía con el banco. Medido con
    -- demo/write_bench.py a 1.000 clientes: ver db/README.md, «Volumen».
    FOR $who IN $after.account<-owns<-customer {
        CREATE notification SET customer = $who, kind = $kind, account = $after.account,
            amount = math::abs($after.amount), concept = $after.txn.concept, txn = $after.txn;
    };
};
