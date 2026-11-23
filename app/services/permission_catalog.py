"""Keeps the permission rows in the database aligned with app.permissions."""

from sqlalchemy.orm import Session

from app.models.access_model import Permission, RolePermission
from app.models.role_model import Role
from app.permissions import PERMISSIONS, SYSTEM_ROLE_DEFAULTS


def institution_configured(db: Session) -> bool:
    """Whether the active institution has saved any role permission (Fase 4 A).

    Until it has, its built-in roles keep their default permissions. This is per
    institution: the permission catalog itself is shared by every institution.
    """
    return db.query(RolePermission.role_permission_id).first() is not None


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
    if SYSTEM_ROLE_DEFAULTS.get(role.name.casefold()) is None:
        return
    if not institution_configured(db):
        # Configuring permissions ends the implicit defaults of every built-in role
        # of the institution, so seed all of them, not only this one.
        ensure_catalog(db)
        return
    _seed_role(db, role, sync_permission_catalog(db))


def _seed_role(db: Session, role: Role, catalog: dict[str, Permission]) -> None:
    defaults = SYSTEM_ROLE_DEFAULTS.get(role.name.casefold())
    if defaults is None:
        return
    scope, slugs = defaults
    role.scope = scope
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
    """Sync the shared catalog; for an institution without any saved permission,
    also seed its built-in roles (Fase 4 A: evaluated per institution).

    Without the second step, the first saved permission would end the defaults
    that unconfigured institutions give to their built-in roles.
    """
    was_empty = not institution_configured(db)
    catalog = sync_permission_catalog(db)
    if was_empty:
        for role in db.query(Role).all():
            _seed_role(db, role, catalog)
    return catalog
