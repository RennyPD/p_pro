"""Plan limits (Fase 4, block D1; decision of 25/11/2026).

Limits apply when something is *added* (a student, a staff account, a file),
never to what already exists. A 10 % margin over the limit is allowed with a
notice; past it the addition is refused with 409 and the current usage.

Institutions without a subscription row (created directly by scripts or
tests) have no limits; the platform always creates one (trial).
"""

import math
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.tenant import current_tenant, tenant_bypass
from app.models.billing_model import Plan, Subscription

MARGIN = 0.10
GB = 1024**3
STAFF_SCOPES = ("institution", "sections")


@dataclass(frozen=True)
class Usage:
    students: int
    staff: int
    storage_bytes: int


def subscription_of(db: Session, institution_id: int | None = None) -> Subscription | None:
    institution_id = institution_id or current_tenant(db)
    if institution_id is None:
        return None
    return db.query(Subscription).filter(Subscription.institution_id == institution_id).first()


def usage(db: Session, institution_id: int) -> Usage:
    """Counts only (the platform never reads an institution's records)."""
    from app.models.finance_model import TransferBatch, TransferRequest
    from app.models.operations_model import StudentDocument, SubmissionAttachment
    from app.models.role_model import Role
    from app.models.student_model import Student
    from app.models.user_model import User

    bypass = tenant_bypass()

    def scalar(query):
        return query.execution_options(**bypass).scalar() or 0

    students = scalar(
        db.query(func.count(Student.student_id)).filter(
            Student.institution_id == institution_id, Student.active.is_(True)
        )
    )
    staff = scalar(
        db.query(func.count(User.user_id))
        .join(Role, Role.role_id == User.role_id)
        .filter(
            User.institution_id == institution_id,
            User.active.is_(True),
            Role.scope.in_(STAFF_SCOPES),
        )
    )
    storage = 0
    for model, column in (
        (StudentDocument, StudentDocument.size_bytes),
        (SubmissionAttachment, SubmissionAttachment.size_bytes),
        (TransferBatch, TransferBatch.proof_size),
        (TransferRequest, TransferRequest.proof_size),
    ):
        storage += scalar(
            db.query(func.coalesce(func.sum(column), 0)).filter(
                model.institution_id == institution_id
            )
        )
    return Usage(students=students, staff=staff, storage_bytes=storage)


def ceiling(limit: int) -> int:
    return math.floor(limit * (1 + MARGIN))


def _refuse(plan: Plan, what: str, limit: int, used: int) -> None:
    raise HTTPException(
        409,
        f"Tu plan {plan.name} permite {limit} {what} ({ceiling(limit)} con el margen) y ya "
        f"tienes {used}. Cambia de plan en «Plan y facturación» para añadir más",
    )


def ensure_room(db: Session, *, students: int = 0, staff: int = 0, storage_bytes: int = 0):
    """Refuse an addition beyond the plan (with its 10 % margin)."""
    subscription = subscription_of(db)
    if subscription is None:
        return
    plan = subscription.plan
    current = usage(db, subscription.institution_id)
    if students and plan.max_students is not None:
        if current.students + students > ceiling(plan.max_students):
            _refuse(plan, "estudiantes activos", plan.max_students, current.students)
    if staff and plan.max_staff is not None:
        if current.staff + staff > ceiling(plan.max_staff):
            _refuse(plan, "cuentas del personal", plan.max_staff, current.staff)
    if storage_bytes and plan.storage_gb is not None:
        if current.storage_bytes + storage_bytes > ceiling(plan.storage_gb * GB):
            raise HTTPException(
                409,
                f"Tu plan {plan.name} incluye {plan.storage_gb} GB de archivos y ya están en uso "
                f"{current.storage_bytes / GB:.1f} GB. Cambia de plan en «Plan y facturación» "
                "para subir más",
            )


def is_staff_role(db: Session, role_id: int | None) -> bool:
    from app.models.role_model import Role

    role = db.get(Role, role_id) if role_id else None
    return role is not None and role.scope in STAFF_SCOPES
