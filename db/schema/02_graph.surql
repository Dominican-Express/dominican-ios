-- Dominican Express — capa de grafo
--
-- `transfer` DUPLICA a propósito lo que ya está en `entry`. El ledger es la
-- verdad contable; la arista es la proyección de grafo sobre la que corren
-- las travesías de fraude. Se escriben en la MISMA transacción, así que no
-- pueden divergir. Dos modelos del mismo hecho en una sola base, sin ETL:
-- ese es el argumento multi-modelo, y es la respuesta a "¿por qué dos veces?".

-- Las aristas también llevan permisos: una consulta del cliente que recorre
-- el grafo solo atraviesa las aristas que puede leer.

-- Ves las aristas de titularidad de TUS cuentas: así la pantalla de cuenta
-- compartida puede listar a los cotitulares y su rol.
DEFINE TABLE OVERWRITE owns TYPE RELATION IN customer OUT account ENFORCED
    PERMISSIONS FOR select WHERE out IN $auth.customer->owns->account;
DEFINE FIELD OVERWRITE role ON owns TYPE string ASSERT $value IN ['titular','cotitular'];
-- Cotitularidad = atributo en la ARISTA, no tabla puente.

DEFINE TABLE OVERWRITE transfer TYPE RELATION IN account OUT account ENFORCED;
DEFINE FIELD OVERWRITE amount ON transfer TYPE decimal;
DEFINE FIELD OVERWRITE txn    ON transfer TYPE option<record<txn>>;
DEFINE FIELD OVERWRITE at     ON transfer TYPE datetime DEFAULT time::now();
DEFINE INDEX OVERWRITE transfer_by_at ON transfer FIELDS at;

DEFINE TABLE OVERWRITE device SCHEMAFULL TYPE NORMAL;
DEFINE FIELD OVERWRITE fingerprint ON device TYPE string;
DEFINE TABLE OVERWRITE uses TYPE RELATION IN customer OUT device ENFORCED;

-- Contactos frecuentes. Solo ves los tuyos; se crean por POST /contacts.
DEFINE TABLE OVERWRITE favorite TYPE RELATION IN customer OUT customer ENFORCED
    PERMISSIONS FOR select WHERE in = $auth.customer;
DEFINE INDEX OVERWRITE favorite_pair ON favorite FIELDS in, out UNIQUE;

-- Pagos con tarjeta, con geolocalización para el detector de viaje imposible.
-- Los crea SOLO fn::charge_card (08_cards), también los denegados: un intento
-- con tarjeta bloqueada es información para el fraude. El titular ve los de
-- las tarjetas de sus cuentas.
DEFINE TABLE OVERWRITE card_payment SCHEMAFULL TYPE NORMAL
    PERMISSIONS FOR select WHERE card.account IN $auth.customer->owns->account;
DEFINE FIELD OVERWRITE card     ON card_payment TYPE record<card>;
DEFINE FIELD OVERWRITE amount   ON card_payment TYPE decimal;
DEFINE FIELD OVERWRITE merchant ON card_payment TYPE string DEFAULT 'comercio';
DEFINE FIELD OVERWRITE status   ON card_payment TYPE string DEFAULT 'approved'
    ASSERT $value IN ['approved','declined'];
DEFINE FIELD OVERWRITE reason   ON card_payment TYPE option<string>;
DEFINE FIELD OVERWRITE txn      ON card_payment TYPE option<record<txn>>;
DEFINE FIELD OVERWRITE at     ON card_payment TYPE datetime DEFAULT time::now();
-- punto = (longitud, latitud). En ese orden: es donde todo el mundo se equivoca.
DEFINE FIELD OVERWRITE loc    ON card_payment TYPE geometry<point>;
DEFINE INDEX OVERWRITE cp_by_card ON card_payment FIELDS card, at;

-- El titular ve solo las alertas de sus propias cuentas. Los eventos que las
-- crean se saltan los permisos, que es justo lo que se necesita: el detector
-- escribe siempre, el usuario lee solo lo suyo.
DEFINE TABLE OVERWRITE fraud_alert SCHEMALESS TYPE NORMAL
    PERMISSIONS FOR select WHERE account IN $auth.customer->owns->account;
DEFINE FIELD OVERWRITE kind  ON fraud_alert TYPE string;
DEFINE FIELD OVERWRITE score ON fraud_alert TYPE float;
DEFINE FIELD OVERWRITE at    ON fraud_alert TYPE datetime VALUE time::now() READONLY;
DEFINE INDEX OVERWRITE alert_by_at ON fraud_alert FIELDS at;
