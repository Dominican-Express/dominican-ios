-- Dominican Express — la API, definida dentro de SurrealDB
--
-- No hay backend intermedio (se descartó Java). Las apps hablan con SurrealDB:
--   - LEEN con consultas normales, protegidas por los permisos de grafo de
--     01_core y 02_graph;
--   - ESCRIBEN lo que exige privilegio (mover dinero, añadir contactos) por
--     estos endpoints, servidos en  POST /api/<ns>/<db>/<ruta>.
--
-- Por qué así y no todo por endpoints: el cuerpo de un DEFINE API se ejecuta
-- SIN comprobar permisos. Si las lecturas pasaran por aquí, la protección del
-- PAN, del CVV o de las cuentas ajenas dependería de que cada endpoint la
-- repitiera bien. Dejándolas en los permisos, la base las aplica siempre.
--
-- Cada endpoint comprueba por sí mismo QUIÉN llama ($auth) y QUÉ es suyo.
-- Y todo devuelve JSON con códigos HTTP de verdad.

-- ---------------------------------------------------------------------------
-- LÍMITES. Valores ilustrativos, no calibrados con datos reales.
-- Se cambian con  UPDATE setting:limits SET …  (solo root).
DEFINE TABLE OVERWRITE setting SCHEMALESS TYPE NORMAL PERMISSIONS NONE;
UPSERT setting:limits MERGE {
    transfer_max: 50000dec,
    bizum_min: 0.50dec,
    bizum_max: 1000dec
};

-- ---------------------------------------------------------------------------
-- ÓRDENES DE PAGO: registro de auditoría y clave de idempotencia a la vez.
--
-- El id lo elige el cliente (un UUID por intento de pago). Si la red se corta y
-- el cliente repite la orden con el MISMO id, recibe la respuesta original en
-- vez de pagar dos veces. Si dos copias llegan a la vez, escriben el mismo
-- registro: chocan, una se rechaza por conflicto y su reintento ve la orden ya
-- hecha. La idempotencia sale del mismo mecanismo que evita los descubiertos.
--
-- Se guardan también las RECHAZADAS: un intento de pagar desde una cuenta
-- ajena es precisamente lo que hay que poder auditar.
DEFINE TABLE OVERWRITE payment_order SCHEMAFULL TYPE NORMAL
    PERMISSIONS FOR select WHERE requester = $auth.id;
DEFINE FIELD OVERWRITE requester   ON payment_order TYPE record<app_user> READONLY;
DEFINE FIELD OVERWRITE kind        ON payment_order TYPE string ASSERT $value IN ['transfer','bizum'];
DEFINE FIELD OVERWRITE from        ON payment_order TYPE option<record<account>>;
DEFINE FIELD OVERWRITE to_ref      ON payment_order TYPE string;   -- IBAN o teléfono, tal como llegó
DEFINE FIELD OVERWRITE amount      ON payment_order TYPE decimal;
DEFINE FIELD OVERWRITE concept     ON payment_order TYPE option<string>;
DEFINE FIELD OVERWRITE status      ON payment_order TYPE string ASSERT $value IN ['done','rejected'];
DEFINE FIELD OVERWRITE reason      ON payment_order TYPE option<string>;
DEFINE FIELD OVERWRITE http_status ON payment_order TYPE int;
DEFINE FIELD OVERWRITE txn         ON payment_order TYPE option<record<txn>>;
DEFINE FIELD OVERWRITE balance_after ON payment_order TYPE option<decimal>;
DEFINE FIELD OVERWRITE at          ON payment_order TYPE datetime VALUE time::now() READONLY;
DEFINE INDEX OVERWRITE order_by_requester ON payment_order FIELDS requester, at;

-- Respuesta de una orden, nueva o repetida: siempre la misma forma.
-- Los importes salen como TEXTO: un número JSON es coma flotante y el dinero
-- no lo es.
DEFINE FUNCTION OVERWRITE fn::order_reply($o: object) {
    RETURN {
        status: $o.http_status,
        body: {
            order: record::id($o.id),
            status: $o.status,
            reason: $o.reason,
            amount: <string>$o.amount,
            balance_after: IF $o.balance_after = NONE { NONE } ELSE { <string>$o.balance_after }
        }
    };
} PERMISSIONS NONE;

-- Lee el cuerpo de la petición. Por qué NO se usa api::req::body("json"):
-- ese lector convierte en tipos de SurrealDB cualquier texto que se les
-- parezca. "account:ana" llega como referencia a un registro, una fecha ISO
-- llega como fecha, y "Cena: viernes" llega como el registro `Cena:viernes`,
-- SIN EL ESPACIO: altera en silencio lo que escribió el cliente. Sin lector,
-- el cuerpo llega en bytes intactos y encoding::json::decode respeta los tipos
-- de JSON: un texto sigue siendo texto. Tampoco evalúa nada de lo que traiga.
--
-- Tope de 16 KB a mano: la documentación lista api::req::max_body(), pero en
-- la 3.2.4 no existe ("no such builtin function found").
-- Limitación conocida: un JSON MALFORMADO hace que decode lance, y un error
-- lanzado dentro de un endpoint sale como 500, no como 400. SurrealQL no tiene
-- try/catch. Los clientes siempre mandan JSON serializado, así que no afecta
-- al uso normal.
DEFINE FUNCTION OVERWRITE fn::read_json($raw: any) {
    IF $raw = NONE OR type::is_bytes($raw) = false OR bytes::len($raw) > 16384 { RETURN NONE };
    RETURN encoding::json::decode(<string>$raw);
} PERMISSIONS NONE;

DEFINE FUNCTION OVERWRITE fn::bad_request($code: string) {
    RETURN { status: 400, body: { error: $code } };
} PERMISSIONS NONE;

-- Ejecuta (o repite) una orden ya resuelta. Lo comparten /transfers y /bizum.
-- $to = NONE significa que el destino no existe.
DEFINE FUNCTION OVERWRITE fn::place_order($key: string, $kind: string,
        $from: option<record<account>>, $to: option<record<account>>,
        $to_ref: string, $amount: decimal, $concept: option<string>) {

    LET $id = type::record('payment_order', $key);
    LET $prev = (SELECT * FROM ONLY $id);
    IF $prev != NONE {
        -- La misma clave usada por OTRO usuario no le revela nada de la orden.
        IF $prev.requester != $auth.id { RETURN { status: 409, body: { error: 'order_id_in_use' } } };
        RETURN fn::order_reply($prev);
    };

    LET $limits = (SELECT * FROM ONLY setting:limits);
    LET $reject = IF $from = NONE OR $from NOTINSIDE $auth.customer->owns->account {
            [403, 'not_your_account']
        } ELSE IF $to = NONE {
            [404, 'destination_not_found']
        } ELSE IF $from = $to {
            [422, 'same_account']
        } ELSE IF $from.currency != $to.currency {
            [422, 'currency_mismatch']
        } ELSE IF $kind = 'bizum' AND ($amount < $limits.bizum_min OR $amount > $limits.bizum_max) {
            [422, 'bizum_amount_out_of_range']
        } ELSE IF $kind = 'transfer' AND $amount > $limits.transfer_max {
            [422, 'amount_over_limit']
        } ELSE IF fn::balance($from) < $amount {
            [422, 'insufficient_funds']
        } ELSE {
            NONE
        };

    IF $reject != NONE {
        LET $o = (CREATE ONLY $id SET requester = $auth.id, kind = $kind, from = $from,
                  to_ref = $to_ref, amount = $amount, concept = $concept,
                  status = 'rejected', reason = $reject[1], http_status = $reject[0]);
        RETURN fn::order_reply($o);
    };

    LET $tx = fn::transfer($from, $to, $amount, $kind, $concept);
    LET $o = (CREATE ONLY $id SET requester = $auth.id, kind = $kind, from = $from,
              to_ref = $to_ref, amount = $amount, concept = $concept,
              status = 'done', http_status = 201, txn = $tx,
              balance_after = (SELECT VALUE balance FROM ONLY $from));
    RETURN fn::order_reply($o);
} PERMISSIONS NONE;

-- Validación de la entrada común a las dos órdenes. Devuelve el código de
-- error o NONE. Lo malformado NO se registra: no es una orden, es basura.
DEFINE FUNCTION OVERWRITE fn::check_order_input($b: any) {
    RETURN IF type::is_object($b) = false {
            'body_must_be_json_object'
        } ELSE IF type::is_string($b.id) = false OR !string::matches($b.id, "^[A-Za-z0-9_-]{8,64}$") {
            'invalid_order_id'
        } ELSE IF type::is_string($b.amount) = false OR !string::matches($b.amount, "^[0-9]{1,9}([.][0-9]{1,2})?$") {
            'invalid_amount'
        } ELSE IF <decimal>$b.amount <= 0dec {
            'invalid_amount'
        } ELSE IF $b.concept != NONE AND (type::is_string($b.concept) = false OR string::len($b.concept) > 140) {
            'invalid_concept'
        } ELSE {
            NONE
        };
} PERMISSIONS NONE;

-- ---------------------------------------------------------------------------
-- POST /transfers   { id, from, to_iban, amount, concept? }
-- Transferencia entre cuentas del banco. `from` es una cuenta tuya, como
-- titular o como cotitular; el destino se da por IBAN, porque una cuenta ajena
-- no la puedes ver ni saber su id.
DEFINE API OVERWRITE "/transfers" FOR post
    MIDDLEWARE api::res::body("json")
    PERMISSIONS WHERE $auth.id != NONE
    THEN {
        LET $b = fn::read_json($request.body);
        LET $err = fn::check_order_input($b);
        IF $err != NONE { RETURN fn::bad_request($err) };
        IF type::is_string($b.to_iban) = false { RETURN fn::bad_request('invalid_iban') };
        IF type::is_string($b.from) = false OR !string::matches($b.from, "^account:[A-Za-z0-9_]{1,64}$") {
            RETURN fn::bad_request('invalid_from')
        };
        LET $from = (SELECT VALUE id FROM ONLY type::record($b.from));
        LET $iban = $b.to_iban;
        LET $to = (SELECT VALUE id FROM account
                   WHERE iban = $iban AND kind = 'customer' LIMIT 1)[0];
        RETURN fn::place_order($b.id, 'transfer', $from, $to, $b.to_iban,
                               <decimal>$b.amount, $b.concept);
    };

-- ---------------------------------------------------------------------------
-- POST /bizum   { id, to_phone, amount, concept? }
-- Sale siempre de TU cuenta de Bizum y llega a la del destinatario.
DEFINE API OVERWRITE "/bizum" FOR post
    MIDDLEWARE api::res::body("json")
    PERMISSIONS WHERE $auth.id != NONE
    THEN {
        LET $b = fn::read_json($request.body);
        LET $err = fn::check_order_input($b);
        IF $err != NONE { RETURN fn::bad_request($err) };
        IF type::is_string($b.to_phone) = false OR !string::matches($b.to_phone, "^[+]34[0-9]{9}$") {
            RETURN fn::bad_request('invalid_phone')
        };
        LET $from = $auth.customer.bizum_account;
        IF $from = NONE { RETURN { status: 409, body: { error: 'bizum_not_enabled' } } };
        LET $phone = $b.to_phone;
        LET $to = (SELECT VALUE bizum_account FROM customer WHERE phone = $phone LIMIT 1)[0];
        RETURN fn::place_order($b.id, 'bizum', $from, $to, $b.to_phone,
                               <decimal>$b.amount, $b.concept);
    };

-- ---------------------------------------------------------------------------
-- POST /contacts   { phone }
-- Añade un contacto frecuente. Desde ese momento ves su nombre y su teléfono
-- (y solo eso: ver el permiso de `customer` en 01_core).
DEFINE API OVERWRITE "/contacts" FOR post
    MIDDLEWARE api::res::body("json")
    PERMISSIONS WHERE $auth.id != NONE
    THEN {
        LET $b = fn::read_json($request.body);
        IF type::is_object($b) = false OR type::is_string($b.phone) = false
           OR !string::matches($b.phone, "^[+]34[0-9]{9}$") {
            RETURN fn::bad_request('invalid_phone')
        };
        LET $phone = $b.phone;
        LET $c = (SELECT * FROM customer WHERE phone = $phone LIMIT 1)[0];
        IF $c = NONE { RETURN { status: 404, body: { error: 'not_a_customer' } } };
        IF $c.id = $auth.customer { RETURN { status: 422, body: { error: 'cannot_add_yourself' } } };
        LET $already = count(SELECT id FROM favorite WHERE in = $auth.customer AND out = $c.id) > 0;
        IF !$already { RELATE ($auth.customer)->favorite->($c.id) };
        RETURN {
            status: IF $already { 200 } ELSE { 201 },
            body: { contact: <string>$c.id, name: $c.name, phone: $c.phone }
        };
    };
