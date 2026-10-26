-- Dominican Express — controles de banco de verdad
--
-- La máquina del tiempo (09) investiga DESPUÉS de que borren el rastro. Un
-- banco no confía en eso como prueba: caduca a los 30 días, vive en el mismo
-- servidor, no dice QUIÉN cambió algo y el motor está en beta. Lo que hace es
-- impedir que el rastro se borre. Tres piezas:
--
--  1. NO SE BORRA, SE TERMINA. Dejar de usar un aparato pone `ended_at`; la
--     relación se queda. Los clientes no pueden borrar (permisos), igual que
--     ya no pueden tocar un apunte del libro.
--  2. AUDITORÍA CON QUIÉN. Cada cambio en lo sensible deja una fila inmutable
--     en `audit_log`: qué, antes, después, cuándo y quién. La escriben eventos:
--     no hay camino para saltársela.
--  3. CONGELAR AL DETECTAR, con respuesta proporcional a la alerta.
--
-- Lo que esto NO cubre y hay que decir: root puede borrar filas, también de
-- audit_log, y REMOVE TABLE no se puede impedir. En un banco la auditoría se
-- copia en caliente fuera de la base, a un almacenamiento que no se puede
-- reescribir (WORM), con la retención legal (5 años la directiva europea,
-- 10 la ley española). Aquí no montamos esa copia.

-- ---------------------------------------------------------------------------
-- 3. CONGELACIÓN: campos de la cuenta.
DEFINE FIELD OVERWRITE frozen_at ON account TYPE option<datetime>;
DEFINE FIELD OVERWRITE frozen_by ON account TYPE option<record<fraud_alert>>;
DEFINE FIELD OVERWRITE review_at ON account TYPE option<datetime>;
DEFINE FIELD OVERWRITE released_note ON account TYPE option<string>;

-- Respuesta PROPORCIONAL a cada alerta. Congelar a cuatro personas por
-- compartir un móvil sería castigar a una familia: eso va a revisión.
--   mule_ring          → congelar la cuenta (no envía dinero) y bloquear sus tarjetas
--   impossible_travel  → bloquear la tarjeta
--   shared_device, structuring, velocity → «en revisión»: un analista mira
--   low_balance        → nada
-- Congelar bloquea las SALIDAS; el dinero que entra sigue llegando.
-- Al cliente no se le dice por qué: avisar a un sospechoso de blanqueo de que
-- se le investiga está prohibido (tipping-off). La API solo dice account_frozen.
DEFINE EVENT OVERWRITE respond ON fraud_alert WHEN $event = 'CREATE' THEN {
    LET $kind = $after.kind;
    IF $kind = 'mule_ring' {
        LET $acc = $after.account;
        UPDATE $acc SET frozen_at = time::now(), frozen_by = $after.id WHERE frozen_at = NONE;
        UPDATE card SET blocked = true WHERE account = $acc AND blocked = false;
    } ELSE IF $kind = 'impossible_travel' {
        LET $card = $after.card;
        UPDATE $card SET blocked = true WHERE blocked = false;
    } ELSE IF $kind IN ['shared_device', 'structuring', 'velocity'] {
        LET $accs = IF $after.device != NONE {
            array::flatten($after.detail.holders.map(|$c| type::record($c)->owns->account))
        } ELSE { [$after.account] };
        UPDATE $accs SET review_at = time::now() WHERE review_at = NONE;
    };
};

-- Liberar es cosa del equipo antifraude (PERMISSIONS NONE), con una nota, y
-- queda en la auditoría. Las tarjetas NO se desbloquean solas: lo pide el
-- cliente, con su PIN (/cards/block).
DEFINE FUNCTION OVERWRITE fn::release_account($acc: record<account>, $note: string) {
    UPDATE $acc SET frozen_at = NONE, frozen_by = NONE, review_at = NONE, released_note = $note;
    RETURN (SELECT VALUE id FROM ONLY $acc);
} PERMISSIONS NONE;

-- ---------------------------------------------------------------------------
-- 1. NO SE BORRA, SE TERMINA.
DEFINE FIELD OVERWRITE ended_at ON uses TYPE option<datetime>;

-- POST /devices/unlink   { device }
-- El cliente deja de usar un aparato suyo. La relación se queda con fecha de
-- fin: el detector de aparato compartido la sigue contando, porque desvincularse
-- no borra que lo usaste. Un aparato ajeno, o ya desvinculado, da el mismo 404.
DEFINE API OVERWRITE "/devices/unlink" FOR post
    MIDDLEWARE api::res::body("json")
    PERMISSIONS WHERE $auth.id != NONE
    THEN {
        LET $b = fn::read_json($request.body);
        IF type::is_object($b) = false OR type::is_string($b.device) = false
           OR !string::matches($b.device, "^device:[A-Za-z0-9_]{1,64}$") {
            RETURN fn::bad_request('invalid_device')
        };
        LET $dev = type::record($b.device);
        LET $me = $auth.customer;
        LET $edge = (SELECT VALUE id FROM uses WHERE in = $me AND out = $dev AND ended_at = NONE)[0];
        IF $edge = NONE { RETURN { status: 404, body: { error: 'device_not_found' } } };
        UPDATE $edge SET ended_at = time::now();
        RETURN { status: 200, body: { device: $dev, ended: true } };
    };

-- ---------------------------------------------------------------------------
-- 2. AUDITORÍA.
--
-- Nadie la lee salvo el equipo antifraude (root / staff), y nadie la escribe
-- salvo los eventos. Campos READONLY: una fila no se corrige, se añade otra.
-- `actor` es el usuario de la app que hizo el cambio, o NONE si fue root o un
-- proceso del propio banco (el barrido); `via` dice cuál (`banca` = la app).
DEFINE TABLE OVERWRITE audit_log SCHEMAFULL TYPE NORMAL PERMISSIONS NONE;
DEFINE FIELD OVERWRITE tbl    ON audit_log TYPE string READONLY;
DEFINE FIELD OVERWRITE rec    ON audit_log TYPE record READONLY;
DEFINE FIELD OVERWRITE action ON audit_log TYPE string READONLY;
DEFINE FIELD OVERWRITE before ON audit_log TYPE option<object> FLEXIBLE READONLY;
DEFINE FIELD OVERWRITE after  ON audit_log TYPE option<object> FLEXIBLE READONLY;
DEFINE FIELD OVERWRITE actor  ON audit_log TYPE option<record> READONLY;
DEFINE FIELD OVERWRITE via    ON audit_log TYPE string READONLY;
DEFINE FIELD OVERWRITE at     ON audit_log TYPE datetime VALUE time::now() READONLY;
DEFINE INDEX OVERWRITE audit_by_rec ON audit_log FIELDS rec, at;

DEFINE FUNCTION OVERWRITE fn::audit($tbl: string, $rec: record, $action: string,
                                    $before: option<object>, $after: option<object>) {
    CREATE audit_log SET tbl = $tbl, rec = $rec, action = $action,
        before = $before, after = $after,
        actor = $auth.id, via = $session.ac ?? 'root';
} PERMISSIONS NONE;

-- Qué se audita. Lo que mueve dinero ya está en el libro (inmutable) y en
-- payment_order: auditar cada cambio de saldo duplicaría millones de filas. Por
-- eso la cuenta solo se audita cuando cambia algo que NO es el saldo.
-- Nunca entran el PAN, el CVV ni el NIF: la auditoría la leen analistas.
DEFINE EVENT OVERWRITE audit_uses ON uses THEN
    fn::audit('uses', $value.id, $event, $before.{in, out, ended_at}, $after.{in, out, ended_at});
DEFINE EVENT OVERWRITE audit_owns ON owns THEN
    fn::audit('owns', $value.id, $event, $before.{in, out, role}, $after.{in, out, role});
DEFINE EVENT OVERWRITE audit_device ON device THEN
    fn::audit('device', $value.id, $event, $before.{fingerprint}, $after.{fingerprint});
-- Cada cobro reescribe `last_used_at` (08_cards): sin el WHEN, una fila por pago.
DEFINE EVENT OVERWRITE audit_card ON card
    WHEN $event != 'UPDATE'
      OR $before.blocked != $after.blocked
      OR $before.monthly_limit != $after.monthly_limit
      OR $before.account != $after.account
      OR $before.holder != $after.holder
    THEN fn::audit('card', $value.id, $event,
              $before.{account, holder, blocked, monthly_limit},
              $after.{account, holder, blocked, monthly_limit});
DEFINE EVENT OVERWRITE audit_account ON account
    WHEN $event != 'UPDATE'
      OR $before.frozen_at != $after.frozen_at
      OR $before.review_at != $after.review_at
      OR $before.iban != $after.iban
    THEN fn::audit('account', $value.id, $event,
                   $before.{iban, kind, frozen_at, frozen_by, review_at, released_note},
                   $after.{iban, kind, frozen_at, frozen_by, review_at, released_note});
DEFINE EVENT OVERWRITE audit_customer ON customer THEN
    fn::audit('customer', $value.id, $event,
              $before.{name, phone, bizum_account}, $after.{name, phone, bizum_account});
