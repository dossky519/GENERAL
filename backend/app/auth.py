"""Web UI login authentication.

Stdlib-only (no extra dependency): passwords are hashed with
PBKDF2-HMAC-SHA256, sessions are HMAC-signed cookies with an expiry
embedded in the payload. User accounts are managed out-of-band via
`manage_users.py`, not through a public self-registration endpoint.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
USERS_FILE = DATA_DIR / "users.json"
SECRET_KEY_FILE = DATA_DIR / "secret_key"

SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", str(8 * 3600)))
COOKIE_NAME = "session"


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_secret_key() -> bytes:
    """Session-signing key. Uses SECRET_KEY env var if set, otherwise a
    key persisted to disk (generated once) so sessions survive restarts."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key.encode("utf-8")
    _ensure_data_dir()
    if SECRET_KEY_FILE.exists():
        return SECRET_KEY_FILE.read_bytes()
    key = os.urandom(32)
    SECRET_KEY_FILE.write_bytes(key)
    try:
        SECRET_KEY_FILE.chmod(0o600)
    except OSError:
        pass
    return key


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2-HMAC-SHA256)
# ---------------------------------------------------------------------------

def hash_password(password: str, iterations: int = 260_000) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${binascii.hexlify(salt).decode()}${binascii.hexlify(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations_s, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iterations_s)
        salt = binascii.unhexlify(salt_hex)
        expected = binascii.unhexlify(hash_hex)
    except (ValueError, binascii.Error):
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(dk, expected)


# ---------------------------------------------------------------------------
# User store (backend/data/users.json)
# ---------------------------------------------------------------------------

def _load_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_users(users: dict) -> None:
    _ensure_data_dir()
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        USERS_FILE.chmod(0o600)
    except OSError:
        pass


def add_user(username: str, password: str) -> None:
    users = _load_users()
    users[username] = {"password_hash": hash_password(password)}
    _save_users(users)


def remove_user(username: str) -> bool:
    users = _load_users()
    if username in users:
        del users[username]
        _save_users(users)
        return True
    return False


def list_users() -> list[str]:
    return sorted(_load_users().keys())


def authenticate(username: str, password: str) -> bool:
    users = _load_users()
    record = users.get(username)
    if not record:
        hash_password(password)  # keep timing roughly constant either way
        return False
    return verify_password(password, record.get("password_hash", ""))


def bootstrap_from_env() -> None:
    """If no users exist yet, create one from ADMIN_USERNAME/ADMIN_PASSWORD
    env vars so the first login is possible without a manual CLI step."""
    if _load_users():
        return
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")
    if username and password:
        add_user(username, password)


# ---------------------------------------------------------------------------
# Signed session tokens
# ---------------------------------------------------------------------------

def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def create_session_token(username: str) -> str:
    secret = get_secret_key()
    payload = {"u": username, "exp": int(time.time()) + SESSION_TTL_SECONDS}
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(secret, payload_bytes, hashlib.sha256).digest()
    return f"{_b64e(payload_bytes)}.{_b64e(sig)}"


def verify_session_token(token: str) -> Optional[str]:
    secret = get_secret_key()
    try:
        payload_part, sig_part = token.split(".", 1)
        payload_bytes = _b64d(payload_part)
        sig = _b64d(sig_part)
    except (ValueError, binascii.Error):
        return None
    expected_sig = hmac.new(secret, payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        return None
    if payload.get("exp", 0) < time.time():
        return None
    username = payload.get("u")
    return username if isinstance(username, str) else None


# ---------------------------------------------------------------------------
# Brute-force login throttling (in-memory, per-process)
# ---------------------------------------------------------------------------

_FAILED_ATTEMPTS: dict[str, list[float]] = {}
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 5 * 60


def is_locked_out(key: str) -> bool:
    now = time.time()
    attempts = [t for t in _FAILED_ATTEMPTS.get(key, []) if now - t < WINDOW_SECONDS]
    _FAILED_ATTEMPTS[key] = attempts
    return len(attempts) >= MAX_ATTEMPTS


def record_failed_attempt(key: str) -> None:
    _FAILED_ATTEMPTS.setdefault(key, []).append(time.time())


def clear_attempts(key: str) -> None:
    _FAILED_ATTEMPTS.pop(key, None)
