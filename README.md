# Dominican Express · iOS DEMO

Aplicación nativa SwiftUI para iPhone, basada en las ocho pantallas de `DOMI RENDER MOVIL.png` y en el documento funcional incluido en el repositorio. Sin servicios externos ni operaciones reales.

## Abrir y ejecutar

1. Instala Xcode estable con SDK iOS 26 o posterior.
2. Abre `DominicanExpress.xcodeproj` (el paquete Swift solo contiene la lógica para pruebas).
3. Selecciona el esquema **DominicanExpress** y un simulador iPhone.
4. Ejecuta con **⌘R**. Para un iPhone físico, configura tu equipo en Signing & Capabilities.

No hay dependencias que instalar, claves ni backend. Deployment target iOS 26.0; Swift 6. El proyecto usa el SDK incluido con Xcode, sin fijar su versión de parche.

## Pantallas y demo

- Inicio: saldo, tarjeta, accesos a enviar/Bizum/pagar/añadir dinero, últimos movimientos, cuenta compartida e Insights.
- Tarjetas: dos tarjetas, bloqueo reversible, ocultación de saldo, datos bajo verificación **simulada**, límites e historial.
- Movimientos: filtros combinados, búsqueda, cuenta seleccionable, detalle y exportación CSV mediante la hoja nativa de compartir.
- Transferir/Bizum: contactos, cuenta demo, importe español, revisión, envío o solicitud simulados.
- Cuenta compartida: titulares, permisos locales e invitación simulada.
- Insights: anillo de categorías, dos períodos demo y alerta de ocio.
- Perfil: datos personales, notificaciones, límites, domiciliaciones, documentos y seguridad.

La navegación inferior conserva cinco destinos. Desplázate por Inicio para acceder a Cuenta compartida e Insights. Las operaciones no alteran saldos ni envían mensajes. Los cambios de estado son efímeros; reiniciar la app restablece la demo. El histórico usa fechas de marzo de 2024 para reproducir la referencia.

## Arquitectura

`Project/App` compone la app. `Core/BankStore` es el estado compartido observable e inyecta `BankRepository`. Los módulos de `Features` agrupan vistas, componentes y view models. `Models`, `Services`, `MockData`, `DesignSystem` y `Utilities` centralizan contratos, datos y presentación reutilizable.

La lógica de selección, filtrado, importes y envíos está separada en view models. Las vistas de consulta sencillas utilizan `BankStore` como view model compartido; no duplican modelos de dominio en cada módulo. La UI corre en MainActor y los servicios usan async/await con contratos Sendable.

## Verificación

```sh
./scripts/test.sh
```

Ocho pruebas de dominio/view models: importes, filtros, validación, simulación sin alterar saldo, bloqueo reversible, totales, CSV y errores. Se han ejecutado correctamente con Swift 6.4 en macOS. La sintaxis de todos los archivos y los plist del proyecto también se han validado.

**Pendiente:** este equipo no tiene Xcode ni SDK/simulador iOS. No se ha compilado ni ejecutado la aplicación iOS. La fidelidad del 95 %, VoiceOver, tamaños de pantalla y Dynamic Type requieren validación en simulador/dispositivo. El logotipo es una reconstrucción tipográfica, pendiente del vector oficial.

Con Xcode instalado:

```sh
xcodebuild -project DominicanExpress.xcodeproj -scheme DominicanExpress \
  -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/DominicanExpressDerivedData CODE_SIGNING_ALLOWED=NO build
```

El proyecto se regenera tras añadir archivos con `python3 scripts/generate_project.py`. El icono se genera con `swift scripts/generate_icon.swift Project/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon.png`.

Toda la continuidad, decisiones y pendientes está en `project_context/`. Empieza por `project_overview.md`.
