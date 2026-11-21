"""Audit trail for sensitive writes (CLAUDE.md, rule 11; audit finding A2).

Every write route records who changed what in ``audit_logs`` inside the same
transaction as the change, so a rolled-back write leaves no entry and a
committed write always has one. ``tests/test_route_audit.py`` fails when a new
write route records nothing.

Finance keeps its own trail (``FinanceEvent``) and grades their change history
(``GradeChange``); both count as audited.
"""

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.security_model import AuditLog

DETAIL_LIMIT = 500


def audit_event(db: Session, user_id: int | None, action: str, resource: str, detail: str):
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            detail=detail[:DETAIL_LIMIT],
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )


def record(db: Session, user, action: str, resource: str, detail: str = "") -> None:
    audit_event(db, user.user_id if user is not None else None, action, resource, detail)


def _text(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "sí" if value else "no"
    return str(value)


def snapshot(item: Any, fields: Iterable[str]) -> dict[str, Any]:
    """Values of ``fields`` on a model instance, to compare after a change."""
    return {field: getattr(item, field, None) for field in fields}


def changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> str:
    """Only the fields that changed, as ``campo: antes → después``."""
    parts = [
        f"{field}: {_text(before.get(field))} → {_text(after.get(field))}"
        for field in after
        if before.get(field) != after.get(field)
    ]
    return "; ".join(parts) if parts else "Sin cambios"
