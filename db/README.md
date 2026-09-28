# Dominican Express — base de datos

Esquema, motor de fraude y demo sobre **SurrealDB**. Todo lo que hay aquí se ha
ejecutado contra **SurrealDB 3.2.4** (macOS aarch64) el 2026-09-28. Las cifras
de este documento son medidas, no estimaciones.

## Arranque

```sh
# servidor en memoria, solo loopback
surreal start --username root --password root --bind 127.0.0.1:8099 --no-banner memory

# esquema completo
./db/demo/apply.sh

# datos y escenario
./db/demo/surql.sh db/demo/01_seed.surql
./db/demo/surql.sh db/demo/02_attack.surql
./db/demo/surql.sh db/demo/03_detect.surql
```

Para la demo en vivo, en una terminal aparte y antes de lanzar el ataque:

```sh
pip install websockets
python3 db/demo/live_listener.py
```

## El principio que gobierna el diseño

`account.balance` **no es la fuente de verdad**. La verdad es `entry`, un libro
de apuntes append-only por partida doble: cada movimiento son dos apuntes que
suman cero, escritos en una sola transacción. Un apunte no se corrige nunca; se
compensa con otro. Por eso `entry` es `READONLY` campo a campo.

El invariante vive en `fn::transfer` y en ningún otro sitio. Ningún cliente
escribe apuntes a mano.

## Concurrencia: el hallazgo principal

SurrealDB usa **aislamiento por instantánea (snapshot isolation)** con detección
de conflictos **write-write sobre el mismo registro** en el momento del commit.

La consecuencia es contraintuitiva: **un libro de apuntes append-only, por sí
solo, no impide un descubierto.** Dos transferencias simultáneas desde la misma
cuenta insertan apuntes *distintos*, así que no colisionan. Las dos leen saldo
100, las dos pasan la comprobación, las dos confirman.

Lo que las serializa es el `UPDATE account SET balance`, porque escribe el mismo
registro en ambas transacciones y provoca el conflicto. Es decir: el saldo
materializado **no es una caché**, es el mecanismo de control de concurrencia.

En SurrealDB 3.3 existe `SELECT ... FOR UPDATE`, que registra los registros
leídos para la detección de conflictos y permitiría expresar esto de forma
explícita. **En la 3.2 estable no existe** (da error de parseo), y la 3.3 estaba
en beta a fecha de este trabajo.

Medido con `db/demo/concurrency_test.sh`, 10 transferencias simultáneas por el
saldo completo, 20 rondas:

| Implementación | Rondas con descubierto |
|---|---|
| `fn::transfer` (escribe `balance`) | **0 / 20** |
| `fn::transfer_unsafe` (ledger puro) | **13 / 20** |

La versión insegura existe a propósito: un invariante que no has visto fallar no
vigila nada. Sin ese caso en rojo, la prueba de reconciliación pasaría igual con
un diseño malo.

## Motor de fraude: dos velocidades

Es la arquitectura de la industria, y aquí además la imponen las limitaciones
reales del motor.

**En línea** (`db/schema/04_events.surql`). `DEFINE EVENT` corre **dentro de la
transacción** que lo dispara. Si el cuerpo del evento lanza, el pago entero se
deshace. Por eso aquí solo van detectores de coste acotado y apoyados en índice:
velocidad, viaje imposible, saldo bajo. Existe `ASYNC`, que los saca de la
transacción a costa de un retardo (el intervalo por defecto es de 5 s).

**Por barrido** (`db/schema/05_detectors.surql`). Travesías de grafo y
agregaciones por ventana, lanzadas fuera de la ruta crítica del pago: anillos de
mulas, dispositivo compartido, estructuración.

Ambos escriben en `fraud_alert`, que es la única tabla que escucha el
`LIVE SELECT` del panel.

### Resultado del escenario

Seis alertas, cero falsos positivos. Cada detector lleva su control negativo:
una cadena lineal legítima, un dispositivo de un solo titular, un cargo grande
declarado, uno dentro del rango pero fuera de la ventana, y un Madrid→Barcelona
en cuatro horas. Ninguno dispara.

## Por qué `transfer` duplica lo que ya está en `entry`

A propósito. El ledger es la verdad contable; la arista `transfer` es la
proyección de grafo sobre la que corren las travesías. Se escriben en la misma
transacción, así que no pueden divergir. Dos modelos del mismo hecho conviviendo
en una sola base sin ETL: ese es el argumento multi-modelo, y es la respuesta a
la pregunta «¿por qué lo guardáis dos veces?».

## Limitaciones que conviene declarar

- **`LIVE SELECT` solo funciona en despliegue de un nodo.** Esto contradice el
  argumento de «escalabilidad distribuida»: hoy no se pueden tener las dos cosas
  a la vez. Es más sólido decirlo que esconderlo.
- Los eventos síncronos añaden coste a cada escritura. Es un compromiso asumido,
  no un descuido.
- Los permisos a nivel de campo sobre PAN y CVV dependen de que exista
  autenticación real (`DEFINE ACCESS`). Mientras se trabaje como `root`, no se
  aplican: root los ve todos.

## Trampas de SurrealQL encontradas al ejecutar

Ninguna de estas aparece leyendo el código; todas salieron corriéndolo.

| Lo que no funciona | Lo correcto | Por qué |
|---|---|---|
| `$valor = /regex/` | `string::matches($v, "^ES[0-9]{22}$")` | Los operadores difusos se eliminaron en 3.0 |
| `type::thing('account', $n)` | `type::record(...)` | Renombrada en 3.x |
| `duration::from::hours($i)` | `duration::from_hours($i)` | El anidamiento `::` se aplanó en 3.x |
| `$i * 1h` · `$i + "h"` | `duration::from_hours($i)` | No hay multiplicación int×duration ni suma int+string |
| `SELECT VALUE math::sum(amount) FROM entry` | `math::sum(SELECT VALUE amount FROM entry ...)` | La primera forma suma **por fila**: `Expected array<number> but found -900dec` |
| `RETURN f(...)` dentro de un `FOR` | `LET $_ = f(...)` | `RETURN` **sale del bucle en la primera vuelta**. Silencioso: se ejecutaba 1 de 8 |
| `WHERE alias != ...` | repetir la expresión | El alias de un `SELECT` no existe en su propio `WHERE` |
| `SELECT ... FOR UPDATE` | — | No existe hasta 3.3 |
| `surreal sql < fichero.surql` | `POST /sql` con el fichero entero | La CLI procesa línea a línea y rompe toda sentencia multilínea |
| enviar cabeceras y ya | `DEFINE NAMESPACE` / `DEFINE DATABASE` | En 3.x no se crean solas: «The database 'x' does not exist» |

Además, dos sutilezas de datos: `math::sum` de un conjunto vacío devuelve el
entero `0`, no `0dec`, así que las comparaciones usan `!=` (tolerante al tipo) y
nunca `!==`; y un punto geográfico se escribe `(longitud, latitud)`, en ese
orden.

## Falsos positivos encontrados ejecutando la demo

- **Velocidad en `account:ext`.** La contrapartida externa recibe todas las
  nóminas seguidas y disparaba ráfaga de cargos. Arreglado con
  `$after.account.kind = 'customer'`.
- **Alertas repetidas.** Sin deduplicación, el detector de velocidad emite una
  alerta por *cada* apunte una vez superado el umbral (2 alertas con 6 cargos).
- **Estructuración contando la cuenta externa**, por el mismo motivo.

## Pendiente

- `DEFINE ACCESS` y usuarios reales, para que los permisos de campo sobre
  PAN/CVV se puedan demostrar con dos sesiones distintas.
- Generador de volumen (decenas de miles de movimientos) para medir los
  detectores con datos de verdad y no con cinco cuentas.
- Comparativa medida de la detección de anillos en SurrealQL frente a un CTE
  recursivo equivalente en PostgreSQL, incluyendo los casos donde SurrealDB
  **no** gana.
- Reintento en el cliente ante conflicto de escritura: el conflicto está pensado
  para reintentarse, no es un error terminal.
