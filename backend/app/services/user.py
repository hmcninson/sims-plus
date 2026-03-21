"""
SIMS Plus - User Service

Business logic for user management.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User, UserRole, UserStatus
from app.utils.sanitize import escape_ilike


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
