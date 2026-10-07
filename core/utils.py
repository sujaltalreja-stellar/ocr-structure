# ============================================================
# DULB ENGINEERING QA POC - BASIC UTILITIES & HELPERS
# ============================================================

import re
import hashlib
import fitz
from config import STOPWORDS


def json_safe(value):
    """Recursively converts PyMuPDF structures and values to JSON-safe primitives."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, fitz.Rect):
        return [value.x0, value.y0, value.x1, value.y1]
    if isinstance(value, fitz.Point):
        return [value.x, value.y]
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return str(value)


def normalize_text(text):
    """Cleans up soft hyphens and normalizes whitespace."""
    if not text:
        return ""
    text = str(text)
    text = text.replace("\xad", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_for_match(text):
    """
    Normalizes text for fuzzy and lexical matching.
    Preserves alphanumeric and engineering symbols like diameter Ø/ø, %, /, +, -.
    """
    text = normalize_text(text).lower()
    text = re.sub(r"[^a-z0-9%Øø./+\- ]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def word_tokens(text):
    """Tokenizes normalized text and filters out stopwords and single/double-char tokens."""
    words = re.findall(r"[a-zA-Z0-9%Øø./+\-]+", normalize_for_match(text))
    return [word for word in words if len(word) > 2 and word not in STOPWORDS]


def clamp_text(text, max_chars=2500):
    """Limits text length to prevent exceeding token context limits."""
    text = normalize_text(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + " ...[TRUNCATED]"


def bbox_union(bboxes):
    """Calculates the enclosing bounding box of multiple bounding boxes."""
    valid = [bbox for bbox in bboxes if bbox and len(bbox) == 4]
    if not valid:
        return None
    return [
        min(bbox[0] for bbox in valid),
        min(bbox[1] for bbox in valid),
        max(bbox[2] for bbox in valid),
        max(bbox[3] for bbox in valid),
    ]


def file_hash(data):
    """Calculates MD5 hash hex digest of bytes data."""
    return hashlib.md5(data).hexdigest()
