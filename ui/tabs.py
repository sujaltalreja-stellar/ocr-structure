# ============================================================
# DULB ENGINEERING QA POC - EXTRACTION SUMMARY & DEBUG TABS UI
# ============================================================

import streamlit as st
import pandas as pd
from core.cad_3d import extract_3d_cad_model, extract_3d_diff_model
from ui.viewer_3d import render_3d_cad_viewer


def render_extraction_summary(old_data, new_data):
    """Renders the extraction comparison summary table."""
    st.divider()
    st.subheader("2. Extraction Summary")

    summary_data = [
        {
            "Drawing": "Old Revision",
            "Pages": old_data["page_count"],
            "Text Characters": sum(
                len(page["text"]["plain_text"]) for page in old_data["pages"]
            ),
            "Text Blocks": sum(
                len(page["text"]["blocks"]) for page in old_data["pages"]
            ),
            "Annotations": sum(
                len(page["annotations"]) for page in old_data["pages"]
            ),
            "Vectors": sum(
                len(page["vectors"]) for page in old_data["pages"]
            ),
        },
        {
            "Drawing": "New Revision",
            "Pages": new_data["page_count"],
            "Text Characters": sum(
                len(page["text"]["plain_text"]) for page in new_data["pages"]
            ),
            "Text Blocks": sum(
                len(page["text"]["blocks"]) for page in new_data["pages"]
            ),
            "Annotations": sum(
                len(page["annotations"]) for page in new_data["pages"]
            ),
            "Vectors": sum(
                len(page["vectors"]) for page in new_data["pages"]
            ),
        },
    ]

    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)


def render_comments_table(comments):
    """Renders the detected consultant comments table and returns the DataFrame."""
    st.divider()
    st.subheader("3. Consultant Comments")

    if not comments:
        st.error(
            """
            No consultant comments were detected from either:

            • native PDF annotations
            • consultant-like native PDF text

            This drawing may require OCR / vision-based
            markup detection.
            """
        )
        st.stop()

    comments_df = pd.DataFrame([
        {
            "ID": comment["id"],
            "Page": comment["page"],
            "Source": comment["source"],
            "Consultant Comment": comment["comment"],
            "BBox": str(comment.get("bbox")),
        }
        for comment in comments
    ])

    st.dataframe(comments_df, use_container_width=True, hide_index=True)
    st.success(f"{len(comments)} consultant comment candidate(s) detected.")
    return comments_df


def render_inspection_tabs(
    old_data,
    new_data,
    comments_df,
    old_path=None,
    new_path=None,
    comments=None,
    theme_mode="light",
):
    """Renders the debug inspection tabs for text, comments, CAD vectors, and 3D visualizer."""
    with st.expander("🔍 Inspect Extracted Drawing Data & 3D Model", expanded=True):
        tabs = st.tabs([
            "🏗️ 3D AutoCAD Visualizer",
            "Text",
            "Comments",
            "Vectors",
        ])

        cad_3d_tab, text_tab, comment_tab, vector_tab = tabs

        # 3D AutoCAD Tab
        with cad_3d_tab:
            st.markdown("### 🏗️ Interactive 3D AutoCAD BIM Model")
            st.caption(
                "Converts 2D AutoCAD PDF linework and walls into an interactive 3D spatial model "
                "with extruded architectural walls, elevated MEP conduits, and 3D consultant comment pins."
            )

            col1, col2 = st.columns([1, 1])
            with col1:
                revision_choice = st.selectbox(
                    "3D Model View",
                    [
                        "✨ NEW Revision 3D Model",
                        "📜 OLD Revision 3D Model",
                        "🔀 3D Revision Diff Overlay (Red/Green Changes)",
                    ],
                    key="3d_revision_choice",
                )
            with col2:
                max_pages = max(old_data["page_count"], new_data["page_count"])
                selected_cad_page = st.selectbox(
                    "Drawing Sheet / Page",
                    list(range(1, max_pages + 1)),
                    key="3d_cad_page",
                )

            with st.spinner("Generating 3D spatial BIM geometry from AutoCAD linework..."):
                if "Diff" in revision_choice and old_path and new_path:
                    cad_model = extract_3d_diff_model(
                        old_pdf_path=old_path,
                        new_pdf_path=new_path,
                        page_num=selected_cad_page,
                        comments=comments,
                    )
                else:
                    active_pdf = new_path if "NEW" in revision_choice else old_path
                    cad_model = extract_3d_cad_model(
                        active_pdf,
                        page_num=selected_cad_page,
                        comments=comments,
                    )

            if cad_model:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🧱 Extruded Walls", len(cad_model.get("walls", [])))
                m2.metric("🏛️ Columns", len(cad_model.get("columns", [])))
                m3.metric("⚡ MEP Conduits", len(cad_model.get("conduits", [])))
                m4.metric("📍 3D Comment Pins", len(cad_model.get("pins", [])))

                render_3d_cad_viewer(
                    cad_model=cad_model,
                    theme_mode=theme_mode,
                    height=680,
                )
            else:
                st.warning("Could not extract 3D CAD vectors from this page.")

        # Text Tab
        with text_tab:
            max_pages = max(old_data["page_count"], new_data["page_count"])
            selected_page = st.selectbox(
                "Page",
                list(range(1, max_pages + 1)),
                key="inspect_page",
            )

            old_page_data = next(
                (p for p in old_data["pages"] if p["page"] == selected_page),
                None,
            )
            new_page_data = next(
                (p for p in new_data["pages"] if p["page"] == selected_page),
                None,
            )

            text_left, text_right = st.columns(2)
            with text_left:
                st.markdown("#### Old Revision")
                old_text = old_page_data["text"]["plain_text"] if old_page_data else ""
                st.text_area(
                    "Old extracted text",
                    old_text,
                    height=350,
                    key="old_extracted_text",
                )

            with text_right:
                st.markdown("#### New Revision")
                new_text = new_page_data["text"]["plain_text"] if new_page_data else ""
                st.text_area(
                    "New extracted text",
                    new_text,
                    height=350,
                    key="new_extracted_text",
                )

        # Comment Tab
        with comment_tab:
            st.dataframe(comments_df, use_container_width=True, hide_index=True)

        # Vector Tab
        with vector_tab:
            vector_summary = []
            max_pages = max(old_data["page_count"], new_data["page_count"])
            for page_number in range(1, max_pages + 1):
                old_page = next(
                    (p for p in old_data["pages"] if p["page"] == page_number),
                    None,
                )
                new_page = next(
                    (p for p in new_data["pages"] if p["page"] == page_number),
                    None,
                )
                old_count = len(old_page["vectors"]) if old_page else 0
                new_count = len(new_page["vectors"]) if new_page else 0
                vector_summary.append({
                    "Page": page_number,
                    "Old Vectors": old_count,
                    "New Vectors": new_count,
                    "Difference": new_count - old_count,
                })
            st.dataframe(
                pd.DataFrame(vector_summary),
                use_container_width=True,
                hide_index=True,
            )
