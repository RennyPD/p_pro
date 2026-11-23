"""Multi-tenant isolation (Fase 4, block A).

Every institution-owned table carries ``institution_id`` (``TenantMixin``).
The active institution lives on the SQLAlchemy session (``set_tenant``):

- Reads: every ORM query, relationship load and ``Session.get`` is filtered to
  the active institution (``with_loader_criteria``).
- Writes: new rows get the active institution; a row of another institution
  is never saved through a tenant session.
- A request session (``get_db``) without an institution sees nothing and may
  not insert tenant rows: no scope means an empty result, never everything
  (CLAUDE.md, rule 2).
- Scripts, migrations and tests that never set a tenant act as the system:
  they see every institution and new rows default to institution 1.
- On PostgreSQL each transaction also sets ``app.institution_id`` (or
  ``app.tenant_bypass`` for the system) so Row-Level Security policies,
  enforced for the application role, back the ORM filter up.

``tenant_bypass()`` as an execution option lets the few cross-institution
lookups (sign-in, tokens) read before the institution is known.
"""

from sqlalchemy import ForeignKey, event, text
from sqlalchemy.orm import (
    Mapped,
    ORMExecuteState,
    Session,
    declared_attr,
    mapped_column,
    object_session,
    with_loader_criteria,
)

DEFAULT_INSTITUTION_ID = 1
TENANT = "nexo_institution_id"
REQUEST = "nexo_request"
NO_INSTITUTION = -1  # matches nothing


class TenantMixin:
    """Adds the owning institution to a model."""

    @declared_attr
    def institution_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("institutions.institution_id"), index=True, nullable=False)


class TenantError(RuntimeError):
    """A tenant rule was broken (programming error, never user input)."""


def current_tenant(db: Session) -> int | None:
    return db.info.get(TENANT)


def is_request(db: Session) -> bool:
    return bool(db.info.get(REQUEST))


def set_tenant(db: Session, institution_id: int | None) -> None:
    """Make ``institution_id`` the active institution of this session."""
    previous = db.info.get(TENANT)
    if previous is not None and institution_id is not None and previous != institution_id:
        raise TenantError("La sesión ya pertenece a otra institución")
    db.info[TENANT] = institution_id
    if db.in_transaction():
        _apply_database_setting(db, db.connection())


def mark_request(db: Session) -> None:
    db.info[REQUEST] = True


def tenant_bypass() -> dict:
    """Execution options for a deliberate cross-institution read."""
    return {"nexo_tenant_bypass": True}


def _filter_value(db: Session) -> int | None:
    tenant = current_tenant(db)
    if tenant is not None:
        return tenant
    return NO_INSTITUTION if is_request(db) else None


@event.listens_for(Session, "do_orm_execute")
def _filter_reads(state: ORMExecuteState) -> None:
    if not (state.is_select or state.is_update or state.is_delete):
        return
    if state.execution_options.get("nexo_tenant_bypass"):
        return
    value = _filter_value(state.session)
    if value is None:
        return
    state.statement = state.statement.options(
        with_loader_criteria(
            TenantMixin,
            lambda cls: cls.institution_id == value,
            include_aliases=True,
        )
    )


def _stamp(session: Session | None, item) -> None:
    tenant = current_tenant(session) if session is not None else None
    if item.institution_id is None:
        if tenant is not None:
            item.institution_id = tenant
        elif session is not None and is_request(session):
            raise TenantError("Una petición sin institución no puede crear registros")
        else:
            item.institution_id = DEFAULT_INSTITUTION_ID
    elif tenant is not None and item.institution_id != tenant:
        raise TenantError("No se puede crear un registro de otra institución")


@event.listens_for(TenantMixin, "before_insert", propagate=True)
def _stamp_insert(_mapper, _connection, target) -> None:
    """Every new row, including those added while flushing, gets its institution."""
    _stamp(object_session(target), target)


@event.listens_for(TenantMixin, "before_update", propagate=True)
def _check_update(_mapper, _connection, target) -> None:
    session = object_session(target)
    tenant = current_tenant(session) if session is not None else None
    if tenant is not None and target.institution_id != tenant:
        raise TenantError("No se puede modificar un registro de otra institución")


def _apply_database_setting(session: Session, connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    tenant = current_tenant(session)
    bypass = "off" if tenant is not None or is_request(session) else "on"
    connection.execute(
        text(
            "SELECT set_config('app.institution_id', :tenant, true), "
            "set_config('app.tenant_bypass', :bypass, true)"
        ),
        {"tenant": str(tenant if tenant is not None else ""), "bypass": bypass},
    )


@event.listens_for(Session, "after_begin")
def _begin(session: Session, _transaction, connection) -> None:
    _apply_database_setting(session, connection)
