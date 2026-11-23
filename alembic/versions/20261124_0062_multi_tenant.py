"""Multi-tenant foundations (Fase 4, block A).

1. ``institutions``: the current installation becomes institution 1.
2. ``institution_id`` on every institution-owned table (66), filled with 1,
   required, indexed and with its foreign key.
3. The 23 business uniques become unique per institution (enrollment number,
   emails, usernames, codes, names...). Technical uniques (tokens,
   idempotency keys) stay global. Settings: one row per institution.
4. PostgreSQL: Row-Level Security on every tenant table. The policy lets a
   transaction see only ``app.institution_id`` unless ``app.tenant_bypass`` is
   on (system jobs). Table owners (migrations, backups) are not affected; the
   application must connect with its own role (see docs/multitenant.md).

Downgrade is only possible while there is a single institution.

Revision ID: 20261124_0062
Revises: 20261123_0061
"""

import sqlalchemy as sa

from alembic import op

revision = "20261124_0062"
down_revision = "20261123_0061"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "academic_periods", "admission_applications", "alert_interventions", "announcements",
    "approval_requests", "assessment_templates", "assessments", "assignments",
    "attendance_changes", "attendances", "audit_logs", "billing_concepts",
    "billing_plan_targets", "billing_plans", "billing_runs", "calendar_events", "careers",
    "cash_closings", "charges", "class_group_members", "class_group_subjects", "class_groups",
    "classrooms", "competency_groups", "course_equivalences", "course_selection_cart",
    "curriculum_courses", "early_alerts", "email_outbox", "enrollments", "finance_events",
    "finance_policies", "financial_adjustments", "grade_changes", "grades",
    "grading_scale_bands", "grading_scales", "guardians", "installments",
    "institution_settings", "lesson_plans", "notifications", "one_time_tokens",
    "payment_plans", "payments", "recovery_exams", "refresh_tokens", "report_card_comments",
    "role_permissions", "roles", "school_years", "section_meetings", "sections",
    "student_accounts", "student_career_history", "student_documents", "student_guardians",
    "students", "subjects", "submission_attachments", "submission_revisions", "submissions",
    "teachers", "transfer_batches", "transfer_requests", "users",
)  # fmt: skip
PER_INSTITUTION = {
    "academic_periods": ["name"],
    "admission_applications": ["email"],
    "billing_concepts": ["name"],
    "billing_plans": ["name"],
    "careers": ["code", "name"],
    "cash_closings": ["closing_date"],
    "classrooms": ["name"],
    "competency_groups": ["position"],
    "grading_scales": ["name"],
    "guardians": ["email"],
    "payments": ["receipt_number"],
    "roles": ["name"],
    "school_years": ["name"],
    "sections": ["code"],
    "students": ["email", "enrollment_number"],
    "subjects": ["code"],
    "teachers": ["email"],
    "transfer_batches": ["reference"],
    "transfer_requests": ["reference"],
    "users": ["email", "username"],
}
# SQLite reflects unnamed unique constraints; this names them so batch mode can drop them.
SQLITE_NAMES = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
POLICY = (
    "current_setting('app.tenant_bypass', true) = 'on' OR institution_id = "
    "NULLIF(current_setting('app.institution_id', true), '')::integer"
)


def single_uniques(table: str, column: str) -> tuple[list[str], list[str]]:
    """Names of the one-column unique constraints and unique indexes on ``column``."""
    inspector = sa.inspect(op.get_bind())
    constraints = [
        item["name"] or f"uq_{table}_{column}"
        for item in inspector.get_unique_constraints(table)
        if item["column_names"] == [column]
    ]
    # PostgreSQL also lists the index behind each unique constraint: skip those.
    indexes = [
        item["name"]
        for item in inspector.get_indexes(table)
        if item["unique"]
        and item["column_names"] == [column]
        and not item.get("duplicates_constraint")
        and item["name"] not in constraints
    ]
    return constraints, indexes


def restore_attendance_day_index() -> None:
    """SQLite batch mode rebuilds the table and drops this expression index (0029)."""
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_enrollment_day "
        "ON attendances (enrollment_id, date(date))"
    )


def upgrade() -> None:
    connection = op.get_bind()
    postgres = connection.dialect.name == "postgresql"
    op.create_table(
        "institutions",
        sa.Column("institution_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("slug", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_institutions_slug"),
    )
    name = connection.execute(
        sa.text("SELECT institution_name FROM institution_settings ORDER BY settings_id LIMIT 1")
    ).scalar()
    connection.execute(
        sa.text(
            "INSERT INTO institutions (institution_id, name, slug, status, created_at) "
            "VALUES (1, :name, 'principal', 'active', CURRENT_TIMESTAMP)"
        ),
        {"name": name or "Institución principal"},
    )
    if postgres:
        connection.execute(
            sa.text(
                "SELECT setval(pg_get_serial_sequence('institutions', 'institution_id'), "
                "(SELECT MAX(institution_id) FROM institutions))"
            )
        )

    for table in TENANT_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("institution_id", sa.Integer(), nullable=True))
        connection.execute(sa.text(f"UPDATE {table} SET institution_id = 1"))
        with op.batch_alter_table(table) as batch:
            batch.alter_column("institution_id", existing_type=sa.Integer(), nullable=False)
            batch.create_foreign_key(
                f"fk_{table}_institution", "institutions", ["institution_id"], ["institution_id"]
            )
            batch.create_index(f"ix_{table}_institution_id", ["institution_id"])
        if table == "attendances" and not postgres:
            restore_attendance_day_index()

    for table, columns in PER_INSTITUTION.items():
        drops = {column: single_uniques(table, column) for column in columns}
        with op.batch_alter_table(table, naming_convention=SQLITE_NAMES) as batch:
            for column, (constraints, indexes) in drops.items():
                for constraint in constraints:
                    batch.drop_constraint(constraint, type_="unique")
                for index in indexes:
                    batch.drop_index(index)
                batch.create_unique_constraint(
                    f"uq_{table}_institution_{column}", ["institution_id", column]
                )
    with op.batch_alter_table("institution_settings") as batch:
        batch.create_unique_constraint("uq_institution_settings_institution", ["institution_id"])

    if postgres:
        for table in TENANT_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY tenant_isolation ON {table} USING ({POLICY}) WITH CHECK ({POLICY})"
            )


def downgrade() -> None:
    connection = op.get_bind()
    count = connection.execute(sa.text("SELECT COUNT(*) FROM institutions")).scalar()
    if count and count > 1:
        raise RuntimeError("No se puede volver atrás con más de una institución")
    if connection.dialect.name == "postgresql":
        for table in TENANT_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    with op.batch_alter_table("institution_settings") as batch:
        batch.drop_constraint("uq_institution_settings_institution", type_="unique")
    for table, columns in PER_INSTITUTION.items():
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.drop_constraint(f"uq_{table}_institution_{column}", type_="unique")
                batch.create_unique_constraint(f"uq_{table}_{column}", [column])
    for table in TENANT_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_institution_id")
            batch.drop_constraint(f"fk_{table}_institution", type_="foreignkey")
            batch.drop_column("institution_id")
        if table == "attendances" and connection.dialect.name != "postgresql":
            restore_attendance_day_index()
    op.drop_table("institutions")
