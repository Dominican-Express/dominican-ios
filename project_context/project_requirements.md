# Requisitos extraídos

## Funcionales del PDF
- Usuario con varias cuentas, cada una con varias tarjetas: entidades relacionadas por identificadores; dos cuentas y dos tarjetas demo.
- Cuenta: número, saldo, divisa y titular; detalle y compartir información demo.
- Tarjeta: número, caducidad y CVV bajo verificación; datos sintéticos tras confirmación explícita simulada.
- Historial por cuenta/tarjeta; búsqueda/filtro y exportación CSV.
- Transferencias dentro del banco y Bizum a usuarios del banco; formularios/revisión/resultado demo.
- Cotitularidad; titulares y roles visibles, cambio local de rol e invitación simulada.
- Avisos de ingresos, nómina y gastos; lista y preferencias en memoria, sin push real.

## Funciones adicionales implementadas en DEMO
Bloqueo/desbloqueo, límites de gasto/retirada, contactos favoritos, domiciliaciones, categorización e Insights, alerta de ocio, configuración de alertas de saldo bajo/sospechosos. No existe detección de fraude ni motor de notificaciones.

## No funcionales
Swift 6, SwiftUI, iPhone, iOS 26+ con SDK del Xcode instalado; Observation/MVVM y async/await; protocolo de repositorio inyectable. Cero librerías externas, red o lógica bancaria real. Colores adaptativos, soporte inicial Dynamic Type, controles etiquetados y Safe Areas. Scroll en formularios y vistas, animaciones que respetan Reducir movimiento. Cinco pestañas persistentes.

## Flujos
Consultar saldo → cuenta o actividad; tarjeta → gestión/datos; contacto + importe → revisión → resultado simulado; cuenta compartida → roles/invitación; categorías → detalle; perfil → preferencias/documentos.

## Entidades
BankAccount, BankCard, BankTransaction, Contact, AccountMember, SpendingCategory, BankNotice; BankSnapshot agrega la demo. DemoPaymentRequest y DemoReceipt delimitan la simulación.

## Diferidos
Objetivos de ahorro, conversión de divisas, préstamos/crédito, detalle del análisis de fraude (opcionales del PDF). Autenticación, REST/GraphQL, persistencia, sincronización y push reales. Consultar `decisions.md` para discrepancias.

## Criterios pendientes de aceptación
Build iOS completado en Debug/Release. Recorrido de las ocho pantallas y flujos principales probado en dos simuladores con modo claro/oscuro. Texto máximo probado en Tarjetas y envío. Pendientes: comparación cuantitativa ≥95 %, VoiceOver manual y cobertura completa de tamaños accesibles. Los resultados reales están en `output/qa` y `progress_log.md`.
