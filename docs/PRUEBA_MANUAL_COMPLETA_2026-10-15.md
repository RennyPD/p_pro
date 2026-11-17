# Prueba manual completa de Nexo

Versión revisada contra el código y la base local el **15 de octubre de 2026**. Esta es una guía para que tú ejecutes la prueba; no es una afirmación de que cada combinación manual ya haya sido aprobada.

## Cómo utilizarla sin saltarte funciones

Haz los bloques en orden. Anota el resultado de cada caso: **aprobado, falló o no ejecutado por falta de preparación**. No marques aprobado un caso que no pudiste ejecutar.

- **[UI]**: se hace desde la interfaz normal.
- **[API]**: la función existe, pero se prueba mediante la documentación interactiva; no se presupone un botón inexistente.
- **[GLOBAL]**: afecta a más personas que el estudiante de prueba.
- **[ÚLTIMO]**: puede bloquear operaciones posteriores; no adelantarlo.

En cada incidencia guarda: código del caso, usuario, matrícula/sección, pasos, resultado esperado, resultado real y captura. Si utilizas API, agrega método, ruta y estado HTTP, sin incluir tokens ni contraseñas en la captura.

**Duración:** varias sesiones de prueba. No está diseñado para completarse en unos minutos. Primero revisa la institución existente; después utiliza el pequeño escenario QA para las operaciones de escritura.

### Índice de recorrido

1. [Preparación, accesos y uso de Swagger](#0-preparación-seguridad-y-credenciales).
2. [Reconocimiento con los cuatro perfiles](#1-primera-vuelta-conocer-lo-existente-con-los-cuatro-perfiles).
3. [Preparación del escenario QA](#2-crear-un-escenario-qa-pequeño-y-controlado).
4. [Selección, espera y horarios](#3-selección-académica-cupos-espera-y-restricciones).
5. [Docencia, asistencia, notas y tareas](#4-docencia-asistencia-evaluaciones-tareas-y-resultados).
6. [Agenda y comunicaciones](#5-agenda-y-comunicaciones).
7. [Finanzas](#6-finanzas-completas-con-números-comprobables).
8. [Equivalencias y carrera](#7-equivalencias-reconocimiento-y-versiones).
9. [Control institucional](#8-control-institucional-alertas-y-admisiones).
10. [Funciones adicionales de API](#9-funciones-disponibles-solo-por-api-o-sin-pantalla-completa).
11. [Configuración y seguridad](#10-configuración-accesos-y-seguridad).
12. [Cierre y reapertura académica](#11-cierres-y-reaperturas-académicas).
13. [Privacidad entre perfiles](#12-matriz-de-aislamiento-repetir-con-los-cuatro-perfiles).
14. [Revisión visual y errores](#13-revisión-visual-y-manejo-de-errores-en-todas-las-pantallas).
15. [Cierre del laboratorio e inventario final](#14-cierre-de-la-prueba-y-registro-de-resultados).

## 0. Preparación, seguridad y credenciales

### PRE-01 — Trabajar sobre una copia, no arriesgar la institución actual

1. Desde `C:\repos112\p_pro`, ejecuta:

   ```powershell
   .\.venv\Scripts\python.exe -B -m scripts.backup_database
   ```

2. Guarda la ruta exacta que devuelve. El comando crea una copia consistente de la SQLite configurada.
3. Recomendado: detén el backend, apunta temporalmente `DATABASE_URL` en el `.env` local a **esa copia** y reinicia el backend. Ejemplo orientativo, sustituyendo el nombre por el archivo realmente generado:

   ```dotenv
   DATABASE_URL=sqlite:///C:/repos112/p_pro/backups/school-FECHA-HORA.db
   ```

4. Conserva anotado el valor anterior para volver a la instalación habitual al terminar. El archivo elegido será ahora tu base de pruebas: conserva otro respaldo sin usar si quieres una restauración adicional.
5. Reinicia también el frontend si no tiene los últimos cambios y cierra las sesiones anteriores.
6. **No ejecutes `seed_institution` sobre tu base actual para seguir esta guía.** Ese cargador sustituye datos. La copia de la institución ya contiene el escenario necesario.

**Esperado:** puedes entrar a la copia con los accesos existentes. Cualquier cargo ficticio, cierre o cambio global de esta guía queda en esa copia.

### PRE-02 — Abrir aplicación y separar perfiles

1. Abre el frontend en su dirección local actual, normalmente `http://127.0.0.1:5173`.
2. Abre la API en `http://127.0.0.1:8000/docs`.
3. Usa perfiles independientes del navegador para administrador, docente, estudiante y tutor. Alternativamente cierra sesión y vuelve a entrar cada vez que cambies de actor.
4. No confíes en varias pestañas del mismo navegador como aislamiento completo: las cookies de renovación se comparten por origen.

| Perfil existente | Usuario | Contraseña del escenario ficticio | Referencia comprobada en la base |
|---|---|---|---|
| Administración | `admin.horizonte` | `NexoAdmin2026!` | Gestión institucional |
| Docente principal | `profesor.01` | `NexoDocente2026!` | Ana Rodríguez; docente 1 |
| Otro docente | `profesor.02` | `NexoDocente2026!` | Carlos Méndez; docente 2 |
| Estudiante | `estudiante.001` | `NexoEstudiante2026!` | Sofía García; ITH-2026-00001; estudiante 1 |
| Otro estudiante | `estudiante.004` | `NexoEstudiante2026!` | Sebastián Santos; ITH-2026-00004; estudiante 4 |
| Tutor | `tutor.01` | `NexoTutor2026!` | Vinculado a Sofía; tutor 1 |
| Otro tutor | `tutor.02` | `NexoTutor2026!` | Vinculado a Mateo Martínez; estudiante 2 |

Las cuentas existen. Las claves son las definidas por el cargador: si ya cambiaste alguna, utiliza su contraseña actual. No se verificaron mediante nuevos inicios de sesión para redactar este documento. No reutilices estas claves fuera de pruebas locales.

### PRE-03 — Registrar IDs sin confundirlos con matrículas

Durante la creación del escenario anota:

| Símbolo que usaremos | Qué debes anotar |
|---|---|
| `C_QA` | ` career_id` de la carrera QA |
| `P_QA` | `period_id` del período QA |
| `A`, `B`, `C` | `student_id` de Mariela, Diego y Camila |
| `MAT_A`, `MAT_B`, `MAT_C` | Sus matrículas visibles, no sus IDs |
| `FUND`, `PROY` | `subject_id` de las dos asignaturas principales |
| `SF`, `SP` | `section_id` de sus secciones |
| `EF_A` | `enrollment_id` de Mariela en Fundamentos |
| `G_QA` | `guardian_id` del tutor QA |

En JSON, reemplaza los símbolos por **números reales**. No envíes literalmente `C_QA`, `<ID>` ni matrículas donde el esquema pide un ID. La URL de detalle o las respuestas de consulta permiten obtener los identificadores.

### API-00 — Cómo probar una operación desde Swagger

1. En `/docs`, abre `POST /auth/login` → **Try it out**.
2. Introduce usuario y contraseña del actor indicado. Si tiene segundo factor activado, incluye su código actual.
3. Ejecuta y copia únicamente `access_token`.
4. En **Authorize**, pega el token en el control HTTP Bearer y autoriza. Si la UI añade el prefijo automáticamente, no escribas `Bearer` dos veces.
5. Ejecuta `GET /auth/me`: confirma usuario, `role_name` y vínculo personal antes de cualquier escritura.
6. Al cambiar de actor vuelve a autorizar con su token. Estar conectado en React no autoriza automáticamente Swagger.

Un 401 significa que falta autenticación o caducó; un 403 es rechazo de autorización; 404 es recurso inexistente/no disponible; 409 es conflicto de negocio; 422 suele ser validación. Un 500 **no** es un rechazo normal esperado.

## 1. Primera vuelta: conocer lo existente con los cuatro perfiles

### COM-01 — Inicio y cierre de sesión [UI, todos]

1. Entra una vez con cada perfil de PRE-02.
2. Comprueba nombre y rol en el lateral.
3. Administrador: identifica Vista general, personas, catálogos, finanzas, control y configuración.
4. Docente: identifica Mi jornada, Mis secciones, Mis estudiantes, Evaluaciones, Agenda y tareas, Calificaciones y Asistencia; no debe administrar carreras ni finanzas.
5. Estudiante: identifica Mi resumen, Elegir asignaturas, horario, tareas, notas, asistencia, progreso, graduación, expediente, cuenta y comunicaciones.
6. Tutor: identifica Seguimiento familiar, agenda/tareas, comunicaciones y Mi cuenta.
7. Cierra sesión y vuelve a entrar. Prueba una contraseña equivocada una sola vez y verifica un error comprensible. No hagas intentos masivos.

**Esperado:** cada actor tiene su propio espacio; la cuenta del estudiante no aparece como docente y el tutor no publica ni entrega trabajos.

### ADM-01 — Vista general [UI, administrador]

1. Entra como `admin.horizonte`.
2. Anota estudiantes, docentes, secciones y selecciones del período.
3. Lee el período mostrado y cualquier aviso de configuración.
4. Visita las listas correspondientes y contrasta qué cuenta cada indicador: estudiantes activos no significa total histórico; selecciones no significa personas únicas.

**Esperado:** cifras explicables y sin errores de carga. Una cifra de demostración no es un objetivo que debas alcanzar artificialmente.

### DOC-01 — Mi jornada y ámbito docente [UI, docente]

1. Entra como `profesor.01` y abre Mi jornada.
2. Abre Mis secciones; localiza `DS-101-A`, de Ana Rodríguez.
3. Abre Mis estudiantes y localiza a Sofía por `ITH-2026-00001`.
4. Revisa el expediente académico que muestra el docente: solo deben computar sus secciones, no el historial longitudinal completo de todos los profesores.
5. Repite como `profesor.02` y contrasta las secciones.

**Esperado:** el ámbito depende de la asignación docente. Compartir un estudiante con otro profesor no concede acceso a todas sus notas.

### EST-01 — Resumen personal [UI, estudiante]

1. Entra como `estudiante.001`.
2. Abre cada opción de su menú y anota qué contiene antes de modificar nada.
3. Distingue nota publicada, resultado provisional, resultado definitivo, crédito aprobado y saldo financiero.
4. No marques como error que una nota visible todavía no produzca créditos: puede faltar cierre del plan evaluativo.

### TUT-01 — Seguimiento familiar existente [UI, tutor]

1. Entra como `tutor.01`.
2. Confirma nombre de Sofía y matrícula `ITH-2026-00001`.
3. Revisa promedio, asistencia, balance, horario y alertas con categorías/prioridades legibles.
4. Como `tutor.02`, comprueba que se muestra Mateo y no Sofía.
5. Si una cuenta solo tiene un estudiante vinculado, no esperes un selector de varios hijos.

**Esperado:** consulta familiar, no acceso administrativo ni capacidad de cambiar notas o pagar por caja.

## 2. Crear un escenario QA pequeño y controlado

Usaremos una carrera de prueba con dos asignaturas principales, un profesor existente, tres estudiantes nuevos y un tutor nuevo. Así cada cierre evaluativo exige calificar a una sola persona, no a cuarenta.

Usa el sufijo `QA-20261015`. Si ya existe, cambia todo el sufijo por otro único; no reutilices accidentalmente una carrera de un intento previo.

### ADM-02 — Carrera profesional [UI, administrador]

1. Carreras → crear programa.
2. Registra código `QA-20261015`, nombre `Programa de Pruebas Institucionales`, título `Certificado de pruebas académicas`, nivel Técnico superior, organización Semestres, 2 períodos, 6 créditos requeridos y versión `QA-2026`.
3. Deja el estado **Activo**; la creación usa En diseño como valor inicial y un programa no activo podría no aparecer en admisiones.
4. Completa modalidad Presencial, facultad `Escuela QA`, departamento `Laboratorio institucional`, coordinación `Laura Prueba`, correo `qa.coordinacion@example.com` y sede `Campus ficticio`.
5. Completa perfiles de ingreso/egreso, campo profesional y requisitos. Texto ficticio: `Bachillerato concluido. Programa exclusivo de validación, sin validez académica real.`
6. Guarda y abre el programa. Revisa resumen, perfiles, pensum y oferta; prueba búsqueda y filtros de estado, nivel, modalidad y facultad en el catálogo.
7. Edita un dato, guarda, recarga y verifica persistencia.

**Esperado:** se conservan identidad, estructura y perfiles. No hay eliminación física en esta vista; archivar conserva historial. Anota `C_QA`.

### ADM-03 — Catálogo de asignaturas [UI, administrador]

1. Asignaturas → crea `QA-FUND-20261015`, nombre `Fundamentos de gestión institucional`.
2. Crea `QA-PROY-20261015`, nombre `Proyecto institucional aplicado`.
3. Crea una tercera asignatura temporal `QA-LIBRE-20261015`, sin vincularla a ninguna carrera.
4. Filtra por carrera QA: una asignatura no aparece en ese filtro hasta vincularla al pensum.
5. Abre el detalle de Fundamentos y revisa programas asociados y secciones.
6. Prueba editar el nombre de la asignatura libre y eliminar **solo esa asignatura libre**, antes de usarla. Debe desaparecer sin borrar programas.
7. Más adelante intenta eliminar Fundamentos cuando tenga relaciones: debe rechazarse para proteger el historial.

**Concepto:** la asignatura es compartida institucionalmente; la carrera decide créditos/requisitos y la sección concreta profesor, horario y cupo. Anota `FUND` y `PROY`.

### ADM-04 — Pensum, créditos y dependencias [UI, administrador]

1. Abre la carrera QA → Pensum → Agregar asignatura.
2. Agrega Fundamentos: versión `QA-2026`, período recomendado 1, 3 créditos, Obligatoria, sin prerrequisito ni correquisito.
3. Agrega Proyecto: misma versión, período 2, 3 créditos, Obligatoria, prerrequisito Fundamentos.
4. Comprueba total 6 y coincidencia con los créditos requeridos del programa.
5. Edita y vuelve a guardar un campo inocuo. Comprueba que cambiar el nombre de la asignatura no duplica la relación.
6. Intenta agregar la misma relación otra vez, seleccionar un período superior a la duración y hacer que una asignatura sea su propio requisito. Debe rechazarse.
7. Consulta también Configuración → Pensum académico: es otra entrada a las relaciones curriculares, no otro catálogo de asignaturas.

**Esperado:** se explica qué carrera/versión aporta cada crédito. Las pruebas de versiones y materias electivas se amplían en ADM-18, después de comprobar la graduación básica.

### ADM-05 — Docentes: ficha y carga [UI, administrador]

1. Abre Docentes → Ana Rodríguez. Revisa Resumen, Perfil profesional, Vinculación institucional, Carga y horario, Datos y contactos.
2. Usa filtros por departamento, estado y tipo de vinculación; busca por nombre y código.
3. Crea el docente adicional `Laura Prueba`, correo `qa.docente@example.com`, especialidad `Pruebas institucionales`, código `DOC-QA-20261015`, departamento `Escuela QA`, maestría ficticia, 5 años de experiencia y vinculación Por asignatura.
4. Completa contacto y emergencia, edita un dato y confirma persistencia. Puedes marcar temporalmente **este docente nuevo sin asignaciones** como inactivo y volver a activarlo; no cambies al profesor principal durante las actividades.
5. Después de crear secciones vuelve a la carga de Ana: contrasta cantidad de estudiantes, horas, períodos y modalidades. Las secciones cerradas/canceladas no cuentan igual que las operativas.

**Esperado:** dar de alta a una persona docente no crea automáticamente su usuario de acceso.

### ADM-06 — Período QA [UI, administrador, GLOBAL]

1. Anota que el período inicialmente vigente es `2026-2027`.
2. Configuración → Períodos académicos → crear `QA-2026-S2`.
3. Para una ejecución en octubre de 2026 usa: año académico `2026`, tipo Semestre, número dentro del año 2, inicio docencia `2026-10-01`, fin `2026-12-31`, selección `2026-10-01` a `2026-10-31`, retiro hasta `2026-12-01`, calificación hasta `2027-01-10`.
4. Etapa **Docencia activa**, casilla **Período vigente** marcada. Si haces la prueba en otra fecha, ajusta el calendario para que hoy esté dentro de selección y las asistencias estén dentro del período y no en el futuro.
5. Verifica que ahora QA es el vigente y que el otro dejó de serlo. Vigente es el período seleccionado por catálogo; etapa indica planificación, selección, docencia o cierre. Son conceptos distintos.
6. En un período temporal sin uso prueba fechas invertidas y número 3 para semestre: deben rechazarse. Cuatrimestre admite 1–3, trimestre 1–4, bimestre 1–6 y anual solo 1.
7. Crea un período temporal en planificación, no vigente y sin uso; edítalo y elimínalo. No lo confundas con QA, que necesitaremos después.

**Esperado:** cambiar vigencia altera el catálogo para toda la copia. No cierres ahora `2026-2027` ni el período QA. Anota `P_QA`.

### ADM-07 — Admisión de Mariela [UI, administrador]

1. Control institucional → Admisiones → Nueva solicitud.
2. Nombres `Mariela`, apellidos `Pérez QA`, correo `qa.mariela@example.com`, teléfono `809-555-0101`, programa QA.
3. Documentación: `Copia ficticia del bachillerato recibida`; observaciones: `Aspirante de validación`.
4. Guarda. Busca por nombre/correo y filtra Recibida.
5. Pasa a En revisión con motivo `Documentos ficticios revisados`.
6. Pasa a Aceptada con motivo `Cumple requisitos de prueba`.
7. Pulsa Crear estudiante. Abre su expediente y anota `A` y `MAT_A`. La solicitud debe quedar Matriculada, vinculada a esa persona.
8. Consulta Historial. No intentes seleccionar Matriculada directamente co mo si fuera otro estado manual.
9. Crea otra solicitud desechable, `Solicitud Rechazada QA`, con correo único. Revisa, rechaza con motivo y devuélvela a revisión; todavía no debe existir estudiante por solo aceptar/rechazar.

**Esperado:** admisión es un aspirante, no una selección de asignatura. Crear estudiante genera expediente/matrícula; no crea asignaturas elegidas, usuario ni tutor. Si necesitas comprobar el reintento de conversión, repite `POST /operations/admissions/{id}/enroll` por API: debe devolver el mismo estudiante, no otro nuevo.

### ADM-08 — Estudiantes: creación, datos y controles [UI, administrador]

1. Estudiantes → crea `Diego Núñez QA`, correo `qa.diego@example.com`, teléfono `809-555-0102`, dirección `Campus ficticio`, programa QA, activo y sin bloqueos. Deja matrícula vacía para generación automática. Anota `B` y `MAT_B`.
2. Completa para Mariela identificación ficticia `DEMO-QA-001`, nacionalidad, nacimiento, fecha de ingreso, procedencia y contacto de emergencia.
3. Abre cada pestaña: Resumen, Datos personales, Trayectoria académica y Familia y contactos.
4. Busca por matrícula, nombre, correo y documento. Prueba filtros de programa, activos/inactivos y controles académico/financiero. Limpia filtros.
5. Activa y desactiva por separado un bloqueo de Mariela; verifica que no se pierde el otro ni se cambia la carrera por un número.
6. Antes de seleccionar materias, deja a los tres estudiantes activos y sin bloqueos. Las pruebas de restricciones se hacen en EST-03/04.

**Esperado:** identidad y matrícula son legibles; la inactividad conserva expediente; un bloqueo no borra notas ni equivale a una sanción automática por saldo.

### ADM-09 — Importar/exportar estudiantes [UI, administrador]

1. Configuración → Importar y exportar → Descargar CSV. Ábrelo y confirma encabezados y matrículas. No vuelvas a importar todo el archivo exportado sin revisar duplicados.
2. Crea un CSV UTF-8 con el contenido siguiente. Sustituye `C_QA` por el número real de carrera:

   ```csv
   first_name,last_name,email,telephone,address,career_id,enrollment_number,active
   Camila,Rojas QA,qa.camila@example.com,809-555-0103,Campus ficticio,C_QA,,true
   Fila,Invalida QA,correo-invalido,809-555-0104,Campus ficticio,C_QA,,true
   ```

3. Selecciona el archivo e impórtalo. Espera una fila creada y otra observada; la carga admite resultado parcial.
4. Localiza Camila en Estudiantes y anota `C`, `MAT_C`.
5. Repite el mismo archivo: no debe duplicarse Camila; observa el aviso de filas que requieren revisión. Para el detalle técnico usa la respuesta de `POST /bulk/students/import`.
6. Vuelve a exportar y verifica que Camila aparece una sola vez.

### ADM-10 — Usuarios y vínculos [UI y API, administrador]

1. Configuración → Usuarios → crea `qa.mariela`, correo `qa.mariela.acceso@example.com`, clave ficticia `PruebaQA2026!`, rol `student`, estudiante vinculado Mariela; deja docente vacío.
2. Repite para `qa.diego`/Diego y `qa.camila`/Camila, con correos distintos y la misma clave de laboratorio.
3. Prueba entrar con cada una y verifica que se muestra su propia matrícula. No basta poner el rol student: el vínculo debe ser correcto.
4. Crea `qa.docente`, rol teacher, vinculado a Laura Prueba. Esta cuenta inicialmente no debe ver secciones ajenas.
5. Edita y consulta una cuenta QA. Si cambias la contraseña desde administración, usa una nueva válida y deja anotada la final; no esperes ver la contraseña almacenada.
6. Por API prueba crear un usuario con `student_id` y `teacher_id` a la vez: debe rechazarse. Comprueba que un usuario estudiantil no se use para acceder como docente por error de vinculación.
7. Para probar eliminación de usuarios, crea una cuenta **temporal sin trabajo propio** y elimínala. No borres los usuarios de esta guía ni el administrador actual.

**Accesos principales nuevos:** `qa.mariela`, `qa.diego`, `qa.camila`, `qa.docente`; contraseña de laboratorio `PruebaQA2026!`, salvo que la cambies.

### ADM-11 — Alta de tutor y vínculos familiares [API, administrador]

La pantalla Usuarios no tiene actualmente el campo de vínculo `guardian_id`; no intentes registrar al tutor como estudiante para compensarlo.

1. `POST /community/guardians`:

   ```json
   {"first_name":"Patricia","last_name":"Pérez QA","email":"qa.patricia@example.com","telephone":"809-555-0110","address":"Campus ficticio"}
   ```

2. Anota el `guardian_id` devuelto como `G_QA`.
3. `POST /community/guardian-links`, con IDs sustituidos:

   ```json
   {"student_id": A,"guardian_id": G_QA,"relationship":"madre","primary_contact":true,"emergency_contact":true,"authorized_pickup":true}
   ```

4. Consulta el ID del rol guardian en `GET /roles/`. Crea por `POST /users/`:

   ```json
   {"username":"qa.tutora","email":"qa.tutora.acceso@example.com","password":"PruebaQA2026!","role_id": ID_ROL_GUARDIAN,"guardian_id": G_QA,"student_id":null,"teacher_id":null}
   ```

5. Entra como `qa.tutora` y verifica Mariela.
6. Para probar varios hijos, añade un segundo vínculo a Diego y confirma selector y separación de resúmenes. No vincules Camila: servirá para probar privacidad.
7. Como administrador abre Familia y contactos de Mariela y verifica nombre/contacto/indicadores de Patricia.

**Esperado:** el tutor ve exclusivamente personas expresamente vinculadas. Crear una cuenta guardian sin vínculo familiar no concede alumnos automáticamente. No hay en la interfaz una gestión completa de altas/bajas de esos vínculos.

### ADM-12 — Secciones y oferta [UI con ajuste API, administrador]

1. Secciones → crea `QA-FUND-A-20261015`, asignatura Fundamentos, docente Ana Rodríguez, capacidad **1**, aula `Aula QA-01`, presencial, lunes y miércoles, 18:00–19:00.
2. Crea `QA-PROY-A-20261015`, Proyecto, Ana, capacidad 1, aula `Aula QA-01`, martes 19:00–20:00.
3. Anota `SF` y `SP`. El formulario actual de sección **no expone período, estado ni mínimo de cupo**. Asígnalos explícitamente por `PATCH /sections/{id}`:

   ```json
   {"period_name":"QA-2026-S2","status":"published","minimum_capacity":1}
   ```

4. Comprueba por consulta que ambos quedaron en QA. No asumas que el texto Aula crea una entidad del catálogo de aulas.
5. Prueba búsqueda, paginación, detalles de fila, edición y legibilidad de docente/asignatura/modalidad/horario. Ver asistencia abre pase de lista, no el editor del plan evaluativo.
6. Intenta inicio 20:00 y fin 19:00: debe rechazarse.
7. En una sección temporal sin alumnos prueba estados draft/published/active/cancelled mediante API y contrasta su disponibilidad en el catálogo. Bórrala antes de agregarle historial.
8. Después de seleccionar estudiantes intenta reducir capacidad por debajo de confirmados, cambiar el período o asignar un período inexistente: debe rechazarse.

**Esperado:** una sección tiene un profesor y una asignatura. La selección del alumno es el vínculo interno; no necesitas una pantalla llamada Inscripciones.

### ADM-13 — Aulas y reuniones de clase [API; administración y docente]

1. Como admin, `POST /scheduling/classrooms`: `{"name":"Aula QA-01","capacity":2,"location":"Campus ficticio","active":true}`. Anota su ID.
2. Consulta `GET /scheduling/classrooms`.
3. Crea por `POST /scheduling/meetings` una reunión para `SF`, lunes 18:00–19:00, con ese `classroom_id` y modalidad `in_person`. Repite miércoles. Para `SP`, martes 19:00–20:00.
4. Consulta `GET /scheduling/sections/{SF}/meetings`. Cuando existen reuniones, las validaciones de asistencia/choques las utilizan.
5. Intenta una reunión de otro grupo en la misma aula y hora: espera conflicto de aula; otro grupo del mismo profesor en otra aula y hora superpuesta: conflicto docente.
6. Prueba una sección con capacidad mayor que la del aula: debe rechazarse la reunión. Prueba virtual sin `virtual_url`: validación; con URL ficticia: válido.
7. Crea una reunión desechable sin choque y elimínala con `DELETE /scheduling/meetings/{id}`. No borres las reuniones del recorrido principal.
8. Con token de `profesor.01`, consulta/gestiona una reunión de su sección y comprueba rechazo en una sección de otro docente. Crear aulas queda en administración.

## 3. Selección académica: cupos, espera y restricciones

### EST-02 — Catálogo, carrito y confirmación [UI, estudiantes QA]

1. Entra como `qa.diego`. Abre Elegir asignaturas; verifica período QA, Fundamentos, Proyecto, profesor, sección, modalidad, aula, horario y créditos.
2. Añade Fundamentos al carrito. Comprueba cantidad/créditos. Quítala una vez y vuelve a añadirla para probar ambas acciones.
3. Antes de confirmar, ejecuta EST-03 sobre Diego y deja sus controles restaurados. Después confirma con el modal. **Esperado: Diego confirmado** y su plaza reservada.
4. Entra como `qa.mariela`, repite Fundamentos. **Esperado: Mariela en espera** porque el cupo es 1.
5. Repite como `qa.camila`. **Esperado: Camila también en espera**, detrás de Mariela.
6. Recarga: los estados deben persistir. Diego no debe aparecer como si hubiera perdido su plaza por estar lleno el grupo.
7. Intenta repetir una selección de la misma asignatura. La UI debe impedirlo o el backend rechazarlo sin duplicar plazas.

### EST-03 — Bloqueos e inactividad [UI, admin + estudiante]

1. Este caso se intercala en el paso 3 de EST-02, antes de que Diego confirme Fundamentos. Activa su bloqueo académico desde Estudiantes.
2. Como Diego, intenta confirmar Fundamentos, que todavía no seleccionó y no tiene prerrequisito. Debe rechazarse sin crear selección.
3. Retira el bloqueo y comprueba que no se alteró su condición financiera.
4. Prueba por separado inactividad y bloqueo financiero, restableciendo cada dato al finalizar.
5. No concluyas que una tarjeta visible significa elegibilidad: la validación definitiva se hace al confirmar.

**Esperado:** bloqueo restringe selección; no elimina cuenta ni resultados. Tener deuda no activa automáticamente la casilla de bloqueo.

### EST-04 — Promoción con bloqueo y retiro repetido [UI y comprobación API]

1. Estado inicial: Diego confirmado, Mariela y Camila en espera.
2. Como admin bloquea financieramente a Mariela.
3. Como Diego retira Fundamentos y confirma el modal.
4. Consulta como Mariela y Camila: Mariela debe seguir en espera; Camila debe ocupar el cupo, sin sobrecargarlo.
5. Repite el retiro de Diego por `POST /academic/catalog/sections/{SF}/withdraw`, con token de Diego. No debe promover a otra persona ni superar 1 confirmado.
6. Admin: retira el bloqueo de Mariela.
7. Como Camila retira la materia. Mariela debe pasar a confirmada.
8. Verifica por admin `GET /enrollments/`: en `SF` debe existir **una** selección `enrolled`, la de Mariela. Anota su `enrollment_id` como `EF_A`.
9. Diego/Camila retirados no deben entregar tareas ni recibir nuevos avisos de estudiantes activos de ese grupo.

**Esperado:** el retiro libera una plaza una vez. Un candidato bloqueado conserva su espera; la promoción revalida requisitos. En adelante el alumno principal es Mariela.

### EST-05 — Prerrequisitos, correquisitos, créditos y choque [UI/API]

1. Como Mariela intenta Proyecto **antes de aprobar definitivamente Fundamentos**. Debe rechazarse; un borrador o nota provisional no cumple el prerrequisito.
2. Para los restantes controles crea asignaturas/secciones QA auxiliares mediante ADM-03/04/12; no alteres carreras reales:
   - `QA-CHOQUE`: electiva de 1 crédito, misma franja de Fundamentos.
   - `QA-CARGA`: electiva de 25 créditos, si la configuración mantiene máximo 24.
   - `QA-LAB1` y `QA-LAB2`: electivas de 1 crédito; LAB2 exige LAB1 como correquisito; usa horarios distintos.
3. Intenta CHOQUE mientras Fundamentos está activo: rechazo por superposición. Intenta CARGA: rechazo por máximo de créditos. Ajusta la carga del ejemplo si cambiaste el máximo institucional; los créditos por asignatura admiten hasta 30.
4. Intenta LAB2 sin LAB1: rechazo. Selecciona LAB1 primero y LAB2 después; espera aceptación si hay cupo y no hay otro impedimento.
5. Retira **las dos selecciones auxiliares** al terminar para no bloquear el cierre del período por materias sin evaluaciones.
6. Mediante `POST /enrollments/` con token admin prueba un `period` inventado y un período existente distinto al de la sección. Ambos deben rechazarse sin escritura.
7. Con dos sesiones estudiantiles intenta simultáneamente confirmar una sección QA auxiliar con **un cupo**, usando una asignatura elegible para ambos. Debe haber como máximo un confirmado; el otro queda en espera o recibe un conflicto controlado. No uses alumnos ya retirados del mismo registro para esta prueba.

**Nota:** al añadir electivas, el catálogo del programa puede advertir que los créditos totales del pensum ya no son 6. Es una variación deliberada de laboratorio; no confundas ese total con haber aprobado las dos materias obligatorias.

### EST-06 / DOC-02 — Horarios [UI, estudiante y docente]

1. Como Mariela abre Mi horario en Lista y Semana.
2. Alterna 12/24 horas. 18:00 debe equivaler a 6:00 p. m., no cambiar el horario almacenado.
3. Contrasta código, asignatura, días, profesor, modalidad y aula con la sección.
4. Repite como Ana; deben aparecer únicamente sus asignaciones.
5. Haz una captura a ancho móvil y revisa legibilidad.

**Límites actuales que debes registrar:** la cuadrícula semanal dibuja lunes–sábado; no la uses para acreditar una clase dominical. La consulta de horario del estudiante no filtra actualmente todos los estados históricos de selección: si ves una retirada/en espera, contrástala con el catálogo y anota esa limitación; no la interpretes como plaza confirmada. Las reuniones detalladas y el horario base también deben contrastarse: la vista semanal utiliza el horario base de la sección.

## 4. Docencia: asistencia, evaluaciones, tareas y resultados

### DOC-03 — Pase de lista [UI, `profesor.01`]

1. Mis secciones → QA Fundamentos → Ver asistencia. Confirma que aparece Mariela y su matrícula, no los retirados ni la espera.
2. Elige un lunes/miércoles **pasado o de hoy**, dentro del período. En esta edición sirven 12 y 14 de octubre de 2026. No inventes una clase futura.
3. Sin registrar no debe aparecer preseleccionado como presente. Marca Presente, escribe motivo `Pase de lista QA`, guarda y recarga.
4. Registra una segunda fecha como Ausente. Dos fechas, una presencia: 50% registrado.
5. Corrige la segunda a Tardanza con motivo. Deben quedar historial y autor; pasa a 100% de presencia computable.
6. Prueba Salida anticipada y Ausencia justificada. Una justificada sin nota ni referencia debe bloquearse; agrega `Constancia ficticia QA-001` y guarda.
7. Comprueba la política: Presente, Tardanza y Salida anticipada computan presencia; Ausente y Justificada no. Se conserva la diferencia de estados, aunque compartan valor computable.
8. Consulta Historial. Si quieres un resultado final fácil de contrastar, deja dos fechas: Presente y Ausencia justificada → 50%.
9. Cambia un estado sin guardar e intenta cambiar de fecha o salir por los accesos que advierten de cambios pendientes: cancelar debe conservar el borrador.
10. Prueba fecha futura y día sin clase: rechazo. Solo admin puede justificar una sesión extraordinaria con el campo de excepción y motivo; no inventes autorización docente.
11. Prueba buscar matrícula y «Marcar sin registrar como presentes» en un grupo auxiliar de varias personas; la confirmación advierte que incluye filas ocultas por el filtro. No lo uses masivamente sin revisar.

**Esperado:** un registro por selección y día; corregir no duplica clases. La UI no ofrece un borrado general de asistencia; la API tiene eliminación con sus controles e historial.

### DOC-04 / ADM-14 — Seguimiento de asistencia [UI]

1. Asistencia → busca sección QA y filtra fechas.
2. Compara porcentaje, total de registros, ausencias y tardanzas con DOC-03.
3. Abre Ver estudiantes; expande Mariela y revisa fechas, observaciones y respaldo.
4. Prueba filtros de estudiante, período y estado de asistencia.
5. Repite como admin: ve más secciones; Ana solo ve las propias.
6. Como Mariela abre Mi asistencia: debe mostrar únicamente sus registros. Una fecha no registrada no debe contarse automáticamente como ausencia.
7. Como tutora comprueba el porcentaje del estudiante. Los indicadores que usan todo el historial no tienen por qué coincidir con un filtro de fechas reducido.

### DOC-05 — Crear y editar el plan evaluativo [UI, docente]

1. Evaluaciones → selecciona la sección QA Fundamentos.
2. Distribución y plantillas → crea `Práctica aplicada`, peso 40%, fecha de entrega cercana; crea `Examen integrador`, peso 60%.
3. Intenta agregar otro componente que exceda 100: debe impedirse.
4. Cambia ambos porcentajes a 50/50, escribe motivo y Guarda distribución. Comprueba total 100 y registro del cambio.
5. Devuelve ambos a 40/60 con motivo; estas serán las ponderaciones para el cálculo de ejemplo.
6. Edita nombre/fecha de un componente y comprueba que no se duplican sus notas.
7. Guarda el plan completo como `Esquema QA 40-60`; guarda además un componente como plantilla.
8. Crea una segunda sección QA **sin alumnos**, de la misma asignatura y período, con código distinto. Copia el esquema completo a esa sección vacía; no debe copiar calificacionses.
9. Comprueba que no puedes aplicar otro esquema completo sobre un plan ya existente. En otra sección vacía prueba plantilla individual, respetando 100%.
10. Compara alcance: esquema creado por admin compartido; uno personal docente no debe aparecer al otro profesor. No confundas guardar una plantilla con aplicarla.

### DOC-06 / EST-07 — Borradores, cero, publicación y correcciones [UI]

1. En Libro de notas, usa exclusivamente **Examen integrador** para los ensayos de este caso. Escribe **0** en esa celda de Mariela, agrega motivo y Guarda borrador del componente. Deja Práctica aplicada totalmente sin notas: se utilizará para la transferencia de tarea.
2. Entra como Mariela: no debe ver ese borrador. Cero no equivale a pendiente, pero sigue privado hasta publicar.
3. Vuelve como docente, publica el cero y comprueba que el estudiante ya ve 0/100.
4. Consulta el historial de la celda; corrige con motivo, publica y comprueba valor anterior, nuevo valor y actor.
5. Prueba anular una nota de un componente abierto con motivo desde su historial; la nota no debe contribuir ni aparecer como vigente al estudiante. Vuelve a registrar una nota en la misma celda y confirma que no se duplica la identidad.
6. Intenta publicar con cambios sin guardar: debe bloquearse. Prueba valores -1 y 101: inválidos.
7. Deja Examen integrador anulado al finalizar el ensayo; lo volverás a registrar manualmente como 90 en DOC-09. Práctica aplicada debe seguir sin una nota creada. **Anular una nota conserva su fila y no libera el componente para una transferencia automática de otra procedencia**: esta rechaza notas independientes, incluso anuladas. Si ya tocaste Práctica aplicada, prueba la transferencia en otro componente realmente vacío de una sección QA auxiliar; no borres historia para forzarla.
8. No cierres todavía las evaluaciones. Guarda la evidencia de notas publicadas antes de continuar.

### DOC-07 / EST-08 — Tareas: borrador, entrega, intentos y devolución [UI]

1. Como docente: Agenda y tareas → Crear tarea. Sección Fundamentos, título `Informe de procesos QA`, instrucciones `Describe en 200 palabras un proceso de biblioteca y propone una mejora`, máximo **50**, fecha futura, vínculo Práctica aplicada, abierta, permite reenvíos y sin publicación inicial.
2. Filtra Borradores y verifica la tarea. Como Mariela no debe aparecer ni ser accesible por su ID.
3. Publica desde Editar. Como Mariela abre Ver tarea, entrega `Primer intento: préstamo de libros registrado manualmente.`
4. Reenvía antes de calificar: `Segundo intento: usar un catálogo para validar disponibilidad.` Debe conservarse cada intento.
5. Como docente abre Revisar entregas: identifica nominalmente entregado/no entregado. Consulta intentos y califica **40/50**, devolución `Propuesta clara; mejora la descripción de excepciones`.
6. Como Mariela verifica puntuación y devolución exactas. Una entrega ya calificada no debe admitir reenvío para alterar el resultado publicado de la tarea.
7. Como docente indica motivo y usa **Crear notas borrador**. La normalización es `40 / 50 × 100 = 80`.
8. Repite la transferencia: no debe duplicar ni sobrescribir una nota diferente. Si hay conflicto, debe pedir revisión, no resolverlo arbitrariamente.
9. En Evaluaciones verifica borrador 80 en Práctica aplicada. Como Mariela todavía no debe verlo como nota académica hasta publicarlo.
10. Publica la nota 80 desde Evaluaciones.

**Esperado:** calificar una tarea y publicar una nota académica son dos actos diferentes. La entrega es contenido de texto; no hay en este flujo un cargador general de archivos de tareas ni rúbricas completas.

### DOC-08 — Políticas de tareas y consulta histórica [UI, docente/estudiante/tutor]

1. Crea otra tarea **de práctica sin vínculo evaluativo**, entrega y califica con 0. Debe verse 0 en la tarea, sin cambiar el promedio académico.
2. Crea una tarea con plazo cercano. Una vez vencida, prueba con entregas tardías deshabilitadas y habilitadas: rechazo/aceptación según política. No adelantes el reloj del equipo.
3. Desactiva reenvíos en otra tarea: debe admitir una sola entrega.
4. Cierra una tarea: no recibe nuevas entregas. Archívala y consulta desde Cerradas y archivadas; no esperes eliminación física.
5. Comprueba que con entregas existentes no se cambia sección, escala ni vínculo evaluativo para reinterpretar trabajos.
6. Como Diego/Camila retirados verifica que no puedan entregar a través de aquella selección. Como profesor ajeno, que no se acceda a contenido privado.
7. Como `qa.tutora`, consulta instrucciones publicadas y plazos, sin botones para entregar, calificar ni leer intentos privados de otras personas.

### DOC-09 / EST-09 — Resultado ponderado y cierre [UI]

1. En Examen integrador registra y publica **90** para Mariela.
2. Antes del cierre verifica la suma: `80 × 0.40 + 90 × 0.60 = 86`. No es el promedio simple 85.
3. En un componente sin una nota publicada intenta cerrar: debe bloquearse; luego vuelve a dejar ambas notas válidas/publicadas.
4. Cierra Práctica aplicada y Examen integrador.
5. Como Mariela consulta Mis notas: Fundamentos debe quedar definitivo/aprobado 86, no provisional.
6. Comprueba Mi progreso y Mi expediente: deben reconocer 3 créditos aprobados de Fundamentos.
7. Como docente intenta corregir una evaluación cerrada: debe bloquearse. Solo admin puede reabrir con motivo; esa prueba se hace después sin perder el resultado final.

### DOC-10 / ADM-15 — Calificaciones: seguimiento por sección [UI]

1. Abre Calificaciones, busca QA, filtra período, pendientes, borradores y definitivos.
2. Verifica cantidad de alumnos, media publicada, resultados definitivos y avance del plan. Un pendiente no debe contarse como un cero inventado.
3. Ver estudiantes → expande Mariela: componente, nota, estado, peso y aporte deben cuadrar con 32 + 54 = 86.
4. Revisa historial separado de anuladas, si lo generaste en DOC-06.
5. Usa Abrir libro de notas para volver a Evaluaciones con la misma sección.
6. Como admin compara sección y detalle; como docente comprueba que no se mezclan secciones ajenas.

### EST-10 — Continuación y graduación básica [UI, estudiante y docente]

1. Ahora que Fundamentos está aprobado definitivamente, Mariela selecciona Proyecto desde el catálogo. Debe superar el prerrequisito.
2. En Proyecto, Ana crea un componente de 100%, registra/publica **70**, cierra y verifica resultado definitivo con el umbral de aprobación de la selección. El valor 70 supone que la configuración seguía en 70 al seleccionar.
3. Como Mariela abre Mi progreso: ambas obligatorias completas y 6 créditos aprobados.
4. Abre Mi graduación: sin otras obligatorias/pasantías/trabajos de grado pendientes, debe ser elegible.
5. Abre Mi expediente: revisa intento, créditos, resultado y promedio. Con 86 y 70, el promedio de esos dos resultados es 78, salvo otros resultados QA añadidos deliberadamente.
6. Descarga PDF del expediente, ábrelo y comprueba identidad, matrícula, programa, caracteres, importes/notas y ausencia de páginas cortadas.
7. Antes de terminar Proyecto, o usando Diego sin materias aprobadas, comprueba el caso contrario: requisitos pendientes, no elegible. Tener suficientes créditos por equivalencia no debe saltarse una obligatoria pendiente.

## 5. Agenda y comunicaciones

### COM-02 — Agenda: eventos, tareas y evaluaciones [UI, todos]

1. Como docente, Agenda y tareas → Agenda académica → Crear evento.
2. Crea `Tutoría de proyecto QA`, tipo Reunión, destinatarios Una sección, Fundamentos, inicio/fin válidos. Guarda, abre y edita la descripción.
3. Como admin crea un evento institucional `Jornada de orientación QA`; comprueba audiencias por institución, rol y sección.
4. Prueba un día no lectivo: es una marca informativa, no cancela automáticamente horarios ni asistencia.
5. Como estudiante/tutor comprueba que solo reciben eventos de su audiencia y tareas/evaluaciones publicadas relevantes; no deben editar.
6. Cambia Mes/Semana/Lista del mes, Hoy, anterior/siguiente, 12/24 horas; busca por texto y filtra sección/tipo.
7. Abre un vencimiento de tarea: debe llevar a la tarea. Abre una evaluación: es fecha de evaluación, no una entrega.
8. Intenta fin anterior al inicio y evento docente de una sección ajena/global: debe rechazarse.

**Esperado:** agenda de fechas puntuales separada del horario recurrente. No hay un borrado de eventos desde esta interfaz; editar no equivale a eliminar.

### COM-03 — Avisos a estudiantes y tutores [UI, admin/docente]

1. Como Ana, Comunicaciones → Nuevo aviso → estudiantes de sección QA Fundamentos.
2. Título `Materiales para la práctica QA`; mensaje `Revisar el procedimiento antes de la próxima clase.`
3. Revisar destinatarios: debe incluir a Mariela activa y no a Diego/Camila retirados de esa sección. Verifica el número antes de confirmar.
4. Confirma una vez. Como Mariela, Recibidos → busca el aviso → marca leído. Prueba filtro leídos/no leídos y marcar todos, sabiendo que solo afecta a esa cuenta.
5. Como Ana, Publicados: verifica entregas internas y marcas de lectura. Leído no significa correo entregado ni comprensión.
6. Envía otro aviso a **Tutores de una sección**; Patricia debe recibirlo por su vínculo con Mariela.
7. Admin: prueba institución y audiencias por rol. Otro estudiante/tutor no perteneciente a la audiencia no debe recibir el aviso restringido.
8. Si cambia la audiencia después de la vista previa —por ejemplo, retiras un alumno desde otra sesión—, confirmar debe exigir una revisión nueva, no usar el conteo anterior.
9. Estudiante/tutor no tienen Nuevo aviso ni Publicados de gestión. Profesor no puede publicar a toda la institución.

**Esperado:** avisos solo internos; no se envían WhatsApp, SMS ni correo. Para reintentos técnicos, reutiliza por API la misma `delivery_key` y payload: no debe duplicar; cambiar contenido con la misma clave debe rechazarse.

## 6. Finanzas completas con números comprobables

Usa **la cuenta nueva de Mariela**, inicialmente en cero, no Sofía con movimientos anteriores. Todos los importes son ficticios de laboratorio en la copia. Nunca envíes dinero real para ejecutar estos casos.

### FIN-00 — Preparación de transferencias y simulador

En la configuración local revisada **no hay instrucciones bancarias**; `FINANCE_SIMULATOR_ENABLED` está habilitado. Por ello reportar transferencias nuevas está bloqueado correctamente hasta configurar instrucciones.

1. En el `.env` de pruebas añade un texto expresamente ficticio, sin cuenta bancaria real:

   ```dotenv
   FINANCE_TRANSFER_INSTRUCTIONS=SOLO PRUEBAS QA. Banco y cuenta ficticios. NO TRANSFERIR DINERO REAL.
   FINANCE_SIMULATOR_ENABLED=true
   ```

2. Reinicia el backend y comprueba `GET /finance/options` o las instrucciones que muestra Mi cuenta.
3. Prepara un PDF/PNG/JPEG válido con texto `COMPROBANTE FICTICIO QA - SIN VALOR`, máximo 2 MB. Renombrar un TXT a PDF no crea un comprobante válido.

### FIN-01 — Cuentas, filtros y días [UI, administrador]

1. Finanzas → busca Mariela por matrícula y abre su cuenta.
2. Anota balance inicial 0. Prueba buscar y filtrar cuentas con deuda, vencidas y sin deuda en el listado.
3. Configura corte 15 y vencimiento 30. Son referencias de cuenta; no generan cargos, mora ni bloqueo automáticamente.
4. Verifica que las cuentas con historial de personas inactivas no desaparecen de los controles financieros por solo inactivarlas.

### FIN-02 — Cargo, efectivo, beca y mora [UI, admin]

1. Registrar cargo, efectivo o ajuste → cargo `Matrícula QA`, **RD$1,000.01**, vencimiento de ayer. Balance: **1,000.01**.
2. Registra efectivo ficticio **200.01**, referencia única `QA-EFECTIVO-001`. Balance: **800.00**. En una operación real solo se registra efectivo recibido.
3. Registra beca **50.00**, descripción `Beca de prueba QA`. Balance: **750.00**.
4. Registra mora/débito **25.00**, descripción `Ajuste ficticio QA`. Balance: **775.00**.
5. Busca/filtra los movimientos; revisa método, signos, vencimientos y recibo. Descarga y abre el recibo del pago.
6. Prueba monto negativo, cero, más de dos decimales y pago mayor que deuda: deben rechazarse.
7. Prueba crédito/descuento y débito en una cuenta QA auxiliar si quieres conservar intacta esta secuencia aritmética. Beca/descuento/crédito reducen deuda; mora/débito la aumentan.

### FIN-03 — Transferencia pendiente, rechazo y aprobación [UI, alumno/admin]

1. Como Mariela: Mi cuenta → Transferencias → reporta **100.00**, referencia `QA-TRANSFER-001`, banco `Banco ficticio QA`, comprobante de FIN-00.
2. Mientras está pendiente, balance sigue **775.00**: subir una imagen no es acreditar un pago.
3. Como admin abre Transferencias, descarga comprobante y Revisar ingreso. En este laboratorio el motivo debe indicar simulación, por ejemplo `Validación ficticia QA; sin ingreso bancario real`.
4. Confirma dinero recibido dentro de la copia ficticia. Balance: **675.00**, un pago y un recibo.
5. Como Mariela revisa aprobación/motivo y descarga el recibo.
6. Reporta otra transferencia de 50, referencia `QA-TRANSFER-002`; admin rechaza con motivo `Comprobante ficticio ilegible`. Balance sigue **675.00**.
7. Prueba referencia repetida, archivo no válido o mayor de 2 MB y monto superior al saldo: rechazo sin movimiento contable.
8. Como Diego intenta descargar el comprobante de Mariela por API: debe negarse; también aprobarlo como estudiante.
9. Mediante API reintenta la aprobación idéntica de la primera solicitud: nunca debe generar un segundo abono. No cambies la referencia para simular un reintento.

### FIN-04 — Planes, cobertura y reversos [UI, admin/estudiante]

1. Con balance **675.00**, Cuotas y planes → crea `Acuerdo QA`, 3 cuotas, primera fecha coherente. Total: tres cuotas de **225.00**; el balance sigue 675.
2. Intenta crear otro plan activo: debe rechazarse.
3. Registra otro efectivo de **100.00**, referencia `QA-EFECTIVO-002`. Balance: **575.00**. La primera cuota debe reflejar cobertura parcial, no tres cuotas pagadas.
4. Como estudiante consulta el mismo plan; no debe poder editar cobertura manualmente.
5. Intenta reversar ese efectivo con el plan activo: debe pedir cancelar el plan antes.
6. Cancela el plan con motivo. No borra pagos ni altera la deuda; conserva su cobertura histórica al cancelar.
7. Reversa el efectivo de 100 con motivo `Corrección ficticia de caja QA`. Balance vuelve a **675.00**; el pago sigue visible como reversado, no eliminado.
8. Intenta reversarlo otra vez: no debe afectar el balance de nuevo. Intenta reversar el cargo de 1,000.01 si eso produciría saldo a favor: debe rechazarse.
9. Añade un cargo de **1.00**. Balance **676.00**. Un plan de 3 cuotas debe sumar exactamente 676, por ejemplo 225.34 + 225.33 + 225.33; no perder centavos.
10. Cancela ese segundo plan para no bloquear otros ensayos. Si quieres probar febrero, crea un plan auxiliar con día 31: la fecha debe adaptarse al último día del mes y conservar la intención para meses siguientes.

### FIN-05 — Simulador, estados de cuenta y auditoría [UI/API]

1. En Simulador de pagos ejecuta aprobado, rechazado y cancelado por 100. Debe indicar simulación y **no** cambiar 676, crear recibo ni asentar un pago.
2. Como alumno comprueba que ese simulador administrativo no aparece.
3. Admin: Auditoría financiera → revisa cargos, efectivo, ajuste, transferencias, plan y reverso, con motivo/autor donde exista.
4. Descarga por API `GET /documents/students/{A}/statement.pdf`; comprueba cada total y el saldo 676.
5. En el portal de Patricia comprueba balance 676 para Mariela y otro balance independiente para Diego.
6. Si quieres probar saldar, registra efectivo ficticio de 676 con referencia nueva; debe quedar 0. Un abono adicional de 1 debe rechazarse. Si no lo ejecutas, deja anotado que el saldo esperado final sigue en 676.

### FIN-06 — Conceptos y cierre de caja [UI, admin, GLOBAL, ÚLTIMO financiero]

1. Finanzas → Caja y catálogo de conceptos → crea `Laboratorio QA`, 250.00, frecuencia mensual.
2. Comprueba que la plantilla aparece, pero **no genera deuda mensual automáticamente**.
3. En una cuenta QA auxiliar, selecciona el concepto en Usar concepto del catálogo; verifica que carga nombre/importe. Solo guardar el cargo crea deuda.
4. Cuando acabes **todas** las pruebas de pagos de este día, revisa la fecha República Dominicana y confirma el cierre de caja del día de prueba.
5. Compara total/cantidad y desglose efectivo/transferencias. Un pago reversado no debe contarse como ingreso vigente.
6. Intenta registrar otro pago/aprobar una transferencia de ese día: debe bloquearse. También un reverso de un pago perteneciente al día cerrado.
7. No hay reapertura de caja: no esperes deshacer el cierre desde la UI. Por eso se hace en la copia y al final; una corrección posterior requiere ajuste documentado, no inventar devolución bancaria.

**Alcance financiero:** recibos internos, no NCF/e-CF; sin tarjetas ni conexión bancaria; planes no generan deuda nueva; el saldo y el bloqueo financiero son controles separados.

## 7. Equivalencias, reconocimiento y versiones

### ADM-16 / EST-11 — Regla de equivalencia y su impacto [UI]

1. Después de verificar la graduación básica, crea `QA-EQUIV-20261015`, `Seminario reconocido QA`, y agrégala al pensum QA versión `QA-2026`, 3 créditos, tipo **Electiva**.
2. Equivalencias → Carrera destino QA, versión QA-2026, origen Fundamentos, destino Seminario reconocido; observaciones `Reconocimiento ficticio del seminario`, motivo `Acuerdo curricular QA`.
3. Revisa impacto sin guardar: debe identificar alumnos que ya aprobaron el origen y créditos previstos. No es una solicitud individual.
4. Confirma. Como Mariela revisa progreso, expediente y graduación: debe aparecer reconocimiento sin nota numérica inventada y sin aumentar créditos intentados por haber cursado una sección inexistente.
5. Admin: filtros por carrera/versión/estado y búsqueda; Gestionar regla → cambia observaciones, consulta historial.
6. Desactiva con revisión de impacto y motivo; comprueba retiro del reconocimiento derivado. Reactiva y contrasta de nuevo.
7. Intenta origen=destino y una cadena circular: rechazo. La dirección es origen → destino, no recíproca.
8. No cambies globalmente la carrera de alumnos reales para probarlo. Si agregas una regla en versión histórica/no activa, no debe conceder progreso actual por esa sola regla.

### ADM-17 — Cambio de carrera conservando historia [API, admin]

1. Usa **Camila**, sin notas definitivas principales, no Mariela.
2. Crea otro programa QA temporal activo, versión explícita.
3. `POST /governance/students/{C}/career-change` con nuevo `career_id`, fecha y motivo `Cambio ficticio de programa QA`.
4. Consulta `GET /governance/students/{C}/career-history`: programa anterior/nuevo, fecha y motivo.
5. Como Camila consulta catálogo y progreso del nuevo plan. El cambio no debe borrar selecciones/notas anteriores ni otorgar equivalencias que no definiste.
6. Cambia de vuelta mediante el mismo procedimiento con otro motivo si necesitas restaurar su programa. No esperes borrar el historial del cambio.

### ADM-18 — Versiones, tipos de materia y retiro del pensum [UI]

1. Crea una asignatura auxiliar con código único y relación de versión `QA-HISTORICA` en el programa QA. No cambies la versión vigente del programa principal.
2. Abre Pensum y cambia el selector de versión: identifica cuál es vigente y cuál histórica. La oferta debe corresponder a las asignaturas de la versión consultada.
3. Prueba en relaciones auxiliares los tipos Electiva, Pasantía y Trabajo de grado; no los agregues como requisitos pendientes a Mariela antes de la prueba de graduación básica.
4. Edita créditos/período/requisitos de esas relaciones y contrasta la vista por períodos.
5. Retira una relación **auxiliar sin uso** del pensum: la asignatura del catálogo y sus otras asociaciones deben conservarse.
6. Asocia una asignatura auxiliar a otra carrera: debe ser el mismo catálogo institucional con créditos/requisitos propios en cada carrera.
7. No esperes poder duplicar sin más una relación de la misma asignatura/carrera para otra versión: la implementación actual protege ese duplicado. Registra como limitación si necesitas planes paralelos completos con las mismas materias.
8. Archiva y reactiva solo el programa QA auxiliar para verificar sus filtros, sin borrar historia. No prometas por cambiar Estado que todas las demás rutas ya implementan un proceso completo de suspensión institucional.

## 8. Control institucional, alertas y admisiones

### ADM-19 — Indicadores interpretables [UI, admin]

1. Control institucional → Indicadores: compara totales superiores con listas, no con cantidad de filas visibles en una página.
2. Filtra QA y luego Todos los períodos. Los totales financieros/institucionales superiores son globales; el filtro afecta resultados académicos y conjunto de riesgo.
3. Revisa resultados por carrera y asignatura: promedio final, muestra, aprobación, asistencia y casos abiertos.
4. Donde no hay resultados debe aparecer Sin datos, no un cero que parezca reprobación.
5. Proporción de activos no es retención longitudinal entre cohortes. Casos del conjunto no significa casos creados durante las fechas de ese período.
6. Contrasta QA con resultados definitivos 86/70 y con la asistencia registrada, teniendo presentes las electivas de laboratorio que agregaste.

### ADM-20 — Casos de seguimiento manuales [API para crear; UI para gestionar]

1. Como admin crea una alerta por `POST /operations/alerts`:

   ```json
   {"student_id": A,"category":"attendance","severity":"high","reason":"QA: dos clases requieren seguimiento con la familia"}
   ```

2. En Casos y seguimientos filtra por Mariela, abiertas, Asistencia y prioridad Alta.
3. Asigna a Ana, fecha próxima y guarda. Debe aceptar un responsable con acceso al estudiante y rechazar uno ajeno.
4. Registra actuación `Contacto ficticio con Patricia; se acuerda revisar el transporte`.
5. Consulta Historial: autor, fecha y texto. Desde API también puedes usar tipos contact, meeting, referral, agreement y note; la UI registra actuación genérica.
6. Resuelve con `Familia informada y plan acordado`; filtra Resueltos y verifica conclusión.
7. Reabre y confirma conservación de la resolución anterior. Repetir resolver/reabrir sin transición válida debe rechazarse.
8. Como Patricia consulta la alerta abierta de Mariela, con categoría/prioridad traducidas. No debe poder asignarla o resolverla desde su portal.

### ADM-21 — Alertas automáticas [UI, admin, GLOBAL]

1. Anota casos abiertos antes de pulsar Revisar alertas automáticas.
2. Ejecuta sobre la copia. Analiza alumnos activos con resultados finales reprobados, asistencia registrada inferior a 80% y deuda pendiente.
3. Repite: no debe duplicar un caso abierto de la misma categoría.
4. Corrige la causa ficticia y revisa: un caso anterior **no se resuelve automáticamente**; documenta actuación y resolución.
5. Para generar los tres tipos sin alterar Mariela, usa un alumno QA auxiliar con deuda, asistencia insuficiente y una nota final por debajo del criterio de aprobación. Un borrador no basta para un caso por reprobación definitiva.

**Esperado:** acción global de detección, no un reporte limitado silenciosamente a la carrera que tengas filtrada.

## 9. Funciones disponibles solo por API o sin pantalla completa

Haz estos casos también si tu objetivo es probar todo lo implementado, no solamente el menú. Usa API-00 y anota todos los IDs devueltos. No hay obligación de programar: Swagger permite enviar los cuerpos y descargar respuestas.

### API-01 — Plan de clase [docente/admin]

1. Ana: `POST /operations/lesson-plans`:

   ```json
   {"section_id": SF,"scheduled_date":"2026-10-14","title":"Proceso de biblioteca QA","content":"Identificar actores y excepciones del préstamo","competencies":"Documentar un proceso","status":"planned"}
   ```

2. Consulta `GET /operations/lesson-plans?section_id={SF}`. Identifica docente/fecha/contenido.
3. Profesor ajeno: la consulta no debe exponer planes ajenos y la creación en `SF` debe rechazarse.
4. Los estados admitidos son planned/delivered/cancelled al crear. **No hay ruta de actualización o borrado de planes** en la implementación actual; no se presenta como ciclo de gestión completo.

### API-02 — Solicitudes de aprobación [usuario autenticado/admin]

1. Como docente crea `POST /operations/approvals` con `request_type="academic_exception"`, `resource_type="section"`, `resource_id=SF`, motivo `Solicitud ficticia de revisión QA`.
2. Como admin consulta `GET /operations/approvals` y resuelve por `PATCH /operations/approvals/{id}` con status approved y nota.
3. Repite con una segunda solicitud para probar rejected.
4. Consulta la sección: la aprobación **no reabre ni cambia automáticamente** el recurso. Es un registro de solicitud/resolución, no un motor completo de excepciones ni una concesión de permisos.
5. Un estudiante/docente no debe resolver usando el endpoint administrativo. El endpoint de creación admite usuarios autenticados; no lo confundas con validar automáticamente la legitimidad del recurso solicitado.

### API-03 — Archivo documental del estudiante [admin para subir]

1. Prepara un PDF/PNG/JPEG ficticio menor de 5 MB. Convierte su contenido a base64 localmente; por ejemplo en PowerShell:

   ```powershell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\ruta\documento-ficticio.pdf'))
   ```

2. Admin: `POST /operations/students/{A}/documents`, campos `document_type="bachillerato"`, `filename="bachillerato-qa.pdf"`, `mime_type="application/pdf"`, `content_base64` real y `expires_on` opcional.
3. Consulta `GET /operations/students/{A}/documents`; anota `student_document_id`.
4. Descarga por `GET /operations/documents/{id}/download`; abre el archivo y verifica contenido/nombre.
5. Mariela puede consultar su archivo; Ana lo hace en su ámbito académico. Un estudiante ajeno no debe descargarlo.
6. Prueba base64 inválido y más de 5 MB: rechazo. No hay aquí botón de borrado, firma electrónica ni certificación de autenticidad documental.

### API-04 — PDFs y exportaciones [según perfil]

1. Como admin y como Mariela descarga sus documentos:
   - `GET /documents/students/{A}/transcript.pdf`: expediente.
   - `GET /documents/students/{A}/enrollment-certificate.pdf`: constancia.
   - `GET /documents/students/{A}/report-card.pdf`: boleta.
   - `GET /documents/students/{A}/statement.pdf`: estado de cuenta.
2. Como Ana: `GET /documents/sections/{SF}/roster.pdf`, lista de sección.
3. Como Ana intenta el expediente/boleta longitudinal de Mariela: debe rechazarse; tener una sección no concede todas sus notas.
4. Como admin: `GET /records/reports/students.csv`, reporte académico, y `GET /bulk/students/export`, directorio. Son exportaciones distintas.
5. Abre cada archivo: nombre/matrícula/carrera, tildes, tablas largas, saltos, fechas, ponderaciones y totales. Responder 200 no acredita por sí solo que el PDF sea legible.
6. Un recibo interno o un encabezado que diga Documento oficial no certifican por sí mismos validez legal/fiscal.

### API-05 — Consultas académicas y protección CRUD

1. Consulta `GET /enrollments/`, `/enrollments/{id}`, `/sections/{id}`, `/academic/sections/{id}/students` con admin, docente propietario, estudiante propietario y actores ajenos.
2. Compara `/academic/students/{id}/grades`, `/profile`, `/schedule`, `/attendance-summary` con la vista correspondiente. Historial docente debe filtrar por sección **antes de paginar**.
3. Consulta `/assessments/sections/{id}/finals` y `/assessments/enrollments/{id}/final`; contrasta con la nota definitiva usada por expediente/graduación.
4. En recursos **auxiliares sin historial**, prueba crear, consultar, editar y eliminar asignatura/sección/rol/usuario donde exista ruta. En recursos con historial, prueba que una eliminación peligrosa se rechace; no fuerces borrados para poder marcar el caso.
5. Una selección con notas no puede borrarse físicamente; usa retiro. Una selección sin notas eliminada administrativamente debe liberar como máximo una plaza y promover una vez.
6. `PATCH /enrollments/{id}` no es un atajo para asignar completed/failed, cambiar persona/sección/período o mover posiciones de espera. Prueba que esos cambios inválidos no eludan los flujos de cierre.
7. La API todavía contiene rutas de notas/asistencias individuales, además de los flujos masivos. En un caso auxiliar prueba creación/consulta/corrección con motivo, historial y anulación/borrado autorizado; deben respetar los mismos cierres y ámbito, no convertirse en otra política.

### API-06 — Salud e instalación inicial [API]

1. Consulta `GET /health`: debe responder `status=ok` y `database=reachable`. Esto prueba conexión y una consulta simple, no todas las tablas o funciones.
2. En la copia con usuarios, intenta `POST /auth/bootstrap` con un nombre/correo ficticios y contraseña válida: debe responder 409 porque ya existe administrador inicial.
3. El bootstrap positivo se prueba **solo en otra base vacía recién migrada**, no borrando usuarios de esta copia. Allí debe crear el primer administrador una vez; el segundo intento debe rechazarse. Si no preparas esa instalación separada, registra «no ejecutado: requiere base vacía», no aprobado.
4. Anota que migraciones, respaldo y restauración son operaciones de mantenimiento, no botones de administración académica ni despliegue requerido para usar el laboratorio.

### SEG-00 — Renovación y cierre de autenticación [API, cuenta QA]

1. Usa un mismo contexto de navegador en Swagger para login de la cuenta QA. La respuesta guarda una cookie HttpOnly de renovación; no pegues esa cookie en un informe ni la publiques.
2. Ejecuta `POST /auth/refresh` sin intentar poner el token de renovación en el JSON: el backend lo toma de la cookie. Debe devolver un access token nuevo y rotar la sesión de renovación.
3. Actualiza Authorize con el access token nuevo y confirma `GET /auth/me`.
4. Ejecuta `POST /auth/logout`. Un nuevo refresh desde ese contexto debe responder 401, porque se eliminó/revocó su renovación.
5. La UI borra además su access token al cerrar sesión. Si hiciste logout solo por API, un bearer ya emitido puede durar hasta su expiración: no interpretes JWT y cookie como si fueran la misma credencial.

## 10. Configuración, accesos y seguridad

### ADM-22 — Institución, matrícula y criterios [UI, admin, GLOBAL]

1. Configuración → Institución y matrícula. Anota nombre, prefijo, dígitos, siguiente secuencia, nota aprobatoria y máximo de créditos antes de cambiar nada.
2. Cambia nombre a `Instituto Horizonte - laboratorio QA`; escribe motivo → Revisar impacto → Confirmar.
3. Consulta Historial y verifica un cambio por campo, actor/fecha/motivo. Cambia otro campo después de previsualizar: debe invalidar la revisión anterior.
4. Abre dos editores con la misma revisión. Guarda uno y después el otro: el segundo debe pedir recargar, no sobrescribir silenciosamente una revisión obsoleta.
5. Cambia prefijo/dígitos y crea un estudiante QA auxiliar con matrícula vacía. Debe usar la numeración nueva sin renumerar a Mariela/Sofía. No reduzcas manualmente el contador para forzar colisiones.
6. Cambia nota aprobatoria **después** de seleccionar las materias principales de Mariela. Esas selecciones conservan su criterio anterior; una nueva toma el nuevo.
7. Para acreditar la diferencia usa una materia/estudiante auxiliar: con nuevo umbral 80, un resultado final 75 debe reprobar allí, sin reclasificar la selección anterior de umbral 70.
8. Prueba máximo de créditos con una selección nueva; cambiarlo no debe retirar asignaturas existentes automáticamente.
9. Restaura los valores anotados al acabar. Cambiar de vuelta la configuración tampoco reescribe criterios ya fijados en selecciones intermedias de prueba.

### ADM-23 — Roles y permisos [UI/API, admin, GLOBAL]

1. Configuración → Roles: crea `qa_observador`, descripción `Rol temporal de pruebas`, edítalo, consulta su detalle. No esperes un nuevo portal completo por inventar un nombre de rol: los cuatro espacios visuales están definidos por admin/teacher/student/guardian.
2. Configuración → Permisos por rol: revisa permisos y cambios propuestos, escribe motivo y confirma. Consulta historial.
3. Usa el rol temporal y una cuenta temporal para pruebas negativas de API. **No retires permisos del administrador principal ni del docente que aún tenga que terminar el recorrido.**
4. Para probar menú docente, retira temporalmente `grades.manage` del rol teacher en la copia, vuelve a entrar con una cuenta docente y comprueba ocultación de funciones evaluativas y rechazo de escrituras; devuelve el permiso inmediatamente.
5. Mis secciones/Mis estudiantes son consultas propias y no dependen del permiso administrativo `academic.manage`.
6. Aunque un rol docente histórico conserve o reciba `academic.manage`, no debe administrar oferta/matrícula/carreras. Compruébalo con token de Ana por API.
7. Con cambios de permisos sin guardar cambia de rol y cancela: el borrador debe conservarse. Revisa también aviso al recargar/cerrar pestaña cuando haya cambios pendientes.
8. Intenta retirar permisos esenciales propios o dejar sin gestores de acceso: debe rechazarse. No confíes en ocultar botones como única protección.
9. Elimina el rol temporal solo después de retirar su usuario/vínculos temporales y cuando no esté usado.

### SEG-01 — Mi cuenta, contraseña y sesiones [UI/API, todos, ÚLTIMO de cada actor]

1. Abre `/account`; admin tiene acceso desde Configuración → Mi seguridad y tutor desde Mi cuenta. Para docente/estudiante puedes abrir esa ruta directamente si no hay acceso visible en su menú.
2. En una cuenta QA prueba contraseña actual incorrecta y confirmación distinta: rechazo.
3. Cambia correctamente a una clave ficticia nueva de al menos 10 caracteres. Cierra sesión y entra con la nueva; la antigua no debe servir.
4. Consulta `GET /auth/sessions`, abre otra sesión QA y compara creación/expiración/actividad.
5. Pulsa Cerrar todas las sesiones. Se revocan las renovaciones; un access token ya emitido puede seguir válido hasta vencer. No exijas una invalidación instantánea de todos los JWT por solo esa acción.
6. Vuelve a iniciar sesión para continuar; registra la contraseña final usada.

### SEG-02 — Segundo factor TOTP [UI/API, cuenta QA auxiliar]

1. Configurar segundo factor → agrega la clave manualmente en una aplicación autenticadora compatible.
2. Introduce su código actual de 6 dígitos y Activa.
3. Cierra sesión e intenta entrar sin código o con uno incorrecto: rechazo; con uno vigente: acceso.
4. Conserva la clave solo durante la prueba y no la incluyas en el informe/capturas.
5. Para desactivar utiliza `POST /auth/mfa/disable` con código válido; la UI actual no ofrece un botón de desactivación.
6. No pruebes esto primero en el único admin: no hay un flujo completo de recuperación de cuenta/segundo factor que debas dar por supuesto.

### SEG-03 — Auditoría general [API, admin]

1. `GET /audit/`: busca eventos recientes de autenticación, contraseña, permisos y operaciones sensibles.
2. Usa los parámetros de filtro que expone Swagger; contrasta actor/acción/recurso/fecha con un caso QA conocido.
3. Docente/estudiante/tutor no deben obtener la auditoría institucional completa.
4. No exijas autores inventados para movimientos históricos anteriores a su trazabilidad ni que toda consulta de lectura genere un evento.

## 11. Cierres y reaperturas académicas

### ADM-24 — Cierre controlado del período [UI, admin, ÚLTIMO académico]

1. Termina tareas, comunicaciones de sección activa, asistencia y selección antes de este bloque.
2. Configuración → Períodos → Cerrar QA. Revisa la previsualización, no confirmes sin leer impedimentos.
3. Para probar rechazo, deja inicialmente una evaluación auxiliar con alumno activo sin publicar/cerrar. El cierre debe enumerar faltantes; corrígela o retira esa selección auxiliar mediante el flujo permitido.
4. Antes del cierre definitivo, Fundamentos y Proyecto principales deben sumar 100% por sección, tener notas publicadas/cerradas, y no quedar selecciones auxiliares activas sin resultados. Una sección cancelada con alumnos no debe saltarse el control.
5. Confirma cierre con motivo `Cierre institucional ficticio QA`.
6. Comprueba período cerrado, secciones correspondientes cerradas y selecciones activas consolidadas completed/failed según sus resultados. Esperas/retiros no deben convertirse en aprobaciones inventadas.
7. Como docente intenta cambiar notas/asistencia; como estudiante seleccionar una materia del período cerrado: debe bloquearse.
8. Consulta Historial del período y resultados del estudiante. Que la etapa cambie a Cerrado no es solo una etiqueta decorativa.

### ADM-25 — Reapertura y corrección trazable [UI, admin]

1. Reabre QA con motivo `Corrección académica autorizada QA`.
2. Comprueba que se restauran los estados que cambió ese cierre y que QA vuelve a vigente; no se adivinan estados de cierres históricos sin instantánea.
3. Las evaluaciones siguen cerradas. En Evaluaciones reabre individualmente Examen integrador con motivo.
4. Comprueba el plazo de calificación: si venció debe ajustarse explícitamente antes de permitir corrección.
5. Corrige una nota, publica, revisa historial y vuelve a cerrar la evaluación. Si cambias el 90 del ejemplo, recalcula el resultado esperado; restaura 90 si quieres volver a 86.
6. Vuelve a cerrar el período tras revisar los impedimentos.
7. Si la sección ya estaba cerrada antes del cierre del período, no esperes que reabrir el período la habilite indiscriminadamente; la corrección evaluativa tiene su propio procedimiento.

## 12. Matriz de aislamiento: repetir con los cuatro perfiles

### SEG-04 — Accesos permitidos y rechazados [UI y API]

| Acción | Admin | Docente de la sección | Estudiante propietario | Tutor vinculado |
|---|---|---|---|---|
| Crear carrera/pensum/sección, administrar selección | Sí, con permiso | No | No | No |
| Consultar sección, lista y expediente docente limitado | Sí | Solo propias | No recibe lista privada de compañeros | No recibe lista privada de compañeros |
| Registrar notas/asistencia y revisar entregas | Sí | Solo propias y con permiso | No | No |
| Entregar tarea | No como alumno | No como alumno | Sí, selección activa y política válida | No |
| Ver notas académicas | Todas según acceso | Solo sus secciones | Propias publicadas | Resumen familiar publicado, no el mismo endpoint estudiantil |
| Expediente longitudinal/PDF individual | Sí | No por ser docente | Propio | Portal familiar; no asumir acceso a todo PDF |
| Registrar efectivo/reversar/aprobar transferencia | Sí, con permiso | No | No | No |
| Reportar transferencia | Gestión autorizada según endpoint | No por docencia | Propia, con instrucciones y comprobante | No por solo vínculo familiar |
| Publicar aviso | Audiencias permitidas | Sus secciones/tutores | No | No |
| Leer notificaciones | Propias | Propias | Propias | Propias |
| Cambiar contraseña/TOTP/sesiones | Propias | Propias | Propias | Propias |

1. Desde React intenta una ruta administrativa con un estudiante. Puede redirigir a inicio en vez de pintar 403; eso no acredita por sí solo seguridad.
2. Desde Swagger repite escrituras administrativas con token estudiante/tutor/docente: deben negarse sin efectos secundarios.
3. Como Ana intenta `PATCH /sections/2` y `PATCH /enrollments/2` fuera de su ámbito o cualquier administración de oferta: rechazo. Usa solo datos ficticios en la copia.
4. Consulta historial de Sofía con Ana: no deben aparecer notas de Carlos. Contrasta IDs con la lista de notas propia del docente.
5. Como un estudiante intenta la cuenta, notas, documentos, comprobante y entregas de otro: rechazo.
6. Como Patricia intenta el seguimiento de Camila, a quien no vinculaste: rechazo.
7. Una URL escrita a mano no debe ampliar privilegios. 401 por token vencido no sustituye la prueba de 403 con un token válido.

## 13. Revisión visual y manejo de errores en todas las pantallas

### UX-01 — Catálogos y tablas [UI, perfiles que los ven]

1. En estudiantes, docentes, carreras, asignaturas, secciones y catálogos administrativos, busca, limpia búsqueda, pagina y expande detalles.
2. Prueba un texto que no coincida: lista vacía explicada, no error ni cifras antiguas engañosas.
3. Comprueba que acciones estén accesibles sin arrastrar toda la tabla y que los detalles secundarios no oculten nombre/matrícula/estado.
4. Usa dos registros QA de nombre idéntico, pero matrículas diferentes, en una sección auxiliar con cupo suficiente: los controles de asistencia y notas deben distinguirlos por matrícula.
5. Comprueba carreras por nombre, no por ID; docentes/asignaturas/modalidades por etiquetas legibles. Un ID en Swagger es normal, en un selector de negocio sin nombre es una observación UX.

### UX-02 — Formularios, modales y móvil

1. En cada formulario de alta/edición abre, cancela, vuelve a abrir, guarda y recarga.
2. Prueba obligatorios vacíos, formato de correo, valores fuera de rango y textos largos. Verifica mensajes sin borrar todo el borrador innecesariamente.
3. Usa Tab/Shift+Tab, Escape y cierre de modal. El foco debe mantenerse en el diálogo y volver al control original al cerrarlo; botones finales y ayudas deben ser visibles.
4. Revisa etiquetas/ayudas completas, selects estilizados, zoom de navegador y ancho móvil. No uses un placeholder cortado como única explicación.
5. Con una escritura pendiente, un doble clic no debe duplicar operación. No todos los formularios tienen el mismo bloqueo de navegación: prueba cada advertencia existente; no supongas un guardián global de cambios sin guardar.

### UX-03 — Errores de conexión y sesión

1. En una consulta sin cambios pendientes, detén temporalmente el backend de pruebas y recarga una pantalla.
2. Debe mostrar error/acción de reintento donde esté disponible, no «sin datos» como si la consulta hubiera tenido éxito.
3. Reinicia el backend y vuelve a intentar. Comprueba que el frontend apunta al puerto correcto y que el origen real está autorizado por CORS.
4. Prueba cerrar sesión y acceder a una ruta protegida; debe pedir autenticación.
5. No ejecutes una interrupción deliberada durante el commit de caja ni cierres sin un plan de recuperación; este bloque no sustituye pruebas transaccionales automatizadas.

## 14. Cierre de la prueba y registro de resultados

### FIN-PRUEBA — Dejar el laboratorio identificado

1. Revisa que no dejaste bloqueados/inactivos a los actores que quieras seguir usando.
2. Anota qué período quedó vigente, qué evaluaciones/caja cerraste y qué contraseñas QA cambiaste. No publiques esas claves.
3. Restaura los permisos y valores institucionales temporales. Los eventos de auditoría y resultados históricos no deben borrarse para «limpiar» la prueba.
4. Si usaste una copia, detén el backend y vuelve a apuntar `DATABASE_URL` a su valor original. Reinicia y verifica que la institución habitual conserva su estado. No copies la base QA encima de `school.db`.
5. Guarda esta ficha por incidencia:

   ```text
   Caso:
   Perfil y usuario:
   Matrícula / sección / período:
   Datos de entrada:
   Pasos exactos:
   Esperado:
   Obtenido:
   Evidencia sin secretos:
   Estado: aprobado / falló / no ejecutado
   ```

## Inventario final para comprobar que recorriste todo

- [ ] Inicio/resumen y sesión de los cuatro perfiles.
- [ ] Estudiantes: directorio, ficha, trayectoria, familia, bloqueos e inactividad.
- [ ] Docentes: ficha profesional, vinculación, carga, horario y filtros.
- [ ] Carreras: identidad, organización, perfiles, pensum, versiones, oferta y archivo.
- [ ] Asignaturas: catálogo libre/compartido, relaciones y protección de eliminación.
- [ ] Pensum: créditos, tipos, prerrequisitos, correquisitos y retiro de relación auxiliar.
- [ ] Períodos: tipo/número, etapas, vigencia, fechas, cierre/reapertura/historial y eliminación segura sin uso.
- [ ] Admisiones: nueva, revisión, aceptación/rechazo, conversión e historial.
- [ ] Usuarios, roles, vínculos personales y protección del acceso administrativo.
- [ ] Tutores: creación/vínculo, varios estudiantes y separación familiar.
- [ ] Secciones: docente/materia/cupo/aula/modalidad/días, período/estado por API.
- [ ] Aulas/reuniones: altas, consultas, virtualidad, choques y eliminación auxiliar.
- [ ] Selección: carrito/quitar/confirmar, espera, promoción, retiro/reintento, bloqueos, límites y concurrencia.
- [ ] Horarios: lista/semana y formatos, con los límites descritos.
- [ ] Asistencia: cinco estados, motivos, excepciones, corrección/historial, seguimiento y consulta personal.
- [ ] Evaluaciones: componentes, redistribución, plantillas individuales/planes, copia e historial.
- [ ] Calificaciones: cero, borrador/publicación, edición/anulación, ponderación y cierre/reapertura.
- [ ] Tareas: políticas, entrega/reenvíos/intentos, calificación/devolución, transferencia, cierre/archivo y privacidad.
- [ ] Agenda: eventos/audiencias, vistas, filtros, 12/24 h, días no lectivos y enlaces de vencimientos.
- [ ] Comunicaciones: audiencias, revisión/confirmación, reintentos, notificaciones y lectura.
- [ ] Finanzas: cuentas/días/cargos/efectivo/ajustes/transferencias/recibos/planes/reversos/auditoría/conceptos/caja/simulador.
- [ ] Progreso, expediente, graduación, créditos directos y equivalencias sin nota.
- [ ] Cambio de carrera con historial; reglas y versiones curriculares.
- [ ] Indicadores institucionales, casos manuales/automáticos, asignaciones/intervenciones/resolución/reapertura.
- [ ] Planes de clase, aprobaciones y archivo documental por API, con límites explícitos.
- [ ] PDFs, CSV de directorio, CSV académico e importación parcial.
- [ ] Reglas institucionales, matrículas, criterio congelado, cambios concurrentes e historial.
- [ ] Permisos, contraseña, sesiones, TOTP y auditoría general.
- [ ] Salud de API, protección del bootstrap y renovación/rotación/logout de autenticación.
- [ ] Seguridad negativa por recurso, teclado/móvil, modales, tablas y errores de conexión.

## Qué no debes intentar acreditar como si ya existiera

No forman parte de la herramienta actual un formulario público de admisión, envío real de correo/SMS/WhatsApp, tarjeta/pasarela bancaria, facturación fiscal NCF/e-CF, firma oficial de títulos, recuperación completa de MFA, rúbricas/recuperaciones académicas complejas ni una certificación de rendimiento de miles de usuarios. Tampoco hay pantallas completas para todas las rutas administrativas de la API. Esas ausencias deben registrarse como alcance pendiente, no marcarse «probadas» ni confundirse con un error de tus datos.

Esta guía no realiza cambios por ti. En su preparación se consultaron código, documentación y datos locales en modo de lectura; no se crearon estos alumnos QA ni se alteraron cuentas, períodos o pagos.
