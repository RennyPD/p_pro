"""Fiscal receipts: issuer, DGII sequences, documents and «facturar a» (Fase 4, block F)."""

import json
from datetime import UTC, date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_permissions
from app.db.Session import get_db
from app.models.finance_model import Payment, StudentAccount
from app.models.fiscal_model import FiscalDocument, FiscalProfile, FiscalSequence
from app.models.user_model import User
from app.pagination import page_query, search
from app.services.audit_log import record
from app.services.business_time import INSTITUTION_TIME_ZONE
from app.services.finance_workflow import get_account, lock_finance
from app.services.fiscal import issuing, reports
from app.services.fiscal.rules import DOC_TYPES, VOID_REASONS, clean_tax_id, valid_rnc
from app.services.pdf_service import simple_pdf
from app.services.rate_limit import EXPORTS, per_account

router = APIRouter(prefix="/fiscal", tags=["fiscal receipts"])
manager = require_permissions("finance.manage", institutional=True)
viewer = require_permissions("finance.view", institutional=True)
collector = require_permissions("finance.collect", institutional=True)
supervisor = require_permissions("finance.supervise", institutional=True)


class ProfileIn(BaseModel):
    enabled: bool
    mode: str = Field(pattern=r"^(ncf|ecf)$")
    rnc: str = Field(default="", max_length=11)
    legal_name: str = Field(default="", max_length=150)
    trade_name: str = Field(default="", max_length=150)
    fiscal_address: str = Field(default="", max_length=250)
    issue_on: str = Field(default="payment", pattern=r"^(payment|request)$")


class SequenceIn(BaseModel):
    doc_type: str = Field(pattern=r"^(B01|B02|B04|B14|B15|E31|E32|E34|E44|E45)$")
    range_start: int = Field(ge=1)
    range_end: int = Field(ge=1)
    expires_on: date | None = None


class VoidRequest(BaseModel):
    reason: str = Field(pattern=r"^(0[1-9]|10)$")
    note: str = Field(min_length=5, max_length=250)


class BillTo(BaseModel):
    name: str = Field(default="", max_length=150)
    tax_id: str = Field(default="", max_length=20)


def profile_out(profile: FiscalProfile | None) -> dict:
    if profile is None:
        return {
            "enabled": False,
            "mode": "ncf",
            "rnc": "",
            "legal_name": "",
            "trade_name": "",
            "fiscal_address": "",
            "issue_on": "payment",
        }
    return {
        key: getattr(profile, key)
        for key in (
            "enabled",
            "mode",
            "rnc",
            "legal_name",
            "trade_name",
            "fiscal_address",
            "issue_on",
        )
    }


@router.get("/profile")
def get_profile(db: Session = Depends(get_db), _user: User = Depends(viewer)):
    return profile_out(issuing.profile_of(db)) | {"doc_types": DOC_TYPES}


@router.put("/profile")
def save_profile(data: ProfileIn, db: Session = Depends(get_db), user: User = Depends(manager)):
    lock_finance(db)
    rnc = "".join(ch for ch in data.rnc if ch.isdigit())
    if data.enabled and not (valid_rnc(rnc) and data.legal_name.strip()):
        raise HTTPException(
            422, "Para emitir comprobantes hacen falta un RNC válido y la razón social"
        )
    profile = issuing.profile_of(db) or FiscalProfile(ecf_secrets="", ecf_provider="sandbox")
    db.add(profile)
    for key, value in data.model_dump().items():
        setattr(profile, key, value.strip() if isinstance(value, str) else value)
    profile.rnc = rnc
    profile.updated_at = issuing.now()
    profile.updated_by = user.user_id
    db.flush()
    record(db, user, "fiscal.profile_saved", "fiscal:profile", json.dumps(profile_out(profile)))
    db.commit()
    return profile_out(profile)


def sequence_out(sequence: FiscalSequence) -> dict:
    return {
        "fiscal_sequence_id": sequence.fiscal_sequence_id,
        "doc_type": sequence.doc_type,
        "label": DOC_TYPES[sequence.doc_type],
        "range_start": sequence.range_start,
        "range_end": sequence.range_end,
        "next_number": sequence.next_number,
        "remaining": max(0, sequence.range_end - sequence.next_number + 1),
        "expires_on": sequence.expires_on.isoformat() if sequence.expires_on else None,
        "active": sequence.active,
    }


@router.get("/sequences")
def list_sequences(db: Session = Depends(get_db), _user: User = Depends(viewer)):
    rows = db.query(FiscalSequence).order_by(FiscalSequence.doc_type, FiscalSequence.range_start)
    return {
        "sequences": [sequence_out(row) for row in rows],
        "alerts": issuing.sequence_alerts(db),
    }


@router.post("/sequences")
def add_sequence(data: SequenceIn, db: Session = Depends(get_db), user: User = Depends(manager)):
    lock_finance(db)
    issuing.validate_range(data.doc_type, data.range_start, data.range_end)
    overlap = (
        db.query(FiscalSequence)
        .filter(
            FiscalSequence.doc_type == data.doc_type,
            FiscalSequence.range_start <= data.range_end,
            FiscalSequence.range_end >= data.range_start,
        )
        .first()
    )
    if overlap is not None:
        raise HTTPException(409, "El rango se cruza con otra secuencia del mismo tipo")
    sequence = FiscalSequence(
        doc_type=data.doc_type,
        range_start=data.range_start,
        range_end=data.range_end,
        next_number=data.range_start,
        expires_on=data.expires_on,
        active=True,
        created_at=issuing.now(),
        created_by=user.user_id,
    )
    db.add(sequence)
    db.flush()
    record(
        db,
        user,
        "fiscal.sequence_added",
        f"fiscal_sequence:{sequence.fiscal_sequence_id}",
        f"{data.doc_type} {data.range_start}-{data.range_end}, vence {data.expires_on or '—'}",
    )
    db.commit()
    return sequence_out(sequence)


@router.post("/sequences/{sequence_id}/deactivate")
def deactivate_sequence(
    sequence_id: int, db: Session = Depends(get_db), user: User = Depends(manager)
):
    lock_finance(db)
    sequence = db.get(FiscalSequence, sequence_id)
    if sequence is None:
        raise HTTPException(404, "Secuencia no encontrada")
    sequence.active = False
    record(
        db, user, "fiscal.sequence_deactivated", f"fiscal_sequence:{sequence_id}", sequence.doc_type
    )
    db.commit()
    return sequence_out(sequence)


def document_out(document: FiscalDocument) -> dict:
    affected = document.affected_document_id
    return {
        "fiscal_document_id": document.fiscal_document_id,
        "doc_type": document.doc_type,
        "label": DOC_TYPES.get(document.doc_type, document.doc_type),
        "ncf": document.ncf,
        "status": document.status,
        "issued_at": document.issued_at.isoformat(),
        "student_id": document.student_id,
        "payment_id": document.payment_id,
        "affected_document_id": affected,
        "buyer_name": document.buyer_name,
        "buyer_tax_id": document.buyer_tax_id,
        "subtotal": f"{document.subtotal:.2f}",
        "itbis": f"{document.itbis:.2f}",
        "total": f"{document.total:.2f}",
        "sequence_expires_on": document.sequence_expires_on.isoformat()
        if document.sequence_expires_on
        else None,
        "ecf_status": document.ecf_status,
        "security_code": document.security_code,
    }


@router.get("/documents")
def list_documents(
    response: Response,
    doc_type: str | None = Query(None, max_length=3),
    q: str | None = Query(None, max_length=60),
    student_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: User = Depends(viewer),
):
    query = db.query(FiscalDocument).order_by(FiscalDocument.fiscal_document_id.desc())
    if doc_type:
        query = query.filter(FiscalDocument.doc_type == doc_type)
    if student_id:
        query = query.filter(FiscalDocument.student_id == student_id)
    query = search(
        query, q, FiscalDocument.ncf, FiscalDocument.buyer_name, FiscalDocument.buyer_tax_id
    )
    return [document_out(row) for row in page_query(query, response, skip, limit)]


@router.get("/payments/{payment_id}")
def documents_of_payment(
    payment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """The receipts of one payment, for whoever may see that account."""
    from app.routers.finance_router import accessible

    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(404, "Pago no encontrado")
    account = db.get(StudentAccount, payment.student_account_id)
    accessible(db, user, account.student_id)
    rows = db.query(FiscalDocument).filter(FiscalDocument.payment_id == payment_id)
    return [document_out(row) for row in rows.order_by(FiscalDocument.fiscal_document_id)]


@router.post("/payments/{payment_id}/issue")
def issue_pending(payment_id: int, db: Session = Depends(get_db), user: User = Depends(collector)):
    """Issue the receipt of a payment (on request, or one left pending)."""
    lock_finance(db)
    payment = db.get(Payment, payment_id)
    if payment is None or payment.status != "posted":
        raise HTTPException(404, "Pago no encontrado")
    account = db.get(StudentAccount, payment.student_account_id)
    document = issuing.issue_for_payment(db, payment, account, user)
    record(db, user, "fiscal.issued_on_request", f"payment:{payment_id}", document.ncf)
    db.commit()
    return document_out(document)


@router.get("/documents/{document_id}.pdf", dependencies=[Depends(per_account(EXPORTS))])
def document_pdf(
    document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    from app.routers.finance_router import accessible

    document = db.get(FiscalDocument, document_id)
    if document is None:
        raise HTTPException(404, "Comprobante no encontrado")
    if document.student_id is not None:
        accessible(db, user, document.student_id)
    profile = issuing.profile_of(db)
    issued = document.issued_at.replace(tzinfo=UTC).astimezone(INSTITUTION_TIME_ZONE)
    lines = [
        f"{profile.legal_name if profile else ''}",
        f"RNC: {profile.rnc if profile else ''}",
        profile.fiscal_address if profile else "",
        "",
        f"{DOC_TYPES.get(document.doc_type, document.doc_type)}",
        f"NCF: {document.ncf}",
    ]
    if document.sequence_expires_on and not document.security_code:
        lines.append(f"Válido hasta: {document.sequence_expires_on:%d/%m/%Y}")
    if document.affected_document_id:
        affected = db.get(FiscalDocument, document.affected_document_id)
        lines.append(f"NCF modificado: {affected.ncf if affected else ''}")
    lines += [
        f"Fecha: {issued:%d/%m/%Y %H:%M}",
        f"Cliente: {document.buyer_name}",
        f"RNC/Cédula del cliente: {document.buyer_tax_id or '—'}",
        "",
    ]
    for line in document.lines:
        rate = f"ITBIS {line.itbis_rate:.0f}%" if line.itbis_rate else "Exento"
        lines.append(f"{line.description} · {rate} · RD$ {line.line_total:,.2f}")
    lines += [
        "",
        f"Subtotal: RD$ {document.subtotal:,.2f}",
        f"ITBIS: RD$ {document.itbis:,.2f}",
        f"Total: RD$ {document.total:,.2f}",
    ]
    if document.security_code:
        lines += [
            "",
            f"Código de seguridad: {document.security_code}",
            f"Fecha de firma digital: {document.signed_at:%d-%m-%Y %H:%M:%S}"
            if document.signed_at
            else "",
        ]
    elif document.ecf_status in ("pending", "in_process"):
        lines += ["", "Comprobante electrónico en proceso de validación"]
    if document.status == "voided":
        lines.append("ANULADO")
    return Response(
        simple_pdf(
            DOC_TYPES.get(document.doc_type, "Comprobante fiscal"),
            lines,
            qr=document.qr_url if document.ecf_status == "accepted" else None,
        ),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{document.ncf}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/accounts/{student_id}/bill-to")
def get_bill_to(student_id: int, db: Session = Depends(get_db), _user: User = Depends(collector)):
    account = get_account(db, student_id)
    return {"name": account.bill_to_name or "", "tax_id": account.bill_to_tax_id or ""}


@router.put("/accounts/{student_id}/bill-to")
def set_bill_to(
    student_id: int, data: BillTo, db: Session = Depends(get_db), user: User = Depends(collector)
):
    """Who the receipts are issued to; with an RNC or cédula they give tax credit."""
    lock_finance(db)
    tax_id = clean_tax_id(data.tax_id)
    if tax_id and not data.name.strip():
        raise HTTPException(422, "Escribe el nombre o la razón social del RNC")
    account = get_account(db, student_id, write=True)
    account.bill_to_name, account.bill_to_tax_id = data.name.strip(), tax_id
    record(
        db,
        user,
        "fiscal.bill_to_changed",
        f"student:{student_id}",
        f"{account.bill_to_name or 'Consumidor final'} {tax_id or ''}".strip(),
    )
    db.commit()
    return {"name": account.bill_to_name, "tax_id": account.bill_to_tax_id}


@router.post("/documents/{document_id}/void")
def void_document(
    document_id: int,
    data: VoidRequest,
    db: Session = Depends(get_db),
    user: User = Depends(supervisor),
):
    """Void a number with a DGII reason (608). A charged sale is undone with a credit
    note instead: this is for receipts issued by mistake."""
    lock_finance(db)
    document = db.get(FiscalDocument, document_id)
    if document is None:
        raise HTTPException(404, "Comprobante no encontrado")
    if document.status == "voided":
        raise HTTPException(409, "El comprobante ya está anulado")
    if (
        db.query(FiscalDocument.fiscal_document_id)
        .filter(
            FiscalDocument.affected_document_id == document_id,
            FiscalDocument.status == "issued",
        )
        .first()
    ):
        raise HTTPException(409, "El comprobante tiene una nota de crédito; anula primero la nota")
    document.status = "voided"
    document.void_reason, document.void_note = data.reason, data.note.strip()
    record(
        db,
        user,
        "fiscal.voided",
        f"fiscal_document:{document_id}",
        f"{document.ncf}: {VOID_REASONS[data.reason]}; {data.note.strip()}",
    )
    db.commit()
    return document_out(document)


def month_param(month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")) -> str:
    return month


@router.get("/reports/607.txt", dependencies=[Depends(per_account(EXPORTS))])
def dgii_607(
    month: str = Depends(month_param), db: Session = Depends(get_db), _user: User = Depends(viewer)
):
    return dgii_file(db, month, "607")


@router.get("/reports/608.txt", dependencies=[Depends(per_account(EXPORTS))])
def dgii_608(
    month: str = Depends(month_param), db: Session = Depends(get_db), _user: User = Depends(viewer)
):
    return dgii_file(db, month, "608")


def dgii_file(db: Session, month: str, kind: str) -> Response:
    profile = issuing.profile_of(db)
    if profile is None or not profile.rnc:
        raise HTTPException(409, "Configura primero el RNC de la institución")
    build = reports.report_607 if kind == "607" else reports.report_608
    return Response(
        build(db, profile.rnc, month),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="DGII_F_{kind}_{profile.rnc}_{month.replace("-", "")}.txt"',
            "Cache-Control": "no-store",
        },
    )
