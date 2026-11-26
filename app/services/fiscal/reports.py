"""DGII monthly formats 607 (sales) and 608 (voided numbers) (Fase 4, block F4).

Pipe-separated text, one header line and one line per document, following the
DGII's layouts (Norma 07-2018). The DGII publishes a validation tool in its
Oficina Virtual: run the first file through it with the accountant.
"""

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.models.fiscal_model import FiscalDocument
from app.services.business_time import INSTITUTION_TIME_ZONE, business_day_utc_range

INCOME_OPERATIONS = "01"  # ingresos por operaciones (no financieros)


def month_range(month: str) -> tuple[datetime, datetime]:
    year, number = (int(part) for part in month.split("-"))
    start = date(year, number, 1)
    end = date(year + (number == 12), number % 12 + 1, 1)
    return business_day_utc_range(start)[0], business_day_utc_range(end)[0]


def local_day(moment: datetime) -> str:
    return moment.replace(tzinfo=UTC).astimezone(INSTITUTION_TIME_ZONE).strftime("%Y%m%d")


def amount(value) -> str:
    return f"{value:.2f}"


def id_type(tax_id: str) -> str:
    return "1" if len(tax_id) == 9 else "2" if len(tax_id) == 11 else ""


def documents(db: Session, month: str, status: str) -> list[FiscalDocument]:
    start, end = month_range(month)
    return (
        db.query(FiscalDocument)
        .filter(
            FiscalDocument.status == status,
            FiscalDocument.issued_at >= start,
            FiscalDocument.issued_at < end,
        )
        .order_by(FiscalDocument.ncf)
        .all()
    )


def report_607(db: Session, rnc: str, month: str) -> str:
    affected = {}
    rows = documents(db, month, "issued")
    ids = {row.affected_document_id for row in rows if row.affected_document_id}
    if ids:
        affected = {
            row.fiscal_document_id: row.ncf
            for row in db.query(FiscalDocument).filter(FiscalDocument.fiscal_document_id.in_(ids))
        }
    lines = [f"607|{rnc}|{month.replace('-', '')}|{len(rows)}"]
    for row in rows:
        total = amount(row.total)
        method = row.payment_method
        cash = total if method == "cash" else "0.00"
        transfer = total if method in ("transfer", "check") else "0.00"
        card = total if method in ("card", "online") else "0.00"
        other = total if method not in ("cash", "transfer", "check", "card", "online") else "0.00"
        lines.append(
            "|".join(
                [
                    row.buyer_tax_id,
                    id_type(row.buyer_tax_id),
                    row.ncf,
                    affected.get(row.affected_document_id, ""),
                    INCOME_OPERATIONS,
                    local_day(row.issued_at),
                    "",
                    amount(row.subtotal),
                    amount(row.itbis),
                    "0.00",  # ITBIS retenido por terceros
                    "0.00",  # ITBIS percibido
                    "0.00",  # retención de renta por terceros
                    "0.00",  # ISR percibido
                    "0.00",  # impuesto selectivo al consumo
                    "0.00",  # otros impuestos o tasas
                    "0.00",  # propina legal
                    cash,
                    transfer,
                    card,
                    "0.00",  # venta a crédito
                    "0.00",  # bonos o certificados de regalo
                    "0.00",  # permuta
                    other,
                ]
            )
        )
    return "\n".join(lines) + "\n"


def report_608(db: Session, rnc: str, month: str) -> str:
    rows = documents(db, month, "voided")
    lines = [f"608|{rnc}|{month.replace('-', '')}|{len(rows)}"]
    for row in rows:
        lines.append("|".join([row.ncf, local_day(row.issued_at), row.void_reason or "04"]))
    return "\n".join(lines) + "\n"
