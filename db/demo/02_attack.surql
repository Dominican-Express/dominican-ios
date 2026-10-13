-- Dominican Express — el ataque
--
-- Cada bloque incluye su CONTROL NEGATIVO: actividad legítima que se le
-- parece y que NO debe disparar. Un detector que solo se ha visto acertar
-- no se ha probado.

-- ---------------------------------------------------------------------------
-- 1. ANILLO DE MULAS: ana -> luis -> marta -> ana
RETURN fn::transfer(account:ana,   account:luis,  900dec);
RETURN fn::transfer(account:luis,  account:marta, 880dec);
RETURN fn::transfer(account:marta, account:ana,   860dec);

-- CONTROL: cadena lineal legítima, sin vuelta al origen. jose -> sara
RETURN fn::transfer(account:jose, account:sara, 120dec);

-- ---------------------------------------------------------------------------
-- 2. DISPOSITIVO COMPARTIDO: cuatro identidades en el mismo aparato
CREATE device:mula SET fingerprint = 'SM-A105F/es_ES/deadbeef';
RELATE customer:ana->uses->device:mula;
RELATE customer:luis->uses->device:mula;
RELATE customer:marta->uses->device:mula;
RELATE customer:jose->uses->device:mula;
-- CONTROL: device:movil_sara sigue con una sola titular.

-- ---------------------------------------------------------------------------
-- 3. ESTRUCTURACIÓN: 8 envíos de 2.900 (umbral de reporte: 3.000)
-- duration::from_hours, NO duration::from::hours (el anidamiento :: se aplanó
-- en 3.x). Y ni `$i * 1h` ni `$i + "h"` son operaciones válidas.
-- Todo pasa por fn::debit_at, que mantiene la partida doble. Sembrar apuntes
-- a mano descuadraría la reconciliación y esa prueba dejaría de significar nada.
-- OJO: `RETURN` dentro de un FOR sale del bucle en la PRIMERA vuelta. Con
-- `RETURN fn::debit_at(...)` aquí, solo se ejecutaba 1 de los 8 cargos y la
-- estructuración no se disparaba nunca. Se usa LET para consumir el valor.
FOR $i IN [1,2,3,4,5,6,7,8] {
    LET $_ = fn::debit_at(account:jose, 2900dec, time::now() - duration::from_hours($i));
};
-- CONTROL A: un único cargo grande y declarado, por encima del rango.
RETURN fn::debit_at(account:sara, 9000dec, time::now() - 2h);
-- CONTROL B: en el rango, pero fuera de la ventana de 24 h.
RETURN fn::debit_at(account:marta, 2800dec, time::now() - duration::from_hours(40));

-- ---------------------------------------------------------------------------
-- 4. VIAJE IMPOSIBLE: Madrid -> Nueva York en 10 minutos
-- El punto se escribe (longitud, latitud). En ese orden.
CREATE card_payment SET card = card:ana, amount = 30dec,
    loc = (-3.7038, 40.4168),  at = time::now() - 20m;
CREATE card_payment SET card = card:ana, amount = 1850dec,
    loc = (-74.0060, 40.7128), at = time::now() - 10m;

-- CONTROL: Madrid -> Barcelona en 4 horas. Plausible en AVE, no debe avisar.
CREATE card_payment SET card = card:luis, amount = 20dec,
    loc = (-3.7038, 40.4168), at = time::now() - duration::from_hours(5);
CREATE card_payment SET card = card:luis, amount = 45dec,
    loc = (2.1734, 41.3851),  at = time::now() - duration::from_hours(1);
