# p_pro backend

Backend educativo en FastAPI y SQLAlchemy. Esta etapa usa SQLite por defecto y deja preparada la configuración para cambiar de base de datos mediante `DATABASE_URL`.

## Requisitos

- Python 3.11 o posterior
- Un entorno virtual de Python

## Instalación

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

La configuración predeterminada usa `sqlite:///./school.db`. Para otra base de datos, modifica `DATABASE_URL` en `.env` e instala el controlador correspondiente.

## Ejecución

```powershell
uvicorn main:app --reload
```

En una instalación nueva, ejecuta primero las migraciones:

```powershell
alembic upgrade head
```

La documentación interactiva estará en `http://127.0.0.1:8000/docs`.

### Datos de demostración

Para crear un escenario local completo y repetible, ejecuta:

```powershell
python -m scripts.seed_demo
```

El cargador conserva los registros existentes y evita duplicar sus propios datos. Crea carreras, materias, docente, estudiante, secciones, inscripciones, una nota, una asistencia y estos accesos:

| Perfil | Usuario | Contraseña |
| --- | --- | --- |
| Administración | `demo.admin` | `NexoAdmin2026!` |
| Docente | `demo.docente` | `NexoDocente2026!` |
| Estudiante | `demo.estudiante` | `NexoEstudiante2026!` |

Estas credenciales son exclusivamente para desarrollo local. No ejecutes el cargador ni reutilices las contraseñas en producción.

### Escenario institucional masivo

Para sustituir los datos locales por una institución ficticia completa, crea primero un respaldo de `school.db` y ejecuta:

```powershell
python -m scripts.seed_institution
```

Este comando elimina los registros ficticios anteriores y carga un escenario reproducible del Instituto Técnico Horizonte con 120 estudiantes, 6 docentes, 12 tutores, 3 carreras, 15 asignaturas, 15 secciones, evaluaciones, selección académica, notas, asistencia, finanzas, calendario, tareas, alertas con responsables e intervenciones, admisiones, documentos, comunicaciones y permisos. No elimina el archivo de base de datos ni modifica su esquema.

| Perfil | Usuario de ejemplo | Contraseña |
| --- | --- | --- |
| Administración | `admin.horizonte` | `NexoAdmin2026!` |
| Docente | `profesor.01` | `NexoDocente2026!` |
| Estudiante | `estudiante.001` | `NexoEstudiante2026!` |
| Tutor | `tutor.01` | `NexoTutor2026!` |

También se crean `profesor.02` a `profesor.06`, `estudiante.002` a `estudiante.120` y `tutor.02` a `tutor.12`, usando la contraseña correspondiente a su perfil. Este cargador es destructivo y debe utilizarse únicamente con datos locales ficticios.

El portal familiar muestra únicamente estudiantes vinculados e incluye promedio, asistencia, horario, balance y alertas. La administración dispone además de cierre controlado de períodos, permisos por rol aplicados a reportes y comunicaciones, e historial de intervenciones de alertas.

### Frontend React

```powershell
Set-Location frontend
npm install
Copy-Item .env.example .env
npm run dev
```

El panel estará en `http://localhost:5173`. La interfaz “Nexo” usa TypeScript, React Router, TanStack Query/Table, React Hook Form, Zod, Zustand, Axios, Lucide y Sonner. Incluye navegación protegida, vistas adaptadas por rol, formularios CRUD, búsqueda, paginación y estados accesibles de carga, error y ausencia de datos.

Para validar el frontend:

```powershell
npm run typecheck
npm run lint
npm run test
npm run build
npm run e2e
```

## Autenticación y roles

Antes de crear usuarios, define un `SECRET_KEY` largo y aleatorio en `.env`.

1. En una instalación sin usuarios, llama una sola vez a `POST /auth/bootstrap` para crear el administrador inicial.
2. Inicia sesión mediante `POST /auth/login` usando nombre de usuario o correo y contraseña.
3. Envía el token devuelto como `Authorization: Bearer <token>`.

Los administradores gestionan programas, pensum, períodos, personas, oferta de secciones, roles y usuarios. La inscripción queda como relación interna: el administrador asigna un docente y una asignatura a cada sección, y el estudiante elige una sección disponible desde su catálogo. Docentes y administradores pueden registrar notas. Las consultas generales requieren autenticación. Las contraseñas se almacenan con `scrypt` y nunca se incluyen en las respuestas. El access token se conserva solo durante la pestaña y se renueva mediante una cookie `HttpOnly`; cerrar sesión revoca la sesión de renovación.

La API limita intentos repetidos de acceso, permite cambiar la contraseña y registra eventos de seguridad en el historial de auditoría (`GET /audit/`, solo administración). Si una persona olvida su contraseña, un administrador puede establecer una nueva desde la gestión de usuarios sin exponer la anterior.

Además, estudiantes solo pueden consultar su expediente, horario, notas y asistencia. Docentes solo acceden a estudiantes, inscripciones, notas y asistencias pertenecientes a sus secciones.

Los permisos configurables complementan el rol y se aplican tanto en la API como en el menú. El catálogo institucional incluye `academic.manage` (configuración, oferta y pensum), `grades.manage` (evaluaciones, notas y asistencia), `finance.manage` (cuentas y caja), `operations.manage` (agenda, tareas y procesos institucionales), `reports.view` (analítica y auditoría), `communications.manage` (avisos) y `access.manage` (usuarios, roles y permisos). Un administrador puede asignarlos por rol desde **Roles y permisos**. Las instalaciones antiguas conservan compatibilidad por rol hasta ejecutar las migraciones y configurar su catálogo.

## Consultas académicas

### Expediente estudiantil

El directorio permite buscar por nombre completo, matrícula, correo o documento y combinar filtros de programa, estado y bloqueos. Cada expediente organiza el resumen institucional, los datos personales, el historial académico por período y los tutores/contactos de emergencia.

La migración `20261010_0024` incorpora campos opcionales de documento de identidad, nacimiento, nacionalidad, fecha de ingreso, centro de procedencia y contacto de emergencia. Los registros anteriores se conservan. El cargador institucional incluye información ficticia para estos campos.

Los promedios del expediente se calculan con las notas registradas y pueden incluir evaluaciones en proceso. La auditoría de graduación y la cuenta financiera se consultan desde sus accesos específicos.

### Expediente docente

El directorio docente permite buscar por nombre completo, código, especialidad, departamento, correo o documento y combinar filtros de departamento, estado y tipo de vinculación. El expediente reúne identificación, formación, experiencia, categoría docente, vinculación y contacto de emergencia.

La migración `20261010_0025` incorpora estos campos opcionales y conserva los docentes existentes. El cargador institucional incluye información ficticia para los seis docentes de Horizonte.

`GET /teachers/{id}/workload` muestra secciones, horario y estudiantes atendidos sin duplicarlos, por período. Por defecto utiliza el período vigente; `period=` permite consultar el acumulado. Las horas se calculan a partir de los encuentros semanales o, si no existen, del horario de la sección. Los indicadores excluyen las secciones cerradas y canceladas. El acceso conserva el ámbito de administración o del propio docente.

- `GET /academic/students/{id}/grades`: historial de notas, con filtro por período.
- `GET /academic/students/{id}/schedule`: horario del estudiante.
- `GET /academic/teachers/{id}/schedule`: horario del docente.
- `GET /academic/catalog`: oferta disponible según el pensum del estudiante.
- `POST /academic/catalog/sections/{id}/select`: selección de una sección por el estudiante.
- `GET /academic/sections/{id}/students`: estudiantes inscritos por sección.
- `/attendances`: CRUD de asistencia sujeto al ámbito del docente.

Los listados aceptan paginación mediante `skip` y `limit`; los catálogos y personas incluyen `q`, mientras inscripciones y notas ofrecen filtros propios.

## Flujos funcionales disponibles

- Expediente integral por estudiante con carrera, inscripciones, promedio y asistencia.
- Espacio de trabajo por sección para pasar lista y registrar notas en grupo.
- Paneles de asistencia y calificaciones agrupados por sección, con promedios generales e historial desplegable por estudiante.
- Horarios personales en lista o cuadrícula semanal, con formato de 12 o 24 horas.
- Períodos académicos por bimestre, trimestre, cuatrimestre, semestre o año.
- Carreras con código, nivel, título otorgado, duración y pensum por créditos.
- Matrículas automáticas configurables y detección de choques de horario.
- Pensum por carrera con créditos, orden recomendado y prerrequisitos.
- Progreso del estudiante con materias aprobadas, cursando y pendientes.
- Paneles operativos específicos para administración, docentes y estudiantes.
- Importación y exportación de estudiantes mediante CSV.
- Control financiero interno con cargos, abonos, balance, vencimientos e historial.
- Evaluaciones ponderadas con cierre y reapertura controlada.
- Selección estudiantil de asignaturas con cupos, espera, bloqueos, prerrequisitos y límite de créditos; la inscripción técnica se administra en segundo plano.
- Resumen de carga académica, retiro dentro de plazo, estados de sección y correquisitos.
- Pensum versionado con asignaturas obligatorias, electivas, pasantías y trabajo de grado.
- Equivalencias entre asignaturas, historial de cambios de carrera y auditoría de graduación.
- Aulas, reuniones semanales y asistencia con tardanza o justificación.
- Tutores, avisos internos, notificaciones privadas y documentos PDF.
- Calendario institucional, planes de clase, tareas, entregas y retroalimentación.
- Alertas tempranas académicas, de asistencia y financieras.
- Admisiones, aprobaciones y expediente digital de archivos.
- Conceptos de facturación, cierres de caja y analítica institucional.
- Permisos configurables por rol y portal familiar para tutores vinculados.

El módulo financiero es un libro de control interno. No procesa tarjetas, transferencias ni cobros mediante una pasarela externa.

### Formato CSV de estudiantes

El archivo de importación debe usar UTF-8 y contener estas columnas:

```text
first_name,last_name,email,telephone,address,career_id,enrollment_number,active
```

`enrollment_number` y `active` son opcionales. Si la matrícula queda vacía, se genera según la configuración institucional.

## Pruebas

Las pruebas CRUD usan una base SQLite temporal en memoria y no modifican `school.db`:

```powershell
python -B -m pytest tests -q -p no:cacheprovider
```

La verificación completa ejecuta lint, formato, cobertura, pruebas, Alembic y frontend:

```powershell
.\scripts\check.ps1
```

Las pruebas de navegador comprueban además el acceso y espacio de trabajo de administración, docencia, estudiante y tutor:

```powershell
Set-Location frontend
npm run e2e
```

Para ejecutar las mismas suites contra PostgreSQL (el esquema `public` de esa base se
borra y se recrea en cada prueba, usa una base descartable):

```powershell
$env:NEXO_TEST_DATABASE_URL = "postgresql+psycopg://usuario@localhost:5432/nexo_pruebas"
python -B -m pytest tests -q -p no:cacheprovider
```

La misma verificación está configurada en `.github/workflows/backend-quality.yml`,
que además aplica las migraciones, ejecuta `alembic check` y corre la suite completa
sobre PostgreSQL 16.
La automatización de CI también ejecuta navegador con API simulada y con un
backend real. En local, `npm run e2e` usa la interfaz en `127.0.0.1:5177` y
responde con datos simulados. `npm run e2e:acceptance` usa la interfaz en
`127.0.0.3:5176`, la API en `127.0.0.3:8012` y una base ficticia nueva
en `backups/acceptance-<id>/acceptance.db`.

## Operación del portal y la API

En Agenda y tareas, cada intento admite texto, un adjunto o ambos. El archivo
puede ser PDF, PNG o JPEG de hasta 5 MiB. Consulta y descarga los archivos
desde el historial de intentos de la entrega.

En Elegir asignaturas, agrega al carrito las dos secciones que son correquisitos
recíprocos. La confirmación de la pareja requiere plaza en ambas secciones.

Para consultar la API desde Swagger usa una sesión de pruebas separada y
autoriza el token en Swagger. Una respuesta `401` indica que la credencial
falta, expiró o fue revocada. Una respuesta `403` indica que la cuenta no
tiene permiso para la operación o para ese registro.

Los directorios de usuarios, períodos, pensum, selecciones y notas conservan
las respuestas como listas. Cuando se envían `skip` y `limit`, las cabeceras
`X-Total-Count` y `X-Has-More` corresponden a los registros que cumplen los
filtros de la consulta. Para obtener el período vigente sin recorrer la lista
usa `GET /periods/?active=true&limit=1`.

Mi seguridad permite activar o sustituir el autenticador, desactivarlo y
consultar sesiones renovables. Cambiar la contraseña, restablecerla desde
Usuarios, cambiar el segundo factor o cerrar todas las sesiones invalida
los tokens de acceso y renovación anteriores de la cuenta. El cierre
individual revoca la renovación de esa sesión y deja expirar su token
de acceso.

## Restauración SQLite

Crea una copia con `python -B -m scripts.backup_database`. Para comprobar
una restauración usa un archivo nuevo distinto del original.

```powershell
python -B -m scripts.backup_database --restore backups/respaldo-qa.db --destination backups/restauracion-qa.db
```

El comando comprueba la integridad y las claves foráneas. Para inspeccionar
la restauración con Alembic o levantar una API de prueba, configura
`DATABASE_URL` con el archivo restaurado en una sesión dedicada.

## Migraciones

Alembic está configurado para leer la misma `DATABASE_URL` de la aplicación.

- Base nueva y vacía: `alembic upgrade head`
- Base existente creada antes de Alembic: respáldala, verifica que su esquema coincida y ejecuta `alembic stamp head` una sola vez.
- Nueva migración: `alembic revision --autogenerate -m "descripcion"`

No ejecutes `upgrade head` sobre una base existente sin revisar primero el estado: la migración inicial crea todas las tablas.

`school.db` permanece versionado y `.gitignore` evita añadir nuevas bases locales no rastreadas. Antes de registrar las revisiones de Alembic se creó `school.db.bak`, ignorada por Git, como copia de seguridad local.

### Estado de la base incluida

La base incluida fue actualizada hasta `20260921_0017`. Las conexiones nuevas activan `PRAGMA foreign_keys=ON`. El historial completo de revisiones conserva la carrera temporal `Sin asignar` para datos heredados y añade seguridad, períodos, pensum, finanzas, evaluaciones, selección académica, horarios, asistencia, comunicaciones y operación institucional.

La revisión `20260918_0015` agrega metadatos universitarios a carreras y períodos sin eliminar los registros existentes.
La revisión `20260921_0016` agrega gobierno académico: estados de secciones, cupos mínimos, versión de pensum, correquisitos y tipos de asignatura.
La revisión `20260921_0017` incorpora equivalencias curriculares e historial formal de cambios de carrera.

## PostgreSQL y contenedores

El desarrollo local puede continuar con SQLite. Para validar una configuración cercana a producción con PostgreSQL:

```powershell
docker compose up --build
```

La API estará en `http://localhost:8000` y Nexo en `http://localhost:3000`. Antes de cualquier despliegue real cambia las contraseñas del compose, define un `SECRET_KEY` aleatorio, configura HTTPS y utiliza un gestor de secretos. Los volúmenes de PostgreSQL deben incluirse en la estrategia de copias de seguridad.

Configura `APP_ENVIRONMENT=production`, un `SECRET_KEY` aleatorio de al menos
32 caracteres y `CORS_ORIGINS` con los orígenes HTTPS permitidos, separados por
comas. En este modo la cookie de renovación lleva el atributo `Secure`.

Otras variables de producción:

| Variable | Uso |
|---|---|
| `BOOTSTRAP_TOKEN` | Obligatoria para crear el primer administrador con `POST /auth/bootstrap` en producción; se envía en la cabecera `X-Bootstrap-Token`. Sin ella, la ruta está deshabilitada en producción. |
| `FORWARDED_ALLOW_IPS` | IP del proxy inverso de confianza. uvicorn corre con `--proxy-headers`, así el límite de intentos de login usa la IP real del cliente. |
| `LOG_LEVEL` | Nivel de los logs JSON en stdout (`INFO` por defecto). Cada respuesta lleva `X-Request-ID`. |

La cadena completa de migraciones requiere una conexión a la base. Las revisiones
históricas inspeccionan el esquema y los datos durante el upgrade, por lo que
`alembic upgrade head --sql` falla. Para validar PostgreSQL ejecuta el upgrade
online en una base descartable y confirma la revisión con `alembic current`.

`school.db` ya no se versiona (18/11/2026); las copias anteriores siguen en el
historial de Git.
