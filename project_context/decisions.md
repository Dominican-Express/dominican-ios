# Decisiones técnicas y discrepancias

## 2026-09-23 — Alcance antes de implementar
- Fuente principal: PDF funcional de 3 páginas, leído completo. Referencia: DOMI RENDER MOVIL.png, ocho pantallas analizadas.
- App SwiftUI para iPhone, MVVM, Observation y async/await. Sin dependencias externas, red, backend ni operaciones bancarias reales.
- Se reproducen las ocho pantallas. Los detalles no dibujados se infieren únicamente para funciones del PDF: datos de cuenta/tarjeta, notificaciones, límites, domiciliaciones, documentos, seguridad, confirmación de pagos y cotitulares.
- El PDF deja abierto el alcance adicional. Bloqueo, límites, contactos, categorías y extractos se incluyen como DEMO por su presencia en referencias. Ahorro, divisas, préstamo y detección de fraude quedan fuera de esta fase.
- Insights aparece en la imagen, no como módulo explícito en PDF: se considera la visualización de categorización de gastos. Sus categorías suman 1.245,70 €, pero los porcentajes impresos son redondeados e inconsistentes (33/24/21/22). Se conservan importes y se calculan porcentajes coherentes.
- La imagen de Tarjetas contiene una etiqueta ilegible junto a Bloquear tarjeta. Se interpreta como «Ver datos», conforme a la consulta bajo verificación del PDF.
- La verificación y los envíos serán explícitamente simulados. Nunca se usan credenciales, biometría ni datos bancarios reales.
- El gráfico, los patrones de tarjeta y los componentes se dibujan con SwiftUI. Al no existir un logotipo independiente, la marca se reconstruye tipográficamente; requiere un SVG/PDF oficial para fidelidad exacta. No se incorpora la captura completa como pantalla.
- Barra inferior de cinco destinos persistentes. Se usa barra propia con controles accesibles para conservar la geometría de la referencia frente al estilo flotante del sistema reciente.
- Deployment target iOS 26.0, SDKROOT iphoneos sin fijar SDK, Swift 6. Se abre con Xcode estable que incluya iOS 26 o superior. La versión exacta estable debe comprobarse al instalar Xcode; los resultados web disponibles no permiten asegurar el último parche a fecha de trabajo.
- No existe Xcode.app ni SDK de iOS en este equipo; solo Command Line Tools (Swift 6.4). No es posible certificar compilación iOS ni fidelidad del 95% sin ejecutar y comparar capturas. Se entrega proyecto Xcode y se registra esta limitación, sin declarar verificaciones no realizadas.
- Estado efímero en memoria, reiniciable al cerrar; repositorio inyectado mediante protocolo Sendable. SurrealDB/Java quedan exclusivamente en notas de integración futura.

## Cierre de implementación
- Swift Package utiliza tools 6.2; el proyecto mantiene lenguaje Swift 6.0. No se necesita Swift 6.4 para el código de aplicación.
- Exportación como archivo CSV con CoreTransferable/UniformTypeIdentifiers; sin archivos persistidos ni red. Compartir solo abre la hoja nativa y requiere selección explícita del usuario.
- Se ha generado icono desde código CoreGraphics/CoreText (herramienta de desarrollo); la aplicación usa exclusivamente frameworks nativos de iOS.
- Preferencias y cambios demo se guardan solo en memoria. Las domiciliaciones mantienen estado local de vista; no representan mandatos reales.
- Se conservaron fechas de marzo de 2024 de la referencia. Insights mensual no se deriva de la muestra reducida del historial; se indica en el detalle de categoría.
- Para pruebas locales, `scripts/test.sh` incluye la ruta del plugin Swift Testing cuando se usan Command Line Tools. Sin dependencias externas de testing.
