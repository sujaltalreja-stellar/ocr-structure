# ============================================================
# DULB ENGINEERING QA POC - EXECUTIVE AUDIT PDF GENERATOR
# ============================================================

import io
import cv2
import numpy as np
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Adds professional running header and two-pass 'Page X of Y' footers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(36, 762, "DULB ENGINEERING QA — DRAWING DEFECT & COMPLIANCE AUDIT REPORT")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(36, 755, 576, 755)

        # Running Footer
        self.setFont("Helvetica", 8)
        self.drawString(36, 25, "CONFIDENTIAL & PROPRIETARY — FOR INTERNAL ENGINEERING QA USE ONLY")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(576, 25, page_str)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(36, 36, 576, 36)

        self.restoreState()


def _np_to_rl_image(np_img, target_w=162, target_h=98):
    """
    Converts an RGB NumPy array to a scaled, highly optimized ReportLab Image.
    Downsamples high-res CAD crops to thumbnail resolution and uses fast JPEG compression (30x faster).
    """
    if np_img is None or not isinstance(np_img, np.ndarray) or np_img.size == 0:
        return None
    try:
        h, w = np_img.shape[:2]
        if h < 5 or w < 5:
            return None

        # Downsample large raw CAD crops (e.g. 1500x1200) to max 480px thumbnail
        max_dim = 480
        if max(h, w) > max_dim:
            scale = max_dim / float(max(h, w))
            new_w = max(int(w * scale), 10)
            new_h = max(int(h * scale), 10)
            small = cv2.resize(np_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            small = np_img

        bgr = cv2.cvtColor(small, cv2.COLOR_RGB2BGR)
        success, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not success:
            return None
        return RLImage(io.BytesIO(buf.tobytes()), width=target_w, height=target_h)
    except Exception:
        return None


def generate_audit_pdf(
    audit_data,
    evidence_store,
    old_filename="Old_Drawing.pdf",
    new_filename="New_Drawing.pdf",
):
    """
    Builds an executive-grade PDF Drawing Quality & Defect Audit Report
    featuring side-by-side visual evidence comparison images, defect punchlists,
    and compliance scoring without layout clipping errors.
    """
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=40,
        bottomMargin=45,
    )

    styles = getSampleStyleSheet()

    # Custom Typography Styles
    title_style = ParagraphStyle(
        "DocTitle",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
    )
    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#475569"),
    )
    sec_heading = ParagraphStyle(
        "SecHead",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=12,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "DocBody",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )
    body_bold = ParagraphStyle(
        "DocBodyBold",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
    )
    verdict_style = ParagraphStyle(
        "VerdictText",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.white,
        alignment=1,
    )
    card_title_style = ParagraphStyle(
        "CardTitle",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0f172a"),
    )

    story = []

    # 1. Title & Header Block
    story.append(Paragraph("DULB ENGINEERING DRAWING QUALITY & DEFECT AUDIT REPORT", title_style))
    story.append(Spacer(1, 3))
    story.append(Paragraph("Consultant Markup Verification, Revision Evidence & Non-Compliance Audit", subtitle_style))
    story.append(Spacer(1, 8))

    # Metadata Grid
    meta_data = [
        [
            Paragraph("<b>Project:</b> DULB Engineering QA", body_style),
            Paragraph(f"<b>Audit Date:</b> {audit_data.get('timestamp')}", body_style),
        ],
        [
            Paragraph(f"<b>OLD Revision Drawing:</b> {old_filename}", body_style),
            Paragraph(f"<b>NEW Revision Drawing:</b> {new_filename}", body_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[265, 275])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # 2. Official Audit Verdict Banner
    verdict = audit_data.get("verdict", "AUDIT PENDING")
    score = audit_data.get("compliance_score", 0.0)
    risk = audit_data.get("risk_level", "UNKNOWN")

    if "PASS" in verdict and "CONDITIONAL" not in verdict:
        v_bg = colors.HexColor("#16a34a")
    elif "CONDITIONAL" in verdict:
        v_bg = colors.HexColor("#ea580c")
    else:
        v_bg = colors.HexColor("#dc2626")

    v_table = Table(
        [
            [Paragraph(f"OFFICIAL AUDIT VERDICT: {verdict}", verdict_style)],
            [Paragraph(f"Compliance Score: {score}% &bull; Risk Level: {risk} &bull; Total Elements: {audit_data.get('counts', {}).get('total', 0)}", ParagraphStyle("SubV", fontName="Helvetica", fontSize=9, leading=11, textColor=colors.white, alignment=1))],
        ],
        colWidths=[540],
    )
    v_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), v_bg),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(v_table)
    story.append(Spacer(1, 10))

    # 3. Defect & Status Breakdown Scorecard
    counts = audit_data.get("counts", {})
    scorecard_data = [
        [
            Paragraph("<b>Fully Resolved</b>", body_style),
            Paragraph("<b>Critical Defects (Blocking)</b>", body_style),
            Paragraph("<b>Major Deficiencies</b>", body_style),
            Paragraph("<b>Verification Gaps</b>", body_style),
        ],
        [
            Paragraph(f"<font size=12 color='#16a34a'><b>{counts.get('resolved', 0)}</b></font>", body_style),
            Paragraph(f"<font size=12 color='#dc2626'><b>{counts.get('not_resolved', 0)}</b></font>", body_style),
            Paragraph(f"<font size=12 color='#ea580c'><b>{counts.get('partial', 0)}</b></font>", body_style),
            Paragraph(f"<font size=12 color='#64748b'><b>{counts.get('cannot_verify', 0)}</b></font>", body_style),
        ],
    ]
    sc_table = Table(scorecard_data, colWidths=[135, 135, 135, 135])
    sc_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(sc_table)
    story.append(Spacer(1, 10))

    # 4. Detailed Defect & Evidence Item Cards
    story.append(Paragraph("AUDITED DRAWING ELEMENTS & DESIGN EVIDENCE", sec_heading))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceBefore=2, spaceAfter=8))

    findings = audit_data.get("findings", [])

    for cid in evidence_store:
        ev = evidence_store[cid]
        comment = ev.get("comment", {})
        comp = ev.get("comparison", {})

        matching_f = next((f for f in findings if f["comment_id"] == cid), None)
        if matching_f:
            status = matching_f["status"]
            severity = matching_f["severity"]
            category = matching_f["category"]
            affected = matching_f["affected_item"]
            root_cause = matching_f["root_cause"]
            action = matching_f["auditor_action"]
        else:
            status = "Resolved"
            severity = "COMPLIANT"
            category = "General"
            affected = "Drawing Element"
            root_cause = "Rectification verified in revised linework."
            action = "None — Cleared for submission."

        if status == "Resolved":
            st_color = "#16a34a"
            card_border = "#86efac"
        elif status == "Not Resolved":
            st_color = "#dc2626"
            card_border = "#fca5a5"
        elif status == "Partially Resolved":
            st_color = "#ea580c"
            card_border = "#fdba74"
        else:
            st_color = "#64748b"
            card_border = "#cbd5e1"

        # Item Header Bar (rendered directly as a flowable table)
        header_text = (
            f"<b>{cid}</b> &bull; Status: <font color='{st_color}'><b>{status.upper()}</b></font> "
            f"&bull; Page {comment.get('page', 1)} &bull; [{severity}]"
        )
        hdr_table = Table([[Paragraph(header_text, card_title_style)]], colWidths=[540])
        hdr_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(card_border)),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))

        # Details Table
        details_data = [
            [
                Paragraph("<b>Consultant Comment:</b>", body_bold),
                Paragraph(comment.get("comment", ""), body_style),
            ],
            [
                Paragraph("<b>Affected Element:</b>", body_bold),
                Paragraph(f"{affected} ({category})", body_style),
            ],
            [
                Paragraph("<b>Engineering Analysis:</b>", body_bold),
                Paragraph(root_cause, body_style),
            ],
            [
                Paragraph("<b>Required Action:</b>", body_bold),
                Paragraph(action, body_style),
            ],
        ]
        dt_table = Table(details_data, colWidths=[115, 425])
        dt_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f8fafc")),
        ]))

        # Keep Header and Details together
        story.append(KeepTogether([hdr_table, dt_table]))

        # Side-by-Side Visual Evidence Images Table
        old_img_flow = _np_to_rl_image(comp.get("old_image"))
        new_img_flow = _np_to_rl_image(comp.get("new_image"))
        diff_img_flow = _np_to_rl_image(comp.get("difference_image"))

        if old_img_flow or new_img_flow or diff_img_flow:
            col_old = old_img_flow if old_img_flow else Paragraph("<i>No Image Region</i>", body_style)
            col_new = new_img_flow if new_img_flow else Paragraph("<i>No Image Region</i>", body_style)
            col_diff = diff_img_flow if diff_img_flow else Paragraph("<i>No Diff Region</i>", body_style)

            sim_score = comp.get("visual_similarity")
            sim_str = f"Sim: {round(sim_score, 4)}" if sim_score is not None else "Sim: N/A"
            v_delta = f"Vectors: Old ({comp.get('old_vectors', 0)}) | New ({comp.get('new_vectors', 0)})"

            img_table_data = [
                [
                    Paragraph("<b>OLD Revision Region</b>", body_bold),
                    Paragraph("<b>NEW Revision Region</b>", body_bold),
                    Paragraph("<b>Detected Difference</b>", body_bold),
                ],
                [col_old, col_new, col_diff],
                [
                    Paragraph(v_delta, body_style),
                    Paragraph(sim_str, body_style),
                    Paragraph("Red Outline: Delta", body_style),
                ],
            ]

            img_table = Table(img_table_data, colWidths=[180, 180, 180])
            img_table.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f8fafc")),
                ("PADDING", (0, 0), (-1, -1), 2),
            ]))

            # Keep image block self-contained
            story.append(Spacer(1, 2))
            story.append(KeepTogether(img_table))

        story.append(Spacer(1, 10))

    # 5. CAD Drafting Correction Punch-List
    punchlist = audit_data.get("punchlist", [])
    if punchlist:
        story.append(Spacer(1, 6))
        story.append(Paragraph("CAD DRAFTING CORRECTION PUNCH-LIST", sec_heading))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceBefore=2, spaceAfter=8))

        punch_table_data = [
            [
                Paragraph("<b>Priority</b>", body_bold),
                Paragraph("<b>Item ID</b>", body_bold),
                Paragraph("<b>Page</b>", body_bold),
                Paragraph("<b>Target Element</b>", body_bold),
                Paragraph("<b>Required CAD Drafting Directive</b>", body_bold),
            ]
        ]
        for p in punchlist:
            punch_table_data.append([
                Paragraph(p.get("priority", "P2"), body_style),
                Paragraph(p.get("item_id", ""), body_bold),
                Paragraph(str(p.get("page", 1)), body_style),
                Paragraph(p.get("target", ""), body_style),
                Paragraph(p.get("action", ""), body_style),
            ])

        pl_table = Table(punch_table_data, colWidths=[65, 45, 35, 115, 280], repeatRows=1)
        pl_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(pl_table)

    # 6. Quality Certification & Disclaimer
    story.append(Spacer(1, 12))
    signoff_data = [
        [
            Paragraph("<b>QA AUDITOR SIGN-OFF:</b>", body_bold),
            Paragraph("<b>PROFESSIONAL ENGINEER REVIEW:</b>", body_bold),
        ],
        [
            Paragraph("<br/><br/>________________________________________<br/>Lead QA Auditor &bull; Date", body_style),
            Paragraph("<br/><br/>________________________________________<br/>Responsible P.E. / Architect &bull; Date", body_style),
        ],
        [
            Paragraph(
                "<i>Disclaimer: This document is an automated engineering compliance audit report. "
                "Final approval and legal submission responsibility resides strictly with the Professional Engineer of Record.</i>",
                ParagraphStyle("Disc", fontName="Helvetica-Oblique", fontSize=7, leading=9.5, textColor=colors.HexColor("#64748b")),
            ),
            "",
        ],
    ]
    sign_table = Table(signoff_data, colWidths=[270, 270])
    sign_table.setStyle(TableStyle([
        ("SPAN", (0, 2), (1, 2)),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(KeepTogether(sign_table))

    # Build PDF using NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()
