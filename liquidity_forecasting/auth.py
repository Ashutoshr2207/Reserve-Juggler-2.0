"""Secure Banker Authentication and MongoDB User Management for Reserve Juggler."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import argon2
from bson import ObjectId
from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

logger = logging.getLogger("reserve_juggler.auth")

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
DEFAULT_SESSION_LIFETIME = 2592000  # 30 days in seconds
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 900  # 15 minutes

# Initialize Argon2id hasher with secure parameters
_HASHER = argon2.PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
    type=argon2.Type.ID,
)

# Dummy hash used to balance timing during failed email lookups
_DUMMY_HASH = _HASHER.hash("DummyPasswordToPreventTimingAttacks!123")


class AuthError(Exception):
    """Base exception for authentication errors."""

    def __init__(self, message: str, status: int = 400, code: str = "auth_error"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


class ValidationError(AuthError):
    def __init__(self, message: str):
        super().__init__(message, status=400, code="validation_error")


class AuthenticationError(AuthError):
    def __init__(self, message: str = "Invalid email or password."):
        super().__init__(message, status=401, code="unauthorized")


class RateLimitError(AuthError):
    def __init__(
        self, message: str = "Too many failed login attempts. Please try again later."
    ):
        super().__init__(message, status=429, code="rate_limited")


class ServiceUnavailableError(AuthError):
    def __init__(
        self, message: str = "Authentication service is temporarily unavailable."
    ):
        super().__init__(message, status=503, code="service_unavailable")


def normalize_email(email: str) -> str:
    """Normalize email address consistently for duplicate checks and lookups."""
    if not isinstance(email, str):
        raise ValidationError("Email must be a valid text string.")
    cleaned = email.strip().lower()
    if not cleaned or not EMAIL_REGEX.match(cleaned):
        raise ValidationError("Please provide a valid work email address.")
    if len(cleaned) > 254:
        raise ValidationError("Email address exceeds maximum permitted length.")
    return cleaned


def hash_password(password: str) -> str:
    """Hash password using Argon2id with secure defaults."""
    return _HASHER.hash(password)


def verify_password(hash_value: str, password: str) -> bool:
    """Verify password against Argon2id hash."""
    try:
        return _HASHER.verify(hash_value, password)
    except (argon2.exceptions.VerifyMismatchError, argon2.exceptions.VerificationError):
        return False
    except Exception:
        return False


def hash_token(token: str) -> str:
    """Generate SHA-256 digest of session token to prevent plaintext storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def sanitize_user(user_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize user document for API response (never return password_hash)."""
    return {
        "id": str(user_doc.get("_id", "")),
        "full_name": user_doc.get("full_name", ""),
        "email": user_doc.get("email", ""),
        "organization_name": user_doc.get("organization_name", ""),
        "job_title": user_doc.get("job_title") or "",
        "role": user_doc.get("role", "banker"),
        "account_status": user_doc.get("account_status", "active"),
        "created_at": user_doc.get("created_at"),
        "last_login_at": user_doc.get("last_login_at"),
    }


class LoginRateLimiter:
    """In-memory rate limiter for login attempts."""

    def __init__(
        self,
        max_attempts: int = MAX_FAILED_ATTEMPTS,
        window_seconds: int = LOCKOUT_WINDOW_SECONDS,
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: Dict[str, List[float]] = {}

    def _cleanup(self, key: str, now: float):
        if key in self.attempts:
            cutoff = now - self.window_seconds
            self.attempts[key] = [t for t in self.attempts[key] if t > cutoff]
            if not self.attempts[key]:
                del self.attempts[key]

    def is_locked(self, key: str) -> bool:
        now = time.time()
        self._cleanup(key, now)
        return len(self.attempts.get(key, [])) >= self.max_attempts

    def record_failure(self, key: str):
        now = time.time()
        self._cleanup(key, now)
        self.attempts.setdefault(key, []).append(now)

    def reset(self, key: str):
        self.attempts.pop(key, None)


class AuthManager:
    """Manages MongoDB user accounts, authentication sessions, and security checks."""

    def __init__(
        self,
        mongo_uri: Optional[str] = None,
        db_name: Optional[str] = None,
        session_lifetime: Optional[int] = None,
        client: Optional[MongoClient] = None,
        database: Optional[Any] = None,
    ):
        self.mongo_uri = mongo_uri or os.environ.get(
            "MONGODB_URI", "mongodb://127.0.0.1:27017"
        )
        raw_db_name = (
            db_name or os.environ.get("MONGODB_DB_NAME", "reserve_juggler")
        ).strip()
        if not raw_db_name or any(c in raw_db_name for c in r'/\. "$*<>:|?'):
            self.db_name = "reserve_juggler"
        else:
            self.db_name = raw_db_name
        try:
            self.session_lifetime = int(
                session_lifetime
                or os.environ.get(
                    "AUTH_SESSION_LIFETIME_SECONDS", DEFAULT_SESSION_LIFETIME
                )
            )
        except (ValueError, TypeError):
            self.session_lifetime = DEFAULT_SESSION_LIFETIME

        self.rate_limiter = LoginRateLimiter()
        self._client: Optional[MongoClient] = client
        self._db: Optional[Any] = database
        self.is_connected = False
        self._last_connect_error = ""

        if self._db is not None:
            self.is_connected = True
            self.setup_indexes()
        else:
            self.connect()

    def connect(self) -> bool:
        """Connect to MongoDB and ensure indexes exist."""
        try:
            if not self._client:
                self._client = MongoClient(
                    self.mongo_uri,
                    serverSelectionTimeoutMS=2500,
                    connectTimeoutMS=2500,
                    tz_aware=True,
                )
            # Ping database to verify connection
            self._client.admin.command("ping")
            self._db = self._client[self.db_name]
            self.is_connected = True
            self._last_connect_error = ""
            self.setup_indexes()
            logger.info("Successfully connected to MongoDB (%s)", self.db_name)
            return True
        except Exception as err:
            self.is_connected = False
            self._last_connect_error = "Could not connect to MongoDB server."
            logger.warning(
                "MongoDB connection unavailable: %s: %s", type(err).__name__, err
            )
            return False

    def check_health(self) -> Dict[str, Any]:
        """Check status of MongoDB connection for the health endpoint."""
        if not self.is_connected:
            # Try a quick reconnect
            if self.connect():
                return {"status": "ok", "database": "connected"}
            return {
                "status": "degraded",
                "database": "unavailable",
                "message": self._last_connect_error
                or "Database connection unavailable.",
            }
        try:
            assert self._client is not None
            self._client.admin.command("ping")
            return {"status": "ok", "database": "connected"}
        except Exception:
            self.is_connected = False
            return {
                "status": "degraded",
                "database": "unavailable",
                "message": "Database ping failed.",
            }

    def setup_indexes(self):
        """Create required unique and TTL indexes idempotently."""
        if self._db is None:
            return
        try:
            # users collection: unique index on normalized_email
            self._db.users.create_index(
                [("normalized_email", ASCENDING)],
                unique=True,
                name="idx_users_normalized_email",
            )
            # auth_sessions collection: unique index on token_hash
            self._db.auth_sessions.create_index(
                [("token_hash", ASCENDING)],
                unique=True,
                name="idx_sessions_token_hash",
            )
            # auth_sessions collection: TTL index on expires_at
            self._db.auth_sessions.create_index(
                [("expires_at", ASCENDING)],
                expireAfterSeconds=0,
                name="idx_sessions_ttl",
            )
            # auth_sessions collection: index on user_id
            self._db.auth_sessions.create_index(
                [("user_id", ASCENDING)],
                name="idx_sessions_user_id",
            )
        except Exception as err:
            logger.warning("Index setup warning: %s", err)

    def _require_db(self):
        if not self.is_connected or self._db is None:
            # Attempt reconnect once
            if not self.connect() or self._db is None:
                raise ServiceUnavailableError(
                    "MongoDB is currently unavailable. "
                    "Authentication is paused until the database reconnects."
                )

    def register(
        self,
        full_name: str,
        email: str,
        organization_name: str,
        job_title: Optional[str] = None,
        password: str = "",
        confirm_password: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], str, str]:
        """Register a new banker account."""
        self._require_db()

        # Input validation
        if not isinstance(full_name, str) or not full_name.strip():
            raise ValidationError("Full name is required.")
        if len(full_name.strip()) > 100:
            raise ValidationError("Full name must be at most 100 characters.")

        norm_email = normalize_email(email)

        if not isinstance(organization_name, str) or not organization_name.strip():
            raise ValidationError("Organization name is required.")
        if len(organization_name.strip()) > 150:
            raise ValidationError("Organization name must be at most 150 characters.")

        clean_job_title = None
        if job_title and isinstance(job_title, str) and job_title.strip():
            clean_job_title = job_title.strip()
            if len(clean_job_title) > 100:
                raise ValidationError("Job title must be at most 100 characters.")

        if not isinstance(password, str):
            raise ValidationError("Password must be a text string.")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
            )
        if len(password) > MAX_PASSWORD_LENGTH:
            raise ValidationError(
                f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters."
            )

        if confirm_password is not None and password != confirm_password:
            raise ValidationError("Password confirmation does not match.")

        # Hash password using Argon2id
        pwd_hash = hash_password(password)

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # Always assign banker role automatically. Never trust client-supplied roles.
        user_doc = {
            "full_name": full_name.strip(),
            "email": email.strip(),
            "normalized_email": norm_email,
            "organization_name": organization_name.strip(),
            "job_title": clean_job_title,
            "role": "banker",
            "account_status": "active",
            "password_hash": pwd_hash,
            "created_at": now_iso,
            "updated_at": now_iso,
            "last_login_at": now_iso,
        }

        try:
            assert self._db is not None
            res = self._db.users.insert_one(user_doc)
            user_doc["_id"] = res.inserted_id
        except DuplicateKeyError:
            raise ValidationError("An account with this email address already exists.")
        except PyMongoError:
            logger.exception("Database error during registration")
            raise ServiceUnavailableError("Database error during account registration.")

        user_id = str(user_doc["_id"])
        session_token, csrf_token = self.create_session(user_id)
        return sanitize_user(user_doc), session_token, csrf_token

    def login(
        self,
        email: str,
        password: str,
        client_ip: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], str, str]:
        """Authenticate banker, apply rate limiting, and rotate session."""
        self._require_db()

        if (
            not isinstance(email, str)
            or not email.strip()
            or not isinstance(password, str)
        ):
            raise AuthenticationError("Invalid email or password.")

        try:
            norm_email = normalize_email(email)
        except ValidationError:
            # Prevent revealing email format checks differently from bad creds
            raise AuthenticationError("Invalid email or password.")

        rate_key = f"{client_ip or 'unknown'}:{norm_email}"
        if self.rate_limiter.is_locked(rate_key):
            raise RateLimitError()

        assert self._db is not None
        user_doc = self._db.users.find_one({"normalized_email": norm_email})

        if not user_doc:
            # Timing attack prevention: perform dummy hash verification
            verify_password(_DUMMY_HASH, password)
            self.rate_limiter.record_failure(rate_key)
            raise AuthenticationError("Invalid email or password.")

        if user_doc.get("account_status") != "active":
            self.rate_limiter.record_failure(rate_key)
            raise AuthenticationError("Account is inactive or suspended.")

        stored_hash = user_doc.get("password_hash", "")
        if not verify_password(stored_hash, password):
            self.rate_limiter.record_failure(rate_key)
            raise AuthenticationError("Invalid email or password.")

        # Success: reset rate limit attempts
        self.rate_limiter.reset(rate_key)

        # Update last login timestamp
        now = datetime.now(timezone.utc)
        self._db.users.update_one(
            {"_id": user_doc["_id"]},
            {"$set": {"last_login_at": now.isoformat(), "updated_at": now.isoformat()}},
        )
        user_doc["last_login_at"] = now.isoformat()

        # Rotate/create fresh session token
        session_token, csrf_token = self.create_session(str(user_doc["_id"]))
        return sanitize_user(user_doc), session_token, csrf_token

    def create_session(self, user_id: str) -> Tuple[str, str]:
        """Create a server-side session and return raw (session_token, csrf_token)."""
        self._require_db()

        # Cryptographically secure random tokens
        session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_hex(16)
        token_digest = hash_token(session_token)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.session_lifetime)

        session_doc = {
            "user_id": str(user_id),
            "token_hash": token_digest,
            "created_at": now,
            "expires_at": expires_at,
            "last_activity_at": now,
            "revoked": False,
            "csrf_token": csrf_token,
        }

        assert self._db is not None
        self._db.auth_sessions.insert_one(session_doc)
        return session_token, csrf_token

    def verify_session(
        self, session_token: Optional[str]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Verify an authentication token.

        Returns (user, session_doc) or (None, None).
        """
        if (
            not session_token
            or not isinstance(session_token, str)
            or len(session_token) < 20
        ):
            return None, None

        if not self.is_connected or self._db is None:
            if not self.connect() or self._db is None:
                return None, None

        token_digest = hash_token(session_token)
        try:
            session_doc = self._db.auth_sessions.find_one({"token_hash": token_digest})
            if not session_doc:
                return None, None

            if session_doc.get("revoked", False):
                return None, None

            now = datetime.now(timezone.utc)
            expires_at = session_doc.get("expires_at")
            if expires_at:
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if now > expires_at:
                    # Session expired independently of async TTL
                    return None, None

            # Fetch user
            user_id = session_doc.get("user_id")
            try:
                obj_id = ObjectId(user_id)
            except Exception:
                return None, None

            user_doc = self._db.users.find_one({"_id": obj_id})
            if not user_doc or user_doc.get("account_status") != "active":
                return None, None

            # Update last activity
            self._db.auth_sessions.update_one(
                {"_id": session_doc["_id"]},
                {"$set": {"last_activity_at": now}},
            )

            return sanitize_user(user_doc), session_doc
        except PyMongoError:
            logger.exception("Error checking session")
            return None, None

    def revoke_session(self, session_token: Optional[str]) -> bool:
        """Revoke a server-side session."""
        if not session_token or not isinstance(session_token, str):
            return False

        if not self.is_connected or self._db is None:
            if not self.connect() or self._db is None:
                return False

        token_digest = hash_token(session_token)
        try:
            res = self._db.auth_sessions.update_one(
                {"token_hash": token_digest},
                {"$set": {"revoked": True}},
            )
            return res.modified_count > 0 or res.matched_count > 0
        except PyMongoError:
            logger.exception("Error revoking session")
            return False

    def close(self):
        """Close MongoDB connection."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self.is_connected = False
