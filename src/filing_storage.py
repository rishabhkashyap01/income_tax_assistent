"""
Filing Storage
==============
Save and load ITR filing data to/from JSON files for persistence across sessions.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

from src.itr_models import ITRFiling

FILING_DIR = os.path.join("data", "filings")


def _ensure_dir():
    os.makedirs(FILING_DIR, exist_ok=True)


def _safe_filename(pan: str, ay: str) -> str:
    """Generate a safe filename from PAN and AY."""
    pan_safe = re.sub(r"[^A-Za-z0-9]", "", pan) or "UNKNOWN"
    ay_safe = re.sub(r"[^0-9-]", "", ay) or "2025-26"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{pan_safe}_{ay_safe}_{timestamp}.json"


def save_filing(filing: ITRFiling) -> str:
    """Save filing to a JSON file. Returns the file path."""
    _ensure_dir()
    filing.updated_at = datetime.now().isoformat()

    # If filing already has a known path, overwrite it
    filename = _safe_filename(filing.personal.pan, filing.assessment_year)
    filepath = os.path.join(FILING_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(filing.to_dict(), f, indent=2, ensure_ascii=False)

    return filepath


def save_filing_to_path(filing: ITRFiling, filepath: str):
    """Save filing to a specific path (for updating existing files)."""
    filing.updated_at = datetime.now().isoformat()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(filing.to_dict(), f, indent=2, ensure_ascii=False)


def load_filing(filepath: str) -> ITRFiling:
    """Load filing from a JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return ITRFiling.from_dict(data)


def list_filings() -> list[dict]:
    """List all saved filings with summary metadata."""
    _ensure_dir()
    filings = []

    for filename in sorted(os.listdir(FILING_DIR), reverse=True):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(FILING_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            filings.append({
                "filepath": filepath,
                "filename": filename,
                "pan": data.get("personal", {}).get("pan", "N/A"),
                "name": data.get("personal", {}).get("name", "Unknown"),
                "form_type": data.get("form_type", ""),
                "assessment_year": data.get("assessment_year", ""),
                "current_step": data.get("current_step", ""),
                "updated_at": data.get("updated_at", ""),
            })
        except (json.JSONDecodeError, KeyError):
            continue

    return filings


def delete_filing(filepath: str) -> bool:
    """Delete a saved filing."""
    try:
        os.remove(filepath)
        return True
    except OSError:
        return False
