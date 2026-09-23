# Integración futura — sin backend en esta entrega

## Frontera actual
BankStore recibe `any BankRepository`; `snapshot()` obtiene BankSnapshot y `simulatePayment(_:)` devuelve un recibo explícitamente demo. MockBankRepository añade latencia asíncrona y respeta cancelación. Las vistas no hacen solicitudes de red. Una integración de consulta puede inyectar otra implementación desde App conservando modelos/view models.

## Contratos futuros
Separar repositorios de cuentas, tarjetas, movimientos y contactos cuando existan endpoints. Incorporar DTOs y mapeo a entidades estables. Paginar movimientos; estados loading/empty/error/retry, control de cancelación y fechas Date en lugar de etiquetas visuales del mock. Dinero Decimal + divisa ISO; API con importes decimales como string o unidades menores, nunca Double.

La simulación de pagos no debe convertirse silenciosamente en un envío real. Diseñar un servicio transaccional distinto con confirmación autenticada, idempotencia, comprobación de titularidad/límites y recibo autoritativo. Hoy los saldos permanecen intactos.

## Arquitectura propuesta por el documento
Backend Java delante de SurrealDB. Cuentas/tarjetas/transacciones como documentos con esquema; usuario–cuenta y usuario–contacto como relaciones con permisos. Cotitularidad y transferencias deben verificarse del lado servidor. Transacciones ACID para cambios de saldo, según la propuesta del documento. Validar capacidades concretas contra la versión elegida al implementar; no se han instalado ni verificado SurrealDB o drivers.

REST o GraphQL detrás del protocolo; jamás credenciales de base de datos en iOS. La selección definitiva de transporte sigue abierta. Live Queries pueden alimentar eventos del backend y APNs; la app no se conecta directamente a la base.

## Seguridad y persistencia futuras
Sesión segura y tokens en Keychain; autenticación real antes de mostrar PAN/CVV. No almacenar/loguear CVV; evitar capturas sensibles y borrar datos al caducar la sesión. Diseño exacto sujeto a contrato y revisión de seguridad. La confirmación actual no equivale a biometría ni autorización.

Para offline, repositorio local SwiftData u otra opción nativa detrás de contratos, estrategia de caché, sincronización, conflictos y revocación de permisos. No se ha añadido persistencia porque esta fase solo solicita mocks.

## Decisiones abiertas del PDF
Alcance final de funciones adicionales y profundidad del análisis de patrones/fraude. Resolver antes de diseñar el esquema definitivo.
