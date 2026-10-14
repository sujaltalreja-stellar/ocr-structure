# ============================================================
# DULB ENGINEERING QA POC
# MAIN APPLICATION ENTRY POINT
#
# PURPOSE:
# OLD consultant-commented engineering PDF
#          +
# NEW revised engineering PDF
#          ↓
# Extract actual drawing information
#          ↓
# Detect consultant comments
#          ↓
# Retrieve only relevant evidence
#          ↓
# LLM verifies each comment
#          ↓
# Resolved / Partial / Not Resolved / Cannot Verify
#          ↓
# Engineer evidence + resubmission report
#
# IMPORTANT:
# Full extracted JSON stays local.
# Full JSON is NEVER sent to LLM.
# ============================================================

import os
import sys
import tempfile
import streamlit as st
from dotenv import load_dotenv

# Ensure environment variables are freshly loaded from .env
load_dotenv(override=True)

# Flush cached submodules so Streamlit hot-reload always uses the latest code from disk
for _mod in list(sys.modules.keys()):
    if _mod.startswith(("core", "ui", "config")):
        del sys.modules[_mod]

from config import VALID_STATUSES
from core import (
    extract_pdf,
    get_comments,
    compare_comment_region,
    retrieve_relevant_blocks,
    build_compact_evidence,
    ask_llm,
    generate_audit_report,
)
from ui import (
    apply_theme,
    render_sidebar,
    render_audit_report_view,
    render_extraction_summary,
    render_comments_table,
    render_inspection_tabs,
    render_verification_report,
    render_status_metrics,
    render_drawing_evidence,
    render_resubmission_readiness,
    render_export_section,
    render_single_pdf_auto_correction,
)

# ============================================================
# STREAMLIT CONFIGURATION & HEADER
# ============================================================

st.set_page_config(
    page_title="DULB Engineering QA POC",
    page_icon="📐",
    layout="wide",
)

# ============================================================
# SIDEBAR & THEME
# ============================================================

ai_config = render_sidebar()
selected_provider = ai_config.get("provider", "Sarvam AI")
selected_model = ai_config.get("model", "sarvam-105b-conversations")
api_key = ai_config.get("api_key") or os.getenv("SARVAM_API_KEY")
top_k = ai_config.get("top_k", 8)
theme_choice = ai_config.get("theme", "☀️ Light Mode")

# Apply responsive theme styling
apply_theme(theme_choice)

workflow_mode = ai_config.get("workflow_mode", "🛠️ Auto-Correction Mode (1 PDF)")

if "Auto-Correction" in workflow_mode:
    st.title("🛠️ Auto-Correction Mode")
    st.write(
        """
        **Autonomous Consultant Comment Rectification Engine**
        
        Upload a **single consultant-commented engineering drawing PDF**.
        The AI automatically detects consultant markups, plans the fixes, wipes outdated annotations,
        burns compliant text & linework, draws standard **CAD revision clouds**, and outputs the **updated drawing file with all corrections**!
        """
    )
    render_single_pdf_auto_correction(
        selected_provider=selected_provider,
        selected_model=selected_model,
        api_key=api_key,
        theme_choice=theme_choice,
    )
    st.stop()

# ============================================================
# 2-DRAWING REVISION QA AUDIT WORKFLOW
# ============================================================

st.title("📐 DULB Engineering Drawing QA")

st.write(
    """
    Compare an OLD consultant-commented engineering drawing
    against a NEW revised drawing.

    The system extracts consultant comments, finds relevant
    evidence in the revised drawing, compares the affected
    drawing regions, and determines whether each consultant
    comment was addressed.
    """
)

st.info(
    """
    Full drawing extraction remains local.

    The AI receives only compact evidence relevant to each
    consultant comment — not the complete extracted JSON.
    """
)

# ============================================================
# 1. FILE UPLOAD (2 DRAWINGS)
# ============================================================

st.divider()
st.subheader("1. Upload Drawings")

left_upload, right_upload = st.columns(2)
with left_upload:
    old_file = st.file_uploader(
        "OLD Revision — Consultant Commented Drawing",
        type=["pdf"],
        key="old_pdf",
    )
with right_upload:
    new_file = st.file_uploader(
        "NEW Revision — Revised Drawing",
        type=["pdf"],
        key="new_pdf",
    )

# ============================================================
# ANALYSIS WORKFLOW
# ============================================================

if old_file and new_file:
    if st.button("🚀 Analyze Drawing Revisions", type="primary", use_container_width=True):
        # Save uploaded files to temporary storage
        temp_dir = tempfile.mkdtemp()
        old_path = os.path.join(temp_dir, "old.pdf")
        new_path = os.path.join(temp_dir, "new.pdf")

        old_bytes = old_file.getvalue()
        new_bytes = new_file.getvalue()

        with open(old_path, "wb") as f:
            f.write(old_bytes)
        with open(new_path, "wb") as f:
            f.write(new_bytes)

        # 2. Extract drawing data
        with st.spinner("Extracting drawing text, coordinates, comments and vectors..."):
            old_data = extract_pdf(old_path, old_file.name)
            new_data = extract_pdf(new_path, new_file.name)

        # Render extraction summary
        render_extraction_summary(old_data, new_data)

        # 3. Consultant comments detection
        comments = get_comments(old_data)
        comments_df = render_comments_table(comments)

        # 3D Model & Debug tabs (3D Visualizer, Text, Comments, Vectors)
        render_inspection_tabs(
            old_data=old_data,
            new_data=new_data,
            comments_df=comments_df,
            old_path=old_path,
            new_path=new_path,
            comments=comments,
            theme_mode="light" if "Light" in theme_choice else "dark",
        )

        # Verify AI model availability
        if not selected_model:
            st.error("No AI model is currently available.")
            st.stop()

        # 4. AI Comment Verification loop
        st.divider()
        st.subheader("4. AI Comment Verification")
        st.caption(
            """
            Each consultant comment is processed independently.
            Only compact relevant evidence is sent to the model.
            """
        )

        results = []
        evidence_store = {}
        progress_bar = st.progress(0)
        progress_text = st.empty()

        for index, comment in enumerate(comments):
            progress_text.write(
                f"Analyzing {comment['id']} — {index + 1}/{len(comments)}"
            )

            # Local region visual & vector comparison
            comparison = compare_comment_region(old_path, new_path, comment)

            if "error" in comparison:
                analysis = {
                    "required_rectification": "",
                    "comment_category": "",
                    "affected_item": "",
                    "detected_change": "",
                    "status": "Cannot Verify",
                    "confidence": 0.0,
                    "reason": comparison["error"],
                    "engineer_review_required": True,
                }
                retrieval = []
                compact_evidence = {}
            else:
                # Retrieve relevant text blocks from revised drawing
                retrieval = retrieve_relevant_blocks(
                    new_data,
                    comment["comment"],
                    top_k=top_k,
                )

                # Build compact evidence payload
                compact_evidence = build_compact_evidence(
                    comment,
                    comparison,
                    retrieval,
                )

                # Query AI model
                try:
                    analysis = ask_llm(
                        model=selected_model,
                        evidence=compact_evidence,
                        provider=selected_provider,
                        api_key=api_key,
                    )
                except Exception as error:
                    analysis = {
                        "required_rectification": "",
                        "comment_category": "",
                        "affected_item": "",
                        "detected_change": "",
                        "status": "Cannot Verify",
                        "confidence": 0.0,
                        "reason": f"AI error: {error}",
                        "engineer_review_required": True,
                    }

            # Validate AI status response
            status = analysis.get("status", "Cannot Verify")
            if status not in VALID_STATUSES:
                status = "Cannot Verify"

            # Record result
            result = {
                "Comment ID": comment["id"],
                "Page": comment["page"],
                "Source": comment["source"],
                "Consultant Comment": comment["comment"],
                "Required Rectification": analysis.get("required_rectification", ""),
                "Category": analysis.get("comment_category", ""),
                "Affected Item": analysis.get("affected_item", ""),
                "Detected Change": analysis.get("detected_change", ""),
                "Status": status,
                "Confidence": analysis.get("confidence", 0.0),
                "Reason": analysis.get("reason", ""),
                "Engineer Review": analysis.get("engineer_review_required", True),
            }
            results.append(result)

            evidence_store[comment["id"]] = {
                "comment": comment,
                "comparison": comparison,
                "retrieval": retrieval,
                "compact_evidence": compact_evidence,
            }

            progress_bar.progress((index + 1) / len(comments))

        progress_text.empty()

        # 5. Verification report table
        report_df = render_verification_report(results)

        # Status metrics cards
        render_status_metrics(results)

        # 6. Formal Drawing Defect & Compliance Audit Report
        audit_data = generate_audit_report(
            results=results,
            evidence_store=evidence_store,
            old_data=old_data,
            new_data=new_data,
            old_filename=old_file.name,
            new_filename=new_file.name,
        )
        render_audit_report_view(
            audit_data=audit_data,
            evidence_store=evidence_store,
            old_filename=old_file.name,
            new_filename=new_file.name,
        )

        # 7. Detailed drawing evidence cards
        render_drawing_evidence(results, evidence_store)

        # 8. Resubmission readiness verdict
        render_resubmission_readiness(results)

        # 9. Export and download options
        render_export_section(
            results=results,
            evidence_store=evidence_store,
            old_file=old_file,
            new_file=new_file,
            old_bytes=old_bytes,
            new_bytes=new_bytes,
            old_data=old_data,
            new_data=new_data,
            comments=comments,
            report_df=report_df,
        )

# ============================================================
# FOOTER
# ============================================================

st.divider()
st.caption(
    """
    Current POC scope:
    PDF-based consultant comment extraction and old-vs-new
    drawing verification.

    Production DWG/DXF correction should use a CAD-native
    parser/editor. The LLM should generate structured correction
    instructions; a CAD engine should execute those changes.
    """
)