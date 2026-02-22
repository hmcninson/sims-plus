"""
Boarding Service Tests

Tests for boarding house, dormitory, bed, assignment, roll call, exeat,
incident, and dining service operations.

Uses the two-engine pattern:
- admin_session: superuser, seeds data (bypasses RLS)
- app_session: sims_app_user, RLS enforced

IMPORTANT: These tests require a running sims_plus_test database with
RLS policies applied (alembic upgrade head).
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.services.boarding import (
    BoardingServiceError,
    HouseService,
    BoardingAssignmentService,
    RollCallService,
    ExeatService,
    IncidentService,
    DiningService,
)

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.xdist_group("boarding_serial"),
]


# =========================
# Helper: seed prerequisites via admin
# =========================


async def seed_school(admin_session, tenant_id):
    """Seed a school for a tenant. Returns school_id."""
    school_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO schools (
                id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF',
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(school_id),
            "tid": str(tenant_id),
            "name": f"School-{uuid4().hex[:6]}",
            "slug": f"school-{uuid4().hex[:8]}",
        },
    )
    return school_id


async def seed_class_and_section(admin_session, tenant_id):
    """Seed a class and section. Returns (class_id, section_id)."""
    class_id = uuid4()
    section_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO classes (
                id, tenant_id, name, sequence, is_active,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(class_id),
            "tid": str(tenant_id),
            "name": f"Class-{uuid4().hex[:6]}",
        },
    )
    await admin_session.execute(
        text("""
            INSERT INTO class_sections (
                id, tenant_id, class_id, name, is_active,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:cid AS uuid),
                'A', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(section_id),
            "tid": str(tenant_id),
            "cid": str(class_id),
        },
    )
    return class_id, section_id


async def seed_student(admin_session, tenant_id, school_id, section_id, is_boarder=False):
    """Seed a student. Returns student_id."""
    student_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO students (
                id, tenant_id, school_id, section_id,
                student_id, first_name, last_name,
                date_of_birth, gender, status, is_boarder,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:sid AS uuid), CAST(:sec_id AS uuid),
                :student_num, :fn, :ln,
                '2012-05-15', 'male', 'active', :is_boarder,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(student_id),
            "tid": str(tenant_id),
            "sid": str(school_id),
            "sec_id": str(section_id),
            "student_num": f"STU-{uuid4().hex[:6]}",
            "fn": f"Student-{uuid4().hex[:4]}",
            "ln": f"Test-{uuid4().hex[:4]}",
            "is_boarder": is_boarder,
        },
    )
    return student_id


async def seed_staff(admin_session, tenant_id, school_id):
    """Seed a staff member. Returns staff record id."""
    staff_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO staff (
                id, tenant_id, school_id,
                staff_id, first_name, last_name,
                gender, email, phone,
                staff_type, status, job_title,
                employment_date,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :staff_num, :fn, :ln,
                'male', :email, '0241234567',
                'teaching', 'active', 'Teacher',
                '2020-09-01',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(staff_id),
            "tid": str(tenant_id),
            "sid": str(school_id),
            "staff_num": f"STF-{uuid4().hex[:6]}",
            "fn": "Kofi",
            "ln": "Mensah",
            "email": f"staff-{uuid4().hex[:6]}@test.com",
        },
    )
    return staff_id


async def seed_academic_year(admin_session, tenant_id):
    """Seed an academic year. Returns academic_year_id."""
    ay_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (
                id, tenant_id, name, start_date, end_date,
                status, is_current,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31',
                'active', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(ay_id),
            "tid": str(tenant_id),
            "name": f"AY-{uuid4().hex[:6]}",
        },
    )
    return ay_id


async def seed_boarding_fixtures(admin_session, tenant_id):
    """Seed all prerequisites for boarding tests.
    Returns dict with all prerequisite IDs.
    """
    school_id = await seed_school(admin_session, tenant_id)
    class_id, section_id = await seed_class_and_section(admin_session, tenant_id)
    student_id = await seed_student(
        admin_session, tenant_id, school_id, section_id, is_boarder=True
    )
    student_id_2 = await seed_student(
        admin_session, tenant_id, school_id, section_id, is_boarder=True
    )
    staff_id = await seed_staff(admin_session, tenant_id, school_id)
    user = await create_test_user(admin_session, tenant_id)
    ay_id = await seed_academic_year(admin_session, tenant_id)
    await admin_session.flush()

    return {
        "school_id": school_id,
        "class_id": class_id,
        "section_id": section_id,
        "student_id": student_id,
        "student_id_2": student_id_2,
        "staff_id": staff_id,
        "user_id": user["id"],
        "academic_year_id": ay_id,
    }


# ===================================================================
# House Service Tests
# ===================================================================


class TestHouseService:
    """Tests for HouseService CRUD and validation."""

    async def test_create_house(self, admin_session, app_session):
        """Creating a house returns a valid house object."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = HouseService(app_session)

        house = await svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Eagle House",
                "house_code": "EGL",
                "gender": "male",
                "capacity": 50,
            },
        )
        assert house.name == "Eagle House"
        assert house.house_code == "EGL"
        assert house.capacity == 50

    async def test_create_house_duplicate_name_rejected(self, admin_session, app_session):
        """Duplicate house name within the same tenant is rejected."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = HouseService(app_session)

        await svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Lion House",
                "house_code": "LIO",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        with pytest.raises(BoardingServiceError) as exc_info:
            await svc.create_house(
                tenant_id=tenant["id"],
                school_id=fixtures["school_id"],
                data={
                    "name": "Lion House",
                    "house_code": "LIO2",
                    "gender": "female",
                    "capacity": 40,
                },
            )
        assert exc_info.value.code == "duplicate_house_name"

    async def test_create_house_duplicate_code_rejected(self, admin_session, app_session):
        """Duplicate house code within the same tenant is rejected."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = HouseService(app_session)

        await svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Hawk House",
                "house_code": "HWK",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        with pytest.raises(BoardingServiceError) as exc_info:
            await svc.create_house(
                tenant_id=tenant["id"],
                school_id=fixtures["school_id"],
                data={
                    "name": "Falcon House",
                    "house_code": "HWK",
                    "gender": "female",
                    "capacity": 40,
                },
            )
        assert exc_info.value.code == "duplicate_house_code"

    async def test_get_houses_with_occupancy_stats(self, admin_session, app_session):
        """get_houses returns list of house dicts with occupancy counts."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = HouseService(app_session)

        await svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Alpha House",
                "house_code": "ALP",
                "gender": "male",
                "capacity": 30,
            },
        )
        await app_session.flush()

        houses = await svc.get_houses(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
        )
        assert len(houses) >= 1
        assert "house" in houses[0]
        assert "current_occupancy" in houses[0]
        assert houses[0]["current_occupancy"] == 0

    async def test_get_house_detail(self, admin_session, app_session):
        """get_house returns a single house with dormitories loaded."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = HouseService(app_session)

        house = await svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Beta House",
                "house_code": "BET",
                "gender": "female",
                "capacity": 40,
            },
        )
        await app_session.flush()
        house_id = house.id

        result = await svc.get_house(tenant_id=tenant["id"], house_id=house_id)
        assert result.id == house_id
        assert result.name == "Beta House"

    async def test_update_house(self, admin_session, app_session):
        """Updating a house changes its attributes."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = HouseService(app_session)

        house = await svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Gamma House",
                "house_code": "GAM",
                "gender": "mixed",
                "capacity": 60,
            },
        )
        await app_session.flush()
        house_id = house.id

        updated = await svc.update_house(
            tenant_id=tenant["id"],
            house_id=house_id,
            data={"capacity": 80},
        )
        assert updated.capacity == 80

    async def test_delete_house_soft_delete(self, admin_session, app_session):
        """Deleting a house sets deleted_at (soft delete)."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = HouseService(app_session)

        house = await svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Delta House",
                "house_code": "DEL",
                "gender": "male",
                "capacity": 30,
            },
        )
        await app_session.flush()
        house_id = house.id

        result = await svc.delete_house(tenant_id=tenant["id"], house_id=house_id)
        assert result is True

        # House should no longer be found
        with pytest.raises(BoardingServiceError) as exc_info:
            await svc.get_house(tenant_id=tenant["id"], house_id=house_id)
        assert exc_info.value.code == "not_found"


# ===================================================================
# Dormitory & Bed Tests
# ===================================================================


class TestDormitoryAndBeds:
    """Tests for dormitory and bed management within houses."""

    async def test_create_dormitory(self, admin_session, app_session):
        """Creating a dormitory within a house works."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = HouseService(app_session)

        house = await svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Epsilon House",
                "house_code": "EPS",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        dorm = await svc.create_dormitory(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            house_id=house.id,
            data={
                "name": "Room A1",
                "capacity": 10,
                "dormitory_type": "room",
            },
        )
        assert dorm.name == "Room A1"
        assert dorm.house_id == house.id

    async def test_create_dormitory_wrong_house_rejected(self, admin_session, app_session):
        """Dormitory creation with a house from another tenant is rejected."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = HouseService(app_session)

        fake_house_id = uuid4()
        with pytest.raises(BoardingServiceError) as exc_info:
            await svc.create_dormitory(
                tenant_id=tenant["id"],
                school_id=fixtures["school_id"],
                house_id=fake_house_id,
                data={
                    "name": "Room X",
                    "capacity": 10,
                    "dormitory_type": "room",
                },
            )
        assert exc_info.value.code == "not_found"

    async def test_get_dormitories_with_bed_counts(self, admin_session, app_session):
        """get_dormitories returns dormitories with bed count stats."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = HouseService(app_session)

        house = await svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Zeta House",
                "house_code": "ZET",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        await svc.create_dormitory(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            house_id=house.id,
            data={"name": "Room B1", "capacity": 4, "dormitory_type": "room"},
        )
        await app_session.flush()

        dorms = await svc.get_dormitories(
            tenant_id=tenant["id"],
            house_id=house.id,
        )
        assert len(dorms) == 1
        assert dorms[0]["bed_count"] == 0  # No beds created yet

    async def test_create_beds_bulk(self, admin_session, app_session):
        """Bulk bed creation creates all beds in one operation."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = HouseService(app_session)

        house = await svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Eta House",
                "house_code": "ETA",
                "gender": "female",
                "capacity": 50,
            },
        )
        await app_session.flush()

        dorm = await svc.create_dormitory(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            house_id=house.id,
            data={"name": "Room C1", "capacity": 4, "dormitory_type": "room"},
        )
        await app_session.flush()

        beds = await svc.create_beds(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            dormitory_id=dorm.id,
            beds_data=[
                {"bed_number": "C1-01", "bed_type": "single"},
                {"bed_number": "C1-02", "bed_type": "single"},
                {"bed_number": "C1-03", "bed_type": "bunk_upper"},
            ],
        )
        assert len(beds) == 3
        assert beds[0].bed_number == "C1-01"

    async def test_create_beds_duplicate_rejected(self, admin_session, app_session):
        """Duplicate bed numbers within the same dormitory are rejected."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = HouseService(app_session)

        house = await svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Theta House",
                "house_code": "THE",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        dorm = await svc.create_dormitory(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            house_id=house.id,
            data={"name": "Room D1", "capacity": 4, "dormitory_type": "room"},
        )
        await app_session.flush()

        # Duplicate within the same batch
        with pytest.raises(BoardingServiceError) as exc_info:
            await svc.create_beds(
                tenant_id=tenant["id"],
                school_id=fixtures["school_id"],
                dormitory_id=dorm.id,
                beds_data=[
                    {"bed_number": "D1-01", "bed_type": "single"},
                    {"bed_number": "D1-01", "bed_type": "single"},
                ],
            )
        assert exc_info.value.code == "duplicate_bed_number"


# ===================================================================
# Boarding Assignment Service Tests
# ===================================================================


class TestBoardingAssignmentService:
    """Tests for student boarding assignment operations."""

    async def test_assign_student_to_house(self, admin_session, app_session):
        """Assigning a student to a house creates an active boarding record."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        house_svc = HouseService(app_session)
        assign_svc = BoardingAssignmentService(app_session)

        house = await house_svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Assign House",
                "house_code": "ASH",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        assignment = await assign_svc.assign_student(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            house_id=house.id,
            dormitory_id=None,
            bed_id=None,
            academic_year_id=fixtures["academic_year_id"],
            check_in_date=date.today(),
        )
        assert assignment.student_id == fixtures["student_id"]
        assert assignment.boarding_status.value == "active"

    async def test_assign_student_already_assigned_rejected(self, admin_session, app_session):
        """Assigning a student who is already assigned for the same year is rejected."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        house_svc = HouseService(app_session)
        assign_svc = BoardingAssignmentService(app_session)

        house = await house_svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Dup Assign House",
                "house_code": "DAH",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        await assign_svc.assign_student(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            house_id=house.id,
            dormitory_id=None,
            bed_id=None,
            academic_year_id=fixtures["academic_year_id"],
            check_in_date=date.today(),
        )
        await app_session.flush()

        with pytest.raises(BoardingServiceError) as exc_info:
            await assign_svc.assign_student(
                tenant_id=tenant["id"],
                school_id=fixtures["school_id"],
                student_id=fixtures["student_id"],
                house_id=house.id,
                dormitory_id=None,
                bed_id=None,
                academic_year_id=fixtures["academic_year_id"],
                check_in_date=date.today(),
            )
        assert exc_info.value.code == "already_assigned"

    async def test_assign_student_bed_occupied_rejected(self, admin_session, app_session):
        """Assigning a student to an occupied bed is rejected."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        house_svc = HouseService(app_session)
        assign_svc = BoardingAssignmentService(app_session)

        house = await house_svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Bed Occ House",
                "house_code": "BOH",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        dorm = await house_svc.create_dormitory(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            house_id=house.id,
            data={"name": "Room E1", "capacity": 2, "dormitory_type": "room"},
        )
        await app_session.flush()

        beds = await house_svc.create_beds(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            dormitory_id=dorm.id,
            beds_data=[{"bed_number": "E1-01", "bed_type": "single"}],
        )
        await app_session.flush()
        bed_id = beds[0].id

        # Assign first student to the bed
        await assign_svc.assign_student(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            house_id=house.id,
            dormitory_id=dorm.id,
            bed_id=bed_id,
            academic_year_id=fixtures["academic_year_id"],
            check_in_date=date.today(),
        )
        await app_session.flush()

        # Second student to the same bed should fail
        with pytest.raises(BoardingServiceError) as exc_info:
            await assign_svc.assign_student(
                tenant_id=tenant["id"],
                school_id=fixtures["school_id"],
                student_id=fixtures["student_id_2"],
                house_id=house.id,
                dormitory_id=dorm.id,
                bed_id=bed_id,
                academic_year_id=fixtures["academic_year_id"],
                check_in_date=date.today(),
            )
        assert exc_info.value.code == "bed_occupied"

    async def test_unassign_student(self, admin_session, app_session):
        """Unassigning a student sets status to withdrawn and releases the bed."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        house_svc = HouseService(app_session)
        assign_svc = BoardingAssignmentService(app_session)

        house = await house_svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Unassign House",
                "house_code": "UNH",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        assignment = await assign_svc.assign_student(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            house_id=house.id,
            dormitory_id=None,
            bed_id=None,
            academic_year_id=fixtures["academic_year_id"],
            check_in_date=date.today(),
        )
        await app_session.flush()

        result = await assign_svc.unassign_student(
            tenant_id=tenant["id"],
            assignment_id=assignment.id,
        )
        assert result.boarding_status.value == "withdrawn"
        assert result.check_out_date is not None

    async def test_bulk_assign_students(self, admin_session, app_session):
        """Bulk assignment creates records for multiple students at once."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        house_svc = HouseService(app_session)
        assign_svc = BoardingAssignmentService(app_session)

        house = await house_svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Bulk House",
                "house_code": "BLK",
                "gender": "male",
                "capacity": 100,
            },
        )
        await app_session.flush()

        result = await assign_svc.bulk_assign(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_ids=[fixtures["student_id"], fixtures["student_id_2"]],
            house_id=house.id,
            academic_year_id=fixtures["academic_year_id"],
            check_in_date=date.today(),
        )
        assert result["created"] == 2
        assert result["skipped"] == 0
        assert result["failed"] == 0


# ===================================================================
# Roll Call Service Tests
# ===================================================================


class TestRollCallService:
    """Tests for boarding roll call operations."""

    async def test_create_roll_call_with_entries(self, admin_session, app_session):
        """Creating a roll call with student entries works."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        house_svc = HouseService(app_session)
        assign_svc = BoardingAssignmentService(app_session)
        roll_svc = RollCallService(app_session)

        house = await house_svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "RC House",
                "house_code": "RCH",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        await assign_svc.assign_student(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            house_id=house.id,
            dormitory_id=None,
            bed_id=None,
            academic_year_id=fixtures["academic_year_id"],
            check_in_date=date.today(),
        )
        await app_session.flush()

        roll_call = await roll_svc.create_roll_call(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            house_id=house.id,
            roll_call_date=date.today(),
            roll_call_type="morning",
            conducted_by_id=fixtures["staff_id"],
            entries=[
                {"student_id": fixtures["student_id"], "status": "present"},
            ],
        )
        assert roll_call.roll_call_type.value == "morning"

    async def test_create_roll_call_validates_students_in_house(self, admin_session, app_session):
        """Roll call rejects students not assigned to the house."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        house_svc = HouseService(app_session)
        roll_svc = RollCallService(app_session)

        house = await house_svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "RC Valid House",
                "house_code": "RVH",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        # Try roll call with a student not assigned to this house
        with pytest.raises(BoardingServiceError) as exc_info:
            await roll_svc.create_roll_call(
                tenant_id=tenant["id"],
                school_id=fixtures["school_id"],
                house_id=house.id,
                roll_call_date=date.today(),
                roll_call_type="evening",
                conducted_by_id=fixtures["staff_id"],
                entries=[
                    {"student_id": fixtures["student_id"], "status": "present"},
                ],
            )
        assert exc_info.value.code == "students_not_in_house"

    async def test_get_roll_call_report(self, admin_session, app_session):
        """Roll call report aggregates attendance data by student."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        house_svc = HouseService(app_session)
        assign_svc = BoardingAssignmentService(app_session)
        roll_svc = RollCallService(app_session)

        house = await house_svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": "Report House",
                "house_code": "RPH",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        await assign_svc.assign_student(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            house_id=house.id,
            dormitory_id=None,
            bed_id=None,
            academic_year_id=fixtures["academic_year_id"],
            check_in_date=date.today(),
        )
        await app_session.flush()

        await roll_svc.create_roll_call(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            house_id=house.id,
            roll_call_date=date.today(),
            roll_call_type="morning",
            conducted_by_id=fixtures["staff_id"],
            entries=[
                {"student_id": fixtures["student_id"], "status": "present"},
            ],
        )
        await app_session.flush()

        report = await roll_svc.get_roll_call_report(
            tenant_id=tenant["id"],
            house_id=house.id,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=1),
        )
        assert len(report) == 1
        assert report[0]["present_count"] == 1
        assert report[0]["present_percentage"] == 100.0


# ===================================================================
# Exeat Service Tests
# ===================================================================


class TestExeatService:
    """Tests for exeat request lifecycle."""

    async def _setup_exeat_prerequisites(self, admin_session, app_session):
        """Common setup: tenant, school, house, student assigned to house."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        house_svc = HouseService(app_session)
        assign_svc = BoardingAssignmentService(app_session)

        house = await house_svc.create_house(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "name": f"Exeat House {uuid4().hex[:6]}",
                "house_code": f"EX{uuid4().hex[:3]}",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        await assign_svc.assign_student(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            house_id=house.id,
            dormitory_id=None,
            bed_id=None,
            academic_year_id=fixtures["academic_year_id"],
            check_in_date=date.today(),
        )
        await app_session.flush()

        return tenant, fixtures

    async def test_request_exeat(self, admin_session, app_session):
        """Requesting an exeat creates a pending exeat record."""
        tenant, fixtures = await self._setup_exeat_prerequisites(admin_session, app_session)

        exeat_svc = ExeatService(app_session)
        exeat = await exeat_svc.request_exeat(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            requested_by_id=fixtures["user_id"],
            data={
                "exeat_type": "weekend",
                "reason": "Family visit",
                "start_date": date.today() + timedelta(days=1),
                "end_date": date.today() + timedelta(days=3),
            },
        )
        assert exeat.status.value == "pending"
        assert exeat.reason == "Family visit"

    async def test_approve_exeat(self, admin_session, app_session):
        """Approving a pending exeat sets status to approved."""
        tenant, fixtures = await self._setup_exeat_prerequisites(admin_session, app_session)

        exeat_svc = ExeatService(app_session)
        exeat = await exeat_svc.request_exeat(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            requested_by_id=fixtures["user_id"],
            data={
                "exeat_type": "medical",
                "reason": "Hospital appointment",
                "start_date": date.today() + timedelta(days=1),
                "end_date": date.today() + timedelta(days=2),
            },
        )
        await app_session.flush()

        approved = await exeat_svc.approve_exeat(
            tenant_id=tenant["id"],
            exeat_id=exeat.id,
            approver_id=fixtures["user_id"],
        )
        assert approved.status.value == "approved"

    async def test_deny_exeat(self, admin_session, app_session):
        """Denying a pending exeat sets status to denied and adds denial reason."""
        tenant, fixtures = await self._setup_exeat_prerequisites(admin_session, app_session)

        exeat_svc = ExeatService(app_session)
        exeat = await exeat_svc.request_exeat(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            requested_by_id=fixtures["user_id"],
            data={
                "exeat_type": "weekend",
                "reason": "Shopping trip",
                "start_date": date.today() + timedelta(days=1),
                "end_date": date.today() + timedelta(days=2),
            },
        )
        await app_session.flush()

        denied = await exeat_svc.deny_exeat(
            tenant_id=tenant["id"],
            exeat_id=exeat.id,
            approver_id=fixtures["user_id"],
            reason="Not enough advance notice",
        )
        assert denied.status.value == "denied"
        assert "Not enough advance notice" in denied.notes

    async def test_exeat_full_lifecycle(self, admin_session, app_session):
        """Full exeat lifecycle: pending -> approved -> active -> returned."""
        tenant, fixtures = await self._setup_exeat_prerequisites(admin_session, app_session)

        exeat_svc = ExeatService(app_session)
        exeat = await exeat_svc.request_exeat(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            requested_by_id=fixtures["user_id"],
            data={
                "exeat_type": "emergency",
                "reason": "Family emergency",
                "start_date": date.today(),
                "end_date": date.today() + timedelta(days=5),
            },
        )
        await app_session.flush()

        # Approve
        exeat = await exeat_svc.approve_exeat(
            tenant_id=tenant["id"], exeat_id=exeat.id, approver_id=fixtures["user_id"],
        )
        assert exeat.status.value == "approved"

        # Activate (student leaves)
        exeat = await exeat_svc.activate_exeat(
            tenant_id=tenant["id"], exeat_id=exeat.id,
        )
        assert exeat.status.value == "active"

        # Return
        exeat = await exeat_svc.record_return(
            tenant_id=tenant["id"], exeat_id=exeat.id,
        )
        assert exeat.status.value == "returned"
        assert exeat.actual_return_date is not None

    async def test_invalid_exeat_transition_rejected(self, admin_session, app_session):
        """Attempting an invalid exeat state transition raises an error."""
        tenant, fixtures = await self._setup_exeat_prerequisites(admin_session, app_session)

        exeat_svc = ExeatService(app_session)
        exeat = await exeat_svc.request_exeat(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            requested_by_id=fixtures["user_id"],
            data={
                "exeat_type": "weekend",
                "reason": "Visit",
                "start_date": date.today() + timedelta(days=1),
                "end_date": date.today() + timedelta(days=2),
            },
        )
        await app_session.flush()

        # Cannot activate a pending exeat (must approve first)
        with pytest.raises(BoardingServiceError) as exc_info:
            await exeat_svc.activate_exeat(
                tenant_id=tenant["id"], exeat_id=exeat.id,
            )
        assert exc_info.value.code == "invalid_status_transition"


# ===================================================================
# Incident Service Tests
# ===================================================================


class TestIncidentService:
    """Tests for boarding incident reporting and resolution."""

    async def test_report_incident(self, admin_session, app_session):
        """Reporting an incident creates an unresolved incident record."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = IncidentService(app_session)

        incident = await svc.report_incident(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "student_id": fixtures["student_id"],
                "reported_by_id": fixtures["user_id"],
                "incident_type": "disciplinary",
                "severity": "medium",
                "description": "Broke curfew at 10pm",
            },
        )
        assert incident.resolved is False
        assert incident.incident_type.value == "disciplinary"

    async def test_resolve_incident(self, admin_session, app_session):
        """Resolving an incident marks it resolved with action taken."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = IncidentService(app_session)

        incident = await svc.report_incident(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "student_id": fixtures["student_id"],
                "reported_by_id": fixtures["user_id"],
                "incident_type": "health",
                "severity": "low",
                "description": "Minor headache",
            },
        )
        await app_session.flush()

        resolved = await svc.resolve_incident(
            tenant_id=tenant["id"],
            incident_id=incident.id,
            resolver_id=fixtures["user_id"],
            action_taken="Gave paracetamol and rest",
        )
        assert resolved.resolved is True
        assert resolved.action_taken == "Gave paracetamol and rest"

    async def test_resolve_already_resolved_rejected(self, admin_session, app_session):
        """Resolving an already-resolved incident is rejected."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = IncidentService(app_session)

        incident = await svc.report_incident(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "student_id": fixtures["student_id"],
                "reported_by_id": fixtures["user_id"],
                "incident_type": "theft",
                "severity": "high",
                "description": "Phone stolen from locker",
            },
        )
        await app_session.flush()

        await svc.resolve_incident(
            tenant_id=tenant["id"],
            incident_id=incident.id,
            resolver_id=fixtures["user_id"],
            action_taken="Investigation complete",
        )
        await app_session.flush()

        with pytest.raises(BoardingServiceError) as exc_info:
            await svc.resolve_incident(
                tenant_id=tenant["id"],
                incident_id=incident.id,
                resolver_id=fixtures["user_id"],
                action_taken="Trying again",
            )
        assert exc_info.value.code == "already_resolved"

    async def test_search_incidents(self, admin_session, app_session):
        """Searching incidents filters by description text."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = IncidentService(app_session)

        await svc.report_incident(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "student_id": fixtures["student_id"],
                "reported_by_id": fixtures["user_id"],
                "incident_type": "bullying",
                "severity": "high",
                "description": "Verbal bullying in the dining hall",
            },
        )
        await app_session.flush()

        results = await svc.get_incidents(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            search="dining hall",
        )
        assert len(results) >= 1


# ===================================================================
# Dining Service Tests
# ===================================================================


class TestDiningService:
    """Tests for dining meal logging and statistics."""

    async def test_log_meal(self, admin_session, app_session):
        """Logging a meal creates a meal record."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = DiningService(app_session)

        meal = await svc.log_meal(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "date": date.today(),
                "meal_type": "breakfast",
                "menu_description": "Rice and beans",
                "head_count": 150,
            },
        )
        assert meal.meal_type.value == "breakfast"
        assert meal.head_count == 150

    async def test_log_meal_duplicate_rejected(self, admin_session, app_session):
        """Logging the same meal type on the same date is rejected."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = DiningService(app_session)

        await svc.log_meal(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "date": date.today(),
                "meal_type": "lunch",
                "menu_description": "Jollof rice",
                "head_count": 140,
            },
        )
        await app_session.flush()

        with pytest.raises(BoardingServiceError) as exc_info:
            await svc.log_meal(
                tenant_id=tenant["id"],
                school_id=fixtures["school_id"],
                data={
                    "date": date.today(),
                    "meal_type": "lunch",
                    "menu_description": "Different lunch",
                    "head_count": 130,
                },
            )
        assert exc_info.value.code == "duplicate_meal"

    async def test_get_dining_stats(self, admin_session, app_session):
        """Dining stats returns monthly aggregated meal data."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_boarding_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = DiningService(app_session)

        today = date.today()
        await svc.log_meal(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            data={
                "date": today,
                "meal_type": "dinner",
                "menu_description": "Banku and tilapia",
                "head_count": 160,
            },
        )
        await app_session.flush()

        stats = await svc.get_dining_stats(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            month=today.month,
            year=today.year,
        )
        assert stats["total_meals"] >= 1
        assert stats["avg_head_count"] is not None
