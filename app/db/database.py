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
