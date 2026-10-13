-- Dominican Express — funciones de dominio
--
-- El invariante de partida doble vive AQUÍ y solo aquí. Ningún cliente
-- escribe apuntes a mano.

DEFINE FUNCTION OVERWRITE fn::balance($acc: record<account>) {
    RETURN math::sum(SELECT VALUE amount FROM entry WHERE account = $acc);
};

-- Transferencia SEGURA.
--
-- Nota sobre `FOR UPDATE`: en SurrealDB 3.3 existe `SELECT ... FOR UPDATE`,
-- que registra los registros leídos para la detección de conflictos. En la
-- 3.2 estable NO existe (error de parseo). Por eso el `UPDATE ... SET balance`
-- de abajo no es decorativo: al escribir el registro de la cuenta, crea el
-- conflicto write-write que impide el descubierto por carrera.
-- Medido: 0/30 descubiertos con esta función, 7/30 sin ella. Ver db/README.md.
DEFINE FUNCTION OVERWRITE fn::transfer($from: record<account>, $to: record<account>, $amount: decimal) {
    IF $amount <= 0dec { THROW "El importe debe ser positivo" };
    LET $f = (SELECT * FROM ONLY $from);
    LET $t = (SELECT * FROM ONLY $to);
    IF $f = NONE OR $t = NONE { THROW "Cuenta inexistente" };
    IF $f.currency != $t.currency { THROW "Divisas distintas" };
    IF fn::balance($from) < $amount { THROW "Saldo insuficiente" };

    LET $tx = (CREATE ONLY txn SET kind = 'transfer');
    CREATE entry SET account = $from, txn = $tx.id, amount = -$amount;
    CREATE entry SET account = $to,   txn = $tx.id, amount =  $amount;

    -- el asiento debe sumar cero o la transacción entera se deshace
    LET $sum = math::sum(SELECT VALUE amount FROM entry WHERE txn = $tx.id);
    IF $sum != 0dec { THROW "Asiento descuadrado" };

    UPDATE $from SET balance -= $amount;
    UPDATE $to   SET balance += $amount;
    RELATE $from->transfer->$to SET amount = $amount, txn = $tx.id;
    RETURN $tx.id;
};

-- Ingreso desde fuera del banco (nómina, recarga). La contrapartida es
-- `account:ext`, sin la cual el asiento no podría cuadrar a cero.
DEFINE FUNCTION OVERWRITE fn::credit($to: record<account>, $amount: decimal, $kind: string) {
    IF $amount <= 0dec { THROW "El importe debe ser positivo" };
    LET $tx = (CREATE ONLY txn SET kind = $kind);
    CREATE entry SET account = account:ext, txn = $tx.id, amount = -$amount;
    CREATE entry SET account = $to,         txn = $tx.id, amount =  $amount;
    UPDATE account:ext SET balance -= $amount;
    UPDATE $to         SET balance += $amount;
    RETURN $tx.id;
};

-- Cargo con fecha pasada, para el generador de histórico. Mantiene la partida
-- doble y el saldo materializado: sin esto, sembrar datos "a mano" descuadra
-- la reconciliación y la prueba deja de significar nada.
DEFINE FUNCTION OVERWRITE fn::debit_at($from: record<account>, $amount: decimal, $at: datetime) {
    IF fn::balance($from) < $amount { THROW "Saldo insuficiente" };
    LET $tx = (CREATE ONLY txn SET kind = 'card');
    CREATE entry SET account = $from,        txn = $tx.id, amount = -$amount, at = $at;
    CREATE entry SET account = account:ext,  txn = $tx.id, amount =  $amount, at = $at;
    UPDATE $from        SET balance -= $amount;
    UPDATE account:ext  SET balance += $amount;
    RETURN $tx.id;
};

-- ---------------------------------------------------------------------------
-- CONTROL EXPERIMENTAL. No usar en la app.
-- Ledger puro sin saldo materializado: sin punto de conflicto, permite
-- descubierto bajo concurrencia. Existe para que la prueba de concurrencia
-- tenga un caso que falle: un invariante que no has visto fallar no vigila nada.
DEFINE FUNCTION OVERWRITE fn::transfer_unsafe($from: record<account>, $to: record<account>, $amount: decimal) {
    IF fn::balance($from) < $amount { THROW "Saldo insuficiente" };
    LET $tx = (CREATE ONLY txn SET kind = 'transfer');
    CREATE entry SET account = $from, txn = $tx.id, amount = -$amount;
    CREATE entry SET account = $to,   txn = $tx.id, amount =  $amount;
    RETURN $tx.id;
};
