# Nexo: contexto del sistema y hoja de ruta

Última revisión: 20 de noviembre de 2026. Repo: `RennyPD/p_pro`.

## 1. Qué es hoy
Sistema de gestión académica de una sola institución, muy orientado a universidades. Unas 14.800 líneas de backend (245 rutas, 53 tablas) y 16.700 de frontend. Fase 0 cerrada el 18/11/2026; Fase 1 cerrada el 21/11/2026.

### Módulos existentes
- **Académico:** carreras, pensum versionado con prerrequisitos y correquisitos, asignaturas, secciones, aulas y bloques horarios, períodos académicos con cierre controlado, equivalencias, auditoría de graduación.
- **Inscripción:** catálogo, carrito, lista de espera; valida cupos, créditos, prerrequisitos, choques de horario, ventana de registro y bloqueos académicos y financieros.
- **Evaluación:** evaluaciones ponderadas, libro de notas, publicación, historial de cambios de nota, plazos de calificación.
- **Asistencia,** tareas y entregas (PDF/PNG/JPEG hasta 5 MiB), planes de clase, agenda.
- **Finanzas:** conceptos de cobro, cargos, pagos idempotentes, reversos auditados, planes de pago, transferencias con comprobante, cierre de caja.
- **Comunidad:** portal de tutores (padres), alertas tempranas, casos institucionales, aprobaciones, admisiones, comunicaciones.
- **Plataforma:** usuarios, roles creados por la institución con permisos granulares (unos 30, de consulta y gestión por módulo; catálogo en `app/permissions.py`) y ámbito de datos por rol (institución, sus secciones, su expediente, estudiantes vinculados), módulos de consulta de la oferta académica con el permiso `programs.view`, 2FA (TOTP), sesiones revocables, auditoría, importación masiva con prevalidación, PDF (boletines, constancias, expedientes), exportes CSV.

### Arquitectura
- `app/models` (SQLAlchemy), `app/schemas` (Pydantic), `app/routers`, `app/services`, `app/repositories`, `alembic/`.
- Autenticación: JWT de acceso de 30 min + refresh token rotativo (con detección de reutilización) en cookie HttpOnly; contraseñas con scrypt; 2FA de un solo uso; límite de intentos en base de datos.
- Acceso por permisos y ámbito (`has_scope`, funciones `ensure_*` en `app/auth.py`).
- Escrituras críticas serializadas con bloqueos por clave (`app/services/write_locks.py`): `academic`, `access`, `finance`.
- Logs JSON en stdout con `X-Request-ID`. Pruebas en SQLite y PostgreSQL (CI).
- `frontend/src/features/<módulo>`, componentes en `components/ui.tsx`, cliente en `lib/api.ts`.
- La documentación funcional está en `docs/` (manual, guías por módulo y registros de correcciones).

## 2. Auditoría vigente: 20/11/2026 (medida de nuevo el 21/11 sobre `master`)
Informe completo: `docs/auditoria/auditoria-2026-11-20.md`. La auditoría del 17/11/2026 (`docs/auditoria/auditoria-2026-11-17.pdf`) quedó cerrada con la Fase 0 salvo B5 y B6.

| Id | Hallazgo | Fase |
|---|---|---|
| A1 | Vínculo tutor–estudiante sin permisos ni auditoría (privacidad de menores) | 2 |
| A2 | ✅ Cerrado (21/11): toda ruta de escritura registra auditoría; `tests/test_route_audit.py` lo vigila | — |
| M1 | ✅ Cerrado en `master` (20/11): permisos granulares por ruta y menú por permisos | — |
| M2 | ✅ Cerrado (21/11): toda ruta de escritura toma el bloqueo de su dominio; `tests/test_route_locks.py` | — |
| M3 | ✅ Cerrado (21/11): los listados filtran y paginan en SQL (`search`, `page_query`) | — |
| M4 | Archivos dentro de la base (5 columnas binarias) | 4 |
| M5 | ✅ Cerrado (21/11): copia y restauración de PostgreSQL verificadas en CI | — |
| M6 | Sin correo: recuperación de contraseña, invitaciones, avisos | 2 |
| M7 | Finanzas incompletas para escuelas (los planes de cobro ya existen) | 2 (vista y pagos) y 3 (facturación) |
| M8 | Portales de tutor y estudiante densos y sin desglose en móvil | 2 |
| M9 | Pruebas del frontend escasas; componentes de más de 1.000 líneas | continuo |
| B3, B4, B8 | ✅ Cerrados (21/11): cobertura de auditoría, panel y permisos al 94–100 %; módulos de consulta por permisos; código muerto de notas eliminado | — |
| B1, B2, B5–B7 | Tipos a mano, build pesado, períodos por nombre, bloqueo académico único, límites solo en login | según fase |
| SaaS | 16 unicidades globales, configuración de una fila, catálogos sin filtro | 4 |

### Historial: auditoría del 17/11/2026
Cerrados en la Fase 0 (18/11/2026): A1, A2, M1–M6, M8, M7 parcial (bloqueos por clave), bajos de seguridad y datos (Float→Numeric, TOTP, refresh, bootstrap, nginx, logs, `date_recorded`, `school.db`), PostgreSQL de punta a punta, Prettier, mensajes en español, tokens de diseño, diálogo propio y tipos generados.

## 3. Hoja de ruta (reconstruida el 20/11/2026)
Cada fase se cierra con pruebas de regresión, capturas antes/después en lo visual y sin romper lo anterior. Tamaño relativo: S (días), M (1–2 semanas), L (varias semanas).

### Fase 0: dejar perfecto lo actual ✅ (18/11/2026)

### Fase 1: cimientos de confianza (M) ✅ (21/11/2026)
Lo que hace falta para que cualquier cliente confíe en los datos. Base para todo lo demás.
1. ✅ **Auditoría completa (A2), 21/11/2026:** `record(...)` en todas las rutas de escritura, en la misma transacción que el cambio (los repositorios hacen `flush()`); `tests/test_route_audit.py` falla si una ruta nueva no registra nada y `tests/test_write_audit.py` comprueba actor y detalle en los casos críticos. Regla 11 ampliada. La medición real eran unas 45 rutas: asistencia, autenticación, finanzas y notas ya tenían su propio historial.
2. ✅ **Vistas de módulo por permisos (B4):** las concesiones por cuenta (`users.module_views`) pasan a permisos del rol con la migración `20261121_0048`; carreras, asignaturas y períodos se consultan con el nuevo `programs.view`.
3. ✅ **Bloqueos (M2):** asistencia, estudiantes, carreras, asignaturas, docentes, secciones, tutores, equivalencias, calendario, documentos y conceptos de cobro bajo el bloqueo de su dominio; prueba guardiana `tests/test_route_locks.py`.
4. ✅ **Paginación en la base (M3)** en estudiantes, docentes, secciones, carreras, asignaturas y roles, con `X-Total-Count`.
5. ✅ **Copias de seguridad de PostgreSQL (M5):** `pg_dump`/`pg_restore` en `scripts/backup_database.py`, restauración solo en una base vacía y comparación de filas; probado en CI contra PostgreSQL 16. Procedimiento en el README.
6. ✅ **Cobertura (B3) y código muerto (B8):** auditoría, panel y módulos al 100 %, editor de permisos al 94 %; eliminados `grade_repository` y las escrituras de notas sin bloqueo ni historial; `objetivos.txt` movido a `docs/historico/`. Queda pendiente unificar del todo las capas `repositories`/`services`, que no bloquea nada.

### Fase 2: familias, pagos y experiencia (L)
Lo que se ve y lo que piden las familias. Funciona con los datos actuales.
1. **Sistema visual:** componentes reutilizables (tarjeta, indicador, chip, estado, avatar, pestañas, progreso) y criterio de «menos texto»; móvil primero en portales. ✅ Primer caso: tarjeta de tareas.
2. **Vínculo tutor–estudiante con permisos (A1):** responsable de pago, ve notas, ve asistencia, ve finanzas; auditado. Por defecto ve lo académico y lo financiero solo si es responsable de pago (pendiente de confirmar).
3. **Portal del tutor detallado (M8):** vista familiar y pestañas por hijo con notas por asignatura y evaluación, asistencia por día y materia, tareas, horario, alertas, comunicados y documentos.
4. **Módulo de pagos para estudiante y tutor (M7, M8):** balance, próximo vencimiento, cuotas, movimientos, recibos y reporte de transferencia; total familiar con desglose por hijo y concepto, y una transferencia para varios hijos. Si el estudiante menor ve sus finanzas lo decide cada institución (por defecto: no en escuelas, sí en universidades; pendiente de confirmar).
5. **Correo electrónico (M6):** recuperación de contraseña, invitaciones y avisos (comunicados, vencimientos, notas publicadas) con un proveedor configurable.
6. **Rediseño de pantallas clave** con el sistema visual: panel principal, «Mi cuenta», finanzas de administración; dividir los componentes de más de 1.000 líneas (M9) y migrar sus tipos a `ApiSchema` (B1).

### Fase 3: modelo escolar (L)
1. **Períodos por id (B5)** y año lectivo con trimestres o bimestres.
2. **Tipo de institución** (`university` | `school` | ambos) como configuración.
3. **Grados y secciones fijas**, inscripción y reinscripción anual, promoción de grado.
4. **Escala de calificación configurable** (0–100, A–F, conceptual).
5. **Finanzas escolares (M7):** planes de cobro por grado y año (ya existen por carrera desde el 20/11) con generación programada; cuenta familiar y descuento por hermanos; reglas de mora y bloqueo automático; cajero y supervisor separados; reportes de morosidad e ingresos.
6. **Boletines MINERD** y reportes por período.
7. **Bloqueo académico por sección y período (B6)** cuando las invariantes escolares estén definidas.

### Fase 4: SaaS (L)
- Multi-tenant: `institution_id` en modelos y consultas, las 16 unicidades por institución, configuración por institución, catálogos filtrados, bloqueos por institución (ya preparados).
- Alta de instituciones (onboarding) y subdominio por cliente; panel de superadmin.
- Planes, límites, suscripciones, prueba gratuita y suspensión por impago (Stripe o PayPal y Azul o CardNet).
- Pagos en línea para familias, comprobantes fiscales (NCF/e-CF) con un proveedor autorizado y moneda por institución.
- Archivos en almacenamiento de objetos (M4), Redis si hace falta, Sentry, límites de peticiones en subidas e importaciones (B7), build ligero (B2).

### Fase 5: lanzamiento (M)
Landing page, demo pública, términos de uso, política de privacidad conforme a la Ley 172-13 con atención a datos de menores, documentación para clientes y soporte.

### Decisiones pendientes del dueño del producto
1. Visibilidad por defecto del tutor (propuesta: académico sí, financiero solo si es responsable de pago).
2. ¿El estudiante menor ve sus finanzas? (propuesta: configurable; no en escuelas, sí en universidades).
3. Proveedor de correo y de comprobantes fiscales.
