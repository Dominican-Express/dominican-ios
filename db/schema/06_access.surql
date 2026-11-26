-- Dominican Express — autenticación y verificación reforzada
--
-- Hasta aquí todo se ejecutaba como `root`, que se salta TODOS los permisos.
-- Es decir: los permisos de campo sobre PAN y CVV existían en el esquema pero
-- no se podían demostrar. Esto los hace demostrables.
--
-- Las cláusulas PERMISSIONS de las tablas de negocio viven junto a cada tabla,
-- en 01_core y 02_graph: duplicar una definición en dos ficheros es garantía
-- de que acaben divergiendo.

DEFINE TABLE OVERWRITE app_user SCHEMAFULL TYPE NORMAL
    PERMISSIONS FOR select WHERE id = $auth.id;
    -- Sin FOR update: el usuario no puede tocar su propia ficha. Comprobado:
    -- ni ponerse `verified_until` en el año 3000, ni borrarse los fallos de
    -- PIN, ni cambiarse el `customer` por el de otro titular tienen efecto.
DEFINE FIELD OVERWRITE email    ON app_user TYPE string;
DEFINE FIELD OVERWRITE customer ON app_user TYPE record<customer>;
-- Los hashes no los lee NADIE, ni su propio dueño.
DEFINE FIELD OVERWRITE pass ON app_user TYPE string PERMISSIONS FOR select NONE;
DEFINE FIELD OVERWRITE pin  ON app_user TYPE string PERMISSIONS FOR select NONE;
DEFINE FIELD OVERWRITE verified_until   ON app_user TYPE option<datetime>;
DEFINE FIELD OVERWRITE pin_failures     ON app_user TYPE int DEFAULT 0;
DEFINE FIELD OVERWRITE pin_locked_until ON app_user TYPE option<datetime>;
DEFINE FIELD OVERWRITE login_failures     ON app_user TYPE int DEFAULT 0;
DEFINE FIELD OVERWRITE login_locked_until ON app_user TYPE option<datetime>;
DEFINE FIELD OVERWRITE last_login_at      ON app_user TYPE option<datetime>;
DEFINE INDEX OVERWRITE app_user_email ON app_user FIELDS email UNIQUE;

-- INICIO DE SESIÓN con límite de intentos: 5 contraseñas incorrectas seguidas
-- bloquean la cuenta 15 minutos, y el bloqueo rechaza incluso la correcta.
-- Un acierto pone el contador a cero.
--
-- Aquí sí se pueden contar los fallos dentro del acceso, al revés que con un
-- EVENT (ver el PIN, más abajo): el SIGNIN rechaza DEVOLVIENDO NONE, no
-- lanzando un error, así que la escritura del contador se queda. Comprobado
-- en 3.2.4: dos fallos dejan el contador en 2.
--  - Intentos a la vez: todos escriben la misma ficha, así que el aislamiento
--    por instantánea deshace todos menos uno (medido: 10 a la vez, 1 contado,
--    9 deshechos). El deshecho responde 400 y no 404, así que se distingue.
--    Por eso el ACIERTO también escribe siempre (`last_login_at`): un 400
--    puede venir de un acierto o de un fallo y no dice nada. Las únicas
--    respuestas que informan, 404 y token, quedan todas contadas.
--  - Para un email que no existe se compara igual contra un hash cualquiera
--    (el resultado se ignora), para que el tiempo de respuesta no delate qué
--    emails tienen cuenta.
--  - El cliente no distingue «bloqueada» de «contraseña incorrecta»: las dos
--    responden lo mismo. Coste conocido: cualquiera que sepa el email puede
--    bloquear la cuenta 15 minutos; el PIN tiene el mismo compromiso.
DEFINE ACCESS OVERWRITE banca ON DATABASE TYPE RECORD
    SIGNIN {
        LET $u = (SELECT * FROM ONLY app_user WHERE email = $email LIMIT 1);
        IF $u = NONE {
            crypto::argon2::compare('$argon2id$v=19$m=19456,t=2,p=1$f6+pN25bhty9vAP9hUpPfA$YsQ9SKpVGvpNGYEw5wCMH/r0RllHueP0jUS1NETwQTw', $pass);
            RETURN NONE;
        };
        IF $u.login_locked_until != NONE AND $u.login_locked_until > time::now() {
            RETURN NONE;
        };
        IF !crypto::argon2::compare($u.pass, $pass) {
            LET $fails = (UPDATE ONLY $u.id SET login_failures += 1 RETURN VALUE login_failures);
            IF $fails >= 5 {
                UPDATE $u.id SET login_failures = 0, login_locked_until = time::now() + 15m;
            };
            RETURN NONE;
        };
        UPDATE $u.id SET login_failures = 0, login_locked_until = NONE, last_login_at = time::now();
        RETURN $u.id;
    }
    DURATION FOR TOKEN 15m, FOR SESSION 2h;

-- ---------------------------------------------------------------------------
-- VERIFICACIÓN POR PIN:  POST /api/<ns>/<db>/verify-pin   { pin }
--
-- Abre una ventana de 90 s durante la cual el titular ve el PAN y el CVV de
-- SUS tarjetas. Tras 3 fallos seguidos, la verificación se bloquea 15 minutos,
-- y el bloqueo rechaza incluso el PIN correcto.
--
-- Historia de esta pieza, porque explica el diseño:
--  1. Una DEFINE FUNCTION no sirve: corre con los permisos de quien la llama,
--     así que su UPDATE no hacía nada y aun así devolvía `true`.
--  2. Un EVENT sí escribía con privilegio, pero no puede contar fallos: para
--     rechazar tiene que lanzar un error, y el error deshace también el
--     contador. Con un evento, un PIN de 4 cifras admitía 10.000 intentos.
--  3. Un endpoint rechaza DEVOLVIENDO un 401, sin lanzar nada, así que el fallo
--     queda guardado. Por eso es la pieza correcta.

REMOVE TABLE IF EXISTS step_up;
REMOVE FUNCTION IF EXISTS fn::verify_step_up;

DEFINE API OVERWRITE "/verify-pin" FOR post
    MIDDLEWARE api::res::body("json")
    PERMISSIONS WHERE $auth.id != NONE
    THEN {
        LET $b = fn::read_json($request.body);
        IF type::is_object($b) = false OR type::is_string($b.pin) = false
           OR !string::matches($b.pin, "^[0-9]{4}$") {
            RETURN fn::bad_request('invalid_pin_format')
        };
        LET $u = (SELECT * FROM ONLY $auth.id);
        IF $u.pin_locked_until != NONE AND $u.pin_locked_until > time::now() {
            RETURN { status: 423, body: { error: 'pin_locked', locked_until: <string>$u.pin_locked_until } }
        };
        IF !crypto::argon2::compare($u.pin, $b.pin) {
            LET $fails = $u.pin_failures + 1;
            IF $fails >= 3 {
                UPDATE $u.id SET pin_failures = 0, pin_locked_until = time::now() + 15m;
                RETURN { status: 423, body: { error: 'pin_locked', attempts_left: 0 } };
            };
            UPDATE $u.id SET pin_failures = $fails;
            RETURN { status: 401, body: { error: 'wrong_pin', attempts_left: 3 - $fails } };
        };
        LET $until = time::now() + 90s;
        UPDATE $u.id SET pin_failures = 0, pin_locked_until = NONE, verified_until = $until;
        RETURN { status: 200, body: { verified_until: <string>$until } };
    };
