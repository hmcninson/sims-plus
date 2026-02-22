"""
SIMS Plus - User Invite Integration Tests

Tests exercise the UserService.create_user method (used by the /users/invite endpoint)
directly against a real PostgreSQL database with RLS enforced via the two-engine pattern:
- admin_session: superuser, seeds tenants, bypasses RLS
- app_session: sims_app_user, RLS enforced, used for service-layer queries

Each test creates its own tenant/data to avoid cross-test interference.

Covers:
- User creation for invite (PENDING status, email_verified=False)
- Duplicate email detection within same tenant
- Cross-tenant same email is allowed (composite unique on email+tenant_id)
- Invited user fields are set correctly (role, status, name, email lowercased)
- Retrieving invited user via get_user and get_user_by_email
- Inviting multiple users to the same tenant
- UserInviteRequest/UserInviteResponse Pydantic schema validation
"""

import pytest
from uuid import uuid4

from sqlalchemy import text

from app.models.user import UserRole, UserStatus
from app.services.user import UserService, UserServiceError

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
]

# Temporary password that satisfies the password policy:
# >= 8 chars, uppercase, lowercase, digit, special character.
TEMP_PASSWORD = "InviteTemp123!"


class TestUserInvite:
    """Tests for user creation in the invite flow."""

    async def test_create_user_for_invite(self, app_session, admin_session):
        """Creating a user with PENDING status succeeds and returns correct fields."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = UserService(app_session)

        user = await service.create_user(
            tenant_id=tenant["id"],
            email="invite-test@school.edu.gh",
            password=TEMP_PASSWORD,
            first_name="Invited",
            last_name="Teacher",
            role=UserRole.TEACHER,
            status=UserStatus.PENDING,
            email_verified=False,
        )

        assert user.id is not None
        assert user.email == "invite-test@school.edu.gh"
        assert user.first_name == "Invited"
        assert user.last_name == "Teacher"
        assert user.role == UserRole.TEACHER
        assert user.status == UserStatus.PENDING
        assert user.email_verified is False
        # Defense-in-depth: tenant_id must match the tenant we created
        assert user.tenant_id == tenant["id"]
        assert user.created_at is not None

    async def test_invite_creates_with_pending_status(self, app_session, admin_session):
        """Invited users should have PENDING status, not ACTIVE."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = UserService(app_session)

        user = await service.create_user(
            tenant_id=tenant["id"],
            email="pending-check@school.edu.gh",
            password=TEMP_PASSWORD,
            first_name="Status",
            last_name="Check",
            role=UserRole.FINANCE_OFFICER,
            status=UserStatus.PENDING,
            email_verified=False,
        )

        assert user.status == UserStatus.PENDING
        # Verify the user is not considered active
        assert user.is_active is False

    async def test_invite_email_lowercased(self, app_session, admin_session):
        """Email addresses should be lowercased on creation."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = UserService(app_session)

        user = await service.create_user(
            tenant_id=tenant["id"],
            email="UPPERCASE@School.EDU.GH",
            password=TEMP_PASSWORD,
            first_name="Case",
            last_name="Test",
            role=UserRole.TEACHER,
            status=UserStatus.PENDING,
            email_verified=False,
        )

        assert user.email == "uppercase@school.edu.gh"

    async def test_invite_duplicate_email_raises_error(self, app_session, admin_session):
        """Creating two users with the same email in the same tenant raises UserServiceError."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = UserService(app_session)

        # First user succeeds
        await service.create_user(
            tenant_id=tenant["id"],
            email="dup@school.edu.gh",
            password=TEMP_PASSWORD,
            first_name="First",
            last_name="User",
            role=UserRole.TEACHER,
            status=UserStatus.PENDING,
            email_verified=False,
        )

        # Second user with same email raises an application-level error
        with pytest.raises(UserServiceError) as exc_info:
            await service.create_user(
                tenant_id=tenant["id"],
                email="dup@school.edu.gh",
                password=TEMP_PASSWORD,
                first_name="Second",
                last_name="User",
                role=UserRole.TEACHER,
                status=UserStatus.PENDING,
                email_verified=False,
            )

        assert "already exists" in exc_info.value.message
        assert exc_info.value.code == "email_exists"

    async def test_invite_duplicate_email_case_insensitive(self, app_session, admin_session):
        """Duplicate email check is case-insensitive because emails are lowercased."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = UserService(app_session)

        await service.create_user(
            tenant_id=tenant["id"],
            email="casedup@school.edu.gh",
            password=TEMP_PASSWORD,
            first_name="Original",
            last_name="User",
            role=UserRole.TEACHER,
            status=UserStatus.PENDING,
            email_verified=False,
        )

        # Same email but different casing should still be rejected
        with pytest.raises(UserServiceError) as exc_info:
            await service.create_user(
                tenant_id=tenant["id"],
                email="CaseDup@School.EDU.GH",
                password=TEMP_PASSWORD,
                first_name="Duplicate",
                last_name="User",
                role=UserRole.TEACHER,
                status=UserStatus.PENDING,
                email_verified=False,
            )

        assert exc_info.value.code == "email_exists"

    async def test_invite_cross_tenant_same_email_allowed(
        self, app_session, admin_session
    ):
        """The same email can be invited to different tenants.

        The users table has a composite unique constraint (email, tenant_id),
        not a global unique constraint on email alone.
        """
        suffix = uuid4().hex[:8]
        tenant_a = await create_test_tenant(admin_session, subdomain=f"school-a-{suffix}")
        tenant_b = await create_test_tenant(admin_session, subdomain=f"school-b-{suffix}")
        await admin_session.commit()

        shared_email = "teacher@school.edu.gh"
        service = UserService(app_session)

        # Create user in tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        user_a = await service.create_user(
            tenant_id=tenant_a["id"],
            email=shared_email,
            password=TEMP_PASSWORD,
            first_name="Alice",
            last_name="Teacher",
            role=UserRole.TEACHER,
            status=UserStatus.PENDING,
            email_verified=False,
        )

        # Capture user_a attributes before switching tenant context.
        # set_app_tenant_context calls expire_all(), which invalidates ORM state.
        user_a_id = user_a.id
        user_a_email = user_a.email
        user_a_tenant_id = user_a.tenant_id

        # Switch context to tenant B and create user with the same email
        await set_app_tenant_context(app_session, tenant_b["id"])
        user_b = await service.create_user(
            tenant_id=tenant_b["id"],
            email=shared_email,
            password=TEMP_PASSWORD,
            first_name="Alice",
            last_name="Teacher",
            role=UserRole.TEACHER,
            status=UserStatus.PENDING,
            email_verified=False,
        )

        # Both users exist with the same email but different tenant_ids
        assert user_a_email == shared_email
        assert user_b.email == shared_email
        assert user_a_tenant_id == tenant_a["id"]
        assert user_b.tenant_id == tenant_b["id"]
        assert user_a_id != user_b.id

    async def test_invite_user_retrievable_by_id(self, app_session, admin_session):
        """An invited user can be retrieved by their UUID via get_user."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = UserService(app_session)

        created = await service.create_user(
            tenant_id=tenant["id"],
            email="retrievable@school.edu.gh",
            password=TEMP_PASSWORD,
            first_name="Retrieve",
            last_name="Test",
            role=UserRole.ACADEMIC_HEAD,
            status=UserStatus.PENDING,
            email_verified=False,
        )

        fetched = await service.get_user(created.id, tenant["id"])

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.email == "retrievable@school.edu.gh"
        assert fetched.status == UserStatus.PENDING

    async def test_invite_user_retrievable_by_email(self, app_session, admin_session):
        """An invited user can be retrieved by email via get_user_by_email."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = UserService(app_session)

        await service.create_user(
            tenant_id=tenant["id"],
            email="findbyemail@school.edu.gh",
            password=TEMP_PASSWORD,
            first_name="Find",
            last_name="ByEmail",
            role=UserRole.TEACHER,
            status=UserStatus.PENDING,
            email_verified=False,
        )

        fetched = await service.get_user_by_email("findbyemail@school.edu.gh", tenant["id"])

        assert fetched is not None
        assert fetched.email == "findbyemail@school.edu.gh"
        assert fetched.first_name == "Find"

    async def test_invite_multiple_users_same_tenant(self, app_session, admin_session):
        """Multiple users can be invited to the same tenant."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = UserService(app_session)

        roles = [
            ("teacher1@school.edu.gh", "Ama", "Mensah", UserRole.TEACHER),
            ("finance1@school.edu.gh", "Kwesi", "Boateng", UserRole.FINANCE_OFFICER),
            ("admin1@school.edu.gh", "Yaa", "Asantewaa", UserRole.SCHOOL_ADMIN),
        ]

        users = []
        for email, first, last, role in roles:
            user = await service.create_user(
                tenant_id=tenant["id"],
                email=email,
                password=TEMP_PASSWORD,
                first_name=first,
                last_name=last,
                role=role,
                status=UserStatus.PENDING,
                email_verified=False,
            )
            users.append(user)

        assert len(users) == 3
        # Each user gets the role they were assigned
        assert users[0].role == UserRole.TEACHER
        assert users[1].role == UserRole.FINANCE_OFFICER
        assert users[2].role == UserRole.SCHOOL_ADMIN
        # All belong to the same tenant
        assert all(u.tenant_id == tenant["id"] for u in users)
        # All IDs are unique
        assert len({u.id for u in users}) == 3

    async def test_invite_user_appears_in_list(self, app_session, admin_session):
        """An invited user appears in list_users results."""
        tenant = await create_test_tenant(admin_session)
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = UserService(app_session)

        await service.create_user(
            tenant_id=tenant["id"],
            email="listeduser@school.edu.gh",
            password=TEMP_PASSWORD,
            first_name="Listed",
            last_name="User",
            role=UserRole.TEACHER,
            status=UserStatus.PENDING,
            email_verified=False,
        )

        users, total = await service.list_users(tenant_id=tenant["id"])

        assert total >= 1
        emails = [u.email for u in users]
        assert "listeduser@school.edu.gh" in emails

    async def test_invite_user_filterable_by_pending_status(
        self, app_session, admin_session
    ):
        """Invited (PENDING) users can be filtered in list_users by status."""
        tenant = await create_test_tenant(admin_session)
        # Seed an ACTIVE user via admin so we have both statuses
        await create_test_user(admin_session, tenant["id"], email="active@school.edu.gh")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        service = UserService(app_session)

        # Create a PENDING user via invite flow
        await service.create_user(
            tenant_id=tenant["id"],
            email="pending-filter@school.edu.gh",
            password=TEMP_PASSWORD,
            first_name="Pending",
            last_name="Filter",
            role=UserRole.TEACHER,
            status=UserStatus.PENDING,
            email_verified=False,
        )

        # Filter by PENDING status -- should only include the invited user
        pending_users, pending_count = await service.list_users(
            tenant_id=tenant["id"], status=UserStatus.PENDING
        )
        assert pending_count >= 1
        assert all(u.status == UserStatus.PENDING for u in pending_users)

        # Filter by ACTIVE status -- should include the seeded user
        active_users, active_count = await service.list_users(
            tenant_id=tenant["id"], status=UserStatus.ACTIVE
        )
        assert active_count >= 1
        assert all(u.status == UserStatus.ACTIVE for u in active_users)


class TestUserInviteSchema:
    """Tests for UserInviteRequest and UserInviteResponse Pydantic schemas."""

    def test_invite_request_valid(self):
        """A valid invite request is accepted."""
        from app.schemas.user import UserInviteRequest

        req = UserInviteRequest(
            email="valid@school.edu.gh",
            role=UserRole.TEACHER,
            first_name="Kofi",
            last_name="Mensah",
        )

        assert req.email == "valid@school.edu.gh"
        assert req.role == UserRole.TEACHER
        assert req.first_name == "Kofi"
        assert req.last_name == "Mensah"

    def test_invite_request_strips_whitespace(self):
        """Leading/trailing whitespace is stripped from string fields."""
        from app.schemas.user import UserInviteRequest

        req = UserInviteRequest(
            email="  padded@school.edu.gh  ",
            role=UserRole.TEACHER,
            first_name="  Ama  ",
            last_name="  Darko  ",
        )

        assert req.first_name == "Ama"
        assert req.last_name == "Darko"

    def test_invite_request_rejects_empty_first_name(self):
        """First name must be at least 1 character after stripping."""
        from app.schemas.user import UserInviteRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            UserInviteRequest(
                email="test@school.edu.gh",
                role=UserRole.TEACHER,
                first_name="",
                last_name="Valid",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("first_name",) for e in errors)

    def test_invite_request_rejects_empty_last_name(self):
        """Last name must be at least 1 character after stripping."""
        from app.schemas.user import UserInviteRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            UserInviteRequest(
                email="test@school.edu.gh",
                role=UserRole.TEACHER,
                first_name="Valid",
                last_name="",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("last_name",) for e in errors)

    def test_invite_request_rejects_invalid_email(self):
        """Invalid email format is rejected."""
        from app.schemas.user import UserInviteRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            UserInviteRequest(
                email="not-an-email",
                role=UserRole.TEACHER,
                first_name="Bad",
                last_name="Email",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("email",) for e in errors)

    def test_invite_request_rejects_invalid_role(self):
        """An invalid role string is rejected."""
        from app.schemas.user import UserInviteRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            UserInviteRequest(
                email="test@school.edu.gh",
                role="superintendent",  # type: ignore[arg-type]
                first_name="Bad",
                last_name="Role",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("role",) for e in errors)

    def test_invite_request_name_max_length(self):
        """Names exceeding 100 characters are rejected."""
        from app.schemas.user import UserInviteRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            UserInviteRequest(
                email="test@school.edu.gh",
                role=UserRole.TEACHER,
                first_name="A" * 101,
                last_name="Valid",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("first_name",) for e in errors)

    def test_invite_response_from_attributes(self):
        """UserInviteResponse can be constructed from ORM-like attributes."""
        from datetime import datetime, UTC
        from app.schemas.user import UserInviteResponse

        now = datetime.now(UTC)
        resp = UserInviteResponse(
            id=uuid4(),
            email="test@school.edu.gh",
            first_name="Test",
            last_name="User",
            role=UserRole.TEACHER,
            status=UserStatus.PENDING,
            created_at=now,
        )

        assert resp.status == UserStatus.PENDING
        assert resp.role == UserRole.TEACHER
        assert resp.created_at == now

    def test_invite_response_all_roles_accepted(self):
        """UserInviteResponse accepts all valid UserRole values."""
        from datetime import datetime, UTC
        from app.schemas.user import UserInviteResponse

        now = datetime.now(UTC)
        for role in UserRole:
            resp = UserInviteResponse(
                id=uuid4(),
                email=f"{role.value}@school.edu.gh",
                first_name="Test",
                last_name="User",
                role=role,
                status=UserStatus.PENDING,
                created_at=now,
            )
            assert resp.role == role
