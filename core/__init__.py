"""
Core engine modules for DULB Engineering QA.
"""

from core.utils import (
    json_safe,
    normalize_text,
    normalize_for_match,
    word_tokens,
    clamp_text,
    bbox_union,
    file_hash,
)
from core.extractor import (
    extract_text,
    extract_annotations,
    extract_vectors,
    extract_pdf,
)
from core.comments import (
    probable_comment_text,
    deduplicate_comments,
    get_comments,
)
from core.vision import (
    normalize_rect,
    denormalize_rect,
    expand_rect,
    text_from_region,
    vectors_in_region,
    render_region,
    visual_similarity,
    create_difference_image,
    compare_comment_region,
)
from core.retrieval import (
    lexical_score,
    retrieve_relevant_blocks,
    build_compact_evidence,
    clean_json_response,
)
from core.ai_client import (
    ask_llm,
    get_ollama_models,
)
from core.cad_3d import (
    extract_3d_cad_model,
    extract_3d_diff_model,
)
from core.audit import (
    generate_audit_report,
)
from core.pdf_report import (
    generate_audit_pdf,
)

__all__ = [
    "json_safe",
    "normalize_text",
    "normalize_for_match",
    "word_tokens",
    "clamp_text",
    "bbox_union",
    "file_hash",
    "extract_text",
    "extract_annotations",
    "extract_vectors",
    "extract_pdf",
    "probable_comment_text",
    "deduplicate_comments",
    "get_comments",
    "normalize_rect",
    "denormalize_rect",
    "expand_rect",
    "text_from_region",
    "vectors_in_region",
    "render_region",
    "visual_similarity",
    "create_difference_image",
    "compare_comment_region",
    "lexical_score",
    "retrieve_relevant_blocks",
    "build_compact_evidence",
    "clean_json_response",
    "ask_llm",
    "get_ollama_models",
    "extract_3d_cad_model",
    "extract_3d_diff_model",
    "generate_audit_report",
    "generate_audit_pdf",
]
