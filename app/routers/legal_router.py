"""Legal documents and their acceptance (Fase 5, step G3)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, has_permission, has_scope
from app.db.Session import get_db
from app.legal import BY_SLUG, DOCUMENTS, INSTITUTION_DOCUMENTS
from app.models.user_model import User
from app.services import legal
from app.services.audit_log import record
from app.services.billing.access import allow_while_read_only
from app.services.rate_limit import PUBLIC, client_ip, per_address
from app.services.write_locks import lock_access

router = APIRouter(tags=["legal"])


class Acceptance(BaseModel):
    kinds: list[str] = Field(min_length=1, max_length=4)


def summary(document) -> dict:
    return {
        "kind": document.kind,
        "title": document.title,
        "version": document.version,
        "slug": document.slug,
    }


@router.get("/public/legal", dependencies=[Depends(per_address(PUBLIC))])
def list_documents():
    return [summary(document) for document in DOCUMENTS.values()]


@router.get("/public/legal/{slug}", dependencies=[Depends(per_address(PUBLIC))])
def read_document(slug: str):
    document = BY_SLUG.get(slug)
    if document is None:
        raise HTTPException(404, "Documento no encontrado")
    return summary(document) | {"text": document.text}


def accepts_for_institution(user: User) -> bool:
    return has_permission(user, "settings.manage") and has_scope(user, "settings.manage")


@router.get("/legal/pending")
def pending(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Documents this account must accept for its institution (administrators only)."""
    if not accepts_for_institution(user):
        return {"documents": []}
    kinds = legal.pending_for_institution(db, user.institution_id)
    return {"documents": [summary(DOCUMENTS[kind]) for kind in kinds]}


@router.post("/legal/accept")
def accept(
    data: Acceptance,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not accepts_for_institution(user):
        raise HTTPException(403, "Solo la administración de la institución acepta estos documentos")
    if not set(data.kinds) <= set(INSTITUTION_DOCUMENTS):
        raise HTTPException(422, "Documento no reconocido")
    allow_while_read_only(db)  # an unpaid institution can still accept the new terms
    lock_access(db)
    legal.accept(
        db,
        data.kinds,
        institution_id=user.institution_id,
        user_id=user.user_id,
        accepted_by=user.email or user.username,
        ip=client_ip(request),
    )
    record(
        db,
        user,
        "legal.accepted",
        "legal",
        ", ".join(f"{DOCUMENTS[kind].title} {DOCUMENTS[kind].version}" for kind in data.kinds),
    )
    db.commit()
    return {
        "documents": [
            summary(DOCUMENTS[k]) for k in legal.pending_for_institution(db, user.institution_id)
        ]
    }


# --- Help center (Fase 5, step G5) ---------------------------------------------------


@router.get("/public/help", dependencies=[Depends(per_address(PUBLIC))])
def list_guides():
    from app.help import GUIDES

    return [
        {"slug": g.slug, "title": g.title, "summary": g.summary, "audience": list(g.audience)}
        for g in GUIDES
    ]


@router.get("/public/help/{slug}", dependencies=[Depends(per_address(PUBLIC))])
def read_guide(slug: str):
    from app.help import BY_SLUG

    guide = BY_SLUG.get(slug)
    if guide is None:
        raise HTTPException(404, "Guía no encontrada")
    return {
        "slug": guide.slug,
        "title": guide.title,
        "audience": list(guide.audience),
        "text": guide.text,
    }
