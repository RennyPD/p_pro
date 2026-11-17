from io import BytesIO

from pypdf import PdfReader

from app.services.pdf_service import simple_pdf


def test_pdf_keeps_every_row_and_wraps_long_unicode_text():
    rows = [
        f"Matrícula {i:03d} · Zoé Núñez — " + "Orientación académica " * 12 + f"CIERRE-{i:03d}"
        for i in range(1, 81)
    ]
    report = PdfReader(BytesIO(simple_pdf("LISTA DE INSCRIPCIÓN", rows)))
    assert len(report.pages) > 2
    text = "\n".join(page.extract_text(extraction_mode="layout") for page in report.pages)
    for i in range(1, 81):
        assert text.count(f"Matrícula {i:03d}") == 1
        assert text.count(f"CIERRE-{i:03d}") == 1
    assert "Zoé Núñez —" in text
    assert f"Página {len(report.pages)}" in text
