from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from engine.constants import EXPORT_DISCLAIMER
from engine.models import BridgeFindings, BridgeInputs


def _money(value) -> str:
    return f"AED {value:,.2f}"


def build_pdf_report(inputs: BridgeInputs, findings: BridgeFindings) -> bytes:
    try:
        return _build_reportlab_pdf(inputs, findings)
    except ModuleNotFoundError:
        return _build_basic_pdf(inputs, findings)


def _build_reportlab_pdf(inputs: BridgeInputs, findings: BridgeFindings) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, title="UAE VAT-to-CT Bridge Report", pageCompression=0)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("UAE VAT-to-CT Bridge Report", styles["Title"]),
        Paragraph(_safe(findings.company_name), styles["Heading2"]),
        Paragraph(EXPORT_DISCLAIMER, styles["BodyText"]),
        Spacer(1, 18),
        Paragraph("Executive Summary", styles["Heading2"]),
        Paragraph(
            f"Residual unexplained difference: {_money(findings.residual)}. "
            f"Materiality: {_money(findings.materiality)}. Status: {findings.bridge_status_label}.",
            styles["BodyText"],
        ),
        Paragraph(f"Pre-filing exception score: {findings.score.score} - {findings.score.label}.", styles["BodyText"]),
        Paragraph(findings.score.narrative, styles["BodyText"]),
        Spacer(1, 12),
        Paragraph("Bridge Table", styles["Heading2"]),
    ]
    bridge_rows = [["Line", "Amount"]] + [[row.label, _money(row.amount)] for row in findings.bridge_table]
    story.append(Table(bridge_rows, repeatRows=1, style=_table_style()))
    story.extend([Spacer(1, 12), Paragraph("Checks Summary", styles["Heading2"])])
    check_rows = [["Check", "Status", "Message"]] + [[c.title, c.status, c.message] for c in findings.checks]
    story.append(Table(check_rows, repeatRows=1, colWidths=[120, 55, 260], style=_table_style()))
    story.extend([Spacer(1, 12), Paragraph("Reconciling Items", styles["Heading2"])])
    recon_cell_style = _recon_cell_style(styles)
    recon_rows = [["Category", "Description", "Amount", "Evidence"]] + [
        [
            _paragraph_cell(item.category, recon_cell_style),
            _paragraph_cell(item.description, recon_cell_style),
            _money(item.amount),
            _paragraph_cell(item.evidence_ref, recon_cell_style),
        ]
        for item in inputs.reconciling_items
    ]
    story.append(Table(recon_rows, repeatRows=1, colWidths=[76, 195, 82, 98], style=_recon_table_style()))
    story.extend(
        [
            Spacer(1, 12),
            Paragraph("Methodology", styles["Heading2"]),
            Paragraph(
                "VAT-declared supplies are summed from standard-rated, zero-rated, exempt supplies and adjustments. "
                "Signed reconciling items are added to produce a bridge target. The residual is accounting revenue "
                "per CT computation less the bridge target.",
                styles["BodyText"],
            ),
            Paragraph(findings.rules_stamp, styles["BodyText"]),
            Spacer(1, 12),
            Paragraph("Known Limitations", styles["Heading2"]),
            Paragraph(
                "This MVP does not compute tax liability, validate legal tax positions, connect to EmaraTax, "
                "or provide official filing assurance. It depends on the completeness and quality of "
                "user-provided data.",
                styles["BodyText"],
            ),
            Spacer(1, 12),
            Paragraph("Disclaimer", styles["Heading2"]),
            Paragraph(EXPORT_DISCLAIMER, styles["BodyText"]),
        ]
    )
    doc.build(story)
    return output.getvalue()


def _safe(value: str) -> str:
    return escape(value or "")


def _paragraph_cell(value: str, style):
    from reportlab.platypus import Paragraph

    return Paragraph(_safe(value), style)


def _recon_cell_style(styles):
    style = styles["BodyText"].clone("ReconcilingItemCell")
    style.fontSize = 7.2
    style.leading = 8.4
    style.wordWrap = "CJK"
    return style


def _table_style():
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle

    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF3")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]
    )


def _recon_table_style():
    style = _table_style()
    style.add("FONTSIZE", (0, 1), (-1, -1), 7.2)
    style.add("LEADING", (0, 1), (-1, -1), 8.4)
    style.add("ALIGN", (2, 1), (2, -1), "RIGHT")
    style.add("LEFTPADDING", (0, 0), (-1, -1), 4)
    style.add("RIGHTPADDING", (0, 0), (-1, -1), 4)
    style.add("TOPPADDING", (0, 0), (-1, -1), 4)
    style.add("BOTTOMPADDING", (0, 0), (-1, -1), 4)
    return style


def _build_basic_pdf(inputs: BridgeInputs, findings: BridgeFindings) -> bytes:
    lines = [
        "UAE VAT-to-CT Bridge Report",
        findings.company_name,
        EXPORT_DISCLAIMER,
        "Executive Summary",
        f"Residual unexplained difference: {_money(findings.residual)}",
        f"Materiality: {_money(findings.materiality)}",
        f"Status: {findings.bridge_status_label}",
        f"Pre-filing exception score: {findings.score.score} - {findings.score.label}",
        findings.score.narrative,
        "Bridge Table",
        *[f"{row.label}: {_money(row.amount)}" for row in findings.bridge_table],
        "Checks Summary",
        *[f"{check.title}: {check.status} - {check.message}" for check in findings.checks],
        "Reconciling Items",
        *[
            f"{item.category}: {item.description}; {_money(item.amount)}; evidence {item.evidence_ref}"
            for item in inputs.reconciling_items
        ],
        "Methodology",
        "VAT-declared supplies plus signed reconciling items equals bridge target.",
        findings.rules_stamp,
        "Known Limitations",
        "This MVP does not calculate tax liability, validate legal tax positions, or integrate with EmaraTax.",
        "Disclaimer",
        EXPORT_DISCLAIMER,
    ]
    escaped = [_escape_pdf_text(line) for line in lines]
    text_commands = ["BT", "/F1 10 Tf", "50 790 Td", "14 TL"]
    for idx, line in enumerate(escaped):
        if idx == 0:
            text_commands.append(f"({line}) Tj")
        else:
            text_commands.append(f"T* ({line[:95]}) Tj")
    text_commands.append("ET")
    stream = "\n".join(text_commands).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode())
    return bytes(pdf)


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
