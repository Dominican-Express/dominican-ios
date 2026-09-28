# Dominican Express — diseño de la base de datos

Fecha: 2026-09-28. Asignatura: Bases de Datos Avanzadas (UFV).
Detalle técnico y resultados medidos: `db/README.md`.

## Alcance acordado

El entregable evaluable es **la base de datos**: esquema, generador de datos,
consultas de fraude y demo. La app iOS se queda con sus datos simulados; se le
conectará una pantalla de alertas solo si sobra tiempo.

Se descarta el backend en Java. Se habla SurrealQL directo, lo que concentra el
trabajo donde está la nota y evita el SDK menos maduro del ecosistema.

Se recorta el alcance del documento funcional original. Fuera: objetivos de
ahorro, conversión de divisa, simulador de préstamo. Para esta asignatura
importa más la profundidad que la cantidad de funciones.

## Decisiones

**El saldo se deriva de un libro de apuntes append-only por partida doble.**
`account.balance` es un saldo materializado, nunca la fuente de verdad. Es la
decisión con más consecuencias y la que hace que ACID sea demostrable en vez de
un argumento de folleto.

**El motor de fraude va a dos velocidades.** En línea, dentro de la transacción,
los detectores de coste acotado. Por barrido, fuera de la ruta crítica del pago,
las travesías de grafo. No es solo elegante: `DEFINE EVENT` es síncrono, y meter
una consulta de grafo profunda en cada pago es exactamente lo que ningún banco
hace.

**La arista `transfer` duplica a propósito lo que ya está en los apuntes.** El
ledger es la verdad contable; la arista es la proyección de grafo. Misma
transacción, así que no divergen. Es el argumento multi-modelo hecho código.

**La cotitularidad es un atributo de la arista `owns`**, no una tabla puente.

**Cada detector lleva su control negativo.** Un detector que solo se ha visto
acertar no está probado.

## Demostración

Dos vías, que se refuerzan: un guion de terminal que narra el ataque paso a
paso, y Surrealist para enseñar consultas en vivo. El oyente de `LIVE SELECT`
hace que las alertas aparezcan según ocurren.

## Riesgos asumidos

- `LIVE SELECT` solo funciona en un nodo, lo que contradice el argumento de
  escalabilidad distribuida del documento original. Se declara en la memoria.
- Los eventos síncronos encarecen cada escritura.
- Los permisos de campo sobre PAN y CVV no se aplican mientras se trabaje como
  `root`. Necesitan `DEFINE ACCESS` para ser demostrables.

## Siguientes pasos

1. `DEFINE ACCESS` y usuarios reales, para la demo de PAN/CVV con dos sesiones.
2. Generador de volumen, para medir los detectores con datos de verdad.
3. Comparativa medida contra un CTE recursivo en PostgreSQL, incluyendo los
   casos donde SurrealDB no gana.
4. Reintento ante conflicto de escritura en el cliente.

## Decisión abierta

Dónde vive este código a largo plazo. Ahora está en `db/` dentro del repo de
iOS, que fue lo pedido. Un repositorio propio en la organización lo separaría
del ciclo de vida de la app; conviene hablarlo en grupo.
