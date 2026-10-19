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

Permisos, actuando como clientes y no como root (solo biblioteca estándar):

```sh
python3 db/demo/access_test.py       # 18 comprobaciones; --expiry espera la caducidad
python3 db/demo/access_redteam.py    # rompe cada protección y exige que su test caiga
python3 db/demo/payments_test.py     # API de pagos; --race añade la concurrencia
python3 db/demo/payments_redteam.py  # rompe cada protección de la API, sobre el fichero real
```

Usuarios de demo: `ana@dominican.test` / `demo-ana` (PIN 1234),
`luis@dominican.test` / `demo-luis` (PIN 5678) y
`marta@dominican.test` / `demo-marta` (PIN 2468). Teléfonos de Bizum:
`+34600000001` (ana) a `+34600000005` (sara).

Para la demo en vivo, en una terminal aparte y antes de lanzar el ataque:

```sh
uv run --with websockets python3 db/demo/live_listener.py
```

Todo de una vez, con subcomandos: `./db/demo/demo.sh` (sin argumentos lista los pasos).

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

## Permisos: la autorización también es un grafo

`root` se salta **todos** los permisos, así que mientras se trabajaba como root
los permisos de campo sobre PAN y CVV estaban escritos pero no se podían
demostrar. `db/schema/06_access.surql` añade usuarios de aplicación
(`DEFINE ACCESS ... TYPE RECORD`, contraseñas y PIN con argon2) y desde ahí las
pruebas se hacen como cliente, no como administrador.

Los permisos se expresan como **travesía de grafo**: ves una cuenta si cuelga de
una arista `owns` tuya.

```surql
DEFINE TABLE account ... PERMISSIONS FOR select WHERE id IN $auth.customer->owns->account;
```

La autorización usa el mismo modelo que la detección de fraude, en la misma
base, sin tabla puente ni JOIN. Y la tarjeta tiene **tres** condiciones sobre la
misma fila:

1. la tarjeta se ve si su cuenta es tuya, como titular o cotitular;
2. el PAN y el CVV solo los ve quien la **lleva** (`holder`), no cualquier
   cotitular: en una cuenta conjunta cada tarjeta sigue siendo personal;
3. y además con una verificación por PIN vigente, que caduca sola a los 90 s.

Sin la condición 2, un cotitular verificado vería el PAN de la tarjeta del otro.
Ese fallo estaba en la primera versión y lo destapó pensar en la cotitularidad
antes de escribir la demo.

### La verificación por PIN, y por qué no es una función

Abrir la ventana exige escribir `app_user.verified_until`, y el usuario no tiene
permiso de escritura sobre su propia ficha (a propósito: si lo tuviera, se
pondría `verified_until` en el año 3000 él solo).

La primera versión usaba una `DEFINE FUNCTION`. **No funciona**: una función se
ejecuta con los permisos de quien la llama, así que su `UPDATE` no hacía nada.
Y lo peor es que la función **devolvía `true` igualmente**. Un fallo silencioso
que diría «verificado» sin haber verificado.

La solución idiomática es un `EVENT`, que se ejecuta sin comprobar permisos. El
usuario solo puede *crear* una petición; el evento compara el PIN con el hash y
únicamente entonces abre la ventana. La petición se borra siempre, para que el
PIN en claro no se quede en la base. El usuario puede **provocar** la escritura
privilegiada, pero no **falsificarla**.

### Cómo se ha probado

`db/demo/access_test.py` actúa como ana y como luis: 18 comprobaciones entre
casos positivos, negativos y ataques (alargarse la ventana a mano, cambiarse de
titular, pedir la verificación de otro, leer hashes, ver cuentas o alertas
ajenas). Con `--expiry` espera 91 s y comprueba que el PAN vuelve a ocultarse.

Pero un test que no has visto fallar no vigila nada. `db/demo/access_redteam.py`
**rompe a propósito** cada protección sobre una base limpia y comprueba que el
test que la vigila cae: **9/9 roturas detectadas**.

Hacerlo destapó dos tests que habrían pasado con el fallo puesto. El usuario no
tiene permiso de lectura sobre `step_up`, así que tanto «el PIN no queda
guardado» como «no puedes pedir la verificación de otro» devolvían vacío pasara
lo que pasara. Ahora se comprueba el **efecto real**, mirando como root: lo que
un usuario no puede leer no demuestra que no exista.

## La API, dentro de la base de datos

**No hay backend intermedio.** El documento original proponía Java delante de
SurrealDB; se descartó, porque SurrealDB 3 ya trae lo que haría ese backend:
usuarios de la app con su propio token, permisos por registro y por campo, y
endpoints HTTP definidos en SurrealQL (`DEFINE API`, estable desde la 3.0).
Toda la lógica de negocio vive en un solo sitio. Código: `schema/07_api.surql`.

**Dos caminos, a propósito:**

- **Las lecturas** son consultas normales, filtradas por los permisos de grafo.
- **Las escrituras privilegiadas** (mover dinero, añadir contactos) pasan por
  endpoints: `POST /api/<ns>/<db>/transfers`, `/bizum` y `/contacts`.

¿Por qué no todo por endpoints? El cuerpo de un `DEFINE API` se ejecuta **sin
comprobar permisos**. Si las lecturas pasaran por ahí, la protección del CVV o
de las cuentas ajenas dependería de que cada endpoint la repitiera bien.
Dejándolas en los permisos, la base las aplica siempre. Por esa misma razón,
cada endpoint comprueba por sí mismo quién llama y qué es suyo.

Y ¿por qué endpoints y no un evento, como el PIN? Un endpoint devuelve códigos
HTTP de verdad (201, 403, 404, 409, 422) y **puede guardar algo aunque rechace
la petición**: las órdenes rechazadas quedan registradas, y un intento de pagar
desde una cuenta ajena es justo lo que hay que poder auditar. Con un evento,
rechazar es lanzar un error, y el error deshace también el registro.

**Las órdenes de pago** (`payment_order`) son a la vez el registro de
auditoría y la **clave de idempotencia**. Su id lo elige la app, un UUID por
intento. Si se corta la red y la app repite la orden con el mismo id, recibe la
respuesta original en vez de pagar dos veces. Si dos copias llegan a la vez,
escriben el mismo registro y chocan: la idempotencia sale del mismo mecanismo
que evita los descubiertos.

**El reintento es obligatorio** y es del cliente. Un conflicto de escritura
deshace la transacción entera; repetirla con el mismo id es seguro. Medido en
una carrera de 10 órdenes por todo el saldo: **sin reintento, 5 de las 10
acaban en conflicto**. Con reintento, siempre una se cumple y las otras nueve
se rechazan por falta de saldo, sin ningún conflicto sin resolver. Ojo:
SurrealDB 3.2 devuelve ese conflicto como **HTTP 400**, que parece un error del
cliente; el reintento lo reconoce por el texto (`api()` en `demo/session.py`).

**Los importes viajan como texto** (`"12.50"`). Un número JSON es coma flotante
y el dinero no lo es, así que el endpoint rechaza un número con 400.

### Cómo se ha probado

`payments_test.py` actúa como clientes. Hace **35 comprobaciones** (32 sin `--race`), mirando siempre
el efecto real como root (saldos, apuntes, órdenes) y no solo la respuesta: un
endpoint que dijera «rechazado» y moviera el dinero igualmente pasaría si solo
se mirara lo que contesta. Con `--race`, además, verifica 10 rondas de 10
órdenes simultáneas y 10 rondas de 10 copias de la **misma** orden: en las
segundas se paga una sola vez y las diez copias reciben 201.

`payments_redteam.py` aplica el esquema real con una línea rota cada vez, por
sustitución de texto exacto sobre el fichero, y exige que caiga la prueba que
la vigila: **11/11**. Destapó un fallo de la propia prueba: con la comprobación
de saldo quitada, el endpoint respondía con un error en texto en vez de un
objeto, y la prueba se caía a medias sin decir qué había fallado. Un test que
se rompe no es un test que falla.

## Limitaciones que conviene declarar

- **`LIVE SELECT` solo funciona en despliegue de un nodo.** Esto contradice el
  argumento de «escalabilidad distribuida»: hoy no se pueden tener las dos cosas
  a la vez. Es más sólido decirlo que esconderlo.
- Los eventos síncronos añaden coste a cada escritura. Es un compromiso asumido,
  no un descuido.
- La alerta de dispositivo compartido no la ve ningún cliente, solo el banco:
  afecta a varios titulares a la vez y enseñársela a uno revelaría a los demás.
- Un JSON **malformado** en un endpoint sale como 500, no como 400: el
  decodificador lanza un error y SurrealQL no tiene try/catch. Las apps siempre
  mandan JSON serializado, así que no afecta al uso normal.
- Los clientes pueden lanzar consultas libres de **lectura**. Los permisos
  limitan lo que ven, pero no lo que cuesta: una consulta enorme gasta CPU. En
  producción se cerrarían con `--deny-arbitrary-query record`, pasando a
  endpoints también las lecturas y repitiendo en ellos cada comprobación. Para
  este proyecto pesa más que la base aplique los permisos siempre.
- Añadir un contacto por teléfono revela si ese número es cliente del banco. Es
  lo mismo que hace Bizum.

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
| escritura privilegiada en `DEFINE FUNCTION` | `DEFINE EVENT` | La función corre con los permisos del que llama: el `UPDATE` no hace nada **y la función devuelve éxito** |
| comprobar un ataque leyendo como el usuario | comprobar el efecto como root | Sin permiso de lectura, el usuario ve `[]` exista o no la fila: el test pasa con el fallo puesto |
| `api::req::body("json")` | sin lector, y `encoding::json::decode(<string>$request.body)` | Convierte en tipos lo que lo parece: `"account:ana"` llega como registro, una fecha ISO como fecha, y **`"Cena: viernes"` como el registro `Cena:viernes`, sin el espacio** |
| `api::req::max_body("16kb")` | `bytes::len($raw) > 16384` | La documentación lo lista, pero la 3.2.4 no lo tiene: «no such builtin function found» |
| devolver un objeto como `body` | `MIDDLEWARE api::res::body("json")` | Sin él: «HTTP API response body must be None, bytes, or string» |
| reintentar solo los 5xx | reconocer el conflicto por su texto | El conflicto de escritura llega como **400** |
| `type::is::string(…)` | `type::is_string(…)` | Otro anidamiento `::` aplanado en 3.x |

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

- Generador de volumen (decenas de miles de movimientos) para medir los
  detectores con datos de verdad y no con cinco cuentas.
- Comparativa medida de la detección de anillos en SurrealQL frente a un CTE
  recursivo equivalente en PostgreSQL, incluyendo los casos donde SurrealDB
  **no** gana.
- Bloqueo de tarjeta que se aplique (hoy el campo `blocked` existe y nada lo
  comprueba), límites de gasto configurables, límite de intentos del PIN y
  notificaciones.
