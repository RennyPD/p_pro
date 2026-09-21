"""Add access management permission.

Revision ID: 20260921_0019
Revises: 20260921_0018
"""
import sqlalchemy as sa
from alembic import op

revision = "20260921_0019"
down_revision = "20260921_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO permissions (slug, description) "
            "SELECT 'access.manage', 'Gestionar usuarios, roles y permisos' "
            "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE slug = 'access.manage')"
        )
    )
    connection.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT roles.role_id, permissions.permission_id FROM roles, permissions "
            "WHERE lower(roles.name) = 'admin' AND permissions.slug = 'access.manage' "
            "AND NOT EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.role_id = roles.role_id "
            "AND rp.permission_id = permissions.permission_id)"
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT permission_id FROM permissions WHERE slug = 'access.manage')"
        )
    )
    connection.execute(sa.text("DELETE FROM permissions WHERE slug = 'access.manage'"))
