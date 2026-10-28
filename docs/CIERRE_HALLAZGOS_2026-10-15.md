# Cierre de hallazgos — 15 de octubre de 2026

## Alcance

Corrección de los siete hallazgos F01–F07 del informe del 14 de octubre y sus siete observaciones adicionales de experiencia/calidad. P1, P2 y P3 son niveles de prioridad, no módulos adicionales. El informe original se conserva como evidencia histórica, no como descripción del estado corregido.

No se hizo commit, push ni despliegue. No se añadieron pagos externos ni integraciones bancarias reales. No se borraron estudiantes, notas, selecciones ni asistencias.

## Hallazgos funcionales

| Hallazgo | Corrección | Comprobación |
|---|---|---|
| F01 / P1 — escrituras docentes fuera de ámbito | `academic.manage` queda reservado a administración institucional, incluso si un rol docente histórico conserva el permiso. Los perfiles docente, estudiante y tutor no administran oferta, carreras ni matrícula. Los docentes mantienen consultas propias, reuniones propias, tareas, notas y asistencia. Admisiones también distingue gestión institucional de la operación docente. | Regresiones negativas sin efectos secundarios, pruebas positivas existentes y navegación real de los cuatro perfiles. |
| F02 / P1 — notas ajenas en historial | Historial de notas, horario, perfil académico y asistencia del docente filtran por sus secciones antes de paginar/calcular. Los documentos longitudinales, créditos, graduación e historial de carrera requieren administración o el propio estudiante. El expediente docente muestra solo sus asignaturas y no solicita créditos globales. | Comparación de IDs de notas y secciones; rechazo de expediente/PDF global al docente; acceso administrativo y del estudiante conservado. |
| F03 / P1 — último cupo simultáneo | Bloqueo de escritura respaldado por la base antes de leer requisitos/carga/cupos; creación del control de bloqueo sin carrera de inicialización en SQLite/PostgreSQL. Revalidación sobre datos actualizados. Reducciones administrativas de capacidad no pueden dejar estudiantes confirmados por encima del cupo. | Solicitudes concurrentes en conexiones SQLite independientes, repetidas; guion original con ocho escenarios de carrera. |
| F04 / P1 — retiro repetido | Se distingue una transición real desde `enrolled`; retiro y promoción usan un único commit. Reintentos no liberan otra plaza. El retiro personal es repetible; eliminación de una selección sin notas libera una sola plaza. La identidad académica no se cambia mediante PATCH. | Reintentos, eliminación repetida, aforo final y rollback inyectado entre retiro/promoción. |
| F05 / P1 — promoción con bloqueo | Se reutilizan actividad, bloqueos, requisitos/correquisitos, créditos, período y choque de horario. Se usan reuniones reales cuando existen, con respaldo del horario base para secciones antiguas. Se vuelve a contar capacidad antes de cada promoción. | Bloqueos financiero/académico, inactividad, fin de registro, prerrequisito, carga y horarios. |
| F06 / P1 — período inexistente | Selecciones requieren período existente, abierto para registro y coherente con la sección. El repositorio interno también valida el período. Nuevas/actualizadas secciones con período explícito deben referenciar uno existente; una sección con historial no cambia de período. | Período inexistente o diferente rechazado sin escritura; prueba por API y repositorio. |
| F07 / P2 — datos ficticios sobrecargados | El cargador genera secciones/aulas de 40 cupos y valida su aforo antes del commit. Se repararon además los datos ficticios de la base habitual con autorización expresa, respaldo y control de conservación. | Base nueva sin sobrecupo, reparación idempotente probada y base habitual sin las nueve discrepancias. |

### Política de lista de espera

Un candidato no elegible permanece en espera con su posición; no se elimina ni se le concede plaza. Se puede continuar con el siguiente candidato elegible. Al liberarse una plaza se repite la validación. Antes de aceptar un nuevo solicitante también se consideran los candidatos previos que hayan recuperado elegibilidad. Reintentar el retiro de alguien ya retirado no inicia otra promoción.

La carga máxima considera asignaturas confirmadas y en espera como carga comprometida. Una posición numérica puede conservar huecos históricos; no significa promesa de cupo. El período de secciones antiguas que está vacío se conserva explícitamente por compatibilidad: esto no permite seleccionar en períodos inexistentes y no reescribe expedientes previos.

## Observaciones de interfaz y calidad

| Prioridad | Observación original | Estado corregido |
|---|---|---|
| P2 | Admisión nueva solo por API | Control institucional → Admisiones → Nueva solicitud. Formulario con programa activo, contacto, documentos y observaciones; errores conservan el borrador y permiten reintentar. Se mantiene el ciclo posterior de revisión/aceptación/conversión. |
| P2 | «Lista de espera» junto a «Confirmada» | El catálogo distingue «Tu plaza está reservada» del aforo disponible para nuevos solicitantes. No hereda el estado personal de otra sección de la misma asignatura. Se muestran errores parciales de confirmación de forma persistente. |
| P2 | E2E de perfiles solo simulado | Nueva aceptación de navegador sin interceptar API: backend real, 32 migraciones, datos nuevos, cuatro perfiles, admisiones y carrito. Los tests simulados originales se conservan para UI. CI ejecuta ambas modalidades. |
| P2 | Ruff no pasaba | Imports y formato corregidos. CI usa pytest para no omitir las regresiones nuevas. |
| P3 | Categorías/prioridades en inglés y «Inscripciones» | Portal familiar traduce categorías, prioridades y modalidades. Indicadores y expediente usan selección/asignaturas; se conserva la ruta interna `/enrollments` por compatibilidad. |
| P3 | Controles repetidos por homónimos | Matrícula en etiquetas de asistencia y notas; código/identificador en acciones de directorios; número de solicitud en admisiones. Regresión con dos estudiantes de nombre idéntico. |
| P3 | «Abrir sección» conducía a asistencia | Acciones del directorio, carrera, asignatura y expediente anuncian «Ver asistencia». La navegación docente de consulta no depende del permiso administrativo eliminado. |

La confirmación del carrito que no pudo acreditarse en la auditoría original ahora usa un modal accesible y se verificó con selección real desde navegador, sin diálogo nativo bloqueante.

## Reparación autorizada de la base habitual

El usuario autorizó conservar los 40 estudiantes por sección y ampliar los cupos ficticios. Se aplicó únicamente el caso conocido de Instituto Técnico Horizonte:

- Nueve secciones: DS-101-A, DS-102-A, DS-201-A, AC-101-A, AC-102-A, AC-201-A, MD-101-A, MD-102-A y MD-201-A: capacidad de 30 a 40.
- Cuatro aulas utilizadas: A-101, A-202, B-103 y LAB-1: de 32 a 40.
- Conservados: **121 estudiantes, 360 selecciones, 720 notas y 2,160 asistencias**. El estudiante adicional respecto del seed de 120 ya existía antes de la reparación.
- Se añadieron nueve entradas `demo.capacity.repaired` al registro de auditoría.
- Respaldo SQLite consistente: `backups/capacity-before-4d99d3f839964028a0e18bd3fa81733e.db`.
- Repetir la comprobación devuelve cero discrepancias y no vuelve a modificar datos.

La reparación no atribuye capacidad física a una institución real: solo corrige este escenario ficticio autorizado. La herramienta `scripts/repair_demo_capacity.py` exige ruta explícita, por defecto solo muestra el plan, rechaza otros patrones de datos y requiere `--apply` para escribir. El respaldo contiene datos locales: no versionarlo ni copiarlo sobre una instalación diferente.

## Verificación y reproducción

| Control final | Resultado |
|---|---|
| Backend, con regresiones nuevas | 71 pruebas aprobadas |
| Cobertura de líneas del backend | 88% (no es porcentaje de funcionalidad completa) |
| Frontend | 38 pruebas aprobadas, 16 archivos |
| Navegador con backend real | 6 recorridos aprobados; cuatro perfiles, admisiones y carrito |
| Navegador, suite original de UI | 5 pruebas aprobadas |
| Ruff, tipos, lint y build | Correctos; avisos no bloqueantes de bundle/dependencia conservados |
| Base habitual y respaldo | Integridad `ok`; cero infracciones de claves foráneas |

La repetición final de los tres guiones originales obtuvo **296 comprobaciones conformes y cero no conformes** (232 + 32 + 32). El aumento frente a 275 se debe a completar las ocho rondas concurrentes sin detenerse en el primer sobrecupo. Evidencia final: `backups/acceptance-ec33e221a6714d0f94cd069c4240ab38/verification-summary.json`. También se conserva la primera repetición corregida en `backups/acceptance-442553cddd5a4384bf39db81c2c3988d/verification-summary.json`.

Durante la repetición se corrigieron dos requisitos del entorno del guion, sin debilitar el producto: el día de clase se calcula para la fecha real en lugar de quedar fijo en miércoles, y el servidor de pruebas configura instrucciones bancarias expresamente ficticias. Una cuenta sin instrucciones sigue rechazando transferencias correctamente.

Comandos desde la raíz:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m ruff check app tests main.py
.\.venv\Scripts\python.exe -B -m ruff format --check app tests main.py
.\.venv\Scripts\python.exe -B -m scripts.verify_audit_fixes
```

Desde `frontend`:

```powershell
npm run typecheck
npm run lint
npm test -- --maxWorkers=2 --no-file-parallelism
npm run build
npm run e2e:acceptance
```

`verify_audit_fixes` crea otra base bajo `backups/acceptance-<uuid>`, ejecuta migraciones y los tres guiones originales en `127.0.0.3:8013`, guarda resultados JSON y detiene solo su propio backend. Rechaza un puerto ya ocupado. La aceptación de navegador usa `127.0.0.3:8012` y `:5176`, no reutiliza servidores y tampoco toca `school.db`. En Windows utiliza `.venv`; en CI utiliza `python`.

Las evidencias, respaldos, dependencias y builds quedan fuera de Git. No se necesita una migración nueva para estas correcciones. Reiniciar el backend y refrescar el frontend carga el código nuevo; no regenerar datos para aplicar esta entrega.

## Límites que siguen siendo límites, no hallazgos cerrados artificialmente

Esta entrega no certifica carga universitaria masiva, cumplimiento legal/fiscal, accesibilidad formal, auditoría externa de seguridad ni integración bancaria productiva. Los PDFs conservan las pruebas existentes, no una certificación oficial. La compilación puede advertir sobre tamaño del bundle y comentarios de una dependencia; no se oculta ese aviso ni se lo confunde con un fallo funcional.
