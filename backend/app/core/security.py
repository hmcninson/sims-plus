"""
SIMS Plus - Security Utilities

Password hashing, JWT token creation/validation, and security helpers.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import jwt

from app.config import settings

# Password hasher using Argon2id (as per security policy)
password_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
)


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2id.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored password hash

    Returns:
        True if password matches, False otherwise
    """
    try:
        password_hasher.verify(hashed_password, plain_password)
        return True
    except VerifyMismatchError:
        return False


def create_access_token(
    subject: str,
    tenant_id: str | None = None,
    school_id: str | None = None,
    role: str | None = None,
    permissions: list[str] | None = None,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        subject: Token subject (usually user ID)
        tenant_id: Tenant ID for multi-tenant context
        school_id: School ID for school-scoped access
        role: User role for RBAC
        permissions: List of permission strings
        expires_delta: Custom expiration time
        extra_claims: Additional claims to include

    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": str(uuid4()),  # Unique ID prevents identical tokens within same second
        "type": "access",
    }

    if tenant_id:
        to_encode["tenant_id"] = tenant_id

    if school_id:
        to_encode["school_id"] = school_id

    if role:
        to_encode["role"] = role

    if permissions:
        to_encode["permissions"] = permissions

    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    subject: str,
    tenant_id: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT refresh token.

    Args:
        subject: Token subject (usually user ID)
        tenant_id: Tenant ID for cross-tenant validation
        expires_delta: Custom expiration time

    Returns:
        Encoded JWT refresh token string
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

    to_encode: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": str(uuid4()),  # Unique ID prevents identical tokens within same second
        "type": "refresh",
    }

    if tenant_id:
        to_encode["tenant_id"] = tenant_id

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        JWTError: If token is invalid or expired
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
