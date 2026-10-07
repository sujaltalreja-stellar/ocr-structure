# ============================================================
# DULB ENGINEERING QA POC - AI CLIENT (SARVAM AI & OLLAMA)
# ============================================================

import os
import json
from config import SARVAM_AVAILABLE, OLLAMA_AVAILABLE
from core.retrieval import clean_json_response

if SARVAM_AVAILABLE:
    try:
        from sarvamai import SarvamAI
    except Exception:
        SarvamAI = None
else:
    SarvamAI = None

if OLLAMA_AVAILABLE:
    try:
        import ollama
    except Exception:
        ollama = None
else:
    ollama = None


def get_ollama_models():
    """Returns a list of locally installed model names from Ollama."""
    if not OLLAMA_AVAILABLE or ollama is None:
        return []
    try:
        response = ollama.list()
        models = getattr(response, "models", None)
        if models is None and isinstance(response, dict):
            models = response.get("models", [])
        names = []
        for item in models or []:
            name = getattr(item, "model", None)
            if name is None and isinstance(item, dict):
                name = item.get("model") or item.get("name")
            if name:
                names.append(name)
        return names
    except Exception:
        return []


def ask_llm(model=None, evidence=None, provider="Sarvam AI", api_key=None):
    """
    Submits compact evidence to Sarvam AI or local Ollama model
    and parses structured verification decision.
    """
    if not provider or provider not in ["Sarvam AI", "Ollama"]:
        provider = "Sarvam AI"
    if not model or "mistral" in str(model).lower():
        model = "sarvam-105b-conversations"

    evidence_json = json.dumps(evidence or {}, ensure_ascii=False)

    prompt = f"""

You are an engineering drawing QA assistant.

You are checking ONE consultant comment from an OLD engineering
drawing against a NEW revised engineering drawing.

The objective is to determine whether the consultant's requested
rectification was actually completed.

IMPORTANT RULES:

1. Use ONLY the evidence supplied below.

2. Do not assume that a drawing change means the consultant
   comment was resolved.

3. Same-region evidence represents approximately the same
   physical region in OLD and NEW drawings.

4. Relevant-new-revision evidence may come from another area
   such as:
   - schedule
   - calculation table
   - legend
   - general note
   - typical detail
   - equipment tag
   - door configuration
   - drawing annotation

5. If the evidence is insufficient, ambiguous, or requires
   engineering judgment not present in the evidence, return
   "Cannot Verify".

6. Do NOT invent:
   - dimensions
   - equipment
   - standards
   - calculations
   - geometry
   - compliance requirements

7. A visual difference alone is NOT proof of resolution.

8. Final approval always belongs to the engineer.

EVIDENCE:

{evidence_json}


Return ONLY valid JSON (no markdown formatting, no commentary):

{{
    "required_rectification": "",
    "comment_category": "",
    "affected_item": "",
    "detected_change": "",
    "status": "Resolved | Partially Resolved | Not Resolved | Cannot Verify",
    "confidence": 0.0,
    "reason": "",
    "engineer_review_required": true
}}

"""

    # ========================================================
    # SARVAM AI
    # ========================================================
    if provider == "Sarvam AI":
        if not api_key:
            api_key = os.getenv("SARVAM_API_KEY")
        if not api_key:
            try:
                import streamlit as st
                if hasattr(st, "secrets") and "SARVAM_API_KEY" in st.secrets:
                    api_key = str(st.secrets["SARVAM_API_KEY"]).strip()
            except Exception:
                pass

        if not api_key:
            raise ValueError("SARVAM_API_KEY is not configured. Please supply it in the sidebar or Streamlit Secrets.")

        # Attempt 1: Official sarvamai SDK if available
        if SARVAM_AVAILABLE and SarvamAI is not None:
            try:
                client = SarvamAI(api_subscription_key=api_key)
                response = client.chat.completions(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                )
                content = response.choices[0].message.content
                return clean_json_response(content)
            except Exception as sdk_err:
                pass  # Fall through to REST API

        # Attempt 2: Direct REST API fallback via requests
        import requests
        url = "https://api.sarvam.ai/v1/chat/completions"
        headers = {
            "api-subscription-key": api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        if res.status_code != 200:
            raise RuntimeError(f"Sarvam AI API error ({res.status_code}): {res.text}")
        data = res.json()
        content = data["choices"][0]["message"]["content"]
        return clean_json_response(content)

    # ========================================================
    # OLLAMA
    # ========================================================
    if provider == "Ollama":
        if not OLLAMA_AVAILABLE or ollama is None:
            raise ValueError("Ollama package is unavailable.")

        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": 0},
        )
        content = response["message"]["content"]
        return clean_json_response(content)

    raise ValueError(f"Unsupported AI provider: {provider}")
