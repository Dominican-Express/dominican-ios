# Registro de progreso

## 2026-09-23 — Análisis
- Inspeccionado repositorio inicial: únicamente PNG y PDF, sin código ni instrucciones AGENTS.md.
- Leído el PDF completo (3 páginas); renderizadas e inspeccionadas las páginas. Analizada la referencia de ocho pantallas antes de escribir código.
- Documentados alcance, entidades, navegación, componentes, sistema visual y discrepancias antes de implementación.
- Entorno: macOS, Command Line Tools Swift 6.4, sin Xcode.app ni SDK iOS. Consulta de documentación Apple: https://developer.apple.com/design/human-interface-guidelines/tab-bars y notas de Xcode. No se afirma conocer el último parche estable.

## Implementación
- Creado proyecto Xcode, esquema compartido, deployment iOS 26.0, Swift 6, SDK dinámico.
- Implementados 26 archivos Swift: app, repositorio mock Sendable, datos demo, BankStore observable, view models, componentes y ocho pantallas con detalles.
- Tarjeta vectorial con ondas, marca tipográfica, paleta adaptativa, barra persistente, gráfico de anillo, estados de carga/error/vacío y animaciones con Reducir movimiento.
- Añadidos filtros/búsqueda, exportación CSV Transferable, verificación simulada, bloqueo reversible, límites, envíos/solicitudes sin modificar saldos, invitaciones/roles locales y preferencias.
- Generado icono 1024 con CoreGraphics/CoreText desde código y manifiesto de privacidad sin recogida de datos.
- Documentación de los diez archivos solicitados, README y scripts reproducibles. Sin dependencias añadidas.

## Validación
- `swiftc -frontend -parse` sobre todos los fuentes: correcto.
- `plutil -lint` sobre project.pbxproj y PrivacyInfo.xcprivacy: correcto.
- Se corrigió swift-tools-version del paquete de 6.0 a 6.2 para soportar `.iOS(.v26)`.
- El compilador requirió acceso a caché fuera del sandbox, aprobado. El motor SwiftPM por defecto no localizaba TestingMacros; se resolvió añadiendo la ruta explícita del plugin instalado. Ocho pruebas Swift Testing aprobadas (0,665 s): formato Decimal, filtros combinados, validación, envío sin cambiar saldos, bloqueo, totales, CSV y errores.
- Comprobación auxiliar de tipos SwiftUI con copias temporales adaptadas a macOS: correcta. Sustituyó modificadores exclusivos de iOS, colores UIKit y usó alias de State por ausencia del plugin SwiftUIMacros en las Command Line Tools. No equivale a build iOS ni verificación visual.
- Pendientes expresos: compilación iOS, ejecución en simulador/dispositivo, QA visual/95 %, Dark Mode y accesibilidad.

## Comprobación final
- Validación repetida tras añadir exportación Transferable: sintaxis y comprobación auxiliar de tipos correctas.
- Verificadas las referencias de los 26 fuentes en el proyecto, el XML del esquema y la presencia de los diez documentos de contexto.
- Icono final opaco RGB inspeccionado visualmente; se corrigió un primer render vacío usando CoreGraphics/CoreText.
- No hay archivos de trabajo temporales, cachés ni dependencias añadidas al repositorio. Las referencias originales se mantienen intactas.

## 2026-09-23 — Xcode instalado y validación real de iOS
- Xcode 27.0 (27A266a), SDK/runtime iOS 27.0. La ausencia de Xcode registrada arriba queda resuelta.
- Compilación Debug para iOS Simulator e instalación/ejecución en iPhone 18 Pro e iPhone 17e. Compilación Release arm64 para iPhone sin firma: BUILD SUCCEEDED. La validación ya no depende del chequeo auxiliar macOS.
- Creado target DominicanUITests en el proyecto y esquema. Seis pruebas cubren las ocho pantallas, búsqueda/CSV, bloqueo/verificación, validación/envío, límites/cotitularidad y texto AX5. Ejecución final: 6 pruebas, 0 fallos, 100,537 s. Recorrido oscuro en iPhone 17e: 1 prueba de ocho pantallas, 0 fallos.
- Swift Testing con toolchain Xcode: 9 pruebas, 0 fallos. Incluye regresión de separadores monetarios de cuatro cifras.
- Detectados/corregidos durante ejecución y revisión: separador de miles ausente, cabecera de Inicio excesiva, nombre de tarjeta recortado en AX5, etiqueta de contacto redundante, símbolo no disponible, concatenación Text obsoleta, logo truncado en tarjeta pequeña, botones en cápsula y barra inferior excesivamente grande en AX5.
- Exportadas e inspeccionadas capturas de las ocho pantallas en claro/oscuro. Tarjeta AX5 pasa auditoría de texto recortado; se probó el envío completo con ese tamaño.
- Informes y 21 capturas reales conservados en `output/qa`; README de esa carpeta contiene enlaces y alcance exacto. Documentación actualizada. Sin dependencias externas nuevas.
- Avisos conservados: AppIntents sin dependencia (informativo) y advertencia de dimensión de layout en transiciones de teclado, sin fallo funcional observado. No se afirma cero avisos de runtime.
- Pendientes acotados: VoiceOver manual/dispositivo físico, runtime iOS 26, matriz completa de texto accesible, vector de marca y certificación visual 95 %. No se ha firmado ni publicado la app.
