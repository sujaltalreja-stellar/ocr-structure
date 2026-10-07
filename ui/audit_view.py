# ============================================================
# DULB ENGINEERING QA POC - AUDIT REPORT UI COMPONENT
# ============================================================

import streamlit as st
import pandas as pd
from core.pdf_report import generate_audit_pdf


def render_audit_report_view(
    audit_data,
    evidence_store=None,
    old_filename="Old_Drawing.pdf",
    new_filename="New_Drawing.pdf",
):
    """
    Renders the formal Engineering Drawing Defect & Quality Audit Report.
    Highlights compliance score, risk level, defect breakdown, CAD punchlist,
    and provides a downloadable publication-grade PDF report with visual evidence.
    """
    st.divider()
    st.subheader("📋 Engineering Drawing Defect & Compliance Audit Report")

    score = audit_data["compliance_score"]
    verdict = audit_data["verdict"]
    verdict_badge = audit_data["verdict_badge"]
    risk = audit_data["risk_level"]
    counts = audit_data["counts"]

    # 1. Executive Audit Summary Banner
    banner_color = "#16a34a" if "PASS" in verdict and "CONDITIONAL" not in verdict else (
        "#ea580c" if "CONDITIONAL" in verdict else "#dc2626"
    )

    st.markdown(
        f"""
        <div style="background-color: {banner_color}; color: #ffffff; padding: 18px 24px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
            <div style="font-size: 14px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; opacity: 0.9;">Official QA Audit Verdict</div>
            <div style="font-size: 26px; font-weight: 800; margin: 4px 0;">{verdict_badge} — {verdict}</div>
            <div style="font-size: 15px; font-weight: 500; opacity: 0.95;">Audit Compliance Score: <strong>{score}%</strong> • Risk Level: <strong>{risk}</strong> • Audited Items: <strong>{counts['total']}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. Key Audit Metric Cards
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "🔴 Critical Defects",
        counts["critical_defects"],
        help="Comments where requested rectification was completely unaddressed or rejected.",
    )
    c2.metric(
        "🟠 Major Deficiencies",
        counts["major_deficiencies"],
        help="Partially completed modifications missing full specs or compliance tags.",
    )
    c3.metric(
        "⚪ Verification Gaps",
        counts["verification_gaps"],
        help="Areas lacking unambiguous evidence; manual engineer check required.",
    )
    c4.metric(
        "🟢 Compliant Items",
        counts["resolved"],
        help="Consultant comments fully verified as resolved.",
    )

    # 3. Defect Findings Table (What is Wrong in Data)
    st.markdown("### 🔍 Drawing Defect Log & Non-Compliances")
    st.caption("Detailed breakdown of what is wrong or missing in the revised engineering drawings.")

    findings = audit_data.get("findings", [])
    if findings:
        findings_df = pd.DataFrame([
            {
                "Severity": f["severity"],
                "Comment ID": f["comment_id"],
                "Page": f["page"],
                "Affected Item": f["affected_item"],
                "What is Wrong (Deficiency)": f["deficiency_summary"],
                "Root Cause": f["root_cause"],
                "Required Action": f["auditor_action"],
            }
            for f in findings
        ])
        st.dataframe(findings_df, use_container_width=True, hide_index=True)
    else:
        st.success("🎉 Zero defects detected! All audited drawing elements comply with consultant directives.")

    # 4. CAD Drafting Correction Punch-List
    st.markdown("### 🛠️ CAD Drafting Team Correction Punch-List")
    st.caption("Action items that draftsmen must execute in AutoCAD before drawing resubmission.")

    punchlist = audit_data.get("punchlist", [])
    if punchlist:
        for idx, item in enumerate(punchlist, 1):
            with st.container():
                st.markdown(
                    f"**{idx}. [{item['priority']}] Page {item['page']} — {item['target']}**"
                )
                st.info(f"👉 **Directive:** {item['action']}")
    else:
        st.write("No punch-list tasks pending.")

    # 5. Drawing Discrepancies
    cad_discrepancies = audit_data.get("cad_discrepancies", [])
    if cad_discrepancies:
        st.markdown("### ⚠️ CAD Geometric Anomaly Warnings")
        for cd in cad_discrepancies:
            st.warning(f"**Page {cd['page']} [{cd['type']}]:** {cd['detail']}")

    # 6. Formal Audit Report Download Options (PDF with Visual Evidence)
    st.markdown("### 📥 Export Official Audit Deliverables")

    # Cache the compiled PDF in session_state so it is generated only once per analysis run
    pdf_cache_key = f"audit_pdf_cache_{audit_data.get('timestamp', 'default')}"
    if pdf_cache_key not in st.session_state or st.session_state[pdf_cache_key] is None:
        with st.spinner("Compiling publication-grade Audit PDF with visual evidence..."):
            st.session_state[pdf_cache_key] = generate_audit_pdf(
                audit_data=audit_data,
                evidence_store=evidence_store or {},
                old_filename=old_filename,
                new_filename=new_filename,
            )

    pdf_bytes = st.session_state[pdf_cache_key]

    st.download_button(
        "📄 Download Official Audit Report (PDF with Visual Evidence & Reason)",
        data=pdf_bytes,
        file_name="DULB_Drawing_Quality_Audit_Report.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )

    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "📑 Download Audit Report Summary (.MD)",
            data=audit_data["report_markdown"].encode("utf-8"),
            file_name="DULB_Drawing_Quality_Audit_Report.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with dl_col2:
        if findings:
            csv_defect_data = pd.DataFrame(findings).to_csv(index=False).encode("utf-8")
        else:
            csv_defect_data = "No defects detected\n".encode("utf-8")

        st.download_button(
            "📊 Download Defect Log (.CSV)",
            data=csv_defect_data,
            file_name="DULB_Drawing_Defect_Log.csv",
            mime="text/csv",
            use_container_width=True,
        )
