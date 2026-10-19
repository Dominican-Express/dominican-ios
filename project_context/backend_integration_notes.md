# Integración futura — sin backend en esta entrega

## Frontera actual
BankStore recibe `any BankRepository`; `snapshot()` obtiene BankSnapshot y `simulatePayment(_:)` devuelve un recibo explícitamente demo. MockBankRepository añade latencia asíncrona y respeta cancelación. Las vistas no hacen solicitudes de red. Una integración de consulta puede inyectar otra implementación desde App conservando modelos/view models.

## Contratos futuros
Separar repositorios de cuentas, tarjetas, movimientos y contactos cuando existan endpoints. Incorporar DTOs y mapeo a entidades estables. Paginar movimientos; estados loading/empty/error/retry, control de cancelación y fechas Date en lugar de etiquetas visuales del mock. Dinero Decimal + divisa ISO; API con importes decimales como string o unidades menores, nunca Double.

La simulación de pagos no debe convertirse silenciosamente en un envío real. Diseñar un servicio transaccional distinto con confirmación autenticada, idempotencia, comprobación de titularidad/límites y recibo autoritativo. Hoy los saldos permanecen intactos.

## Arquitectura decidida (2026-10-19): sin backend intermedio
El documento original proponía un backend Java delante de SurrealDB. **Se descarta**: la app habla directamente con SurrealDB 3.2, que está pensada para ello. El detalle está en `db/README.md` («La API, dentro de la base de datos») y el código en `db/schema/07_api.surql`.

- **Sesión:** `POST /signin` con `{ns, db, ac: "banca", email, pass}`. Devuelve un token de usuario de la app, que se guarda en Keychain. iOS nunca lleva credenciales de la base: el token solo da los permisos de ese cliente.
- **Lecturas:** consultas SurrealQL por `POST /sql` con el token. Los permisos de la base ya filtran a lo suyo: sus cuentas, sus movimientos, sus tarjetas (el PAN y el CVV solo tras verificar el PIN), sus contactos y los cotitulares.
- **Escrituras:** endpoints HTTP JSON definidos dentro de la base, en `POST /api/<ns>/<db>/<ruta>`: `/transfers`, `/bizum` y `/contacts`. Comprueban la titularidad y devuelven códigos HTTP de verdad (201, 403, 404, 409, 422).
- **Importes:** siempre como texto (`"12.50"`), nunca como número JSON; el endpoint rechaza un número con 400.
- **Idempotencia:** cada orden lleva un `id` que genera la app (un UUID por intento de pago). Repetir con el mismo id devuelve la respuesta original sin pagar dos veces.
- **Reintento obligatorio** ante «Transaction conflict … can be retried», que SurrealDB devuelve como **HTTP 400**: se reintenta con el MISMO id. Es seguro por la idempotencia. Referencia: `api()` en `db/demo/session.py`.
- **Alertas:** `LIVE SELECT` sobre `fraud_alert` por WebSocket (`/rpc`), ya filtrado por los permisos.

En `BankRepository` esto supone una implementación `SurrealBankRepository` con URLSession; las vistas y los view models no cambian.

## Seguridad y persistencia futuras
Sesión segura y tokens en Keychain; autenticación real antes de mostrar PAN/CVV. No almacenar/loguear CVV; evitar capturas sensibles y borrar datos al caducar la sesión. Diseño exacto sujeto a contrato y revisión de seguridad. La confirmación actual no equivale a biometría ni autorización.

Para offline, repositorio local SwiftData u otra opción nativa detrás de contratos, estrategia de caché, sincronización, conflictos y revocación de permisos. No se ha añadido persistencia porque esta fase solo solicita mocks.

## Decisiones abiertas del PDF
Alcance final de funciones adicionales y profundidad del análisis de patrones/fraude. Resolver antes de diseñar el esquema definitivo.
