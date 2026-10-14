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
from core.correction_engine import (
    plan_corrections_for_comment,
    apply_pdf_corrections,
    rectify_drawing_selectively,
    validate_rectifications,
    draw_cad_revision_cloud,
    draw_cad_delta_tag,
)
from core.cad_schema import (
    CADActionType,
    CADEditAction,
    CADCorrectionPlan,
    GeometricAssertion,
    GeometricVerificationReport,
    EngineeringObjectType,
    SelectiveActionType,
    EngineeringDrawingObject,
    SelectiveEditCommand,
)
from core.cad_pipeline import (
    reconstruct_pdf_to_dxf,
    execute_cad_modifications,
    export_cad_to_vector_pdf,
)
from core.dwg_converter import convert_dxf_to_dwg, get_dwg_converter_status
from core.freecad_bridge import get_freecad_status
from core.object_mapper import (
    map_vectors_to_engineering_objects,
    find_target_object_for_comment,
    extract_page_raw_elements,
)
from core.selective_engine import (
    execute_selective_command,
    clean_all_consultant_markups,
    replace_card_reader_symbol,
    move_card_reader_or_equipment,
    remove_conduit_line,
    replace_text_or_dimension,
    update_equipment_elevation,
    restore_space_ids,
    regenerate_legend_or_table,
)
from core.llm_agent import synthesize_selective_command
from core.verification import verify_selective_modifications

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
    "plan_corrections_for_comment",
    "apply_pdf_corrections",
    "rectify_drawing_selectively",
    "validate_rectifications",
    "draw_cad_revision_cloud",
    "draw_cad_delta_tag",
    "CADActionType",
    "CADEditAction",
    "CADCorrectionPlan",
    "GeometricAssertion",
    "GeometricVerificationReport",
    "EngineeringObjectType",
    "SelectiveActionType",
    "EngineeringDrawingObject",
    "SelectiveEditCommand",
    "reconstruct_pdf_to_dxf",
    "execute_cad_modifications",
    "export_cad_to_vector_pdf",
    "convert_dxf_to_dwg",
    "get_dwg_converter_status",
    "get_freecad_status",
    "map_vectors_to_engineering_objects",
    "find_target_object_for_comment",
    "extract_page_raw_elements",
    "execute_selective_command",
    "clean_all_consultant_markups",
    "replace_card_reader_symbol",
    "move_card_reader_or_equipment",
    "remove_conduit_line",
    "replace_text_or_dimension",
    "update_equipment_elevation",
    "restore_space_ids",
    "regenerate_legend_or_table",
    "synthesize_selective_command",
    "verify_selective_modifications",
]
