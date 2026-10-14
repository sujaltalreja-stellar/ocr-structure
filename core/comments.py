# ============================================================
# DULB ENGINEERING QA POC - CONSULTANT COMMENT PROCESSING
# ============================================================

import re
from difflib import SequenceMatcher
from config import COMMENT_PHRASES
from core.utils import normalize_text, normalize_for_match


def probable_comment_text(text):
    """
    Heuristic detector for consultant markup comments in drawing text.
    Detects consultant phrasing or engineering action directives.
    """
    normalized = normalize_for_match(text)
    if len(normalized) < 20:
        return False
    phrase_match = any(phrase in normalized for phrase in COMMENT_PHRASES)
    action_match = bool(
        re.search(
            r"\b(rectify|restore|provide|include|indicate|show|reflect|keep|remove|revise|correct)\b",
            normalized,
        )
    )
    return phrase_match or action_match


def deduplicate_comments(comments, threshold=0.9):
    """
    Deduplicates overlapping consultant comments (e.g. annotation vs text block)
    using string similarity comparison. Assigns unique comment IDs (C-001, C-002, ...).
    """
    result = []
    for comment in comments:
        normalized = normalize_for_match(comment["comment"])
        if not normalized:
            continue
        duplicate_found = False
        for existing in result:
            if comment["page"] != existing["page"]:
                continue
            similarity = SequenceMatcher(
                None, normalized, normalize_for_match(existing["comment"])
            ).ratio()
            if similarity >= threshold:
                duplicate_found = True
                if (
                    comment["source"] == "annotation"
                    and existing["source"] != "annotation"
                ):
                    existing.update(comment)
                break
        if not duplicate_found:
            result.append(comment)

    for index, comment in enumerate(result, start=1):
        comment["id"] = f"C-{index:03d}"
    return result


def get_comments(pdf_data):
    """
    Extracts all consultant comments from both native annotations
    and detected native text blocks across all pages.
    """
    comments = []
    for page in pdf_data["pages"]:
        page_number = page["page"]
        for annotation in page["annotations"]:
            content = normalize_text(annotation.get("content") or "")
            if not content:
                continue
            verts = annotation.get("vertices")
            tip = [float(verts[0][0]), float(verts[0][1])] if (verts and len(verts) > 0) else None
            comments.append({
                "id": None,
                "page": page_number,
                "comment": content,
                "subject": annotation.get("subject"),
                "title": annotation.get("title"),
                "bbox": annotation.get("bbox"),
                "vertices": verts,
                "arrow_tip": tip,
                "source": "annotation",
            })
        for block in page["text"]["blocks"]:
            block_text = normalize_text(block.get("text", ""))
            if probable_comment_text(block_text):
                comments.append({
                    "id": None,
                    "page": page_number,
                    "comment": block_text,
                    "subject": None,
                    "title": None,
                    "bbox": block.get("bbox"),
                    "source": "native_text_block",
                })

    comments = deduplicate_comments(comments)
    return comments
