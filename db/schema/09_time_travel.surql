-- Dominican Express — la máquina del tiempo
--
-- DOS RELOJES, a propósito:
--
--  * Tiempo del BANCO: el campo `at` del libro de apuntes. El libro es
--    inmutable (READONLY) y no caduca, así que «¿cuánto tenía esta cuenta el
--    día X?» se responde desde él, sin depender del versionado. Sirve años.
--
--  * Tiempo del SISTEMA: el versionado del motor (SurrealKV). Guarda cada
--    estado anterior de cada registro durante la retención (30 días aquí) y
--    deja consultar la base tal como estaba con `SELECT ... VERSION d'...'`.
--    Es para lo que SÍ se puede cambiar o borrar: aparatos, titularidades,
--    saldos materializados. Lo usa la investigación de una alerta.
--
-- El servidor tiene que arrancar con versionado (lo hacen `demo.sh` y `domex`):
--     SURREAL_DATASTORE_VERSIONED=true SURREAL_DATASTORE_RETENTION=30d
-- Sin él, `fn::investigate` falla con «Versioned queries not enabled».
--
-- Medido en 3.2.4: VERSION acepta la fecha en un parámetro, funciona dentro de
-- una función y llega a los recorridos del grafo, PERO esos recorridos pueden
-- traer registros ya borrados (ver fn::owners_at más abajo). Una fecha anterior
-- a que existiera la tabla da error, no una lista vacía. El versionado está
-- en beta (SurrealKV) y la 3.3 lo quita del motor en memoria.

-- ---------------------------------------------------------------------------
-- Saldo en una fecha, desde el libro (tiempo del banco).
DEFINE FUNCTION OVERWRITE fn::balance_at($acc: record<account>, $when: datetime) {
    RETURN math::sum(SELECT VALUE amount FROM entry WHERE account = $acc AND at <= $when);
} PERMISSIONS NONE;

-- ---------------------------------------------------------------------------
-- Lectura en el pasado que NO se fía de los recorridos.
--
-- Fallo abierto en 3.x (surrealdb#7601, arreglado solo en main): recorrer una
-- tabla o una relación con VERSION devuelve también registros BORRADOS ANTES
-- de esa fecha. Medido aquí: jose se había desvinculado de un aparato y el
-- recorrido `<-uses<-customer ... VERSION` lo seguía poniendo como usuario.
-- En una investigación eso es una prueba falsa.
-- Leer por id con VERSION sí es correcto. Así que: el recorrido da
-- CANDIDATOS (puede sobrar, nunca faltar) y cada uno se CONFIRMA leyéndolo
-- por su id en esa fecha. VERSION no admite una subconsulta como origen
-- («Place the VERSION clause inside the subquery»): los candidatos van en LET.

-- Quién estaba al otro lado de las relaciones `owns` de una cuenta en $at.
DEFINE FUNCTION OVERWRITE fn::owners_at($acc: record<account>, $at: datetime) {
    LET $cand = (SELECT VALUE <-owns FROM ONLY $acc VERSION $at) ?? [];
    RETURN SELECT VALUE in FROM $cand VERSION $at;
} PERMISSIONS NONE;

-- Quién usaba un aparato en $at.
DEFINE FUNCTION OVERWRITE fn::users_at($dev: record<device>, $at: datetime) {
    LET $cand = (SELECT VALUE <-uses FROM ONLY $dev VERSION $at) ?? [];
    RETURN SELECT VALUE in FROM $cand VERSION $at;
} PERMISSIONS NONE;

-- ---------------------------------------------------------------------------
-- Investigación de una alerta (tiempo del sistema).
--
-- Reconstruye lo que rodeaba a la alerta EN EL INSTANTE EN QUE SALTÓ: cuentas
-- implicadas, sus titulares y saldos, y los aparatos de esos titulares con
-- quién los usaba. Al lado pone cómo está todo AHORA y lista lo que ha
-- cambiado desde entonces: si las mulas borran el rastro después del aviso,
-- aquí reaparece.
--
-- Solo para el equipo antifraude (PERMISSIONS NONE): un cliente no la puede
-- llamar.
DEFINE FUNCTION OVERWRITE fn::investigate($alert: record<fraud_alert>) {
    LET $a = (SELECT * FROM ONLY $alert);
    IF $a = NONE { THROW 'alert_not_found' };
    LET $at = $a.at;

    -- Cuentas implicadas: la de la alerta, los miembros del anillo (van en el
    -- id de la alerta) y las de quienes usaban el aparato señalado.
    LET $ring = IF $a.kind = 'mule_ring' { record::id($a.id)[2] } ELSE { [] };
    LET $holders = IF $a.device != NONE { fn::users_at($a.device, $at) } ELSE { [] };
    LET $own_cand = array::flatten(SELECT VALUE ->owns FROM $holders VERSION $at);
    LET $holder_accs = (SELECT VALUE out FROM $own_cand VERSION $at);
    LET $accs = array::distinct(array::flatten([
        IF $a.account != NONE { [$a.account] } ELSE { [] }, $ring, $holder_accs]));

    LET $acc_then = (SELECT id, balance FROM $accs VERSION $at)
        .map(|$t| { id: $t.id, balance: $t.balance, owners: fn::owners_at($t.id, $at) });
    LET $acc_now  = (SELECT id, balance, <-owns<-customer AS owners FROM $accs);

    LET $people = array::distinct(array::flatten([$holders, $acc_then.owners]));
    LET $use_cand = array::flatten(SELECT VALUE ->uses FROM $people VERSION $at);
    LET $devs = array::distinct(SELECT VALUE out FROM $use_cand VERSION $at);
    LET $dev_then = (SELECT id, fingerprint FROM $devs VERSION $at)
        .map(|$t| { id: $t.id, fingerprint: $t.fingerprint, users: fn::users_at($t.id, $at) });
    LET $dev_now  = (SELECT id, <-uses<-customer AS users FROM $devs);

    LET $accounts = $acc_then.map(|$t| {
        LET $n = $acc_now.find(|$x| $x.id = $t.id);
        RETURN {
            id: $t.id,
            balance_then: $t.balance, balance_now: $n.balance,
            owners_then: $t.owners, owners_now: $n.owners ?? []
        };
    });
    LET $devices = $dev_then.map(|$t| {
        LET $n = $dev_now.find(|$x| $x.id = $t.id);
        RETURN {
            id: $t.id, fingerprint: $t.fingerprint,
            users_then: $t.users, users_now: $n.users ?? [], deleted: $n = NONE
        };
    });

    -- Lo que ha cambiado desde la alerta, en una lista que se lee de un vistazo.
    LET $changes = array::flatten([
        $devices.filter(|$d| $d.deleted)
                .map(|$d| { change: 'device_deleted', device: $d.id, used_by: $d.users_then }),
        $devices.filter(|$d| !$d.deleted)
                .map(|$d| array::complement($d.users_then, $d.users_now)
                    .map(|$c| { change: 'device_unlinked', device: $d.id, customer: $c })),
        $accounts.map(|$x| array::complement($x.owners_then, $x.owners_now)
                    .map(|$c| { change: 'owner_removed', account: $x.id, customer: $c })),
        $accounts.filter(|$x| $x.balance_now < $x.balance_then)
                 .map(|$x| { change: 'balance_drop', account: $x.id,
                             from: $x.balance_then, to: $x.balance_now })
    ]);

    RETURN {
        alert: $a.id, kind: $a.kind, at: $at,
        accounts: $accounts, devices: $devices, changes: array::flatten($changes)
    };
} PERMISSIONS NONE;
