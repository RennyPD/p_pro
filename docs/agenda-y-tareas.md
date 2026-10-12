# Agenda y tareas

## Conceptos

La **agenda académica** reúne eventos institucionales, vencimientos de tareas publicadas y fechas de evaluación. Se consulta por mes, semana o lista del mes, con filtros de sección, texto y tipo y formato horario de 12/24 horas. No sustituye el horario recurrente de clases. Los días no lectivos son marcas informativas: no anulan automáticamente clases ni registros de asistencia.

**Tareas y entregas** organiza las actividades por asignatura, sección y período. Las alertas y métricas institucionales permanecen en Control institucional, no mezcladas con la agenda.

## Recorrido docente / administrador

1. Crear tarea, seleccionar sección, escribir instrucciones y establecer plazo y puntuación máxima.
2. Guardar como borrador o marcarla publicada. Los estudiantes no acceden a borradores, tampoco filtrando por sección.
3. Definir si permite entrega tardía y reenvío. Abrir una tarea muestra el listado nominal de estudiantes y quién todavía no ha entregado.
4. Revisar el contenido e historial de intentos; registrar puntuación (incluido cero) y devolución visible al estudiante.
5. Cerrar para dejar de recibir entregas. Archivar conserva los registros y bloquea su calificación. Se puede consultar el histórico con los filtros.

Con entregas existentes no se cambia sección, vínculo de evaluación ni escala. No hay eliminación física de tareas o entregas en esta interfaz. Períodos/secciones cerrados y plazos de calificación vencidos bloquean cambios académicos; requieren el procedimiento administrativo de reapertura.

## Recorrido estudiante

Ver las tareas publicadas de sus secciones, abrir instrucciones, enviar contenido y confirmar el estado de la entrega. Puede reenviar antes de calificar si está permitido: se conserva cada intento. Una entrega ya calificada no admite reenvío, para no invalidar resultados publicados. Puede consultar puntuación y comentarios; el resultado de la tarea no implica por sí solo una nota académica.

Solo un estudiante con selección activa (`enrolled`) puede entregar. Las selecciones históricas completadas/reprobadas permiten consultar, no entregar; retirados y lista de espera no acceden por esa selección.

## Tareas calificables

Una tarea de práctica no altera el promedio académico. Una calificable se vincula a una evaluación de **la misma sección**. Se admite una tarea por componente evaluativo; no se inventa una media entre múltiples tareas.

En **Crear notas borrador**, el docente indica motivo y confirma. Se normaliza `puntuación × 100 / máximo`. La transferencia es transaccional, requiere permiso de calificaciones y respeta cierre de evaluación/período. No publica notas ni sobrescribe notas independientes o diferentes. Repetir la transferencia omite resultados iguales ya transferidos por esa tarea y permite añadir entregas calificadas posteriores. Si el resultado cambió después de transferir, debe revisarse explícitamente en Evaluaciones. Allí se publican y cierran las notas con el flujo habitual.

Las acciones principales quedan en auditoría. El historial de contenido solo está disponible al estudiante propietario y al personal autorizado de la sección.

## Eventos y tutores

Administración crea y edita eventos institucionales o por sección. Docentes solo gestionan eventos de sus secciones. Tutores pueden consultar agenda y tareas publicadas de sus estudiantes vinculados, sin crear ni entregar y sin acceder al contenido privado de entregas de otros usuarios.

Las fechas enviadas desde la interfaz se convierten a UTC y se presentan en la zona local del navegador. Las fechas antiguas sin zona se interpretan como UTC, igual que el backend.

## Actualización local

Respaldar SQLite con `python -m scripts.backup_database` y aplicar `alembic upgrade head` usando el entorno virtual. La migración `20261012_0028` agrega políticas e historial y copia las entregas existentes como primer intento. No borra datos. Si ya hay múltiples tareas ligadas a una misma evaluación, detiene la migración antes de modificarla y exige revisar ese caso.

## Prueba sugerida

Crear borrador docente → comprobar que no aparece al estudiante → publicar → entregar y reenviar → revisar historial docente → calificar con devolución → comprobar resultado estudiante → transferir a evaluación → verificar borrador y publicar allí → cerrar y comprobar rechazo de entregas → archivar y consultar histórico. Probar también plazo vencido, entrega tardía permitida y accesos de otra sección.
