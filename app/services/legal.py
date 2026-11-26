"""Acceptance of the legal documents (Fase 5, step G3).

- Self sign-up: the terms and the privacy policy, by the person registering.
- Each institution: its administrator (``settings.manage``) accepts the terms
  and the data processing agreement on its behalf, again whenever their
  version changes. Other accounts are never blocked.
"""

from sqlalchemy.orm import Session

from app.legal import DOCUMENTS, INSTITUTION_DOCUMENTS
from app.models.legal_model import LegalAcceptance, now


def accept(
    db: Session,
    kinds,
    *,
    institution_id: int | None,
    user_id: int | None,
    accepted_by: str,
    ip: str = "",
) -> list[LegalAcceptance]:
    rows = []
    for kind in kinds:
        document = DOCUMENTS[kind]
        row = LegalAcceptance(
            kind=kind,
            version=document.version,
            institution_id=institution_id,
            user_id=user_id,
            accepted_by=accepted_by[:255],
            ip=ip[:64],
            accepted_at=now(),
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def pending_for_institution(db: Session, institution_id: int) -> list[str]:
    """Documents whose current version the institution has not accepted yet."""
    accepted = {
        (kind, version)
        for kind, version in db.query(LegalAcceptance.kind, LegalAcceptance.version).filter(
            LegalAcceptance.institution_id == institution_id
        )
    }
    return [
        kind for kind in INSTITUTION_DOCUMENTS if (kind, DOCUMENTS[kind].version) not in accepted
    ]
