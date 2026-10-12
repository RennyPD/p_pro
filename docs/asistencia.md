# Asistencia

## Registro por sección

En Asistencia → sección → Registrar asistencia, seleccionar fecha y pasar lista. Cada estudiante inicia **Sin registrar** si no existe registro. Esto no equivale a presente ni ausente. Se ofrecen Presente, Ausente, Tardanza, Justificada y Salida anticipada, observación y referencia del justificante.

La acción de marcar pendientes como presentes es explícita y solicita confirmación: incluye los pendientes ocultos por la búsqueda. Guardar envía únicamente estudiantes modificados y requiere motivo. Una justificación requiere observación o referencia. No se cargan archivos adjuntos: la referencia es texto.

Cambiar fecha o salir mediante los enlaces del registro advierte si hay cambios pendientes; recargar/cerrar la pestaña también. No hay autosave. Los cambios se guardan en una transacción y se actualizan las consultas del seguimiento, estudiante y paneles.

## Reglas conservadas de porcentaje

`presencias computables / registros guardados × 100`.

- Presente, Tardanza y Salida anticipada cuentan como presencia.
- Ausente y Justificada no cuentan como presencia.
- Días sin registros no se cuentan como ausencia ni se agregan al denominador.
- Sin registros se muestra sin datos, no 0%.

No se reinterpretan registros antiguos ni se cambia esta regla. Una justificación explica la ausencia pero no la excluye del denominador. El resultado no es porcentaje de todas las clases programadas.

## Validaciones

Solo administración o docente asignado con permiso `grades.manage` registra. Los estudiantes consultan sus registros y no pasan lista. Asistencia nueva requiere selección activa; selecciones completadas o reprobadas permiten corregir registros existentes, no añadir asistencia nueva. Retirados y lista de espera no se registran. Secciones cerradas/canceladas o períodos cerrados requieren reapertura por los procedimientos correspondientes.

No se aceptan fechas futuras ni fuera del período. Se utiliza el calendario local del servidor para determinar hoy; las fechas de clase son fechas civiles, no instantes convertidos a UTC.

Se validan días contra los encuentros configurados; si no hay encuentros, contra los días de la sección. Una sesión extraordinaria en otro día exige administrador y motivo de excepción. Un registro histórico puede corregirse en su día original, aunque el horario actual no coincida. La marca de día no lectivo en Agenda sigue siendo informativa: no anula ni bloquea automáticamente la asistencia.

Hay un registro por selección de estudiante y día, incluso si las horas difieren. Se mantiene el modelo diario: no distingue dos encuentros del mismo día. POST individual rechaza duplicados, y el pase de lista actualiza el existente. Correcciones individuales requieren motivo; el envío masivo que corrige registros también debe indicar motivo explícito. Campos nulos, estudiantes duplicados en un envío y estudiantes de otras secciones se rechazan sin guardar parcialmente.

## Seguimiento y vista estudiantil

El seguimiento mantiene resumen y detalle sobre las mismas selecciones: activas, completadas y reprobadas. Filtrar Desde/Hasta recalcula asistencia y cantidades solo sobre ese rango. Se muestran los cinco estados y registros totales. El filtro de estado en el detalle modifica las filas visibles, no el porcentaje del rango.

Mi asistencia muestra asignatura, sección, período, cantidad de presencias computables y registros, cinco estados y fechas/observaciones/referencias. Conserva consulta histórica de las selecciones, con filtros de período y fechas.

## Historial y conservación

Cada registro/corrección nueva conserva autor, fecha, motivo y valores anteriores/nuevos. El botón Historial permite consultarlo al personal autorizado de la sección. Registros anteriores a esta actualización no reciben un autor ficticio: sus correcciones posteriores sí quedan auditadas.

La interfaz no ofrece eliminación. El endpoint heredado de eliminación conserva una instantánea en historial antes de borrar y exige autorización y período abierto. El historial no se elimina en cascada con registros académicos; no se modifica automáticamente ningún registro existente.

## Actualización y pruebas

Respaldar SQLite (`python -m scripts.backup_database`) y ejecutar `alembic upgrade head`. La revisión `20261012_0029` agrega índice diario único e historial. Si encuentra registros duplicados por día, se detiene antes de cambios: no elige ni elimina registros por su cuenta.

Prueba: abrir fecha sin registros → comprobar Sin registrar → marcar estados → justificar con observación → guardar con motivo → consultar resumen y detalle → corregir y consultar historial → entrar como estudiante y revisar fecha/comentario. Probar rechazos por fecha futura, día no programado, período cerrado y selección no activa. Verificar sesión extraordinaria con excepción administrativa.
