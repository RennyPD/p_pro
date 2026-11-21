"""Granular permission catalog and an explicit data scope per role.

Every route now checks a granular permission (see app/permissions.py). This
migration:

1. adds roles.scope (institution | sections | own | linked), set from the
   built-in role names; custom roles keep institution scope, as before;
2. inserts the catalog permissions;
3. converts each role's broad grants (academic.manage, operations.manage,
   access.manage, ...) into the granular permissions they implied, and gives the
   built-in roles the defaults that match what they could already do;
4. removes the broad grants that no longer exist in the catalog.

Revision ID: 20261120_0046
Revises: 20261120_0045
"""

import sqlalchemy as sa

from alembic import op

revision = "20261120_0046"
down_revision = "20261120_0045"
branch_labels = None
depends_on = None

# Frozen copies (migrations must not import app code that may change later).
CATALOG = {
    "students.view": "Consultar estudiantes",
    "students.manage": "Gestionar estudiantes",
    "teachers.view": "Consultar docentes",
    "teachers.manage": "Gestionar docentes",
    "programs.manage": "Gestionar carreras y pensum",
    "equivalences.manage": "Gestionar equivalencias",
    "sections.view": "Consultar secciones",
    "sections.manage": "Gestionar secciones",
    "schedule.manage": "Gestionar horarios",
    "classrooms.manage": "Gestionar aulas",
    "enrollments.manage": "Gestionar inscripciones",
    "grades.view": "Consultar calificaciones",
    "grades.manage": "Gestionar calificaciones",
    "attendance.view": "Consultar asistencia",
    "attendance.manage": "Registrar asistencia",
    "tasks.manage": "Gestionar tareas",
    "calendar.manage": "Gestionar agenda",
    "finance.view": "Consultar finanzas",
    "finance.manage": "Gestionar finanzas",
    "admissions.manage": "Gestionar admisiones",
    "cases.manage": "Gestionar casos",
    "approvals.manage": "Resolver solicitudes",
    "communications.manage": "Publicar avisos",
    "reports.view": "Consultar reportes",
    "audit.view": "Consultar auditoría",
    "settings.manage": "Gestionar configuración",
    "users.manage": "Gestionar usuarios",
    "roles.manage": "Gestionar roles",
    "records.own": "Consultar su información",
    "selection.own": "Elegir asignaturas",
}
BUNDLES = {
    "academic.manage": [
        "students.view",
        "students.manage",
        "teachers.view",
        "teachers.manage",
        "programs.manage",
        "equivalences.manage",
        "sections.view",
        "sections.manage",
        "classrooms.manage",
        "enrollments.manage",
        "grades.view",
        "attendance.view",
        "settings.manage",
    ],
    "operations.manage": [
        "tasks.manage",
        "calendar.manage",
        "admissions.manage",
        "cases.manage",
        "approvals.manage",
    ],
    "access.manage": ["users.manage", "roles.manage"],
    "reports.view": ["audit.view"],
    "finance.manage": ["finance.view"],
    "grades.manage": ["grades.view", "attendance.view", "attendance.manage"],
}
DEFAULTS = {
    "admin": (
        "institution",
        [slug for slug in CATALOG if slug not in {"records.own", "selection.own"}],
    ),
    "teacher": (
        "sections",
        [
            "students.view",
            "sections.view",
            "grades.view",
            "grades.manage",
            "attendance.view",
            "attendance.manage",
            "tasks.manage",
            "calendar.manage",
            "cases.manage",
            "communications.manage",
        ],
    ),
    "student": ("own", ["records.own", "selection.own"]),
    "guardian": ("linked", ["records.own"]),
}


def upgrade() -> None:
    with op.batch_alter_table("roles") as batch:
        batch.add_column(
            sa.Column("scope", sa.String(20), nullable=False, server_default="institution")
        )
    connection = op.get_bind()
    for name, (scope, _) in DEFAULTS.items():
        connection.execute(
            sa.text("UPDATE roles SET scope = :scope WHERE lower(name) = :name"),
            {"scope": scope, "name": name},
        )
    for slug, description in CATALOG.items():
        connection.execute(
            sa.text(
                "INSERT INTO permissions (slug, description) SELECT :slug, :description "
                "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE slug = :slug)"
            ),
            {"slug": slug, "description": description},
        )
    ids = {
        row.slug: row.permission_id
        for row in connection.execute(sa.text("SELECT permission_id, slug FROM permissions"))
    }
    held = {}
    for row in connection.execute(
        sa.text(
            "SELECT rp.role_id, p.slug FROM role_permissions rp "
            "JOIN permissions p ON p.permission_id = rp.permission_id"
        )
    ):
        held.setdefault(row.role_id, set()).add(row.slug)
    roles = {
        row.role_id: row.name.casefold()
        for row in connection.execute(sa.text("SELECT role_id, name FROM roles"))
    }
    for role_id, name in roles.items():
        current = held.get(role_id, set())
        if name in DEFAULTS and DEFAULTS[name][0] != "institution":
            # Personal-scope built-in roles get exactly their defaults, plus any
            # catalog permission an institution had added on purpose.
            wanted = set(DEFAULTS[name][1]) | (current & set(CATALOG))
        else:
            wanted = set(current)
            for slug in current:
                wanted.update(BUNDLES.get(slug, []))
            if name in DEFAULTS:
                wanted.update(DEFAULTS[name][1])
        for slug in sorted(wanted - current):
            if slug in ids:
                connection.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"
                    ),
                    {"r": role_id, "p": ids[slug]},
                )
    obsolete = [slug for slug in ids if slug not in CATALOG]
    for slug in obsolete:
        connection.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = :p"), {"p": ids[slug]}
        )
        connection.execute(
            sa.text("DELETE FROM permissions WHERE permission_id = :p"), {"p": ids[slug]}
        )


def downgrade() -> None:
    connection = op.get_bind()
    for legacy, description in {
        "academic.manage": "Gestionar operación académica",
        "operations.manage": "Gestionar agenda, tareas y procesos institucionales",
        "access.manage": "Gestionar usuarios, roles y permisos",
    }.items():
        connection.execute(
            sa.text(
                "INSERT INTO permissions (slug, description) SELECT :slug, :description "
                "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE slug = :slug)"
            ),
            {"slug": legacy, "description": description},
        )
    # Roles that hold the first permission of a bundle get the broad grant back.
    for legacy, marker in {
        "academic.manage": "students.manage",
        "operations.manage": "admissions.manage",
        "access.manage": "roles.manage",
    }.items():
        connection.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT DISTINCT rp.role_id, legacy.permission_id FROM role_permissions rp "
                "JOIN permissions marker ON marker.permission_id = rp.permission_id "
                "CROSS JOIN permissions legacy "
                "WHERE marker.slug = :marker AND legacy.slug = :legacy"
            ),
            {"legacy": legacy, "marker": marker},
        )
    with op.batch_alter_table("roles") as batch:
        batch.drop_column("scope")
