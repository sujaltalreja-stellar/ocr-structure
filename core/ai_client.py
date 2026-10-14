# ============================================================
# DULB ENGINEERING QA POC - AI CLIENT (SARVAM AI PRIMARY)
# ============================================================
# Primary Provider: Sarvam AI REST API (sarvam-105b-conversations)
# Secondary Provider: Mistral AI REST API (mistral-small-latest)
# ============================================================

import os
import json
import time
import requests
from typing import Optional, Dict, Any

from config import (
    SARVAM_API_KEY,
    SARVAM_MODEL,
    SARVAM_BASE_URL,
    MISTRAL_API_KEY,
    MISTRAL_MODEL,
    MISTRAL_BASE_URL,
)
from core.retrieval import clean_json_response


# ─────────────────────────────────────────────────────────────
# SARVAM AI REST CALL (PRIMARY)
# ─────────────────────────────────────────────────────────────

def _call_sarvam(
    prompt: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.05,
    timeout: int = 60,
    max_retries: int = 3,
) -> str:
    """
    Calls Sarvam AI /v1/chat/completions endpoint using api-subscription-key.
    Returns the assistant content string.
    """
    key = api_key or SARVAM_API_KEY or os.getenv("SARVAM_API_KEY", "")
    if not key:
        raise ValueError(
            "SARVAM_API_KEY is not configured. "
            "Please configure it in .env, sidebar, or Streamlit Secrets."
        )

    m = model or SARVAM_MODEL or "sarvam-105b-conversations"
    url = f"{SARVAM_BASE_URL}/chat/completions"
    headers = {
        "api-subscription-key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "model": m,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert engineering CAD drawing rectification AI. "
                    "You strictly analyze engineering drawings, consultant markups, "
                    "dimensions, vectors, symbols, and geometry. "
                    "You ALWAYS respond with valid JSON only — no markdown fences, "
                    "no prose, no explanation. Just the raw JSON object."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }

    last_err = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 429:
                wait = 5 * (2 ** attempt)
                last_err = f"429 Rate limited — retrying in {wait}s"
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Sarvam AI API error ({resp.status_code}): {resp.text[:400]}"
                )
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content or not content.strip():
                raise RuntimeError("Sarvam AI returned an empty response.")
            return content
        except requests.Timeout:
            last_err = f"Sarvam AI timed out (attempt {attempt+1}/{max_retries})"
            time.sleep(3)
            continue
        except Exception as e:
            if "Sarvam AI API error" in str(e):
                raise
            last_err = str(e)
            time.sleep(2)

    raise RuntimeError(f"Sarvam AI call failed after {max_retries} attempts: {last_err}")


# ─────────────────────────────────────────────────────────────
# MISTRAL AI REST CALL (SECONDARY / FALLBACK)
# ─────────────────────────────────────────────────────────────

def _call_mistral_raw(
    prompt: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.05,
    timeout: int = 90,
    max_retries: int = 3,
) -> str:
    key = api_key or MISTRAL_API_KEY or os.getenv("MISTRAL_API_KEY", "")
    if not key:
        raise ValueError("MISTRAL_API_KEY is not configured.")

    m = model or MISTRAL_MODEL
    url = f"{MISTRAL_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "model": m,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert engineering drawing rectification assistant. "
                    "You ALWAYS respond with valid JSON only — no markdown fences, "
                    "no prose, no code blocks. Just the raw JSON object."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }

    last_err = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 429:
                wait = 10 * (2 ** attempt)
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                raise RuntimeError(f"Mistral API error ({resp.status_code}): {resp.text[:400]}")
            content = resp.json()["choices"][0]["message"]["content"]
            if not content or not content.strip():
                raise RuntimeError("Mistral returned an empty response.")
            return content
        except requests.Timeout:
            last_err = f"Timed out (attempt {attempt+1}/{max_retries})"
            time.sleep(3)
            continue

    raise RuntimeError(f"Mistral API failed: {last_err}")


# ─────────────────────────────────────────────────────────────
# UNIFIED CALL LLM (Sarvam default)
# ─────────────────────────────────────────────────────────────

def call_llm(
    prompt: str,
    provider: Optional[str] = "Sarvam AI",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.05,
) -> str:
    """
    Unified LLM caller. Defaults to Sarvam AI.
    Falls back to Mistral if requested or if Sarvam is unavailable.
    """
    p = (provider or "Sarvam AI").strip()
    if "Mistral" in p:
        return _call_mistral_raw(prompt, api_key=api_key, model=model, temperature=temperature)

    # Otherwise default to Sarvam AI
    return _call_sarvam(prompt, api_key=api_key, model=model, temperature=temperature)


# Backward compatibility alias
def _call_mistral(
    prompt: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.05,
    timeout: int = 60,
    max_retries: int = 3,
) -> str:
    """
    Backwards compatibility router:
    If SARVAM_API_KEY is configured (or user provided it), route to Sarvam AI.
    Otherwise, fall back to Mistral.
    """
    sarvam_key = os.getenv("SARVAM_API_KEY", "") or SARVAM_API_KEY
    if sarvam_key:
        return _call_sarvam(
            prompt,
            api_key=sarvam_key,
            model=model if (model and "sarvam" in model.lower()) else SARVAM_MODEL,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
        )
    return _call_mistral_raw(
        prompt,
        api_key=api_key,
        model=model,
        temperature=temperature,
        timeout=timeout,
        max_retries=max_retries,
    )


# ─────────────────────────────────────────────────────────────
# PUBLIC QA VERIFICATION CALL (Audit Flow)
# ─────────────────────────────────────────────────────────────

def ask_llm(
    model: Optional[str] = None,
    evidence: Optional[Dict[str, Any]] = None,
    provider: str = "Sarvam AI",
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Submits compact evidence to Sarvam AI (or specified provider)
    and returns a structured verification decision.
    """
    evidence_json = json.dumps(evidence or {}, ensure_ascii=False)

    prompt = f"""
You are an engineering drawing QA assistant.

You are checking ONE consultant comment from an OLD engineering
drawing against a NEW revised engineering drawing.

The objective is to determine whether the consultant's requested
rectification was actually completed.

IMPORTANT RULES:
1. Use ONLY the evidence supplied below.
2. Do not assume that a drawing change means the consultant comment was resolved.
3. Same-region evidence represents approximately the same physical region in OLD and NEW drawings.
4. Relevant-new-revision evidence may come from another area such as:
   - schedule / calculation table / legend / general note
   - typical detail / equipment tag / door configuration / drawing annotation
5. If the evidence is insufficient, ambiguous, or requires engineering judgment
   not present in the evidence, return "Cannot Verify".
6. Do NOT invent dimensions, equipment, standards, calculations, geometry,
   or compliance requirements.
7. A visual difference alone is NOT proof of resolution.
8. Final approval always belongs to the engineer.

EVIDENCE:
{evidence_json}

Return ONLY valid JSON (no markdown, no commentary):
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
    raw = call_llm(prompt, provider=provider, api_key=api_key, model=model)
    return clean_json_response(raw)


def get_ollama_models():
    return []
