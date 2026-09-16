from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Settings(BaseSettings):
    database_url: str = "sqlite:///./school.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


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
