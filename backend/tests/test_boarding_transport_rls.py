"""
Boarding & Transport Tenant Isolation (RLS) Tests

Verifies that Row-Level Security prevents cross-tenant data access
for all boarding and transport models.

Pattern:
1. Create data as Tenant A via admin session
2. Switch app session to Tenant B context
3. Verify Tenant B sees NOTHING from Tenant A

IMPORTANT: Uses the two-engine pattern.
- admin_session: superuser (bypasses RLS) -- for seeding data
- app_session: sims_app_user (RLS enforced) -- for isolation assertions
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.services.boarding import (
    BoardingServiceError,
    HouseService,
    BoardingAssignmentService,
    ExeatService,
    RollCallService,
)
from app.services.transport import (
    TransportServiceError,
    VehicleService,
    DriverService,
    RouteService,
    TransportAssignmentService,
    TripService,
)

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.xdist_group("rls_isolation_serial"),
]


# =========================
# Helpers: seed prerequisites via admin
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
        {"id": str(class_id), "tid": str(tenant_id), "name": f"C-{uuid4().hex[:6]}"},
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
        {"id": str(section_id), "tid": str(tenant_id), "cid": str(class_id)},
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
        {"id": str(ay_id), "tid": str(tenant_id), "name": f"AY-{uuid4().hex[:6]}"},
    )
    return ay_id


async def seed_full_tenant(admin_session, subdomain_prefix="iso"):
    """Create a complete tenant with school, student, staff, user, and academic year.
    Returns (tenant_dict, fixtures_dict) with all IDs captured as plain values.
    """
    tenant = await create_test_tenant(
        admin_session, subdomain=f"{subdomain_prefix}-{uuid4().hex[:8]}"
    )
    school_id = await seed_school(admin_session, tenant["id"])
    class_id, section_id = await seed_class_and_section(admin_session, tenant["id"])
    student_id = await seed_student(
        admin_session, tenant["id"], school_id, section_id, is_boarder=True
    )
    staff_id = await seed_staff(admin_session, tenant["id"], school_id)
    user = await create_test_user(admin_session, tenant["id"])
    ay_id = await seed_academic_year(admin_session, tenant["id"])
    await admin_session.flush()

    return tenant, {
        "school_id": school_id,
        "student_id": student_id,
        "staff_id": staff_id,
        "user_id": user["id"],
        "academic_year_id": ay_id,
    }


# ===================================================================
# Boarding Tenant Isolation Tests
# ===================================================================


class TestBoardingTenantIsolation:
    """Verify that boarding data is isolated between tenants via RLS."""

    async def test_house_tenant_isolation(self, admin_session, app_session):
        """Tenant B cannot see Tenant A's boarding houses."""
        tenant_a, fixtures_a = await seed_full_tenant(admin_session, "house-a")
        tenant_b, fixtures_b = await seed_full_tenant(admin_session, "house-b")
        await admin_session.commit()

        # Create house as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        svc = HouseService(app_session)
        house_a = await svc.create_house(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            data={
                "name": "Isolation Eagle",
                "house_code": "IEG",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()
        house_a_id = house_a.id

        # Switch to Tenant B context -- should NOT see Tenant A's house
        await set_app_tenant_context(app_session, tenant_b["id"])
        svc_b = HouseService(app_session)

        houses = await svc_b.get_houses(
            tenant_id=tenant_b["id"],
            school_id=fixtures_b["school_id"],
        )
        house_ids = [h["house"].id for h in houses]
        assert house_a_id not in house_ids

        # Direct fetch should return not_found
        with pytest.raises(BoardingServiceError) as exc_info:
            await svc_b.get_house(tenant_id=tenant_b["id"], house_id=house_a_id)
        assert exc_info.value.code == "not_found"

    async def test_boarding_assignment_tenant_isolation(self, admin_session, app_session):
        """Tenant B cannot see Tenant A's boarding assignments."""
        tenant_a, fixtures_a = await seed_full_tenant(admin_session, "assign-a")
        tenant_b, fixtures_b = await seed_full_tenant(admin_session, "assign-b")
        await admin_session.commit()

        # Create house and assign student as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        house_svc = HouseService(app_session)
        assign_svc = BoardingAssignmentService(app_session)

        house = await house_svc.create_house(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            data={
                "name": "Iso Assign House",
                "house_code": "IAH",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        assignment = await assign_svc.assign_student(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            student_id=fixtures_a["student_id"],
            house_id=house.id,
            dormitory_id=None,
            bed_id=None,
            academic_year_id=fixtures_a["academic_year_id"],
            check_in_date=date.today(),
        )
        await app_session.flush()
        assignment_id = assignment.id

        # Switch to Tenant B -- should NOT see Tenant A's assignment
        await set_app_tenant_context(app_session, tenant_b["id"])
        assign_svc_b = BoardingAssignmentService(app_session)

        assignments = await assign_svc_b.get_assignments(
            tenant_id=tenant_b["id"],
            school_id=fixtures_b["school_id"],
        )
        assignment_ids = [a.id for a in assignments]
        assert assignment_id not in assignment_ids

    async def test_exeat_tenant_isolation(self, admin_session, app_session):
        """Tenant B cannot see Tenant A's exeats."""
        tenant_a, fixtures_a = await seed_full_tenant(admin_session, "exeat-a")
        tenant_b, fixtures_b = await seed_full_tenant(admin_session, "exeat-b")
        await admin_session.commit()

        # Create house, assign student, request exeat as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        house_svc = HouseService(app_session)
        assign_svc = BoardingAssignmentService(app_session)
        exeat_svc = ExeatService(app_session)

        house = await house_svc.create_house(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            data={
                "name": "Iso Exeat House",
                "house_code": "IXH",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        await assign_svc.assign_student(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            student_id=fixtures_a["student_id"],
            house_id=house.id,
            dormitory_id=None,
            bed_id=None,
            academic_year_id=fixtures_a["academic_year_id"],
            check_in_date=date.today(),
        )
        await app_session.flush()

        exeat = await exeat_svc.request_exeat(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            student_id=fixtures_a["student_id"],
            requested_by_id=fixtures_a["user_id"],
            data={
                "exeat_type": "weekend",
                "reason": "Cross-tenant test",
                "start_date": date.today() + timedelta(days=1),
                "end_date": date.today() + timedelta(days=2),
            },
        )
        await app_session.flush()
        exeat_id = exeat.id

        # Switch to Tenant B -- should NOT see Tenant A's exeat
        await set_app_tenant_context(app_session, tenant_b["id"])
        exeat_svc_b = ExeatService(app_session)

        exeats = await exeat_svc_b.get_exeats(
            tenant_id=tenant_b["id"],
            school_id=fixtures_b["school_id"],
        )
        exeat_ids = [e.id for e in exeats]
        assert exeat_id not in exeat_ids

        # Direct fetch should return not_found
        with pytest.raises(BoardingServiceError) as exc_info:
            await exeat_svc_b.get_exeat(
                tenant_id=tenant_b["id"], exeat_id=exeat_id
            )
        assert exc_info.value.code == "not_found"

    async def test_cross_tenant_roll_call_blocked(self, admin_session, app_session):
        """Tenant B cannot see Tenant A's roll call records."""
        tenant_a, fixtures_a = await seed_full_tenant(admin_session, "rc-a")
        tenant_b, fixtures_b = await seed_full_tenant(admin_session, "rc-b")
        await admin_session.commit()

        # Create house, assign student, create roll call as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        house_svc = HouseService(app_session)
        assign_svc = BoardingAssignmentService(app_session)
        roll_svc = RollCallService(app_session)

        house = await house_svc.create_house(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            data={
                "name": "Iso RC House",
                "house_code": "IRC",
                "gender": "male",
                "capacity": 50,
            },
        )
        await app_session.flush()

        await assign_svc.assign_student(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            student_id=fixtures_a["student_id"],
            house_id=house.id,
            dormitory_id=None,
            bed_id=None,
            academic_year_id=fixtures_a["academic_year_id"],
            check_in_date=date.today(),
        )
        await app_session.flush()

        roll_call = await roll_svc.create_roll_call(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            house_id=house.id,
            roll_call_date=date.today(),
            roll_call_type="morning",
            conducted_by_id=fixtures_a["user_id"],
            entries=[
                {"student_id": fixtures_a["student_id"], "status": "present"},
            ],
        )
        await app_session.flush()
        roll_call_id = roll_call.id

        # Switch to Tenant B -- should NOT see Tenant A's roll call
        await set_app_tenant_context(app_session, tenant_b["id"])
        roll_svc_b = RollCallService(app_session)

        with pytest.raises(BoardingServiceError) as exc_info:
            await roll_svc_b.get_roll_call(
                tenant_id=tenant_b["id"], roll_call_id=roll_call_id
            )
        assert exc_info.value.code == "not_found"


# ===================================================================
# Transport Tenant Isolation Tests
# ===================================================================


class TestTransportTenantIsolation:
    """Verify that transport data is isolated between tenants via RLS."""

    async def test_vehicle_tenant_isolation(self, admin_session, app_session):
        """Tenant B cannot see Tenant A's vehicles."""
        tenant_a, fixtures_a = await seed_full_tenant(admin_session, "veh-a")
        tenant_b, fixtures_b = await seed_full_tenant(admin_session, "veh-b")
        await admin_session.commit()

        # Create vehicle as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        svc = VehicleService(app_session)

        vehicle = await svc.create_vehicle(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            registration_number="ISO-VEH-001",
            vehicle_type="bus",
            capacity=45,
        )
        await app_session.flush()
        vehicle_id = vehicle.id

        # Switch to Tenant B -- should NOT see Tenant A's vehicle
        await set_app_tenant_context(app_session, tenant_b["id"])
        svc_b = VehicleService(app_session)

        vehicles, total = await svc_b.get_vehicles(
            tenant_id=tenant_b["id"],
            school_id=fixtures_b["school_id"],
        )
        vehicle_ids = [v.id for v in vehicles]
        assert vehicle_id not in vehicle_ids

        with pytest.raises(TransportServiceError) as exc_info:
            await svc_b.get_vehicle(tenant_id=tenant_b["id"], vehicle_id=vehicle_id)
        assert exc_info.value.code == "not_found"

    async def test_route_tenant_isolation(self, admin_session, app_session):
        """Tenant B cannot see Tenant A's routes."""
        tenant_a, fixtures_a = await seed_full_tenant(admin_session, "route-a")
        tenant_b, fixtures_b = await seed_full_tenant(admin_session, "route-b")
        await admin_session.commit()

        # Create route as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        svc = RouteService(app_session)

        route = await svc.create_route(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            name="Isolation Route",
            route_code="ISOR",
            route_type="both",
        )
        await app_session.flush()
        route_id = route.id

        # Switch to Tenant B -- should NOT see Tenant A's route
        await set_app_tenant_context(app_session, tenant_b["id"])
        svc_b = RouteService(app_session)

        routes, total = await svc_b.get_routes(
            tenant_id=tenant_b["id"],
            school_id=fixtures_b["school_id"],
        )
        route_ids = [r.id for r in routes]
        assert route_id not in route_ids

        with pytest.raises(TransportServiceError) as exc_info:
            await svc_b.get_route(tenant_id=tenant_b["id"], route_id=route_id)
        assert exc_info.value.code == "not_found"

    async def test_transport_assignment_tenant_isolation(self, admin_session, app_session):
        """Tenant B cannot see Tenant A's transport assignments."""
        tenant_a, fixtures_a = await seed_full_tenant(admin_session, "ta-a")
        tenant_b, fixtures_b = await seed_full_tenant(admin_session, "ta-b")
        await admin_session.commit()

        # Create route, stop, and assignment as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        route_svc = RouteService(app_session)
        assign_svc = TransportAssignmentService(app_session)

        route = await route_svc.create_route_with_stops(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            name="TA Iso Route",
            route_code=f"TAI{uuid4().hex[:3]}",
            route_type="both",
            stops_data=[{"stop_name": "TA Stop", "stop_order": 1}],
        )
        await app_session.flush()
        stop_id = route.stops[0].id

        assignment = await assign_svc.assign_student(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            student_id=fixtures_a["student_id"],
            route_id=route.id,
            stop_id=stop_id,
            academic_year_id=fixtures_a["academic_year_id"],
        )
        await app_session.flush()
        assignment_id = assignment.id

        # Switch to Tenant B -- should NOT see Tenant A's assignment
        await set_app_tenant_context(app_session, tenant_b["id"])
        assign_svc_b = TransportAssignmentService(app_session)

        assignments, total = await assign_svc_b.get_assignments(
            tenant_id=tenant_b["id"],
            school_id=fixtures_b["school_id"],
        )
        assignment_ids = [a.id for a in assignments]
        assert assignment_id not in assignment_ids

    async def test_cross_tenant_trip_blocked(self, admin_session, app_session):
        """Tenant B cannot see Tenant A's trip logs."""
        tenant_a, fixtures_a = await seed_full_tenant(admin_session, "trip-a")
        tenant_b, fixtures_b = await seed_full_tenant(admin_session, "trip-b")
        await admin_session.commit()

        # Create vehicle, driver, route, and trip as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        vehicle_svc = VehicleService(app_session)
        driver_svc = DriverService(app_session)
        route_svc = RouteService(app_session)
        trip_svc = TripService(app_session)

        vehicle = await vehicle_svc.create_vehicle(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            registration_number=f"ISO-{uuid4().hex[:6]}",
            vehicle_type="bus",
            capacity=45,
        )
        await app_session.flush()

        driver = await driver_svc.create_driver(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            first_name="Iso",
            last_name="Driver",
            phone="0248888888",
            license_number=f"ISO-DRV-{uuid4().hex[:6]}",
            license_expiry=date.today() + timedelta(days=365),
            license_class="D",
        )
        await app_session.flush()

        route = await route_svc.create_route(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            name="Iso Trip Route",
            route_code=f"ITR{uuid4().hex[:3]}",
            route_type="both",
            vehicle_id=vehicle.id,
            driver_id=driver.id,
        )
        await app_session.flush()

        trip = await trip_svc.create_trip(
            tenant_id=tenant_a["id"],
            school_id=fixtures_a["school_id"],
            route_id=route.id,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            trip_date=date.today(),
            trip_type="morning_pickup",
            student_count=30,
            logged_by_id=fixtures_a["user_id"],
        )
        await app_session.flush()
        trip_id = trip.id

        # Switch to Tenant B -- should NOT see Tenant A's trip
        await set_app_tenant_context(app_session, tenant_b["id"])
        trip_svc_b = TripService(app_session)

        with pytest.raises(TransportServiceError) as exc_info:
            await trip_svc_b.get_trip(tenant_id=tenant_b["id"], trip_id=trip_id)
        assert exc_info.value.code == "not_found"
