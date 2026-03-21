"""
SIMS Plus - Onboarding Service

Business logic for school registration and onboarding.
"""

from datetime import UTC, datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.middleware.tenant import set_db_tenant_context
from app.models.tenant import Tenant, TenantType, SubscriptionTier
from app.models.school import School, SchoolType, SchoolStatus, SchoolCategory, BoardingType
from app.models.user import User, UserRole, UserStatus
from app.models.reserved_subdomain import ReservedSubdomain
import structlog

from app.config import settings
from app.services.tenant import TenantService
from app.services.email import email_service
from app.services.email_verification import EmailVerificationService

logger = structlog.get_logger()


class OnboardingError(Exception):
    """Onboarding operation failed."""

    def __init__(self, message: str, code: str = "onboarding_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class OnboardingService:
    """Service for school registration and onboarding."""

    # Trial duration — read from settings for consistency across the app
    TRIAL_DAYS = settings.TRIAL_DAYS

    # Max students by plan
    MAX_STUDENTS_BY_PLAN = {
        "trial": 100,
        "starter": 300,
        "professional": 1000,
        "enterprise": 10000,
    }

    def __init__(self, db: AsyncSession, redis_client: Optional[aioredis.Redis] = None):
        self.db = db
        self.redis_client = redis_client
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
        tenant_type: str = "single_school",
        plan: str = "trial",
        school_category: Optional[str] = None,
        boarding_type: Optional[str] = None,
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
            tenant_type: Tenant type (single_school or school_chain)
            plan: Subscription plan
            school_category: Optional school category (public, private, etc.)
            boarding_type: Optional boarding type (day_only, boarding_only, mixed)

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

        # Map tenant_type string to enum (defaults to SINGLE_SCHOOL for safety)
        resolved_tenant_type = TenantType(tenant_type.lower()) if tenant_type else TenantType.SINGLE_SCHOOL

        # Create tenant
        tenant = Tenant(
            name=school_name,
            subdomain=subdomain.lower(),
            slug=subdomain.lower(),
            tenant_type=resolved_tenant_type,
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

        # CRITICAL: Set tenant context for RLS before inserting into tenant-scoped tables.
        # Without this, the hardened RLS WITH CHECK clause rejects the inserts
        # because tenant_id != get_current_tenant_id() (which would be NULL).
        await set_db_tenant_context(self.db, tenant.id)

        # Create school
        school = School(
            tenant_id=tenant.id,
            name=school_name,
            slug=subdomain.lower(),
            school_type=SchoolType(school_type.lower()),
            status=SchoolStatus.ACTIVE,
            category=SchoolCategory(school_category) if school_category else None,
            boarding_type=BoardingType(boarding_type) if boarding_type else None,
            email=admin_email,
            phone=admin_phone,
            is_active=True,
        )
        self.db.add(school)
        await self.db.flush()

        # Chain tenants get chain_admin role; single schools get school_admin
        admin_role = (
            UserRole.CHAIN_ADMIN
            if resolved_tenant_type == TenantType.SCHOOL_CHAIN
            else UserRole.SCHOOL_ADMIN
        )

        # Create admin user with PENDING status — requires email verification before login
        admin_user = User(
            tenant_id=tenant.id,
            school_id=school.id,
            email=admin_email.lower(),
            password_hash=hash_password(admin_password),
            first_name=admin_first_name,
            last_name=admin_last_name,
            phone=admin_phone,
            role=admin_role,
            status=UserStatus.PENDING,
            email_verified=False,
            email_verified_at=None,
        )
        self.db.add(admin_user)
        await self.db.flush()

        # Refresh to get all fields
        await self.db.refresh(tenant)
        await self.db.refresh(school)
        await self.db.refresh(admin_user)

        # Send verification email (non-blocking, don't fail registration if email fails)
        verification_sent = False
        try:
            verification_service = EmailVerificationService(
                self.db, redis_client=self.redis_client
            )
            token = await verification_service.create_verification_token(
                user_id=admin_user.id,
                tenant_id=tenant.id,
                email=admin_email.lower(),
            )
            if token:
                await verification_service.send_verification_email(
                    email=admin_email.lower(),
                    token=token,
                    subdomain=subdomain,
                    first_name=admin_first_name,
                )
                verification_sent = True
                logger.info("verification_email_sent", to=admin_email)
            else:
                # Redis unavailable -- token could not be created
                logger.warning(
                    "verification_token_creation_failed",
                    to=admin_email,
                    reason="redis_unavailable",
                )
        except Exception:
            # Log error but don't fail registration
            logger.error("verification_email_failed", to=admin_email, exc_info=True)

        # Fallback: if verification email could not be sent (Redis down, email
        # service failure, etc.), activate the user immediately so they are not
        # locked out with no way to verify. Email verification is a nice-to-have
        # layer for the initial admin, not a hard security gate.
        if not verification_sent:
            logger.warning(
                "email_verification_skipped_activating_user",
                user_id=str(admin_user.id),
                tenant_id=str(tenant.id),
                reason="verification_email_could_not_be_sent",
            )
            admin_user.status = UserStatus.ACTIVE
            admin_user.email_verified = True
            admin_user.email_verified_at = datetime.now(UTC)
            await self.db.flush()
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
            logger.info("welcome_email_sent", to=admin_email)
        except Exception:
            # Log error but don't fail registration
            logger.error("welcome_email_failed", to=admin_email, exc_info=True)

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
