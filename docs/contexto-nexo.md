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
- **A1.** Desactivar a un estudiante o docente (`active = False`) no le quita el acceso: `get_current_user`, `login` y `refresh` no lo comprueban.
- **A2.** `User` no tiene campo `active`; borrar un usuario con historial falla (27 claves foráneas apuntan a `users`) y la API responde un 409 genérico.

### Medios
- **M1.** Las comprobaciones de ámbito usan `is_admin()` por nombre de rol: los roles personalizados con permiso (p. ej. `finance.manage`) reciben 403 al leer.
- **M2.** `student_scope_ids` (alertas) devuelve `None` (= todo) para usuarios no admin sin vínculo.
- **M3.** `access.manage` permite restablecer la contraseña de un admin o crear admins.
- **M4.** Límite de login por usuario, en memoria: permite bloquear al admin y no funciona con varios workers.
- **M5.** Los tutores no pueden descargar documentos de sus hijos.
- **M6.** 97 mensajes de error del API en inglés que llegan a la interfaz.
- **M7.** Un único bloqueo global para todas las escrituras.
- **M8.** Consultas N+1 o de tabla completa en cuentas financieras, cierre de caja y alertas.

### Bajos
Montos en `Float`, TOTP reutilizable dentro de su ventana, enumeración de usuarios por tiempo, sin detección de reutilización del refresh token, `/auth/bootstrap` abierto en una instalación vacía, sin logs, nginx sin cabeceras de seguridad, `school.db` y `__pycache__` versionados, `date_recorded` como texto, períodos enlazados por nombre. PostgreSQL sin probar de punta a punta.

### Frontend y UI
Contraste insuficiente (`--muted` #718096 → usar #5b6678), código compactado sin Prettier, colores escritos a mano en 25 CSS con dos paletas mezcladas, `window.confirm` nativo, fuentes por `@import`, tipos del API escritos a mano (generarlos con `openapi-typescript`). No hace falta un rediseño completo: basta con un sistema de diseño con tokens.

## 3. Hoja de ruta
Cada fase se cierra con pruebas de regresión y sin romper lo anterior.

### Fase 0: dejar perfecto lo actual
1. Acceso: A1, A2, M2, M3.
2. Permisos y portal: M1, M5.
3. Calidad y UX: Prettier/Ruff, mensajes en español, contraste, tokens de diseño, modales, tipos generados.
4. Producción: M4 (Redis), M7, M8, bajos y una prueba completa sobre PostgreSQL.

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
