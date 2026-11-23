"""Academic periods linked by id instead of by name (audit B5, Fase 3 block A).

Sections (period_name), enrollments (period) and cart items (period) stored
the period's name as text, so renaming a period silently broke every link.
This migration:

1. Creates a closed placeholder period for any name that has no period row
   (legacy data), and prints them so an administrator can review them.
2. Adds period_id with a foreign key, fills it from the name and makes it
   required for enrollments and cart items (sections may still have none).
3. Moves the uniqueness of a selection to (student, section, period_id) and
   drops the text columns. The models keep period_name / period as the name of
   the linked period, so the API does not change.

Revision ID: 20261123_0054
Revises: 20261122_0053
"""

from datetime import date

import sqlalchemy as sa

from alembic import op

revision = "20261123_0054"
down_revision = "20261122_0053"
branch_labels = None
depends_on = None

LINKED = (
    # table, text column, nullable period, unique name, unique columns
    ("sections", "period_name", True, None, None),
    (
        "enrollments",
        "period",
        False,
        "uq_enrollment_student_section_period",
        ["student_id", "section_id"],
    ),
    (
        "course_selection_cart",
        "period",
        False,
        "uq_cart_student_section_period",
        ["student_id", "section_id"],
    ),
)


def create_missing_periods(connection) -> list[str]:
    known = {row[0] for row in connection.execute(sa.text("SELECT name FROM academic_periods"))}
    names: dict[str, tuple[date | None, date | None]] = {}
    for table, column, *_ in LINKED:
        dated = table == "enrollments"
        query = (
            f"SELECT {column}, MIN(enrollment_date), MAX(enrollment_date) FROM {table} "
            f"WHERE {column} IS NOT NULL AND {column} <> '' GROUP BY {column}"
            if dated
            else f"SELECT DISTINCT {column}, NULL, NULL FROM {table} "
            f"WHERE {column} IS NOT NULL AND {column} <> ''"
        )
        for name, first, last in connection.execute(sa.text(query)):
            if name not in known:
                names.setdefault(name, (first, last))
    created = []
    for name, (first, last) in sorted(names.items()):
        start = (first.date() if hasattr(first, "date") else first) if first else date.today()
        end = (last.date() if hasattr(last, "date") else last) if last else start
        if isinstance(start, str):
            start = date.fromisoformat(start[:10])
        if isinstance(end, str):
            end = date.fromisoformat(end[:10])
        connection.execute(
            sa.text(
                "INSERT INTO academic_periods (name, start_date, end_date, active, status, "
                "period_type, sequence, academic_year) VALUES (:name, :start, :end, :active, "
                "'closed', 'semester', 1, '')"
            ),
            {"name": name, "start": start, "end": max(start, end), "active": False},
        )
        created.append(name)
    return created


def upgrade() -> None:
    connection = op.get_bind()
    created = create_missing_periods(connection)
    if created:
        print(f"[0054] Períodos creados como cerrados para datos heredados: {', '.join(created)}")
    for table, column, nullable, unique, columns in LINKED:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("period_id", sa.Integer(), nullable=True))
        connection.execute(
            sa.text(
                f"UPDATE {table} SET period_id = (SELECT period_id FROM academic_periods "
                f"WHERE academic_periods.name = {table}.{column})"
            )
        )
        with op.batch_alter_table(table) as batch:
            if unique:
                batch.drop_constraint(unique, type_="unique")
            batch.drop_column(column)
            batch.alter_column("period_id", existing_type=sa.Integer(), nullable=nullable)
            batch.create_foreign_key(
                f"fk_{table}_period", "academic_periods", ["period_id"], ["period_id"]
            )
            batch.create_index(f"ix_{table}_period_id", ["period_id"])
            if unique:
                batch.create_unique_constraint(unique, [*columns, "period_id"])


def downgrade() -> None:
    connection = op.get_bind()
    for table, column, nullable, unique, columns in LINKED:
        with op.batch_alter_table(table) as batch:
            batch.add_column(
                sa.Column(column, sa.String(50), nullable=True, server_default="")
            )
        connection.execute(
            sa.text(
                f"UPDATE {table} SET {column} = COALESCE((SELECT name FROM academic_periods "
                f"WHERE academic_periods.period_id = {table}.period_id), '')"
            )
        )
        with op.batch_alter_table(table) as batch:
            if unique:
                batch.drop_constraint(unique, type_="unique")
            batch.drop_index(f"ix_{table}_period_id")
            batch.drop_constraint(f"fk_{table}_period", type_="foreignkey")
            batch.drop_column("period_id")
            batch.alter_column(column, existing_type=sa.String(50), nullable=nullable)
            if unique:
                batch.create_unique_constraint(unique, [*columns, column])
