"""
Authentication
==============
Simple username/password auth with bcrypt hashing.
"""

from __future__ import annotations

import secrets
from datetime import datetime

import bcrypt
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from src.database import get_db


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def register_user(username: str, password: str) -> dict | None:
    """Create a new user. Returns the user dict, or None if username is taken."""
    db = get_db()
    user_doc = {
        "username": username,
        "password_hash": hash_password(password),
        "created_at": datetime.now().isoformat(),
    }
    try:
        result = db.users.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        return user_doc
    except DuplicateKeyError:
        return None


def authenticate_user(username: str, password: str) -> dict | None:
    """Verify credentials. Returns user dict if valid, None otherwise."""
    db = get_db()
    user = db.users.find_one({"username": username})
    if user and verify_password(password, user["password_hash"]):
        return user
    return None


def create_session(user_id: str) -> str:
    """Create a persistent session token for the user. Returns the token."""
    db = get_db()
    token = secrets.token_urlsafe(32)
    db.sessions.insert_one({
        "token": token,
        "user_id": user_id,
        "created_at": datetime.now().isoformat(),
    })
    return token


def validate_session(token: str) -> dict | None:
    """Look up a session token. Returns the user dict if valid, None otherwise."""
    db = get_db()
    session = db.sessions.find_one({"token": token})
    if not session:
        return None
    user = db.users.find_one({"_id": ObjectId(session["user_id"])})
    return user


def delete_session(token: str):
    """Delete a session token (logout)."""
    db = get_db()
    db.sessions.delete_one({"token": token})
