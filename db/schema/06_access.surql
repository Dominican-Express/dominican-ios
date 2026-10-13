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
    -- ni ponerse `verified_until` en el año 3000 ni cambiarse el `customer`
    -- por el de otro titular tienen efecto.
DEFINE FIELD OVERWRITE email    ON app_user TYPE string;
DEFINE FIELD OVERWRITE customer ON app_user TYPE record<customer>;
-- Los hashes no los lee NADIE, ni su propio dueño.
DEFINE FIELD OVERWRITE pass ON app_user TYPE string PERMISSIONS FOR select NONE;
DEFINE FIELD OVERWRITE pin  ON app_user TYPE string PERMISSIONS FOR select NONE;
DEFINE FIELD OVERWRITE verified_until ON app_user TYPE option<datetime>;
DEFINE INDEX OVERWRITE app_user_email ON app_user FIELDS email UNIQUE;

DEFINE ACCESS OVERWRITE banca ON DATABASE TYPE RECORD
    SIGNIN ( SELECT * FROM app_user
             WHERE email = $email AND crypto::argon2::compare(pass, $pass) )
    DURATION FOR TOKEN 15m, FOR SESSION 2h;

-- ---------------------------------------------------------------------------
-- VERIFICACIÓN REFORZADA (step-up)
--
-- El problema: abrir la ventana exige escribir `app_user.verified_until`, y el
-- usuario no tiene permiso de escritura sobre su ficha (a propósito, ver
-- arriba). Una DEFINE FUNCTION no sirve: se ejecuta con los permisos de quien
-- la llama, así que su UPDATE no hace nada y, peor, la función devuelve éxito
-- igualmente. Comprobado: devolvía `true` con `verified_until` intacto.
--
-- La solución idiomática es un EVENT, que se ejecuta SIN comprobar permisos.
-- El usuario solo puede CREAR una petición; el evento comprueba el PIN contra
-- el hash y únicamente entonces abre la ventana. El usuario puede provocar la
-- escritura privilegiada, pero no falsificarla.

DEFINE TABLE OVERWRITE step_up SCHEMAFULL TYPE NORMAL
    PERMISSIONS FOR create WHERE $auth.id != NONE;
-- `user` lo fija la base, no el cliente: nadie puede pedir la verificación de otro.
DEFINE FIELD OVERWRITE user ON step_up TYPE record<app_user> VALUE $auth.id READONLY;
DEFINE FIELD OVERWRITE pin  ON step_up TYPE string;

DEFINE EVENT OVERWRITE step_up_check ON step_up WHEN $event = "CREATE" THEN {
    LET $ok = crypto::argon2::compare($after.user.pin, $after.pin);
    -- La petición se borra siempre: el PIN en claro no se queda en la base.
    DELETE $after.id;
    IF !$ok { THROW "PIN incorrecto" };
    UPDATE $after.user SET verified_until = time::now() + 90s;
};

-- Envoltorio para el cliente. Si el PIN falla, el THROW del evento deshace la
-- transacción entera y la llamada devuelve el error.
DEFINE FUNCTION OVERWRITE fn::verify_step_up($pin: string) {
    CREATE step_up SET pin = $pin;
    RETURN true;
};
