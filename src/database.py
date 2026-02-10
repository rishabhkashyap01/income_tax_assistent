"""
Database Connection
===================
MongoDB connection management using pymongo.
"""

from __future__ import annotations

import os

from pymongo import MongoClient
from pymongo.database import Database
from dotenv import load_dotenv

load_dotenv()

_client: MongoClient | None = None
_db: Database | None = None


def get_db() -> Database:
    """Return the MongoDB database instance (lazy singleton)."""
    global _client, _db
    if _db is None:
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB_NAME", "tax_assistant")
        _client = MongoClient(mongo_uri)
        _db = _client[db_name]
        _ensure_indexes(_db)
    return _db


def _ensure_indexes(db: Database):
    """Create indexes on first connection (idempotent)."""
    db.users.create_index("username", unique=True)
    db.filings.create_index("user_id")
    db.filings.create_index([("user_id", 1), ("updated_at", -1)])
