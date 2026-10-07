# ============================================================
# DULB ENGINEERING QA POC - ADVANCED 3D CAD GEOMETRY ENGINE
# ============================================================

import fitz
import numpy as np


def extract_3d_cad_model(pdf_path, page_num=1, comments=None, wall_height=3.0):
    """
    Parses CAD linework, wall boundaries, service conduits, columns,
    and markup pins from an engineering PDF drawing and projects them
    into rich 3D BIM-like entities.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return None

    if page_num < 1 or page_num > len(doc):
        page_num = 1

    page = doc[page_num - 1]
    page_rect = page.rect
    pw = max(float(page_rect.width), 10.0)
    ph = max(float(page_rect.height), 10.0)

    # Architectural 3D plane scale (target ~50 meters footprint)
    target_span = 50.0
    scale = target_span / max(pw, ph)
    cx = pw / 2.0
    cy = ph / 2.0

    model = {
        "dimensions": {
            "width": round(pw * scale, 2),
            "depth": round(ph * scale, 2),
            "wall_height": float(wall_height),
        },
        "walls": [],
        "columns": [],
        "lines": [],
        "conduits": [],
        "pins": [],
        "labels": [],
    }

    def to_3d(x, y):
        return round((x - cx) * scale, 3), round((y - cy) * scale, 3)

    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []

    wall_candidates = []
    column_candidates = []
    line_candidates = []
    conduit_candidates = []

    for d in drawings:
        rect = d.get("rect")
        if not rect:
            continue

        width = d.get("width") or 1.0
        color = d.get("color")
        fill = d.get("fill")
        layer = d.get("layer") or "A-WALL"
        items = d.get("items", [])

        # Layer & Color classification
        hex_color = "#94a3b8"
        is_colored = False
        conduit_type = "electrical"
        if color and len(color) >= 3:
            r, g, b = int(color[0] * 255), int(color[1] * 255), int(color[2] * 255)
            # Detect MEP colored layers (blue/cyan for telecom/security, orange/red for power/fire)
            if b > r + 30 and b > g + 30:
                is_colored = True
                hex_color = "#0ea5e9"  # Cyan/blue telecom/security
                conduit_type = "telecom"
            elif r > g + 40 and r > b + 40:
                is_colored = True
                hex_color = "#f97316"  # Orange/amber power/tray
                conduit_type = "power"
            elif g > r + 30 and g > b + 30:
                is_colored = True
                hex_color = "#10b981"  # Green HVAC/control
                conduit_type = "hvac"

        for item in items:
            cmd = item[0]

            # 1. Rectangles: Extruded Walls, Columns, Equipment pads
            if cmd == "re":
                r_rect = item[1]
                rw = abs(r_rect.x1 - r_rect.x0)
                rh = abs(r_rect.y1 - r_rect.y0)
                if rw < 1.0 or rh < 1.0:
                    continue

                rx, rz = to_3d((r_rect.x0 + r_rect.x1) / 2.0, (r_rect.y0 + r_rect.y1) / 2.0)
                sw = max(round(rw * scale, 3), 0.15)
                sd = max(round(rh * scale, 3), 0.15)

                # Column check: square-like compact block
                if sw < 1.8 and sd < 1.8 and (0.7 < sw / max(sd, 0.01) < 1.4):
                    column_candidates.append({
                        "x": rx,
                        "z": rz,
                        "w": sw,
                        "d": sd,
                        "h": wall_height + 0.2,
                        "color": "#64748b",
                        "layer": layer,
                        "category": "Structural Column",
                    })
                # Solid wall or elongated geometry
                elif fill is not None or width >= 1.2 or (rw / max(rh, 0.1) > 2.0) or (rh / max(rw, 0.1) > 2.0):
                    wall_candidates.append({
                        "x": rx,
                        "z": rz,
                        "w": sw,
                        "d": sd,
                        "h": wall_height,
                        "color": "#e2e8f0" if fill is None else "#cbd5e1",
                        "layer": layer,
                        "category": "Architectural Wall",
                    })
                else:
                    line_candidates.append({
                        "x1": round(rx - sw / 2, 3), "z1": round(rz - sd / 2, 3),
                        "x2": round(rx + sw / 2, 3), "z2": round(rz + sd / 2, 3),
                        "color": hex_color, "elev": 0.04,
                        "layer": layer,
                    })

            # 2. Straight lines
            elif cmd == "l":
                p1 = item[1]
                p2 = item[2]
                x1, z1 = to_3d(p1.x, p1.y)
                x2, z2 = to_3d(p2.x, p2.y)
                length = np.hypot(x2 - x1, z2 - z1)
                if length < 0.12:
                    continue

                if is_colored or width >= 2.0:
                    # Raised 3D Conduit / Cable Tray at ceiling height
                    conduit_candidates.append({
                        "x1": x1, "z1": z1,
                        "x2": x2, "z2": z2,
                        "elev": 2.65,
                        "color": hex_color,
                        "radius": 0.12 if width >= 3.0 else 0.07,
                        "conduit_type": conduit_type,
                        "category": "MEP Cable Tray / Conduit",
                    })
                elif width >= 1.4:
                    # Thick CAD line -> Extrude as wall partition
                    angle = np.arctan2(z2 - z1, x2 - x1)
                    mx = (x1 + x2) / 2.0
                    mz = (z1 + z2) / 2.0
                    wall_candidates.append({
                        "x": round(mx, 3),
                        "z": round(mz, 3),
                        "w": round(length, 3),
                        "d": 0.22,
                        "h": wall_height,
                        "rotation": round(angle, 3),
                        "color": "#cbd5e1",
                        "layer": layer,
                        "category": "Partition Wall",
                    })
                else:
                    line_candidates.append({
                        "x1": x1, "z1": z1,
                        "x2": x2, "z2": z2,
                        "elev": 0.04,
                        "color": hex_color,
                        "layer": layer,
                    })

            # 3. Cubic Curves (door swings, curved ducting)
            elif cmd == "c":
                p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
                # Sample 4 points along curve
                t_vals = [0.0, 0.33, 0.66, 1.0]
                pts = []
                for t in t_vals:
                    omt = 1.0 - t
                    px = omt**3 * p1.x + 3 * omt**2 * t * p2.x + 3 * omt * t**2 * p3.x + t**3 * p4.x
                    py = omt**3 * p1.y + 3 * omt**2 * t * p2.y + 3 * omt * t**2 * p3.y + t**3 * p4.y
                    pts.append(to_3d(px, py))

                for i in range(len(pts) - 1):
                    line_candidates.append({
                        "x1": pts[i][0], "z1": pts[i][1],
                        "x2": pts[i+1][0], "z2": pts[i+1][1],
                        "elev": 0.04,
                        "color": "#94a3b8",
                        "layer": "DOOR-SWING",
                    })

    model["walls"] = wall_candidates[:900]
    model["columns"] = column_candidates[:300]
    model["lines"] = line_candidates[:1800]
    model["conduits"] = conduit_candidates[:500]

    # Consultant Comment 3D Pins with spatial metadata
    if comments:
        for c in comments:
            if c.get("page") != page_num:
                continue
            bbox = c.get("bbox")
            if bbox and len(bbox) == 4:
                cx_c = (bbox[0] + bbox[2]) / 2.0
                cy_c = (bbox[1] + bbox[3]) / 2.0
            else:
                cx_c, cy_c = cx, cy

            px, pz = to_3d(cx_c, cy_c)
            model["pins"].append({
                "id": c.get("id") or "PIN",
                "x": px,
                "z": pz,
                "elev": wall_height + 0.6,
                "comment": (c.get("comment") or "")[:120],
                "source": c.get("source", "annotation"),
            })

    # Prominent Room Labels / Space IDs
    try:
        words = page.get_text("words")
        for w in words[:120]:
            text_str = str(w[4]).strip()
            # Catch room tags, elevations, card readers, door tags
            if len(w) >= 5 and (len(text_str) >= 3) and (any(ch.isdigit() for ch in text_str) or text_str.isupper()):
                lx, lz = to_3d((w[0] + w[2]) / 2.0, (w[1] + w[3]) / 2.0)
                model["labels"].append({
                    "x": lx,
                    "z": lz,
                    "text": text_str,
                })
    except Exception:
        pass

    doc.close()
    return model


def extract_3d_diff_model(old_pdf_path, new_pdf_path, page_num=1, comments=None, wall_height=3.0):
    """
    Computes a 3D Revision Diff Overlay between Old and New drawings:
    - Neutral Gray: Unchanged geometry
    - Ghost Red: Removed/Old geometry
    - Vibrant Emerald Green: Added/Revised geometry in New Revision
    """
    old_model = extract_3d_cad_model(old_pdf_path, page_num=page_num, comments=comments, wall_height=wall_height)
    new_model = extract_3d_cad_model(new_pdf_path, page_num=page_num, comments=comments, wall_height=wall_height)

    if not old_model or not new_model:
        return new_model or old_model

    diff_walls = []
    # Identify unchanged vs added in new_model
    old_centers = {(round(w["x"], 1), round(w["z"], 1)) for w in old_model.get("walls", [])}

    for w in new_model.get("walls", []):
        key = (round(w["x"], 1), round(w["z"], 1))
        if key in old_centers:
            # Unchanged
            w_diff = dict(w)
            w_diff["color"] = "#cbd5e1"
            w_diff["diff_status"] = "unchanged"
            diff_walls.append(w_diff)
        else:
            # Added / Modified in New Revision -> Highlight Green
            w_diff = dict(w)
            w_diff["color"] = "#10b981"
            w_diff["diff_status"] = "added"
            diff_walls.append(w_diff)

    # Removed elements from Old -> Highlight Red
    new_centers = {(round(w["x"], 1), round(w["z"], 1)) for w in new_model.get("walls", [])}
    for w in old_model.get("walls", []):
        key = (round(w["x"], 1), round(w["z"], 1))
        if key not in new_centers:
            w_diff = dict(w)
            w_diff["color"] = "#ef4444"
            w_diff["diff_status"] = "removed"
            diff_walls.append(w_diff)

    combined_model = dict(new_model)
    combined_model["walls"] = diff_walls[:1100]
    combined_model["is_diff"] = True
    return combined_model
