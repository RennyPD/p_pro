"""Academic period by id, with its name as a computed attribute (audit B5).

Sections, enrollments and cart items store ``period_id`` (a real foreign key)
since migration 0054. ``period_name`` / ``period`` stay available on the
models as the linked period's name so the API and existing queries keep
working, and renaming a period no longer breaks any link:

- Reading returns the name of the linked period ("" when there is none).
- Assigning a name links the period with that name; an unknown name fails
  with the same 409 the services already use.
- In queries the attribute compares against the linked period's name.
"""

from fastapi import HTTPException
from sqlalchemy import event, func, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Session, object_session

UNKNOWN_PERIOD = "El período académico no existe"


def resolve_period(session: Session, name: str):
    from app.models.configuration_model import AcademicPeriod

    if not name:
        return None
    pending = [
        item for item in session.new if isinstance(item, AcademicPeriod) and item.name == name
    ]
    if pending:
        return pending[0]
    with session.no_autoflush:
        period = session.query(AcademicPeriod).filter_by(name=name).first()
    if period is None:
        raise HTTPException(409, UNKNOWN_PERIOD)
    return period


def period_by_name(attribute: str) -> hybrid_property:
    """Hybrid attribute ``attribute`` backed by ``period_id`` / ``academic_period``."""
    pending = f"_pending_{attribute}"

    def getter(self) -> str:
        if pending in self.__dict__:
            return self.__dict__[pending]
        period = self.academic_period
        return period.name if period is not None else ""

    def setter(self, value) -> None:
        name = value or ""
        session = object_session(self)
        if session is None:
            # Linked when the object is flushed (see link_pending_periods).
            self.__dict__[pending] = name
            return
        self.academic_period = resolve_period(session, name)
        self.__dict__.pop(pending, None)

    def expression(cls):
        from app.models.configuration_model import AcademicPeriod

        name = (
            select(AcademicPeriod.name)
            .where(AcademicPeriod.period_id == cls.period_id)
            .correlate_except(AcademicPeriod)
            .scalar_subquery()
        )
        return func.coalesce(name, "")

    return hybrid_property(getter, setter, expr=expression)


PENDING_ATTRIBUTES = ("_pending_period_name", "_pending_period")


@event.listens_for(Session, "before_flush")
def link_pending_periods(session: Session, _context, _instances) -> None:
    """Objects created with a period name get their period linked before insert."""
    for item in list(session.new):
        for key in PENDING_ATTRIBUTES:
            if key in item.__dict__:
                name = item.__dict__.pop(key)
                item.academic_period = resolve_period(session, name)
