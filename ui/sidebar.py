# ============================================================
# DULB ENGINEERING QA POC - SIDEBAR CONFIGURATION UI
# ============================================================

import os
import streamlit as st
from config import SARVAM_AVAILABLE, OLLAMA_AVAILABLE
from core.ai_client import get_ollama_models


def render_sidebar():
    """Renders the AI model configuration, retrieval settings, and theme toggle in the sidebar."""
    st.sidebar.header("🎨 Theme & Appearance")
    theme_choice = st.sidebar.selectbox(
        "Display Theme",
        ["☀️ Light Mode", "🌙 Dark Mode"],
        index=0,
    )

    st.sidebar.divider()
    st.sidebar.header("⚙️ AI Settings")

    providers = []
    if SARVAM_AVAILABLE:
        providers.append("Sarvam AI")
    if OLLAMA_AVAILABLE:
        providers.append("Ollama")
    if not providers:
        providers = ["Sarvam AI", "Ollama"]

    selected_provider = st.sidebar.selectbox("AI Provider", providers, index=0)
    selected_model = None
    api_key = None

    if selected_provider == "Sarvam AI":
        sarvam_api_key = os.getenv("SARVAM_API_KEY", "")
        key_source = ".env / environment"
        if not sarvam_api_key and hasattr(st, "secrets") and "SARVAM_API_KEY" in st.secrets:
            sarvam_api_key = str(st.secrets["SARVAM_API_KEY"]).strip()
            key_source = "Streamlit Cloud secrets"

        if not sarvam_api_key:
            api_key = st.sidebar.text_input("Sarvam API Key", type="password")
        else:
            api_key = sarvam_api_key
            st.sidebar.success(f"Sarvam API key loaded from {key_source}")

        selected_model = st.sidebar.selectbox(
            "Sarvam Model",
            [
                "sarvam-105b-conversations",
                "sarvam-2b",
            ],
            index=0,
        )

    elif selected_provider == "Ollama":
        ollama_models = get_ollama_models()
        if ollama_models:
            selected_model = st.sidebar.selectbox("Ollama Model", ollama_models)
        else:
            st.sidebar.warning("No Ollama model detected.")

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
        The complete extracted drawing JSON is never sent to AI.
        Only the consultant comment, nearby old/new region,
        vector counts, visual similarity and top relevant
        revised-drawing text blocks are sent.
        """
    )

    return {
        "provider": selected_provider,
        "model": selected_model,
        "api_key": api_key,
        "top_k": top_k,
        "theme": theme_choice,
    }
