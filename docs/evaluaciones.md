# Evaluaciones y libro de notas

## Organización

Cada sección tiene su propio plan de evaluación. Una asignatura puede disponer de esquemas completos reutilizables (100%): administración comparte sus esquemas con docentes; los esquemas personales del docente solo son visibles para él. Aplicarlos crea copias independientes y solo está permitido en secciones sin evaluaciones. Nunca reemplaza notas ni planes existentes automáticamente.

## Flujo docente

1. Abre **Evaluaciones** y elige sección, asignatura y período.
2. En **Distribución y plantillas**, crea componentes o copia un esquema de esa asignatura. Para pasar de 40/60 a 50/50 cambia ambos porcentajes y guarda la distribución completa con un motivo.
3. En **Libro de notas**, escribe valores entre 0 y 100. Un campo vacío es pendiente; cero es una nota válida.
4. Escribe un motivo y guarda los cambios de cada componente como borrador. Solo se envían las celdas modificadas; las otras notas publicadas no se convierten en borrador.
5. Publica las notas guardadas. La interfaz bloquea publicar si hay cambios sin guardar y muestra cantidades publicadas, borradores y pendientes.
6. Cierra la evaluación cuando todos los estudiantes inscritos activos tengan una nota publicada. Retirados y estudiantes en espera no bloquean el cierre.
7. Administración puede reabrir una evaluación con motivo; primero debe reabrirse el período si está cerrado y ajustarse el plazo de calificación si ya venció. Si la sección estaba cerrada, la reapertura de evaluación la activa para la corrección y lo deja auditado. Los estudiantes con selección completada o reprobada permanecen visibles para corregir su historial; retirados y estudiantes en espera no se califican. Cierres, reaperturas y distribuciones quedan auditados.

## Resultados

Las notas publicadas se ponderan sobre 100. Por ejemplo, 80 en un componente de 40% y 90 en uno de 60% producen 86, no el promedio simple de 85.

El resultado es provisional mientras falten componentes, notas publicadas o cierres. Solo un plan de 100% con todas sus evaluaciones cerradas y todas las notas publicadas por estudiante genera aprobación definitiva. Este cálculo se reutiliza en récord, pensum, graduación, selección de asignaturas, paneles y portal de tutores.

Los registros antiguos **sin plan ponderado** conservan el cálculo histórico de promedio de notas publicadas (modo `legacy`). No se reinterpretan ni se borran automáticamente. Si se añade un plan ponderado, sus notas deben registrarse en los componentes correspondientes: las notas antiguas sin evaluación no se mezclan con el plan nuevo.

## Correcciones e historial

Una nota se identifica por estudiante inscrito y evaluación, no por el nombre. Renombrar una evaluación no duplica las notas. Las ediciones individuales exigen un motivo; se conserva quién cambió la nota, valores, estados y fecha. Publicar también registra un evento.

El icono de historial permite consultar los cambios y anular una nota abierta con motivo. La anulación conserva físicamente la nota y su historial, pero la excluye de resultados y vistas de estudiantes. Puede registrarse nuevamente en la misma celda, reutilizando su identidad. Una selección con notas no puede eliminarse físicamente: debe retirarse para conservar el expediente.

Estudiantes y tutores no reciben notas en borrador ni anuladas, tampoco mediante una consulta directa por identificador. Las notas borrador no otorgan créditos ni cumplen prerrequisitos.

## Seguimiento por sección

En **Calificaciones y evaluaciones**, el resumen y el detalle incluyen las mismas selecciones: activas, completadas y reprobadas. Excluyen retirados y lista de espera, también en el seguimiento de asistencia. Así se conservan resultados históricos sin contar estudiantes que ya no pertenecen al seguimiento académico.

La **media de resultados publicados** se calcula solo entre estudiantes con algún resultado publicado y explica su denominador. Puede combinar resultados provisionales y definitivos; no equivale al promedio de aprobaciones ni trata pendientes como cero. Ejemplo: una nota publicada de 80 con peso 40% aporta 32 puntos acumulados, no una nota definitiva de 32.

Las tarjetas muestran estudiantes con resultado definitivo o por completar, notas borrador/publicadas, evaluaciones cerradas y porcentaje del plan configurado. El filtro de pendientes significa resultados no definitivos, aunque ya tengan notas publicadas; el filtro de borradores permite localizar trabajo pendiente de publicación.

El resumen permite buscar por asignatura, código de sección o docente y filtrar por período de la sección. El detalle permite buscar por nombre o matrícula y filtrar por período de selección y estado del resultado. Cada nota muestra su peso y aporte; solo las publicadas contribuyen. Las anuladas permanecen en un historial separado, sin influir en el resultado. Las notas históricas sin evaluación están identificadas explícitamente.

**Abrir libro de notas** lleva a Evaluaciones con la sección seleccionada. El seguimiento es de consulta: no modifica calificaciones. Sus consultas de caché se separan por usuario.

## Alcance funcional

La escala actual sigue siendo 0–100 y el umbral de aprobación es configurable institucionalmente. Recuperaciones, rúbricas y evaluaciones extraordinarias requieren reglas adicionales y no forman parte de esta fase.
