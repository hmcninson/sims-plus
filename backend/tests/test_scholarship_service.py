"""
SIMS Plus - Scholarship Service Integration Tests

Tests exercise ScholarshipService directly with a real PostgreSQL database.
Admin session seeds data (bypasses RLS), app session runs under RLS.

Covers:
- Create scholarship with tenant_id
- Duplicate code detection
- Award scholarship to student
- Max recipients limit enforcement
- Revoke scholarship (sets status, records reason)
- Duplicate active award detection
- Scholarship discount applied at invoice generation
- Tenant isolation
"""

import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import text

from app.models.finance import ScholarshipStatus, CoverageType, InvoiceStatus
from app.services.finance.scholarship_service import ScholarshipService
from app.services.finance.invoice_service import InvoiceService
from app.services.finance.fee_structure_service import FeeStructureService
from app.services.finance._shared import FinanceServiceError
from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)


# ---------------------------------------------------------------------------
# Raw SQL helpers for seeding
# ---------------------------------------------------------------------------

_SCHOOL_INSERT = text("""
    INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
        student_id_prefix, staff_id_prefix, is_active,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
        'basic', 'active', 'STU', 'STF', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_AY_INSERT = text("""
    INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
        status, is_current, created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
        :start_date, :end_date, 'active', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_TERM_INSERT = text("""
    INSERT INTO terms (id, tenant_id, academic_year_id, name, short_name,
        sequence, start_date, end_date, status, is_current,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ay_id AS uuid),
        :name, :short_name, :seq, :start_date, :end_date,
        'active', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_STUDENT_INSERT = text("""
    INSERT INTO students (id, tenant_id, student_id, first_name,
        last_name, date_of_birth, gender, status,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid,
        :fn, :ln, '2012-03-10', 'female', 'active',
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_school(session, school_id, tenant_id, slug):
    await session.execute(
        _SCHOOL_INSERT,
        {"id": str(school_id), "tid": str(tenant_id), "name": f"School {slug}", "slug": slug},
    )


async def _seed_academic_year(session, ay_id, tenant_id):
    await session.execute(
        _AY_INSERT,
        {
            "id": str(ay_id), "tid": str(tenant_id), "name": "2025/2026",
            "start_date": date(2025, 9, 1), "end_date": date(2026, 7, 31),
        },
    )


async def _seed_term(session, term_id, tenant_id, ay_id):
    await session.execute(
        _TERM_INSERT,
        {
            "id": str(term_id), "tid": str(tenant_id), "ay_id": str(ay_id),
            "name": "First Term", "short_name": "T1", "seq": 1,
            "start_date": date(2025, 9, 1), "end_date": date(2025, 12, 20),
        },
    )


async def _seed_student(session, student_id, tenant_id, sid, fn, ln):
    await session.execute(
        _STUDENT_INSERT,
        {"id": str(student_id), "tid": str(tenant_id), "sid": sid, "fn": fn, "ln": ln},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


class TestScholarshipService:
    """Service-level tests for ScholarshipService."""

    async def test_create_scholarship_returns_with_tenant_id(self, admin_session, app_session):
        """Creating a scholarship assigns the correct tenant_id."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ScholarshipService(app_session)

        scholarship = await svc.create_scholarship(
            tenant_id=tenant["id"],
            school_id=school_id,
            name="Academic Excellence",
            code="AE-2026",
            scholarship_type="merit",
            coverage_type="percentage",
            coverage_value=Decimal("50.00"),
            description="50% tuition discount for top students",
        )

        assert scholarship.tenant_id == tenant["id"]
        assert scholarship.name == "Academic Excellence"
        assert scholarship.code == "AE-2026"
        assert scholarship.coverage_type == CoverageType.PERCENTAGE
        assert scholarship.coverage_value == Decimal("50.00")
        assert scholarship.is_active is True

    async def test_create_duplicate_code_raises_error(self, admin_session, app_session):
        """Creating a scholarship with a duplicate code raises FinanceServiceError."""
        tenant = await create_test_tenant(admin_session)
        school_id = uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ScholarshipService(app_session)

        await svc.create_scholarship(
            tenant_id=tenant["id"], school_id=school_id,
            name="First", code="DUP-001",
            scholarship_type="partial", coverage_type="fixed_amount",
            coverage_value=Decimal("100.00"),
        )

        with pytest.raises(FinanceServiceError) as exc_info:
            await svc.create_scholarship(
                tenant_id=tenant["id"], school_id=school_id,
                name="Second", code="DUP-001",
                scholarship_type="merit", coverage_type="percentage",
                coverage_value=Decimal("25.00"),
            )

        assert exc_info.value.code == "duplicate_code"

    async def test_award_scholarship_to_student(self, admin_session, app_session):
        """Awarding a scholarship creates a StudentScholarship record."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, student_id = uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_student(admin_session, student_id, tenant["id"], "STU-AW", "Ama", "Award")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ScholarshipService(app_session)

        scholarship = await svc.create_scholarship(
            tenant_id=tenant["id"], school_id=school_id,
            name="Merit Award", code="MA-2026",
            scholarship_type="merit", coverage_type="percentage",
            coverage_value=Decimal("100.00"),
        )

        ss = await svc.award_scholarship(
            tenant_id=tenant["id"],
            scholarship_id=scholarship.id,
            student_id=student_id,
            academic_year_id=ay_id,
            effective_from=date(2025, 9, 1),
            awarded_by=user["id"],
            justification="Top performer",
        )

        assert ss.status == ScholarshipStatus.ACTIVE
        assert ss.student_id == student_id
        assert ss.scholarship_id == scholarship.id
        assert ss.justification == "Top performer"

    async def test_max_recipients_limit_enforced(self, admin_session, app_session):
        """Awarding beyond max_recipients raises FinanceServiceError."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id = uuid4(), uuid4()
        student_1, student_2 = uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_student(admin_session, student_1, tenant["id"], "STU-MR1", "Alice", "A")
        await _seed_student(admin_session, student_2, tenant["id"], "STU-MR2", "Bob", "B")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ScholarshipService(app_session)

        scholarship = await svc.create_scholarship(
            tenant_id=tenant["id"], school_id=school_id,
            name="Limited Award", code="LIM-001",
            scholarship_type="special", coverage_type="fixed_amount",
            coverage_value=Decimal("200.00"),
            max_recipients=1,
        )

        # First award succeeds
        await svc.award_scholarship(
            tenant_id=tenant["id"],
            scholarship_id=scholarship.id,
            student_id=student_1,
            academic_year_id=ay_id,
            effective_from=date(2025, 9, 1),
        )

        # Second award exceeds limit
        with pytest.raises(FinanceServiceError) as exc_info:
            await svc.award_scholarship(
                tenant_id=tenant["id"],
                scholarship_id=scholarship.id,
                student_id=student_2,
                academic_year_id=ay_id,
                effective_from=date(2025, 9, 1),
            )

        assert exc_info.value.code == "max_recipients"

    async def test_duplicate_active_award_raises_error(self, admin_session, app_session):
        """Awarding the same scholarship to the same student twice raises an error."""
        tenant = await create_test_tenant(admin_session)
        school_id, ay_id, student_id = uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_student(admin_session, student_id, tenant["id"], "STU-DA", "Esi", "Dup")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ScholarshipService(app_session)

        scholarship = await svc.create_scholarship(
            tenant_id=tenant["id"], school_id=school_id,
            name="Once Only", code="ONCE-001",
            scholarship_type="partial", coverage_type="percentage",
            coverage_value=Decimal("30.00"),
        )

        await svc.award_scholarship(
            tenant_id=tenant["id"],
            scholarship_id=scholarship.id,
            student_id=student_id,
            academic_year_id=ay_id,
            effective_from=date(2025, 9, 1),
        )

        with pytest.raises(FinanceServiceError) as exc_info:
            await svc.award_scholarship(
                tenant_id=tenant["id"],
                scholarship_id=scholarship.id,
                student_id=student_id,
                academic_year_id=ay_id,
                effective_from=date(2025, 9, 1),
            )

        assert exc_info.value.code == "duplicate_award"

    async def test_revoke_scholarship_sets_status_and_reason(self, admin_session, app_session):
        """Revoking a scholarship sets status=revoked and stores the reason."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, student_id = uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_student(admin_session, student_id, tenant["id"], "STU-RV", "Kwame", "Revoke")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ScholarshipService(app_session)

        scholarship = await svc.create_scholarship(
            tenant_id=tenant["id"], school_id=school_id,
            name="Revocable", code="REV-001",
            scholarship_type="need_based", coverage_type="fixed_amount",
            coverage_value=Decimal("300.00"),
        )

        ss = await svc.award_scholarship(
            tenant_id=tenant["id"],
            scholarship_id=scholarship.id,
            student_id=student_id,
            academic_year_id=ay_id,
            effective_from=date(2025, 9, 1),
        )

        revoked = await svc.revoke_scholarship(
            tenant_id=tenant["id"],
            student_scholarship_id=ss.id,
            revoked_by=user["id"],
            reason="Academic misconduct",
            create_adjustment_invoices=False,
        )

        assert revoked.status == ScholarshipStatus.REVOKED
        assert revoked.revoke_reason == "Academic misconduct"
        assert revoked.revoked_by == user["id"]

    async def test_revoke_already_revoked_raises_error(self, admin_session, app_session):
        """Revoking an already-revoked scholarship raises FinanceServiceError."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, student_id = uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_student(admin_session, student_id, tenant["id"], "STU-RR", "Yaa", "Double")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ScholarshipService(app_session)

        scholarship = await svc.create_scholarship(
            tenant_id=tenant["id"], school_id=school_id,
            name="Double Revoke", code="DR-001",
            scholarship_type="athletic", coverage_type="percentage",
            coverage_value=Decimal("25.00"),
        )
        ss = await svc.award_scholarship(
            tenant_id=tenant["id"],
            scholarship_id=scholarship.id,
            student_id=student_id,
            academic_year_id=ay_id,
            effective_from=date(2025, 9, 1),
        )
        await svc.revoke_scholarship(
            tenant_id=tenant["id"],
            student_scholarship_id=ss.id,
            revoked_by=user["id"],
            reason="First revoke",
            create_adjustment_invoices=False,
        )

        with pytest.raises(FinanceServiceError) as exc_info:
            await svc.revoke_scholarship(
                tenant_id=tenant["id"],
                student_scholarship_id=ss.id,
                revoked_by=user["id"],
                reason="Second revoke",
            )

        assert exc_info.value.code == "already_revoked"

    async def test_scholarship_discount_applied_at_invoice_generation(self, admin_session, app_session):
        """Invoice generated for a student with an active scholarship includes the discount."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        school_id, ay_id, term_id, student_id = uuid4(), uuid4(), uuid4(), uuid4()
        await _seed_school(admin_session, school_id, tenant["id"], tenant["subdomain"])
        await _seed_academic_year(admin_session, ay_id, tenant["id"])
        await _seed_term(admin_session, term_id, tenant["id"], ay_id)
        await _seed_student(admin_session, student_id, tenant["id"], "STU-SD", "Esi", "Scholar")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])

        # Create a 50% scholarship
        sch_svc = ScholarshipService(app_session)
        scholarship = await sch_svc.create_scholarship(
            tenant_id=tenant["id"], school_id=school_id,
            name="Half Scholarship", code="HALF-001",
            scholarship_type="merit", coverage_type="percentage",
            coverage_value=Decimal("50.00"),
        )
        await sch_svc.award_scholarship(
            tenant_id=tenant["id"],
            scholarship_id=scholarship.id,
            student_id=student_id,
            academic_year_id=ay_id,
            effective_from=date(2025, 9, 1),
        )

        # Create fee structure: 1000 total
        fs_svc = FeeStructureService(app_session)
        fs = await fs_svc.create_fee_structure(
            tenant_id=tenant["id"], school_id=school_id,
            name="Scholar Fees",
            items=[{"name": "Tuition", "amount": "1000.00", "is_optional": False}],
        )

        # Generate invoice -- scholarship should auto-apply
        inv_svc = InvoiceService(app_session)
        invoice = await inv_svc.create_invoice(
            tenant_id=tenant["id"], school_id=school_id,
            student_id=student_id, academic_year_id=ay_id, term_id=term_id,
            fee_structure_id=fs.id,
        )

        assert invoice.subtotal == Decimal("1000.00")
        assert invoice.scholarship_discount == Decimal("500.00")
        assert invoice.total_amount == Decimal("500.00")


class TestScholarshipTenantIsolation:
    """Tenant A must NOT see Tenant B's scholarships."""

    async def test_tenant_a_cannot_see_tenant_b_scholarships(self, admin_session, app_session):
        """Scholarships from Tenant A are invisible to Tenant B under RLS."""
        tenant_a = await create_test_tenant(admin_session)
        school_a = uuid4()
        await _seed_school(admin_session, school_a, tenant_a["id"], tenant_a["subdomain"])

        tenant_b = await create_test_tenant(admin_session)
        school_b = uuid4()
        await _seed_school(admin_session, school_b, tenant_b["id"], tenant_b["subdomain"])
        await admin_session.commit()

        # Create scholarship as Tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        svc = ScholarshipService(app_session)
        sch_a = await svc.create_scholarship(
            tenant_id=tenant_a["id"], school_id=school_a,
            name="Tenant A Scholarship", code="TA-001",
            scholarship_type="full", coverage_type="percentage",
            coverage_value=Decimal("100.00"),
        )
        sch_a_id = sch_a.id

        # Switch to Tenant B
        await set_app_tenant_context(app_session, tenant_b["id"])

        scholarships, total = await svc.list_scholarships(tenant_id=tenant_b["id"])
        scholarship_ids = {s.id for s in scholarships}
        assert sch_a_id not in scholarship_ids
        assert total == 0

        found = await svc.get_scholarship(tenant_b["id"], sch_a_id)
        assert found is None
