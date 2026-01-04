"""
SIMS Plus - Onboarding Service

Business logic for school registration and onboarding.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.tenant import Tenant, TenantType, SubscriptionTier
from app.models.school import School, SchoolType, SchoolStatus
from app.models.user import User, UserRole, UserStatus
from app.models.reserved_subdomain import ReservedSubdomain
from app.services.tenant import TenantService
from app.services.email import email_service

logger = logging.getLogger(__name__)


class OnboardingError(Exception):
    """Onboarding operation failed."""

    def __init__(self, message: str, code: str = "onboarding_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class OnboardingService:
    """Service for school registration and onboarding."""

    # Trial duration
    TRIAL_DAYS = 30

    # Max students by plan
    MAX_STUDENTS_BY_PLAN = {
        "trial": 100,
        "starter": 300,
        "professional": 1000,
        "enterprise": 10000,
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.tenant_service = TenantService(db)

    async def register_school(
        self,
        school_name: str,
        subdomain: str,
        school_type: str,
        admin_email: str,
        admin_first_name: str,
        admin_last_name: str,
        admin_password: str,
        admin_phone: Optional[str] = None,
        plan: str = "trial",
    ) -> Tuple[Tenant, School, User]:
        """
        Register a new school.

        Creates:
        1. Tenant (organization)
        2. School (within tenant)
        3. Admin user (school admin)

        Args:
            school_name: Official school name
            subdomain: Unique subdomain
            school_type: Type of school
            admin_email: Admin email
            admin_first_name: Admin first name
            admin_last_name: Admin last name
            admin_password: Admin password
            admin_phone: Optional admin phone
            plan: Subscription plan

        Returns:
            Tuple of (Tenant, School, User)

        Raises:
            OnboardingError: If registration fails
        """
        # Validate subdomain availability
        available, reason = await self.tenant_service.check_subdomain_availability(
            subdomain
        )
        if not available:
            raise OnboardingError(
                reason or "Subdomain is not available",
                code="subdomain_unavailable",
            )

        # Check email doesn't exist globally (for new registrations)
        existing_user = await self._check_email_exists(admin_email)
        if existing_user:
            raise OnboardingError(
                "An account with this email already exists. Please login to your existing school or use a different email.",
                code="email_exists",
            )

        # Map plan to subscription tier
        subscription_tier = self._map_plan_to_tier(plan)

        # Calculate trial end date
        trial_end = None
        if subscription_tier == SubscriptionTier.TRIAL:
            trial_end = datetime.now(UTC) + timedelta(days=self.TRIAL_DAYS)

        # Create tenant
        tenant = Tenant(
            name=school_name,
            subdomain=subdomain.lower(),
            slug=subdomain.lower(),
            tenant_type=TenantType.SINGLE_SCHOOL,
            subscription_tier=subscription_tier,
            subscription_start=datetime.now(UTC).date(),
            subscription_end=trial_end.date() if trial_end else None,
            max_students=self.MAX_STUDENTS_BY_PLAN.get(plan, 100),
            email=admin_email,
            phone=admin_phone,
            is_active=True,
            primary_color="#1B4F72",  # Default navy blue
        )
        self.db.add(tenant)
        await self.db.flush()

        # Create school
        school = School(
            tenant_id=tenant.id,
            name=school_name,
            slug=subdomain.lower(),
            school_type=SchoolType(school_type.lower()),
            status=SchoolStatus.ACTIVE,
            email=admin_email,
            phone=admin_phone,
            is_active=True,
        )
        self.db.add(school)
        await self.db.flush()

        # Create admin user
        admin_user = User(
            tenant_id=tenant.id,
            school_id=school.id,
            email=admin_email.lower(),
            password_hash=hash_password(admin_password),
            first_name=admin_first_name,
            last_name=admin_last_name,
            phone=admin_phone,
            role=UserRole.SCHOOL_ADMIN,
            status=UserStatus.ACTIVE,  # Auto-verify for initial admin
            email_verified=True,
            email_verified_at=datetime.now(UTC),
        )
        self.db.add(admin_user)
        await self.db.flush()

        # Refresh to get all fields
        await self.db.refresh(tenant)
        await self.db.refresh(school)
        await self.db.refresh(admin_user)

        # Send welcome email (non-blocking, don't fail registration if email fails)
        try:
            trial_ends_at = None
            if trial_end:
                trial_ends_at = trial_end

            await email_service.send_welcome_email(
                to_email=admin_email,
                admin_name=f"{admin_first_name} {admin_last_name}",
                school_name=school_name,
                subdomain=subdomain,
                trial_ends_at=trial_ends_at,
            )
            logger.info(f"Welcome email sent to {admin_email}")
        except Exception as e:
            # Log error but don't fail registration
            logger.error(f"Failed to send welcome email to {admin_email}: {e}")

        return tenant, school, admin_user

    async def get_portal_url(self, subdomain: str) -> str:
        """Get the portal URL for a subdomain."""
        # In production, use actual domain
        # For now, return the subdomain format
        return f"https://{subdomain}.simsplus.io"

    async def _check_email_exists(self, email: str) -> bool:
        """Check if email exists in any tenant."""
        result = await self.db.execute(
            select(User).where(
                User.email == email.lower(),
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none() is not None

    def _map_plan_to_tier(self, plan: str) -> SubscriptionTier:
        """Map plan string to SubscriptionTier enum."""
        mapping = {
            "trial": SubscriptionTier.TRIAL,
            "starter": SubscriptionTier.STARTER,
            "professional": SubscriptionTier.PROFESSIONAL,
            "enterprise": SubscriptionTier.ENTERPRISE,
        }
        return mapping.get(plan.lower(), SubscriptionTier.TRIAL)

    async def generate_subdomain_suggestions(
        self,
        school_name: str,
        count: int = 3,
    ) -> list[str]:
        """
        Generate subdomain suggestions based on school name.

        Args:
            school_name: School name to base suggestions on
            count: Number of suggestions to generate

        Returns:
            List of available subdomain suggestions
        """
        # Clean and process school name
        base = self._clean_subdomain(school_name)

        if len(base) < 4:
            base = base + "school"

        suggestions = []
        candidates = [
            base,
            base[:20],  # Truncated
            f"{base}gh",  # With Ghana suffix
            f"{base}edu",  # With edu suffix
        ]

        # Add numbered variants
        for i in range(1, 10):
            candidates.append(f"{base[:18]}{i}")

        for candidate in candidates:
            if len(suggestions) >= count:
                break

            if len(candidate) < 4 or len(candidate) > 63:
                continue

            available, _ = await self.tenant_service.check_subdomain_availability(
                candidate
            )
            if available:
                suggestions.append(candidate)

        return suggestions

    def _clean_subdomain(self, name: str) -> str:
        """Clean a name into a valid subdomain."""
        import re

        # Lowercase
        subdomain = name.lower()

        # Remove special characters
        subdomain = re.sub(r"[^a-z0-9\s-]", "", subdomain)

        # Replace spaces with nothing (merge words)
        subdomain = re.sub(r"\s+", "", subdomain)

        # Remove consecutive hyphens
        subdomain = re.sub(r"-+", "-", subdomain)

        # Remove leading/trailing hyphens
        subdomain = subdomain.strip("-")

        # Limit length
        return subdomain[:63]
