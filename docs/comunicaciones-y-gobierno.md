# Comunicaciones, Control institucional y Configuración

## Comunicaciones

Son avisos internos del portal; no se envían correos, SMS ni WhatsApp.

- Administración puede dirigir avisos a toda la institución, a un rol, a estudiantes de una sección o a sus tutores.
- El docente solo puede elegir sus secciones publicadas/activas y sus estudiantes o tutores. No puede publicar avisos globales ni en secciones ajenas.
- Secciones: solo selecciones en estado enrolled, estudiantes activos y, cuando la sección tiene período asignado, del mismo período. No se incluyen retirados, listas de espera ni selecciones completadas/reprobadas. Los tutores deben tener vínculo con un estudiante elegible y una cuenta de usuario.
- La vista previa muestra cantidad y distribución por rol, sin publicar. Al confirmar se vuelve a comprobar el alcance; si cambió, se debe revisar nuevamente.
- Cada publicación del formulario usa una clave de operación. Reintentar la misma operación no duplica avisos; reutilizarla con otro contenido se rechaza.
- Los nuevos avisos vinculan sus notificaciones al original: se muestran entregas internas y marcas de lectura. Leído significa una acción del usuario, no comprensión ni recepción de un correo.
- Los avisos antiguos sin vínculo se muestran como históricos, sin inventar métricas de entrega o lectura.
- Buscar y filtrar por lectura; marcar uno o todos como leídos afecta únicamente la cuenta autenticada. La primera fecha de lectura se conserva.

### Prueba rápida

Como docente: Nuevo aviso → elegir sección → escribir título/mensaje → Revisar destinatarios → Confirmar publicación. Como estudiante de esa sección: revisar Recibidos y marcar Leído. Volver como docente a Publicados para consultar el conteo. Probar también Tutores de una sección con cuentas vinculadas.

## Control institucional

Tres áreas separadas:

1. Indicadores: totales institucionales globales y resultados académicos filtrables por período.
2. Casos y seguimientos: filtros por texto, estado, categoría y prioridad; asignación a personal elegible, actuaciones y resolución con nota.
3. Admisiones: búsqueda, filtros, estados controlados, matrícula e historial.

### Qué significan los indicadores

- Proporción de estudiantes activos = estudiantes marcados activos / estudiantes del conjunto. **No equivale a permanencia o retención longitudinal entre períodos.**
- Sin período: el conjunto comprende toda la institución. Con período: estudiantes con selecciones académicas elegibles en ese período.
- Promedios y aprobación por carrera/asignatura usan resultados finales publicados. No se mezclan borradores ni selecciones retiradas/en espera.
- Sin datos es distinto de una calificación cero; se muestra el tamaño de la muestra.
- Asistencia = presencias computables / registros existentes, según la política de asistencia. No se infieren ausencias por días sin registro.
- Los casos abiertos pertenecen a estudiantes del conjunto filtrado; no significa que los casos se hayan originado en ese período.
- Las cuentas por cobrar y los totales superiores siguen siendo institucionales/globales.

### Seguimientos

Solo se asignan casos abiertos a administradores o docentes con acceso al estudiante. Las actuaciones requieren contenido; resolver exige una explicación. Reabrir conserva en el historial la resolución anterior. Las acciones repetidas de resolver/reabrir se rechazan cuando el estado no corresponde.

Revisar alertas automáticas analiza globalmente estudiantes activos: resultados finales reprobados según el criterio de cada selección, asistencia registrada inferior al 80 % y deuda pendiente. No duplica casos abiertos de la misma categoría ni resuelve automáticamente casos anteriores; el personal debe documentar su atención.

### Admisiones

Flujo: Recibida → En revisión → Aceptada → Crear estudiante. Se puede rechazar y devolver a revisión, pero no seleccionar Matriculada manualmente.

La conversión solo se permite desde Aceptada y guarda estudiante, matrícula y estado de la solicitud en una única transacción. Si falla, no queda un estudiante parcial ni se consume el número. Un reintento de una conversión nueva ya completada devuelve el mismo estudiante.

Las solicitudes matriculadas antiguas que no guardaban student_id se conservan y requieren revisión manual; no se vinculan por coincidencia de nombre o correo. El historial comienza con esta mejora.

## Configuración

El centro se agrupa en reglas académicas, seguridad/accesos y datos/supervisión. Permisos por rol ya no está mezclado con indicadores.

### Reglas institucionales

Revisar impacto, indicar motivo y confirmar. Se detecta una edición basada en una revisión desactualizada. Hay historial por campo y protección de recarga con cambios sin guardar; cambiar de rol con cambios pendientes requiere confirmación.

La nota aprobatoria se fija por selección académica. La migración congela para las selecciones existentes el criterio que usaba el sistema en ese momento; no reconstruye políticas históricas desconocidas. Las selecciones nuevas toman la configuración vigente. Cambiar la nota no reclasifica las anteriores.

Si existen filas heredadas nuevas sin criterio fijado (por ejemplo, cargadas por un script directo), una actualización institucional fija su valor anterior antes de cambiarlo. Cambiar créditos afecta validaciones de nuevas selecciones, sin retirar materias existentes. Cambiar prefijo/dígitos no renumera estudiantes; la matrícula automática evita colisiones y conserva la secuencia.

### Permisos y usuarios

La interfaz muestra concesiones/retiros, exige motivo y confirma su aplicación al rol. La comprobación de permisos permanece en el backend; ocultar un botón no concede ni retira autorización.

Se evita retirar desde la misma sesión permisos esenciales ya asignados de gestión de acceso, academia o reportes, y dejar sin usuarios gestores de acceso. También se impide eliminar la propia cuenta administrativa o cambiar su propio rol desde esa sesión.

Los cambios registran autor/fecha/motivo. El registro general de auditoría conserva hasta 500 caracteres por detalle; la configuración registra una entrada por campo modificado. No se fabrican registros para cambios previos.

### Períodos

- Validación de inicio/fin, orden de selección, retiro dentro del período y plazo de calificación no anterior al fin.
- Número dentro del año compatible con tipo: anual 1, semestre 1–2, cuatrimestre 1–3, trimestre 1–4, bimestre 1–6.
- No se renombra un período usado por secciones, selecciones o carritos.
- Solo se elimina un período de planificación, no vigente y sin uso.
- Se edita un período cerrado únicamente después de reabrirlo.

Antes de cerrar se muestran impedimentos. Para secciones con estudiantes, se requieren evaluaciones cerradas que sumen 100 % y resultados finales publicados para todos los estudiantes elegibles. También se detectan selecciones vinculadas a secciones de otro período. Una sección cancelada con estudiantes no puede pasar silenciosamente el cierre.

Al cerrar: se conserva una instantánea de los estados que se cambian; se cierran secciones no canceladas y las selecciones activas quedan completed o failed según su resultado. No se inventan notas.

Al reabrir: se restauran únicamente los estados modificados por ese cierre, no las secciones que ya estaban cerradas. El período pasa a vigente y activo; los demás dejan de estar vigentes. Las evaluaciones siguen cerradas y requieren su reapertura individual autorizada.

Cierres antiguos sin instantánea: la interfaz advierte que secciones/selecciones necesitan revisión manual. No se adivinan sus estados previos.

## Instalación y verificación

Respaldar SQLite con `python -B -m scripts.backup_database`, ejecutar `python -B -m alembic upgrade head` y reiniciar backend/frontend. La migración 20261014_0032 conserva las columnas y los registros anteriores, y añade vínculos/criterios/instantáneas/controles nuevos.

La protección de cambios sin guardar cubre recarga/cierre de pestaña y cambio de rol en el editor de permisos; no hay un bloqueo global de toda navegación interna.

Las pruebas cubren destinatarios, lectura privada y publicación idempotente, tutores, admisiones con rollback/reintento, criterio aprobatorio conservado, edición desactualizada, permisos esenciales, cierre con notas faltantes, restauración selectiva y ausencia de muestras académicas.
