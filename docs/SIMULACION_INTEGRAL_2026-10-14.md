# Simulación institucional integral — 14 de octubre de 2026

## Dictamen

Nexo tiene un recorrido académico y financiero interno funcional, pero **no supera todavía una aceptación institucional exigente**. Los bloqueantes están principalmente en autorización por ámbito y consistencia de la selección académica. Añadir más módulos antes de resolverlos aumentaría el riesgo y la complejidad.

La evaluación no certifica cumplimiento normativo, seguridad exhaustiva ni capacidad para una universidad de gran escala. «Integral» describe el recorrido transversal de los módulos disponibles, no todas las combinaciones imaginables ni una certificación de calidad.

## Entorno y conservación

- Repositorio comprobado: `C:\repos112\p_pro`, remoto `https://github.com/RennyPD/p_pro.git`, rama `master`.
- Se conservaron los cambios locales preexistentes. No se hizo commit ni push.
- Base independiente: `backups/institutional-audit-20261014/audit.db`.
- Backend real de auditoría: `http://127.0.0.2:8001`; frontend real: `http://127.0.0.2:5175`. La dirección distinta separó también las cookies de la aplicación habitual.
- Ninguna escritura de los guiones ni del navegador se dirigió al backend habitual de `127.0.0.1:8000`. No se borró ni sustituyó `school.db`.
- Se ejecutaron las 32 migraciones desde una base nueva hasta `20261014_0032` y se cargó el escenario institucional ficticio.
- Base inicial de demostración: 120 estudiantes, 6 docentes, 12 tutores, 3 carreras, 15 asignaturas, 15 secciones, 360 selecciones, 720 notas y 2,160 asistencias. Las simulaciones añadieron personas y programas ficticios separados.
- Los importes, comprobantes, cuentas y avisos fueron ficticios. No hubo pagos, mensajes externos ni conexiones bancarias reales.

## Resultados medidos

| Verificación | Resultado |
|---|---|
| Suite existente de backend | 53 pruebas aprobadas |
| Suite existente de frontend | 33 pruebas aprobadas |
| Tipos, lint y compilación del frontend | Correctos; advertencia no bloqueante de tamaño de bundle |
| Guion institucional contra backend real | 206 comprobaciones conformes, 5 no conformes |
| Reproducción de permisos y reintentos | 28 conformes, 4 no conformes |
| Graduación, equivalencias y documentos | 31 conformes, 1 no conforme |
| Total de las últimas tres ejecuciones API | **275 comprobaciones: 265 conformes y 10 no conformes** |
| Integridad física de SQLite / claves foráneas | `ok` / cero infracciones |
| Ruff del backend | No supera el control: 5 incidencias de orden de imports; 3 archivos requieren formato |

Las 10 comprobaciones no conformes se agrupan en **7 hallazgos funcionales o de datos**, porque varios controles reproducen el mismo defecto. Estos números no son un porcentaje de funcionalidades completas ni cobertura de código. Las pruebas existentes siguen pasando pese a los defectos nuevos, por lo que su cobertura de casos excepcionales debe ampliarse.

Las primeras ejecuciones contenían expectativas equivocadas del guion: permisos de administración de avisos para estudiantes/tutores, códigos 422 frente a 409, una consulta de impacto sin el parámetro `active` y una ruta PDF incorrecta. Se corrigió únicamente el guion y se repitió el recorrido con nuevas entidades. También se corrigió un nombre de carrera reutilizado en el guion, correctamente rechazado por unicidad. Las salidas iniciales se conservaron como `initial-*.json` y `harness-retry-conflict.json`; **no se cuentan como fallos del producto**.

## Recorridos que funcionaron

### Administración

Creación de carrera, asignaturas, pensum y oferta; alta de solicitudes, revisión, aceptación y conversión a estudiante; matrícula automática; provisión de acceso y reintento de conversión sin duplicados. Se comprobó cierre con resultados publicados, bloqueo de cambios académicos tras el cierre, reapertura y trazabilidad. Los indicadores pudieron mostrar resultados reales del programa creado para la prueba.

### Docencia y estudiante

El estudiante seleccionó una sección, se rechazó una selección duplicada y un prerrequisito no aprobado. Un segundo estudiante entró en espera y fue promovido tras liberar la plaza en el caso secuencial normal. Un bloqueo académico impidió una selección directa.

El docente creó una tarea calificable, recibió la entrega del estudiante activo y calificó 40/50. La transferencia creó una nota borrador de 80/100; repetirla no duplicó ni sobrescribió notas. El estudiante no pudo consultar el borrador. Publicar y cerrar produjo un resultado definitivo de 80, y el cierre prematuro y las modificaciones posteriores fueron rechazados.

Se guardó asistencia explícita, se rechazó una justificación sin respaldo textual y se bloquearon escrituras tras cerrar el período. Posteriormente se verificó que un cero publicado es válido y que su corrección a 90 conserva valor anterior, autor y motivo.

### Graduación y equivalencias

El estudiante no resultó elegible al tener todavía una asignatura obligatoria pendiente. Tras completarla, el sistema reconoció los créditos y pasó a elegible. Una equivalencia añadió créditos reconocidos con origen explícito y sin notas numéricas inventadas; su impacto, desactivación e historial respondieron correctamente. Se descargaron expediente, constancia y boleta PDF por sus endpoints reales; no se realizó una validación visual exhaustiva de esos PDF.

### Finanzas y comunicaciones

Cargo ficticio de RD$1,000.01, efectivo de RD$200.01 y transferencia aprobada de RD$100.00: balance de **RD$700.00**. Reintentar el efectivo no duplicó el pago; se rechazaron decimales excesivos, sobrepago y aprobación por el propio estudiante. Un estudiante ajeno no descargó el comprobante. El simulador no cambió el balance y se creó un plan mensual sin duplicar deuda.

El aviso de sección requirió revisión de audiencia, llegó una sola vez pese al reintento y el docente no pudo preparar un envío global. Estudiantes y tutores quedaron fuera de los endpoints de gestión de avisos, pero pudieron consultar sus notificaciones.

### Navegador con backend real: los cuatro perfiles

La habilidad `computer-use` se utilizó para revisar la interfaz real; no se sustituyó la API con respuestas simuladas.

- **Administración:** inicio, indicadores y admisiones. Se observaron los aspirantes y estados creados por el guion.
- **Docente:** navegación propia sin menú institucional; apertura de sección, guardado de asistencia para `ITH-2026-00001`, creación y publicación de una tarea de práctica, revisión de la entrega y devolución de 88/100.
- **Estudiante:** navegación propia, notas y catálogo; entrega de la tarea nueva; comprobación posterior de **88/100 y la devolución exacta del docente**.
- **Tutor:** seguimiento de Sofía García, matrícula `ITH-2026-00001`, con promedio, asistencia, saldo, horario y alerta; comunicaciones sin botón de publicación ni menú de administración. En API se rechazó acceder a estudiantes no vinculados.

Evidencia local adicional: `ui-evidence.json`, `entrega-verificada.jpg` y `tutor-verificado.jpg`, en la carpeta de auditoría.

## Hallazgos prioritarios y reproducción

### F01 — P1: las escrituras de gestión académica no respetan el ámbito del docente

**Comprobado:** `profesor.01` pudo retirar la selección 2, perteneciente a la sección de otro docente, con `PATCH /enrollments/2`. La lectura posterior confirmó el cambio efectivo de `enrolled` a `withdrawn`. También pudo cambiar la descripción de la sección 2 con `PATCH /sections/2`. Ambos devolvieron 200. Los cambios de prueba sobre estas entidades ficticias se restauraron mediante administración.

**Origen:** el rol de demostración tiene `academic.manage`; las rutas de escritura de selecciones y secciones solo comprueban ese permiso general, sin aplicar ámbito por recurso. Ocultar los botones en React no impide invocar la API.

**Fuentes:** `app/routers/enrollment_router.py`, `app/routers/section_router.py`, `app/auth.py` y asignación de permisos del cargador institucional.

**Criterio de corrección:** separar administración de oferta/matrícula de la consulta docente, definir explícitamente los poderes de cada permiso y comprobar el recurso en cada escritura. Probar que un docente conserva sus funciones legítimas y obtiene 403 sin efectos secundarios sobre recursos ajenos.

### F02 — P1: el historial individual permite leer notas de otras secciones

**Comprobado:** la lista general `/grades/` del docente limita las notas a sus secciones. Sin embargo, `GET /academic/students/1/grades` devolvió además las notas 3, 4, 5 y 6 de secciones de otros docentes, porque basta con que el estudiante pertenezca a alguna sección propia.

**Origen:** `student_grade_history` valida acceso al estudiante, pero no restringe el conjunto de notas a las secciones del docente (`app/routers/academic_router.py`, función desde la línea 436).

**Criterio de corrección:** aplicar una política consistente en historial, expediente, exportaciones y resúmenes. Si la institución desea acceso longitudinal para determinados docentes/coordinadores, debe ser una concesión explícita, no un efecto accidental del acceso a una sola sección.

### F03 — P1: dos selecciones simultáneas pueden exceder el último cupo

**Comprobado en ambas ejecuciones:** se creó una sección nueva con capacidad 1 y un período válido. Dos peticiones simultáneas de selección de estudiantes diferentes devolvieron 200 con estado `enrolled`: **dos plazas confirmadas para un cupo**.

**Origen:** el servicio calcula disponibilidad antes del bloqueo de escritura; el bloqueo del repositorio llega después de decidir el estado (`app/services/enrollment_service.py` y `app/repositories/enrollment_repository.py`).

**Criterio de corrección:** validar y escribir disponibilidad, duplicados, créditos y conflictos dentro de una operación serializada, con revalidación tras obtener el bloqueo. El segundo estudiante debe quedar en espera o recibir un conflicto controlado; nunca confirmar otra plaza.

### F04 — P1: reintentar un retiro promueve a un segundo estudiante indebidamente

**Comprobado:** sección de capacidad 1, estudiante A confirmado y B/C en espera. Primer retiro de A: se promueve B. Repetir el mismo `PATCH state=withdrawn` de A vuelve a ejecutar la promoción y también confirma a C. Resultado: **dos confirmados para capacidad 1 sin concurrencia**.

**Origen:** el servicio ejecuta la promoción cada vez que el estado resultante es `withdrawn`, sin exigir una transición real desde una plaza ocupada ni recontar cupos.

**Criterio de corrección:** retiro idempotente, promoción solo si realmente se libera una plaza y verificación atómica de capacidad.

### F05 — P1: la promoción automática ignora un bloqueo vigente

**Comprobado:** B entró en espera, luego administración activó su bloqueo financiero. Al retirarse A, B pasó a `enrolled` de todos modos.

**Origen:** la promoción asigna el estado directamente sin repetir las validaciones de elegibilidad (`app/services/enrollment_service.py`, bloque de `next_waiting`).

**Criterio de corrección:** revalidar actividad, bloqueos, créditos, requisitos, período y choques de horario antes de promover; documentar qué ocurre con candidatos que dejan de ser elegibles.

### F06 — P1: se puede crear una selección con un período inexistente

**Comprobado:** `POST /enrollments/` con un estudiante nuevo, una sección válida y `period=NONEXISTENT-AUDIT` devolvió 200 y creó la selección.

**Origen:** si la búsqueda del período no encuentra nada, el servicio omite sus validaciones y continúa. El período de la selección sigue siendo texto sin relación obligatoria con el catálogo.

**Criterio de corrección:** exigir período válido y coherente con la sección en creación y actualizaciones, y proteger también escrituras internas. No reescribir datos históricos sin una estrategia de conservación explícita.

### F07 — P2: el cargador institucional produce nueve secciones sobrecargadas

**Comprobado en la base recién creada, antes de atribuirlo a las carreras de prueba:** nueve secciones de demostración tienen **40 estudiantes confirmados y capacidad 30**: DS-101-A, DS-102-A, DS-201-A, AC-101-A, AC-102-A, AC-201-A, MD-101-A, MD-102-A y MD-201-A.

**Origen:** el cargador crea selecciones directamente, sin pasar por las validaciones de selección. Fuentes: `scripts/seed_institution.py`, capacidad en torno a la línea 452 y creación de selecciones en torno a la 532.

**Criterio de corrección:** el escenario de prueba debe cumplir las reglas o identificar explícitamente los datos deliberadamente inválidos. Una institución ficticia grande no equivale a una institución ficticia coherente.

## Vacíos de experiencia y controles de calidad

| Prioridad | Observación | Consecuencia / siguiente criterio |
|---|---|---|
| P2 | Admisiones permite revisar y convertir solicitudes existentes, pero no tiene acción para registrar una nueva desde esa pantalla. | El ciclo de admisión probado necesitó la API; falta cerrar el recorrido de usuario sin herramientas técnicas. |
| P2 | El catálogo muestra «Lista de espera» por ausencia de cupos y «Confirmada» en la misma tarjeta de un estudiante ya inscrito. | Separar disponibilidad de la sección del estado personal; no sugerir que el alumno perdió una plaza confirmada. |
| P2 | La suite de navegador existente de perfiles intercepta todas las peticiones y devuelve respuestas simuladas. | Añadir aceptación contra backend y migraciones reales; las pruebas de menú no acreditan aislamiento ni consistencia transaccional. |
| P2 | Ruff no supera imports y formato del backend actual. | Resolver el control de calidad antes de declarar una entrega consolidada, sin confundir formato con un defecto funcional. |
| P3 | El portal familiar expone categorías/prioridades como `academic` y `high`; persisten textos como «Inscripciones» en indicadores. | Unificar traducciones y vocabulario de negocio. |
| P3 | Personas con el mismo nombre producen controles accesibles con el mismo nombre. | Incorporar matrícula a las etiquetas accesibles; se pudo desambiguar visualmente por matrícula. |
| P3 | La acción «Abrir sección» lleva al pase de lista. | Hacer explícito el destino o aportar una cabecera de navegación de sección. No impidió registrar asistencia. |

## Lo no acreditado y límites

- La confirmación del carrito en navegador abrió una interacción que bloqueó el control automatizado. `getJsDialog` no expuso un diálogo; se recuperó cerrando únicamente la pestaña de auditoría y se continuó en otra. **No se presenta como fallo demostrado de Nexo.** La selección individual y sus restricciones sí se ejercitaron contra la API real; la confirmación visual del carrito queda para revisión manual.
- No se ejecutó una prueba de carga de miles de usuarios ni se certificó rendimiento para una universidad grande. La prueba de dos solicitudes simultáneas es un ensayo de consistencia, no un benchmark de capacidad.
- No se agotaron todos los cruces de permisos, cambios de carrera, correquisitos, anulaciones y fallos de red. Algunos tienen pruebas existentes, pero no se les atribuye una nueva aceptación exhaustiva por esa sola razón.
- No se realizaron cobros reales, integración bancaria, validación fiscal, auditoría externa de seguridad, evaluación legal ni revisión formal de accesibilidad.
- Los documentos PDF se comprobaron como respuestas descargables, no como certificaciones oficiales ni con validación visual exhaustiva.
- Los cambios preexistentes y las correcciones de la plataforma no se mezclaron con el diagnóstico: en esta tarea solo se añadieron guiones y evidencias de auditoría.

## Orden recomendado de trabajo

1. Resolver F01/F02: permisos y ámbito en todas las lecturas/escrituras relacionadas, con regresiones negativas por los cuatro perfiles.
2. Resolver F03/F04/F05: transacción única de selección, retiro y promoción; reintentos y concurrencia comprobados.
3. Resolver F06 y validar coherencia de período, sección y estudiante en rutas alternativas de escritura.
4. Reparar el cargador institucional y volver a generar **otra base de pruebas**, nunca la base habitual sin autorización.
5. Cerrar admisiones desde interfaz y aclarar estados del catálogo, vocabulario y etiquetas accesibles.
6. Convertir estas reproducciones en pruebas automatizadas mantenibles, corregir el control de calidad y repetir la aceptación.

## Evidencia y reproducción

Carpeta local: `C:\repos112\p_pro\backups\institutional-audit-20261014`.

- `api-evidence.json`: recorrido institucional definitivo de esta evaluación, ejecución `AUD-172801`.
- `api-followup.json`: cambios efectivos fuera de ámbito y retiro repetido, ejecución `AUD-172801-F`.
- `api-completion.json`: graduación, equivalencias, documentos e integridad, ejecución `AUD-172801-G`.
- `ui-evidence.json`, `entrega-verificada.jpg`, `tutor-verificado.jpg`: observaciones de navegador.
- `initial-*.json` y `harness-retry-conflict.json`: salidas iniciales conservadas para distinguir errores del guion de defectos del producto.

Guiones: `scripts/audit_institutional.py`, `scripts/audit_institutional_followup.py` y `scripts/audit_institutional_completion.py`. Solo están dirigidos a `127.0.0.2:8001` y la base separada de auditoría. No ejecutarlos contra otra instalación. Primero levantar el backend aislado con su `DATABASE_URL`, realizar migraciones y cargar datos ficticios en una base de pruebas nueva; después ejecutar los tres módulos en ese orden.

La base conserva los casos inválidos deliberadamente creados por las pruebas de rechazo, cupos y promoción. No debe reutilizarse como base institucional sana ni copiarse sobre `school.db`.
