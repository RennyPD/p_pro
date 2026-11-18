"""Grant every configured permission to the built-in admin role.

Institution-wide reads now follow permissions instead of the role name. The
built-in administrator kept full reach before this change, so it receives any
configured permission it was missing. Installations without permissions keep
working through the legacy fallback and are left untouched.
"""

import sqlalchemy as sa

from alembic import op

revision = "20261118_0039"
down_revision = "20261117_0038"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.role_id, p.permission_id
            FROM roles r CROSS JOIN permissions p
            WHERE lower(r.name) = 'admin'
              AND NOT EXISTS (
                SELECT 1 FROM role_permissions rp
                WHERE rp.role_id = r.role_id AND rp.permission_id = p.permission_id
              )
            """
        )
    )


def downgrade():
    # Grants cannot be told apart from those configured by hand; keep them.
    pass
