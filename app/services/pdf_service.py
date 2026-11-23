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


def report_card_pdf(cards: list[dict], title: str = "BOLETÍN DE CALIFICACIONES") -> bytes:
    """School report cards (Fase 3 F), one landscape A4 page per student.

    The layout is isolated here: an official format only changes this function.
    """
    from reportlab.lib.pagesizes import landscape
    from reportlab.platypus import PageBreak, Table, TableStyle

    output = BytesIO()
    page = landscape(A4)
    document = SimpleDocTemplate(
        output,
        pagesize=page,
        title=title,
        leftMargin=32,
        rightMargin=32,
        topMargin=28,
        bottomMargin=28,
    )
    ink, line, soft = HexColor("#18263C"), HexColor("#C9D2DD"), HexColor("#EEF2F7")
    small = ParagraphStyle("Small", fontName=FONT, fontSize=8, leading=10)
    body = ParagraphStyle("Body", fontName=FONT, fontSize=9, leading=12)
    bold = ParagraphStyle("Bold", fontName=FONT_BOLD, fontSize=9, leading=12)
    heading = ParagraphStyle("Heading", fontName=FONT_BOLD, fontSize=13, leading=16, textColor=ink)

    def cell(text, style=small):
        return Paragraph(escape(str(text if text is not None else "—")), style)

    def grid(data, widths, header_rows=1):
        table = Table(data, colWidths=widths, repeatRows=header_rows)
        table.hAlign = "LEFT"
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, line),
                    ("BACKGROUND", (0, 0), (-1, header_rows - 1), soft),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return table

    usable = page[0] - 64
    story = []
    for index, card in enumerate(cards):
        if index:
            story.append(PageBreak())
        school = card["institution"]
        ids = " · ".join(
            part
            for part in (
                f"Código {school['school_code']}" if school["school_code"] else "",
                f"Regional {school['regional']}" if school["regional"] else "",
                f"Distrito {school['district']}" if school["district"] else "",
            )
            if part
        )
        story.append(Paragraph(escape(school["name"]), heading))
        if ids:
            story.append(Paragraph(escape(ids), small))
        story.append(Paragraph(escape(f"{title} · Año lectivo {card['school_year']}"), bold))
        story.append(Spacer(1, 6))
        info = [
            [
                cell("Estudiante", bold),
                cell(card["student_name"], body),
                cell("Matrícula", bold),
                cell(card["enrollment_number"], body),
            ],
            [
                cell("Grado y sección", bold),
                cell(card["group_label"], body),
                cell("Titular", bold),
                cell(card["homeroom_teacher"] or "Sin asignar", body),
            ],
        ]
        story.append(grid(info, [usable * 0.14, usable * 0.36, usable * 0.12, usable * 0.38], 0))
        story.append(Spacer(1, 8))
        shorts = [p["short"] for p in card["periods"]]
        header = [cell("Asignatura", bold), *[cell(s, bold) for s in shorts]] + [
            cell(text, bold) for text in ("Promedio", "Compl.", "Extraord.", "Final", "Situación")
        ]
        rows = [header]
        for subject in card["subjects"]:
            rows.append(
                [
                    cell(subject["name"], body),
                    *[cell(value or "—") for value in subject["periods"]],
                    cell(subject["average_label"] or "—"),
                    cell(subject["completivo"] or "—"),
                    cell(subject["extraordinario"] or "—"),
                    cell(subject["final"] or "—", bold),
                    cell(subject["status_label"]),
                ]
            )
        first = usable * 0.26
        rest = (usable - first) / (len(shorts) + 5)
        story.append(grid(rows, [first] + [rest] * (len(shorts) + 5)))
        story.append(
            Paragraph(
                "Compl.: calificación completiva · Extraord.: calificación extraordinaria", small
            )
        )
        story.append(Spacer(1, 8))
        attendance = [[cell("Asistencia", bold), *[cell(s, bold) for s in shorts]]]
        for key, text in (
            ("present", "Presente"),
            ("late", "Tardanzas"),
            ("absent", "Ausencias"),
            ("excused", "Excusas"),
        ):
            attendance.append([cell(text), *[cell(a[key]) for a in card["attendance"]]])
        attendance.append(
            [
                cell("% asistencia", bold),
                *[
                    cell(f"{a['percentage']} %" if a["percentage"] is not None else "—")
                    for a in card["attendance"]
                ],
            ]
        )
        story.append(grid(attendance, [first] + [rest] * len(shorts)))
        story.append(Spacer(1, 8))
        if card["comments"]:
            story.append(Paragraph("Observaciones del titular", bold))
            for comment in card["comments"]:
                story.append(Paragraph(escape(f"{comment['period']}: {comment['comment']}"), body))
            story.append(Spacer(1, 6))
        story.append(
            Paragraph(
                escape(
                    f"Situación final: {card['result_label']} · Nota mínima {card['passing_grade']:g} "
                    f"({card['scale_name']})"
                ),
                bold,
            )
        )
        story.append(Spacer(1, 26))
        signatures = Table(
            [["_" * 34, "_" * 34, "_" * 34], ["Titular", "Dirección", "Padre, madre o tutor"]],
            colWidths=[usable / 3] * 3,
        )
        signatures.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), FONT),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]
            )
        )
        story.append(signatures)
    document.build(story or [Spacer(1, 1)])
    return output.getvalue()
