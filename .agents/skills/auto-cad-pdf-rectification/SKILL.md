---
name: auto-cad-pdf-rectification
description: Autonomous 2D CAD engineering drawing rectification engine that performs direct in-place selective vector and text modifications inside the original engineering PDF (Card Readers, Conduits, Dimensions, Equipment, Legends, Space IDs), maps vector geometry to semantic engineering objects via scikit-image and Shapely, connects AI tools via Pydantic AI, wipes consultant markups, and exports clean updated vector PDFs and editable DXF drawings with dual OpenCV diff and geometric invariance verification.
---

# Autonomous 2D CAD Engineering Drawing Rectification Engine

## 1. Overview & Objective
This engine provides **actual AI-driven 2D engineering drawing modification** directly within the original vector PDF. It fulfills the core requirement: **The client uploads ONE engineering PDF containing consultant comments, and the system understands the comments, identifies the exact affected drawing elements, modifies them in-place, and generates ONE clean, updated 2D vector engineering drawing**.

### Core Tenets:
1. **Preserves 100% of Unaffected Linework & Fonts**: Does not regenerate the whole sheet from scratch or blindly vectorize into generic DXF. Preserves drawing scale, title blocks, and unchanged engineering layers.
2. **Surgical In-Place Modification**: Modifies only the specific elements targeted by consultant comments (Card Readers, Conduits, Dimensions, Elevation Tags, Legends, Space IDs).
3. **No Dummy Redaction Blocks or Labels**: Wipes consultant sticky notes, callouts, and leader arrows completely. Does not stamp dummy blue/red labels (e.g. `"RECTIFIED PER C-001"`) or forced revision clouds.
4. **Authentic 2D Linework**: Replaces symbols with IFC-compliant vector symbols, draws clean conduit drop lines, updates nominal dimensions in CAD black font, and restores space IDs.
5. **Dual Verification**: OpenCV alteration heatmaps + geometric assertions confirming target elements changed while unaffected geometry remains 100% invariant.

---

## 2. Technology Stack & Framework Matrix

| Technology | Role & Integration |
| :--- | :--- |
| **`PyMuPDF` (`fitz` >= 1.24.0)** | Direct vector PDF surgery: tight glyph/path-level redaction, native text baseline insertion, precision vector shape drawing (`draw_rect`, `draw_line`, `draw_bezier`), and annotation stripping. |
| **`scikit-image` & `NumPy`** | Geometric shape clustering and object segmentation: groups vector drawing elements and text spans into semantic CAD objects. |
| **`Shapely` (>= 2.0.0)** | 2D Spatial topology & geometric analysis: builds `STRtree` spatial indices, computes Euclidean distances from consultant leader arrow tips (`annot.vertices[0]`), and proves unaffected scale invariance. |
| **`svgpathtools` (>= 1.8.0)** | High-precision vector path manipulation for curves, door arcs, and MEP conduit linework. |
| **`ezdxf` (>= 1.3.0)** | Reconstructs PDF vector geometry into editable DXF entities (`LINE`, `LWPOLYLINE`, `MTEXT`) for CAD interoperability. |
| **`FreeCAD Python API`** | Parametric 2D engineering profile generator when installed, with analytical fallbacks. |
| **`Pydantic AI` & `Pydantic`** | Validates structured tool calls and CAD parameters: enforces schemas for `SelectiveEditCommand`, `EngineeringDrawingObject`, and `GeometricVerificationReport`. |
| **`OpenCV` (`cv2`)** | Computer vision diffing (`cv2.absdiff`), alteration heatmap generation, and structural similarity verification. |
| **`Streamlit` (>= 1.35.0)** | Interactive web UI with dedicated Single-PDF 1-click Auto-Correction Mode. |

---

## 3. End-to-End Architectural Pipeline

```
[Consultant-Commented Engineering PDF]
                   │
                   ▼
1. PDF-TO-CAD RECONSTRUCTION PIPELINE (`core/cad_pipeline.py`)
   ├─ PyMuPDF extracts vector strokes (re, l, c) & text spans
   ├─ Maps colors to engineering layers (A-WALL, M-CONDUIT, E-EQUIP, G-ANNO)
   ├─ Generates native ezdxf Document (AutoCAD R2018, units=mm)
   └─ Builds Shapely Spatial Index (STRtree) for microsecond 2D queries
                   │
                   ▼
2. GEOMETRY-AWARE OBJECT RECOGNIZER
   ├─ Queries target region around consultant comments (+120pt buffer)
   ├─ Associates dimension lines with measurement text
   ├─ Detects equipment pads and connected conduit lines
   └─ Identifies consultant markup arrows and callout pins (OpenCV)
                   │
                   ▼
3. PYDANTIC AI ACTION SYNTHESIZER (`core/cad_schema.py`)
   ├─ LLM evaluates consultant directive & surrounding CAD context
   ├─ Generates validated Pydantic CADEditAction operations:
   │  - MOVE_EQUIPMENT, REPLACE_SYMBOL, UPDATE_DIMENSION
   │  - REMOVE_CONDUIT, RESTORE_LABEL, CREATE_2D_DETAIL
   │  - DRAW_REVISION_CLOUD, ADD_DELTA_TAG
   └─ Flags missing reference information for engineer sign-off
                   │
                   ▼
4. CAD GEOMETRY MODIFICATION ENGINE
   ├─ Displaces equipment vertices & associated labels by (dx, dy)
   ├─ Replaces non-compliant symbols with standard IFC blocks
   ├─ Adjusts dimension lines and nominal text values
   ├─ Deletes/severs incorrect conduit connections
   ├─ Renders authentic scalloped CAD revision clouds on REVISION-CLOUDS layer
   ├─ Places triangular revision delta tags (Δ1)
   └─ Stamps title block with official "AI AUTO-RECTIFIED" revision ledger
                   │
                   ▼
5. DUAL GEOMETRIC & VISUAL VERIFICATION
   ├─ Geometric Assertion Suite:
   │  - Displacement check: measured Δ(x,y) vs. expected Δ(x,y)
   │  - Disconnection check: target conduit severed from equipment
   │  - Scale preservation check: 100% of unaffected linework invariant
   └─ OpenCV Visual Validation:
      - 2.0x zoom Before vs. After raster comparison
      - Absolute difference alteration heatmap
                   │
                   ▼
6. MULTI-FORMAT EXPORT
   ├─ 📐 Editable AutoCAD DXF (`AutoRectified_[Drawing].dxf`)
   ├─ 📥 Publication-grade Vector PDF (`AutoRectified_[Drawing].pdf`)
   ├─ 📄 Geometric Audit Ledger (`Geometric_CAD_Audit_Report.json`)
   └─ 🔄 Optional DWG output via ODA File Converter
```

---

## 4. Key Module Index

| Module | Core Functions & Classes |
| :--- | :--- |
| [`core/cad_schema.py`](file:///c:/Users/Pc/Desktop/OCR%20DULB/core/cad_schema.py) | `EngineeringObjectType`, `SelectiveActionType`, `EngineeringDrawingObject`, `SelectiveEditCommand`, `GeometricAssertion`, `GeometricVerificationReport`. Pydantic models enforcing CAD operations. |
| [`core/object_mapper.py`](file:///c:/Users/Pc/Desktop/OCR%20DULB/core/object_mapper.py) | `map_vectors_to_engineering_objects()`, `find_target_object_for_comment()`, `extract_page_raw_elements()`. Groups raw PDF vectors into semantic CAD objects (Card Readers, Doors, Conduits, Legends) using leader arrow vertices. |
| [`core/selective_engine.py`](file:///c:/Users/Pc/Desktop/OCR%20DULB/core/selective_engine.py) | Direct in-place PDF vector modification engine: `replace_card_reader_symbol()`, `move_card_reader_or_equipment()`, `remove_conduit_line()`, `replace_text_or_dimension()`, `update_equipment_elevation()`, `restore_space_ids()`, `regenerate_legend_or_table()`, `clean_all_consultant_markups()`. |
| [`core/llm_agent.py`](file:///c:/Users/Pc/Desktop/OCR%20DULB/core/llm_agent.py) | `synthesize_selective_command()`. Bridges Sarvam AI/Ollama LLM to structured `SelectiveEditCommand` Pydantic actions with deterministic engineering fallback. |
| [`core/verification.py`](file:///c:/Users/Pc/Desktop/OCR%20DULB/core/verification.py) | `verify_selective_modifications()`. Dual geometric assertions + OpenCV alteration heatmaps + 100% scale and linework invariance auditing. |
| [`core/correction_engine.py`](file:///c:/Users/Pc/Desktop/OCR%20DULB/core/correction_engine.py) | High-level orchestrator: `rectify_drawing_selectively()` (single-drawing in-place selective pipeline) and `apply_pdf_corrections()` (DXF pipeline). |
| [`core/cad_pipeline.py`](file:///c:/Users/Pc/Desktop/OCR%20DULB/core/cad_pipeline.py) | `reconstruct_pdf_to_dxf()`, `SpatialCadModel`, `execute_cad_modifications()`, `export_cad_to_vector_pdf()`. |
| [`core/dwg_converter.py`](file:///c:/Users/Pc/Desktop/OCR%20DULB/core/dwg_converter.py) | `find_oda_converter()`, `get_dwg_converter_status()`, `convert_dxf_to_dwg()`. External ODA CLI converter integration. |
| [`core/freecad_bridge.py`](file:///c:/Users/Pc/Desktop/OCR%20DULB/core/freecad_bridge.py) | `discover_freecad_python()`, `generate_parametric_2d_profile()`. Parametric 2D profile synthesis. |
| [`ui/correction_view.py`](file:///c:/Users/Pc/Desktop/OCR%20DULB/ui/correction_view.py) | Streamlit UI component: single-drawing auto-rectification view, multi-format downloads (DXF/PDF/JSON), geometric assertions, and OpenCV diff cards. |
| [`pages/Auto_Correction_Mode.py`](file:///c:/Users/Pc/Desktop/OCR%20DULB/pages/Auto_Correction_Mode.py) | Dedicated single-PDF autonomous CAD rectification page. |
| [`app.py`](file:///c:/Users/Pc/Desktop/OCR%20DULB/app.py) | Main application entrypoint supporting mode switching. |

---

## 5. Pydantic Action Schema Reference

```json
{
  "comment_id": "C-101",
  "summary": "Rectified door width to 1050mm and severed incorrect conduit connection",
  "revision_note": "Rev B - Rectified Door & Conduit per C-101",
  "engineer_review_required": false,
  "missing_references": [],
  "actions": [
    {
      "action_type": "update_dimension",
      "object_type": "dimension",
      "target_id": "C-101",
      "page": 1,
      "spatial_region": [100.0, 130.0, 320.0, 240.0],
      "new_dimension_value": "1050 mm",
      "engineering_justification": "Adjust nominal CAD dimension line and measurement text to 1050 mm."
    },
    {
      "action_type": "remove_conduit",
      "object_type": "conduit",
      "target_id": "C-101",
      "page": 1,
      "spatial_region": [200.0, 180.0, 320.0, 200.0],
      "engineering_justification": "Sever non-compliant MEP conduit run from panel."
    },
    {
      "action_type": "draw_revision_cloud",
      "object_type": "revision_cloud",
      "target_id": "C-101",
      "page": 1,
      "spatial_region": [75.0, 110.0, 345.0, 260.0],
      "engineering_justification": "Render authentic CAD revision cloud on REVISION-CLOUDS layer."
    },
    {
      "action_type": "add_delta_tag",
      "object_type": "delta_tag",
      "target_id": "C-101",
      "page": 1,
      "spatial_region": [65.0, 95.0, 85.0, 115.0],
      "new_label_text": "Δ1",
      "engineering_justification": "Add standard CAD revision delta symbol Δ1."
    }
  ]
}
```

---

## 6. How to Run & Verify

1. **Launch Streamlit**:
   ```powershell
   streamlit run app.py
   ```
2. **Select Workflow Mode**:
   In the sidebar under **`📍 Workflow Mode`**, select **`🛠️ Auto-Correction Mode (1 PDF)`**.
3. **Upload Drawing**:
   Upload any engineering drawing containing consultant comments or markups.
4. **Execute**:
   Click **`⚡ Automatically Generate Updated Drawing with All Corrections`**.
5. **Inspect Results**:
   - Check the **Geometric Assertions Table** confirming displacements and topological changes.
   - Inspect the **OpenCV Visual Diff Heatmaps** showing Before vs. After.
   - Review any **Engineer Review Required** warnings if specifications were ambiguous.
6. **Download Deliverables**:
   - 📥 **Vector PDF** (`AutoRectified_[Drawing].pdf`)
   - 📐 **Editable DXF** (`AutoRectified_[Drawing].dxf`)
   - 📄 **Geometric Audit JSON** (`Geometric_CAD_Audit_Report.json`)
