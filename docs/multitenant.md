# Multi-tenant (Fase 4, bloque A)

Nexo atiende a varias instituciones en una sola base de datos. Cada tabla de la institución (66) lleva `institution_id`. Solo son globales el catálogo de permisos (`permissions`), las llaves de bloqueo (`write_locks`, que ya incluyen la institución en la llave) y el freno de intentos de acceso (`login_throttles`).

## Cómo se aísla cada institución

1. **Institución activa por sesión** (`app/db/tenant.py`). La autenticación la fija (`set_tenant`) con la institución de la cuenta.
2. **Filtro automático.** Toda consulta del ORM, carga de relaciones y `Session.get` se limitan a esa institución. Las actualizaciones y borrados masivos (`query(...).update()`) también.
3. **Registros nuevos.** Reciben la institución activa. Crear o modificar un registro de otra institución lanza `TenantError`.
4. **Sin institución, nada.** Una sesión de petición (`get_db`) sin institución no ve ningún registro ni puede crearlos (regla 2 de CLAUDE.md).
5. **Contexto de sistema.** Los scripts, las migraciones y las pruebas que no fijan institución actúan como sistema: ven todas las instituciones y lo nuevo va a la institución 1. Los procesos diarios (`run_billing`, `send_due_reminders`) recorren las instituciones activas, cada una en su propia sesión (`app/services/tenants.py`).
6. **Row-Level Security en PostgreSQL** (migración `20261124_0062`):
   - Cada tabla tiene la política `tenant_isolation`. En cada transacción, la sesión fija `app.institution_id` (o `app.tenant_bypass = on` en el contexto de sistema).
   - Aunque el código olvidara filtrar, la base no devuelve ni acepta filas de otra institución.
   - Los dueños de las tablas (migraciones, respaldos) no están sujetos a RLS. Por eso **la aplicación debe conectarse con su propio rol**.
7. **Bloqueos por institución.** Las llaves son `<institución>:academic`, `<institución>:academic:section:<id>`, etc.
8. **Unicidades por institución.** Matrícula, correos, usuarios, códigos y nombres se repiten libremente entre instituciones. Los tokens y las claves de idempotencia siguen siendo globales.

## Rol de la aplicación en producción

```sql
CREATE ROLE nexo_app LOGIN PASSWORD '<secreto>';
GRANT CONNECT ON DATABASE nexo TO nexo_app;
GRANT USAGE ON SCHEMA public TO nexo_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nexo_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexo_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nexo_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO nexo_app;
```

- `DATABASE_URL` del servidor web usa `nexo_app`.
- Las migraciones (`alembic upgrade head`) y los respaldos se ejecutan con el rol dueño.
- Los procesos diarios pueden usar `nexo_app`: fijan la institución en cada sesión.

## Inicio de sesión

- La cuenta pertenece a una institución.
- Si el usuario o el correo existe en una sola institución, basta con usuario y contraseña. Si existe en varias, el servidor responde 409 y la pantalla pide el código de la institución (`slug`).
- El bloque B añade el subdominio por institución.
- La recuperación de contraseña sigue la misma regla y, si hay ambigüedad, no envía nada.

## Para quien desarrolla

- Un modelo nuevo de la institución hereda `TenantMixin` y su migración añade `institution_id` y la política RLS.
- No uses `db.get(InstitutionSettings, 1)`: usa `settings_of(db)`.
- Una lectura entre instituciones a propósito (antes de conocer la institución, como en el inicio de sesión o con tokens) usa `execution_options(**tenant_bypass())` y fija la institución justo después.
- Las pruebas de aislamiento (`tests/test_multi_tenant.py`) recorren todas las rutas GET con una segunda institución. Tienen un control positivo que demuestra que detectarían una filtración.
