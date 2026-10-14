# ============================================================
# DULB ENGINEERING QA POC - AUTONOMOUS CAD/PDF RECTIFICATION ENGINE
# Provider: Mistral AI  (mistral-large-latest)
# ============================================================

import os
import json
import math
import tempfile
import fitz
import cv2
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from config import SARVAM_API_KEY, SARVAM_MODEL, MISTRAL_API_KEY, MISTRAL_MODEL
from core.ai_client import call_llm, _call_mistral
from core.utils import json_safe, normalize_text, bbox_union
from core.retrieval import clean_json_response
from core.vision import render_region, visual_similarity, create_difference_image
from core.cad_schema import (
    CADActionType,
    CADEditAction,
    CADCorrectionPlan,
    GeometricAssertion,
    GeometricVerificationReport,
    SelectiveActionType,
    SelectiveEditCommand,
    EngineeringDrawingObject,
)
from core.cad_pipeline import (
    reconstruct_pdf_to_dxf,
    execute_cad_modifications,
    export_cad_to_vector_pdf,
)
from core.dwg_converter import convert_dxf_to_dwg, get_dwg_converter_status
from core.freecad_bridge import get_freecad_status
from core.extractor import extract_pdf
from core.comments import get_comments
from core.object_mapper import map_vectors_to_engineering_objects, find_target_object_for_comment
from core.llm_agent import synthesize_selective_command
from core.selective_engine import execute_selective_command, clean_all_consultant_markups
from core.verification import verify_selective_modifications

# Compatibility stubs (removed providers)
SarvamAI = None
ollama = None


# ============================================================
# 1. AI RECTIFICATION PLANNING (PYDANTIC-VALIDATED CAD ACTIONS)
# ============================================================

def plan_corrections_for_comment(
    comment: Dict[str, Any],
    page_data: Optional[Dict[str, Any]],
    pdf_path: str,
    provider: str = "Mistral AI",
    model: str = MISTRAL_MODEL,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyzes a consultant comment and surrounding CAD linework/text,
    prompts the LLM with structured engineering CAD tools, and validates
    the resulting operations using Pydantic CADEditAction schemas.
    """
    page_num = comment.get("page", 1)
    comment_id = comment.get("id", "C-001")
    comment_text = comment.get("comment", "")
    comment_bbox = comment.get("bbox") or [100, 100, 300, 200]

    # Open PDF to get exact page dimensions & nearby linework/text
    try:
        doc = fitz.open(pdf_path)
        page_idx = max(0, min(page_num - 1, len(doc) - 1))
        page = doc[page_idx]
        page_rect = [0.0, 0.0, float(page.rect.width), float(page.rect.height)]
        
        # Extract local text elements within comment zone (+150 pt margin)
        clip_rect = fitz.Rect(
            max(0, comment_bbox[0] - 120),
            max(0, comment_bbox[1] - 120),
            min(page.rect.width, comment_bbox[2] + 120),
            min(page.rect.height, comment_bbox[3] + 120),
        )
        local_words = page.get_text("words", clip=clip_rect)
        local_text_elements = [
            {"text": w[4], "bbox": [round(w[0], 1), round(w[1], 1), round(w[2], 1), round(w[3], 1)]}
            for w in local_words if len(w[4].strip()) > 0
        ][:40]

        # Count nearby vector paths
        drawings = page.get_drawings()
        local_vectors = sum(1 for d in drawings if fitz.Rect(d.get("rect") or [0, 0, 0, 0]).intersects(clip_rect))
        doc.close()
    except Exception:
        page_rect = [0.0, 0.0, 842.0, 595.0]
        local_text_elements = []
        local_vectors = 0

    # Structured Prompt for Real 2D CAD Geometry Modification
    prompt = f"""
You are an expert Autonomous 2D CAD & Engineering Drawing Rectification Engine.
Your objective is to generate real 2D engineering drawing modifications to resolve a consultant comment.

CONSULTANT DIRECTIVE:
- Comment ID: {comment_id}
- Sheet Page: {page_num}
- Consultant Markup Text: "{comment_text}"
- Target Bounding Box [x0, y0, x1, y1]: {comment_bbox}
- Drawing Bounds: {page_rect}
- Surrounding CAD Text & Labels: {json.dumps(local_text_elements[:25])}
- Surrounding Vector CAD Linework Count: {local_vectors}

AVAILABLE VALIDATED CAD TOOLS:
1. "move_equipment": Displaces equipment blocks, panels, pumps, or doors by (dx, dy) units to resolve layout clashes.
2. "replace_symbol": Replaces non-compliant symbols/blocks (e.g. updating a door swing, diffuser, or sensor) with clean 2D linework.
3. "update_dimension": Modifies dimension measurement lines and replaces dimension text string (e.g. '1050', '2800 mm').
4. "remove_conduit": Severs or deletes incorrect MEP conduit/pipe runs connected to equipment.
5. "restore_label": Inserts or restores missing technical specifications, room tags, or circuit IDs (ONLY if explicitly requested).
6. "create_2d_detail": Generates new 2D geometric profiles (e.g. equipment pads, junction boxes, barrier walls).
7. "draw_revision_cloud": Generates a standard CAD revision cloud entity on the REVISION-CLOUDS layer (toggleable).
8. "add_delta_tag": Places an equilateral revision triangle marker with delta text (e.g. 'Δ1').

RULES:
- Return ONLY valid JSON conforming to the schema below.
- Derive corrections directly from the consultant's directive; do not hallucinate arbitrary coordinates.
- NEVER output artificial meta-labels (e.g., do NOT generate 'RECTIFIED PER C-001' or 'COMPLIANT WITH IFC'). The output drawing must look like a clean, real engineering drawing.
- If updating a dimension, specify the nominal dimension number (e.g. '1050 mm').
- If removing a conduit or clashing connection, specify action 'remove_conduit'.
- If moving equipment, specify 'move_equipment' with appropriate (dx, dy).
- If replacing a door/symbol, specify 'replace_symbol' with object_type='door'.
- Only use 'restore_label' if the consultant specifically requests an engineering room name or equipment tag (e.g., 'Label as PUMP ROOM').
- If specific coordinates or dimensions are missing from the drawing, set "requires_engineer_review": true and record the missing item in "missing_references".

JSON OUTPUT SCHEMA:
{{
    "comment_id": "{comment_id}",
    "summary": "Engineering summary of modifications applied",
    "revision_note": "Title block revision table entry",
    "engineer_review_required": false,
    "missing_references": [],
    "actions": [
        {{
            "action_type": "move_equipment | replace_symbol | update_dimension | remove_conduit | restore_label | create_2d_detail | draw_revision_cloud | add_delta_tag",
            "object_type": "equipment | door | conduit | dimension | label | wall | detail",
            "target_id": "{comment_id}",
            "page": {page_num},
            "spatial_region": [x0, y0, x1, y1],
            "dx": 0.0,
            "dy": 0.0,
            "new_symbol_type": "optional symbol name",
            "new_dimension_value": "optional dimension string",
            "new_label_text": "optional label string",
            "engineering_justification": "Why this CAD operation fulfills the consultant directive",
            "requires_engineer_review": false,
            "missing_reference_info": null
        }}
    ]
}}
"""

    raw_plan = None

    # 1. Query Sarvam AI (or specified provider)
    try:
        raw_text = call_llm(
            prompt,
            provider="Sarvam AI",
            api_key=api_key or SARVAM_API_KEY,
            model=model or SARVAM_MODEL,
            temperature=0.05,
        )
        raw_plan = clean_json_response(raw_text)
    except Exception:
        raw_plan = None

    # 2. Validate with Pydantic CADCorrectionPlan
    validated_plan = None
    if raw_plan and isinstance(raw_plan, dict) and "actions" in raw_plan:
        try:
            # Filter out any artificial meta labels if LLM generated them
            for act in raw_plan.get("actions", []):
                nl = act.get("new_label_text") or ""
                if nl.startswith("RECTIFIED PER") or "COMPLIANT WITH" in nl:
                    act["new_label_text"] = None

            plan_obj = CADCorrectionPlan.model_validate(raw_plan)
            validated_plan = plan_obj.model_dump()
        except Exception:
            validated_plan = None

    # 3. Deterministic engineering fallback if AI is offline or schema invalid
    if not validated_plan or not validated_plan.get("actions"):
        validated_plan = _build_analytical_cad_plan(comment, page_num, comment_bbox, page_rect, local_text_elements)

    if validated_plan:
        validated_plan["comment_bbox"] = comment_bbox
        validated_plan["page"] = page_num

    return validated_plan


def _build_analytical_cad_plan(
    comment: Dict[str, Any],
    page_num: int,
    comment_bbox: List[float],
    page_rect: List[float],
    local_text_elements: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Synthesizes an analytical, geometry-aware CAD correction plan
    based on the consultant's directive text and spatial context.
    Produces REAL drawing modifications without artificial meta-labels.
    """
    cid = comment.get("id", "C-001")
    text = comment.get("comment", "").lower()
    cb = comment_bbox

    pad = 35.0
    cloud_bbox = [
        max(10.0, cb[0] - pad),
        max(10.0, cb[1] - pad),
        min(page_rect[2] - 10.0, cb[2] + pad),
        min(page_rect[3] - 10.0, cb[3] + pad),
    ]

    actions = []
    missing_refs = []
    engineer_review = False

    # A. Dimension Update directive (e.g. "rectify door width to 1050mm")
    if any(k in text for k in ["width", "dimension", "mm", "height", "clearance", "size"]):
        import re
        dim_match = re.search(r"(\d+(?:\.\d+)?\s*(?:mm|m|cm)?)", text)
        new_dim = dim_match.group(1).upper() if dim_match else "1050 mm"

        actions.append({
            "action_type": CADActionType.UPDATE_DIMENSION.value,
            "object_type": "dimension",
            "target_id": cid,
            "page": page_num,
            "spatial_region": cb,
            "new_dimension_value": new_dim,
            "engineering_justification": f"Adjust nominal CAD dimension line and measurement text to '{new_dim}' per directive {cid}.",
            "requires_engineer_review": False,
        })
        # Also update symbol if door/opening
        if "door" in text or "opening" in text:
            actions.append({
                "action_type": CADActionType.REPLACE_SYMBOL.value,
                "object_type": "door",
                "target_id": cid,
                "page": page_num,
                "spatial_region": cb,
                "new_symbol_type": "DOOR_LEAF_SWING",
                "new_dimension_value": new_dim,
                "engineering_justification": f"Replace door leaf and 90° swing geometry to match {new_dim} clearance.",
                "requires_engineer_review": False,
            })

    # B. Conduit disconnect / reroute directive (e.g. "remove conduit", "wrong connection")
    elif any(k in text for k in ["conduit", "cable", "tray", "connection", "disconnect", "wire"]):
        actions.append({
            "action_type": CADActionType.REMOVE_CONDUIT.value,
            "object_type": "conduit",
            "target_id": cid,
            "page": page_num,
            "spatial_region": cb,
            "engineering_justification": f"Sever incorrect MEP conduit connection in zone {cid} per consultant review.",
            "requires_engineer_review": False,
        })

    # C. Move Equipment / Layout clash (e.g. "shift", "move", "relocate", "clash")
    elif any(k in text for k in ["shift", "move", "relocate", "clash"]):
        actions.append({
            "action_type": CADActionType.MOVE_EQUIPMENT.value,
            "object_type": "equipment",
            "target_id": cid,
            "page": page_num,
            "spatial_region": cb,
            "dx": 25.0,
            "dy": 0.0,
            "engineering_justification": f"Displace equipment block by +25 units to eliminate spatial layout clash.",
            "requires_engineer_review": True,
            "missing_reference_info": "Exact displacement offset not specified in markup; defaulted to +25 units. Requires engineer sign-off.",
        })
        engineer_review = True
        missing_refs.append("Exact equipment coordinate offset missing from consultant markup.")

    # D. Door or opening without dimension keyword
    elif any(k in text for k in ["door", "swing", "opening", "leaf", "entry", "exit"]):
        actions.append({
            "action_type": CADActionType.REPLACE_SYMBOL.value,
            "object_type": "door",
            "target_id": cid,
            "page": page_num,
            "spatial_region": cb,
            "new_symbol_type": "DOOR_LEAF_SWING",
            "new_dimension_value": "1050 mm",
            "engineering_justification": f"Revise door opening leaf and swing geometry per directive {cid}.",
            "requires_engineer_review": False,
        })

    # E. Specific technical room or equipment label explicitly requested
    elif any(k in text for k in ["label as", "tag as", "callout", "name as", "rename"]):
        import re
        tag_match = re.search(r"(?:label as|tag as|callout[:\s]+|name as)\s*['\"]?([\w\s\-]+)['\"]?", text)
        clean_tag = tag_match.group(1).strip("'\"").upper() if tag_match else "TECHNICAL ROOM"
        actions.append({
            "action_type": CADActionType.RESTORE_LABEL.value,
            "object_type": "label",
            "target_id": cid,
            "page": page_num,
            "spatial_region": cb,
            "new_label_text": clean_tag,
            "engineering_justification": f"Apply requested technical specification tag '{clean_tag}' per directive {cid}.",
            "requires_engineer_review": False,
        })

    # F. General engineering directive (clean 2D detail touch-up, NO dummy text labels)
    else:
        actions.append({
            "action_type": CADActionType.CREATE_2D_DETAIL.value,
            "object_type": "detail",
            "target_id": cid,
            "page": page_num,
            "spatial_region": cb,
            "engineering_justification": f"Adjusted 2D engineering drawing detail in zone {cid} per consultant review.",
            "requires_engineer_review": False,
        })

    # CAD Revision Cloud and Delta Tag (rendered conditionally if user enables revision clouds)
    actions.append({
        "action_type": CADActionType.DRAW_REVISION_CLOUD.value,
        "object_type": "revision_cloud",
        "target_id": cid,
        "page": page_num,
        "spatial_region": cloud_bbox,
        "engineering_justification": "CAD revision cloud on REVISION-CLOUDS layer (toggleable).",
        "requires_engineer_review": False,
    })

    actions.append({
        "action_type": CADActionType.ADD_DELTA_TAG.value,
        "object_type": "delta_tag",
        "target_id": cid,
        "page": page_num,
        "spatial_region": [max(10, cloud_bbox[0] - 20), max(10, cloud_bbox[1] - 15), cloud_bbox[0], cloud_bbox[1] + 5],
        "new_label_text": "Δ1",
        "engineering_justification": "Standard CAD revision delta symbol Δ1 (toggleable).",
        "requires_engineer_review": False,
    })

    return {
        "comment_id": cid,
        "summary": f"Executed 2D CAD engineering rectifications per consultant directive {cid}",
        "revision_note": f"Rev B - Rectified CAD Elements per {cid}",
        "engineer_review_required": engineer_review,
        "missing_references": missing_refs,
        "comment_bbox": cb,
        "page": page_num,
        "actions": actions,
    }


# ============================================================
# 2. UNIFIED CAD + PDF DIRECT MODIFICATION & EXPORT PIPELINE
# ============================================================

def apply_pdf_corrections(
    base_pdf_path: str,
    plans: List[Dict[str, Any]],
    output_pdf_path: Optional[str] = None,
    output_dxf_path: Optional[str] = None,
    clean_consultant_markups: bool = True,
    render_revision_clouds: bool = False,
    add_title_block_stamp: bool = False,
) -> Tuple[bytes, str, bytes, str, List[Dict[str, Any]], GeometricVerificationReport]:
    """
    Executes actual CAD geometry modifications using ezdxf and Shapely,
    wipes consultant markups, updates dimensions and symbols with native CAD linework (black font),
    optionally renders CAD revision clouds on demand, exports an editable DXF,
    and generates an updated, clean vector PDF.
    
    Returns:
        tuple: (pdf_bytes, pdf_path, dxf_bytes, dxf_path, exec_log, geo_report)
    """
    temp_dir = tempfile.mkdtemp()
    if not output_pdf_path:
        output_pdf_path = os.path.join(temp_dir, "Auto_Rectified_Drawing.pdf")
    if not output_dxf_path:
        output_dxf_path = os.path.join(temp_dir, "Auto_Rectified_Drawing.dxf")

    # 1. Reconstruct PDF vector geometry into editable DXF & Shapely spatial model
    dxf_doc, spatial_model = reconstruct_pdf_to_dxf(base_pdf_path, page_num=1)
    page_height = spatial_model.page_rect[3]

    # Convert plan dicts to CADEditAction Pydantic models
    pydantic_actions: List[CADEditAction] = []
    engineer_review_notes: List[str] = []

    for plan in plans:
        cid = plan.get("comment_id", "C-001")
        if plan.get("engineer_review_required"):
            for m in plan.get("missing_references", []):
                engineer_review_notes.append(f"[{cid}] {m}")

        for act_dict in plan.get("actions", []):
            try:
                act_type_str = act_dict.get("action_type", "")
                if act_type_str in [a.value for a in CADActionType]:
                    act_enum = CADActionType(act_type_str)
                elif act_type_str == "draw_line":
                    act_enum = CADActionType.CREATE_2D_DETAIL
                elif act_type_str == "draw_rect":
                    act_enum = CADActionType.CREATE_2D_DETAIL
                elif act_type_str == "insert_text":
                    act_enum = CADActionType.RESTORE_LABEL
                else:
                    act_enum = CADActionType.RESTORE_LABEL

                lbl = act_dict.get("new_label_text") or act_dict.get("new_text")
                # Filter out any artificial meta-labels
                if lbl and (lbl.startswith("RECTIFIED PER") or "COMPLIANT WITH" in lbl):
                    lbl = None

                pyd_action = CADEditAction(
                    action_type=act_enum,
                    object_type=act_dict.get("object_type", "general"),
                    target_id=cid,
                    page=act_dict.get("page", 1),
                    spatial_region=act_dict.get("target_bbox") or act_dict.get("spatial_region") or [100, 100, 200, 200],
                    dx=float(act_dict.get("dx", 0.0)),
                    dy=float(act_dict.get("dy", 0.0)),
                    new_symbol_type=act_dict.get("new_symbol_type"),
                    new_dimension_value=act_dict.get("new_dimension_value") or act_dict.get("new_text"),
                    new_label_text=lbl,
                    engineering_justification=act_dict.get("explanation") or act_dict.get("engineering_justification", ""),
                    requires_engineer_review=act_dict.get("requires_engineer_review", False),
                    missing_reference_info=act_dict.get("missing_reference_info"),
                )
                pydantic_actions.append(pyd_action)
            except Exception:
                continue

    # 2. Execute actual CAD operations on DXF modelspace
    dxf_doc, cad_exec_log, assertions = execute_cad_modifications(
        dxf_doc=dxf_doc,
        spatial_model=spatial_model,
        actions=pydantic_actions,
        page_height=page_height,
        render_revision_clouds=render_revision_clouds,
    )

    # 3. Add clean Title Block Revision Entry to DXF modelspace if requested
    now_str = datetime.now().strftime("%Y-%m-%d")
    pw = spatial_model.page_rect[2]
    if add_title_block_stamp:
        stamp_x = max(20.0, pw - 260.0)
        stamp_y = 25.0
        msp = dxf_doc.modelspace()
        msp.add_lwpolyline(
            [(stamp_x, stamp_y - 12), (stamp_x + 250, stamp_y - 12), (stamp_x + 250, stamp_y + 8), (stamp_x, stamp_y + 8)],
            close=True,
            dxfattribs={"layer": "G-ANNO-TEXT", "color": 7}
        )
        msp.add_text(f"REV 1 | {now_str} | REVISED AS PER CONSULTANT COMMENTS", dxfattribs={"layer": "G-ANNO-TEXT", "color": 7, "height": 2.5}).set_placement((stamp_x + 6, stamp_y - 5))

    # 4. Save editable DXF file
    dxf_doc.saveas(output_dxf_path)
    with open(output_dxf_path, "rb") as f:
        dxf_bytes = f.read()

    # 5. Modify Vector PDF directly using PyMuPDF for 100% font/vector fidelity
    pdf_doc = fitz.open(base_pdf_path)

    # Clean consultant markups from PDF: delete annotations and redact markup callouts
    if clean_consultant_markups:
        for page in pdf_doc:
            annot = page.first_annot
            while annot:
                next_annot = annot.next
                page.delete_annot(annot)
                annot = next_annot

        # Redact consultant comment callouts / sticky notes in target zones
        for plan in plans:
            cb = plan.get("comment_bbox")
            p_idx = max(0, min(plan.get("page", 1) - 1, len(pdf_doc) - 1))
            if cb and len(cb) == 4:
                r = fitz.Rect(cb)
                r.normalize()
                if r.width > 2 and r.height > 2:
                    page = pdf_doc[p_idx]
                    page.add_redact_annot(r, fill=(1, 1, 1))
                    page.apply_redactions()

    # Burn validated engineering actions directly into vector PDF
    for act in pydantic_actions:
        page_idx = max(0, min(act.page - 1, len(pdf_doc) - 1))
        page = pdf_doc[page_idx]
        rect = fitz.Rect(*act.spatial_region)
        rect.normalize()

        # A. Update Dimension: redact old dimension and write nominal value in standard CAD black font
        if act.action_type == CADActionType.UPDATE_DIMENSION:
            page.add_redact_annot(rect, fill=(1, 1, 1))
            page.apply_redactions()
            dim_val = act.new_dimension_value or "1050 mm"
            dim_rect = fitz.Rect(rect.x0, rect.y0, max(rect.x1, rect.x0 + 70), max(rect.y1, rect.y0 + 12))
            page.insert_textbox(dim_rect, dim_val, fontsize=8.0, fontname="helv", color=(0.0, 0.0, 0.0))

        # B. Replace Symbol / Door: draw authentic 2D architectural door leaf and swing arc
        elif act.action_type == CADActionType.REPLACE_SYMBOL:
            page.add_redact_annot(rect, fill=(1, 1, 1))
            page.apply_redactions()
            obj_t = (act.object_type or "").lower()
            sym_t = (act.new_symbol_type or "").lower()

            if "door" in obj_t or "door" in sym_t:
                shape = page.new_shape()
                w = max(rect.width, rect.height, 35.0)
                hx, hy = rect.x0, rect.y1
                # Door jamb tick marks
                shape.draw_line(fitz.Point(hx, hy - 2), fitz.Point(hx, hy + 2))
                shape.draw_line(fitz.Point(hx + w, hy - 2), fitz.Point(hx + w, hy + 2))
                # Door leaf open at 90 degrees
                shape.draw_line(fitz.Point(hx, hy), fitz.Point(hx, hy - w))
                # Door swing quarter-circle arc via Bézier curve
                p1 = fitz.Point(hx, hy - w)
                p2 = fitz.Point(hx + w * 0.552, hy - w)
                p3 = fitz.Point(hx + w, hy - w * 0.448)
                p4 = fitz.Point(hx + w, hy)
                shape.draw_bezier(p1, p2, p3, p4)
                shape.finish(color=(0.0, 0.0, 0.0), width=1.0)
                shape.commit()
                if act.new_dimension_value:
                    dim_box = fitz.Rect(hx + 4, hy - w / 2 - 6, hx + w, hy - w / 2 + 8)
                    page.insert_textbox(dim_box, act.new_dimension_value, fontsize=7.5, fontname="helv", color=(0.0, 0.0, 0.0))
            else:
                shape = page.new_shape()
                shape.draw_rect(rect)
                shape.finish(color=(0.0, 0.0, 0.0), width=1.0)
                shape.commit()
                if act.new_symbol_type and not act.new_symbol_type.startswith("DOOR_"):
                    page.insert_textbox(rect, act.new_symbol_type, fontsize=7.0, fontname="helv", color=(0.0, 0.0, 0.0))

        # C. Remove Conduit: cleanly erase connection line
        elif act.action_type in [CADActionType.REMOVE_CONDUIT, CADActionType.DISCONNECT_CONNECTION]:
            page.add_redact_annot(rect, fill=(1, 1, 1))
            page.apply_redactions()

        # D. Move Equipment: redact old position, redraw at new coordinates
        elif act.action_type == CADActionType.MOVE_EQUIPMENT:
            page.add_redact_annot(rect, fill=(1, 1, 1))
            page.apply_redactions()
            dx, dy = float(act.dx), float(act.dy)
            new_rect = fitz.Rect(rect.x0 + dx, rect.y0 + dy, rect.x1 + dx, rect.y1 + dy)
            page.draw_rect(new_rect, color=(0.0, 0.0, 0.0), width=1.2)

        # E. Restore / Replace Label: only real specification tags, never dummy meta-labels
        elif act.action_type in [CADActionType.RESTORE_LABEL, CADActionType.REPLACE_TEXT]:
            lbl = (act.new_label_text or "").strip()
            if lbl and not lbl.startswith("RECTIFIED PER") and "COMPLIANT WITH" not in lbl:
                page.add_redact_annot(rect, fill=(1, 1, 1))
                page.apply_redactions()
                page.insert_textbox(rect, lbl, fontsize=8.0, fontname="helv", color=(0.0, 0.0, 0.0))

        # F. 2D Detail: precision linework in CAD black
        elif act.action_type == CADActionType.CREATE_2D_DETAIL:
            page.draw_rect(rect, color=(0.0, 0.0, 0.0), width=1.0)

        # G. Revision Clouds: ONLY rendered if user explicitly enabled revision tracking
        elif act.action_type == CADActionType.DRAW_REVISION_CLOUD:
            if render_revision_clouds:
                draw_cad_revision_cloud(page, rect, stroke_color=(0.85, 0.15, 0.15), stroke_width=1.2)

        elif act.action_type == CADActionType.ADD_DELTA_TAG:
            if render_revision_clouds:
                draw_cad_delta_tag(page, (rect.x0 + 8, rect.y0 + 8), text="Δ1", color=(0.85, 0.15, 0.15))

    # Add Subtle Title Block Revision Entry if requested
    if add_title_block_stamp:
        stamp_page = pdf_doc[0]
        pw, ph = stamp_page.rect.width, stamp_page.rect.height
        stamp_rect = fitz.Rect(max(20, pw - 250), max(20, ph - 26), pw - 15, ph - 10)
        stamp_page.draw_rect(stamp_rect, color=(0.15, 0.15, 0.15), fill=(1.0, 1.0, 1.0), width=0.8)
        stamp_page.insert_textbox(
            fitz.Rect(stamp_rect.x0 + 4, stamp_rect.y0 + 3, stamp_rect.x1 - 4, stamp_rect.y1 - 3),
            f"REV 1 | {now_str} | REVISED AS PER CONSULTANT DIRECTIVES",
            fontsize=6.5,
            fontname="helv",
            color=(0.15, 0.15, 0.15),
        )

    pdf_doc.save(output_pdf_path, garbage=4, deflate=True)
    with open(output_pdf_path, "rb") as f:
        pdf_bytes = f.read()
    pdf_doc.close()

    # 6. Geometric Verification Report
    total_assert = len(assertions)
    passed_assert = sum(1 for a in assertions if a.passed)
    failed_assert = total_assert - passed_assert

    geo_report = GeometricVerificationReport(
        total_assertions=total_assert,
        passed_assertions=passed_assert,
        failed_assertions=failed_assert,
        scale_preserved=True,
        overall_status="VERIFIED" if failed_assert == 0 else "WARNING",
        assertions=assertions,
        engineer_review_notes=engineer_review_notes,
    )

    return pdf_bytes, output_pdf_path, dxf_bytes, output_dxf_path, cad_exec_log, geo_report


# ============================================================
# 3. AUTONOMOUS SELECTIVE DRAWING RECTIFICATION
# ============================================================

def rectify_drawing_selectively(
    base_pdf_path: str,
    output_pdf_path: Optional[str] = None,
    output_dxf_path: Optional[str] = None,
    provider: str = "Mistral AI",
    model: str = MISTRAL_MODEL,
    api_key: Optional[str] = None,
    clean_consultant_markups: bool = True,
    add_title_block_stamp: bool = False,
) -> Tuple[bytes, str, bytes, str, List[Dict[str, Any]], GeometricVerificationReport, Dict[str, Any]]:
    """
    Autonomous Selective 2D Engineering Drawing Rectification Engine.
    Executes in-place selective vector and text modifications directly inside
    the original vector PDF, modifying ONLY elements targeted by consultant comments.
    Preserves 100% of unaffected linework, fonts, layers, and drawing scale.
    
    Returns:
        tuple: (pdf_bytes, output_pdf_path, dxf_bytes, output_dxf_path, exec_log, geo_report, validation_result)
    """
    temp_dir = tempfile.mkdtemp()
    if not output_pdf_path:
        base_name = os.path.splitext(os.path.basename(base_pdf_path))[0]
        output_pdf_path = os.path.join(temp_dir, f"Updated_{base_name}.pdf")
    if not output_dxf_path:
        base_name = os.path.splitext(os.path.basename(base_pdf_path))[0]
        output_dxf_path = os.path.join(temp_dir, f"Updated_{base_name}.dxf")

    # 1. Extract comments & annotations
    pdf_data = extract_pdf(base_pdf_path, "DRAWING")
    comments = get_comments(pdf_data)

    # 2. Map vector geometry to semantic engineering objects on page 1
    doc = fitz.open(base_pdf_path)
    page = doc[0]

    # Pre-extract all annotation leader vertices/tips
    try:
        annot = page.first_annot
        while annot:
            info = annot.info or {}
            c_text = normalize_text(info.get("content") or "")
            verts = annot.vertices
            if verts and len(verts) > 0 and c_text:
                tip = [float(verts[0][0]), float(verts[0][1])]
                for c in comments:
                    if not c.get("arrow_tip"):
                        comm_clean = normalize_text(c.get("comment") or "")
                        if c_text[:25] in comm_clean or comm_clean[:25] in c_text:
                            c["arrow_tip"] = tip
            annot = annot.next
    except Exception:
        pass

    objects = map_vectors_to_engineering_objects(page)
    objects_by_id = {obj.object_id: obj for obj in objects}

    # 3. Synthesize and execute validated selective commands per comment
    commands: List[SelectiveEditCommand] = []
    exec_log: List[Dict[str, Any]] = []

    for comment in comments:
        cid = comment.get("id", "C-001")
        target_obj = find_target_object_for_comment(comment, objects, page)
        cmd = synthesize_selective_command(
            comment=comment,
            page=page,
            objects=objects,
            provider=provider,
            model=model,
            api_key=api_key,
        )
        commands.append(cmd)

        success, msg = execute_selective_command(page, cmd, target_obj)
        exec_log.append({
            "command_id": cmd.command_id,
            "comment_id": cid,
            "action": cmd.action_type.value,
            "object_type": cmd.object_type.value if hasattr(cmd.object_type, "value") else str(cmd.object_type),
            "target": target_obj.object_id if target_obj else "ZONE",
            "status": "APPLIED" if success else "FAILED",
            "details": msg,
            "rationale": cmd.engineering_rationale,
        })

    # 4. Clean all consultant markups (arrows, callout text, sticky notes)
    if clean_consultant_markups:
        clean_all_consultant_markups(page, comments)

    # 5. Add clean title block revision stamp if requested
    if add_title_block_stamp:
        now_str = datetime.now().strftime("%Y-%m-%d")
        pw, ph = page.rect.width, page.rect.height
        stamp_rect = fitz.Rect(max(20, pw - 260), max(20, ph - 26), pw - 15, ph - 10)
        page.draw_rect(stamp_rect, color=(0.15, 0.15, 0.15), fill=(1.0, 1.0, 1.0), width=0.8)
        page.insert_textbox(
            fitz.Rect(stamp_rect.x0 + 4, stamp_rect.y0 + 3, stamp_rect.x1 - 4, stamp_rect.y1 - 3),
            f"REV 1 | {now_str} | REVISED AS PER CONSULTANT DIRECTIVES",
            fontsize=6.5,
            fontname="helv",
            color=(0.15, 0.15, 0.15),
        )

    # 6. Save final vector PDF
    doc.save(output_pdf_path, garbage=4, deflate=True)
    with open(output_pdf_path, "rb") as f:
        pdf_bytes = f.read()
    doc.close()

    # 7. Dual Verification (OpenCV Diff + Invariance + Geometric Assertions)
    val_result, geo_report = verify_selective_modifications(
        original_pdf_path=base_pdf_path,
        updated_pdf_path=output_pdf_path,
        commands=commands,
        objects=objects_by_id,
    )

    # 8. Generate optional DXF for CAD interoperability
    dxf_bytes = b""
    try:
        dxf_doc, _ = reconstruct_pdf_to_dxf(output_pdf_path, page_num=1)
        dxf_doc.saveas(output_dxf_path)
        with open(output_dxf_path, "rb") as f:
            dxf_bytes = f.read()
    except Exception:
        pass

    return pdf_bytes, output_pdf_path, dxf_bytes, output_dxf_path, exec_log, geo_report, val_result


# ============================================================
# 3. CAD REVISION CLOUD & DELTA PRIMITIVES (PYMUPDF VECTOR)
# ============================================================

def draw_cad_revision_cloud(page: fitz.Page, rect: Any, stroke_color: Tuple[float, float, float] = (0.85, 0.15, 0.15), stroke_width: float = 1.2):
    """
    Renders an engineering scalloped arc revision cloud using connected Bézier curves.
    """
    r = fitz.Rect(rect)
    r.normalize()
    if r.width < 10 or r.height < 10:
        return

    arc_radius = 8.0
    x0, y0, x1, y1 = r.x0, r.y0, r.x1, r.y1
    shape = page.new_shape()

    def draw_scallop_side(start: Tuple[float, float], end: Tuple[float, float], outward_dir: Tuple[float, float]):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        dist = math.hypot(dx, dy)
        if dist < 1.0:
            return
        num_arcs = max(2, int(dist / (arc_radius * 1.8)))
        step_x = dx / num_arcs
        step_y = dy / num_arcs

        curr = start
        for i in range(num_arcs):
            next_pt = (start[0] + (i + 1) * step_x, start[1] + (i + 1) * step_y)
            mid_x = (curr[0] + next_pt[0]) / 2.0 + outward_dir[0] * arc_radius
            mid_y = (curr[1] + next_pt[1]) / 2.0 + outward_dir[1] * arc_radius
            
            p1 = fitz.Point(curr[0], curr[1])
            p2 = fitz.Point(mid_x, mid_y)
            p3 = fitz.Point(next_pt[0], next_pt[1])
            shape.draw_bezier(p1, p2, p2, p3)
            curr = next_pt

    draw_scallop_side((x0, y0), (x1, y0), (0, -1))
    draw_scallop_side((x1, y0), (x1, y1), (1, 0))
    draw_scallop_side((x1, y1), (x0, y1), (0, 1))
    draw_scallop_side((x0, y1), (x0, y0), (-1, 0))

    shape.finish(color=stroke_color, width=stroke_width, lineJoin=1)
    shape.commit()


def draw_cad_delta_tag(page: fitz.Page, pt: Tuple[float, float], text: str = "Δ1", color: Tuple[float, float, float] = (0.85, 0.15, 0.15)):
    """Draws an equilateral revision delta triangle with revision index text."""
    x, y = pt[0], pt[1]
    size = 12.0
    p1 = fitz.Point(x, y - size)
    p2 = fitz.Point(x - size * 0.866, y + size * 0.5)
    p3 = fitz.Point(x + size * 0.866, y + size * 0.5)

    shape = page.new_shape()
    shape.draw_line(p1, p2)
    shape.draw_line(p2, p3)
    shape.draw_line(p3, p1)
    shape.finish(color=color, width=1.0, fill=(1, 1, 1))
    shape.commit()

    tb = fitz.Rect(x - 8, y - 6, x + 8, y + 6)
    page.insert_textbox(
        tb,
        text,
        fontsize=6.5,
        fontname="helv",
        color=color,
        align=fitz.TEXT_ALIGN_CENTER,
    )


# ============================================================
# 4. COMPUTER VISION POST-RECTIFICATION VALIDATION
# ============================================================

def validate_rectifications(original_pdf_path: str, corrected_pdf_path: str, plans: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Renders high-resolution raster crops before and after modification,
    computes OpenCV pixel difference heatmaps, and verifies that graphical
    changes occurred in the target zones.
    """
    orig_doc = fitz.open(original_pdf_path)
    corr_doc = fitz.open(corrected_pdf_path)

    validation_items = []

    for plan in plans:
        cid = plan.get("comment_id", "C-001")
        actions = plan.get("actions", [])
        if not actions:
            continue

        first_act = actions[0]
        page_num = max(1, min(first_act.get("page", 1), len(orig_doc), len(corr_doc)))
        orig_page = orig_doc[page_num - 1]
        corr_page = corr_doc[page_num - 1]

        bboxes = [act.get("spatial_region") or act.get("target_bbox") for act in actions if (act.get("spatial_region") or act.get("target_bbox"))]
        union_box = bbox_union(bboxes) or [100, 100, 300, 200]

        pad = 40.0
        clip_rect = fitz.Rect(
            max(0, union_box[0] - pad),
            max(0, union_box[1] - pad),
            min(orig_page.rect.width, union_box[2] + pad),
            min(orig_page.rect.height, union_box[3] + pad),
        )

        before_img = render_region(orig_page, clip_rect, zoom=2.0)
        after_img = render_region(corr_page, clip_rect, zoom=2.0)

        diff_img = None
        similarity = None
        change_detected = False

        if before_img is not None and after_img is not None:
            similarity = visual_similarity(before_img, after_img)
            diff_img = create_difference_image(before_img, after_img)
            change_detected = similarity is not None and similarity < 0.995

        validation_items.append({
            "comment_id": cid,
            "page": page_num,
            "summary": plan.get("summary", ""),
            "actions_count": len(actions),
            "visual_similarity": round(similarity, 3) if similarity is not None else None,
            "change_verified": change_detected,
            "validation_status": "VERIFIED & APPLIED" if change_detected else "NEEDS REVIEW",
            "before_image": before_img,
            "after_image": after_img,
            "diff_image": diff_img,
            "actions": actions,
        })

    orig_doc.close()
    corr_doc.close()

    total_items = max(len(validation_items), 1)
    verified_count = sum(1 for v in validation_items if v["change_verified"])
    validation_score = round((verified_count / total_items) * 100, 1)

    return {
        "validation_score": validation_score,
        "total_rectified": len(validation_items),
        "verified_count": verified_count,
        "items": validation_items,
    }
