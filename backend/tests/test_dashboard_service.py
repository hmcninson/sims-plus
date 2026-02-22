"""
Tests for the DashboardService.

Verifies that dashboard analytics queries return correct results for:
- Overview stats (students, staff, classes, attendance, finance)
- Gender distribution
- Attendance trend
- Fee collection trend

These tests use the two-engine pattern: admin engine to seed data,
app engine (RLS enforced) to run dashboard queries.
"""

import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.services.dashboard import DashboardService
from tests.conftest import admin_session_maker, app_session_maker


@pytest_asyncio.fixture
async def dashboard_tenant():
    """Create a tenant + school with some test data for dashboard queries."""
    tenant_id = uuid4()
    school_id = uuid4()
    subdomain = f"dash-{uuid4().hex[:8]}"

    async with admin_session_maker() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                    subscription_tier, status, max_students, max_staff, is_active)
                VALUES (CAST(:id AS uuid), :sub, :sub, :name,
                    'single_school', 'professional', 'active', 1000, 100, true)
            """),
            {"id": str(tenant_id), "sub": subdomain, "name": "Dashboard Test School"},
        )
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Dashboard School', :slug, 'DSH', 'basic')
            """),
            {"id": str(school_id), "tid": str(tenant_id), "slug": subdomain},
        )
        await session.commit()

    yield {"tenant_id": tenant_id, "school_id": school_id, "subdomain": subdomain}

    # Cleanup
    async with admin_session_maker() as session:
        for table in [
            "student_attendance", "students", "staff",
            "invoices", "payments",
            "terms", "academic_years",
            "classes",
            "schools",
        ]:
            await session.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                {"tid": str(tenant_id)},
            )
        await session.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tenant_id)},
        )
        await session.commit()


# --- Overview Stats ---


@pytest.mark.asyncio
async def test_overview_stats_empty_school(dashboard_tenant):
    """Dashboard stats for a school with no data should return zeros."""
    tid = dashboard_tenant["tenant_id"]

    async with app_session_maker() as session:
        await session.execute(
            text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
            {"tid": str(tid)},
        )

        service = DashboardService(session)
        stats = await service.get_overview_stats(tid)

        assert stats["total_students"] == 0
        assert stats["total_staff"] == 0
        assert stats["total_classes"] == 0
        assert stats["attendance_today"]["rate"] == 0.0
        assert stats["finance"]["total_billed"] == 0.0
        assert stats["finance"]["total_collected"] == 0.0
        assert stats["finance"]["outstanding"] == 0.0

        await session.execute(text("SELECT clear_tenant_context()"))


@pytest.mark.asyncio
async def test_overview_stats_with_students(dashboard_tenant):
    """Dashboard should count active students correctly."""
    tid = dashboard_tenant["tenant_id"]
    sid = dashboard_tenant["school_id"]

    # Seed two active students and one inactive
    async with admin_session_maker() as session:
        for i, status in enumerate(["active", "active", "inactive"]):
            await session.execute(
                text("""
                    INSERT INTO students (id, tenant_id, school_id, student_id, first_name,
                        last_name, date_of_birth, gender, status)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                        :student_id, :fn, :ln, '2015-01-01', 'male', :status)
                """),
                {
                    "id": str(uuid4()),
                    "tid": str(tid),
                    "sid": str(sid),
                    "student_id": f"DSH-{uuid4().hex[:6]}",
                    "fn": f"Student{i}",
                    "ln": "Test",
                    "status": status,
                },
            )
        await session.commit()

    # Query via app session with RLS
    async with app_session_maker() as session:
        await session.execute(
            text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
            {"tid": str(tid)},
        )

        service = DashboardService(session)
        stats = await service.get_overview_stats(tid)

        # Only 2 active students should be counted
        assert stats["total_students"] == 2

        await session.execute(text("SELECT clear_tenant_context()"))


# --- Gender Distribution ---


@pytest.mark.asyncio
async def test_gender_distribution_empty(dashboard_tenant):
    """Gender distribution with no students returns zeros."""
    tid = dashboard_tenant["tenant_id"]

    async with app_session_maker() as session:
        await session.execute(
            text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
            {"tid": str(tid)},
        )

        service = DashboardService(session)
        result = await service.get_gender_distribution(tid)

        assert result["male"] == 0
        assert result["female"] == 0

        await session.execute(text("SELECT clear_tenant_context()"))


@pytest.mark.asyncio
async def test_gender_distribution_with_students(dashboard_tenant):
    """Gender distribution should count male and female students."""
    tid = dashboard_tenant["tenant_id"]
    sid = dashboard_tenant["school_id"]

    # Seed: 3 male, 2 female students
    async with admin_session_maker() as session:
        for i, gender in enumerate(["male", "male", "male", "female", "female"]):
            await session.execute(
                text("""
                    INSERT INTO students (id, tenant_id, school_id, student_id, first_name,
                        last_name, date_of_birth, gender, status)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                        :student_id, :fn, :ln, '2015-01-01', :gender, 'active')
                """),
                {
                    "id": str(uuid4()),
                    "tid": str(tid),
                    "sid": str(sid),
                    "student_id": f"DSH-G-{uuid4().hex[:6]}",
                    "fn": f"GenStudent{i}",
                    "ln": "Test",
                    "gender": gender,
                },
            )
        await session.commit()

    async with app_session_maker() as session:
        await session.execute(
            text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
            {"tid": str(tid)},
        )

        service = DashboardService(session)
        result = await service.get_gender_distribution(tid)

        assert result["male"] == 3
        assert result["female"] == 2

        await session.execute(text("SELECT clear_tenant_context()"))


# --- Attendance Trend ---


@pytest.mark.asyncio
async def test_attendance_trend_empty(dashboard_tenant):
    """Attendance trend with no attendance data returns empty list."""
    tid = dashboard_tenant["tenant_id"]

    async with app_session_maker() as session:
        await session.execute(
            text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
            {"tid": str(tid)},
        )

        service = DashboardService(session)
        result = await service.get_attendance_trend(tid, days=7)

        assert result == []

        await session.execute(text("SELECT clear_tenant_context()"))


# --- Fee Collection Trend ---


@pytest.mark.asyncio
async def test_fee_collection_trend_empty(dashboard_tenant):
    """Fee collection trend with no invoices/payments returns empty list."""
    tid = dashboard_tenant["tenant_id"]

    async with app_session_maker() as session:
        await session.execute(
            text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
            {"tid": str(tid)},
        )

        service = DashboardService(session)
        result = await service.get_fee_collection_trend(tid, months=3)

        assert result == []

        await session.execute(text("SELECT clear_tenant_context()"))


# --- Tenant Isolation ---


@pytest.mark.asyncio
async def test_dashboard_tenant_isolation():
    """Dashboard stats for Tenant A must NOT include Tenant B's students."""
    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    school_a_id = uuid4()
    school_b_id = uuid4()

    async with admin_session_maker() as session:
        # Create two tenants
        for tid, sub, sid in [
            (tenant_a_id, f"dash-a-{uuid4().hex[:6]}", school_a_id),
            (tenant_b_id, f"dash-b-{uuid4().hex[:6]}", school_b_id),
        ]:
            await session.execute(
                text("""
                    INSERT INTO tenants (id, subdomain, slug, name, tenant_type,
                        subscription_tier, status, max_students, max_staff, is_active)
                    VALUES (CAST(:id AS uuid), :sub, :sub, :name,
                        'single_school', 'professional', 'active', 1000, 100, true)
                """),
                {"id": str(tid), "sub": sub, "name": f"Iso {sub}"},
            )
            await session.execute(
                text("""
                    INSERT INTO schools (id, tenant_id, name, slug, school_type)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'basic')
                """),
                {"id": str(sid), "tid": str(tid), "name": f"School {sub}", "slug": sub},
            )

        # Add 2 students to Tenant A, 5 to Tenant B
        for i in range(2):
            await session.execute(
                text("""
                    INSERT INTO students (id, tenant_id, school_id, student_id, first_name,
                        last_name, date_of_birth, gender, status)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                        :student_id, :fn, 'Iso', '2015-01-01', 'male', 'active')
                """),
                {
                    "id": str(uuid4()), "tid": str(tenant_a_id), "sid": str(school_a_id),
                    "student_id": f"ISO-A-{uuid4().hex[:6]}", "fn": f"StudentA{i}",
                },
            )
        for i in range(5):
            await session.execute(
                text("""
                    INSERT INTO students (id, tenant_id, school_id, student_id, first_name,
                        last_name, date_of_birth, gender, status)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                        :student_id, :fn, 'Iso', '2015-01-01', 'female', 'active')
                """),
                {
                    "id": str(uuid4()), "tid": str(tenant_b_id), "sid": str(school_b_id),
                    "student_id": f"ISO-B-{uuid4().hex[:6]}", "fn": f"StudentB{i}",
                },
            )
        await session.commit()

    try:
        # Tenant A should see only 2 students
        async with app_session_maker() as session:
            await session.execute(
                text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
                {"tid": str(tenant_a_id)},
            )
            service_a = DashboardService(session)
            stats_a = await service_a.get_overview_stats(tenant_a_id)
            assert stats_a["total_students"] == 2
            await session.execute(text("SELECT clear_tenant_context()"))

        # Tenant B should see only 5 students
        async with app_session_maker() as session:
            await session.execute(
                text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
                {"tid": str(tenant_b_id)},
            )
            service_b = DashboardService(session)
            stats_b = await service_b.get_overview_stats(tenant_b_id)
            assert stats_b["total_students"] == 5
            await session.execute(text("SELECT clear_tenant_context()"))
    finally:
        # Cleanup both tenants
        async with admin_session_maker() as session:
            for tid in [tenant_a_id, tenant_b_id]:
                for table in ["students", "schools"]:
                    await session.execute(
                        text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                        {"tid": str(tid)},
                    )
                await session.execute(
                    text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
                    {"tid": str(tid)},
                )
            await session.commit()
