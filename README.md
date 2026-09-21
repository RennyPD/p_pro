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

## Consultas académicas

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
python -m unittest discover -s tests -v
```

La verificación completa ejecuta lint, formato, cobertura, pruebas, Alembic y frontend:

```powershell
.\scripts\check.ps1
```

La misma verificación está configurada en `.github/workflows/backend-quality.yml`.

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

Si Docker no está disponible, todavía puedes revisar que Alembic genere SQL compatible con PostgreSQL sin conectarse a una base:

```powershell
$env:DATABASE_URL='postgresql+psycopg://p_pro:local-development-only@localhost:5432/p_pro'
alembic upgrade head --sql
Remove-Item Env:DATABASE_URL
```
