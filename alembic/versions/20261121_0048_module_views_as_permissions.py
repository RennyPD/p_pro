"""Read-only modules follow role permissions instead of per-account grants (B4).

Until now an administrator could give a single account read-only "modules"
(``users.module_views``) beside the permissions of its role: two access systems
in parallel. From here on:

- Students, teachers and sections are read with ``students.view``,
  ``teachers.view`` and ``sections.view``, whose pages already exist.
- Careers, subjects and periods are read with the new ``programs.view``.

Each account's old modules become the matching permissions of its role, so
nobody loses what they could see. Because a role is shared, the other accounts
of that role gain the same read access; the migration only adds view
permissions, never management ones. A database whose permission catalog is
still empty keeps the built-in defaults untouched.

Revision ID: 20261121_0048
Revises: 20261120_0047
"""

import json

import sqlalchemy as sa

from alembic import op

revision = "20261121_0048"
down_revision = "20261120_0047"
branch_labels = None
depends_on = None

MODULE_PERMISSIONS = {
    "students": "students.view",
    "teachers": "teachers.view",
    "sections": "sections.view",
    "careers": "programs.view",
    "subjects": "programs.view",
    "periods": "programs.view",
}


def permission_id(connection, slug: str) -> int:
    row = connection.execute(
        sa.text("SELECT permission_id FROM permissions WHERE slug = :slug"), {"slug": slug}
    ).first()
    if row is None:
        connection.execute(
            sa.text("INSERT INTO permissions (slug, description) VALUES (:slug, :slug)"),
            {"slug": slug},
        )
        row = connection.execute(
            sa.text("SELECT permission_id FROM permissions WHERE slug = :slug"), {"slug": slug}
        ).first()
    return row[0]


def upgrade() -> None:
    connection = op.get_bind()
    catalog_in_use = connection.execute(sa.text("SELECT 1 FROM permissions LIMIT 1")).first()
    if catalog_in_use:
        connection.execute(
            sa.text(
                "INSERT INTO permissions (slug, description) "
                "SELECT 'programs.view', 'Consultar oferta académica' "
                "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE slug = 'programs.view')"
            )
        )
        # Administrators keep every permission of the catalog.
        connection.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT roles.role_id, p.permission_id FROM roles CROSS JOIN permissions p "
                "WHERE lower(roles.name) = 'admin' AND p.slug = 'programs.view' "
                "AND NOT EXISTS (SELECT 1 FROM role_permissions rp "
                "WHERE rp.role_id = roles.role_id AND rp.permission_id = p.permission_id)"
            )
        )
    wanted: set[tuple[int, str]] = set()
    rows = connection.execute(
        sa.text("SELECT role_id, module_views FROM users WHERE module_views IS NOT NULL")
    )
    for role_id, modules in rows:
        if isinstance(modules, str):
            modules = json.loads(modules or "null")
        for module in modules or []:
            slug = MODULE_PERMISSIONS.get(module)
            if slug and role_id is not None:
                wanted.add((role_id, slug))
    # With an empty catalog the built-in roles still use their defaults; a first
    # grant would end them, so old grants are only carried over to a catalog in use.
    for role_id, slug in sorted(wanted) if catalog_in_use else ():
        target = permission_id(connection, slug)
        held = connection.execute(
            sa.text(
                "SELECT 1 FROM role_permissions WHERE role_id = :role AND permission_id = :perm"
            ),
            {"role": role_id, "perm": target},
        ).first()
        if held is None:
            connection.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) VALUES (:role, :perm)"
                ),
                {"role": role_id, "perm": target},
            )
    with op.batch_alter_table("users") as batch:
        batch.drop_column("module_views")


def downgrade() -> None:
    op.add_column("users", sa.Column("module_views", sa.JSON()))
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT permission_id FROM permissions WHERE slug = 'programs.view')"
        )
    )
    connection.execute(sa.text("DELETE FROM permissions WHERE slug = 'programs.view'"))
