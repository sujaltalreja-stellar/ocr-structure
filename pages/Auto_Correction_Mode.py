# ============================================================
# DULB ENGINEERING QA POC - AUTO CORRECTION MODE
# DEDICATED ROUTE: SINGLE-PDF AUTONOMOUS 2D CAD RECTIFICATION
# ============================================================

import os
import sys
import streamlit as st
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(override=True)

# Flush cached submodules so Streamlit hot-reload always uses the latest code from disk
for _mod in list(sys.modules.keys()):
    if _mod.startswith(("core", "ui", "config")):
        del sys.modules[_mod]

from ui import (
    apply_theme,
    render_sidebar,
    render_single_pdf_auto_correction,
)

# ============================================================
# PAGE CONFIGURATION & HEADER
# ============================================================

st.set_page_config(
    page_title="Auto Correction Mode — DULB Engineering",
    page_icon="🛠️",
    layout="wide",
)

# Sidebar configuration & Theme
ai_config = render_sidebar()
selected_provider = ai_config.get("provider", "Mistral AI")
selected_model = ai_config.get("model", "mistral-large-latest")
api_key = ai_config.get("api_key") or os.getenv("MISTRAL_API_KEY")
theme_choice = ai_config.get("theme", "☀️ Light Mode")

apply_theme(theme_choice)

st.title("🛠️ Auto Correction Mode")
st.write(
    """
    **Autonomous 2D CAD & Engineering Drawing Rectification Studio**
    
    Upload a **single consultant-commented engineering drawing PDF**. The system will:
    1. Parse and reconstruct the drawing into editable **AutoCAD DXF** entities via `ezdxf` & `Shapely`.
    2. Implement the required modifications directly in the CAD drawing: updating nominal dimensions, replacing symbols with 2D linework, severing conduits, and moving equipment.
    3. Wipe consultant markup notes, sticky notes, and comment boxes clean from the drawing.
    4. Export an **actual updated drawing file** (clean **Vector PDF** and editable **AutoCAD DXF** in native CAD black font, with optional revision cloud tracking).
    """
)

st.info(
    """
    💡 **Single-Drawing Autonomous Mode**: Upload your drawing with consultant comments. 
    The AI automatically acts as the CAD draftsperson, producing the actual revised CAD and vector PDF drawings ready for construction/resubmission.
    """
)

# Execute Single-PDF Autonomous CAD Correction Workflow
render_single_pdf_auto_correction(
    selected_provider=selected_provider,
    selected_model=selected_model,
    api_key=api_key,
    theme_choice=theme_choice,
)
