# Sistema de diseño

Referencia: ocho iPhones del PNG. Paleta: azul eléctrico #0066FF, azul marino #06134D, noche #00132B, superficies #F3F5F8, azul hielo #E7F1FF; ingresos verdes y alerta naranja.
Tipografía nativa SF: títulos 20–22 semibold, importes 28–34 bold, cuerpo 15–17, metadatos 12–13. Dynamic Type mediante estilos relativos; layouts desplazables y sin altura fija para formularios.
Márgenes 20 pt, espaciado base 8 pt, tarjetas 16–20 pt de radio, inputs 12 pt, avatares circulares. Acciones mínimas 44 pt; encabezados centrados; cinco pestañas inferiores.
Inicio oscuro por diseño en ambos modos. Resto usa colores semánticos adaptados a Dark Mode. SF Symbols con etiquetas accesibles. Reducir movimiento desactiva animaciones decorativas.
Marca reconstruida tipográficamente a partir de la referencia, pendiente del vector oficial. Tarjetas implementadas con gradiente y ondas vectoriales, no una captura plana. Gráfico de anillo vectorial con leyenda accesible y valores textuales.

Validación en simulador: Inicio usa separación de 12 pt y tarjeta 1,9:1. En categorías de texto de accesibilidad, la cabecera de tarjeta se apila y la proporción es 0,78:1; carrusel de 470 pt para que el texto siga visible. Esta excepción se justifica por un recorte detectado mediante auditoría XCTest, no por un cambio de diseño estándar.

La barra inferior limita su escala hasta XXXL estándar, como los controles de navegación nativos, y ofrece Large Content Viewer para accesibilidad. Evita que los nombres de las cinco pestañas se fragmenten y ocupen un tercio de la pantalla a AX5. La marca usa altura intrínseca para mantener sus dos líneas. OutlinedButtonStyle conserva los botones rectangulares de borde azul de la referencia frente a las cápsulas por defecto de iOS 27.
