# CLAUDE.md: Nexo

Nexo es un sistema de gestión educativa que se venderá como SaaS. El objetivo es un producto completo para **universidades y escuelas (K-12)**, configurable por institución y multi-tenant. El contexto completo, los pendientes de la auditoría y la hoja de ruta están en `docs/contexto-nexo.md`: léelo antes de un cambio grande. El informe de la auditoría está en `docs/auditoria/auditoria-2026-11-17.pdf`.

El dueño del producto escribe en español. Responde en español; código, nombres y commits pueden ir en inglés.

## Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2. Entrada en `main.py`.
  - `app/models`, `app/schemas`, `app/routers`, `app/services`, `app/repositories`, `app/auth.py`, `app/security.py`.
- Frontend (`frontend/`): React 19 + TypeScript, Vite, TanStack Query, Zustand, Axios, React Router, react-hook-form + zod, Vitest, Playwright.
  - `src/features/<módulo>`, componentes en `src/components/ui.tsx`, cliente API en `src/lib/api.ts`.
- Base de datos: SQLite (`DATABASE_URL`, por defecto `sqlite:///./school.db`) en desarrollo, PostgreSQL en producción.
- Zona horaria de negocio: America/Santo_Domingo (`app/services/business_time.py`). Fechas de auditoría en UTC.

## Comandos
Backend, desde la raíz:
```
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
python -m scripts.seed_demo
python -B -m pytest tests -q -p no:cacheprovider
ruff check app tests main.py
ruff format app tests main.py
alembic revision --autogenerate -m "descripcion"
```
Frontend, desde `frontend/`:
```
npm install
npm run dev
npm run format
npm run format:check
npm run lint
npm run typecheck
npm run test
npm run build
npm run e2e
```
Verificación completa en Windows: `.\scripts\check.ps1`. CI: `.github/workflows/`.

Antes de dar una tarea por terminada, corre como mínimo pytest y ruff (backend), o format:check, lint, typecheck y test (frontend), según lo que hayas tocado.

## Reglas
1. **No romper lo que funciona.** Todo cambio de modelo va con su migración Alembic, y todo arreglo con una prueba de regresión en `tests/` (o `*.test.tsx`).
2. **Acceso seguro por defecto.** Toda ruta valida autenticación, permiso y ámbito (qué estudiantes, secciones o institución puede ver el usuario). Si no hay ámbito, el resultado es vacío, nunca "todo".
3. **Permisos, no nombres de rol.** No decidas el acceso a datos con `is_admin()`. Usa los permisos (`finance.manage`, `reports.view`, `grades.manage`…) de `require_permissions` y las funciones `ensure_*`.
4. **Preparar el multi-tenant.** Diseña los modelos, las consultas, las restricciones de unicidad y los bloqueos de forma que puedan llevar `institution_id` sin rediseño.
5. **Universidad y escuela.** Antes de diseñar una funcionalidad, piensa cómo funciona con créditos y selección libre (universidad) y con grados y secciones fijas (escuela). Prefiere la configuración por institución al código duplicado.
6. **Interfaz 100 % en español.** Los mensajes de `HTTPException` que llegan al usuario van en español.
7. **Tipos correctos.** Dinero en `Decimal`/`Numeric`, nunca `Float`. Fechas como `date`/`datetime`, nunca texto libre.
8. **Concurrencia.** Las escrituras críticas usan `lock_governance` / `lock_finance`. No añadas escrituras de notas, inscripciones o finanzas sin bloqueo.
9. **Código legible.** El backend se formatea con Ruff. En el frontend, nada de JSX ni CSS compactado en una línea. Usa los tokens CSS (`--ink`, `--muted`, etc.), no colores escritos a mano.
10. **Auditoría.** Los cambios sensibles (notas, finanzas, usuarios, permisos, períodos) se registran con `record(...)`.
11. **Sin secretos en el repo.** Nada de `.env`, bases de datos ni `__pycache__` versionados.

## Forma de trabajar
- Para cambios grandes: primero un plan corto (archivos, migraciones, riesgos) y espera aprobación; después implementa un paso a la vez.
- Si una petición es una mala idea o rompe estas reglas, dilo con franqueza antes de hacerla.
- Al terminar, resume qué cambió y qué comandos correr para verificarlo.
- Cuando cierres un hallazgo de la auditoría, márcalo en `docs/contexto-nexo.md`.
