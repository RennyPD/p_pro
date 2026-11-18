"""grades.date_recorded becomes a real DATE instead of free text (audit, low finding).

Accepted text: ISO dates (2026-09-15, with or without time) and dd/mm/yyyy.
Anything else falls back to the date of updated_at. If neither works the
migration stops and lists the grade ids so they can be fixed by hand; no
date is invented.
"""

from datetime import date, datetime

import sqlalchemy as sa

from alembic import op

revision = "20261118_0044"
down_revision = "20261118_0043"
branch_labels = None
depends_on = None


def parse_day(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for parser in (
        lambda t: date.fromisoformat(t[:10]),
        lambda t: datetime.strptime(t, "%d/%m/%Y").date(),
    ):
        try:
            return parser(text)
        except ValueError:
            continue
    return None


def upgrade():
    op.add_column("grades", sa.Column("date_recorded_on", sa.Date(), nullable=True))
    connection = op.get_bind()
    grades = sa.table(
        "grades",
        sa.column("grade_id", sa.Integer()),
        sa.column("date_recorded", sa.String()),
        sa.column("updated_at", sa.String()),
        sa.column("date_recorded_on", sa.Date()),
    )
    unresolved = []
    rows = connection.execute(
        sa.select(grades.c.grade_id, grades.c.date_recorded, grades.c.updated_at)
    ).all()
    for grade_id, recorded, updated_at in rows:
        day = parse_day(recorded) or parse_day(updated_at)
        if day is None:
            unresolved.append(grade_id)
            continue
        connection.execute(
            grades.update().where(grades.c.grade_id == grade_id).values(date_recorded_on=day)
        )
    if unresolved:
        raise RuntimeError(
            "Fechas de nota no reconocidas en grades.grade_id "
            f"{unresolved[:20]}; corrígelas (AAAA-MM-DD) y vuelve a migrar"
        )
    with op.batch_alter_table("grades") as batch:
        batch.drop_column("date_recorded")
        batch.alter_column(
            "date_recorded_on",
            new_column_name="date_recorded",
            existing_type=sa.Date(),
            nullable=False,
        )


def downgrade():
    op.add_column("grades", sa.Column("date_recorded_text", sa.String(50), nullable=True))
    op.execute("UPDATE grades SET date_recorded_text = CAST(date_recorded AS VARCHAR(50))")
    with op.batch_alter_table("grades") as batch:
        batch.drop_column("date_recorded")
        batch.alter_column(
            "date_recorded_text",
            new_column_name="date_recorded",
            existing_type=sa.String(50),
            nullable=False,
        )
