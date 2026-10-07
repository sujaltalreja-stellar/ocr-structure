# ============================================================
# DULB ENGINEERING QA POC - CONFIGURATION & CONSTANTS
# ============================================================

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================
# OPTIONAL AI PROVIDER DETECTION
# ============================================================

try:
    from sarvamai import SarvamAI
    SARVAM_AVAILABLE = True
except Exception:
    SARVAM_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except Exception:
    OLLAMA_AVAILABLE = False


# ============================================================
# CONSTANTS
# ============================================================

COMMENT_PHRASES = [
    "the contractor",
    "the engineer",
    "shall provide",
    "shall include",
    "shall indicate",
    "shall reflect",
    "shall show",
    "shall restore",
    "shall rectify",
    "rectify",
    "restore",
    "why",
    "not indicated",
    "not provided",
    "not complied",
    "rejected",
    "changed by the contractor",
    "as per the ifc",
    "keep it as",
    "missing",
    "incorrect",
    "wrong",
]

STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "have", "has",
    "had", "was", "were", "shall", "should", "would", "could", "their", "there",
    "then", "than", "they", "them", "its", "our", "your", "you", "are", "not",
    "all", "any", "per", "here", "only", "also", "upon", "been", "being", "will",
    "can", "but", "due", "drawing", "drawings", "contractor", "engineer",
}

VALID_STATUSES = [
    "Resolved",
    "Partially Resolved",
    "Not Resolved",
    "Cannot Verify",
]
