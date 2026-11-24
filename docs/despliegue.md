# Despliegue en producción (Fase 4, bloque C)

Nexo se despliega con imágenes Docker y no depende de un proveedor concreto. Sirve cualquier servidor o plataforma que ejecute contenedores (un VPS con Docker Compose, AWS ECS, Google Cloud Run, DigitalOcean App Platform, Fly.io…).

## Piezas

| Pieza | Qué es | Cuántas |
|---|---|---|
| `api` | Imagen raíz (`Dockerfile`): uvicorn con `WEB_CONCURRENCY` procesos | 1 o más réplicas |
| `worker` | Misma imagen, `python -m scripts.scheduler`: correos cada 2 min, cobros diarios a las 6:30 y recordatorios a las 7:00 (America/Santo_Domingo) | 1 (más réplicas quedan en espera) |
| `migrate` | Misma imagen, `alembic upgrade head` | Una vez por versión, antes de `api` y `worker` |
| `web` | `frontend/Dockerfile`: nginx con la interfaz compilada | 1 o más |
| PostgreSQL 16 o superior | Servicio gestionado recomendado (copias automáticas) | 1 |
| Almacenamiento S3 compatible | Archivos subidos (Cloudflare R2 recomendado; AWS S3, Spaces o MinIO también sirven) | 1 bucket privado |
| SMTP | Correo (Amazon SES, Brevo, Resend, Google Workspace…) | 1 |
| Sentry o GlitchTip | Errores, sin datos personales (opcional) | 1 proyecto |

La imagen corre con un usuario sin privilegios (uid 10001). Además:

- **Healthcheck:** usa `/health/ready`, que comprueba la base de datos y el almacenamiento.
- **Migraciones:** nunca corren al arrancar el contenedor. Si varias réplicas arrancan a la vez, no deben migrar a la vez.
- **Tareas programadas:** con PostgreSQL, un bloqueo de la base garantiza que solo un `worker` las ejecute. Las demás réplicas toman el relevo si ese se detiene.

## 1. Base de datos y roles

Usa dos roles:

- **El dueño de las tablas** solo para las migraciones (`MIGRATION_DATABASE_URL`).
- **`nexo_app`** para la aplicación (`DATABASE_URL`). Este rol está sujeto a Row-Level Security: aunque el código fallara, la base no entrega filas de otra institución.

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

Los `ALTER DEFAULT PRIVILEGES` deben ejecutarse con el rol dueño, para que las tablas de futuras migraciones también queden concedidas. Más detalle en `docs/multitenant.md`.

## 2. DNS y HTTPS

Con `TENANT_BASE_DOMAIN=nexo.do`:

| Dirección | Destino |
|---|---|
| `*.nexo.do` (comodín) | `web`: cada institución en `<código>.nexo.do` |
| `admin.nexo.do` | `web`: panel de plataforma en `/plataforma` |
| `api.nexo.do` | `api` |

- El certificado comodín (`*.nexo.do`) requiere validación por DNS. Cloudflare (proxy y certificados automáticos), un balanceador del proveedor o Caddy/Traefik con desafío DNS lo resuelven.
- El proxy debe pasar la cabecera `Host` y las cabeceras `X-Forwarded-*`. Configura `FORWARDED_ALLOW_IPS` con la dirección del proxy; usa `*` solo si el contenedor no es accesible de otra forma, como en `docker-compose.prod.yml`, donde escucha solo en `127.0.0.1`.
- El API identifica la institución por el `Origin` de la página cuando vive en `api.nexo.do`. CORS acepta automáticamente los subdominios HTTPS de `TENANT_BASE_DOMAIN`.

## 3. Variables

Crea `.env.production` en el servidor (nunca en el repositorio) o usa el gestor de secretos de la plataforma.

| Variable | Valor |
|---|---|
| `MIGRATION_DATABASE_URL` | `postgresql+psycopg://<dueño>:<clave>@<host>/nexo` |
| `DATABASE_URL` | `postgresql+psycopg://nexo_app:<clave>@<host>/nexo` |
| `SECRET_KEY` | Aleatorio, 32 caracteres o más (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) |
| `CORS_ORIGINS` | `https://admin.nexo.do` (los subdominios entran por `TENANT_BASE_DOMAIN`) |
| `TENANT_BASE_DOMAIN` | `nexo.do` |
| `APP_URL` | `https://admin.nexo.do` (enlaces de los correos) |
| `EMAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` | Proveedor de correo |
| `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | Almacenamiento (R2: `S3_ENDPOINT_URL=https://<cuenta>.r2.cloudflarestorage.com`, `S3_REGION=auto`) |
| `VITE_API_URL` | `https://api.nexo.do` (al construir `web`) |
| `BILLING_PROVIDER` | `stripe` para cobrar en línea. Con `sandbox`, en producción el pago en línea queda desactivado y la plataforma asigna los planes |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Claves de Stripe (webhook: `https://api.nexo.do/billing/webhooks/stripe` con los eventos `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed` y `customer.subscription.deleted`) |
| `BILLING_TRIAL_DAYS` | Días de prueba de una institución nueva (30) |
| `SIGNUP_ENABLED` | `false` cierra el registro público en `/registro` (las instituciones se crean desde la plataforma) |
| `SENTRY_DSN`, `VITE_SENTRY_DSN` | Opcionales |
| `RELEASE` | Versión o commit desplegado (Sentry) |
| `WEB_CONCURRENCY` | Procesos por réplica de `api` (2 a 4 por CPU) |

Las claves del bucket deben poder leer, escribir y borrar solo en ese bucket, que debe ser privado: las descargas pasan por el API.

## 4. Desplegar una versión

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production build
docker compose -f docker-compose.prod.yml --env-file .env.production run --rm migrate
docker compose -f docker-compose.prod.yml --env-file .env.production up -d api worker web
```

`up` también ejecuta `migrate` primero, porque `api` y `worker` dependen de que termine bien.

Comprueba que todo responde:

```bash
curl -fsS https://api.nexo.do/health/ready
```

## 5. Primera puesta en marcha

1. **Cuenta de plataforma, con segundo factor.** Ejecuta:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.production run --rm api python -m scripts.create_platform_admin soporte@nexo.do "Equipo Nexo"
   ```
2. **Primera institución.** Entra en `https://admin.nexo.do/plataforma` y crea la institución. Su administrador recibe la invitación por correo.
3. **Archivos de una instalación anterior.** Si había archivos guardados en la base, trasládalos y verifica:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.production run --rm api python -m scripts.move_files_to_storage --clear
   docker compose -f docker-compose.prod.yml --env-file .env.production run --rm api python -m scripts.move_files_to_storage --verify
   ```

## 6. Copias de seguridad

- **PostgreSQL:** activa las copias automáticas del servicio gestionado, con restauración a un punto en el tiempo. `scripts/backup_database.py` hace copias y restauraciones verificadas (necesita `pg_dump` y `pg_restore`, que no vienen en la imagen del API; ejecútalo desde una máquina de administración o una imagen `postgres:16`). Usa `pg_dump` y `pg_restore` de la misma versión mayor que el servidor: una versión más nueva escribe parámetros que un servidor anterior no reconoce (por ejemplo `transaction_timeout` de PostgreSQL 17 en un servidor 16). Haz una prueba de restauración al mes.
- **Archivos:** activa el versionado del bucket, o una réplica en otra región o proveedor. Una copia de la base sin los archivos deja enlaces rotos, así que conserva ambas con la misma frecuencia.

## 7. Operación

| Qué | Dónde |
|---|---|
| Logs | Formato JSON en la salida estándar, con `request_id` por petición (cabecera `X-Request-ID`) |
| Errores | Sentry o GlitchTip, etiquetados por institución, sin datos personales |
| Salud | `/health`: el proceso vive. `/health/ready`: la base y el almacenamiento responden; úsalo en el balanceador |
| Tareas | Logs `job_done` y `job_failed` del `worker`. Si se detiene, los cobros y los recordatorios se ponen al día al volver, porque son idempotentes |
| Límites | 429 con `Retry-After` en subidas, exportaciones e importaciones (ver `docs/contexto-nexo.md`) |

Para escalar, añade réplicas de `api`: no guardan estado y comparten la base y el bucket. Un `worker` basta.
