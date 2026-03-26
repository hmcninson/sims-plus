"""
SIMS Plus - User Service

Business logic for user management.
"""

import csv
import io
import re
import secrets
import string
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.school import School
from app.models.user import User, UserRole, UserStatus
from app.models.user_school import UserSchool
from app.utils.sanitize import escape_ilike

logger = structlog.get_logger()

# Basic email format validation
_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Staff roles allowed for CSV import (no platform_admin, chain_admin, parent, student, applicant)
IMPORTABLE_ROLES = frozenset({
    "school_admin",
    "academic_head",
    "finance_officer",
    "hr_officer",
    "teacher",
    "house_parent",
    "transport_officer",
})

MAX_IMPORT_ROWS = 200

# Characters for temp password generation — includes letters, digits, and safe specials
_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*"


class UserServiceError(Exception):
    """User service error."""

    def __init__(self, message: str, code: str = "user_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class UserService:
    """Service for user management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_users(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        role: Optional[UserRole] = None,
        status: Optional[UserStatus] = None,
        school_id: Optional[UUID] = None,
    ) -> tuple[list[User], int]:
        """
        List users with pagination and filters.

        Returns:
            Tuple of (users, total_count)
        """
        query = select(User).where(
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None),
        )

        # Apply filters
        if search:
            # Escape ILIKE wildcards to prevent wildcard injection
            search_pattern = f"%{escape_ilike(search)}%"
            query = query.where(
                (User.first_name.ilike(search_pattern))
                | (User.last_name.ilike(search_pattern))
                | (User.email.ilike(search_pattern))
            )

        if role:
            query = query.where(User.role == role)

        if status:
            query = query.where(User.status == status)

        if school_id:
            query = query.where(User.school_id == school_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order_by(User.created_at.desc()).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        users = list(result.scalars().all())

        return users, total

    async def get_user(self, user_id: UUID, tenant_id: UUID) -> Optional[User]:
        """Get a single user by ID."""
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str, tenant_id: UUID) -> Optional[User]:
        """Get a user by email within a tenant."""
        result = await self.db.execute(
            select(User).where(
                User.email == email.lower(),
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        tenant_id: UUID,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        role: UserRole = UserRole.TEACHER,
        phone: Optional[str] = None,
        school_id: Optional[UUID] = None,
        status: UserStatus = UserStatus.ACTIVE,
        email_verified: bool = False,
    ) -> User:
        """
        Create a new user.

        Args:
            tenant_id: Tenant UUID
            email: User email (must be unique)
            password: Plain text password (will be hashed)
            first_name: User's first name
            last_name: User's last name
            role: User role (defaults to TEACHER)
            phone: Optional phone number
            school_id: Optional school association
            status: Initial status (defaults to ACTIVE for admin-created users)
            email_verified: Whether email is pre-verified

        Returns:
            Created User object

        Raises:
            UserServiceError: If email already exists
            LimitExceededError: If user account limit is reached
        """
        # Check plan limit before creating (raises LimitExceededError if exceeded)
        from app.services.subscription import SubscriptionService
        sub_service = SubscriptionService(self.db)
        await sub_service.check_user_limit(tenant_id)

        # Check if email already exists
        existing = await self.get_user_by_email(email, tenant_id)
        if existing:
            raise UserServiceError(
                message="A user with this email already exists",
                code="email_exists",
            )

        # Create user
        user = User(
            tenant_id=tenant_id,
            email=email.lower(),
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role=role,
            status=status,
            school_id=school_id,
            email_verified=email_verified,
        )

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def update_user(
        self,
        user_id: UUID,
        tenant_id: UUID,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        role: Optional[UserRole] = None,
        status: Optional[UserStatus] = None,
        school_id: Optional[UUID] = None,
    ) -> Optional[User]:
        """
        Update a user.

        Returns:
            Updated User object or None if not found
        """
        user = await self.get_user(user_id, tenant_id)
        if not user:
            return None

        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if phone is not None:
            user.phone = phone
        if role is not None:
            user.role = role
        if status is not None:
            user.status = status
        if school_id is not None:
            user.school_id = school_id

        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def update_user_role(
        self,
        user_id: UUID,
        tenant_id: UUID,
        role: UserRole,
    ) -> Optional[User]:
        """Update a user's role."""
        user = await self.get_user(user_id, tenant_id)
        if not user:
            return None

        user.role = role
        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def update_user_status(
        self,
        user_id: UUID,
        tenant_id: UUID,
        status: UserStatus,
    ) -> Optional[User]:
        """Update a user's status."""
        user = await self.get_user(user_id, tenant_id)
        if not user:
            return None

        user.status = status
        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def reset_user_password(
        self,
        user_id: UUID,
        tenant_id: UUID,
        new_password: str,
    ) -> Optional[User]:
        """
        Reset a user's password (admin action).

        Returns:
            Updated User object or None if not found
        """
        user = await self.get_user(user_id, tenant_id)
        if not user:
            return None

        user.password_hash = hash_password(new_password)
        user.failed_login_attempts = 0
        user.locked_until = None

        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def delete_user(self, user_id: UUID, tenant_id: UUID) -> bool:
        """
        Soft delete a user.

        Returns:
            True if deleted, False if not found
        """
        user = await self.get_user(user_id, tenant_id)
        if not user:
            return False

        # Soft delete
        from datetime import datetime, UTC
        user.deleted_at = datetime.now(UTC)
        user.status = UserStatus.DEACTIVATED

        await self.db.flush()

        return True

    async def count_users_by_role(self, tenant_id: UUID) -> dict[str, int]:
        """Get count of users grouped by role."""
        result = await self.db.execute(
            select(User.role, func.count(User.id))
            .where(
                User.tenant_id == tenant_id,
                User.deleted_at.is_(None),
            )
            .group_by(User.role)
        )

        counts = {role.value: 0 for role in UserRole}
        for role, count in result.all():
            counts[role.value] = count

        return counts

    # =========================================================================
    # Bulk CSV Import
    # =========================================================================

    async def import_users_from_file(
        self,
        tenant_id: UUID,
        school_id: Optional[UUID],
        file_content: bytes,
        preview_only: bool = False,
        created_by_id: Optional[UUID] = None,
    ) -> dict:
        """
        Import users from a CSV file.

        CSV columns: email (req), first_name (req), last_name (req), role (req), phone (opt).

        In preview mode, validates all rows without creating users. In create mode,
        bulk-creates valid users with PENDING status and auto-generated temp passwords.

        Returns a dict with total, valid, created, errors, preview, and credentials.
        """
        # --- 1. Parse CSV (utf-8-sig handles BOM from Excel) ---
        try:
            text_content = file_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise UserServiceError(
                "File encoding not supported. Please save as UTF-8 CSV.",
                "invalid_encoding",
            )

        reader = csv.DictReader(io.StringIO(text_content))

        # --- 2. Validate header row ---
        if reader.fieldnames is None:
            raise UserServiceError("CSV file is empty or has no header row", "empty_file")

        # Normalize headers (strip whitespace, lowercase)
        normalized_headers = {h.strip().lower() for h in reader.fieldnames}
        required_columns = {"email", "first_name", "last_name", "role"}
        missing = required_columns - normalized_headers
        if missing:
            raise UserServiceError(
                f"Missing required columns: {', '.join(sorted(missing))}",
                "missing_columns",
            )

        # --- 3. Read rows and enforce max limit ---
        rows = list(reader)
        if not rows:
            raise UserServiceError("CSV file contains no data rows", "empty_file")

        if len(rows) > MAX_IMPORT_ROWS:
            raise UserServiceError(
                f"Maximum {MAX_IMPORT_ROWS} rows per import (file has {len(rows)})",
                "import_limit_exceeded",
            )

        # --- 4. Check subscription limit before processing ---
        # Only check in create mode to avoid blocking previews unnecessarily
        if not preview_only:
            from app.services.subscription import SubscriptionService, LimitExceededError
            sub_service = SubscriptionService(self.db)
            # Pre-check with max possible users (actual valid count determined below,
            # but we'll re-check after validation)

        # --- 5. Validate each row ---
        preview = []
        errors = []
        valid_rows = []
        seen_emails: set[str] = set()

        for i, row in enumerate(rows, start=2):  # Row 1 is the header
            row_errors: list[str] = []

            email = (row.get("email") or "").strip().lower()
            first_name = (row.get("first_name") or "").strip()
            last_name = (row.get("last_name") or "").strip()
            role = (row.get("role") or "").strip().lower()
            phone = (row.get("phone") or "").strip() or None

            # Required field checks
            if not email:
                row_errors.append("Email is required")
            elif not _EMAIL_PATTERN.match(email):
                row_errors.append("Invalid email format")
            elif email in seen_emails:
                row_errors.append("Duplicate email in file")

            if not first_name:
                row_errors.append("First name is required")
            elif len(first_name) > 100:
                row_errors.append("First name must be 100 characters or less")

            if not last_name:
                row_errors.append("Last name is required")
            elif len(last_name) > 100:
                row_errors.append("Last name must be 100 characters or less")

            if not role:
                row_errors.append("Role is required")
            elif role not in IMPORTABLE_ROLES:
                row_errors.append(
                    f"Invalid role. Must be one of: {', '.join(sorted(IMPORTABLE_ROLES))}"
                )

            # Check email uniqueness in database (skip if already has errors)
            if email and not row_errors:
                existing = await self.db.execute(
                    select(User.id).where(
                        User.email == email,
                        # Defense-in-depth: always scope by tenant_id
                        User.tenant_id == tenant_id,
                        User.deleted_at.is_(None),
                    )
                )
                if existing.scalar_one_or_none():
                    row_errors.append("Email already exists in this school")

            seen_emails.add(email)

            is_valid = len(row_errors) == 0
            preview.append({
                "row_number": i,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "role": role,
                "phone": phone,
                "valid": is_valid,
                "errors": row_errors,
            })

            if is_valid:
                valid_rows.append({
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": role,
                    "phone": phone,
                })

            for err in row_errors:
                errors.append({"row": i, "field": "row", "error": err})

        # --- 6. Preview mode: return validation results without creating users ---
        if preview_only:
            return {
                "total": len(rows),
                "valid": len(valid_rows),
                "created": 0,
                "errors": errors,
                "preview": preview,
                "credentials": None,
            }

        # --- 7. Check subscription limit with actual valid count ---
        if valid_rows:
            from app.services.subscription import SubscriptionService, LimitExceededError
            sub_service = SubscriptionService(self.db)
            try:
                await sub_service.check_user_limit(tenant_id, additional=len(valid_rows))
            except LimitExceededError:
                raise UserServiceError(
                    f"Cannot import {len(valid_rows)} users: would exceed your plan's user limit. "
                    "Upgrade your subscription or reduce the number of users.",
                    "user_limit_exceeded",
                )

        # --- 8. Create users ---
        credentials = []
        created_count = 0

        for row_data in valid_rows:
            # Generate 16-char temporary password that guarantees all 4 character
            # classes required by the password policy (random selection alone
            # does not guarantee at least one from each class)
            password_chars = [
                secrets.choice(string.ascii_uppercase),
                secrets.choice(string.ascii_lowercase),
                secrets.choice(string.digits),
                secrets.choice("!@#$%^&*"),
            ]
            password_chars += [
                secrets.choice(_PASSWORD_ALPHABET) for _ in range(12)
            ]
            secrets.SystemRandom().shuffle(password_chars)
            temp_password = "".join(password_chars)

            user = User(
                tenant_id=tenant_id,
                school_id=school_id,
                email=row_data["email"],
                first_name=row_data["first_name"],
                last_name=row_data["last_name"],
                role=UserRole(row_data["role"]),
                phone=row_data["phone"],
                password_hash=hash_password(temp_password),
                status=UserStatus.PENDING,
                email_verified=False,
            )
            self.db.add(user)
            credentials.append({
                "email": row_data["email"],
                "temporary_password": temp_password,
            })
            created_count += 1

        await self.db.flush()

        logger.info(
            "bulk_user_import_complete",
            tenant_id=str(tenant_id),
            total=len(rows),
            valid=len(valid_rows),
            created=created_count,
            errors=len(errors),
            created_by=str(created_by_id) if created_by_id else None,
        )

        return {
            "total": len(rows),
            "valid": len(valid_rows),
            "created": created_count,
            "errors": errors,
            "preview": preview,
            "credentials": credentials,
        }

    async def get_user_school_roles(
        self,
        tenant_id: UUID,
        user_id: UUID,
    ) -> list[dict]:
        """Return the schools and roles for a user within their tenant.

        For single-school tenants with no user_schools entries, falls back
        to returning the single school from the schools table.
        """
        # Defense-in-depth: filter by tenant_id even though RLS handles isolation
        result = await self.db.execute(
            select(
                UserSchool.school_id,
                School.name.label("school_name"),
                UserSchool.role_at_school,
                UserSchool.is_primary,
                UserSchool.is_active,
            )
            .join(School, UserSchool.school_id == School.id)
            .where(UserSchool.tenant_id == tenant_id)
            .where(UserSchool.user_id == user_id)
            .where(School.deleted_at.is_(None))
            .order_by(UserSchool.is_primary.desc(), School.name)
        )
        rows = result.all()

        if rows:
            return [
                {
                    "school_id": row.school_id,
                    "school_name": row.school_name,
                    "role_at_school": row.role_at_school,
                    "is_primary": row.is_primary,
                    "is_active": row.is_active,
                }
                for row in rows
            ]

        # Fallback for single-school tenants without user_schools entries:
        # return the lone active school in the tenant.
        school_result = await self.db.execute(
            select(School.id, School.name)
            .where(School.tenant_id == tenant_id)
            .where(School.deleted_at.is_(None))
            .where(School.is_active.is_(True))
            .limit(1)
        )
        school = school_result.first()
        if school:
            return [
                {
                    "school_id": school.id,
                    "school_name": school.name,
                    "role_at_school": None,
                    "is_primary": True,
                    "is_active": True,
                }
            ]

        return []
