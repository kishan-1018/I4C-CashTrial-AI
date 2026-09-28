"""
Forensic Evidence & Integrity Report PDF Generator.
Complies with §9 and §19 of the implementation plan:
- Windows & ReportLab Unicode safety (ASCII-safe 'INR' formatting)
- Cryptographic SHA-256 integrity watermark and audit summary
- Multi-state transaction hop ledger
- Explicit legal disclaimer (integrity mechanism, non-certified)
"""

import io
import datetime
import hashlib
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

class ForensicPDFGenerator:
    """Produces Forensic Evidence & Integrity Report PDFs."""

    @staticmethod
    def generate_dossier_pdf(complaint: Dict[str, Any], decision_support: Dict[str, Any], audit_events: List[Dict[str, Any]]) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=letter,
            rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#0F172A'),
            alignment=1
        )
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#475569'),
            alignment=1
        )
        h2_style = ParagraphStyle(
            'H2',
            parent=styles['Heading2'],
            fontSize=12,
            leading=15,
            textColor=colors.HexColor('#1E293B'),
            spaceBefore=10,
            spaceAfter=6
        )
        normal_style = ParagraphStyle(
            'NormalStyle',
            parent=styles['Normal'],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor('#1E293B')
        )
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor('#64748B'),
            alignment=1
        )

        elements = []

        # Header
        elements.append(Paragraph("<b>FORENSIC EVIDENCE & INTEGRITY REPORT</b>", title_style))
        elements.append(Paragraph("INDIAN CYBER CRIME COORDINATION CENTRE (I4C) — DECISION-SUPPORT PROTOTYPE", subtitle_style))
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284C7'), spaceBefore=2, spaceAfter=10))

        # Metadata Summary Box
        cid = complaint.get("complaint_id", "UNKNOWN")
        IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        now_str = datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
        amount = complaint.get("disputed_amount_inr", 0)
        delay = complaint.get("reporting_delay_minutes", 0)
        scam = complaint.get("scam_category", "UNKNOWN")
        origin = complaint.get("origin_jurisdiction", {}).get("state", "UNKNOWN")

        summary_data = [
            [Paragraph("<b>Incident Reference:</b>", normal_style), Paragraph(str(cid), normal_style),
             Paragraph("<b>Report Generated:</b>", normal_style), Paragraph(now_str, normal_style)],
            [Paragraph("<b>Disputed Amount:</b>", normal_style), Paragraph(f"INR {amount:,.2f}", normal_style),
             Paragraph("<b>Reporting Delay:</b>", normal_style), Paragraph(f"{delay} minutes", normal_style)],
            [Paragraph("<b>Scam Category:</b>", normal_style), Paragraph(scam, normal_style),
             Paragraph("<b>Origin Jurisdiction:</b>", normal_style), Paragraph(origin, normal_style)]
        ]
        t_summary = Table(summary_data, colWidths=[110, 160, 110, 160])
        t_summary.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t_summary)
        elements.append(Spacer(1, 12))

        # Analytical Outputs & Predictions
        elements.append(Paragraph("1. AI Predictive Analysis & Triage Summary", h2_style))
        p_tier = decision_support.get("priority_assessment", {}).get("priority_tier", "HIGH PRIORITY")
        corridor = decision_support.get("taxonomy", {}).get("predicted", {}).get("primary_corridor", {})
        top_tp = decision_support.get("taxonomy", {}).get("predicted", {}).get("top_candidate_touchpoint", {})
        eta = decision_support.get("response_opportunity", {}).get("patrol_eta_range", "7-12 mins")

        ai_data = [
            [Paragraph("<b>Response Priority:</b>", normal_style), Paragraph(f"<b>{p_tier}</b>", normal_style)],
            [Paragraph("<b>Predicted Corridor:</b>", normal_style), Paragraph(f"{corridor.get('name', 'N/A')} ({corridor.get('confidence', 0)*100:.1f}%)", normal_style)],
            [Paragraph("<b>Top Candidate Touchpoint:</b>", normal_style), Paragraph(f"{top_tp.get('institution_name', 'N/A')} [{top_tp.get('touchpoint_type', 'N/A')}]", normal_style)],
            [Paragraph("<b>Estimated Patrol ETA:</b>", normal_style), Paragraph(eta, normal_style)]
        ]
        t_ai = Table(ai_data, colWidths=[140, 400])
        t_ai.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t_ai)
        elements.append(Spacer(1, 12))

        # Transaction Trail Table
        elements.append(Paragraph("2. Multi-Hop Money Flow Trail (Beneficiary Accounts)", h2_style))
        chain = complaint.get("transaction_chain", [])
        tx_rows = [["Hop", "Bank", "IFSC", "Receiver Account", "UTR", "Amount", "Transit State"]]
        for h in chain:
            tx_rows.append([
                str(h.get("hop_number", "")),
                (h.get("bank_name") or "")[:18],
                h.get("ifsc") or "",
                (h.get("receiver_account") or "")[:16],
                (h.get("utr_number") or "")[:14],
                f"INR {h.get('amount_inr', 0):,.0f}",
                (h.get("branch_state") or "")[:12]
            ])
        t_tx = Table(tx_rows, colWidths=[25, 95, 75, 95, 85, 75, 90])
        t_tx.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0284C7')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7.5),
            ('FONTSIZE', (0, 1), (-1, -1), 7.5),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(t_tx)
        elements.append(Spacer(1, 12))

        # Audit Provenance & SHA-256 Block
        elements.append(Paragraph("3. Cryptographic Chain & Audit Provenance", h2_style))
        last_event = audit_events[-1] if audit_events else {"payload_hash_sha256": "N/A", "timestamp": now_str}
        sha_hash = last_event.get("payload_hash_sha256", hashlib.sha256(cid.encode()).hexdigest())

        audit_data = [
            [Paragraph("<b>Cryptographic Ledger Hash:</b>", normal_style), Paragraph(f"<font color='#0369A1'><b>{sha_hash}</b></font>", normal_style)],
            [Paragraph("<b>Hashing Algorithm:</b>", normal_style), Paragraph("SHA-256 (FIPS 180-4)", normal_style)],
            [Paragraph("<b>Audit Ledger Chain Depth:</b>", normal_style), Paragraph(f"{len(audit_events)} recorded events", normal_style)]
        ]
        t_audit = Table(audit_data, colWidths=[160, 380])
        t_audit.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(t_audit)
        elements.append(Spacer(1, 18))

        # Legal & Governance Boundary Note
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#94A3B8'), spaceBefore=2, spaceAfter=8))
        disclaimer_text = (
            "<b>STATUTORY DISCLAIMER & BOUNDARY DECLARATION:</b><br/>"
            "This document is an AI-generated decision-support dossier produced for investigative lead triage. "
            "It does not establish guilt and does not independently constitute judicial evidence or police dispatch authorization. "
            "Cryptographic hashes provide mathematical proof of record provenance and non-tampering only, and do not establish "
            "substantive admissibility without official certification under Section 63 of Bharatiya Sakshya Adhiniyam (BSA), 2023."
        )
        elements.append(Paragraph(disclaimer_text, disclaimer_style))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
