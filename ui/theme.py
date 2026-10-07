# ============================================================
# DULB ENGINEERING QA POC - THEME STYLING & LIGHT MODE SUPPORT
# ============================================================

import streamlit as st


def apply_theme(theme_choice="☀️ Light Mode"):
    """
    Applies custom CSS rules according to selected theme.
    Ensures crisp, high-contrast engineering aesthetics.
    """
    if theme_choice == "☀️ Light Mode":
        st.markdown(
            """
            <style>
            /* Base Application Styling - Clean Engineering Light Mode */
            .stApp {
                background-color: #f8fafc !important;
                color: #0f172a !important;
            }

            /* Main Content Container */
            .main .block-container {
                padding-top: 2rem;
                padding-bottom: 3rem;
                max-width: 95rem;
            }

            /* Headers */
            h1, h2, h3, h4, h5, h6 {
                color: #0f172a !important;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-weight: 700;
            }

            /* Sidebar Styling */
            section[data-testid="stSidebar"] {
                background-color: #ffffff !important;
                border-right: 1px solid #e2e8f0 !important;
            }
            section[data-testid="stSidebar"] * {
                color: #1e293b !important;
            }

            /* Metrics Cards */
            div[data-testid="stMetric"] {
                background-color: #ffffff !important;
                border: 1px solid #e2e8f0 !important;
                border-radius: 10px !important;
                padding: 12px 18px !important;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
            }
            div[data-testid="stMetricValue"] {
                color: #1e293b !important;
                font-weight: 700 !important;
            }
            div[data-testid="stMetricLabel"] {
                color: #64748b !important;
                font-weight: 600 !important;
            }

            /* Expanders */
            div[data-testid="stExpander"] {
                background-color: #ffffff !important;
                border: 1px solid #e2e8f0 !important;
                border-radius: 8px !important;
                box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
                margin-bottom: 0.75rem;
            }
            div[data-testid="stExpander"] summary {
                color: #0f172a !important;
                font-weight: 600 !important;
            }

            /* Text Areas and Inputs */
            textarea, input[type="text"], input[type="password"] {
                background-color: #ffffff !important;
                color: #0f172a !important;
                border: 1px solid #cbd5e1 !important;
                border-radius: 6px !important;
            }
            textarea:focus, input:focus {
                border-color: #2563eb !important;
                box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2) !important;
            }

            /* Buttons */
            .stButton > button[kind="primary"] {
                background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
                color: #ffffff !important;
                border: none !important;
                border-radius: 8px !important;
                font-weight: 600 !important;
                box-shadow: 0 2px 4px rgba(37, 99, 235, 0.3) !important;
                transition: all 0.2s ease;
            }
            .stButton > button[kind="primary"]:hover {
                background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%) !important;
                box-shadow: 0 4px 8px rgba(37, 99, 235, 0.4) !important;
                transform: translateY(-1px);
            }
            .stButton > button:not([kind="primary"]) {
                background-color: #ffffff !important;
                color: #334155 !important;
                border: 1px solid #cbd5e1 !important;
                border-radius: 8px !important;
            }

            /* DataFrames and Tables */
            div[data-testid="stDataFrame"] {
                border: 1px solid #e2e8f0 !important;
                border-radius: 8px !important;
                background-color: #ffffff !important;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
            }

            /* Tabs */
            div[data-testid="stTabs"] button[role="tab"] {
                color: #64748b !important;
                font-weight: 600 !important;
            }
            div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
                color: #2563eb !important;
                border-bottom: 2px solid #2563eb !important;
            }

            /* Alert / Info / Success Boxes */
            div[data-testid="stAlert"] {
                border-radius: 8px !important;
                border: 1px solid rgba(0, 0, 0, 0.05) !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    elif theme_choice == "🌙 Dark Mode":
        st.markdown(
            """
            <style>
            .stApp {
                background-color: #0b0f19 !important;
                color: #f1f5f9 !important;
            }
            section[data-testid="stSidebar"] {
                background-color: #111827 !important;
                border-right: 1px solid #1f2937 !important;
            }
            div[data-testid="stMetric"] {
                background-color: #111827 !important;
                border: 1px solid #1f2937 !important;
                border-radius: 10px !important;
            }
            div[data-testid="stExpander"] {
                background-color: #111827 !important;
                border: 1px solid #1f2937 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
