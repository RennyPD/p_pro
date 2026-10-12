# Reglas de equivalencia

## Concepto y alcance

Una regla general es direccional: aprobar A reconoce B en una carrera y versión de pensum concretas. No es recíproca ni una asignación de profesor o sección. Se aplica a todos los estudiantes de esa carrera, utilizando la versión activa de la carrera. No crea matrículas, notas ni asistencia.

Este módulo no gestiona expedientes externos ni convalidaciones individuales con documentos y aprobación del comité. Esos procesos requieren un módulo separado; no se simulan mediante notas ficticias.

## Operación administrativa

1. Abrir Equivalencias y seleccionar carrera y una versión existente.
2. Buscar la asignatura de origen en el catálogo. El destino solo puede elegirse entre las materias del pensum y versión seleccionados.
3. Registrar observaciones y motivo; revisar el impacto y confirmar.
4. Usar Gestionar regla para editar observaciones o activar/desactivar con motivo. Los cambios de estado requieren revisar su impacto en la interfaz.
5. Consultar Historial para autor, fecha, acción y motivo. No hay eliminación de reglas; se conserva su identidad y trazabilidad. Para cambiar materias, carrera o versión se registra otra relación.

El historial comienza con esta mejora: no se inventan autores ni fechas para reglas existentes. El registro de auditoría conserva hasta 500 caracteres de detalle (el motivo precede a las observaciones); las observaciones actuales permiten hasta 2000 caracteres.

## Reglas académicas

- El origen debe estar aprobado conforme al motor de calificaciones publicadas y definitivas (o el modo legado compatible). Borradores, resultados provisionales y retiros no habilitan reconocimiento.
- Se usan únicamente reglas activas de la carrera y versión activa cuyo destino pertenece a ese pensum.
- Se admiten cadenas A → B → C, independientemente del orden de registro. Nuevas activaciones cíclicas y duplicados dentro de una misma carrera/versión se rechazan.
- Progreso, récord, graduación y requisitos de selección usan el mismo motor.
- Cada materia aporta créditos una sola vez; una aprobación directa tiene prioridad.
- El récord identifica el origen y los IDs de las reglas. El reconocimiento no tiene nota ni intento, no altera el promedio y no se atribuye a un período cursado ficticio. Sus créditos se muestran separados de los créditos obtenidos en períodos reales.
- Desactivar una regla recalcula los reconocimientos actuales y puede retirar créditos y habilitación de requisitos, incluidas cadenas dependientes. No borra calificaciones reales ni selecciones anteriores.
- La vista previa no escribe datos. Muestra totales y hasta 100 estudiantes afectados, incluido el cambio de créditos.

## Límites existentes del pensum

El sistema todavía asigna la versión desde la carrera, no individualmente por cohorte/estudiante. El pensum tiene unicidad carrera/asignatura, por lo que no soporta simultáneamente la misma materia en varios planes de esa carrera. Las reglas históricas se conservan y filtran por versión; esto no equivale a implementar planes paralelos completos.

## Verificación

Pruebas: consistencia entre progreso/récord/graduación, impacto sin escrituras, permisos, destinos inválidos, duplicados/ciclos, desactivación e historial, cadenas, filtrado de versiones, prerrequisitos/correquisitos, prioridad de aprobación directa y ausencia de notas nuevas.

La migración 20261012_0030 añade estado y autores opcionales, y amplía la unicidad de la regla para incluir versión. No elimina registros existentes. Antes de aplicarla en otra PC: respaldar SQLite con `python -B -m scripts.backup_database`, luego `python -B -m alembic upgrade head`; reiniciar el backend.
