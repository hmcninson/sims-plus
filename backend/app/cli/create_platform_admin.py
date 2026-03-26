"""
CLI command to create a platform admin user.

Usage:
    python -m app.cli.create_platform_admin \
        --email admin@simsplus.io \
        --first-name Harry \
        --last-name McNinson

The password will be prompted interactively (not passed as argument).

This script:
1. Connects to the database using the same DATABASE_URL as the app
2. Sets tenant context to the platform tenant UUID
3. Creates a User with role=platform_admin, tenant_id=<platform_tenant_id>
4. The user is created with status=ACTIVE and email_verified=True
   (platform admins are created by operators, not self-registered)
5. MFA is NOT enabled on creation -- the platform login endpoint
   will enforce MFA setup on first login

Requirements:
- The platform tenant must already exist (run migration first)
- The email must not already be in use within the platform tenant
"""

import argparse
import asyncio
import getpass
import re
import sys

from sqlalchemy import select, text

from app.config import settings
from app.core.security import hash_password
from app.db.session import async_session_maker
from app.models.user import User, UserRole, UserStatus


# Must contain uppercase, lowercase, digit, and special character
PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{}|;:,.<>?])"
)

MIN_PASSWORD_LENGTH = 8


def validate_password(password: str) -> str | None:
    """Validate password meets policy requirements.

    Returns None if valid, or an error message string if invalid.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if not PASSWORD_PATTERN.match(password):
        return (
            "Password must include at least one uppercase letter, "
            "one lowercase letter, one digit, and one special character."
        )
    return None


async def create_platform_admin(
    email: str,
    first_name: str,
    last_name: str,
    password: str,
) -> None:
    """Create a platform admin user in the database."""
    platform_tenant_id = settings.PLATFORM_TENANT_ID

    async with async_session_maker() as session:
        # 1. Verify platform tenant exists
        result = await session.execute(
            text("SELECT id FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": platform_tenant_id},
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            print("ERROR: Platform tenant not found. Run migrations first:")
            print("  alembic upgrade head")
            sys.exit(1)

        # 2. Set tenant context so RLS allows the INSERT
        await session.execute(
            text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
            {"tid": platform_tenant_id},
        )

        # 3. Check email uniqueness within platform tenant
        result = await session.execute(
            select(User).where(
                User.email == email.lower(),
                User.tenant_id == platform_tenant_id,
                User.deleted_at.is_(None),
            )
        )
        if result.scalar_one_or_none():
            print(f"ERROR: A platform admin with email '{email}' already exists.")
            sys.exit(1)

        # 4. Create the user
        user = User(
            tenant_id=platform_tenant_id,
            email=email.lower(),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            password_hash=hash_password(password),
            role=UserRole.PLATFORM_ADMIN,
            status=UserStatus.ACTIVE,
            email_verified=True,
            mfa_enabled=False,  # MFA setup enforced on first login
        )
        session.add(user)
        await session.commit()

        print("Platform admin created successfully:")
        print(f"  Email:     {user.email}")
        print(f"  Name:      {first_name} {last_name}")
        print(f"  Tenant ID: {platform_tenant_id}")
        print(f"  Role:      platform_admin")
        print(f"  Status:    active")
        print()
        print("IMPORTANT: MFA setup will be required on first login.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a platform admin user for SIMS Plus"
    )
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--first-name", required=True, help="First name")
    parser.add_argument("--last-name", required=True, help="Last name")
    args = parser.parse_args()

    # Interactive password prompt -- never accept passwords as CLI arguments
    # to avoid leaking them in shell history or process listings
    while True:
        password = getpass.getpass("Password: ")
        error = validate_password(password)
        if error:
            print(error)
            continue

        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.")
            continue

        break

    asyncio.run(
        create_platform_admin(
            email=args.email,
            first_name=args.first_name,
            last_name=args.last_name,
            password=password,
        )
    )


if __name__ == "__main__":
    main()
