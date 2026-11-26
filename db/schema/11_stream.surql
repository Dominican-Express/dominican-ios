-- Dominican Express: pagos que llegan por Kafka (db/STREAMING.md)
--
-- Los pagos de fuera del banco (red de tarjetas, otros bancos, pasarela de
-- Bizum) llegan al topic `payments`. Un consumidor (demo/stream_consumer.py)
-- los aplica uno a uno llamando a fn::stream_apply.
--
-- Kafka entrega cada mensaje AL MENOS una vez: si el consumidor se cae después
-- de pagar y antes de confirmar el offset, al volver recibe otra vez el mismo
-- mensaje. Para que eso no cobre dos veces, cada mensaje trae su propio id y
-- queda apuntado en `stream_msg` EN LA MISMA TRANSACCIÓN que el pago: o se
-- guardan los dos o ninguno. Una segunda copia encuentra el apunte y no paga.
-- Si dos copias llegan a la vez, escriben el mismo registro y chocan: una se
-- deshace y su reintento ve la primera. Es el mismo mecanismo que la
-- idempotencia de payment_order (07_api) y que el saldo materializado (03).

DEFINE TABLE OVERWRITE stream_msg SCHEMAFULL TYPE NORMAL PERMISSIONS NONE;
DEFINE FIELD OVERWRITE status ON stream_msg TYPE string ASSERT $value IN ['done','rejected'];
DEFINE FIELD OVERWRITE reason ON stream_msg TYPE option<string>;
DEFINE FIELD OVERWRITE from   ON stream_msg TYPE record<account>;
DEFINE FIELD OVERWRITE to     ON stream_msg TYPE record<account>;
DEFINE FIELD OVERWRITE amount ON stream_msg TYPE decimal;
DEFINE FIELD OVERWRITE txn    ON stream_msg TYPE option<record<txn>>;
-- De dónde salió la copia que se aplicó: topic/partición@offset. Sirve para
-- auditar y para ver en la prueba qué copia ganó.
DEFINE FIELD OVERWRITE source ON stream_msg TYPE string;
-- Huella del contenido. Una copia repetida trae la misma; un mensaje DISTINTO
-- con un id ya usado trae otra, y no debe darse por repetido en silencio.
DEFINE FIELD OVERWRITE digest ON stream_msg TYPE string;
DEFINE FIELD OVERWRITE at     ON stream_msg TYPE datetime VALUE time::now() READONLY;

-- Aplica un mensaje. Devuelve { status, reason, duplicate }.
-- Los rechazos se GUARDAN y no se lanzan: un THROW desharía también el apunte
-- en stream_msg, y la copia repetida volvería a intentarlo. Por eso las
-- comprobaciones se hacen antes de llamar a fn::transfer, como en
-- fn::place_order. Un rechazo es definitivo para ese id, como un pago hecho:
-- releer el topic no lo reintenta. Un pago que deba repetirse es un mensaje
-- nuevo, con id nuevo.
DEFINE FUNCTION OVERWRITE fn::stream_apply($key: string, $from: record<account>,
        $to: record<account>, $amount: decimal, $kind: string, $source: string) {
    LET $id = type::record('stream_msg', $key);
    LET $digest = crypto::sha256(<string>[$from, $to, $amount, $kind]);
    LET $prev = (SELECT * FROM ONLY $id);
    IF $prev != NONE {
        IF $prev.digest != $digest {
            RETURN { status: 'rejected', reason: 'id_reused', duplicate: true };
        };
        RETURN { status: $prev.status, reason: $prev.reason, duplicate: true };
    };

    LET $f = (SELECT * FROM ONLY $from);
    LET $t = (SELECT * FROM ONLY $to);
    LET $reason = IF $f = NONE OR $t = NONE {
            'account_not_found'
        } ELSE IF $from = $to {
            'same_account'
        } ELSE IF $amount <= 0dec {
            'invalid_amount'
        } ELSE IF $kind NOT IN ['transfer', 'bizum', 'payroll'] {
            -- Lo que puede llegar de fuera. `card` y `fee` los crea el banco;
            -- sin esto, el ASSERT de txn.kind lanzaría y el consumidor se
            -- quedaría reintentando el mismo mensaje.
            'invalid_kind'
        } ELSE IF $f.currency != $t.currency {
            'currency_mismatch'
        } ELSE IF $f.frozen_at != NONE {
            'account_frozen'
        } ELSE IF fn::balance($from) < $amount {
            'insufficient_funds'
        } ELSE {
            NONE
        };

    IF $reason != NONE {
        CREATE $id SET status = 'rejected', reason = $reason, from = $from, to = $to,
            amount = $amount, source = $source, digest = $digest;
        RETURN { status: 'rejected', reason: $reason, duplicate: false };
    };

    LET $tx = fn::transfer($from, $to, $amount, $kind, NONE);
    CREATE $id SET status = 'done', from = $from, to = $to, amount = $amount,
        txn = $tx, source = $source, digest = $digest;
    RETURN { status: 'done', reason: NONE, duplicate: false };
} PERMISSIONS NONE;
