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
DEFINE INDEX OVERWRITE app_user_email ON app_user FIELDS email UNIQUE;

DEFINE ACCESS OVERWRITE banca ON DATABASE TYPE RECORD
    SIGNIN ( SELECT * FROM app_user
             WHERE email = $email AND crypto::argon2::compare(pass, $pass) )
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
