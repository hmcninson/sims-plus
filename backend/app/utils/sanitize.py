"""
Input sanitization utilities for SIMS Plus.

IMPORTANT: All user input used in ILIKE queries MUST be sanitized
through escape_ilike() to prevent wildcard injection attacks.

IMPORTANT: All file uploads MUST be validated with validate_file_magic()
to prevent Content-Type spoofing attacks.
"""


def escape_ilike(value: str) -> str:
    """Escape special ILIKE characters in user input.

    PostgreSQL ILIKE treats % and _ as wildcards. Without escaping,
    a user searching for "100%" would match any string starting with "100".

    Args:
        value: Raw user input string

    Returns:
        Escaped string safe for use in ILIKE patterns
    """
    # Escape backslash first (since it's the escape character)
    value = value.replace("\\", "\\\\")
    # Escape ILIKE wildcards
    value = value.replace("%", "\\%")
    value = value.replace("_", "\\_")
    return value


# Magic byte signatures for supported image types.
# Client-controlled Content-Type headers cannot be trusted, so we verify
# actual file content against known binary signatures.
MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    "image/png": [b"\x89PNG"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/webp": [b"RIFF"],  # Additional check: bytes 8-12 must be b"WEBP"
    "image/gif": [b"GIF87a", b"GIF89a"],
}


def validate_file_magic(content: bytes, claimed_type: str) -> bool:
    """Verify file content matches claimed MIME type via magic byte inspection.

    Prevents Content-Type spoofing where an attacker sets a legitimate
    image MIME type but uploads a malicious file (e.g., HTML, executable).

    Args:
        content: Raw file bytes (only the first ~12 bytes are inspected)
        claimed_type: The MIME type declared by the client (e.g., "image/png")

    Returns:
        True if magic bytes match the claimed type, False otherwise
    """
    sigs = MAGIC_SIGNATURES.get(claimed_type)
    if not sigs:
        return False

    for sig in sigs:
        if content[: len(sig)] == sig:
            # WEBP has a two-part signature: starts with "RIFF" and bytes 8-12 == "WEBP"
            if claimed_type == "image/webp":
                return content[8:12] == b"WEBP"
            return True

    return False
