"""School years as their own table (Fase 3, block B).

Periods stored their year as free text (academic_year). This migration
creates ``school_years``, one row per distinct non-empty name, dated from the
first start to the last end of its periods and with the scheme of its first
period's type, links each period by id and drops the text column. The model
keeps ``academic_year`` as the linked year's name, so the API does not change.

Revision ID: 20261123_0056
Revises: 20261123_0055
"""

from datetime import date

import sqlalchemy as sa

from alembic import op

revision = "20261123_0056"
down_revision = "20261123_0055"
branch_labels = None
depends_on = None

SCHEME_FOR_TYPE = {
    "bimester": "bimesters",
    "trimester": "trimesters",
    "quarter": "quarters",
    "quadrimester": "quadrimesters",
    "semester": "semesters",
    "annual": "annual",
}


def as_date(value):
    return date.fromisoformat(value[:10]) if isinstance(value, str) else value


def upgrade() -> None:
    op.create_table(
        "school_years",
        sa.Column("school_year_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("period_scheme", sa.String(20), nullable=False, server_default="semesters"),
        sa.UniqueConstraint("name", name="uq_school_years_name"),
    )
    connection = op.get_bind()
    years: dict[str, dict] = {}
    rows = connection.execute(
        sa.text(
            "SELECT TRIM(academic_year), start_date, end_date, period_type FROM academic_periods "
            "WHERE academic_year IS NOT NULL AND TRIM(academic_year) <> '' "
            "ORDER BY start_date, period_id"
        )
    )
    for name, start, end, period_type in rows:
        start, end = as_date(start), as_date(end)
        year = years.setdefault(
            name,
            {"start": start, "end": end, "scheme": SCHEME_FOR_TYPE.get(period_type, "semesters")},
        )
        year["start"] = min(year["start"], start)
        year["end"] = max(year["end"], end)
    for name, year in years.items():
        connection.execute(
            sa.text(
                "INSERT INTO school_years (name, start_date, end_date, period_scheme) "
                "VALUES (:name, :start, :end, :scheme)"
            ),
            {"name": name, **year},
        )
    with op.batch_alter_table("academic_periods") as batch:
        batch.add_column(sa.Column("school_year_id", sa.Integer(), nullable=True))
    connection.execute(
        sa.text(
            "UPDATE academic_periods SET school_year_id = (SELECT school_year_id "
            "FROM school_years WHERE school_years.name = TRIM(academic_periods.academic_year))"
        )
    )
    with op.batch_alter_table("academic_periods") as batch:
        batch.drop_column("academic_year")
        batch.create_foreign_key(
            "fk_academic_periods_school_year",
            "school_years",
            ["school_year_id"],
            ["school_year_id"],
        )
        batch.create_index("ix_academic_periods_school_year_id", ["school_year_id"])


def downgrade() -> None:
    with op.batch_alter_table("academic_periods") as batch:
        batch.add_column(
            sa.Column("academic_year", sa.String(20), nullable=True, server_default="")
        )
    op.get_bind().execute(
        sa.text(
            "UPDATE academic_periods SET academic_year = COALESCE((SELECT name FROM school_years "
            "WHERE school_years.school_year_id = academic_periods.school_year_id), '')"
        )
    )
    with op.batch_alter_table("academic_periods") as batch:
        batch.drop_index("ix_academic_periods_school_year_id")
        batch.drop_constraint("fk_academic_periods_school_year", type_="foreignkey")
        batch.drop_column("school_year_id")
    op.drop_table("school_years")
