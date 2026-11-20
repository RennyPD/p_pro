# Auditoría de Nexo: 20 de noviembre de 2026

Segunda auditoría completa, tras cerrar la Fase 0. Revisa el código de la rama `claude/fervent-faraday-xgto0d` (commit `ed454f0`) con mediciones automáticas y comprobaciones manuales. Sustituye como referencia a la auditoría del 17/11/2026 (`auditoria-2026-11-17.pdf`), cuyos hallazgos se cerraron salvo los indicados.

## Resumen

Nexo es hoy una base técnica sólida para **una sola institución universitaria**: autenticación robusta, permisos por ámbito, pruebas en SQLite y PostgreSQL, 90 % de cobertura en el backend y registros de errores. Para venderlo a escuelas y como SaaS faltan tres cosas, en este orden:

1. **Trazabilidad y permisos completos.** 47 rutas de escritura no dejan registro de auditoría, 32 escriben sin bloqueo y 15 rutas, más el menú del frontend, siguen decidiendo por nombre de rol.
2. **Familias, pagos y experiencia móvil.** El portal del tutor es una sola página larga sin desglose por hijo; no hay módulo de pagos para tutor ni estudiante, ni correo electrónico (recuperación de contraseña, avisos).
3. **Modelo escolar y multi-tenant.** No existen grados, años lectivos ni facturación recurrente; 16 restricciones de unicidad son globales y la configuración es una sola fila.

## Cifras

| Medida | Valor |
|---|---|
| Backend | 14.805 líneas, 53 tablas, 245 rutas |
| Frontend | 16.688 líneas en componentes, 38 rutas de pantalla |
| Pruebas backend | 135 (SQLite y PostgreSQL 16 en CI), cobertura 90 % |
| Pruebas frontend | 78 en 24 archivos, 12 e2e |
| Rutas públicas | 5 (`/health` y autenticación), todas legítimas |
| Rutas autenticadas sin permiso explícito | 88; 75 aplican ámbito dentro de la función, 13 son catálogos |
| Escrituras sin registro de auditoría | 47 (heurística, verificadas a mano las críticas) |
| Escrituras sin bloqueo | 32 |
| Decisiones por nombre de rol | 15 rutas (`require_roles`) y 42 en el frontend |
| Restricciones de unicidad globales | 16 que deberían ser por institución |
| Tipos del API escritos a mano | 86 (solo 2 usan los tipos generados) |
| Build principal | 476 KB sin comprimir |

## Lo que está bien

- **Autenticación:** JWT de 30 minutos y refresh token rotativo con detección de robo; contraseñas con scrypt; 2FA con códigos de un solo uso; sesiones revocables; límite de intentos en base de datos por IP y usuario; sin enumeración de usuarios por tiempo; `/auth/bootstrap` protegido en producción.
- **Acceso a datos:** el ámbito institucional depende de permisos (`has_scope`); sin permiso ni vínculo el resultado es vacío; `access.manage` no puede escalar privilegios.
- **Datos:** dinero en `Numeric(12,2)` y `Decimal`, fechas tipadas, pagos idempotentes, reversos en lugar de borrados, cierre de caja.
- **Calidad:** mensajes 100 % en español vigilados por una prueba; Ruff y Prettier en CI; migraciones y `alembic check` limpios en PostgreSQL; logs JSON con `X-Request-ID`.
- **Interfaz:** tokens de diseño con contraste AA, diálogo de confirmación accesible, infraestructura de tipos generados.

## Hallazgos

### Altos

**A1. Privacidad de menores en el vínculo tutor–estudiante.** Cualquier tutor vinculado ve todo lo académico y financiero del estudiante; el vínculo no distingue responsable de pago, custodia ni permisos. Crear tutores y vínculos (`POST /community/guardians`, `POST /community/guardian-links`) no deja registro de auditoría ni usa bloqueo. En K-12 y con la Ley 172-13 de protección de datos de República Dominicana, esto debe resolverse antes de vender a escuelas.

**A2. Cambios sensibles sin auditoría.** Verificado a mano:
- `PATCH /students/{id}` cambia bloqueos académico y financiero y el estado activo sin registro (ni bloqueo).
- `POST /users/` crea cuentas sin registro; `POST/PATCH/DELETE /roles/` tampoco registra.
- Inscripciones (`POST/PATCH/DELETE /enrollments/`, selección y retiro en el catálogo) no guardan quién hizo el cambio.
- Importación masiva de estudiantes, cambios de pensum, carreras, asignaturas y docentes.

La regla 11 de `CLAUDE.md` exige `record(...)` en notas, finanzas, usuarios, permisos y períodos; las inscripciones y los bloqueos deberían añadirse a esa lista.

### Medios

**M1. Decisiones por nombre de rol.** 15 rutas usan `require_roles(...)`: gestión de tutores y vínculos, cambio de carrera, equivalencias, horarios, asignación de pensum, creación de tareas, vistas de módulo y portal familiar. Un rol personalizado (p. ej. «Coordinación») no puede usarlas aunque tenga permisos. El frontend decide menú y botones con `role_name === "admin"` en 42 lugares, así que oculta funciones a roles personalizados.

**M2. Escrituras sin bloqueo.** 32 rutas, entre ellas asistencia (solo la protege un índice único, no el cierre de período), edición y borrado de estudiantes, borrado de secciones, docentes, asignaturas, carreras, calendario, vínculos de tutor, equivalencias y subida de documentos.

**M3. Paginación en memoria.** 7 listados cargan la tabla entera y filtran en Python (`paginate_and_filter`): estudiantes, secciones, docentes, carreras, asignaturas, roles. Con varios miles de registros por institución será lento.

**M4. Archivos dentro de la base de datos.** 5 columnas `LargeBinary` (comprobantes, entregas, documentos) inflan la base y las copias de seguridad.

**M5. Copias de seguridad solo para SQLite.** `scripts/backup_database.py` usa `sqlite3`; no hay procedimiento para PostgreSQL.

**M6. Sin correo electrónico.** No hay recuperación de contraseña, invitaciones ni avisos; la administración restablece contraseñas a mano y las familias no reciben notificaciones.

**M7. Finanzas incompletas para una escuela.** La base es correcta, pero:
- Los conceptos de cobro son un catálogo: no generan mensualidades.
- No hay cuenta familiar ni descuento por hermanos.
- Recargos por mora y bloqueo financiero son manuales.
- Un solo permiso (`finance.manage`) permite cobrar, reversar el propio pago y cerrar caja.
- No hay reportes de morosidad, comprobantes fiscales (NCF/e-CF) ni pagos en línea.

**M8. Experiencia en los portales de familia y estudiante.** En un teléfono, el portal del tutor es una página de 1.930 px sin pestañas por hijo; los indicadores ocupan una tarjeta alta cada uno; los botones de descarga quedan desalineados; el horario es texto denso. «Mi cuenta» del estudiante muestra cuatro tarjetas de totales y un párrafo legal antes de los movimientos, sin próximo vencimiento ni acción principal. No hay módulo de pagos para el tutor.

**M9. Pruebas del frontend escasas.** 24 archivos de prueba para unas 16.700 líneas; comunidad no tiene ninguna y finanzas una sola para una página de 1.407 líneas. Tres componentes superan las 1.000 líneas (`FinancePages`, `OperationsPage`, `AssessmentsPage`).

### Bajos

- **B1.** 86 tipos del API escritos a mano y 19 usos de `any`; solo 2 usan `ApiSchema<...>`.
- **B2.** Build principal de 476 KB: las gráficas y librerías pesadas deberían cargarse al abrir la pantalla.
- **B3.** Cobertura baja en auditoría (37 %), panel (62 %), permisos (69 %) y `grade_repository` (30 %, posible código muerto).
- **B4.** Dos sistemas de acceso en paralelo: permisos por rol y vistas de módulo por cuenta (esta última decide con nombres de rol).
- **B5.** Períodos enlazados por nombre (`period_name`), pendiente desde la Fase 0.
- **B6.** El bloqueo académico sigue siendo uno solo (M7 de la auditoría anterior, parcial).
- **B7.** Solo el login tiene límite de peticiones; subidas, exportaciones e importación masiva no.
- **B8.** Restos heredados: capas `repositories`/`services` inconsistentes, `requierments.txt` (errata) y `objetivos.txt`.

### Bloqueantes para SaaS (no son errores hoy)

- 16 restricciones de unicidad globales que deben incluir la institución: códigos de carrera, asignatura y sección, nombres de período, aula y rol, correos de estudiante, docente, tutor y aspirante, matrícula, concepto de cobro, fecha de cierre de caja, número de recibo y referencia de transferencia.
- `institution_settings` es una sola fila; los catálogos (carreras, asignaturas, períodos, aulas) se leen sin filtro de institución.
- Los bloqueos ya usan claves `<institución>:<dominio>`.

## Método

- Inventario de rutas y dependencias de seguridad recorriendo la aplicación FastAPI.
- Análisis estático de las funciones de cada ruta de escritura (bloqueo y auditoría) y revisión manual de los casos críticos.
- Inventario de restricciones de unicidad desde los metadatos de SQLAlchemy.
- Cobertura con `coverage` sobre la suite completa.
- Capturas en un iPhone 13 emulado de los portales de tutor y estudiante con datos de `seed_institution`.
- Métricas del frontend: tamaño de componentes, tipos, pruebas y build.
