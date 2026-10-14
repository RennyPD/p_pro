# Diseño de la interfaz

## Criterios compartidos

La capa `frontend/src/workspace-design.css`, cargada después de los estilos de los módulos, establece la jerarquía visual común sin cambiar las reglas de negocio:

- Encabezados compactos, una acción principal visible y descripciones breves. Las explicaciones extensas se ofrecen bajo demanda.
- Paneles y campos con un ritmo de espaciado uniforme, controles de al menos 40–44 px y estados con texto además de color.
- Formularios de dos columnas cuando hay espacio; referencias extensas, búsquedas relacionadas y textos largos pueden ocupar el ancho completo. En móvil se usa una columna.
- Las instrucciones largas no dependen de un placeholder recortado: se muestran como ayuda asociada al campo.
- Modales con título persistente, un solo desplazamiento, Escape, recorrido de teclado contenido y restauración del foco al cerrar. Los botones de formularios de recursos permanecen accesibles durante el desplazamiento.

## Información por tarea

Asistencia y calificaciones muestran primero una cifra principal, cantidad de estudiantes y tres contadores breves. El desglose se abre sin navegar; «Ver estudiantes» abre el seguimiento individual. No se ocultan ni se alteran las fuentes del cálculo.

Control institucional combina indicadores generales, señales de seguimiento, tarjetas de carreras y filas de asignaturas. Las muestras (cantidad de resultados o registros) acompañan las cifras para distinguir un cero real de la ausencia de datos. La proporción de estudiantes activos no se presenta como permanencia histórica.

Los directorios ya no repiten un bloque promocional encima del título. Su explicación se conserva en «Acerca de esta vista».

## Revisión manual sugerida

1. Abrir Estudiantes, Docentes y Carreras; comprobar filtros, acciones y formularios con campos largos. Abrir y cancelar sin guardar para revisar diseño sin alterar datos.
2. Revisar Asistencia y Calificaciones, abrir los desgloses y después el detalle de estudiantes. Confirmar que los resultados provisionales no se confundan con definitivos y las secciones vacías no se marquen como finalizadas.
3. Revisar Control institucional con y sin muestras académicas, y cambiar el período.
4. Abrir Nueva tarea, Nuevo evento, Nuevo aviso y los formularios financieros; comprobar márgenes y desplazamiento.
5. Repetir en ancho móvil; recorrer los modales con Tab y Shift+Tab, cerrarlos con Escape y comprobar el retorno del foco.

Las pruebas automatizadas cubren los estados académicos, las muestras ausentes, los desgloses y el comportamiento básico de los modales. No sustituyen la revisión visual de todos los formularios y estados posibles.
