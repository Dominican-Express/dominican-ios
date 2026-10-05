-- Dominican Express — núcleo contable
-- Verificado contra SurrealDB 3.2.4 (macOS aarch64), 2026-09-28.
--
-- PRINCIPIO: `account.balance` NO es la fuente de verdad. La verdad es el
-- libro de apuntes `entry`, que es append-only. `balance` es un saldo
-- materializado que, en SurrealDB 3.2, cumple además una función crítica:
-- es el punto de conflicto write-write que serializa las transferencias
-- concurrentes. Ver db/README.md, sección "Concurrencia".

-- Los PERMISSIONS se expresan como TRAVESÍA DE GRAFO: "ves esta cuenta si
-- cuelga de una arista `owns` tuya". La autorización usa el mismo modelo que
-- la detección de fraude, en la misma base, sin tabla puente ni JOIN.
-- Sin cláusula, el valor por defecto de una tabla es PERMISSIONS NONE y un
-- usuario de registro no ve absolutamente nada. `root` se las salta todas.

DEFINE TABLE OVERWRITE customer SCHEMAFULL TYPE NORMAL
    PERMISSIONS FOR select WHERE id = $auth.customer;
DEFINE FIELD OVERWRITE name ON customer TYPE string;
DEFINE FIELD OVERWRITE nif  ON customer TYPE string;

DEFINE TABLE OVERWRITE account SCHEMAFULL TYPE NORMAL
    PERMISSIONS FOR select WHERE id IN $auth.customer->owns->account;
-- string::matches: los operadores de coincidencia difusa (~) se eliminaron en 3.0
DEFINE FIELD OVERWRITE iban     ON account TYPE string ASSERT string::matches($value, "^ES[0-9]{22}$");
DEFINE FIELD OVERWRITE currency ON account TYPE string DEFAULT 'EUR';
DEFINE FIELD OVERWRITE kind     ON account TYPE string DEFAULT 'customer' ASSERT $value IN ['customer','external'];
DEFINE FIELD OVERWRITE opened   ON account TYPE datetime VALUE time::now() READONLY;
DEFINE FIELD OVERWRITE balance  ON account TYPE decimal DEFAULT 0dec;

DEFINE TABLE OVERWRITE txn SCHEMAFULL TYPE NORMAL;
DEFINE FIELD OVERWRITE kind ON txn TYPE string ASSERT $value IN ['transfer','bizum','payroll','card','fee'];
DEFINE FIELD OVERWRITE at   ON txn TYPE datetime VALUE time::now() READONLY;

-- El apunte es inmutable: no se corrige, se compensa con otro apunte.
DEFINE TABLE OVERWRITE entry SCHEMAFULL TYPE NORMAL
    PERMISSIONS FOR select WHERE account IN $auth.customer->owns->account;
DEFINE FIELD OVERWRITE account ON entry TYPE record<account> READONLY;
DEFINE FIELD OVERWRITE txn     ON entry TYPE record<txn>     READONLY;
DEFINE FIELD OVERWRITE amount  ON entry TYPE decimal         READONLY;
-- DEFAULT y no VALUE: el generador de datos necesita poder fechar hacia atrás.
DEFINE FIELD OVERWRITE at      ON entry TYPE datetime DEFAULT time::now() READONLY;
DEFINE INDEX OVERWRITE entry_by_account ON entry FIELDS account, at;
DEFINE INDEX OVERWRITE entry_by_txn     ON entry FIELDS txn;

-- Tarjetas: TRES condiciones sobre la misma fila.
--  1. La tarjeta se ve si su cuenta es tuya (titular o cotitular).
--  2. El PAN y el CVV solo los ve quien la LLEVA (`holder`), no cualquier
--     cotitular: en una cuenta conjunta cada tarjeta sigue siendo personal.
--  3. Y además con una verificación vigente, que caduca sola.
-- Sin la condición 2, un cotitular verificado vería el PAN de la tarjeta del
-- otro. Eso es lo que no se puede expresar con permisos de tabla.
DEFINE TABLE OVERWRITE card SCHEMAFULL TYPE NORMAL
    PERMISSIONS FOR select WHERE account IN $auth.customer->owns->account;
DEFINE FIELD OVERWRITE account   ON card TYPE record<account>;
DEFINE FIELD OVERWRITE holder    ON card TYPE record<customer>;
DEFINE FIELD OVERWRITE pan_last4 ON card TYPE string;
DEFINE FIELD OVERWRITE blocked   ON card TYPE bool DEFAULT false;
DEFINE FIELD OVERWRITE pan ON card TYPE option<string>
    PERMISSIONS FOR select WHERE holder = $auth.customer AND $auth.verified_until > time::now();
DEFINE FIELD OVERWRITE cvv ON card TYPE option<string>
    PERMISSIONS FOR select WHERE holder = $auth.customer AND $auth.verified_until > time::now();
