# ============================================================
# DULB ENGINEERING QA POC - RETRIEVAL & EVIDENCE PREPARATION
# ============================================================

import json
import re
from core.utils import word_tokens, normalize_for_match, clamp_text


def lexical_score(query, candidate):
    """
    Computes a domain-weighted lexical overlap score between a consultant comment
    and a candidate text block from the revised drawing.
    """
    query_tokens = set(word_tokens(query))
    candidate_tokens = set(word_tokens(candidate))
    if not query_tokens or not candidate_tokens:
        return 0.0

    overlap = len(query_tokens & candidate_tokens)
    base_score = overlap / max(1, len(query_tokens))

    query_normalized = normalize_for_match(query)
    candidate_normalized = normalize_for_match(candidate)
    bonus = 0.0

    technical_terms = [
        "conduit", "fill", "spare", "diameter", "backbox", "card reader",
        "reader", "elevation", "space id", "lock", "secure", "unsecure",
        "ifc", "legend", "door", "cable", "calculation",
    ]

    for term in technical_terms:
        if term in query_normalized and term in candidate_normalized:
            bonus += 0.05

    return base_score + bonus


def retrieve_relevant_blocks(pdf_data, query, top_k=8):
    """
    Scans the entire revised drawing to find the most relevant text blocks
    matching a consultant comment's keywords and technical terms.
    """
    candidates = []
    for page in pdf_data["pages"]:
        for block in page["text"]["blocks"]:
            text = block.get("text", "")
            score = lexical_score(query, text)
            if score <= 0:
                continue
            candidates.append({
                "page": page["page"],
                "bbox": block.get("bbox"),
                "text": text,
                "score": round(float(score), 4),
            })

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:top_k]


def build_compact_evidence(comment, comparison, retrieval):
    """
    Constructs a compact, privacy-safe evidence package for one consultant comment.
    Contains ONLY the affected region comparison and retrieved relevant blocks,
    NEVER the full drawing JSON.
    """
    retrieved_items = []
    for item in retrieval:
        retrieved_items.append({
            "page": item["page"],
            "bbox": item["bbox"],
            "relevance_score": item["score"],
            "text": clamp_text(item["text"], 1200),
        })

    compact = {
        "comment_id": comment["id"],
        "comment_source": comment["source"],
        "consultant_comment": clamp_text(comment["comment"], 2500),
        "comment_page": comment["page"],
        "comment_bbox": comment.get("bbox"),
        "same_region_evidence": {
            "old_text": clamp_text(comparison.get("old_text", ""), 1800),
            "new_text": clamp_text(comparison.get("new_text", ""), 1800),
            "old_vector_count": comparison.get("old_vectors"),
            "new_vector_count": comparison.get("new_vectors"),
            "visual_similarity": comparison.get("visual_similarity"),
        },
        "relevant_new_revision_evidence": retrieved_items,
    }
    return compact


def clean_json_response(content):
    """Strips markdown code blocks and returns parsed JSON dictionary."""
    if isinstance(content, list):
        pieces = []
        for item in content:
            if isinstance(item, str):
                pieces.append(item)
            else:
                pieces.append(getattr(item, "text", str(item)))
        content = "".join(pieces)

    content = str(content).strip()
    content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
    content = re.sub(r"\s*```$", "", content)
    return json.loads(content)
