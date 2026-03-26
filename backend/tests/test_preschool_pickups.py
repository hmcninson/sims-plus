"""
SIMS Plus - Preschool Pickup Tests

Tests exercise the PreschoolPickupService directly against a real PostgreSQL database.
Covers authorized pickup CRUD, pickup log validation (guardian vs authorized person),
deactivation, and date server-side enforcement.

Uses admin_session for seeding, app_session with RLS for service calls.
"""

import pytest
from datetime import date, time
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.preschool import PreschoolPickupService, PreschoolServiceError
from app.schemas.preschool.pickup import (
    AuthorizedPickupCreate,
    AuthorizedPickupUpdate,
    PickupLogCreate,
)

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)


# ============================================================
# SQL templates
# ============================================================

_SCHOOL_INSERT = text("""
    INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
        student_id_prefix, staff_id_prefix, is_active,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
        'preschool', 'active', 'STU', 'STF', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_CLASS_INSERT = text("""
    INSERT INTO classes (id, tenant_id, name, level, sequence,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :level, :seq,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_STUDENT_INSERT = text("""
    INSERT INTO students (id, tenant_id, student_id, first_name, last_name,
        date_of_birth, gender, status, class_id, school_id,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, :fn, :ln,
        '2021-05-10', 'female', 'active', CAST(:cid AS uuid), CAST(:school_id AS uuid),
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_GUARDIAN_INSERT = text("""
    INSERT INTO guardians (id, tenant_id, first_name, last_name, phone,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :fn, :ln, :phone,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_STUDENT_GUARDIAN_INSERT = text("""
    INSERT INTO student_guardians (id, tenant_id, student_id, guardian_id,
        relationship, is_primary, can_pickup, created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
        CAST(:gid AS uuid), :rel, :is_primary, :can_pickup,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_pickup_env(session: AsyncSession) -> dict:
    """Seed environment for pickup tests.

    Creates: tenant, school, class (KG1), 2 students, user (teacher),
    2 guardians linked to student_1 (one with can_pickup=True, one False).
    """
    tenant = await create_test_tenant(session)
    tid = tenant["id"]

    school_id = uuid4()
    class_id = uuid4()
    student1_id = uuid4()
    student2_id = uuid4()
    guardian1_id = uuid4()
    guardian2_id = uuid4()
    user = await create_test_user(session, tid)

    await session.execute(_SCHOOL_INSERT, {
        "id": str(school_id), "tid": str(tid),
        "name": "Preschool Academy", "slug": f"ps-{uuid4().hex[:8]}",
    })
    await session.execute(_CLASS_INSERT, {
        "id": str(class_id), "tid": str(tid),
        "name": "KG 1", "level": "kg_1", "seq": 1,
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student1_id), "tid": str(tid), "sid": "PRE-001",
        "fn": "Esi", "ln": "Owusu", "cid": str(class_id),
        "school_id": str(school_id),
    })
    await session.execute(_STUDENT_INSERT, {
        "id": str(student2_id), "tid": str(tid), "sid": "PRE-002",
        "fn": "Kofi", "ln": "Boateng", "cid": str(class_id),
        "school_id": str(school_id),
    })

    # Guardian 1: can_pickup=True, linked to student_1
    await session.execute(_GUARDIAN_INSERT, {
        "id": str(guardian1_id), "tid": str(tid),
        "fn": "Ama", "ln": "Owusu", "phone": "+233201234567",
    })
    await session.execute(_STUDENT_GUARDIAN_INSERT, {
        "id": str(uuid4()), "tid": str(tid),
        "sid": str(student1_id), "gid": str(guardian1_id),
        "rel": "mother", "is_primary": True, "can_pickup": True,
    })

    # Guardian 2: can_pickup=False, linked to student_1
    await session.execute(_GUARDIAN_INSERT, {
        "id": str(guardian2_id), "tid": str(tid),
        "fn": "Kweku", "ln": "Owusu", "phone": "+233209876543",
    })
    await session.execute(_STUDENT_GUARDIAN_INSERT, {
        "id": str(uuid4()), "tid": str(tid),
        "sid": str(student1_id), "gid": str(guardian2_id),
        "rel": "uncle", "is_primary": False, "can_pickup": False,
    })

    await session.commit()

    return {
        "tenant_id": tid,
        "school_id": school_id,
        "class_id": class_id,
        "student1_id": student1_id,
        "student2_id": student2_id,
        "guardian1_id": guardian1_id,  # can_pickup=True
        "guardian2_id": guardian2_id,  # can_pickup=False
        "user_id": user["id"],
    }


@pytest.mark.asyncio
class TestAuthorizedPickups:
    """Test authorized pickup person management."""

    async def test_add_authorized_pickup(self, admin_session, app_session):
        """Add an authorized pickup person for a student."""
        env = await _seed_pickup_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])

        service = PreschoolPickupService(app_session)
        pickup = await service.add_authorized_pickup(
            tenant_id=env["tenant_id"],
            student_id=env["student1_id"],
            data=AuthorizedPickupCreate(
                full_name="Auntie Akua", phone="+233241112222",
                relationship_to_student="aunt",
            ),
            added_by=env["user_id"],
        )

        assert pickup.is_active is True
        assert pickup.student_id == env["student1_id"]
        assert pickup.full_name == "Auntie Akua"

    async def test_add_duplicate_phone_rejected(self, admin_session, app_session):
        """Cannot add same phone number for same student twice."""
        env = await _seed_pickup_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        data = AuthorizedPickupCreate(
            full_name="Person A", phone="+233241112222",
        )
        await service.add_authorized_pickup(
            env["tenant_id"], env["student1_id"], data, env["user_id"],
        )

        data2 = AuthorizedPickupCreate(
            full_name="Person B", phone="+233241112222",
        )
        with pytest.raises(Exception):
            # DB unique constraint should reject duplicate phone per student
            await service.add_authorized_pickup(
                env["tenant_id"], env["student1_id"], data2, env["user_id"],
            )

    async def test_list_authorized_pickups(self, admin_session, app_session):
        """List all authorized pickup persons for a student."""
        env = await _seed_pickup_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        for i in range(3):
            await service.add_authorized_pickup(
                env["tenant_id"], env["student1_id"],
                AuthorizedPickupCreate(
                    full_name=f"Person {i}", phone=f"+23324111000{i}",
                ),
                env["user_id"],
            )

        result = await service.list_authorized_pickups(
            env["tenant_id"], env["student1_id"],
        )
        assert len(result) == 3

    async def test_update_authorized_pickup(self, admin_session, app_session):
        """Update name and phone of authorized person."""
        env = await _seed_pickup_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        pickup = await service.add_authorized_pickup(
            env["tenant_id"], env["student1_id"],
            AuthorizedPickupCreate(full_name="Old Name", phone="+233241112222"),
            env["user_id"],
        )

        updated = await service.update_authorized_pickup(
            env["tenant_id"], pickup.id,
            AuthorizedPickupUpdate(full_name="New Name", phone="+233241113333"),
        )

        assert updated.full_name == "New Name"
        assert updated.phone == "+233241113333"

    async def test_deactivate_authorized_pickup(self, admin_session, app_session):
        """Soft-delete an authorized person."""
        env = await _seed_pickup_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        pickup = await service.add_authorized_pickup(
            env["tenant_id"], env["student1_id"],
            AuthorizedPickupCreate(full_name="To Remove", phone="+233241112222"),
            env["user_id"],
        )

        await service.deactivate_authorized_pickup(env["tenant_id"], pickup.id)

        # Should not appear in list (list filters deleted_at.is_(None))
        result = await service.list_authorized_pickups(
            env["tenant_id"], env["student1_id"],
        )
        assert len(result) == 0

    async def test_student_not_found(self, admin_session, app_session):
        """Error when student doesn't belong to tenant."""
        env = await _seed_pickup_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        with pytest.raises(PreschoolServiceError) as exc_info:
            await service.add_authorized_pickup(
                env["tenant_id"], uuid4(),
                AuthorizedPickupCreate(full_name="Nobody", phone="+233241112222"),
                env["user_id"],
            )
        assert exc_info.value.code == "STUDENT_NOT_FOUND"


@pytest.mark.asyncio
class TestPickupLogs:
    """Test pickup log recording and validation."""

    async def test_record_pickup_by_guardian_with_can_pickup(self, admin_session, app_session):
        """Record pickup by a guardian who has can_pickup=True."""
        env = await _seed_pickup_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        log = await service.record_pickup(
            tenant_id=env["tenant_id"],
            data=PickupLogCreate(
                student_id=env["student1_id"],
                pickup_time=time(15, 0),
                picked_up_by_type="guardian",
                picked_up_by_guardian_id=env["guardian1_id"],
            ),
            verified_by=env["user_id"],
        )

        assert log.pickup_date == date.today()
        assert log.picked_up_by_type == "guardian"
        assert log.picked_up_by_guardian_id == env["guardian1_id"]

    async def test_reject_pickup_by_guardian_without_can_pickup(self, admin_session, app_session):
        """Reject pickup by guardian with can_pickup=False."""
        env = await _seed_pickup_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        with pytest.raises(PreschoolServiceError) as exc_info:
            await service.record_pickup(
                tenant_id=env["tenant_id"],
                data=PickupLogCreate(
                    student_id=env["student1_id"],
                    pickup_time=time(15, 0),
                    picked_up_by_type="guardian",
                    picked_up_by_guardian_id=env["guardian2_id"],
                ),
                verified_by=env["user_id"],
            )
        assert exc_info.value.code == "GUARDIAN_PICKUP_NOT_AUTHORIZED"

    async def test_reject_pickup_by_unlinked_guardian(self, admin_session, app_session):
        """Reject pickup by guardian not linked to student."""
        env = await _seed_pickup_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        # guardian1 is linked to student1, not student2
        with pytest.raises(PreschoolServiceError) as exc_info:
            await service.record_pickup(
                tenant_id=env["tenant_id"],
                data=PickupLogCreate(
                    student_id=env["student2_id"],
                    pickup_time=time(15, 0),
                    picked_up_by_type="guardian",
                    picked_up_by_guardian_id=env["guardian1_id"],
                ),
                verified_by=env["user_id"],
            )
        assert exc_info.value.code == "GUARDIAN_NOT_LINKED"

    async def test_record_pickup_by_authorized_person(self, admin_session, app_session):
        """Record pickup by an active authorized person."""
        env = await _seed_pickup_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        # Add authorized person first
        auth_person = await service.add_authorized_pickup(
            env["tenant_id"], env["student1_id"],
            AuthorizedPickupCreate(full_name="Uncle Joe", phone="+233241112222"),
            env["user_id"],
        )

        log = await service.record_pickup(
            tenant_id=env["tenant_id"],
            data=PickupLogCreate(
                student_id=env["student1_id"],
                pickup_time=time(15, 30),
                picked_up_by_type="authorized_person",
                picked_up_by_authorized_id=auth_person.id,
            ),
            verified_by=env["user_id"],
        )

        assert log.picked_up_by_type == "authorized_person"
        assert log.picked_up_by_authorized_id == auth_person.id

    async def test_reject_pickup_by_inactive_authorized_person(self, admin_session, app_session):
        """Reject pickup by deactivated authorized person."""
        env = await _seed_pickup_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        auth_person = await service.add_authorized_pickup(
            env["tenant_id"], env["student1_id"],
            AuthorizedPickupCreate(full_name="Revoked", phone="+233241112222"),
            env["user_id"],
        )
        await service.deactivate_authorized_pickup(env["tenant_id"], auth_person.id)

        with pytest.raises(PreschoolServiceError) as exc_info:
            await service.record_pickup(
                tenant_id=env["tenant_id"],
                data=PickupLogCreate(
                    student_id=env["student1_id"],
                    pickup_time=time(15, 0),
                    picked_up_by_type="authorized_person",
                    picked_up_by_authorized_id=auth_person.id,
                ),
                verified_by=env["user_id"],
            )
        assert exc_info.value.code == "AUTHORIZED_PICKUP_NOT_FOUND"

    async def test_pickup_date_set_server_side(self, admin_session, app_session):
        """Verify pickup_date is always today, set server-side."""
        env = await _seed_pickup_env(admin_session)
        await set_app_tenant_context(app_session, env["tenant_id"])
        service = PreschoolPickupService(app_session)

        log = await service.record_pickup(
            tenant_id=env["tenant_id"],
            data=PickupLogCreate(
                student_id=env["student1_id"],
                pickup_time=time(15, 0),
                picked_up_by_type="guardian",
                picked_up_by_guardian_id=env["guardian1_id"],
            ),
            verified_by=env["user_id"],
        )

        assert log.pickup_date == date.today()
