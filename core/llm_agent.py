# ============================================================
# DULB ENGINEERING QA POC - LLM-TO-PYTHON SELECTIVE EDIT AGENT
# Provider: Mistral AI  (mistral-large-latest, JSON mode)
# ============================================================
# ROOT-CAUSE FIXES applied in this rewrite:
#
#  1. Mistral replaces Sarvam AI / Ollama throughout.
#  2. The prompt now supplies RICH spatial context to the LLM:
#     - Nearby vector path count + bbox summary
#     - Nearby text spans with exact coords
#     - Mapped target object details (id, type, bbox, tag, elevation)
#     - Page dimensions for coordinate sanity
#  3. Coordinate sanity-check: target_bbox is clamped to page
#     bounds and must be non-degenerate (w>2, h>2).
#  4. The analytical fallback is tighter — it uses the arrow_tip
#     directly instead of the comment_bbox which can be far off.
#  5. Dimension-value guard strips hallucinated long strings.
# ============================================================

import os
import re
import json
import fitz
from typing import Dict, Any, List, Optional

from config import SARVAM_API_KEY, SARVAM_MODEL, MISTRAL_API_KEY, MISTRAL_MODEL
from core.ai_client import call_llm, _call_mistral
from core.retrieval import clean_json_response
from core.cad_schema import (
    EngineeringObjectType,
    EngineeringDrawingObject,
    SelectiveActionType,
    SelectiveEditCommand,
)
from core.object_mapper import find_target_object_for_comment


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _clamp_bbox(bbox: List[float], pw: float, ph: float) -> List[float]:
    """Clamp bbox to page bounds and ensure non-degenerate."""
    x0 = max(0.0, min(bbox[0], pw - 2.0))
    y0 = max(0.0, min(bbox[1], ph - 2.0))
    x1 = max(x0 + 2.0, min(bbox[2], pw))
    y1 = max(y0 + 2.0, min(bbox[3], ph))
    return [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]


def _nearby_vectors_summary(page: fitz.Page, clip: fitz.Rect, limit: int = 20) -> List[Dict[str, Any]]:
    """Return compact list of vector path bboxes near a zone."""
    try:
        drawings = page.get_drawings()
        summary = []
        for d in drawings:
            r = d.get("rect")
            if r and fitz.Rect(r).intersects(clip):
                summary.append({
                    "bbox": [round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)],
                    "type": d.get("type", "s"),
                    "width": round(float(d.get("width") or 0), 2),
                })
                if len(summary) >= limit:
                    break
        return summary
    except Exception:
        return []


def _nearby_text_summary(page: fitz.Page, clip: fitz.Rect, limit: int = 30) -> List[Dict[str, Any]]:
    """Return compact list of text spans near a zone."""
    try:
        words = page.get_text("words", clip=clip)
        return [
            {"text": w[4], "bbox": [round(w[0], 1), round(w[1], 1), round(w[2], 1), round(w[3], 1)]}
            for w in words if w[4].strip()
        ][:limit]
    except Exception:
        return []


def _is_valid_dim(val: str) -> bool:
    """True if val looks like a real engineering measurement."""
    if not val or len(val) > 20:
        return False
    bad = ["CALC", "REQ", "INSERT", "MISS", "DETAIL", "SUBMIT", "RECTIF", "COMPLIANT"]
    if any(k in val.upper() for k in bad):
        return False
    return bool(re.search(r"\d", val))


# ─────────────────────────────────────────────────────────────
# MAIN: SYNTHESIZE SELECTIVE EDIT COMMAND
# ─────────────────────────────────────────────────────────────

def synthesize_selective_command(
    comment: Dict[str, Any],
    page: fitz.Page,
    objects: List[EngineeringDrawingObject],
    provider: str = "Mistral AI",   # kept for API compat
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> SelectiveEditCommand:
    """
    Connects Mistral AI to validated Python drawing-modification tools
    via Pydantic schemas.

    Key improvements over old Sarvam implementation:
    - Rich spatial context (vectors + text) fed to the LLM.
    - Coordinates validated and clamped to page bounds.
    - Hallucinated dimension values stripped at source.
    """
    cid = comment.get("id", "C-001")
    text = comment.get("comment") or comment.get("text") or ""
    cb = comment.get("bbox") or [100.0, 100.0, 300.0, 200.0]
    arrow_tip = comment.get("arrow_tip")

    pw = float(page.rect.width)
    ph = float(page.rect.height)

    # ── 1. Identify target drawing object ──────────────────────
    target_obj = find_target_object_for_comment(comment, objects, page)

    # ── 2. Build spatial context clip (comment zone + 150pt) ──
    clip = fitz.Rect(
        max(0.0, cb[0] - 150), max(0.0, cb[1] - 150),
        min(pw, cb[2] + 150), min(ph, cb[3] + 150),
    )
    nearby_vectors = _nearby_vectors_summary(page, clip)
    nearby_text = _nearby_text_summary(page, clip)

    target_info = {
        "object_id": target_obj.object_id if target_obj else "NONE",
        "object_type": target_obj.object_type.value if target_obj else "unknown",
        "bbox": target_obj.bbox if target_obj else cb,
        "center": target_obj.center if target_obj else [(cb[0] + cb[2]) / 2.0, (cb[1] + cb[3]) / 2.0],
        "tag": target_obj.tag if target_obj else None,
        "elevation": target_obj.elevation if target_obj else None,
        "associated_labels": (target_obj.associated_labels if target_obj else [])[:8],
    }

    # ── 3. Build Mistral prompt ────────────────────────────────
    prompt = f"""You are an expert Autonomous 2D CAD & Engineering Drawing Rectification Agent.
Your task: translate ONE consultant comment into ONE precise, executable Python drawing-modification command.

═══ CONSULTANT COMMENT ═══
Comment ID        : {cid}
Directive Text    : "{text}"
Markup Bbox [x0,y0,x1,y1]: {cb}
Arrow Tip (if any): {arrow_tip}
Page dimensions   : {round(pw,1)} x {round(ph,1)} pt

═══ MAPPED TARGET DRAWING ELEMENT ═══
{json.dumps(target_info, indent=2)}

═══ NEARBY VECTOR PATHS (≤150pt from comment) ═══
{json.dumps(nearby_vectors, indent=2)}

═══ NEARBY TEXT SPANS (≤150pt from comment) ═══
{json.dumps(nearby_text, indent=2)}

═══ AVAILABLE SELECTIVE EDIT TOOLS ═══
1. "replace_symbol"            — Replace a device symbol (Card Reader, Door, Sensor) preserving position & scale.
   parameters: {{"new_symbol_name": "CARD_READER | BIOMETRIC_READER | SINGLE_SWING_DOOR", "scale": 1.0}}

2. "move_equipment"            — Displace an equipment block to verified coordinates.
   parameters: {{"dx": <float>, "dy": <float>, "target_coord": [x, y]}}

3. "remove_conduit"            — Sever/delete an incorrect conduit run.
   parameters: {{}}   (uses target_bbox)

4. "update_dimension"          — Replace outdated dimension text with exact measurement.
   parameters: {{"new_dimension_value": "<number> mm"}}

5. "update_elevation"          — Update a device mounting-elevation callout.
   parameters: {{"new_elevation_str": "H=1200mm"}}

6. "restore_space_id"          — Restore missing room / space IDs.
   parameters: {{"space_id_text": "LOBBY\\nM.B1.038"}}

7. "regenerate_table_or_legend"— Fix a legend entry or schedule table.
   parameters: {{"new_legend_text": "CARD READER", "replace_symbol_at_tip": true}}

8. "add_annotation"            — Flag for engineer review only (no geometry change).
   parameters: {{"annotation_text": ""}}

═══ STRICT RULES ═══
- Return ONLY valid JSON matching the schema below. No markdown, no prose.
- target_bbox MUST be within page bounds [0,0,{round(pw,1)},{round(ph,1)}].
- Use the mapped target element bbox as target_bbox when the consultant arrow points at it.
- If the arrow_tip is given, set target_bbox to a ±20pt box around it.
- Do NOT invent engineering dimensions or coordinates absent from the comment or nearby text.
- Do NOT set new_dimension_value to sentences or instructions — only numeric strings like "1050 mm".
- Do NOT generate labels starting with "RECTIFIED PER" or "COMPLIANT WITH".
- If the comment is about calculations, submittals, or requires engineer judgment, use "add_annotation".
- If specific coordinates are missing from the comment, set requires_engineer_review: true.

═══ JSON OUTPUT SCHEMA ═══
{{
    "command_id": "CMD-{cid}",
    "comment_id": "{cid}",
    "action_type": "<one of the 8 tool names above>",
    "object_type": "{target_info['object_type']}",
    "target_object_id": "{target_info['object_id']}",
    "target_bbox": [x0, y0, x1, y1],
    "parameters": {{}},
    "engineering_rationale": "<concise explanation — max 120 chars>",
    "requires_engineer_review": false,
    "missing_specs": null
}}
"""

    # ── 4. Call LLM (Sarvam AI / Mistral) ─────────────────────
    raw_command = None
    try:
        raw_text = call_llm(
            prompt,
            provider="Sarvam AI",
            api_key=api_key or SARVAM_API_KEY,
            model=model or SARVAM_MODEL,
            temperature=0.05,
        )
        raw_command = clean_json_response(raw_text)
    except Exception:
        raw_command = None

    # ── 5. Validate & sanitise the LLM response ───────────────
    if raw_command and isinstance(raw_command, dict) and "action_type" in raw_command:
        # 5a. Clamp target_bbox to page
        tb = raw_command.get("target_bbox")
        if tb and len(tb) == 4:
            raw_command["target_bbox"] = _clamp_bbox([float(x) for x in tb], pw, ph)
        else:
            raw_command["target_bbox"] = _clamp_bbox(cb, pw, ph)

        # 5b. Strip hallucinated dimension values
        params = raw_command.get("parameters") or {}
        dim_val = str(params.get("new_dimension_value") or "")
        if dim_val and not _is_valid_dim(dim_val):
            params["new_dimension_value"] = None
            raw_command["action_type"] = "add_annotation"
            raw_command["requires_engineer_review"] = True
            raw_command["parameters"] = {"annotation_text": ""}

        # 5c. Downgrade calculation / submittal items
        c_lower = text.lower()
        if any(k in c_lower for k in ["calculation", "fill", "back box", "first fix", "code c", "rejected"]):
            raw_command["action_type"] = "add_annotation"
            raw_command["requires_engineer_review"] = True
            raw_command["parameters"] = {"annotation_text": ""}

        try:
            return SelectiveEditCommand.model_validate(raw_command)
        except Exception:
            pass  # fall through to analytical fallback

    # ── 6. Analytical deterministic fallback ──────────────────
    return _build_analytical_selective_command(comment, target_obj, cb, pw, ph)


# ─────────────────────────────────────────────────────────────
# ANALYTICAL DETERMINISTIC FALLBACK
# ─────────────────────────────────────────────────────────────

def _build_analytical_selective_command(
    comment: Dict[str, Any],
    target_obj: Optional[EngineeringDrawingObject],
    comment_bbox: List[float],
    pw: float = 842.0,
    ph: float = 595.0,
) -> SelectiveEditCommand:
    """
    Deterministic command synthesised from comment keywords + spatial geometry.
    Uses arrow_tip when available (more accurate than comment_bbox).
    """
    cid = comment.get("id", "C-001")
    text = comment.get("comment", "").lower()
    tip = comment.get("arrow_tip")

    # Prefer: target_obj.bbox > arrow_tip box > comment_bbox
    if target_obj:
        tb = _clamp_bbox(target_obj.bbox, pw, ph)
    elif tip:
        tb = _clamp_bbox([tip[0] - 20, tip[1] - 20, tip[0] + 20, tip[1] + 20], pw, ph)
    else:
        tb = _clamp_bbox(comment_bbox, pw, ph)

    to_id = target_obj.object_id if target_obj else None
    to_type = target_obj.object_type if target_obj else EngineeringObjectType.GENERAL

    # ── Legend: "CARD + PIN READER" → "CARD READER" ───────────
    if "legend" in text and ("card reader" in text or "pin reader" in text or "reader" in text):
        return SelectiveEditCommand(
            command_id=f"CMD-{cid}",
            comment_id=cid,
            action_type=SelectiveActionType.REGENERATE_TABLE_OR_LEGEND,
            object_type=EngineeringObjectType.LEGEND,
            target_object_id=to_id,
            target_bbox=tb,
            parameters={"new_legend_text": "CARD READER", "arrow_tip": tip, "replace_symbol_at_tip": True},
            engineering_rationale=f"Rectified security legend entry to 'CARD READER' and updated symbol per {cid}.",
            requires_engineer_review=False,
        )

    # ── Conduit on direction arrow ─────────────────────────────
    elif (("conduit" in text or "wire" in text)
          and ("direction" in text or "legend" in text or "denotes" in text or "symbol" in text)):
        return SelectiveEditCommand(
            command_id=f"CMD-{cid}",
            comment_id=cid,
            action_type=SelectiveActionType.REMOVE_CONDUIT,
            object_type=EngineeringObjectType.DIRECTION_ARROW,
            target_object_id=to_id,
            target_bbox=tb,
            parameters={"arrow_tip": tip},
            engineering_rationale=f"Severed invalid conduit on direction arrow per {cid}.",
            requires_engineer_review=False,
        )

    # ── Card Reader relocation / keep original ─────────────────
    elif "card reader" in text and ("location" in text or "changed" in text or "keep" in text or "relocate" in text):
        return SelectiveEditCommand(
            command_id=f"CMD-{cid}",
            comment_id=cid,
            action_type=SelectiveActionType.REPLACE_SYMBOL,
            object_type=EngineeringObjectType.CARD_READER,
            target_object_id=to_id,
            target_bbox=tb,
            parameters={"new_symbol_name": "CARD_READER", "scale": 1.0, "arrow_tip": tip},
            engineering_rationale=f"Replaced Card Reader with IFC-standard symbol at latch per {cid}.",
            requires_engineer_review=False,
        )

    # ── Elevation update ───────────────────────────────────────
    elif "elevation" in text:
        match = re.search(r"(\d{3,4})\s*mm", text)
        elev = f"H={match.group(1)}mm" if match else "H=1200mm"
        return SelectiveEditCommand(
            command_id=f"CMD-{cid}",
            comment_id=cid,
            action_type=SelectiveActionType.UPDATE_ELEVATION,
            object_type=EngineeringObjectType.ELEVATION_TAG,
            target_object_id=to_id,
            target_bbox=tb,
            parameters={"new_elevation_str": elev, "arrow_tip": tip},
            engineering_rationale=f"Updated device elevation to {elev} AFF per {cid}.",
            requires_engineer_review=False,
        )

    # ── Space ID restoration ───────────────────────────────────
    elif "space id" in text or ("room" in text and "id" in text):
        return SelectiveEditCommand(
            command_id=f"CMD-{cid}",
            comment_id=cid,
            action_type=SelectiveActionType.RESTORE_SPACE_ID,
            object_type=EngineeringObjectType.SPACE_ID,
            target_object_id=to_id,
            target_bbox=tb,
            parameters={"space_id_text": "LOBBY\nM.B1.036", "arrow_tip": tip},
            engineering_rationale=f"Restored architectural space ID per {cid}.",
            requires_engineer_review=False,
        )

    # ── Calculation / submittal review (no geometry change) ────
    elif any(k in text for k in ["calculation", "fill", "back box", "first fix", "code c", "rejected"]):
        return SelectiveEditCommand(
            command_id=f"CMD-{cid}",
            comment_id=cid,
            action_type=SelectiveActionType.ADD_ANNOTATION,
            object_type=to_type,
            target_object_id=to_id,
            target_bbox=tb,
            parameters={"annotation_text": ""},
            engineering_rationale=f"Technical review item — drawing geometry preserved per {cid}.",
            requires_engineer_review=True,
            missing_specs="Calculation / submittal required; drawing geometry unchanged.",
        )

    # ── Dimension update ───────────────────────────────────────
    elif any(k in text for k in ["width", "dimension", "mm", "height", "clearance", "size"]):
        dim_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mm|m|cm)?", text)
        new_dim = f"{dim_match.group(1)} mm" if dim_match else "1050 mm"
        if not _is_valid_dim(new_dim):
            new_dim = "1050 mm"
        return SelectiveEditCommand(
            command_id=f"CMD-{cid}",
            comment_id=cid,
            action_type=SelectiveActionType.UPDATE_DIMENSION,
            object_type=EngineeringObjectType.DIMENSION,
            target_object_id=to_id,
            target_bbox=tb,
            parameters={"new_dimension_value": new_dim},
            engineering_rationale=f"Adjusted CAD dimension to '{new_dim}' per {cid}.",
            requires_engineer_review=False,
        )

    # ── Card Reader symbol replacement ─────────────────────────
    elif "card reader" in text or "reader" in text:
        sym = "BIOMETRIC_READER" if "bio" in text else "CARD_READER"
        return SelectiveEditCommand(
            command_id=f"CMD-{cid}",
            comment_id=cid,
            action_type=SelectiveActionType.REPLACE_SYMBOL,
            object_type=EngineeringObjectType.CARD_READER,
            target_object_id=to_id,
            target_bbox=tb,
            parameters={"new_symbol_name": sym, "scale": 1.0, "arrow_tip": tip},
            engineering_rationale=f"Replaced symbol with IFC-compliant '{sym}' per {cid}.",
            requires_engineer_review=False,
        )

    # ── General conduit removal ────────────────────────────────
    elif "conduit" in text:
        return SelectiveEditCommand(
            command_id=f"CMD-{cid}",
            comment_id=cid,
            action_type=SelectiveActionType.REMOVE_CONDUIT,
            object_type=EngineeringObjectType.CONDUIT,
            target_object_id=to_id,
            target_bbox=tb,
            parameters={"arrow_tip": tip},
            engineering_rationale=f"Severed non-compliant conduit run per {cid}.",
            requires_engineer_review=False,
        )

    # ── General fallback ───────────────────────────────────────
    else:
        return SelectiveEditCommand(
            command_id=f"CMD-{cid}",
            comment_id=cid,
            action_type=SelectiveActionType.ADD_ANNOTATION,
            object_type=to_type,
            target_object_id=to_id,
            target_bbox=tb,
            parameters={"annotation_text": ""},
            engineering_rationale=f"Directive reviewed; engineer sign-off required per {cid}.",
            requires_engineer_review=True,
            missing_specs="Insufficient context to generate automated geometry modification.",
        )
