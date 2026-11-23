"""Running work institution by institution (Fase 4, block A)."""

from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.orm import Session

from app.db.tenant import set_tenant
from app.models.institution_model import Institution

T = TypeVar("T")


def active_institutions(bind) -> list[int]:
    with Session(bind=bind) as db:
        return [
            row[0]
            for row in db.query(Institution.institution_id)
            .filter(Institution.status == "active")
            .order_by(Institution.institution_id)
        ]


def for_each_institution(bind, work: Callable[[Session], T], commit: bool = True) -> dict[int, T]:
    """Run ``work`` once per active institution, each in its own tenant session."""
    results: dict[int, T] = {}
    for institution_id in active_institutions(bind):
        with Session(bind=bind) as db:
            set_tenant(db, institution_id)
            results[institution_id] = work(db)
            if commit:
                db.commit()
            else:
                db.rollback()
    return results
