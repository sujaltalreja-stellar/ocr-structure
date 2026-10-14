# ============================================================
# DULB ENGINEERING QA POC - CAD PYDANTIC ACTION SCHEMAS
# ============================================================

from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator


class CADActionType(str, Enum):
    MOVE_EQUIPMENT = "move_equipment"
    REPLACE_SYMBOL = "replace_symbol"
    UPDATE_DIMENSION = "update_dimension"
    REMOVE_CONDUIT = "remove_conduit"
    RESTORE_LABEL = "restore_label"
    CREATE_2D_DETAIL = "create_2d_detail"
    DISCONNECT_CONNECTION = "disconnect_connection"
    DRAW_REVISION_CLOUD = "draw_revision_cloud"
    ADD_DELTA_TAG = "add_delta_tag"
    REPLACE_TEXT = "replace_text"
    REDACT_REGION = "redact_region"


class EngineeringObjectType(str, Enum):
    CARD_READER = "card_reader"
    DOOR = "door"
    CONDUIT = "conduit"
    PULL_BOX = "pull_box"
    DIMENSION = "dimension"
    EQUIPMENT = "equipment"
    ELEVATION_TAG = "elevation_tag"
    LEGEND = "legend"
    TABLE = "table"
    SPACE_ID = "space_id"
    DIRECTION_ARROW = "direction_arrow"
    ANNOTATION = "annotation"
    GENERAL = "general"


class SelectiveActionType(str, Enum):
    REPLACE_SYMBOL = "replace_symbol"
    MOVE_EQUIPMENT = "move_equipment"
    REMOVE_CONDUIT = "remove_conduit"
    UPDATE_DIMENSION = "update_dimension"
    UPDATE_ELEVATION = "update_elevation"
    RESTORE_SPACE_ID = "restore_space_id"
    REGENERATE_TABLE_OR_LEGEND = "regenerate_table_or_legend"
    ADD_ANNOTATION = "add_annotation"
    MODIFY_GEOMETRY = "modify_geometry"


class EngineeringDrawingObject(BaseModel):
    """
    Structured model representing an engineering entity mapped from PDF vectors and text.
    """
    object_id: str = Field(..., description="Unique entity identifier (e.g. OBJ-CR-001, OBJ-DOOR-002)")
    object_type: EngineeringObjectType = Field(..., description="Classification of the engineering entity")
    page: int = Field(default=1, ge=1)
    bbox: List[float] = Field(..., description="Bounding box [x0, y0, x1, y1] in PDF points")
    center: List[float] = Field(..., description="Center coordinates [cx, cy]")
    width: float = Field(default=0.0)
    height: float = Field(default=0.0)
    tag: Optional[str] = Field(default=None, description="Primary technical tag (e.g. 'CR', 'D-01', 'PB', 'H=1200mm')")
    elevation: Optional[str] = Field(default=None, description="Mounting height/elevation if detected (e.g. 'H=1200mm')")
    text_elements: List[Dict[str, Any]] = Field(default_factory=list, description="Constituent text spans with metadata")
    vector_indices: List[int] = Field(default_factory=list, description="Indices of vector drawing paths in page.get_drawings()")
    associated_labels: List[str] = Field(default_factory=list, description="Nearby or associated text labels")


class SelectiveEditCommand(BaseModel):
    """
    Validated command for executing a selective modification directly inside the PDF.
    """
    command_id: str = Field(..., description="Unique command ID (e.g. CMD-001)")
    comment_id: str = Field(..., description="Associated consultant comment ID (e.g. C-006)")
    action_type: SelectiveActionType = Field(..., description="Action to execute")
    object_type: EngineeringObjectType = Field(default=EngineeringObjectType.GENERAL)
    target_object_id: Optional[str] = Field(default=None, description="ID of target EngineeringDrawingObject")
    target_bbox: List[float] = Field(..., description="Spatial region [x0, y0, x1, y1] to modify")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action-specific parameters")
    engineering_rationale: str = Field(default="", description="Why this operation fulfills the consultant directive")
    requires_engineer_review: bool = Field(default=False, description="Flag if information was insufficient")
    missing_specs: Optional[str] = Field(default=None, description="Explanation of missing IFC specifications")


class CADEditAction(BaseModel):
    """
    Strictly validated Pydantic model for a single CAD drawing modification.
    """
    action_type: CADActionType = Field(
        ...,
        description="The type of CAD modification to execute."
    )
    object_type: str = Field(
        default="general",
        description="Engineering element type: 'equipment', 'conduit', 'door', 'dimension', 'label', 'wall', etc."
    )
    target_id: Optional[str] = Field(
        default=None,
        description="Identifier of target entity or markup reference."
    )
    page: int = Field(
        default=1,
        ge=1,
        description="1-indexed sheet page number."
    )
    spatial_region: List[float] = Field(
        ...,
        description="Target bounding box [x0, y0, x1, y1] in drawing coordinates."
    )
    dx: float = Field(
        default=0.0,
        description="Horizontal movement displacement in drawing units (for move_equipment)."
    )
    dy: float = Field(
        default=0.0,
        description="Vertical movement displacement in drawing units (for move_equipment)."
    )
    new_symbol_type: Optional[str] = Field(
        default=None,
        description="New symbol/block name (e.g., 'DOOR_1050', 'SECURITY_CAMERA', 'ELECTRICAL_OUTLET')."
    )
    new_dimension_value: Optional[str] = Field(
        default=None,
        description="Updated nominal dimension string (e.g. '1050', '2800 mm', 'Ø50')."
    )
    new_label_text: Optional[str] = Field(
        default=None,
        description="Updated or restored annotation/callout text."
    )
    conduit_disconnect_filter: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters for identifying incorrect conduit segment to sever/reroute."
    )
    new_geometry_specs: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Specifications for new 2D vector detail (shape, points, stroke_width, layer)."
    )
    engineering_justification: str = Field(
        default="",
        description="Detailed explanation of how this CAD change resolves the consultant's markup."
    )
    requires_engineer_review: bool = Field(
        default=False,
        description="True if required dimension/coordinate was missing from references and needs engineer sign-off."
    )
    missing_reference_info: Optional[str] = Field(
        default=None,
        description="Specific information missing from IFC/drawings (e.g. 'exact panel schedule tag not specified')."
    )

    @field_validator("spatial_region")
    @classmethod
    def validate_bbox(cls, v):
        if len(v) != 4:
            raise ValueError("spatial_region must be a 4-element list [x0, y0, x1, y1]")
        return [float(x) for x in v]


class CADCorrectionPlan(BaseModel):
    """
    Complete structured plan for resolving one or more consultant comments via CAD modification.
    """
    comment_id: str = Field(..., description="Unique comment identifier (e.g. C-001)")
    summary: str = Field(..., description="High-level summary of engineering rectifications")
    revision_note: str = Field(..., description="Title block revision table note")
    actions: List[CADEditAction] = Field(default_factory=list, description="Validated atomic CAD modifications")
    engineer_review_required: bool = Field(default=False, description="Flag indicating engineer review needed")
    missing_references: List[str] = Field(default_factory=list, description="List of unverified assumptions or missing specs")


class GeometricAssertion(BaseModel):
    """
    Verification check testing a specific geometric condition after CAD editing.
    """
    assertion_type: str = Field(..., description="e.g. 'DISPLACEMENT_CONFIRMED', 'CONDUIT_SEVERED', 'DIMENSION_MATCHES', 'SCALE_PRESERVED'")
    target_id: Optional[str] = None
    passed: bool
    measured_delta: Optional[float] = None
    expected_delta: Optional[float] = None
    details: str


class GeometricVerificationReport(BaseModel):
    """
    Comprehensive verification report validating topological and geometric modifications.
    """
    total_assertions: int
    passed_assertions: int
    failed_assertions: int
    scale_preserved: bool = True
    overall_status: str  # "VERIFIED", "WARNING", "FAILED"
    assertions: List[GeometricAssertion] = Field(default_factory=list)
    engineer_review_notes: List[str] = Field(default_factory=list)
