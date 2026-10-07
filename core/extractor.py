# ============================================================
# DULB ENGINEERING QA POC - PDF DRAWING EXTRACTION
# ============================================================

import fitz
from core.utils import json_safe, normalize_text, bbox_union


def extract_text(page):
    """
    Extracts text from a PyMuPDF page at words, spans, and blocks levels
    including spatial bounding boxes and font metadata.
    """
    result = {
        "plain_text": page.get_text("text"),
        "words": [],
        "spans": [],
        "blocks": [],
    }

    words = page.get_text("words", sort=False)
    for word in words:
        if len(word) < 8:
            continue
        x0 = word[0]
        y0 = word[1]
        x1 = word[2]
        y1 = word[3]
        text = word[4]
        block_number = word[5]
        line_number = word[6]
        word_number = word[7]
        result["words"].append({
            "text": text,
            "bbox": [x0, y0, x1, y1],
            "block": block_number,
            "line": line_number,
            "word": word_number,
        })

    raw = page.get_text("dict", sort=False)
    for block_index, block in enumerate(raw.get("blocks", [])):
        if "lines" not in block:
            continue
        block_text = []
        block_bboxes = []
        for line_index, line in enumerate(block.get("lines", [])):
            direction = line.get("dir", (1.0, 0.0))
            for span_index, span in enumerate(line.get("spans", [])):
                text = span.get("text", "")
                bbox = json_safe(span.get("bbox"))
                if text:
                    block_text.append(text)
                if bbox:
                    block_bboxes.append(bbox)
                result["spans"].append({
                    "text": text,
                    "bbox": bbox,
                    "font": span.get("font"),
                    "size": span.get("size"),
                    "color": span.get("color"),
                    "flags": span.get("flags"),
                    "direction": json_safe(direction),
                    "block_index": block_index,
                    "line_index": line_index,
                    "span_index": span_index,
                })

        joined_text = normalize_text(" ".join(block_text))
        if joined_text:
            result["blocks"].append({
                "block_index": block_index,
                "text": joined_text,
                "bbox": bbox_union(block_bboxes),
            })

    return result


def extract_annotations(page):
    """Extracts native PDF annotations (comments, markups, callouts) from a page."""
    results = []
    annot = page.first_annot
    while annot:
        info = annot.info or {}
        try:
            vertices = json_safe(annot.vertices)
        except Exception:
            vertices = None
        try:
            colors = json_safe(annot.colors)
        except Exception:
            colors = None
        results.append({
            "xref": annot.xref,
            "type": json_safe(annot.type),
            "bbox": json_safe(annot.rect),
            "content": info.get("content"),
            "title": info.get("title"),
            "subject": info.get("subject"),
            "colors": colors,
            "vertices": vertices,
        })
        annot = annot.next
    return results


def extract_vectors(page):
    """Extracts CAD vector drawings (lines, rectangles, curves) from a page."""
    results = []
    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []
    for index, drawing in enumerate(drawings):
        results.append({
            "index": index,
            "bbox": json_safe(drawing.get("rect")),
            "type": drawing.get("type"),
            "color": json_safe(drawing.get("color")),
            "fill": json_safe(drawing.get("fill")),
            "width": drawing.get("width"),
            "layer": drawing.get("layer"),
        })
    return results


def extract_pdf(pdf_path, source_name=None):
    """Extracts all text, annotations, and vector elements from each page of a PDF drawing."""
    doc = fitz.open(pdf_path)
    result = {
        "source_name": source_name,
        "page_count": len(doc),
        "pages": [],
    }
    for page_number in range(len(doc)):
        page = doc[page_number]
        result["pages"].append({
            "page": page_number + 1,
            "page_rect": json_safe(page.rect),
            "rotation": page.rotation,
            "text": extract_text(page),
            "annotations": extract_annotations(page),
            "vectors": extract_vectors(page),
        })
    doc.close()
    return result
