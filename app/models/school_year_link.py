"""School year by id, with its name as ``AcademicPeriod.academic_year`` (Fase 3 B).

Periods point to ``school_years`` by id since migration 0056. The
``academic_year`` attribute keeps the old text API working:

- Reading returns the linked year's name ("" when there is none).
- Assigning a name links the year with that name; when it does not exist yet
  it is created from the period's dates, so the existing period form keeps
  working. A linked year is widened to cover the period's dates.
- In queries the attribute compares against the linked year's name.
"""

from sqlalchemy import event, func, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Session, object_session

PENDING = "_pending_academic_year"

# Period type → the year's scheme (how many periods it is divided into).
SCHEME_FOR_TYPE = {
    "bimester": "bimesters",
    "trimester": "trimesters",
    "quarter": "quarters",
    "quadrimester": "quadrimesters",
    "semester": "semesters",
    "annual": "annual",
}


def link_school_year(session: Session, period, name: str) -> None:
    from app.models.configuration_model import SchoolYear

    name = (name or "").strip()
    if not name:
        period.school_year = None
        return
    pending = [item for item in session.new if isinstance(item, SchoolYear) and item.name == name]
    with session.no_autoflush:
        year = pending[0] if pending else session.query(SchoolYear).filter_by(name=name).first()
    start, end = period.start_date, period.end_date
    if year is None:
        year = SchoolYear(
            name=name,
            start_date=start,
            end_date=end,
            period_scheme=SCHEME_FOR_TYPE.get(period.period_type or "semester", "semesters"),
        )
        session.add(year)
    else:
        if start and start < year.start_date:
            year.start_date = start
        if end and end > year.end_date:
            year.end_date = end
    period.school_year = year


def school_year_by_name() -> hybrid_property:
    def getter(self) -> str:
        if PENDING in self.__dict__:
            return self.__dict__[PENDING]
        year = self.school_year
        return year.name if year is not None else ""

    def setter(self, value) -> None:
        session = object_session(self)
        if session is None:
            # Linked when the period is flushed (see link_pending_years).
            self.__dict__[PENDING] = (value or "").strip()
            return
        self.__dict__.pop(PENDING, None)
        link_school_year(session, self, value)

    def expression(cls):
        from app.models.configuration_model import SchoolYear

        name = (
            select(SchoolYear.name)
            .where(SchoolYear.school_year_id == cls.school_year_id)
            .correlate_except(SchoolYear)
            .scalar_subquery()
        )
        return func.coalesce(name, "")

    return hybrid_property(getter, setter, expr=expression)


@event.listens_for(Session, "before_flush")
def link_pending_years(session: Session, _context, _instances) -> None:
    for item in list(session.new):
        if PENDING in item.__dict__:
            link_school_year(session, item, item.__dict__.pop(PENDING))
