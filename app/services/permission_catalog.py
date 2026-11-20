"""Keeps the permission rows in the database aligned with app.permissions."""

from sqlalchemy.orm import Session

from app.models.access_model import Permission, RolePermission
from app.models.role_model import Role
from app.permissions import PERMISSIONS, SYSTEM_ROLE_DEFAULTS


def sync_permission_catalog(db: Session) -> dict[str, Permission]:
    """Insert missing catalog permissions and refresh their descriptions."""
    existing = {item.slug: item for item in db.query(Permission).all()}
    for definition in PERMISSIONS:
        item = existing.get(definition.slug)
        if item is None:
            item = Permission(slug=definition.slug, description=definition.label)
            db.add(item)
            existing[definition.slug] = item
        else:
            item.description = definition.label
    db.flush()
    return existing


def grant_system_defaults(db: Session, role: Role) -> None:
    """Give a built-in role (admin, teacher, student, guardian) its default scope and grants."""
    defaults = SYSTEM_ROLE_DEFAULTS.get(role.name.casefold())
    if defaults is None:
        return
    scope, slugs = defaults
    role.scope = scope
    catalog = sync_permission_catalog(db)
    held = {
        row[0]
        for row in db.query(RolePermission.permission_id).filter(
            RolePermission.role_id == role.role_id
        )
    }
    for slug in slugs:
        permission = catalog[slug]
        if permission.permission_id not in held:
            db.add(RolePermission(role_id=role.role_id, permission_id=permission.permission_id))
    db.flush()


def ensure_catalog(db: Session) -> dict[str, Permission]:
    """Sync the catalog; on a database that had none, also seed the built-in roles.

    Without the second step, the first saved permission would end the defaults
    that unconfigured databases give to the built-in roles.
    """
    was_empty = db.query(Permission.permission_id).first() is None
    catalog = sync_permission_catalog(db)
    if was_empty:
        for role in db.query(Role).all():
            grant_system_defaults(db, role)
    return catalog
