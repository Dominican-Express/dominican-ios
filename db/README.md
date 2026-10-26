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
python3 db/demo/cards_test.py        # PIN con límite de intentos, tarjetas, notificaciones
python3 db/demo/cards_redteam.py
python3 db/demo/detect_test.py       # repetir el barrido no duplica alertas
python3 db/demo/detect_redteam.py
python3 db/demo/time_travel_test.py      # máquina del tiempo; servidor CON versionado
python3 db/demo/time_travel_redteam.py
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

Para enseñarla con **Surrealist** (la interfaz gráfica oficial), la base va en
disco y sobrevive entre sesiones (`~/.local/share/dominican-express`, unos
32 MB):

```sh
./db/demo/demo.sh studio        # terminal aparte; se para con Ctrl-C
./db/demo/demo.sh studio-load   # una vez: bases `bank` (5 clientes) y `volume` (300)
```

Conexión en Surrealist: HTTP `127.0.0.1:8099`, Root `root`/`root`, namespace
`dx`. En la vista Query, el modo de resultado **Graph** dibuja cada registro
devuelto como nodo y busca solo las aristas entre ellos: `SELECT * FROM account;`
en `bank` enseña el anillo ana → luis → marta → ana.

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

Los barridos se pueden repetir: cada alerta lleva un id que dice qué se ha visto
(`['mule_ring', cuenta, miembros]`, `['shared_device', aparato, titulares]`,
`['structuring', cuenta, día]`) y se escribe con `INSERT IGNORE`. Con `CREATE`,
cada pasada duplicaba las alertas (22 → 44 → 66 en el banco de 300 clientes);
`bench.py` no lo veía porque borra las alertas antes de medir.

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

### La verificación por PIN: tres intentos de diseño

Abrir la ventana exige escribir `app_user.verified_until`, y el usuario no tiene
permiso de escritura sobre su propia ficha (a propósito: si lo tuviera, se
pondría `verified_until` en el año 3000 él solo). Hizo falta probar tres piezas
hasta dar con la buena, y cada fallo enseña algo de SurrealDB:

1. **`DEFINE FUNCTION`: no funciona.** Una función se ejecuta con los permisos de
   quien la llama, así que su `UPDATE` no hacía nada. Y lo peor es que la
   función **devolvía `true` igualmente**: decía «verificado» sin haber
   verificado.
2. **`DEFINE EVENT`: funciona, pero no puede contar intentos.** El evento se
   ejecuta sin comprobar permisos y escribe con privilegio. Pero para rechazar
   un PIN tiene que lanzar un error, y el error deshace la transacción entera,
   **contador de fallos incluido**. Con ese diseño, un PIN de 4 cifras admitía
   los 10.000 intentos.
3. **`DEFINE API`: la buena.** `POST /verify-pin` rechaza **devolviendo** un 401,
   sin lanzar nada, así que el fallo queda guardado. Tras 3 fallos seguidos
   bloquea la verificación 15 minutos, y el bloqueo rechaza incluso el PIN
   correcto. El PIN viaja en la petición y no se escribe en ninguna tabla.

### Cómo se ha probado

`db/demo/access_test.py` actúa como ana y como luis: 18 comprobaciones entre
casos positivos, negativos y ataques (alargarse la ventana a mano, cambiarse de
titular, pedir la verificación de otro, leer hashes, ver cuentas o alertas
ajenas). Con `--expiry` espera 91 s y comprueba que el PAN vuelve a ocultarse.

Pero un test que no has visto fallar no vigila nada. `db/demo/access_redteam.py`
**rompe a propósito** cada protección sobre una base limpia y comprueba que el
test que la vigila cae: **9/9 roturas detectadas**.

Hacerlo destapó dos tests que habrían pasado con el fallo puesto: el usuario no
tenía permiso de lectura sobre la tabla de peticiones de PIN de la versión con
evento, así que veía vacío pasara lo que pasara. Desde entonces se comprueba el
**efecto real**, mirando como root: lo que un usuario no puede leer no demuestra
que no exista.

Las tres pruebas en rojo (`access_`, `payments_` y `cards_redteam.py`) usan el
mismo motor, `demo/redteam.py`: aplican el esquema REAL con un texto exacto
sustituido, en vez de redefiniciones escritas a mano. Las escritas a mano se
quedaban viejas: la del viaje imposible reescribía un evento que ya había
cambiado. Si el texto a romper desaparece del fichero, el caso cuenta como roto.

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

## Tarjetas y notificaciones

`schema/08_cards.surql`. Hasta este bloque, un pago con tarjeta creaba su
registro pero **no movía dinero**, y el campo `blocked` existía sin que nada lo
mirara. Ahora todo pago pasa por `fn::charge_card`, que deniega por tarjeta
bloqueada, por límite mensual o por falta de saldo. **El pago denegado también
se guarda con su motivo**, porque un intento con una tarjeta bloqueada es
justo lo que interesa al análisis de fraude.

- **Quien lleva la tarjeta** la bloquea (`/cards/block`) y cambia su límite
  (`/cards/limit`, hasta el tope del banco). Ser cotitular de la cuenta no basta.
  A una tarjeta ajena se responde lo mismo que a una inexistente (404), para no
  revelar cuál de las dos es.
- **Un cobro escribe también la tarjeta** (`last_used_at`). Así, un cobro y un
  bloqueo simultáneos chocan y se serializan: es el mismo mecanismo que evita
  los descubiertos, aplicado a la tarjeta. Esto es por diseño y no tiene prueba
  propia: los dos órdenes posibles (cobrar y luego bloquear, o al revés) son
  válidos, así que no hay un estado final que distinga el fallo.

**Las notificaciones son filas, no mensajes.** Cada apunte avisa a todos los
titulares de su cuenta: ingreso, nómina o gasto, más el aviso de pago
denegado. El cliente solo puede marcarlas como leídas: con permiso de escritura
sobre la fila, cada uno de los demás campos lo prohíbe por separado.

`LIVE SELECT` solo sirve para que lleguen al instante, y no es la fuente de
verdad. **Medido en la 3.2.4** (`demo/live_delivery_check.py`): con un único
suscriptor llegaron 30 de 30, pero con dos suscriptores a la vez se perdieron
entregas (23/30 y 24/30 como clientes, en dos mediciones; 28/30 como root), sin
ningún error y con la fila guardada. SurrealDB tiene fallos conocidos de este
tipo ([corregido uno en la 3.1](https://surrealdb.com/releases/3.1),
[otro relacionado](https://github.com/surrealdb/surrealdb/issues/7570)). Por eso la
app pide las no leídas al abrir y al reconectar: un aviso perdido por el camino
llega tarde, pero no se pierde.

`demo/cards_test.py`: **41 comprobaciones**. `demo/cards_redteam.py`: **12/12**.

## Volumen: lo que solo se ve con datos de verdad

`demo/gen_volume.py` genera un banco con vida normal (nóminas, contactos
frecuentes, amigos que se devuelven dinero, pagos con tarjeta en su ciudad,
viajes en tren, cuentas conjuntas, familias con una tablet común) y **planta
fraude conocido**, guardando qué se plantó. `demo/bench.py` mide cada detector
en tiempo y en acierto contra esa verdad. `demo/write_bench.py` mide la ruta de
pago. Reproducible: la misma semilla da el mismo banco.

**Hallazgo 1: el detector de anillos original no servía.** A 100 clientes
tardaba **54 s y marcaba 75 cuentas inocentes**, porque dos amigos que se
devuelven dinero ya forman un ciclo y cada transferencia repetida multiplica
los caminos. El nuevo busca lo que de verdad define un anillo: el mismo dinero
reenviado, en menos de 48 h y con una comisión de hasta el 15 %, por 3 o más
cuentas. **Sobre el mismo banco: 0,03 s y 0 falsos positivos.** El viejo se
conserva como `fn::detect_rings_naive` para poder repetir la comparación.

**Hallazgo 2: la escritura no escalaba**, y la causa es una trampa de SurrealDB
3.2. Comparar en un `WHERE` con el **campo de una variable**
(`WHERE txn = $tx.id`) hace que el planificador ignore el índice y recorra la
tabla entera; con una variable simple (`LET $txid = $tx.id; … WHERE txn =
$txid`) usa el índice. `EXPLAIN` lo muestra: `TableScan` frente a `IndexScan`.
Pasaba en el cuadre del asiento, en los eventos de velocidad y de viaje
imposible y en el detector de anillos. A 1.000 clientes:

| | Antes | Después |
|---|---|---|
| `fn::transfer` | 72 ms | 1,2 ms |
| Generar 60 días de vida normal (33.286 operaciones) | 522 s, 64/s | 21,6 s, 1.540/s |
| Pagos sueltos con todos los eventos | 26/s | 692/s |

De paso, el índice único de IBAN que faltaba cazó un fallo del propio
generador: dos cuentas con el mismo IBAN.

**Resultado a 3.000 clientes** (200.846 apuntes, 65.278 pagos con tarjeta,
29.623 transferencias, 148.899 notificaciones), con 100.614 operaciones de vida
normal a 1.342/s:

| Detector | Tiempo | Plantados encontrados | Falsos positivos |
|---|---|---|---|
| Viaje imposible | en línea | 30/30 | 0 |
| Ráfaga de cargos | en línea | 30/30 | 0 |
| Anillos de mulas | 1,31 s | 249/249 | 0 |
| Dispositivo compartido | 0,06 s | 30/30 | 0 |
| Estructuración | 0,33 s | 30/30 | 0 |

**Cómo leer el 100 %:** el fraude lo planté yo, siguiendo las mismas reglas que
buscan los detectores. Así que demuestra que **la implementación es correcta y
escala**, no que detectaría a un blanqueador real, que se adapta. Los falsos
positivos sí son informativos, porque la vida normal no está hecha para
esquivarlos. Y el dispositivo compartido descansa en un supuesto declarado: los
hogares que comparten aparato comparten también una cuenta.

## La máquina del tiempo: investigar una alerta como estaba

Cuando salta una alerta, el investigador necesita ver el banco **como estaba
en ese momento**: para entonces las mulas pueden haber vaciado las cuentas,
dado de baja el móvil o quitado un cotitular. `db/schema/09_time_travel.surql`
lo resuelve con **dos relojes**, elegidos a propósito:

- **Tiempo del banco** (`at` del libro de apuntes). El libro es inmutable y no
  caduca: `fn::balance_at(cuenta, fecha)` da el saldo de cualquier fecha sin
  depender de nada más. Es la historia larga, la que pide un regulador.
- **Tiempo del sistema** (versionado del motor, SurrealKV). Guarda cada estado
  anterior de cada registro durante la retención (30 días) y deja consultar con
  `SELECT ... VERSION d'...'`. Es para lo que sí se puede cambiar o borrar.
  `fn::investigate(alerta)` reconstruye cuentas, titulares, saldos y aparatos en
  el instante de la alerta, los pone al lado de cómo están ahora y lista lo que
  ha cambiado (`device_deleted`, `owner_removed`, `balance_drop`…).

Demo: `demo.sh stage`, `demo.sh attack` (las alertas saltan en directo),
`demo.sh coverup` (las mulas borran el rastro) y `fn::investigate` sobre una
alerta: el móvil borrado reaparece con sus cuatro usuarios, Luis vuelve a ser
cotitular de Ana y la cuenta vaciada de Marta tenía 3.220 €.
`fn::balance_at(account:marta, <hora de la alerta>)` da lo mismo: **los dos
relojes coinciden**, y el test lo comprueba cuenta por cuenta.

**Por qué esto pesa en la elección de SurrealDB.** Es el único de los cinco
motores comparados con consultas al pasado dentro del lenguaje. MongoDB lee
instantáneas con `atClusterTime`, pero solo unos 5 minutos atrás por defecto
(`minSnapshotHistoryWindowInSeconds = 300`); su recuperación a un instante de
Atlas restaura una copia, no responde una consulta. PostgreSQL lo dice en su
documentación: «does not currently support system time» (hace falta una
extensión o disparadores; `WITHOUT OVERLAPS` de la 18 es tiempo de aplicación).
Neo4j y ArangoDB no lo ofrecen: copia y restauración, o modelarlo a mano.

**Lo que cuesta y lo que falla, medido:**

- **Disco:** el mismo banco (5 + 300 clientes) ocupa 26 MB sin versionado y
  42 MB con él (+62 %), porque cada pago reescribe el saldo y se guarda cada
  versión. Tiempo de carga igual (55 s frente a 53 s, una pasada de cada: la
  diferencia es ruido). De ahí la retención de 30 días y no «para siempre».
- **Un fallo del motor que fabricaba pruebas falsas** (surrealdb#7601, arreglado
  solo en la rama principal): recorrer una tabla o una relación con `VERSION`
  devuelve también registros **borrados antes** de esa fecha. Medido: Jose se
  había desvinculado de un aparato y el recorrido lo seguía poniendo como
  usuario. Leer **por id** sí es correcto, así que cada recorrido da
  *candidatos* y cada candidato se *confirma* leyéndolo por su id en esa fecha
  (`fn::owners_at`, `fn::users_at`). El test tiene una trampa por cada sitio
  donde se confirma.
- **El fallo depende del camino de ejecución:** la misma llamada,
  `fn::owners_at(account:jose, $at)`, devuelve la prueba falsa ejecutada
  directamente y la correcta dentro de un `.map(...)`. Dentro de
  `fn::investigate` no se manifestaba, y la prueba en rojo lo destapó: romper la
  confirmación no hacía fallar el test. Ahora los ayudantes se prueban
  llamándolos directamente. La confirmación se queda aunque hoy no haga falta
  en todos los caminos: no se puede depender de un detalle interno que cambiará.
- **Madurez:** SurrealKV está oficialmente en beta, y la 3.3 quita el versionado
  del motor en memoria. `CREATE ... VERSION` se acepta y se ignora en 3.x.

Pruebas: `time_travel_test.py`, **20 comprobaciones** (requiere servidor con
versionado: lo arrancan así `demo.sh` y `domex`); `time_travel_redteam.py`,
**10/10**. Con el versionado activado siguen en orden las demás suites, incluida
la carrera de pagos, y el oyente en vivo recibe las 6 alertas del ataque.

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
| redefinir una tabla para «limpiarla» | `REMOVE FIELD` / `REMOVE TABLE` explícitos | `DEFINE TABLE OVERWRITE` **no borra los campos viejos**: uno obligatorio que ya sobra hace fallar cada inserción. Por eso 06_access lleva `REMOVE TABLE IF EXISTS step_up` |
| fiarse de que `LIVE SELECT` entrega todo | guardar la notificación y pedir las no leídas | Con dos suscriptores se perdieron entregas sin ningún error (ver «Tarjetas y notificaciones») |
| rechazar lanzando un error en un evento | rechazar devolviendo un código en un endpoint | El error deshace también lo que se quería guardar, como un contador de fallos |
| `WHERE campo = $var.campo` | `LET $x = $var.campo; … WHERE campo = $x` | Con el campo de una variable el planificador **no usa el índice** y recorre la tabla: 72 ms frente a 1,2 ms por transferencia |
| `LET $acc = $acc + 1` dentro de un `FOR` | recursión, o `map`/`filter` | El `LET` del bucle crea otra variable: el acumulador de fuera se queda en su valor inicial, sin error |
| recorrer el grafo con `VERSION` y fiarse | recorrido = candidatos; confirmar cada uno leyéndolo por id con `VERSION` | surrealdb#7601: devuelve registros borrados ANTES de la fecha. Una prueba falsa en una investigación. Y solo en algunos caminos de ejecución |
| `SELECT ... FROM (subconsulta) VERSION $t` | `LET $c = (...); SELECT ... FROM $c VERSION $t` | «VERSION clause cannot be used with a subquery source» |
| `VERSION` antes de que existiera la tabla | — | Da error («The table 'x' does not exist»), no una lista vacía |

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

- Generador de volumen: HECHO (ver «Volumen»). Queda medir a más de 3.000
  clientes y con un servidor en disco, no en memoria.
- Comparativa medida de la detección de anillos en SurrealQL frente a un CTE
  recursivo equivalente en PostgreSQL, incluyendo los casos donde SurrealDB
  **no** gana.
- Límite de intentos también en el inicio de sesión: hoy la contraseña no lo
  tiene, solo el PIN.
- El motor avisa de que el permiso del campo `customer.bizum_account` tiene
  «dependencias opacas» y obliga a evaluar todos los campos calculados de cada
  fila. Revisar la expresión.
- Confirmar si SurrealKV purga de verdad las versiones más viejas que la
  retención (documentado para RocksDB; para SurrealKV no consta).
