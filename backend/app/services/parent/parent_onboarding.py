"""
SIMS Plus - Parent Onboarding Service

Handles parent account creation, invitation, and profile completion.

The parent-to-student link is established through email matching:
  User.email == Guardian.email (within the same tenant).
When a parent account is created, the User email is set to match the
Guardian email, so the existing parent service's email-based resolution
continues to work seamlessly.
"""

import secrets
import string
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password
from app.models.parent import ParentNotificationPreference
from app.models.school import School
from app.models.student import Guardian, Student, StudentGuardian, GuardianRelationship
from app.models.tenant import Tenant
from app.models.user import User, UserRole, UserStatus
from app.services.email import email_service
from app.services.parent._shared import ParentServiceError

logger = structlog.get_logger()


class ParentOnboardingService:
    """
    Handles parent account creation, invitation, and profile completion.

    Supports single-student and bulk invitation workflows. Deduplicates
    by email so the same parent can be linked to multiple children without
    creating duplicate user accounts.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Public Methods
    # =========================

    async def create_parent_for_student(
        self,
        student_id: UUID,
        guardian_data: dict,
        tenant_id: UUID,
        school_id: UUID,
        invited_by: UUID,
    ) -> User:
        """
        Create a parent user account and link it to a student.

        Flow:
        1. Validate the student exists and belongs to this tenant.
        2. Check if a user with this email already exists in this tenant.
           a. If exists AND is a parent: create student_guardian link (additional child).
           b. If exists AND is NOT a parent: raise error (email belongs to staff/admin).
        3. If no user exists:
           a. Find or create a Guardian record (matched by email within tenant).
           b. Create User with role=PARENT, status=PENDING, matching guardian email.
           c. Create StudentGuardian link.
           d. Send invitation email with temporary password.
        4. Return the user.

        Args:
            student_id: Student to link the parent to
            guardian_data: Dict with keys: first_name, last_name, email (required),
                          phone, relationship (GuardianRelationship value string),
                          is_primary (bool), plus optional guardian fields
            tenant_id: Tenant UUID for multi-tenant scoping
            school_id: School UUID for the invitation context
            invited_by: UUID of the admin/teacher creating this invitation

        Returns:
            The parent User (newly created or existing)

        Raises:
            ParentServiceError: If validation fails or email conflicts with non-parent role
        """
        email = guardian_data.get("email")
        if not email:
            raise ParentServiceError(
                "Email is required to create a parent account",
                code="email_required",
            )
        email = email.strip().lower()

        # Validate student exists within tenant
        student = await self._get_student(tenant_id, student_id)
        if not student:
            raise ParentServiceError("Student not found", code="student_not_found")

        # Check if a user with this email already exists in this tenant
        existing_user = await self._get_user_by_email(email, tenant_id)

        if existing_user:
            if existing_user.role != UserRole.PARENT:
                raise ParentServiceError(
                    "This email address belongs to an existing staff or admin account. "
                    "Please use a different email for the parent invitation.",
                    code="email_role_conflict",
                )

            # Parent user exists -- just ensure guardian + link exist
            guardian = await self._find_or_create_guardian(
                tenant_id=tenant_id,
                email=email,
                first_name=guardian_data.get("first_name", existing_user.first_name),
                last_name=guardian_data.get("last_name", existing_user.last_name),
                phone=guardian_data.get("phone", existing_user.phone),
                extra_fields=guardian_data,
            )
            await self._ensure_student_guardian_link(
                tenant_id=tenant_id,
                student_id=student_id,
                guardian_id=guardian.id,
                relationship=guardian_data.get("relationship", "guardian"),
                is_primary=guardian_data.get("is_primary", False),
            )

            logger.info(
                "parent_child_linked",
                user_id=str(existing_user.id),
                student_id=str(student_id),
                email=email,
            )
            return existing_user

        # No existing user -- create guardian, user, and link
        guardian = await self._find_or_create_guardian(
            tenant_id=tenant_id,
            email=email,
            first_name=guardian_data["first_name"],
            last_name=guardian_data["last_name"],
            phone=guardian_data.get("phone", ""),
            extra_fields=guardian_data,
        )

        temp_password = self._generate_temp_password()

        user = User(
            email=email,
            password_hash=hash_password(temp_password),
            first_name=guardian_data["first_name"],
            last_name=guardian_data["last_name"],
            phone=guardian_data.get("phone"),
            tenant_id=tenant_id,
            school_id=school_id,
            role=UserRole.PARENT,
            # PENDING until the parent logs in and sets their own password
            status=UserStatus.PENDING,
            email_verified=False,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        await self._ensure_student_guardian_link(
            tenant_id=tenant_id,
            student_id=student_id,
            guardian_id=guardian.id,
            relationship=guardian_data.get("relationship", "guardian"),
            is_primary=guardian_data.get("is_primary", False),
        )

        # Look up tenant/school info for the invitation email
        tenant_subdomain = await self._get_tenant_subdomain(tenant_id)
        school_name = await self._get_school_name(tenant_id, school_id)

        await self._send_parent_invitation(
            user=user,
            temp_password=temp_password,
            tenant_subdomain=tenant_subdomain,
            school_name=school_name,
        )

        logger.info(
            "parent_account_created",
            user_id=str(user.id),
            student_id=str(student_id),
            email=email,
            invited_by=str(invited_by),
        )
        return user

    async def bulk_create_parents(
        self,
        invitations: list[dict],
        tenant_id: UUID,
        school_id: UUID,
        invited_by: UUID,
    ) -> dict:
        """
        Batch invite parents for multiple students.

        Deduplicates by email: if the same email appears for multiple students,
        one user account is created and multiple student_guardian links are made.

        Each invitation dict must contain:
            student_id (UUID), email (str), first_name (str), last_name (str),
            phone (str, optional), relationship (str, optional),
            is_primary (bool, optional)

        Args:
            invitations: List of invitation dicts
            tenant_id: Tenant UUID
            school_id: School UUID
            invited_by: UUID of the admin creating these invitations

        Returns:
            Dict with keys: created (int), linked (int), errors (list[dict])
            - created: number of new parent accounts created
            - linked: number of additional child links added to existing parents
            - errors: list of {index, email, error} for failed invitations
        """
        created = 0
        linked = 0
        errors: list[dict] = []

        # Group by email to avoid redundant DB lookups for the same parent
        email_to_indices: dict[str, list[int]] = {}
        for idx, invitation in enumerate(invitations):
            email = (invitation.get("email") or "").strip().lower()
            if not email:
                errors.append({
                    "index": idx,
                    "email": "",
                    "error": "Email is required",
                })
                continue
            email_to_indices.setdefault(email, []).append(idx)

        # Pre-fetch tenant and school info once (avoids N queries)
        tenant_subdomain = await self._get_tenant_subdomain(tenant_id)
        school_name = await self._get_school_name(tenant_id, school_id)

        # Track which emails we have already processed in this batch
        # to avoid re-creating users for duplicate emails within the same request
        processed_users: dict[str, User] = {}

        for email, indices in email_to_indices.items():
            for idx in indices:
                invitation = invitations[idx]
                try:
                    if email in processed_users:
                        # We already created or found the user in this batch --
                        # just add the student_guardian link
                        user = processed_users[email]
                        student_id = UUID(str(invitation["student_id"]))

                        student = await self._get_student(tenant_id, student_id)
                        if not student:
                            errors.append({
                                "index": idx,
                                "email": email,
                                "error": "Student not found",
                            })
                            continue

                        guardian = await self._find_or_create_guardian(
                            tenant_id=tenant_id,
                            email=email,
                            first_name=invitation.get("first_name", user.first_name),
                            last_name=invitation.get("last_name", user.last_name),
                            phone=invitation.get("phone", user.phone or ""),
                            extra_fields=invitation,
                        )
                        await self._ensure_student_guardian_link(
                            tenant_id=tenant_id,
                            student_id=student_id,
                            guardian_id=guardian.id,
                            relationship=invitation.get("relationship", "guardian"),
                            is_primary=invitation.get("is_primary", False),
                        )
                        linked += 1
                    else:
                        # First time seeing this email in the batch --
                        # delegate to the single-student method
                        user = await self.create_parent_for_student(
                            student_id=UUID(str(invitation["student_id"])),
                            guardian_data={
                                "email": email,
                                "first_name": invitation["first_name"],
                                "last_name": invitation["last_name"],
                                "phone": invitation.get("phone"),
                                "relationship": invitation.get("relationship", "guardian"),
                                "is_primary": invitation.get("is_primary", False),
                            },
                            tenant_id=tenant_id,
                            school_id=school_id,
                            invited_by=invited_by,
                        )
                        processed_users[email] = user

                        # Determine if this was a new creation or a link to existing
                        existing_user = await self._get_user_by_email(email, tenant_id)
                        if existing_user and existing_user.id == user.id:
                            # If the user's status is PENDING, it was freshly created
                            if user.status == UserStatus.PENDING:
                                created += 1
                            else:
                                linked += 1
                        else:
                            created += 1

                except ParentServiceError as e:
                    errors.append({
                        "index": idx,
                        "email": email,
                        "error": e.message,
                    })
                except Exception:
                    logger.exception(
                        "bulk_parent_invite_unexpected_error",
                        index=idx,
                        email=email,
                    )
                    errors.append({
                        "index": idx,
                        "email": email,
                        "error": "An unexpected error occurred",
                    })

        logger.info(
            "bulk_parent_invite_complete",
            tenant_id=str(tenant_id),
            invited_by=str(invited_by),
            created=created,
            linked=linked,
            error_count=len(errors),
        )

        return {"created": created, "linked": linked, "errors": errors}

    async def complete_profile(
        self,
        user_id: UUID,
        tenant_id: UUID,
        data: dict,
    ) -> None:
        """
        Complete parent profile after first login.

        Updates the user's phone number and creates default notification
        preferences if they do not already exist.

        Args:
            user_id: The parent user's ID
            tenant_id: Tenant UUID for multi-tenant scoping
            data: Dict with optional keys: phone (str), timezone (str)

        Raises:
            ParentServiceError: If user not found or not a parent
        """
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.id == user_id,
                    User.tenant_id == tenant_id,
                    User.deleted_at.is_(None),
                )
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ParentServiceError("User not found", code="user_not_found")

        if user.role != UserRole.PARENT:
            raise ParentServiceError(
                "Only parent accounts can complete parent profile",
                code="not_a_parent",
            )

        # Update phone if provided
        if data.get("phone"):
            user.phone = data["phone"]

        # Update timezone if provided
        if data.get("timezone"):
            user.timezone = data["timezone"]

        # Mark email as verified and activate the account on first profile completion
        if user.status == UserStatus.PENDING:
            user.status = UserStatus.ACTIVE
            user.email_verified = True
            user.email_verified_at = datetime.now(UTC)

        await self.db.flush()

        # Create default notification preferences if they do not exist
        existing_prefs = await self.db.execute(
            select(ParentNotificationPreference).where(
                and_(
                    ParentNotificationPreference.user_id == user_id,
                    ParentNotificationPreference.tenant_id == tenant_id,
                )
            )
        )
        if not existing_prefs.scalar_one_or_none():
            prefs = ParentNotificationPreference(
                tenant_id=tenant_id,
                user_id=user_id,
                # Defaults from the model: email=True, sms=False, push=False
                # All category notifications enabled by default
            )
            self.db.add(prefs)
            await self.db.flush()

        logger.info(
            "parent_profile_completed",
            user_id=str(user_id),
            tenant_id=str(tenant_id),
        )

    # =========================
    # Private Helper Methods
    # =========================

    async def _send_parent_invitation(
        self,
        user: User,
        temp_password: str,
        tenant_subdomain: str,
        school_name: str,
    ) -> None:
        """
        Send invitation email to a parent with their temporary credentials.

        Best-effort: logs warning on failure but does not raise. The parent
        account is still created even if the email fails.
        """
        if settings.is_production:
            portal_url = f"https://{tenant_subdomain}.simsplus.io"
        else:
            portal_url = "http://localhost:3000"

        try:
            await email_service.send_user_invite(
                to_email=user.email,
                inviter_name=school_name,
                school_name=school_name,
                temp_password=temp_password,
                role="Parent",
                portal_url=portal_url,
            )
        except Exception:
            # Never let email failure block account creation
            logger.warning(
                "parent_invitation_email_failed",
                user_id=str(user.id),
                email=user.email,
                exc_info=True,
            )

    async def _get_student(
        self, tenant_id: UUID, student_id: UUID
    ) -> Optional[Student]:
        """Get a student by ID within a tenant."""
        result = await self.db.execute(
            select(Student).where(
                and_(
                    # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                    Student.tenant_id == tenant_id,
                    Student.id == student_id,
                    Student.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def _get_user_by_email(
        self, email: str, tenant_id: UUID
    ) -> Optional[User]:
        """Get a user by email within a tenant."""
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.email == email.lower(),
                    User.tenant_id == tenant_id,
                    User.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def _find_or_create_guardian(
        self,
        tenant_id: UUID,
        email: str,
        first_name: str,
        last_name: str,
        phone: str,
        extra_fields: Optional[dict] = None,
    ) -> Guardian:
        """
        Find an existing guardian by email within the tenant, or create one.

        If a guardian with this email already exists (and is not soft-deleted),
        return it without modifying it. Otherwise create a new guardian record.
        """
        result = await self.db.execute(
            select(Guardian).where(
                and_(
                    Guardian.tenant_id == tenant_id,
                    Guardian.email == email.lower(),
                    Guardian.deleted_at.is_(None),
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        extra = extra_fields or {}
        guardian = Guardian(
            tenant_id=tenant_id,
            first_name=first_name,
            last_name=last_name,
            phone=phone or "",
            email=email.lower(),
            phone_secondary=extra.get("phone_secondary"),
            address=extra.get("address"),
            city=extra.get("city"),
            region=extra.get("region"),
            occupation=extra.get("occupation"),
            workplace=extra.get("workplace"),
            work_phone=extra.get("work_phone"),
        )
        self.db.add(guardian)
        await self.db.flush()
        await self.db.refresh(guardian)
        return guardian

    async def _ensure_student_guardian_link(
        self,
        tenant_id: UUID,
        student_id: UUID,
        guardian_id: UUID,
        relationship: str = "guardian",
        is_primary: bool = False,
    ) -> StudentGuardian:
        """
        Create a student_guardian link if one does not already exist.

        If the link exists, return the existing one. If is_primary is True
        and other primary guardians exist for this student, unset them first.
        """
        # Check for existing link
        result = await self.db.execute(
            select(StudentGuardian).where(
                and_(
                    StudentGuardian.tenant_id == tenant_id,
                    StudentGuardian.student_id == student_id,
                    StudentGuardian.guardian_id == guardian_id,
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        # Unset other primary guardians if this one is marked primary
        if is_primary:
            await self._unset_primary_guardians(tenant_id, student_id)

        # Parse the relationship string into the enum
        try:
            relation_enum = GuardianRelationship(relationship)
        except ValueError:
            relation_enum = GuardianRelationship.GUARDIAN

        link = StudentGuardian(
            tenant_id=tenant_id,
            student_id=student_id,
            guardian_id=guardian_id,
            relation_type=relation_enum,
            is_primary=is_primary,
            is_emergency_contact=True,
            can_pickup=True,
        )
        self.db.add(link)
        await self.db.flush()
        await self.db.refresh(link)
        return link

    async def _unset_primary_guardians(
        self, tenant_id: UUID, student_id: UUID
    ) -> None:
        """Unset is_primary on all guardians of a student."""
        result = await self.db.execute(
            select(StudentGuardian).where(
                and_(
                    StudentGuardian.tenant_id == tenant_id,
                    StudentGuardian.student_id == student_id,
                    StudentGuardian.is_primary == True,  # noqa: E712
                )
            )
        )
        for link in result.scalars().all():
            link.is_primary = False

    async def _get_tenant_subdomain(self, tenant_id: UUID) -> str:
        """Get the subdomain for a tenant."""
        result = await self.db.execute(
            select(Tenant.subdomain).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none() or ""

    async def _get_school_name(
        self, tenant_id: UUID, school_id: UUID
    ) -> str:
        """Get the school name, falling back to tenant name if not found."""
        result = await self.db.execute(
            select(School.name).where(
                and_(
                    School.id == school_id,
                    School.tenant_id == tenant_id,
                    School.deleted_at.is_(None),
                )
            )
        )
        school_name = result.scalar_one_or_none()
        if school_name:
            return school_name

        # Fallback to tenant name
        result = await self.db.execute(
            select(Tenant.name).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none() or "Your School"

    @staticmethod
    def _generate_temp_password() -> str:
        """Generate a cryptographically secure temporary password (16 chars)."""
        alphabet = string.ascii_letters + string.digits + "!@#$%&*"
        return "".join(secrets.choice(alphabet) for _ in range(16))
