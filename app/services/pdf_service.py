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


def simple_pdf(title: str, lines: list[str], qr: str | None = None) -> bytes:
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
    if qr:
        # e-CF (Fase 4 F5): the DGII's check link as a QR code.
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing

        widget = QrCodeWidget(qr)
        left, bottom, right, top = widget.getBounds()
        side = 110
        drawing = Drawing(
            side, side, transform=[side / (right - left), 0, 0, side / (top - bottom), 0, 0]
        )
        drawing.add(widget)
        paragraphs += [Spacer(1, 10), drawing]
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
    tiny = ParagraphStyle("Tiny", fontName=FONT, fontSize=5.6, leading=6.6, alignment=1)
    tiny_bold = ParagraphStyle(
        "TinyBold", fontName=FONT_BOLD, fontSize=5.6, leading=6.6, alignment=1
    )
    green = HexColor("#D5E5B5")
    note = ParagraphStyle("Note", fontName=FONT, fontSize=7, leading=8.5)
    note_bold = ParagraphStyle("NoteBold", fontName=FONT_BOLD, fontSize=7, leading=8.5)

    def number(value):
        return f"{value:g}" if isinstance(value, (int, float)) else (value or "")

    def official_pages(card):
        """Official MINERD secondary report card (Fase 3 F2): cover and grades pages.

        Mirrors the ministry's model (1.er grado, nivel secundario) with text
        headings; the government emblem is not reproduced.
        """
        school = card["institution"]
        grade = card["grade_number"]
        cycle = "Primer ciclo" if grade <= 3 else "Segundo ciclo"
        ordinal = {1: "1.er", 2: "2.º", 3: "3.er", 4: "4.º", 5: "5.º", 6: "6.º"}.get(
            grade, f"{grade}.º"
        )
        year = card["school_year"].replace("-", " – ")
        fields = [
            ("Año escolar", year),
            ("Sección", card["section_name"]),
            ("Número de orden", str(card["order_number"])),
            ("Nombre (s)", card["first_name"]),
            ("Apellido (s)", card["last_name"]),
            ("ID estudiante (SIGERD)", card["sigerd_id"]),
            ("Docente", card["homeroom_teacher"] or ""),
            ("Centro educativo", school["name"]),
            ("Código del centro", school["school_code"]),
            ("Tanda", card["shift"].capitalize()),
            ("Teléfono del centro", school["phone"]),
            ("Distrito educativo", school["district"]),
            ("Regional de educación", school["regional"]),
            ("Provincia", school["province"]),
            ("Municipio", school["municipality"]),
        ]
        half = usable / 2 - 12
        signature_rows = [[cell("FIRMA DEL PADRE, MADRE O TUTOR", bold)]] + [
            [cell(f"{p['months']}:  ______________________________________", body)]
            for p in card["periods"]
        ]
        signatures = Table(signature_rows, colWidths=[half])
        observations = [[cell("Observaciones:", bold)]] + [
            [cell(f"{c['period']}: {c['comment']}", body)] for c in card["comments"]
        ]
        observations += [[cell(" ", body)] for _ in range(max(0, 14 - len(observations)))]
        notes = Table(
            observations, colWidths=[half], rowHeights=[None] + [18] * (len(observations) - 1)
        )
        for table in (signatures, notes):
            table.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.6, ink),
                        ("BACKGROUND", (0, 0), (-1, 0), green),
                        ("LINEBELOW", (0, 1), (-1, -1), 0.3, line),
                    ]
                )
            )
        left = [signatures, Spacer(1, 14), notes]
        right = [
            Paragraph("REPÚBLICA DOMINICANA · MINISTERIO DE EDUCACIÓN", bold),
            Paragraph("Viceministerio de Servicios Técnicos y Pedagógicos", small),
            Paragraph("Dirección General de Educación Secundaria", small),
            Spacer(1, 10),
            Paragraph("BOLETÍN DE CALIFICACIONES", heading),
            Paragraph(escape(f"{ordinal} grado · {cycle} · Nivel secundario"), bold),
            Spacer(1, 8),
            Table(
                [[cell(f"{name}:", bold), cell(value or "", body)] for name, value in fields],
                colWidths=[half * 0.38, half * 0.62],
                style=TableStyle([("LINEBELOW", (1, 0), (1, -1), 0.4, line)]),
            ),
        ]
        cover = Table([[left, right]], colWidths=[usable / 2, usable / 2])
        cover.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(cover)
        story.append(PageBreak())

        story.append(
            Paragraph(
                escape(
                    f"Nombre(s) y apellido(s): {card['student_name']}    Grado: {ordinal} · "
                    f"{card['career_name']}    Sección: {card['section_name']}"
                ),
                small,
            )
        )
        story.append(Spacer(1, 4))
        groups = card["competency_groups"] or ["Competencias"] * 4
        w_comp = card["weights"].get("completivo", 50)
        w_ext = card["weights"].get("extraordinario", 30)
        head1 = [Paragraph("COMPETENCIAS FUNDAMENTALES", tiny_bold)]
        for name in groups:
            head1 += [Paragraph(escape(name), tiny_bold), "", "", ""]
        head1 += [Paragraph("PROMEDIO GRUPO DE COMPETENCIAS ESPECÍFICAS", tiny_bold), "", "", ""]
        head1 += [Paragraph("C.F. DEL ÁREA", tiny_bold)]
        head1 += [Paragraph("CALIFICACIÓN COMPLETIVA", tiny_bold), "", "", ""]
        head1 += [Paragraph("CALIFICACIÓN EXTRAORDINARIA", tiny_bold), "", "", ""]
        head1 += [Paragraph("EVALUACIÓN ESPECIAL", tiny_bold), ""]
        head1 += [Paragraph("SITUACIÓN FINAL", tiny_bold), ""]
        shorts = [p["short"] for p in card["periods"]]
        head2 = [Paragraph("PERÍODOS", tiny_bold)]
        head2 += [Paragraph(s, tiny_bold) for _ in groups for s in shorts]
        head2 += [Paragraph(f"PC{i}", tiny_bold) for i in range(1, len(shorts) + 1)]
        head2 += [""]
        head2 += [
            Paragraph(text, tiny_bold)
            for text in (
                f"{w_comp:g}% C.F.",
                "C.E.C.",
                f"{100 - w_comp:g}% C.E.C.",
                "C.C.F.",
                f"{w_ext:g}% C.F.",
                "C.E. EX",
                f"{100 - w_ext:g}% C.E. EX",
                "C.EX.F.",
                "C.F.",
                "C.E.",
                "A",
                "R",
            )
        ]
        rows = [head1, head2]
        for subject in card["subjects"]:
            competencies = subject["competencies"] or [[None] * len(shorts)] * len(groups)
            row = [
                Paragraph(
                    escape(subject["name"]),
                    ParagraphStyle("Area", fontName=FONT_BOLD, fontSize=6.2, leading=7.2),
                )
            ]
            for values in competencies:
                row += [Paragraph(value or "", tiny) for value in values]
            row += [Paragraph(value or "", tiny) for value in subject["periods"]]
            row += [Paragraph(subject["average_label"] or "", tiny_bold)]
            for kind, weight in (("completivo", w_comp), ("extraordinario", w_ext)):
                exam = subject["recovery"].get(kind)
                if exam:
                    part_average = round(exam["average"] * weight / 100, 2)
                    part_exam = round(exam["exam"] * (100 - weight) / 100, 2)
                    values = [part_average, exam["exam"], part_exam, exam["final"]]
                else:
                    values = ["", "", "", ""]
                row += [Paragraph(number(v), tiny) for v in values]
            especial = subject["recovery"].get("especial")
            row += [
                Paragraph((subject["average_label"] or "") if especial else "", tiny),
                Paragraph(number(especial["exam"]) if especial else "", tiny),
            ]
            row += [
                Paragraph("X" if subject["situation"] == "A" else "", tiny_bold),
                Paragraph("X" if subject["situation"] == "R" else "", tiny_bold),
            ]
            rows.append(row)
        area = 92
        rest = (usable - area) / (len(row) - 1)
        table = Table(rows, colWidths=[area] + [rest] * (len(row) - 1), repeatRows=2)
        style = [
            ("GRID", (0, 0), (-1, -1), 0.4, ink),
            ("BACKGROUND", (0, 0), (-1, 1), green),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 1),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1),
        ]
        column = 1
        for span in [4] * len(groups) + [4]:
            style.append(("SPAN", (column, 0), (column + span - 1, 0)))
            column += span
        style.append(("SPAN", (column, 0), (column, 1)))  # C.F. del área
        column += 1
        for span in (4, 4, 2, 2):
            style.append(("SPAN", (column, 0), (column + span - 1, 0)))
            column += span
        table.setStyle(TableStyle(style))
        story.append(table)
        story.append(Spacer(1, 8))

        attended = [a["present"] + a["late"] for a in card["attendance"]]
        absent = [a["absent"] + a["excused"] for a in card["attendance"]]
        total = sum(attended) + sum(absent)
        yearly = (
            (f"{sum(attended) * 100 / total:.1f} %", f"{sum(absent) * 100 / total:.1f} %")
            if total
            else ("", "")
        )
        attendance = [
            [cell("RESUMEN DE ASISTENCIA DEL/LA ESTUDIANTE", note_bold), "", "", "", ""],
            [
                cell(t, note_bold)
                for t in ("Períodos", "Asistencia", "Ausencia", "% anual asist.", "% anual aus.")
            ],
        ]
        for index, short in enumerate(shorts):
            attendance.append(
                [
                    cell(short, note_bold),
                    cell(attended[index], note),
                    cell(absent[index], note),
                    cell(yearly[0] if index == 0 else "", note),
                    cell(yearly[1] if index == 0 else "", note),
                ]
            )
        attendance_table = Table(attendance, colWidths=[44, 52, 52, 56, 56])
        attendance_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, ink),
                    ("SPAN", (0, 0), (-1, 0)),
                    ("BACKGROUND", (0, 0), (-1, 0), green),
                    ("SPAN", (3, 2), (3, -1)),
                    ("SPAN", (4, 2), (4, -1)),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        legend = [
            ("P1–P4", "Períodos 1 a 4"),
            ("PC", "Promedio grupo de competencias específicas"),
            ("C.F.", "Calificación final"),
            ("C.E.C.", "Calificación evaluación completiva"),
            ("C.C.F.", "Calificación completiva final"),
            ("C.E. EX", "Calificación evaluación extraordinaria"),
            ("C.EX.F.", "Calificación extraordinaria final"),
            ("C.E.", "Calificación especial"),
            ("A / R", "Aprobado / Reprobado"),
        ]
        legend_table = Table(
            [[cell("LEYENDA", note_bold), ""]]
            + [[cell(k, note_bold), cell(v, note)] for k, v in legend],
            colWidths=[48, 152],
        )
        legend_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.4, ink),
                    ("SPAN", (0, 0), (-1, 0)),
                    ("BACKGROUND", (0, 0), (-1, 0), green),
                    ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                ]
            )
        )
        promoted = card["result"] == "promoted"
        repeated = card["result"] == "repeated"
        condition = card["result_label"] + (
            f". {card['result_note']}" if card["result_note"] else ""
        )
        situation = [
            Paragraph(
                escape(
                    f"SITUACIÓN DEL/DE LA ESTUDIANTE:   Promovido/a ({'X' if promoted else ' '})   "
                    f"Repitente ({'X' if repeated else ' '})"
                ),
                note_bold,
            ),
            Spacer(1, 4),
            Table(
                [[cell("CONDICIÓN FINAL DEL/DE LA ESTUDIANTE:", bold)], [cell(condition, body)]],
                colWidths=[usable - 470],
                rowHeights=[None, 46],
                style=TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.4, ink),
                        ("BACKGROUND", (0, 0), (-1, 0), green),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                ),
            ),
            Spacer(1, 22),
            Table(
                [
                    ["_" * 32, "_" * 32],
                    ["Maestro(a) encargado(a) del grado", "Director(a) del centro educativo"],
                ],
                colWidths=[(usable - 470) / 2] * 2,
                style=TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), FONT),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]
                ),
            ),
        ]
        bottom = Table(
            [[attendance_table, legend_table, situation]],
            colWidths=[270, 200, usable - 470],
        )
        bottom.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(bottom)

    for index, card in enumerate(cards):
        if index:
            story.append(PageBreak())
        if card.get("format") == "minerd_secondary":
            official_pages(card)
            continue
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
