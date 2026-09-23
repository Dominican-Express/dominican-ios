# Validación iOS — 23 de septiembre de 2026

Xcode 27.0 (27A266a), SDK/runtime iOS 27.0, deployment mínimo iOS 26.0.

| Comprobación | Resultado |
|---|---|
| Debug · iOS Simulator | Compilado y ejecutado |
| Release · iPhone arm64, sin firma | BUILD SUCCEEDED |
| Swift Testing · dominio y view models | 9 pruebas, 0 fallos |
| XCUITest · iPhone 18 Pro | 6 pruebas, 0 fallos |
| XCUITest · iPhone 17e oscuro | 1 recorrido de las 8 pantallas, 0 fallos |
| Texto AX5 en Tarjetas | Auditoría de recortes aprobada |
| Envío con texto AX5 | Flujo completo aprobado |

Las pruebas UI cubren las ocho pantallas, búsqueda/filtros y hoja de compartir CSV, bloqueo/verificación de tarjeta, límites, ajustes de seguridad, invitación de cotitular y envío con validación/recibo. La apertura de la hoja de compartir no envía documentos a terceros.

## Capturas reales de simulador

| Pantalla | Claro · iPhone 18 Pro | Oscuro · iPhone 17e |
|---|---|---|
| Inicio | [Ver captura](light-iphone18pro/01-Inicio.png) | [Ver captura](dark-iphone17e/01-Inicio.png) |
| Tarjetas | [Ver captura](light-iphone18pro/02-Tarjetas.png) | [Ver captura](dark-iphone17e/02-Tarjetas.png) |
| Movimientos | [Ver captura](light-iphone18pro/03-Movimientos.png) | [Ver captura](dark-iphone17e/03-Movimientos.png) |
| Transferir | [Ver captura](light-iphone18pro/04-Transferir.png) | [Ver captura](dark-iphone17e/04-Transferir.png) |
| Bizum | [Ver captura](light-iphone18pro/05-Bizum.png) | [Ver captura](dark-iphone17e/05-Bizum.png) |
| Cuenta-compartida | [Ver captura](light-iphone18pro/06-Cuenta-compartida.png) | [Ver captura](dark-iphone17e/06-Cuenta-compartida.png) |
| Insights | [Ver captura](light-iphone18pro/07-Insights.png) | [Ver captura](dark-iphone17e/07-Insights.png) |
| Perfil | [Ver captura](light-iphone18pro/08-Perfil.png) | [Ver captura](dark-iphone17e/08-Perfil.png) |

[Tarjeta con texto accesible máximo](light-iphone18pro/13-Tarjetas-texto-accesible.png) · [Recibo demo](light-iphone18pro/09-Recibo-demo.png) · [Hoja de exportación](light-iphone18pro/10-Exportar-CSV.png)

## Evidencia

- `ui-tests-summary.json`: resumen exportado de `/tmp/DominicanUI-Final.xcresult`.
- `dark-tests-summary.json`: resumen exportado de `/tmp/DominicanUI-DarkFinal.xcresult`.
- `domain-tests.log`: salida de las nueve pruebas de dominio.
- Compilación Release: `/tmp/dominican-release.log`; producto `/tmp/DominicanRelease/Build/Products/Release-iphoneos/DominicanExpress.app` (sin firma).
- Producto ejecutable en simulador: `/tmp/DominicanExpressDerivedData/Build/Products/Debug-iphonesimulator/DominicanExpress.app`.

Los archivos de /tmp son temporales; las capturas y resúmenes de esta carpeta son la evidencia conservada. Ejecutar `./scripts/test-ui.sh UUID` para regenerar las pruebas o ⌘U desde Xcode.

## Límites de la validación

Inspección visual de las ocho pantallas en ambos modos y corrección de recortes/espaciado, sin porcentaje de similitud medido. Logo oficial vectorial, VoiceOver manual en dispositivo, runtime iOS 26 y cobertura completa de tamaños accesibles pendientes. No hay firma, publicación ni conexión bancaria real.

Xcode emite el aviso informativo de extracción AppIntents porque la app no usa ese framework. En dos transiciones de teclado se registró «Invalid frame dimension (negative or non-finite)» sin fallo de aserciones; pendiente de aislar si persiste. No se han ocultado esos avisos ni se afirma validación de producción.
