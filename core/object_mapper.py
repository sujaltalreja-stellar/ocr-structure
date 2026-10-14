# ============================================================
# DULB ENGINEERING QA POC - VECTOR-TO-ENGINEERING OBJECT MAPPER
# ============================================================

import re
import math
import fitz
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from shapely.geometry import box, Point, LineString, Polygon
from shapely.strtree import STRtree
import skimage.measure

from core.cad_schema import (
    EngineeringObjectType,
    EngineeringDrawingObject,
)


def extract_page_raw_elements(page: fitz.Page) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extracts all vector paths and text spans from a PyMuPDF page,
    preserving exact coordinates, line styles, and font metadata.
    """
    # 1. Vector drawings
    drawings = []
    try:
        raw_drawings = page.get_drawings()
    except Exception:
        raw_drawings = []

    for idx, d in enumerate(raw_drawings):
        r = d.get("rect")
        if not r:
            continue
        rect_list = [float(r.x0), float(r.y0), float(r.x1), float(r.y1)]
        w = max(0.0, rect_list[2] - rect_list[0])
        h = max(0.0, rect_list[3] - rect_list[1])
        if w < 0.2 and h < 0.2:
            continue

        drawings.append({
            "index": len(drawings),
            "raw_index": idx,
            "bbox": rect_list,
            "type": d.get("type", "s"),
            "items": d.get("items", []),
            "color": d.get("color"),
            "fill": d.get("fill"),
            "width": float(d.get("width") or 1.0),
            "line_count": sum(1 for item in d.get("items", []) if item[0] in ["l", "c", "re"]),
        })

    # 2. Text spans
    spans = []
    raw_dict = page.get_text("dict")
    for block in raw_dict.get("blocks", []):
        if "lines" not in block:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                t = span.get("text", "").strip()
                if not t:
                    continue
                bbox = [float(x) for x in span.get("bbox", [0, 0, 0, 0])]
                spans.append({
                    "text": t,
                    "bbox": bbox,
                    "size": float(span.get("size", 8.0)),
                    "font": span.get("font", "helv"),
                    "color": span.get("color", 0),
                    "origin": [float(x) for x in span.get("origin", [bbox[0], bbox[3]])],
                })

    return drawings, spans


def map_vectors_to_engineering_objects(page: fitz.Page) -> List[EngineeringDrawingObject]:
    """
    Groups raw PDF vector paths and text spans into semantic engineering objects:
    Card Readers, Doors, Conduits, Pull Boxes, Dimensions, Elevation Tags, Legends, and Tables.
    Maintains original coordinates and references to constituent paths and text spans.
    """
    drawings, spans = extract_page_raw_elements(page)
    objects: List[EngineeringDrawingObject] = []
    obj_counter = 1

    # ---------------------------------------------------------
    # 1. DETECT CARD READERS & EQUIPMENT SYMBOLS
    # ---------------------------------------------------------
    # Pattern: Small square/box (8x8 to 40x40 pt) or text containing 'CR', 'READER', 'BIO',
    # often with nearby elevation 'H=1200mm' or near doors/walls.
    used_span_indices = set()
    used_drawing_indices = set()

    # Find candidate card reader spans
    for s_idx, s in enumerate(spans):
        text_upper = s["text"].upper()
        is_reader_text = any(k in text_upper for k in ["CR", "READER", "CARD", "BIO", "PIR"])
        if is_reader_text and len(s["text"]) <= 25:
            sb = s["bbox"]
            search_box = [sb[0] - 35, sb[1] - 35, sb[2] + 35, sb[3] + 35]
            matched_drawings = []
            for d in drawings:
                db = d["bbox"]
                dw = db[2] - db[0]
                dh = db[3] - db[1]
                # Small device symbol
                if dw <= 45 and dh <= 45:
                    if not (db[2] < search_box[0] or db[0] > search_box[2] or db[3] < search_box[1] or db[1] > search_box[3]):
                        matched_drawings.append(d["index"])
                        used_drawing_indices.add(d["index"])

            # Find nearby elevation tag (e.g. H=1200mm)
            elev_str = None
            nearby_labels = [s["text"]]
            for o_idx, o_span in enumerate(spans):
                if o_idx != s_idx:
                    ot = o_span["text"]
                    if re.search(r"H\s*=\s*\d+", ot) or "AFF" in ot:
                        ob = o_span["bbox"]
                        if math.hypot(ob[0] - sb[0], ob[1] - sb[1]) < 70:
                            elev_str = ot
                            nearby_labels.append(ot)
                            used_span_indices.add(o_idx)

            used_span_indices.add(s_idx)
            matched_boxes = [drawings[i]["bbox"] for i in matched_drawings if 0 <= i < len(drawings)]
            if matched_boxes:
                union_b = [
                    min(sb[0], min(b[0] for b in matched_boxes)),
                    min(sb[1], min(b[1] for b in matched_boxes)),
                    max(sb[2], max(b[2] for b in matched_boxes)),
                    max(sb[3], max(b[3] for b in matched_boxes)),
                ]
            else:
                union_b = list(sb)
            cx = (union_b[0] + union_b[2]) / 2.0
            cy = (union_b[1] + union_b[3]) / 2.0

            objects.append(EngineeringDrawingObject(
                object_id=f"OBJ-CR-{obj_counter:04d}",
                object_type=EngineeringObjectType.CARD_READER,
                page=1,
                bbox=union_b,
                center=[cx, cy],
                width=union_b[2] - union_b[0],
                height=union_b[3] - union_b[1],
                tag=s["text"],
                elevation=elev_str,
                text_elements=[s],
                vector_indices=matched_drawings,
                associated_labels=nearby_labels,
            ))
            obj_counter += 1

    # Also detect Card Reader symbols represented purely as vector blocks with H=1200mm nearby
    for s_idx, s in enumerate(spans):
        if s_idx in used_span_indices:
            continue
        ot = s["text"]
        if re.search(r"H\s*=\s*1200", ot):
            sb = s["bbox"]
            search_box = [sb[0] - 45, sb[1] - 45, sb[2] + 45, sb[3] + 45]
            matched_drawings = []
            for d in drawings:
                if d["index"] in used_drawing_indices:
                    continue
                db = d["bbox"]
                dw = db[2] - db[0]
                dh = db[3] - db[1]
                if 4.0 <= dw <= 40.0 and 4.0 <= dh <= 40.0:
                    if not (db[2] < search_box[0] or db[0] > search_box[2] or db[3] < search_box[1] or db[1] > search_box[3]):
                        matched_drawings.append(d["index"])
                        used_drawing_indices.add(d["index"])

            if matched_drawings:
                used_span_indices.add(s_idx)
                matched_boxes = [drawings[i]["bbox"] for i in matched_drawings if 0 <= i < len(drawings)]
                if matched_boxes:
                    union_b = [
                        min(sb[0], min(b[0] for b in matched_boxes)),
                        min(sb[1], min(b[1] for b in matched_boxes)),
                        max(sb[2], max(b[2] for b in matched_boxes)),
                        max(sb[3], max(b[3] for b in matched_boxes)),
                    ]
                else:
                    union_b = list(sb)
                cx = (union_b[0] + union_b[2]) / 2.0
                cy = (union_b[1] + union_b[3]) / 2.0

                objects.append(EngineeringDrawingObject(
                    object_id=f"OBJ-CR-{obj_counter:04d}",
                    object_type=EngineeringObjectType.CARD_READER,
                    page=1,
                    bbox=union_b,
                    center=[cx, cy],
                    width=union_b[2] - union_b[0],
                    height=union_b[3] - union_b[1],
                    tag="CARD READER",
                    elevation=ot,
                    text_elements=[s],
                    vector_indices=matched_drawings,
                    associated_labels=[ot],
                ))
                obj_counter += 1

    # ---------------------------------------------------------
    # 2. DETECT PULL BOXES (PB / JB)
    # ---------------------------------------------------------
    for s_idx, s in enumerate(spans):
        if s_idx in used_span_indices:
            continue
        if s["text"].strip() in ["PB", "JB"]:
            sb = s["bbox"]
            used_span_indices.add(s_idx)
            pb_box = [sb[0] - 8, sb[1] - 8, sb[2] + 8, sb[3] + 8]
            cx = (pb_box[0] + pb_box[2]) / 2.0
            cy = (pb_box[1] + pb_box[3]) / 2.0

            objects.append(EngineeringDrawingObject(
                object_id=f"OBJ-PB-{obj_counter:04d}",
                object_type=EngineeringObjectType.PULL_BOX,
                page=1,
                bbox=pb_box,
                center=[cx, cy],
                width=pb_box[2] - pb_box[0],
                height=pb_box[3] - pb_box[1],
                tag=s["text"].strip(),
                text_elements=[s],
                vector_indices=[],
                associated_labels=[s["text"]],
            ))
            obj_counter += 1

    # ---------------------------------------------------------
    # 3. DETECT DOORS & OPENINGS
    # ---------------------------------------------------------
    for s_idx, s in enumerate(spans):
        if s_idx in used_span_indices:
            continue
        t = s["text"].strip()
        # Door tags: e.g. SL-08, MUS-SL-08, D-01, D1050
        if re.match(r"^(?:MUS-)?(?:SL|D)[-\s]?\d+$", t):
            sb = s["bbox"]
            used_span_indices.add(s_idx)
            door_box = [sb[0] - 40, sb[1] - 40, sb[2] + 40, sb[3] + 40]
            cx = (door_box[0] + door_box[2]) / 2.0
            cy = (door_box[1] + door_box[3]) / 2.0

            objects.append(EngineeringDrawingObject(
                object_id=f"OBJ-DOOR-{obj_counter:04d}",
                object_type=EngineeringObjectType.DOOR,
                page=1,
                bbox=door_box,
                center=[cx, cy],
                width=door_box[2] - door_box[0],
                height=door_box[3] - door_box[1],
                tag=t,
                text_elements=[s],
                vector_indices=[],
                associated_labels=[t],
            ))
            obj_counter += 1

    # ---------------------------------------------------------
    # 4. DETECT DIMENSIONS
    # ---------------------------------------------------------
    for s_idx, s in enumerate(spans):
        if s_idx in used_span_indices:
            continue
        t = s["text"].strip()
        if re.match(r"^\d{2,5}(?:\.\d+)?\s*(?:mm|m)?$", t) and float(re.findall(r"\d+", t)[0]) >= 50:
            sb = s["bbox"]
            used_span_indices.add(s_idx)
            cx = (sb[0] + sb[2]) / 2.0
            cy = (sb[1] + sb[3]) / 2.0

            objects.append(EngineeringDrawingObject(
                object_id=f"OBJ-DIM-{obj_counter:04d}",
                object_type=EngineeringObjectType.DIMENSION,
                page=1,
                bbox=sb,
                center=[cx, cy],
                width=sb[2] - sb[0],
                height=sb[3] - sb[1],
                tag=t,
                text_elements=[s],
                vector_indices=[],
                associated_labels=[t],
            ))
            obj_counter += 1

    # ---------------------------------------------------------
    # 5. DETECT DIRECTION ARROW / SECURE-UNSECURE LEGEND
    # ---------------------------------------------------------
    for s_idx, s in enumerate(spans):
        t_upper = s["text"].upper()
        if "SECURE SIDE" in t_upper or "UNSECURE" in t_upper:
            sb = s["bbox"]
            arr_box = [sb[0] - 60, sb[1] - 40, sb[2] + 60, sb[3] + 40]
            cx = (arr_box[0] + arr_box[2]) / 2.0
            cy = (arr_box[1] + arr_box[3]) / 2.0

            # Find connected conduit lines running to this arrow
            conduit_vecs = []
            for d in drawings:
                db = d["bbox"]
                dw = db[2] - db[0]
                dh = db[3] - db[1]
                # Linear line
                if (dw > 25 and dh < 5) or (dh > 25 and dw < 5):
                    if not (db[2] < arr_box[0] or db[0] > arr_box[2] or db[3] < arr_box[1] or db[1] > arr_box[3]):
                        conduit_vecs.append(d["index"])

            objects.append(EngineeringDrawingObject(
                object_id=f"OBJ-DIR-ARROW-{obj_counter:04d}",
                object_type=EngineeringObjectType.DIRECTION_ARROW,
                page=1,
                bbox=arr_box,
                center=[cx, cy],
                width=arr_box[2] - arr_box[0],
                height=arr_box[3] - arr_box[1],
                tag=s["text"],
                text_elements=[s],
                vector_indices=conduit_vecs,
                associated_labels=[s["text"]],
            ))
            obj_counter += 1

    # ---------------------------------------------------------
    # 6. DETECT LEGENDS & TABLE BLOCKS
    # ---------------------------------------------------------
    for s_idx, s in enumerate(spans):
        t_upper = s["text"].upper()
        if "CARD + PIN READER" in t_upper or ("LEGEND" in t_upper and len(s["text"]) < 20):
            sb = s["bbox"]
            leg_box = [sb[0] - 20, sb[1] - 15, sb[2] + 120, sb[3] + 15]
            cx = (leg_box[0] + leg_box[2]) / 2.0
            cy = (leg_box[1] + leg_box[3]) / 2.0

            objects.append(EngineeringDrawingObject(
                object_id=f"OBJ-LEGEND-{obj_counter:04d}",
                object_type=EngineeringObjectType.LEGEND,
                page=1,
                bbox=leg_box,
                center=[cx, cy],
                width=leg_box[2] - leg_box[0],
                height=leg_box[3] - leg_box[1],
                tag=s["text"],
                text_elements=[s],
                vector_indices=[],
                associated_labels=[s["text"]],
            ))
            obj_counter += 1

    # ---------------------------------------------------------
    # 7. DETECT SPACE / ROOM IDS
    # ---------------------------------------------------------
    for s_idx, s in enumerate(spans):
        t = s["text"].strip()
        if re.search(r"\bM\.B1\.\d+\b", t) or any(k in t.upper() for k in ["LOBBY", "STAIR", "VENT SHAFT", "WORKSHOP"]):
            sb = s["bbox"]
            cx = (sb[0] + sb[2]) / 2.0
            cy = (sb[1] + sb[3]) / 2.0

            objects.append(EngineeringDrawingObject(
                object_id=f"OBJ-SPACE-{obj_counter:04d}",
                object_type=EngineeringObjectType.SPACE_ID,
                page=1,
                bbox=sb,
                center=[cx, cy],
                width=sb[2] - sb[0],
                height=sb[3] - sb[1],
                tag=t,
                text_elements=[s],
                vector_indices=[],
                associated_labels=[t],
            ))
            obj_counter += 1

    return objects


def find_target_object_for_comment(
    comment: Dict[str, Any],
    objects: List[EngineeringDrawingObject],
    page: fitz.Page,
) -> Optional[EngineeringDrawingObject]:
    """
    Identifies the exact target engineering object for a consultant comment
    using leader arrow tips, annotation callout vertices, keyword semantics,
    and Shapely Euclidean spatial distance.
    """
    comment_text = comment.get("comment", "").lower()
    comment_bbox = comment.get("bbox") or [100, 100, 200, 200]

    # 1. Check for native annotation leader arrow tip
    arrow_tip: Optional[Tuple[float, float]] = None
    try:
        annot = page.first_annot
        cid = comment.get("id", "")
        while annot:
            info = annot.info or {}
            c_text = info.get("content") or ""
            # Match comment content
            if c_text and (c_text[:35] in comment.get("comment", "") or comment.get("comment", "")[:35] in c_text):
                try:
                    verts = annot.vertices
                    if verts and len(verts) >= 1:
                        # First vertex of leader line is typically the arrow tip pointing at the drawing element
                        arrow_tip = (float(verts[0][0]), float(verts[0][1]))
                        break
                except Exception:
                    pass
            annot = annot.next
    except Exception:
        arrow_tip = None

    # Reference point for spatial matching
    ref_pt = Point(arrow_tip[0], arrow_tip[1]) if arrow_tip else Point((comment_bbox[0] + comment_bbox[2]) / 2.0, (comment_bbox[1] + comment_bbox[3]) / 2.0)

    # 2. Determine target object type priority from comment keywords
    target_type = None
    if "card reader" in comment_text or "reader" in comment_text:
        target_type = EngineeringObjectType.LEGEND if "legend" in comment_text else EngineeringObjectType.CARD_READER
    elif "conduit" in comment_text or "wire" in comment_text:
        target_type = EngineeringObjectType.DIRECTION_ARROW if "direction" in comment_text or "legend" in comment_text else EngineeringObjectType.CONDUIT
    elif "space id" in comment_text or "room" in comment_text:
        target_type = EngineeringObjectType.SPACE_ID
    elif "door" in comment_text or "lock" in comment_text:
        target_type = EngineeringObjectType.DOOR
    elif "elevation" in comment_text:
        target_type = EngineeringObjectType.ELEVATION_TAG
    elif "dimension" in comment_text or "width" in comment_text or "mm" in comment_text:
        target_type = EngineeringObjectType.DIMENSION

    # 3. Filter candidate objects
    candidates = [obj for obj in objects if obj.object_type == target_type] if target_type else objects
    if not candidates:
        candidates = objects

    if not candidates:
        return None

    # 4. Find closest object to reference point using Shapely distance
    best_obj = None
    min_dist = float("inf")

    for obj in candidates:
        obj_geom = box(obj.bbox[0], obj.bbox[1], obj.bbox[2], obj.bbox[3])
        dist = ref_pt.distance(obj_geom)
        if dist < min_dist:
            min_dist = dist
            best_obj = obj

    # If the closest object is too far (> 180pt) or no candidate matched, anchor directly to arrow_tip
    if arrow_tip and (best_obj is None or min_dist > 180.0):
        tip_x, tip_y = arrow_tip[0], arrow_tip[1]
        cid = comment.get("id", "C-001")
        return EngineeringDrawingObject(
            object_id=f"OBJ-TIP-{cid}",
            object_type=target_type or EngineeringObjectType.GENERAL,
            page=comment.get("page", 1),
            bbox=[tip_x - 15.0, tip_y - 15.0, tip_x + 15.0, tip_y + 15.0],
            center=[tip_x, tip_y],
            width=30.0,
            height=30.0,
            associated_labels=[comment_text[:40]],
        )

    return best_obj
