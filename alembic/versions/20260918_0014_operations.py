"""Add academic operations, admissions and digital records.

Revision ID: 20260918_0014
Revises: 20260918_0013
"""

import sqlalchemy as sa
from alembic import op

revision = "20260918_0014"
down_revision = "20260918_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("guardian_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_users_guardian", "guardians", ["guardian_id"], ["guardian_id"])
    permissions = op.create_table("permissions", sa.Column("permission_id", sa.Integer(), primary_key=True), sa.Column("slug", sa.String(80), nullable=False, unique=True), sa.Column("description", sa.String(255), nullable=False))
    op.create_table("role_permissions", sa.Column("role_permission_id", sa.Integer(), primary_key=True), sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.role_id"), nullable=False), sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.permission_id"), nullable=False), sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"))
    op.bulk_insert(permissions, [{"slug": "academic.manage", "description": "Gestionar operación académica"}, {"slug": "grades.manage", "description": "Registrar y cerrar calificaciones"}, {"slug": "finance.manage", "description": "Gestionar cuentas y caja"}, {"slug": "reports.view", "description": "Consultar reportes institucionales"}, {"slug": "records.own", "description": "Consultar expediente vinculado"}, {"slug": "communications.manage", "description": "Publicar comunicaciones"}])
    op.execute("INSERT INTO role_permissions (role_id, permission_id) SELECT roles.role_id, permissions.permission_id FROM roles CROSS JOIN permissions WHERE lower(roles.name) = 'admin'")
    op.execute("INSERT INTO role_permissions (role_id, permission_id) SELECT roles.role_id, permissions.permission_id FROM roles CROSS JOIN permissions WHERE lower(roles.name) = 'teacher' AND permissions.slug IN ('academic.manage','grades.manage','communications.manage')")
    op.execute("INSERT INTO role_permissions (role_id, permission_id) SELECT roles.role_id, permissions.permission_id FROM roles CROSS JOIN permissions WHERE lower(roles.name) IN ('student','guardian') AND permissions.slug = 'records.own'")
    op.create_table("calendar_events", sa.Column("calendar_event_id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(150), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("event_type", sa.String(30), nullable=False), sa.Column("audience", sa.String(20), nullable=False), sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.section_id"), nullable=True), sa.Column("starts_at", sa.DateTime(), nullable=False), sa.Column("ends_at", sa.DateTime(), nullable=False), sa.Column("no_school", sa.Boolean(), nullable=False), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False))
    op.create_table("lesson_plans", sa.Column("lesson_plan_id", sa.Integer(), primary_key=True), sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.section_id"), nullable=False), sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teachers.teacher_id"), nullable=False), sa.Column("scheduled_date", sa.Date(), nullable=False), sa.Column("title", sa.String(150), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("competencies", sa.Text(), nullable=False), sa.Column("status", sa.String(20), nullable=False))
    op.create_table("assignments", sa.Column("assignment_id", sa.Integer(), primary_key=True), sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.section_id"), nullable=False), sa.Column("title", sa.String(150), nullable=False), sa.Column("instructions", sa.Text(), nullable=False), sa.Column("due_at", sa.DateTime(), nullable=False), sa.Column("max_score", sa.Float(), nullable=False), sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("assessments.assessment_id"), nullable=True), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False), sa.Column("published", sa.Boolean(), nullable=False))
    op.create_table("submissions", sa.Column("submission_id", sa.Integer(), primary_key=True), sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.assignment_id"), nullable=False), sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.student_id"), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("submitted_at", sa.DateTime(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("score", sa.Float(), nullable=True), sa.Column("feedback", sa.Text(), nullable=False), sa.UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student"))
    op.create_table("early_alerts", sa.Column("early_alert_id", sa.Integer(), primary_key=True), sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.student_id"), nullable=False), sa.Column("category", sa.String(30), nullable=False), sa.Column("severity", sa.String(20), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("resolved_at", sa.DateTime(), nullable=True))
    op.create_table("admission_applications", sa.Column("admission_application_id", sa.Integer(), primary_key=True), sa.Column("first_name", sa.String(100), nullable=False), sa.Column("last_name", sa.String(100), nullable=False), sa.Column("email", sa.String(255), nullable=False, unique=True), sa.Column("telephone", sa.String(30), nullable=False), sa.Column("career_id", sa.Integer(), sa.ForeignKey("careers.career_id"), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("checklist", sa.Text(), nullable=False), sa.Column("notes", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_table("approval_requests", sa.Column("approval_request_id", sa.Integer(), primary_key=True), sa.Column("request_type", sa.String(40), nullable=False), sa.Column("resource_type", sa.String(40), nullable=False), sa.Column("resource_id", sa.Integer(), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False), sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True), sa.Column("resolution_notes", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("resolved_at", sa.DateTime(), nullable=True))
    op.create_table("student_documents", sa.Column("student_document_id", sa.Integer(), primary_key=True), sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.student_id"), nullable=False), sa.Column("document_type", sa.String(50), nullable=False), sa.Column("filename", sa.String(255), nullable=False), sa.Column("mime_type", sa.String(100), nullable=False), sa.Column("content", sa.LargeBinary(), nullable=False), sa.Column("expires_on", sa.Date(), nullable=True), sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False), sa.Column("uploaded_at", sa.DateTime(), nullable=False))
    op.create_table("billing_concepts", sa.Column("billing_concept_id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(120), nullable=False, unique=True), sa.Column("description", sa.String(250), nullable=False), sa.Column("amount", sa.Float(), nullable=False), sa.Column("frequency", sa.String(20), nullable=False), sa.Column("active", sa.Boolean(), nullable=False))
    op.create_table("cash_closings", sa.Column("cash_closing_id", sa.Integer(), primary_key=True), sa.Column("closing_date", sa.Date(), nullable=False, unique=True), sa.Column("total_payments", sa.Float(), nullable=False), sa.Column("payment_count", sa.Integer(), nullable=False), sa.Column("closed_by", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))


def downgrade() -> None:
    for table in ("cash_closings", "billing_concepts", "student_documents", "approval_requests", "admission_applications", "early_alerts", "submissions", "assignments", "lesson_plans", "calendar_events"):
        op.drop_table(table)
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_guardian", type_="foreignkey")
        batch.drop_column("guardian_id")
