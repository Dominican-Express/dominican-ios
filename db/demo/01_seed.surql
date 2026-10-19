-- Dominican Express — datos de partida (sintéticos)
-- IBAN no válidos a propósito. Ningún dato real.

DELETE fraud_alert; DELETE card_payment; DELETE transfer; DELETE uses;
DELETE owns; DELETE favorite; DELETE entry; DELETE txn; DELETE app_user; DELETE payment_order;
DELETE card; DELETE device; DELETE account; DELETE customer;

-- Contrapartida externa: sin ella, una nómina no podría cuadrar a cero.
CREATE account:ext SET iban = 'ES0000000000000000000000', kind = 'external';

CREATE customer:ana   SET name = 'Ana García',    nif = '00000001A', phone = '+34600000001';
CREATE customer:luis  SET name = 'Luis Romero',   nif = '00000002B', phone = '+34600000002';
CREATE customer:marta SET name = 'Marta Sanz',    nif = '00000003C', phone = '+34600000003';
CREATE customer:jose  SET name = 'José Iglesias', nif = '00000004D', phone = '+34600000004';
CREATE customer:sara  SET name = 'Sara Nuño',     nif = '00000005E', phone = '+34600000005';

CREATE account:ana   SET iban = 'ES1111111111111111111111';
CREATE account:luis  SET iban = 'ES2222222222222222222222';
CREATE account:marta SET iban = 'ES3333333333333333333333';
CREATE account:jose  SET iban = 'ES4444444444444444444444';
CREATE account:sara  SET iban = 'ES5555555555555555555555';

-- Cuenta de Bizum de cada cliente. La de ana es la conjunta con luis.
UPDATE customer:ana   SET bizum_account = account:ana;
UPDATE customer:luis  SET bizum_account = account:luis;
UPDATE customer:marta SET bizum_account = account:marta;
UPDATE customer:jose  SET bizum_account = account:jose;
UPDATE customer:sara  SET bizum_account = account:sara;

-- Cotitularidad: el rol vive en la ARISTA.
RELATE customer:ana->owns->account:ana   SET role = 'titular';
RELATE customer:luis->owns->account:ana  SET role = 'cotitular';
RELATE customer:luis->owns->account:luis SET role = 'titular';
RELATE customer:marta->owns->account:marta SET role = 'titular';
RELATE customer:jose->owns->account:jose   SET role = 'titular';
RELATE customer:sara->owns->account:sara   SET role = 'titular';

-- Nóminas. Pasan por fn::credit, así que cada asiento cuadra.
RETURN fn::credit(account:ana,   8425.60dec, 'payroll');
RETURN fn::credit(account:luis,  3200.00dec, 'payroll');
RETURN fn::credit(account:marta, 6000.00dec, 'payroll');
-- jose y sara van holgados a propósito: son los que ejecutan los escenarios
-- de estructuración y de cargo grande, y deben poder pagarlos sin descubierto.
RETURN fn::credit(account:jose, 30000.00dec, 'payroll');
RETURN fn::credit(account:sara, 12000.00dec, 'payroll');

-- card:ana cuelga de la cuenta CONJUNTA de ana y luis, pero la lleva ana.
CREATE card:ana  SET account = account:ana,  holder = customer:ana,
                     pan_last4 = '4242', pan = '4111111111114242', cvv = '123';
CREATE card:luis SET account = account:luis, holder = customer:luis,
                     pan_last4 = '1010', pan = '4111111111111010', cvv = '456';

-- Usuarios de la app. Contraseñas de demo, hasheadas con argon2: la base
-- nunca guarda la contraseña en claro.
CREATE app_user:ana  SET email = 'ana@dominican.test',  customer = customer:ana,
                         pass = crypto::argon2::generate('demo-ana'),
                         pin  = crypto::argon2::generate('1234');
CREATE app_user:luis SET email = 'luis@dominican.test', customer = customer:luis,
                         pass = crypto::argon2::generate('demo-luis'),
                         pin  = crypto::argon2::generate('5678');
-- marta no comparte nada con ana ni con luis: es la tercera persona de las
-- pruebas de permisos y de pagos.
CREATE app_user:marta SET email = 'marta@dominican.test', customer = customer:marta,
                          pass = crypto::argon2::generate('demo-marta'),
                          pin  = crypto::argon2::generate('2468');

CREATE device:movil_ana  SET fingerprint = 'iPhone15,2/es_ES/a1b2c3';
CREATE device:movil_sara SET fingerprint = 'SM-A515F/es_ES/d4e5f6';
RELATE customer:ana->uses->device:movil_ana;
RELATE customer:sara->uses->device:movil_sara;
