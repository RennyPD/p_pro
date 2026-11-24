import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Settings(BaseSettings):
    app_environment: Literal["development", "production"] = "development"
    database_url: str = "sqlite:///./school.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:5173"
    cors_origin_regex: str | None = None
    finance_transfer_instructions: str = ""
    finance_simulator_enabled: bool = True
    # Required in production to create the first administrator via /auth/bootstrap.
    bootstrap_token: str | None = None
    # Email (audit M6). "console" only logs (development and tests); "smtp" sends
    # through any provider (Amazon SES, Brevo, Google Workspace, Resend...).
    email_backend: Literal["console", "smtp"] = "console"
    email_from: str = "Nexo <no-reply@localhost>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    # Public address of the interface, used to build links in emails.
    app_url: str | None = None
    # Fase 4 B: each institution answers at <code>.<tenant_base_domain>
    # (e.g. colegio-horizonte.nexo.do); the panel at admin.<tenant_base_domain>.
    tenant_base_domain: str | None = None
    # Fase 4 C (audit M4): uploaded files live outside the database. "local" keeps
    # them in STORAGE_DIR (development, a single server with a volume); "s3" uses
    # any S3-compatible service (AWS S3, Cloudflare R2, DigitalOcean Spaces, MinIO).
    # Fase 4 C: error tracking (Sentry or GlitchTip). Empty: disabled. Events
    # never carry request bodies, headers, cookies, emails or tokens.
    sentry_dsn: str | None = None
    sentry_environment: str | None = None
    sentry_release: str | None = None
    sentry_traces_sample_rate: float = 0.0
    # Fase 4 C (audit B7): limits on uploads, exports, imports and public routes.
    rate_limits_enabled: bool = True
    storage_backend: Literal["local", "s3"] = "local"
    storage_dir: str = "./storage"
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    @model_validator(mode="after")
    def validate_environment(self):
        if self.app_environment == "development":
            if self.cors_origin_regex is None:
                self.cors_origin_regex = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
            return self
        if len(self.secret_key.strip()) < 32:
            raise ValueError(
                "Configura SECRET_KEY con un secreto aleatorio de al menos 32 caracteres"
            )
        for origin in self.cors_origins.split(","):
            url = urlsplit(origin.strip())
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username is not None
                or url.path
                or url.query
                or url.fragment
                or "*" in origin
            ):
                raise ValueError("CORS_ORIGINS requiere orígenes HTTPS explícitos")
        if self.cors_origin_regex is not None:
            raise ValueError("Usa CORS_ORIGINS para definir los orígenes de producción")
        if self.tenant_base_domain:
            domain = self.tenant_base_domain.strip().lower()
            if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", domain):
                raise ValueError("TENANT_BASE_DOMAIN debe ser un dominio, por ejemplo nexo.do")
            # Only HTTPS subdomains of the configured domain (one label deep).
            self.cors_origin_regex = rf"https://([a-z0-9-]+\.)?{re.escape(domain)}"
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("Configura S3_BUCKET para guardar los archivos en S3")
        if self.email_backend == "smtp" and not self.smtp_host:
            raise ValueError("Configura SMTP_HOST para enviar correo por SMTP")
        if self.app_url and urlsplit(self.app_url).scheme != "https":
            raise ValueError("APP_URL debe usar HTTPS en producción")
        return self

    @property
    def secure_cookies(self) -> bool:
        return self.app_environment == "production"


settings = Settings()
DATABASE_URL = settings.database_url

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass
