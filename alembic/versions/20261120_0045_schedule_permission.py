"""Schedule blocks are edited with the schedule.manage permission, not by role name.

Until now any account with the teacher or admin role could create, edit or
delete the blocks of the sections in its scope. The new permission goes to
every role that already manages academic operations (academic.manage), so
coordinators keep their access. Roles named teacher are left out on purpose:
an institution that wants its teachers to edit their own sections grants the
permission to that role from the access screen.

Revision ID: 20261120_0045
Revises: 20261118_0044
"""

import sqlalchemy as sa

from alembic import op

revision = "20261120_0045"
down_revision = "20261118_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO permissions (slug, description) "
            "SELECT 'schedule.manage', "
            "'Gestionar bloques de horario y aulas de las secciones' "
            "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE slug = 'schedule.manage')"
        )
    )
    connection.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT DISTINCT roles.role_id, target.permission_id "
            "FROM roles "
            "JOIN role_permissions held ON held.role_id = roles.role_id "
            "JOIN permissions source ON source.permission_id = held.permission_id "
            "CROSS JOIN permissions target "
            "WHERE source.slug = 'academic.manage' "
            "AND target.slug = 'schedule.manage' "
            "AND lower(roles.name) <> 'teacher' "
            "AND NOT EXISTS (SELECT 1 FROM role_permissions rp "
            "WHERE rp.role_id = roles.role_id "
            "AND rp.permission_id = target.permission_id)"
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT permission_id FROM permissions WHERE slug = 'schedule.manage')"
        )
    )
    connection.execute(sa.text("DELETE FROM permissions WHERE slug = 'schedule.manage'"))
