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
- Estado efímero en memoria, reiniciable al cerrar; repositorio inyectado mediante protocolo Sendable. SurrealDB queda en las notas de integración futura (sin Java: se decidió el 2026-10-19 que la app hable directamente con la base).

## Cierre de implementación
- Swift Package utiliza tools 6.2; el proyecto mantiene lenguaje Swift 6.0. No se necesita Swift 6.4 para el código de aplicación.
- Exportación como archivo CSV con CoreTransferable/UniformTypeIdentifiers; sin archivos persistidos ni red. Compartir solo abre la hoja nativa y requiere selección explícita del usuario.
- Se ha generado icono desde código CoreGraphics/CoreText (herramienta de desarrollo); la aplicación usa exclusivamente frameworks nativos de iOS.
- Preferencias y cambios demo se guardan solo en memoria. Las domiciliaciones mantienen estado local de vista; no representan mandatos reales.
- Se conservaron fechas de marzo de 2024 de la referencia. Insights mensual no se deriva de la muestra reducida del historial; se indica en el detalle de categoría.
- Para pruebas locales, `scripts/test.sh` incluye la ruta del plugin Swift Testing cuando se usan Command Line Tools. Sin dependencias externas de testing.

## 2026-09-23 — Validación con Xcode instalado
- Xcode 27.0 (27A266a), SDK/runtime iOS 27.0. Se mantiene deployment target iOS 26.0.
- Incorporado target DominicanUITests y al esquema compartido; generador del proyecto conserva la configuración de pruebas. No se añaden dependencias externas.
- Corregido formato monetario: la referencia agrupa cuatro cifras (8.425,60), mientras es_ES en el sistema nuevo omite ese separador. NumberFormatter utiliza separadores españoles explícitos y agrupación de tres cifras, con prueba de regresión.
- Reducida la separación de la cabecera de Inicio y ajustada su tarjeta a proporción 1,9 para recuperar la densidad de la referencia.
- La auditoría de recortes encontró el nombre de tarjeta truncado con texto de accesibilidad máximo. En tamaños accesibles se apila el encabezado y se amplían tarjeta/carrusel; se mantiene el diseño normal para tamaños estándar.
- ContactListView expone el nombre del contacto como etiqueta accesible, sin iniciales ni chevron redundantes.
- Sustituido símbolo no disponible chart.donut por chart.pie; eliminada concatenación Text obsoleta en iOS 26.
- Las pruebas UI usan `-collect-test-diagnostics never` para evitar la recogida de sysdiagnose excesivamente lenta de este runtime tras fallos. Se conservan aserciones, capturas e informes XCTest.
- Tras inspección de capturas AX5, la barra inferior limita su Dynamic Type a XXXL estándar y añade Large Content Viewer; el contenido principal mantiene tamaños accesibles completos. Se evita fragmentar las cinco etiquetas de navegación.
- BrandMark fija su altura intrínseca para no perder la segunda línea en el iPhone pequeño. OutlinedButtonStyle reemplaza el estilo bordered del sistema, que en iOS 27 producía cápsulas diferentes de la referencia.
