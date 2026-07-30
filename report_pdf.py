"""Turn one call's QA result into a clean, downloadable PDF report.

The scoring is already done by run_pipeline in web_app.py; this module only
lays that result out on a page. It takes the same result dict the /analyze
endpoint returns and produces PDF bytes, so nothing new is analysed here.

    from report_pdf import build_report
    pdf_bytes = build_report(result)
"""

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)


def _register_fonts():
    """Embed a real TrueType font so the PDF renders in every viewer.

    reportlab's built-in Helvetica is not embedded, which some viewers can't
    draw. We try a few common system fonts; if none are found we fall back to
    Helvetica, which still renders in all standard PDF readers.
    """
    candidates = [
        ("/System/Library/Fonts/Supplemental/Arial.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for regular, bold in candidates:
        try:
            pdfmetrics.registerFont(TTFont("ReportFont", regular))
            pdfmetrics.registerFont(TTFont("ReportFont-Bold", bold))
            # Register as a family so inline <b> markup maps to the bold face.
            pdfmetrics.registerFontFamily(
                "ReportFont", normal="ReportFont", bold="ReportFont-Bold")
            return "ReportFont", "ReportFont-Bold"
        except Exception:
            continue
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = _register_fonts()

# Colours per band, so the header reads at a glance.
BAND_COLORS = {
    "GOOD": colors.HexColor("#1a7f37"),
    "OKAY": colors.HexColor("#9a6700"),
    "NEEDS IMPROVEMENT": colors.HexColor("#b42318"),
}
# Colours for a PASS / PARTIAL / FAIL verdict.
VERDICT_COLORS = {
    "PASS": colors.HexColor("#1a7f37"),
    "PARTIAL": colors.HexColor("#9a6700"),
    "FAIL": colors.HexColor("#b42318"),
    "UNRATED": colors.HexColor("#57606a"),
}
INK = colors.HexColor("#1f2328")
MUTED = colors.HexColor("#57606a")
LINE = colors.HexColor("#d0d7de")
PANEL = colors.HexColor("#f6f8fa")


def _hx(color):
    """'#rrggbb' string for a reportlab colour, for inline <font> markup."""
    return "#" + color.hexval()[2:]


def _styles():
    """Paragraph styles used throughout the report."""
    ss = getSampleStyleSheet()
    base = ss["Normal"]
    base.fontName = FONT
    base.fontSize = 9.5
    base.leading = 13
    base.textColor = INK
    return {
        "body": base,
        "h1": ParagraphStyle(
            "h1", parent=base, fontName=FONT_BOLD, fontSize=17,
            leading=21, spaceAfter=2),
        "h2": ParagraphStyle(
            "h2", parent=base, fontName=FONT_BOLD, fontSize=11.5,
            leading=15, spaceBefore=12, spaceAfter=5, textColor=INK),
        "muted": ParagraphStyle(
            "muted", parent=base, textColor=MUTED, fontSize=8.5, leading=11),
        "cell": ParagraphStyle(
            "cell", parent=base, fontSize=9, leading=12),
        "cellmuted": ParagraphStyle(
            "cellmuted", parent=base, fontSize=8.5, leading=11,
            textColor=MUTED),
    }


def _fmt(score):
    """A sub-score number, or 'n/a' when the component was not available."""
    return "n/a" if score is None else f"{score:g}"


def _as_lines(suggestions):
    """Normalise suggestions (a newline string or a list) into clean lines.

    The pipeline returns suggestions as one newline-separated string, and each
    line may already start with a bullet marker. We split it into lines and
    strip any leading '-', '*' or bullet so we don't double up.
    """
    if isinstance(suggestions, str):
        items = suggestions.splitlines()
    else:
        items = list(suggestions)
    lines = []
    for item in items:
        text = str(item).strip().lstrip("-*•").strip()
        if text:
            lines.append(text)
    return lines


def _header(result, st):
    """The top band: big final score, its band, and the date."""
    final = result.get("final", 0)
    bandtext = str(result.get("band", "")).upper()
    color = BAND_COLORS.get(bandtext, MUTED)

    score_cell = Paragraph(
        f'<font size=26><b>{final:g}</b></font>'
        f'<font size=12 color="#57606a"> / 100</font>', st["body"])
    band_cell = Paragraph(
        f'<font size=13 color="{_hx(color)}"><b>{bandtext}</b></font>'
        f'<br/><font size=8 color="#57606a">'
        f'{datetime.now():%d %b %Y, %H:%M}</font>', st["body"])

    t = Table([[score_cell, band_cell]], colWidths=[3.1 * inch, 3.4 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("BOX", (0, 0), (-1, -1), 0.75, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
    ]))
    return t


def _subscores(result, st):
    """The five component sub-scores as a compact table."""
    rows = [["Component", "Score"]]
    data = [
        ("Agent handling", result.get("agent")),
        ("Answer accuracy", result.get("accuracy_overall")),
        ("Compliance", result.get("compliance_score")),
        ("Customer sentiment", result.get("conversation")),
        ("Response time", result.get("response_time_score")),
    ]
    for name, val in data:
        rows.append([name, _fmt(val)])
    t = Table(rows, colWidths=[4.9 * inch, 1.6 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("BACKGROUND", (0, 0), (-1, 0), PANEL),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _verdict_para(rating, st):
    """A coloured PASS / PARTIAL / FAIL cell."""
    r = (rating or "UNRATED").upper()
    color = _hx(VERDICT_COLORS.get(r, MUTED))
    return Paragraph(f'<font color="{color}"><b>{r}</b></font>', st["cell"])


def _scorecard(result, st):
    """The agent scorecard: parameter, verdict, reason."""
    rows = [["Parameter", "Verdict", "Reason"]]
    for r in result.get("ratings", []):
        rows.append([
            Paragraph(r.get("name", ""), st["cell"]),
            _verdict_para(r.get("rating"), st),
            Paragraph(r.get("reason", "") or "", st["cellmuted"]),
        ])
    t = Table(rows, colWidths=[1.5 * inch, 0.9 * inch, 4.1 * inch])
    t.setStyle(_table_style())
    return t


def _compliance(result, st):
    """Compliance rules: rule, status, evidence."""
    rows = [["Rule", "Status", "Evidence"]]
    for r in result.get("compliance", []):
        status = r.get("status", "")
        color = ("#1a7f37" if status == "OK" else "#b42318")
        rows.append([
            Paragraph(r.get("rule", ""), st["cell"]),
            Paragraph(f'<font color="{color}"><b>{status}</b></font>',
                      st["cell"]),
            Paragraph(r.get("evidence", "") or "-", st["cellmuted"]),
        ])
    t = Table(rows, colWidths=[2.4 * inch, 0.8 * inch, 3.3 * inch])
    t.setStyle(_table_style())
    return t


def _accuracy(result, st):
    """Answer accuracy: question, what was covered, what was missed."""
    rows = [["Question", "Covered", "Missed"]]
    for r in result.get("accuracy", []):
        covered = ", ".join(r.get("covered", [])) or "-"
        missed = ", ".join(r.get("missed", [])) or "-"
        rows.append([
            Paragraph(r.get("client_question", ""), st["cell"]),
            Paragraph(covered, st["cellmuted"]),
            Paragraph(missed, st["cellmuted"]),
        ])
    t = Table(rows, colWidths=[2.4 * inch, 2.05 * inch, 2.05 * inch])
    t.setStyle(_table_style())
    return t


def _table_style():
    """Shared header/grid style for the detail tables."""
    return TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), INK),
        ("BACKGROUND", (0, 0), (-1, 0), PANEL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ])


def build_report(result):
    """Render a QA result dict to PDF bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        title="Call QA Report")
    st = _styles()
    flow = []

    flow.append(Paragraph("Call QA Report", st["h1"]))
    flow.append(Paragraph(
        "Automated quality score for a single support call.", st["muted"]))
    flow.append(Spacer(1, 10))
    flow.append(_header(result, st))

    warning = result.get("warning")
    if warning:
        flow.append(Spacer(1, 8))
        flow.append(Paragraph(
            f'<font color="#b42318"><b>Note:</b> {warning}</font>',
            st["cellmuted"]))

    summary = result.get("summary")
    if summary:
        flow.append(Paragraph("Summary", st["h2"]))
        flow.append(Paragraph(summary, st["body"]))

    flow.append(Paragraph("Score breakdown", st["h2"]))
    flow.append(_subscores(result, st))

    if result.get("ratings"):
        flow.append(Paragraph("Agent scorecard", st["h2"]))
        flow.append(_scorecard(result, st))

    if result.get("compliance"):
        flow.append(Paragraph("Compliance", st["h2"]))
        flow.append(_compliance(result, st))

    if result.get("accuracy"):
        flow.append(Paragraph("Answer accuracy", st["h2"]))
        flow.append(_accuracy(result, st))

    suggestions = _as_lines(result.get("suggestions") or [])
    if suggestions:
        flow.append(Paragraph("Coaching suggestions", st["h2"]))
        for s in suggestions:
            flow.append(Paragraph(f"&bull;&nbsp;&nbsp;{s}", st["body"]))

    doc.build(flow)
    buf.seek(0)
    return buf.getvalue()
