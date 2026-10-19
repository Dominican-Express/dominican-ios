# Tareas pendientes — tras validación en Xcode

## Completado
- Xcode 27.0 (27A266a) instalado y activo, SDK/runtime iOS 27.0.
- Compilación Debug para simulador y Release para iPhone sin firma.
- App instalada y ejecutada en simuladores iPhone 18 Pro e iPhone 17e.
- Pruebas de lógica, recorrido de las ocho pantallas, filtros, consulta/bloqueo de tarjeta, envío demo, límites, invitación y hoja de compartir.
- Capturas de las ocho pantallas en claro/oscuro, revisión visual y correcciones de espaciado, importes, logotipo, botones y barra inferior.
- Auditoría de texto recortado en Tarjetas con tamaño accesible máximo; flujo de envío con ese tamaño.

## Pendientes de calidad y aceptación
- Revisión manual integral con VoiceOver en dispositivo físico; las etiquetas y auditoría automática no sustituyen esta revisión.
- Verificar todos los detalles y formularios en todos los tamaños Dynamic Type. Se ha probado tamaño máximo en Tarjetas y envío, no cada combinación de vista/tamaño.
- Ejecutar en runtime iOS 26, mínimo soportado; el runtime instalado y probado es iOS 27.
- Instalación en iPhone físico requiere seleccionar equipo de firma. No se ha firmado ni publicado la aplicación.
- Comprobar entrega del CSV a una aplicación/destino externo elegido por el usuario; se ha validado el contenido con pruebas y la apertura de la hoja nativa, sin compartirlo con terceros.
- Investigar si persiste el aviso de runtime «Invalid frame dimension (negative or non-finite)» observado durante transiciones de teclado en dos pruebas. Los flujos finalizaron correctamente; no se ha identificado una dimensión inválida en el código propio.

## Fidelidad visual
- El logotipo sigue siendo una reconstrucción tipográfica; incorporar vector oficial para exactitud.
- Se han comparado visualmente capturas con la referencia y corregido diferencias evidentes. No existe medición que certifique ≥95 % de similitud.
- Las barras superiores usan controles nativos de iOS 27; su acabado difiere del render original. Conservar navegación nativa mientras se acuerda el nivel de reproducción exacta.
- Confirmar alcance final de funciones adicionales con el grupo, según el documento original.

## Fuera de esta fase
Conexión con SurrealDB (sin backend intermedio, ver `backend_integration_notes.md`), autenticación, APIs, persistencia, sincronización, APNs, biometría real y operaciones monetarias. Ahorro, divisas, crédito y análisis de fraude pendientes de decisión de producto.
