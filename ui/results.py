# ============================================================
# DULB ENGINEERING QA POC - VERIFICATION RESULTS & EXPORT UI
# ============================================================

import json
import streamlit as st
import pandas as pd
import numpy as np
from core.utils import file_hash


def render_verification_report(results):
    """Renders the main verification report table and returns the DataFrame."""
    st.divider()
    st.subheader("5. Consultant Comment Verification Report")
    report_df = pd.DataFrame(results)
    st.dataframe(report_df, use_container_width=True, hide_index=True)
    return report_df


def render_status_metrics(results):
    """Renders status breakdown KPI metric cards."""
    resolved = sum(r["Status"] == "Resolved" for r in results)
    partial = sum(r["Status"] == "Partially Resolved" for r in results)
    unresolved = sum(r["Status"] == "Not Resolved" for r in results)
    cannot_verify = sum(r["Status"] == "Cannot Verify" for r in results)

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("✅ Resolved", resolved)
    metric2.metric("🟠 Partial", partial)
    metric3.metric("❌ Not Resolved", unresolved)
    metric4.metric("⚪ Cannot Verify", cannot_verify)


def _is_valid_image(img):
    """Verifies that an image is a non-empty NumPy array with valid dimensions."""
    if img is None:
        return False
    if not isinstance(img, np.ndarray):
        return False
    if img.size == 0 or img.ndim < 2:
        return False
    if img.shape[0] <= 0 or img.shape[1] <= 0:
        return False
    return True


def render_drawing_evidence(results, evidence_store):
    """Renders detailed visual and textual evidence cards for each analyzed comment."""
    st.divider()
    st.subheader("6. Drawing Evidence")

    for result in results:
        comment_id = result["Comment ID"]
        evidence = evidence_store[comment_id]
        comparison = evidence["comparison"]

        title = f"{comment_id} — {result['Status']} — {result['Consultant Comment'][:100]}"
        with st.expander(title):
            st.markdown("### Consultant Comment")
            st.write(result["Consultant Comment"])
            st.caption(f"Detected from: {result['Source']}")

            st.markdown("### AI Interpretation")
            st.write("**Required Rectification:**", result["Required Rectification"])
            st.write("**Category:**", result["Category"])
            st.write("**Affected Item:**", result["Affected Item"])
            st.write("**Detected Change:**", result["Detected Change"])
            st.write("**Status:**", result["Status"])
            st.write("**Confidence:**", result["Confidence"])
            st.write("**Reason:**", result["Reason"])

            # Visual Comparison Images
            if comparison and "error" not in comparison:
                old_col, new_col, diff_col = st.columns(3)
                with old_col:
                    st.markdown("#### OLD Revision")
                    old_img = comparison.get("old_image")
                    if _is_valid_image(old_img):
                        st.image(old_img, use_container_width=True)
                    else:
                        st.caption("Region image unavailable.")
                with new_col:
                    st.markdown("#### NEW Revision")
                    new_img = comparison.get("new_image")
                    if _is_valid_image(new_img):
                        st.image(new_img, use_container_width=True)
                    else:
                        st.caption("Region image unavailable.")
                with diff_col:
                    st.markdown("#### Detected Difference")
                    diff_img = comparison.get("difference_image")
                    if _is_valid_image(diff_img):
                        st.image(diff_img, use_container_width=True)
                    else:
                        st.caption("No visual difference detected.")

                # Local Text
                local_left, local_right = st.columns(2)
                with local_left:
                    st.text_area(
                        "Old local region text",
                        comparison.get("old_text", ""),
                        height=180,
                        key=f"old_region_{comment_id}",
                    )
                with local_right:
                    st.text_area(
                        "New local region text",
                        comparison.get("new_text", ""),
                        height=180,
                        key=f"new_region_{comment_id}",
                    )

                # Local Metrics
                em1, em2, em3 = st.columns(3)
                sim = comparison.get("visual_similarity")
                em1.metric(
                    "Visual Similarity",
                    round(sim, 4) if sim is not None else "N/A",
                )
                em2.metric("Old Vector Count", comparison.get("old_vectors", 0))
                em3.metric("New Vector Count", comparison.get("new_vectors", 0))

            # Retrieved Evidence in New Drawing
            st.markdown("### Relevant Evidence Found in NEW Drawing")
            retrieval = evidence["retrieval"]
            if retrieval:
                retrieval_df = pd.DataFrame([
                    {
                        "Page": item["page"],
                        "Relevance": item["score"],
                        "Text": item["text"],
                        "BBox": str(item["bbox"]),
                    }
                    for item in retrieval
                ])
                st.dataframe(retrieval_df, use_container_width=True, hide_index=True)
            else:
                st.info("No additional relevant text blocks found.")

            # Compact Payload Inspection
            with st.expander("🧠 Show compact data sent to LLM"):
                st.json(evidence["compact_evidence"], expanded=False)


def render_resubmission_readiness(results):
    """Renders resubmission readiness verdict and blocking comments list."""
    st.divider()
    st.subheader("7. Resubmission Readiness")

    blocking = [
        r for r in results
        if r["Status"] in ["Partially Resolved", "Not Resolved", "Cannot Verify"]
    ]

    if results and len(blocking) == 0:
        st.success(
            """
            All detected consultant comments appear resolved.
            The drawing may proceed to final engineering review.
            Final approval remains with the responsible engineer.
            """
        )
    else:
        st.warning(
            f"""
            {len(blocking)} consultant comment(s) still require
            rectification or engineer verification.
            Drawing should not be treated as ready for
            resubmission solely from this automated check.
            """
        )

    if blocking:
        blocking_df = pd.DataFrame([
            {
                "Comment ID": item["Comment ID"],
                "Status": item["Status"],
                "Comment": item["Consultant Comment"],
                "Reason": item["Reason"],
            }
            for item in blocking
        ])
        st.dataframe(blocking_df, use_container_width=True, hide_index=True)


def render_export_section(
    results,
    evidence_store,
    old_file,
    new_file,
    old_bytes,
    new_bytes,
    old_data,
    new_data,
    comments,
    report_df,
):
    """Renders download buttons for CSV, compact verification JSON, and full raw extraction."""
    st.divider()
    st.subheader("8. Export Results")

    # CSV Download
    csv_data = report_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download Verification Report CSV",
        data=csv_data,
        file_name="DULB_comment_verification.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # Compact JSON Export
    resolved = sum(r["Status"] == "Resolved" for r in results)
    partial = sum(r["Status"] == "Partially Resolved" for r in results)
    unresolved = sum(r["Status"] == "Not Resolved" for r in results)
    cannot_verify = sum(r["Status"] == "Cannot Verify" for r in results)

    compact_export = {
        "project": "DULB Engineering QA",
        "old_file": old_file.name,
        "new_file": new_file.name,
        "old_file_hash": file_hash(old_bytes),
        "new_file_hash": file_hash(new_bytes),
        "comments_detected": len(comments),
        "summary": {
            "resolved": resolved,
            "partially_resolved": partial,
            "not_resolved": unresolved,
            "cannot_verify": cannot_verify,
        },
        "results": results,
        "llm_evidence": {
            cid: evidence_store[cid]["compact_evidence"]
            for cid in evidence_store
        },
    }

    compact_json = json.dumps(compact_export, indent=2, ensure_ascii=False)
    st.download_button(
        "📥 Download Compact Verification JSON",
        data=compact_json,
        file_name="DULB_compact_verification.json",
        mime="application/json",
        use_container_width=True,
    )

    # Full Raw Extraction Download
    with st.expander("⚠️ Full Raw Extraction JSON"):
        st.warning(
            """
            These files can be very large.
            They are provided for engineering/debugging only.
            They are NOT sent to the LLM.
            """
        )
        raw_left, raw_right = st.columns(2)
        with raw_left:
            old_raw_json = json.dumps(old_data, ensure_ascii=False)
            st.download_button(
                "Download OLD Full Extraction",
                data=old_raw_json,
                file_name="old_drawing_extracted.json",
                mime="application/json",
                use_container_width=True,
            )
        with raw_right:
            new_raw_json = json.dumps(new_data, ensure_ascii=False)
            st.download_button(
                "Download NEW Full Extraction",
                data=new_raw_json,
                file_name="new_drawing_extracted.json",
                mime="application/json",
                use_container_width=True,
            )
