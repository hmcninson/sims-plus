"""
Transport Service Tests

Tests for vehicle, driver, route, transport assignment, and trip
service operations.

Uses the two-engine pattern:
- admin_session: superuser, seeds data (bypasses RLS)
- app_session: sims_app_user, RLS enforced

IMPORTANT: These tests require a running sims_plus_test database with
RLS policies applied (alembic upgrade head).
"""

from datetime import date, time, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

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
    pytest.mark.xdist_group("transport_serial"),
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


async def seed_student(admin_session, tenant_id, school_id, section_id):
    """Seed a student. Returns student_id."""
    student_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO students (
                id, tenant_id, school_id, section_id,
                student_id, first_name, last_name,
                date_of_birth, gender, status,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:sid AS uuid), CAST(:sec_id AS uuid),
                :student_num, :fn, :ln,
                '2012-05-15', 'male', 'active',
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
        },
    )
    return student_id


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


async def seed_transport_fixtures(admin_session, tenant_id):
    """Seed all prerequisites for transport tests.
    Returns dict with all prerequisite IDs.
    """
    school_id = await seed_school(admin_session, tenant_id)
    class_id, section_id = await seed_class_and_section(admin_session, tenant_id)
    student_id = await seed_student(admin_session, tenant_id, school_id, section_id)
    student_id_2 = await seed_student(admin_session, tenant_id, school_id, section_id)
    user = await create_test_user(admin_session, tenant_id)
    ay_id = await seed_academic_year(admin_session, tenant_id)
    await admin_session.flush()

    return {
        "school_id": school_id,
        "class_id": class_id,
        "section_id": section_id,
        "student_id": student_id,
        "student_id_2": student_id_2,
        "user_id": user["id"],
        "academic_year_id": ay_id,
    }


# ===================================================================
# Vehicle Service Tests
# ===================================================================


class TestVehicleService:
    """Tests for vehicle CRUD and maintenance tracking."""

    async def test_create_vehicle(self, admin_session, app_session):
        """Creating a vehicle returns a valid vehicle object."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = VehicleService(app_session)

        vehicle = await svc.create_vehicle(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            registration_number="GR-1234-21",
            vehicle_type="bus",
            capacity=45,
            make="Toyota",
            model_name="Coaster",
            year=2020,
        )
        assert vehicle.registration_number == "GR-1234-21"
        assert vehicle.capacity == 45
        assert vehicle.status.value == "active"

    async def test_create_vehicle_duplicate_registration_rejected(self, admin_session, app_session):
        """Duplicate registration number within the same tenant is rejected."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = VehicleService(app_session)

        await svc.create_vehicle(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            registration_number="GR-5678-22",
            vehicle_type="minibus",
            capacity=30,
        )
        await app_session.flush()

        with pytest.raises(TransportServiceError) as exc_info:
            await svc.create_vehicle(
                tenant_id=tenant["id"],
                school_id=fixtures["school_id"],
                registration_number="GR-5678-22",
                vehicle_type="bus",
                capacity=50,
            )
        assert exc_info.value.code == "duplicate_registration"

    async def test_get_vehicles_with_search(self, admin_session, app_session):
        """Searching vehicles matches against registration/make/model."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = VehicleService(app_session)

        await svc.create_vehicle(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            registration_number="GT-9999-23",
            vehicle_type="bus",
            capacity=45,
            make="Mercedes",
            model_name="Sprinter",
        )
        await app_session.flush()

        vehicles, total = await svc.get_vehicles(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            search="Mercedes",
        )
        assert total >= 1
        assert any(v.registration_number == "GT-9999-23" for v in vehicles)

    async def test_update_vehicle(self, admin_session, app_session):
        """Updating a vehicle changes its attributes."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = VehicleService(app_session)

        vehicle = await svc.create_vehicle(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            registration_number="GN-1111-24",
            vehicle_type="van",
            capacity=15,
        )
        await app_session.flush()

        updated = await svc.update_vehicle(
            tenant_id=tenant["id"],
            vehicle_id=vehicle.id,
            capacity=18,
            make="Nissan",
        )
        assert updated.capacity == 18
        assert updated.make == "Nissan"

    async def test_delete_vehicle_soft_delete(self, admin_session, app_session):
        """Deleting a vehicle sets deleted_at (soft delete)."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = VehicleService(app_session)

        vehicle = await svc.create_vehicle(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            registration_number="GS-2222-24",
            vehicle_type="car",
            capacity=5,
        )
        await app_session.flush()

        result = await svc.delete_vehicle(
            tenant_id=tenant["id"], vehicle_id=vehicle.id
        )
        assert result is True

        with pytest.raises(TransportServiceError) as exc_info:
            await svc.get_vehicle(tenant_id=tenant["id"], vehicle_id=vehicle.id)
        assert exc_info.value.code == "not_found"

    async def test_delete_vehicle_with_active_routes_rejected(self, admin_session, app_session):
        """Deleting a vehicle assigned to active routes is rejected."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        vehicle_svc = VehicleService(app_session)
        route_svc = RouteService(app_session)

        vehicle = await vehicle_svc.create_vehicle(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            registration_number="GW-3333-24",
            vehicle_type="bus",
            capacity=45,
        )
        await app_session.flush()

        await route_svc.create_route(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            name="Test Route",
            route_code=f"TR{uuid4().hex[:4]}",
            route_type="both",
            vehicle_id=vehicle.id,
        )
        await app_session.flush()

        with pytest.raises(TransportServiceError) as exc_info:
            await vehicle_svc.delete_vehicle(
                tenant_id=tenant["id"], vehicle_id=vehicle.id
            )
        assert exc_info.value.code == "vehicle_in_use"

    async def test_create_maintenance_record(self, admin_session, app_session):
        """Creating a maintenance record for a vehicle works."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = VehicleService(app_session)

        vehicle = await svc.create_vehicle(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            registration_number="GE-4444-24",
            vehicle_type="bus",
            capacity=45,
        )
        await app_session.flush()

        maintenance = await svc.create_maintenance(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            vehicle_id=vehicle.id,
            logged_by_id=fixtures["user_id"],
            maintenance_type="routine",
            description="Oil change and filter replacement",
            service_date=date.today(),
            cost=250.00,
        )
        assert maintenance.maintenance_type.value == "routine"
        assert maintenance.vehicle_id == vehicle.id

    async def test_get_maintenance_history(self, admin_session, app_session):
        """Maintenance history returns records ordered by most recent first."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = VehicleService(app_session)

        vehicle = await svc.create_vehicle(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            registration_number="GH-5555-24",
            vehicle_type="bus",
            capacity=45,
        )
        await app_session.flush()

        await svc.create_maintenance(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            vehicle_id=vehicle.id,
            logged_by_id=fixtures["user_id"],
            maintenance_type="repair",
            description="Brake pad replacement",
            service_date=date.today(),
        )
        await app_session.flush()

        records, total = await svc.get_maintenance_history(
            tenant_id=tenant["id"],
            vehicle_id=vehicle.id,
        )
        assert total >= 1
        assert len(records) >= 1


# ===================================================================
# Driver Service Tests
# ===================================================================


class TestDriverService:
    """Tests for driver CRUD operations."""

    async def test_create_driver(self, admin_session, app_session):
        """Creating a driver returns a valid driver object."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = DriverService(app_session)

        driver = await svc.create_driver(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            first_name="Kwesi",
            last_name="Boateng",
            phone="0241234567",
            license_number="DRV-001-2024",
            license_expiry=date.today() + timedelta(days=365),
            license_class="D",
        )
        assert driver.first_name == "Kwesi"
        assert driver.license_number == "DRV-001-2024"
        assert driver.status.value == "active"

    async def test_create_driver_duplicate_license_rejected(self, admin_session, app_session):
        """Duplicate license number within the same tenant is rejected."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = DriverService(app_session)

        await svc.create_driver(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            first_name="Ama",
            last_name="Serwaa",
            phone="0249876543",
            license_number="DRV-002-2024",
            license_expiry=date.today() + timedelta(days=365),
            license_class="C",
        )
        await app_session.flush()

        with pytest.raises(TransportServiceError) as exc_info:
            await svc.create_driver(
                tenant_id=tenant["id"],
                school_id=fixtures["school_id"],
                first_name="Kofi",
                last_name="Mensah",
                phone="0241111111",
                license_number="DRV-002-2024",
                license_expiry=date.today() + timedelta(days=365),
                license_class="D",
            )
        assert exc_info.value.code == "duplicate_license"

    async def test_get_drivers_with_search(self, admin_session, app_session):
        """Searching drivers matches against name, phone, and license."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = DriverService(app_session)

        await svc.create_driver(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            first_name="Yaw",
            last_name="Appiah",
            phone="0242222222",
            license_number="DRV-003-2024",
            license_expiry=date.today() + timedelta(days=365),
            license_class="D",
        )
        await app_session.flush()

        drivers, total = await svc.get_drivers(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            search="Appiah",
        )
        assert total >= 1

    async def test_update_driver(self, admin_session, app_session):
        """Updating a driver changes its attributes."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = DriverService(app_session)

        driver = await svc.create_driver(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            first_name="Akua",
            last_name="Donkor",
            phone="0243333333",
            license_number="DRV-004-2024",
            license_expiry=date.today() + timedelta(days=365),
            license_class="C",
        )
        await app_session.flush()

        updated = await svc.update_driver(
            tenant_id=tenant["id"],
            driver_id=driver.id,
            phone="0244444444",
        )
        assert updated.phone == "0244444444"

    async def test_delete_driver_soft_delete(self, admin_session, app_session):
        """Deleting a driver sets deleted_at (soft delete)."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = DriverService(app_session)

        driver = await svc.create_driver(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            first_name="Esi",
            last_name="Amoah",
            phone="0245555555",
            license_number="DRV-005-2024",
            license_expiry=date.today() + timedelta(days=365),
            license_class="B",
        )
        await app_session.flush()

        result = await svc.delete_driver(
            tenant_id=tenant["id"], driver_id=driver.id
        )
        assert result is True

        with pytest.raises(TransportServiceError) as exc_info:
            await svc.get_driver(tenant_id=tenant["id"], driver_id=driver.id)
        assert exc_info.value.code == "not_found"


# ===================================================================
# Route Service Tests
# ===================================================================


class TestRouteService:
    """Tests for route CRUD and stop management."""

    async def test_create_route(self, admin_session, app_session):
        """Creating a route returns a valid route object."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = RouteService(app_session)

        route = await svc.create_route(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            name="East Legon Route",
            route_code="ELR",
            route_type="both",
            distance_km=15.5,
            estimated_duration_minutes=45,
        )
        assert route.name == "East Legon Route"
        assert route.route_code == "ELR"
        assert route.is_active is True

    async def test_create_route_with_stops(self, admin_session, app_session):
        """Creating a route with stops creates both in one transaction."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = RouteService(app_session)

        route = await svc.create_route_with_stops(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            name="Tema Route",
            route_code=f"TMR{uuid4().hex[:3]}",
            route_type="morning_pickup",
            stops_data=[
                {"stop_name": "Tema Station", "stop_order": 1},
                {"stop_name": "Community 1 Junction", "stop_order": 2},
                {"stop_name": "School Gate", "stop_order": 3},
            ],
        )
        assert len(route.stops) == 3
        assert route.stops[0].stop_name == "Tema Station"

    async def test_get_route_detail_with_stops(self, admin_session, app_session):
        """get_route returns a route with stops eagerly loaded."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = RouteService(app_session)

        created = await svc.create_route_with_stops(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            name="Spintex Route",
            route_code=f"SPX{uuid4().hex[:3]}",
            route_type="afternoon_dropoff",
            stops_data=[
                {"stop_name": "Spintex Mall", "stop_order": 1},
                {"stop_name": "Manet Junction", "stop_order": 2},
            ],
        )
        await app_session.flush()

        route = await svc.get_route(
            tenant_id=tenant["id"], route_id=created.id
        )
        assert route.name == "Spintex Route"
        assert len(route.stops) == 2

    async def test_update_route(self, admin_session, app_session):
        """Updating a route changes its attributes."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = RouteService(app_session)

        route = await svc.create_route(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            name="Madina Route",
            route_code=f"MDR{uuid4().hex[:3]}",
            route_type="both",
        )
        await app_session.flush()

        updated = await svc.update_route(
            tenant_id=tenant["id"],
            route_id=route.id,
            estimated_duration_minutes=60,
        )
        assert updated.estimated_duration_minutes == 60

    async def test_delete_route_soft_delete(self, admin_session, app_session):
        """Deleting a route sets deleted_at (soft delete)."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = RouteService(app_session)

        route = await svc.create_route(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            name="Kasoa Route",
            route_code=f"KSR{uuid4().hex[:3]}",
            route_type="both",
        )
        await app_session.flush()

        result = await svc.delete_route(
            tenant_id=tenant["id"], route_id=route.id
        )
        assert result is True

        with pytest.raises(TransportServiceError) as exc_info:
            await svc.get_route(tenant_id=tenant["id"], route_id=route.id)
        assert exc_info.value.code == "not_found"

    async def test_add_stop_to_route(self, admin_session, app_session):
        """Adding a stop to an existing route works."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = RouteService(app_session)

        route = await svc.create_route(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            name="Achimota Route",
            route_code=f"ACH{uuid4().hex[:3]}",
            route_type="both",
        )
        await app_session.flush()

        stop = await svc.add_stop(
            tenant_id=tenant["id"],
            route_id=route.id,
            stop_name="Achimota Station",
            stop_order=1,
        )
        assert stop.stop_name == "Achimota Station"
        assert stop.route_id == route.id

    async def test_reorder_stops(self, admin_session, app_session):
        """Reordering stops updates their stop_order values."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = RouteService(app_session)

        route = await svc.create_route_with_stops(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            name="Reorder Route",
            route_code=f"ROR{uuid4().hex[:3]}",
            route_type="both",
            stops_data=[
                {"stop_name": "Stop A", "stop_order": 1},
                {"stop_name": "Stop B", "stop_order": 2},
                {"stop_name": "Stop C", "stop_order": 3},
            ],
        )
        await app_session.flush()

        stop_ids = [s.id for s in route.stops]
        # Reverse the order: C, B, A
        reversed_ids = list(reversed(stop_ids))

        reordered = await svc.reorder_stops(
            tenant_id=tenant["id"],
            route_id=route.id,
            stop_ids_in_order=reversed_ids,
        )
        assert reordered[0].stop_name == "Stop C"
        assert reordered[0].stop_order == 1

    async def test_get_route_manifest(self, admin_session, app_session):
        """Route manifest returns students grouped by stop."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        route_svc = RouteService(app_session)
        assign_svc = TransportAssignmentService(app_session)

        route = await route_svc.create_route_with_stops(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            name="Manifest Route",
            route_code=f"MFR{uuid4().hex[:3]}",
            route_type="both",
            stops_data=[
                {"stop_name": "Pickup Point A", "stop_order": 1},
            ],
        )
        await app_session.flush()
        stop_id = route.stops[0].id

        await assign_svc.assign_student(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            route_id=route.id,
            stop_id=stop_id,
            academic_year_id=fixtures["academic_year_id"],
        )
        await app_session.flush()

        manifest = await route_svc.get_route_manifest(
            tenant_id=tenant["id"],
            route_id=route.id,
            academic_year_id=fixtures["academic_year_id"],
        )
        assert manifest["total_students"] == 1
        assert len(manifest["stops"]) == 1
        assert len(manifest["stops"][0]["students"]) == 1


# ===================================================================
# Transport Assignment Service Tests
# ===================================================================


class TestTransportAssignmentService:
    """Tests for student transport assignment operations."""

    async def _create_route_with_stop(self, app_session, tenant_id, school_id, vehicle_id=None):
        """Helper to create a route with one stop. Returns (route, stop)."""
        route_svc = RouteService(app_session)
        route = await route_svc.create_route_with_stops(
            tenant_id=tenant_id,
            school_id=school_id,
            name=f"Route-{uuid4().hex[:6]}",
            route_code=f"R{uuid4().hex[:5]}",
            route_type="both",
            stops_data=[{"stop_name": "Main Stop", "stop_order": 1}],
            vehicle_id=vehicle_id,
        )
        await app_session.flush()
        return route, route.stops[0]

    async def test_assign_student_to_route(self, admin_session, app_session):
        """Assigning a student to a route creates an active transport record."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = TransportAssignmentService(app_session)
        route, stop = await self._create_route_with_stop(
            app_session, tenant["id"], fixtures["school_id"]
        )

        assignment = await svc.assign_student(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            route_id=route.id,
            stop_id=stop.id,
            academic_year_id=fixtures["academic_year_id"],
        )
        assert assignment.student_id == fixtures["student_id"]
        assert assignment.status.value == "active"

    async def test_assign_duplicate_rejected(self, admin_session, app_session):
        """Duplicate assignment for the same student+year is rejected."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = TransportAssignmentService(app_session)
        route, stop = await self._create_route_with_stop(
            app_session, tenant["id"], fixtures["school_id"]
        )

        await svc.assign_student(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            route_id=route.id,
            stop_id=stop.id,
            academic_year_id=fixtures["academic_year_id"],
        )
        await app_session.flush()

        with pytest.raises(TransportServiceError) as exc_info:
            await svc.assign_student(
                tenant_id=tenant["id"],
                school_id=fixtures["school_id"],
                student_id=fixtures["student_id"],
                route_id=route.id,
                stop_id=stop.id,
                academic_year_id=fixtures["academic_year_id"],
            )
        assert exc_info.value.code == "duplicate_assignment"

    async def test_assign_over_capacity_rejected(self, admin_session, app_session):
        """Assigning to a route at full vehicle capacity is rejected."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        vehicle_svc = VehicleService(app_session)
        svc = TransportAssignmentService(app_session)

        # Create a vehicle with capacity=1
        vehicle = await vehicle_svc.create_vehicle(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            registration_number=f"GR-{uuid4().hex[:4]}-24",
            vehicle_type="car",
            capacity=1,
        )
        await app_session.flush()

        route, stop = await self._create_route_with_stop(
            app_session, tenant["id"], fixtures["school_id"],
            vehicle_id=vehicle.id,
        )

        # First assignment fills the seat
        await svc.assign_student(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            route_id=route.id,
            stop_id=stop.id,
            academic_year_id=fixtures["academic_year_id"],
        )
        await app_session.flush()

        # Second assignment should fail (over capacity)
        with pytest.raises(TransportServiceError) as exc_info:
            await svc.assign_student(
                tenant_id=tenant["id"],
                school_id=fixtures["school_id"],
                student_id=fixtures["student_id_2"],
                route_id=route.id,
                stop_id=stop.id,
                academic_year_id=fixtures["academic_year_id"],
            )
        assert exc_info.value.code == "route_full"

    async def test_unassign_student_sets_cancelled(self, admin_session, app_session):
        """Unassigning a student sets the status to cancelled."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = TransportAssignmentService(app_session)
        route, stop = await self._create_route_with_stop(
            app_session, tenant["id"], fixtures["school_id"]
        )

        assignment = await svc.assign_student(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            route_id=route.id,
            stop_id=stop.id,
            academic_year_id=fixtures["academic_year_id"],
        )
        await app_session.flush()

        result = await svc.unassign_student(
            tenant_id=tenant["id"],
            assignment_id=assignment.id,
        )
        assert result.status.value == "cancelled"

    async def test_update_assignment_route_change(self, admin_session, app_session):
        """Updating an assignment to a different route works."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = TransportAssignmentService(app_session)

        route1, stop1 = await self._create_route_with_stop(
            app_session, tenant["id"], fixtures["school_id"]
        )
        route2, stop2 = await self._create_route_with_stop(
            app_session, tenant["id"], fixtures["school_id"]
        )

        assignment = await svc.assign_student(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            student_id=fixtures["student_id"],
            route_id=route1.id,
            stop_id=stop1.id,
            academic_year_id=fixtures["academic_year_id"],
        )
        await app_session.flush()

        updated = await svc.update_assignment(
            tenant_id=tenant["id"],
            assignment_id=assignment.id,
            route_id=route2.id,
            stop_id=stop2.id,
        )
        assert updated.route_id == route2.id


# ===================================================================
# Trip Service Tests
# ===================================================================


class TestTripService:
    """Tests for trip logging and lifecycle management."""

    async def _create_trip_prerequisites(self, admin_session, app_session):
        """Create tenant, school, vehicle, driver, and route for trip tests."""
        tenant = await create_test_tenant(admin_session)
        fixtures = await seed_transport_fixtures(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        vehicle_svc = VehicleService(app_session)
        driver_svc = DriverService(app_session)
        route_svc = RouteService(app_session)

        vehicle = await vehicle_svc.create_vehicle(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            registration_number=f"GR-{uuid4().hex[:4]}-25",
            vehicle_type="bus",
            capacity=45,
        )
        await app_session.flush()

        driver = await driver_svc.create_driver(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            first_name="Trip",
            last_name="Driver",
            phone="0249999999",
            license_number=f"DRV-{uuid4().hex[:6]}",
            license_expiry=date.today() + timedelta(days=365),
            license_class="D",
        )
        await app_session.flush()

        route = await route_svc.create_route(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            name=f"Trip Route {uuid4().hex[:6]}",
            route_code=f"TRP{uuid4().hex[:3]}",
            route_type="both",
            vehicle_id=vehicle.id,
            driver_id=driver.id,
        )
        await app_session.flush()

        return tenant, fixtures, vehicle, driver, route

    async def test_create_trip(self, admin_session, app_session):
        """Creating a trip returns a valid trip log entry."""
        tenant, fixtures, vehicle, driver, route = (
            await self._create_trip_prerequisites(admin_session, app_session)
        )
        trip_svc = TripService(app_session)

        trip = await trip_svc.create_trip(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            route_id=route.id,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            trip_date=date.today(),
            trip_type="morning_pickup",
            student_count=30,
            logged_by_id=fixtures["user_id"],
        )
        assert trip.trip_type.value == "morning_pickup"
        assert trip.student_count == 30
        assert trip.status.value == "scheduled"

    async def test_trip_lifecycle(self, admin_session, app_session):
        """Full trip lifecycle: scheduled -> in_progress -> completed."""
        tenant, fixtures, vehicle, driver, route = (
            await self._create_trip_prerequisites(admin_session, app_session)
        )
        trip_svc = TripService(app_session)

        trip = await trip_svc.create_trip(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            route_id=route.id,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            trip_date=date.today(),
            trip_type="morning_pickup",
            student_count=25,
            logged_by_id=fixtures["user_id"],
            odometer_start=50000,
        )
        await app_session.flush()

        # Start the trip
        trip = await trip_svc.start_trip(
            tenant_id=tenant["id"],
            trip_id=trip.id,
            departure_time=time(6, 30),
        )
        assert trip.status.value == "in_progress"
        assert trip.departure_time == time(6, 30)

        # Complete the trip
        trip = await trip_svc.complete_trip(
            tenant_id=tenant["id"],
            trip_id=trip.id,
            arrival_time=time(7, 45),
            odometer_end=50025,
        )
        assert trip.status.value == "completed"
        assert trip.arrival_time == time(7, 45)
        assert trip.odometer_end == 50025

    async def test_complete_trip_validates_odometer(self, admin_session, app_session):
        """Completing a trip with odometer_end < odometer_start is rejected."""
        tenant, fixtures, vehicle, driver, route = (
            await self._create_trip_prerequisites(admin_session, app_session)
        )
        trip_svc = TripService(app_session)

        trip = await trip_svc.create_trip(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            route_id=route.id,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            trip_date=date.today(),
            trip_type="afternoon_dropoff",
            student_count=20,
            logged_by_id=fixtures["user_id"],
            odometer_start=60000,
        )
        await app_session.flush()

        trip = await trip_svc.start_trip(
            tenant_id=tenant["id"], trip_id=trip.id,
        )
        await app_session.flush()

        with pytest.raises(TransportServiceError) as exc_info:
            await trip_svc.complete_trip(
                tenant_id=tenant["id"],
                trip_id=trip.id,
                odometer_end=59000,  # Less than start
            )
        assert exc_info.value.code == "invalid_odometer"

    async def test_cancel_trip(self, admin_session, app_session):
        """Cancelling a scheduled trip sets status to cancelled."""
        tenant, fixtures, vehicle, driver, route = (
            await self._create_trip_prerequisites(admin_session, app_session)
        )
        trip_svc = TripService(app_session)

        trip = await trip_svc.create_trip(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            route_id=route.id,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            trip_date=date.today() + timedelta(days=1),
            trip_type="field_trip",
            student_count=40,
            logged_by_id=fixtures["user_id"],
        )
        await app_session.flush()

        cancelled = await trip_svc.cancel_trip(
            tenant_id=tenant["id"], trip_id=trip.id,
        )
        assert cancelled.status.value == "cancelled"

    async def test_get_trip_stats(self, admin_session, app_session):
        """Trip stats returns monthly aggregate data."""
        tenant, fixtures, vehicle, driver, route = (
            await self._create_trip_prerequisites(admin_session, app_session)
        )
        trip_svc = TripService(app_session)

        today = date.today()
        trip = await trip_svc.create_trip(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            route_id=route.id,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            trip_date=today,
            trip_type="morning_pickup",
            student_count=30,
            logged_by_id=fixtures["user_id"],
        )
        await app_session.flush()

        # Start and complete the trip so it counts in completed stats
        trip = await trip_svc.start_trip(tenant_id=tenant["id"], trip_id=trip.id)
        trip = await trip_svc.complete_trip(tenant_id=tenant["id"], trip_id=trip.id)
        await app_session.flush()

        stats = await trip_svc.get_trip_stats(
            tenant_id=tenant["id"],
            school_id=fixtures["school_id"],
            month=today.month,
            year=today.year,
        )
        assert stats["total_trips"] >= 1
        assert stats["completed_trips"] >= 1
        assert stats["avg_student_count"] > 0
