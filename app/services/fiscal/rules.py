"""DGII document types, number formats and taxpayer ids (Fase 4, block F).

NCF: a letter B, the two-digit type and 8 digits (B0200000001).
e-CF: a letter E, the two-digit type and 10 digits (E320000000001).
"""

from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException

DOC_TYPES = {
    "B01": "Factura de crédito fiscal",
    "B02": "Factura de consumo",
    "B04": "Nota de crédito",
    "B14": "Factura de regímenes especiales",
    "B15": "Factura gubernamental",
    "E31": "Factura de crédito fiscal electrónica",
    "E32": "Factura de consumo electrónica",
    "E34": "Nota de crédito electrónica",
    "E44": "Comprobante electrónico de regímenes especiales",
    "E45": "Comprobante electrónico gubernamental",
}
CREDIT_NOTES = {"B04", "E34"}
# DGII 608: reasons to void a number.
VOID_REASONS = {
    "01": "Deterioro de factura preimpresa",
    "02": "Errores de impresión (factura preimpresa)",
    "03": "Impresión defectuosa",
    "04": "Corrección de la información",
    "05": "Cambio de productos",
    "06": "Devolución de productos",
    "07": "Omisión de productos",
    "08": "Errores en secuencia de NCF",
    "09": "Por cese de operaciones",
    "10": "Pérdida o hurto de talonarios",
}
ITBIS_RATES = (Decimal("0"), Decimal("16"), Decimal("18"))


def electronic(doc_type: str) -> bool:
    return doc_type.startswith("E")


def number_text(doc_type: str, number: int) -> str:
    digits = 10 if electronic(doc_type) else 8
    if number >= 10**digits:
        raise HTTPException(422, "El número supera la longitud del comprobante")
    return f"{doc_type}{number:0{digits}d}"


def max_number(doc_type: str) -> int:
    return 10 ** (10 if electronic(doc_type) else 8) - 1


def receipt_type(mode: str, buyer_tax_id: str) -> str:
    """Consumer receipt unless the buyer gave an RNC or cédula for tax credit."""
    credit = bool(buyer_tax_id)
    if mode == "ecf":
        return "E31" if credit else "E32"
    return "B01" if credit else "B02"


def credit_note_type(doc_type: str) -> str:
    return "E34" if electronic(doc_type) else "B04"


def valid_rnc(value: str) -> bool:
    if len(value) != 9 or not value.isdigit():
        return False
    weights = (7, 9, 8, 6, 5, 4, 3, 2)
    total = sum(int(d) * w for d, w in zip(value[:8], weights, strict=True))
    remainder = total % 11
    check = 2 if remainder == 0 else 1 if remainder == 1 else 11 - remainder
    return check == int(value[8])


def valid_cedula(value: str) -> bool:
    if len(value) != 11 or not value.isdigit():
        return False
    total = 0
    for index, digit in enumerate(value[:10]):
        product = int(digit) * (1 if index % 2 == 0 else 2)
        total += product // 10 + product % 10
    return (10 - total % 10) % 10 == int(value[10])


def clean_tax_id(value: str | None) -> str:
    """RNC (9 digits) or cédula (11 digits), without dashes; empty is allowed."""
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if not digits:
        return ""
    if not (valid_rnc(digits) or valid_cedula(digits)):
        raise HTTPException(422, "El RNC o la cédula no es válido. Revisa los dígitos")
    return digits


def split_itbis(total_cents: int, rate: Decimal) -> tuple[int, int]:
    """Amount with ITBIS included -> (base, ITBIS), in cents."""
    if not rate:
        return total_cents, 0
    base = (Decimal(total_cents) / (1 + rate / 100)).quantize(Decimal("1"), ROUND_HALF_UP)
    return int(base), total_cents - int(base)
