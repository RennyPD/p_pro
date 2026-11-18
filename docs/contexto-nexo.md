# Nexo: contexto del sistema y hoja de ruta

Última revisión: 17 de noviembre de 2026. Repo: `RennyPD/p_pro`.

## 1. Qué es hoy
Sistema de gestión académica de una sola institución, muy orientado a universidades. Unas 14.000 líneas de backend (242 rutas, 53 modelos) y 82 archivos de frontend.

### Módulos existentes
- **Académico:** carreras, pensum versionado con prerrequisitos y correquisitos, asignaturas, secciones, aulas y bloques horarios, períodos académicos con cierre controlado, equivalencias, auditoría de graduación.
- **Inscripción:** catálogo, carrito, lista de espera; valida cupos, créditos, prerrequisitos, choques de horario, ventana de registro y bloqueos académicos y financieros.
- **Evaluación:** evaluaciones ponderadas, libro de notas, publicación, historial de cambios de nota, plazos de calificación.
- **Asistencia,** tareas y entregas (PDF/PNG/JPEG hasta 5 MiB), planes de clase, agenda.
- **Finanzas:** conceptos de cobro, cargos, pagos idempotentes, reversos auditados, planes de pago, transferencias con comprobante, cierre de caja.
- **Comunidad:** portal de tutores (padres), alertas tempranas, casos institucionales, aprobaciones, admisiones, comunicaciones.
- **Plataforma:** usuarios, roles y permisos configurables, módulos por rol personalizado, 2FA (TOTP), sesiones revocables, auditoría, importación masiva con prevalidación, PDF (boletines, constancias, expedientes), exportes CSV.

### Arquitectura
- `app/models` (SQLAlchemy), `app/schemas` (Pydantic), `app/routers`, `app/services`, `app/repositories`, `alembic/`.
- Autenticación: JWT de acceso de 30 min + refresh token rotativo en cookie HttpOnly; contraseñas con scrypt; versión de sesión para revocar.
- Escrituras críticas serializadas con `lock_governance` (una fila global).
- `frontend/src/features/<módulo>`, componentes en `components/ui.tsx`, cliente en `lib/api.ts`.
- La documentación funcional está en `docs/` (manual, guías por módulo y registros de correcciones).

## 2. Auditoría del 17/11/2026: pendientes
Informe completo: `docs/auditoria/auditoria-2026-11-17.pdf` (versión web: https://claude.ai/artifact/HEqmZ157CfCEaCHRHBmb1g)

### Altos
- ✅ **A1** (cerrado 17/11/2026). Desactivar a un estudiante o docente (`active = False`) no le quita el acceso: `get_current_user`, `login` y `refresh` no lo comprueban.
- ✅ **A2** (cerrado 17/11/2026: `User.active`, `POST /users/{id}/deactivate` y `/activate`, 409 explicativo al borrar con historial). `User` no tenía campo `active`; borrar un usuario con historial falla (27 claves foráneas apuntan a `users`) y la API responde un 409 genérico.

### Medios
- ✅ **M1** (cerrado 18/11/2026: `has_scope` en `app/auth.py` decide el ámbito institucional por permisos; `academic.manage`/`reports.view` para lo académico, `finance.manage`/`reports.view` para finanzas; migración 0039 da al rol `admin` todos los permisos). Las comprobaciones de ámbito usan `is_admin()` por nombre de rol: los roles personalizados con permiso (p. ej. `finance.manage`) reciben 403 al leer.
- ✅ **M2** (verificado con prueba de regresión 17/11/2026). `student_scope_ids` (alertas) devuelve `None` (= todo) para usuarios no admin sin vínculo.
- ✅ **M3** (cerrado 17/11/2026: nadie gestiona cuentas ni concede permisos por encima de los suyos). `access.manage` permitía restablecer la contraseña de un admin o crear admins.
- ✅ **M4** (cerrado 18/11/2026: tabla `login_throttles`, claves IP+usuario e IP; uvicorn con `--proxy-headers`, configurar `FORWARDED_ALLOW_IPS` detrás de un proxy). Límite de login por usuario, en memoria: permite bloquear al admin y no funciona con varios workers.
- ✅ **M5** (cerrado 18/11/2026: `ensure_student_document_access` y sección de documentos en el portal familiar). Los tutores no podían descargar documentos de sus hijos.
- ✅ **M6** (cerrado 18/11/2026: mensajes del API, validadores y errores 422 en español; `tests/test_spanish_messages.py` impide que vuelvan). 97 mensajes de error del API en inglés que llegan a la interfaz.
- ✅ **M7** (parcial, 18/11/2026: bloqueos por clave `write_locks` con formato `<institución>:<dominio>`; accesos y finanzas separados de lo académico. **Pendiente:** dividir el dominio académico tras auditar sus invariantes). Un único bloqueo global para todas las escrituras.
- ✅ **M8** (cerrado 18/11/2026: cuentas con `selectinload`, cierre de caja por rango indexado, alertas con join; `tests/test_query_counts.py`). Consultas N+1 o de tabla completa en cuentas financieras, cierre de caja y alertas.

### Bajos
~~Montos en `Float`~~ (✅ 18/11: `Numeric(12,2)` y `Decimal`, migración 0042), ~~TOTP reutilizable dentro de su ventana~~ (✅ 18/11), ~~enumeración de usuarios por tiempo~~ (✅ 18/11: hash de relleno), ~~sin detección de reutilización del refresh token~~ (✅ 18/11), ~~`/auth/bootstrap` abierto en una instalación vacía~~ (✅ 18/11: `BOOTSTRAP_TOKEN` en producción), ~~sin logs~~ (✅ 18/11: logs JSON con `X-Request-ID`), ~~nginx sin cabeceras de seguridad~~ (✅ 18/11), ~~`school.db` y `__pycache__` versionados~~ (✅ 18/11), ~~`date_recorded` como texto~~ (✅ 18/11, migración 0044), períodos enlazados por nombre (**pendiente**: pasar `period_name` a `period_id`; toca secciones, inscripciones y reportes, conviene hacerlo al empezar la Fase 1). ~~PostgreSQL sin probar de punta a punta~~ (✅ 18/11: migraciones corregidas, `alembic check` limpio y suite completa en PostgreSQL en CI; se corrigieron 2 migraciones y 2 consultas que fallaban en PostgreSQL).

### Frontend y UI
✅ Cerrado el 18/11/2026 (Fase 0, paso 3):
- Prettier 3.3.3 en todo el frontend, comprobado en CI (`npm run format:check`).
- Tokens de diseño en `src/styles.css`; sin colores escritos a mano en los CSS (lo vigila `src/test/design-tokens.test.ts`). `--muted` = #5b6678.
- Diálogo de confirmación propio (`confirmAction` en `src/lib/confirm.ts`), sin `window.confirm`.
- Fuentes con `<link>` en `index.html`, no con `@import`.
- Tipos del API generados con `openapi-typescript` (`npm run api:types` → `src/lib/api-schema.d.ts`, usados con `ApiSchema<"Nombre">`). `User` y `TokenResponse` ya los usan. **Pendiente:** migrar los demás tipos escritos a mano en `src/features/*` módulo por módulo; varias rutas devuelven diccionarios sin `response_model` y necesitan esquema antes de poder tiparse.

## 3. Hoja de ruta
Cada fase se cierra con pruebas de regresión y sin romper lo anterior.

### Fase 0: dejar perfecto lo actual
1. ✅ Acceso: A1, A2, M2, M3.
2. ✅ Permisos y portal: M1, M5.
3. ✅ Calidad y UX: Prettier/Ruff, mensajes en español, contraste, tokens de diseño, modales, tipos generados (queda la migración progresiva de tipos por módulo).
4. ✅ Producción: M4 (en base de datos, sin Redis), M7 (parcial), M8, bajos (salvo períodos por nombre) y prueba completa sobre PostgreSQL en CI.

### Fase 1: modelo escolar (K-12)
- Tipo de institución configurable: `university` | `school` (o ambos).
- Grados/cursos y secciones fijas con alumnos asignados (sin selección libre).
- Inscripción y reinscripción anual; promoción de grado.
- Escala de calificación configurable (0–100, A–F, conceptual) y períodos por trimestre o bimestre.
- Boletines en el formato del MINERD (República Dominicana) y reportes por período.
- Más peso al portal de padres: notas, asistencia, tareas, pagos y comunicaciones.
- Reutilizar todo lo común (asistencia, finanzas, tareas, comunicaciones, documentos) detrás de la configuración.

### Fase 2: SaaS
- Multi-tenant: `institution_id` en todos los modelos y consultas (o una base por cliente), unicidad por institución, bloqueos por institución.
- Alta de instituciones (onboarding), subdominio por cliente.
- Email transaccional: invitaciones, recuperación de contraseña, notificaciones.
- Planes, límites por plan, suscripciones y pagos (Stripe o PayPal y una pasarela local como Azul o CardNet), periodo de prueba y suspensión por impago.
- Archivos fuera de la base (S3 o compatible), Redis, logs estructurados, Sentry, backups de PostgreSQL.
- Panel de superadmin (todas las instituciones).

### Fase 3: lanzamiento
Landing page, términos de uso, política de privacidad (datos de menores), documentación para clientes, demo pública.
