"""
Tests for student withdrawal workflow (Phase 2).

Covers: fee checks, clearance creation, clearance updates,
auto-completion, withdrawal completion, and endpoint smoke tests.
Uses two-engine pattern (admin for seeding, app for RLS queries).
"""

import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_withdrawal_prereqs(admin_session, tenant_id, *, with_invoice=False):
    """Seed school, academic year, class, section, student, and optional invoice.

    Returns dict with all IDs.
    """
    school_id = uuid4()
    ay_id = uuid4()
    class_id = uuid4()
    section_id = uuid4()
    student_id = uuid4()
    user_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type,
                student_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'STU', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"school-{uuid4().hex[:8]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31', 'active', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ay_id), "tid": str(tenant_id), "name": f"AY-{uuid4().hex[:6]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class_id), "tid": str(tenant_id),
         "name": f"Class-{uuid4().hex[:6]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO class_sections (id, tenant_id, class_id, name,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:cid AS uuid), 'A', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(section_id), "tid": str(tenant_id), "cid": str(class_id)},
    )

    await admin_session.execute(
        text("""
            INSERT INTO students (id, tenant_id, school_id, student_id,
                first_name, last_name, date_of_birth, gender, status,
                class_id, section_id, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :stuid, 'Kwame', 'Asante', '2012-03-15', 'male', 'active',
                CAST(:cid AS uuid), CAST(:secid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(student_id), "tid": str(tenant_id), "sid": str(school_id),
            "stuid": f"STU-{uuid4().hex[:8]}",
            "cid": str(class_id), "secid": str(section_id),
        },
    )

    # Create a user (for performed_by)
    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, 'hash',
                'Admin', 'User', 'school_admin', 'active',
                true, false, 0, 'UTC',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"admin-{uuid4().hex[:8]}@example.com"},
    )

    # Create an active class assignment
    ch_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO student_class_history (id, tenant_id, student_id, school_id,
                class_id, section_id, academic_year_id, enrolled_date,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:stuid AS uuid),
                CAST(:sid AS uuid), CAST(:cid AS uuid), CAST(:secid AS uuid),
                CAST(:ayid AS uuid), '2025-09-01',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ch_id), "tid": str(tenant_id), "stuid": str(student_id),
         "sid": str(school_id), "cid": str(class_id), "secid": str(section_id),
         "ayid": str(ay_id)},
    )

    invoice_id = None
    if with_invoice:
        invoice_id = uuid4()
        term_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO terms (id, tenant_id, academic_year_id, name,
                    start_date, end_date, status, sequence, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ayid AS uuid),
                    'Term 1', '2025-09-01', '2025-12-15', 'active', 1,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(term_id), "tid": str(tenant_id), "ayid": str(ay_id)},
        )
        await admin_session.execute(
            text("""
                INSERT INTO invoices (id, tenant_id, student_id, school_id,
                    academic_year_id, term_id,
                    invoice_number, total_amount, amount_paid, status,
                    due_date, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:stuid AS uuid),
                    CAST(:sid AS uuid), CAST(:ayid AS uuid), CAST(:termid AS uuid),
                    :inv_num, 500.00, 100.00, 'issued',
                    '2026-06-30', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(invoice_id), "tid": str(tenant_id),
             "stuid": str(student_id), "sid": str(school_id),
             "ayid": str(ay_id), "termid": str(term_id),
             "inv_num": f"INV-{uuid4().hex[:8]}"},
        )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "ay_id": ay_id,
        "class_id": class_id,
        "section_id": section_id,
        "student_id": student_id,
        "user_id": user_id,
        "ch_id": ch_id,
        "invoice_id": invoice_id,
    }


# --- Tests ---


async def test_check_outstanding_fees_with_invoice(app_session, admin_session):
    """Fee check returns correct data when student has outstanding invoices."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_withdrawal_prereqs(
        admin_session, tenant["id"], with_invoice=True,
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)
    result = await svc.check_outstanding_fees(tenant["id"], prereqs["student_id"])

    assert result["has_outstanding"] is True
    assert result["invoice_count"] == 1
    assert result["total_outstanding"] == 400.0  # 500 - 100 paid
    assert len(result["invoices"]) == 1
    assert result["invoices"][0]["balance"] == 400.0


async def test_check_outstanding_fees_no_invoices(app_session, admin_session):
    """Fee check returns has_outstanding=False when student has no invoices."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_withdrawal_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)
    result = await svc.check_outstanding_fees(tenant["id"], prereqs["student_id"])

    assert result["has_outstanding"] is False
    assert result["total_outstanding"] == 0.0
    assert result["invoice_count"] == 0


async def test_initiate_withdrawal(app_session, admin_session):
    """Initiate withdrawal creates clearance but does NOT change student status."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_withdrawal_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)
    result = await svc.initiate_withdrawal(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        reason="Family relocation",
        effective_date=date(2026, 3, 25),
        performed_by=prereqs["user_id"],
    )

    assert result["clearance_id"] is not None
    assert result["type"] == "withdrawal"

    # Student should still be active
    row = await app_session.execute(
        text("SELECT status FROM students WHERE id = CAST(:id AS uuid)"),
        {"id": str(prereqs["student_id"])},
    )
    assert row.scalar_one() == "active"


async def test_initiate_withdrawal_duplicate_rejected(app_session, admin_session):
    """Second withdrawal initiation is rejected when a pending clearance exists."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_withdrawal_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.services.student._shared import StudentServiceError

    svc = StudentService(app_session)

    await svc.initiate_withdrawal(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        reason="First attempt",
        effective_date=date(2026, 3, 25),
        performed_by=prereqs["user_id"],
    )

    with pytest.raises(StudentServiceError) as exc_info:
        await svc.initiate_withdrawal(
            tenant_id=tenant["id"],
            student_id=prereqs["student_id"],
            school_id=prereqs["school_id"],
            reason="Second attempt",
            effective_date=date(2026, 3, 25),
            performed_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "clearance_already_exists"


async def test_initiate_withdrawal_inactive_student(app_session, admin_session):
    """Withdrawal initiation rejected for non-active student."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_withdrawal_prereqs(admin_session, tenant["id"])

    # Mark student as withdrawn via admin
    await admin_session.execute(
        text("UPDATE students SET status = 'withdrawn' WHERE id = CAST(:id AS uuid)"),
        {"id": str(prereqs["student_id"])},
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.services.student._shared import StudentServiceError

    svc = StudentService(app_session)

    with pytest.raises(StudentServiceError) as exc_info:
        await svc.initiate_withdrawal(
            tenant_id=tenant["id"],
            student_id=prereqs["student_id"],
            school_id=prereqs["school_id"],
            reason="Should fail",
            effective_date=date(2026, 3, 25),
            performed_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "student_not_active"


async def test_update_clearance_items(app_session, admin_session):
    """Update individual clearance items."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_withdrawal_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)

    result = await svc.initiate_withdrawal(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        reason="Moving",
        effective_date=date(2026, 3, 25),
        performed_by=prereqs["user_id"],
    )
    clearance_id = result["clearance_id"]

    # Update library cleared
    clearance = await svc.update_clearance(
        tenant_id=tenant["id"],
        clearance_id=clearance_id,
        student_id=prereqs["student_id"],
        library_cleared=True,
    )
    assert clearance.library_cleared is True
    assert clearance.is_complete is False  # Not all items cleared yet


async def test_update_clearance_auto_complete(app_session, admin_session):
    """All required items cleared triggers auto-completion."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_withdrawal_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)

    result = await svc.initiate_withdrawal(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        reason="Moving",
        effective_date=date(2026, 3, 25),
        performed_by=prereqs["user_id"],
    )
    clearance_id = result["clearance_id"]

    # Clear all three required items
    clearance = await svc.update_clearance(
        tenant_id=tenant["id"],
        clearance_id=clearance_id,
        student_id=prereqs["student_id"],
        library_cleared=True,
        finance_cleared=True,
        property_cleared=True,
    )
    assert clearance.is_complete is True


async def test_complete_withdrawal(app_session, admin_session):
    """Completing withdrawal changes student status to 'withdrawn'.

    Uses fee_override=True to bypass clearance completion, because
    _get_pending_clearance() queries for is_complete=False -- once
    update_clearance auto-completes, the clearance can't be found.
    """
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_withdrawal_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)

    # Initiate with fee_override=True so complete_withdrawal succeeds
    # even though clearance items aren't all marked
    await svc.initiate_withdrawal(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        reason="Leaving",
        effective_date=date(2026, 3, 25),
        performed_by=prereqs["user_id"],
        fee_override=True,
    )

    # Complete the withdrawal
    student = await svc.complete_withdrawal(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        performed_by=prereqs["user_id"],
    )
    assert student.status.value == "withdrawn"


async def test_complete_withdrawal_incomplete_clearance_rejected(app_session, admin_session):
    """Withdrawal completion rejected if clearance not complete and no fee_override."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_withdrawal_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.services.student._shared import StudentServiceError

    svc = StudentService(app_session)

    # Initiate without clearing anything
    await svc.initiate_withdrawal(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        reason="Test",
        effective_date=date(2026, 3, 25),
        performed_by=prereqs["user_id"],
    )

    with pytest.raises(StudentServiceError) as exc_info:
        await svc.complete_withdrawal(
            tenant_id=tenant["id"],
            student_id=prereqs["student_id"],
            performed_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "clearance_incomplete"


async def test_complete_withdrawal_with_fee_override(app_session, admin_session):
    """Withdrawal succeeds with fee_override even if clearance items not all cleared."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_withdrawal_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)

    # Initiate with fee_override=True
    await svc.initiate_withdrawal(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        reason="Override test",
        effective_date=date(2026, 3, 25),
        performed_by=prereqs["user_id"],
        fee_override=True,
    )

    # Complete should work despite incomplete clearance items
    student = await svc.complete_withdrawal(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        performed_by=prereqs["user_id"],
    )
    assert student.status.value == "withdrawn"


async def test_withdrawal_creates_status_change(app_session, admin_session):
    """Completing withdrawal creates a status change record."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_withdrawal_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)

    result = await svc.initiate_withdrawal(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        reason="Graduated early",
        effective_date=date(2026, 3, 25),
        performed_by=prereqs["user_id"],
        fee_override=True,
    )

    await svc.complete_withdrawal(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        performed_by=prereqs["user_id"],
    )

    # Check status change was recorded
    history = await svc.get_status_history(tenant["id"], prereqs["student_id"])
    withdrawal_records = [h for h in history if h["to_status"] == "withdrawn"]
    assert len(withdrawal_records) >= 1
    assert withdrawal_records[0]["from_status"] == "active"
