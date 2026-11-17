from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

FONT = "Nexo"
FONT_BOLD = "Nexo Bold"
MARGIN = 48
FONT_DIR = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont(FONT, str(FONT_DIR / "Vera.ttf")))
pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONT_DIR / "VeraBd.ttf")))


def simple_pdf(title: str, lines: list[str]) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        title=title,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=100,
        bottomMargin=56,
    )
    body = ParagraphStyle("Body", fontName=FONT, fontSize=10, leading=14, spaceAfter=4)
    heading = ParagraphStyle("Heading", fontName=FONT_BOLD, fontSize=15, leading=19)

    def page_frame(canvas, doc):
        width, height = doc.pagesize
        canvas.saveState()
        canvas.setFillColor(HexColor("#18263C"))
        header = Paragraph(escape(title), heading)
        _, text_height = header.wrap(width - MARGIN * 2, 52)
        header.drawOn(canvas, MARGIN, height - 46 - text_height)
        canvas.setStrokeColor(HexColor("#D9E0E8"))
        canvas.line(MARGIN, height - 84, width - MARGIN, height - 84)
        canvas.setFont(FONT, 9)
        canvas.drawRightString(width - MARGIN, 32, f"Página {doc.page}")
        canvas.restoreState()

    paragraphs = [
        Paragraph(escape(line).replace("\n", "<br/>"), body) if line.strip() else Spacer(1, 7)
        for line in lines
    ]
    document.build(paragraphs or [Spacer(1, 1)], onFirstPage=page_frame, onLaterPages=page_frame)
    return output.getvalue()
