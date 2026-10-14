# ============================================================
# DULB ENGINEERING QA POC - SIDEBAR CONFIGURATION UI
# Provider: Sarvam AI (Primary)
# ============================================================

import os
import streamlit as st
from config import SARVAM_API_KEY, SARVAM_MODEL, MISTRAL_API_KEY, MISTRAL_MODEL


def render_sidebar():
    """Renders the workflow mode selector, AI model configuration, and theme toggle in the sidebar."""
    st.sidebar.header("📍 Workflow Mode")
    workflow_mode = st.sidebar.radio(
        "Choose Mode:",
        [
            "🛠️ Auto-Correction Mode (1 PDF)",
            "🔍 Revision QA Audit (2 PDFs)",
        ],
        index=0,
        key="app_workflow_mode",
    )
    st.sidebar.divider()

    st.sidebar.header("🎨 Theme & Appearance")
    theme_choice = st.sidebar.selectbox(
        "Display Theme",
        ["☀️ Light Mode", "🌙 Dark Mode"],
        index=0,
    )

    st.sidebar.divider()
    st.sidebar.header("⚙️ AI Settings")

    providers = ["Sarvam AI", "Mistral AI"]
    selected_provider = st.sidebar.selectbox("AI Provider", providers, index=0)

    selected_model = None
    api_key = None

    if selected_provider == "Sarvam AI":
        key_from_env = SARVAM_API_KEY or os.getenv("SARVAM_API_KEY", "")
        key_from_secrets = ""
        try:
            if hasattr(st, "secrets") and "SARVAM_API_KEY" in st.secrets:
                key_from_secrets = str(st.secrets["SARVAM_API_KEY"]).strip()
        except Exception:
            pass

        auto_key = key_from_env or key_from_secrets
        if auto_key:
            api_key = auto_key
            st.sidebar.success("✅ Sarvam API key loaded from environment")
        else:
            api_key = st.sidebar.text_input(
                "Sarvam API Key",
                type="password",
                placeholder="sk_...",
                help="Enter your Sarvam AI API subscription key",
            )

        selected_model = st.sidebar.selectbox(
            "Sarvam Model",
            [
                "sarvam-105b-conversations",
                "sarvam-105b",
            ],
            index=0,
            help="sarvam-105b-conversations: High-precision engineering instruction following.",
        )

    else:
        # Mistral fallback
        key_from_env = MISTRAL_API_KEY or os.getenv("MISTRAL_API_KEY", "")
        key_from_secrets = ""
        try:
            if hasattr(st, "secrets") and "MISTRAL_API_KEY" in st.secrets:
                key_from_secrets = str(st.secrets["MISTRAL_API_KEY"]).strip()
        except Exception:
            pass

        auto_key = key_from_env or key_from_secrets
        if auto_key:
            api_key = auto_key
            st.sidebar.success("✅ Mistral API key loaded from environment")
        else:
            api_key = st.sidebar.text_input(
                "Mistral API Key",
                type="password",
                placeholder="mstrl_...",
            )

        selected_model = st.sidebar.selectbox(
            "Mistral Model",
            [
                "mistral-small-latest",
                "mistral-medium-latest",
                "ministral-8b-latest",
                "codestral-latest",
            ],
            index=0,
        )

    st.sidebar.divider()
    st.sidebar.subheader("Retrieval Settings")
    top_k = st.sidebar.slider(
        "Relevant chunks per comment",
        min_value=3,
        max_value=15,
        value=8,
        step=1,
    )
    st.sidebar.caption(
        """
        Only the consultant comment, nearby drawing region,
        vector counts, visual similarity, and top relevant
        revised-drawing text blocks are sent to the AI.
        """
    )

    return {
        "workflow_mode": workflow_mode,
        "provider": selected_provider,
        "model": selected_model,
        "api_key": api_key,
        "top_k": top_k,
        "theme": theme_choice,
    }
