"""
Filing Storage (MongoDB)
========================
Save and load ITR filing data to/from MongoDB.
"""

from __future__ import annotations

from datetime import datetime

from bson import ObjectId

from src.database import get_db
from src.itr_models import ITRFiling


def save_filing(filing: ITRFiling, user_id: str, messages: list[dict] | None = None) -> str:
    """Insert a new filing. Returns the filing_id (string)."""
    db = get_db()
    filing.updated_at = datetime.now().isoformat()
    doc = filing.to_dict()
    doc["user_id"] = ObjectId(user_id)
    doc["filing_messages"] = messages or []
    result = db.filings.insert_one(doc)
    return str(result.inserted_id)


def update_filing(filing: ITRFiling, filing_id: str, messages: list[dict] | None = None):
    """Update an existing filing in-place."""
    db = get_db()
    filing.updated_at = datetime.now().isoformat()
    doc = filing.to_dict()
    if messages is not None:
        doc["filing_messages"] = messages
    db.filings.update_one(
        {"_id": ObjectId(filing_id)},
        {"$set": doc},
    )


def load_filing(filing_id: str) -> tuple[ITRFiling, list[dict]]:
    """Load a filing by its ID. Returns (ITRFiling, filing_messages)."""
    db = get_db()
    doc = db.filings.find_one({"_id": ObjectId(filing_id)})
    if doc is None:
        raise ValueError(f"Filing not found: {filing_id}")
    messages = doc.pop("filing_messages", [])
    doc.pop("_id", None)
    doc.pop("user_id", None)
    return ITRFiling.from_dict(doc), messages


def list_filings(user_id: str) -> list[dict]:
    """List all filings for a user, sorted by most recently updated."""
    db = get_db()
    cursor = db.filings.find(
        {"user_id": ObjectId(user_id)},
        {
            "personal.pan": 1,
            "personal.name": 1,
            "form_type": 1,
            "assessment_year": 1,
            "current_step": 1,
            "updated_at": 1,
        },
    ).sort("updated_at", -1).limit(20)

    filings = []
    for doc in cursor:
        filings.append({
            "filing_id": str(doc["_id"]),
            "pan": doc.get("personal", {}).get("pan", "N/A"),
            "name": doc.get("personal", {}).get("name", "Unknown"),
            "form_type": doc.get("form_type", ""),
            "assessment_year": doc.get("assessment_year", ""),
            "current_step": doc.get("current_step", ""),
            "updated_at": doc.get("updated_at", ""),
        })
    return filings


def delete_filing(filing_id: str) -> bool:
    """Delete a filing by its ID."""
    db = get_db()
    result = db.filings.delete_one({"_id": ObjectId(filing_id)})
    return result.deleted_count > 0
