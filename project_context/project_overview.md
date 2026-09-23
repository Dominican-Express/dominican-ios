# Dominican Express — contexto de continuidad

## Objetivo
Demo bancaria nativa para iPhone, SwiftUI/MVVM, que reproduce ocho pantallas de la referencia. Proyecto académico UFV de Bases de Datos Avanzadas. El backend Java/SurrealDB pertenece a una fase futura.

## Fuentes de verdad
1. `Dominican Express — Funcionalidades y Justificación de SurrealDB.pdf`, 3 páginas, fecha 2026-09-21. Leído completo; páginas renderizadas e inspeccionadas.
2. `DOMI RENDER MOVIL.png`, 1536 × 1024, ocho pantallas. Analizada completa antes de programar.
3. Solicitud de implementación: nativo, Swift/SwiftUI, async/await, MVVM, mocks, Dark Mode, accesibilidad, documentación y fidelidad visual.

## Estado de entrega, 2026-09-23
Implementación de las ocho pantallas, detalles y flujos DEMO en 26 archivos Swift. Proyecto Xcode autocontenido, esquema compartido, icono y manifiesto de privacidad. No hay dependencias externas ni llamadas de red. Ocho pruebas de dominio/view models ejecutadas y aprobadas.

No hay Xcode.app/SDK iOS/simulador en este equipo: compilación y ejecución iOS pendientes. No certificar 95 % de fidelidad ni calidad de producción sin QA visual y de dispositivo. El logo se aproxima mediante texto vectorial; solicitar vector oficial para reproducción exacta.

## Cómo continuar
Abrir `DominicanExpress.xcodeproj` en Xcode estable con SDK iOS 26+. Ejecutar en iPhone. Consultar `pending_tasks.md` y `progress_log.md`. `README.md` contiene comandos. El paquete Swift no es la aplicación: expone únicamente el dominio para pruebas macOS.

## Mapa del código
- App: punto de entrada e inyección de BankStore.
- Core: navegación por cinco pestañas y BankStore observable compartido.
- DesignSystem: paleta semántica, estilos, campos, botones, avatares, filas, logo tipográfico.
- Features: Home, Cards, Activity, Payments, SharedAccount, Insights, Profile.
- Models: entidades Sendable. Services: protocolo BankRepository y contratos demo.
- MockData: snapshot fijo y repositorio asíncrono sin red.
- Utilities: importes Decimal y formato español.
- Resources: catálogo de assets/icono y PrivacyInfo.xcprivacy.
- Tests: ocho pruebas con Swift Testing. Scripts: generador determinista de proyecto, icono y comando de pruebas.

## Estado y datos
Ana García; cuenta personal € 8.425,60; compartida € 4.280,50; tarjeta principal disponible € 3.150; límite inicial € 5.000. Siete movimientos, siete contactos, tres cotitulares, cuatro categorías, cuatro avisos. Datos sintéticos y cuentas ES00 no válidas. El resumen Insights es independiente de la lista de movimientos recientes. Estado en memoria, sin almacenamiento persistente.
