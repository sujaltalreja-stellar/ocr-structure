# ============================================================
# DULB ENGINEERING QA POC - ODA / AUTOCAD DWG INTERFACE
# ============================================================

import os
import shutil
import subprocess
from typing import Dict, Any, Optional


def find_oda_converter() -> Optional[str]:
    """
    Searches for ODA File Converter executable on Windows systems.
    Checks standard Program Files directories and system PATH.
    """
    # 1. Check system PATH
    on_path = shutil.which("ODAFileConverter.exe") or shutil.which("odafileconverter")
    if on_path and os.path.exists(on_path):
        return on_path

    # 2. Check standard Windows Program Files paths
    standard_paths = [
        r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
        r"C:\Program Files (x86)\ODA\ODAFileConverter\ODAFileConverter.exe",
        r"C:\Program Files\ODAFileConverter\ODAFileConverter.exe",
        r"C:\Program Files (x86)\ODAFileConverter\ODAFileConverter.exe",
    ]
    for p in standard_paths:
        if os.path.exists(p):
            return p

    # 3. Check custom environment variable
    custom_path = os.getenv("ODA_FILE_CONVERTER_PATH")
    if custom_path and os.path.exists(custom_path):
        return custom_path

    return None


def get_dwg_converter_status() -> Dict[str, Any]:
    """
    Returns diagnostic status for DWG conversion availability.
    """
    oda_path = find_oda_converter()
    autocad_available = False

    # Check for AutoCAD COM automation on Windows
    try:
        import win32com.client
        autocad_available = True
    except Exception:
        autocad_available = False

    return {
        "oda_available": oda_path is not None,
        "oda_path": oda_path,
        "autocad_com_available": autocad_available,
        "native_dxf_support": True,
        "message": (
            f"ODA File Converter found at {oda_path}"
            if oda_path
            else "ODA File Converter not detected. Native DXF (R2018) is fully supported and directly editable in AutoCAD, DraftSight, and FreeCAD. To enable direct DWG output, install ODA File Converter or set ODA_FILE_CONVERTER_PATH."
        ),
    }


def convert_dxf_to_dwg(
    dxf_path: str,
    output_dir: str,
    output_version: str = "ACAD2018",
) -> Dict[str, Any]:
    """
    Converts a DXF file to DWG using the ODA File Converter CLI.
    Command syntax:
      ODAFileConverter "InputFolder" "OutputFolder" "ACAD2018" "DWG" "0" "1"
    """
    oda_path = find_oda_converter()
    if not oda_path:
        return {
            "success": False,
            "dwg_path": None,
            "error": "ODA File Converter is not installed. Use the exported DXF file directly in AutoCAD.",
        }

    input_dir = os.path.dirname(os.path.abspath(dxf_path))
    filename = os.path.splitext(os.path.basename(dxf_path))[0]
    expected_dwg = os.path.join(output_dir, f"{filename}.dwg")

    cmd = [
        oda_path,
        input_dir,
        output_dir,
        output_version,
        "DWG",
        "0",  # Recurse: No
        "1",  # Audit: Yes
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if os.path.exists(expected_dwg):
            return {
                "success": True,
                "dwg_path": expected_dwg,
                "error": None,
            }
        else:
            return {
                "success": False,
                "dwg_path": None,
                "error": f"ODA converter finished but DWG not found. Stdout: {result.stdout}",
            }
    except Exception as e:
        return {
            "success": False,
            "dwg_path": None,
            "error": str(e),
        }
