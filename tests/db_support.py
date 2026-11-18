"""Test database selection.

By default every suite uses its own SQLite database. Setting
NEXO_TEST_DATABASE_URL (for example postgresql+psycopg://user@host/db) runs the
same suites against that server; its public schema is reset before use.
"""

import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = os.environ.get("NEXO_TEST_DATABASE_URL")


def reset_schema(engine) -> None:
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))


def make_engine(sqlite_url: str = "sqlite://", **sqlite_kwargs):
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        reset_schema(engine)
        return engine
    if sqlite_url == "sqlite://":
        sqlite_kwargs.setdefault("poolclass", StaticPool)
    connect_args = {"check_same_thread": False, **sqlite_kwargs.pop("connect_args", {})}
    engine = create_engine(sqlite_url, connect_args=connect_args, **sqlite_kwargs)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine
