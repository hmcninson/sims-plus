"""
Tests for the offer expiry Celery task logic.

Covers: expiring overdue offers, not expiring active/responded offers,
multi-tenant expiry. Tests call the async inner function directly
(not the Celery wrapper).

Uses admin_session to seed and verify, since the task uses its own
superuser session_maker internally. We mock get_platform_admin_session_maker
to use the test admin session.
"""

import pytest
import secrets
from datetime import date, datetime, timedelta, UTC
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    admin_session_maker,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---

async def _seed_expiry_prereqs(admin_session, tenant_id, *,
                                response_deadline,
                                offer_responded_at=None,
                                app_status="offered"):
    """Seed school, year, class, period, user, application, and decision for expiry test.
    Returns dict with app_id and decision_id."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()
    app_id = uuid4()
    decision_id = uuid4()
    user_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"S-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31', 'active', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(year_id), "tid": str(tenant_id), "name": f"AY-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"C-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO admission_periods (id, tenant_id, school_id, academic_year_id,
                name, start_date, end_date, status,
                application_fee_amount, application_fee_required,
                entrance_exam_required, target_classes, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid), :name, '2025-01-01', '2027-12-31', 'open',
                0, false, false, '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(period_id), "tid": str(tenant_id), "sid": str(school_id),
         "ayid": str(year_id), "name": f"P-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Expiry', 'Test', 'school_admin', 'active',
                true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"expiry-{uuid4().hex[:6]}@test.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
    )

    responded_sql = "NULL"
    if offer_responded_at:
        responded_sql = f"'{offer_responded_at.isoformat()}'"

    await admin_session.execute(
        text(f"""
            INSERT INTO applications (id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                offer_responded_at,
                custom_fields, fee_waived, exam_waived, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid), :tc, 'Expiry', 'Test',
                '2012-01-01', 'male', CAST(:cid AS uuid), :status,
                {responded_sql},
                '{{}}'::jsonb, false, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(app_id), "tid": str(tenant_id),
            "sid": str(school_id), "pid": str(period_id),
            "tc": secrets.token_urlsafe(48), "cid": str(class_id),
            "status": app_status,
        },
    )

    await admin_session.execute(
        text("""
            INSERT INTO admission_decisions (id, tenant_id, application_id,
                decision_type, decided_by, offered_class_id,
                decision_date, response_deadline, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                'accepted', CAST(:uid AS uuid), CAST(:cid AS uuid),
                CURRENT_DATE, :deadline, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(decision_id), "tid": str(tenant_id), "aid": str(app_id),
            "uid": str(user_id), "cid": str(class_id),
            "deadline": response_deadline,
        },
    )

    await admin_session.commit()
    return {"app_id": app_id, "decision_id": decision_id}


async def _get_app_status(admin_session, app_id):
    """Get application status via admin session (bypasses RLS)."""
    result = await admin_session.execute(
        text("SELECT status FROM applications WHERE id = CAST(:id AS uuid)"),
        {"id": str(app_id)},
    )
    return result.scalar()


# --- Tests ---


async def test_expire_overdue_offers(admin_session):
    """Offered application with past deadline -> status becomes 'expired'."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_expiry_prereqs(
        admin_session, tenant["id"],
        response_deadline=date(2025, 1, 1),  # Well in the past
    )

    from app.tasks.offer_expiry import _expire_offers_for_tenant

    # Set tenant context for the task function
    await admin_session.execute(
        text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
        {"tid": str(tenant["id"])},
    )

    count = await _expire_offers_for_tenant(admin_session, str(tenant["id"]))
    await admin_session.flush()

    assert count == 1

    status = await _get_app_status(admin_session, prereqs["app_id"])
    assert status == "expired"


async def test_not_expire_active_offers(admin_session):
    """Deadline in the future -> status remains 'offered'."""
    tenant = await create_test_tenant(admin_session)
    future_deadline = date.today() + timedelta(days=30)
    prereqs = await _seed_expiry_prereqs(
        admin_session, tenant["id"],
        response_deadline=future_deadline,
    )

    from app.tasks.offer_expiry import _expire_offers_for_tenant

    await admin_session.execute(
        text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
        {"tid": str(tenant["id"])},
    )

    count = await _expire_offers_for_tenant(admin_session, str(tenant["id"]))
    assert count == 0

    status = await _get_app_status(admin_session, prereqs["app_id"])
    assert status == "offered"


async def test_not_expire_responded_offers(admin_session):
    """Offer already responded to (offer_responded_at set) -> not expired even if past deadline."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_expiry_prereqs(
        admin_session, tenant["id"],
        response_deadline=date(2025, 1, 1),  # Past deadline
        offer_responded_at=datetime(2025, 1, 1, tzinfo=UTC),  # But responded
    )

    from app.tasks.offer_expiry import _expire_offers_for_tenant

    await admin_session.execute(
        text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
        {"tid": str(tenant["id"])},
    )

    count = await _expire_offers_for_tenant(admin_session, str(tenant["id"]))
    assert count == 0

    status = await _get_app_status(admin_session, prereqs["app_id"])
    assert status == "offered"  # Unchanged


async def test_expire_multiple_tenants(admin_session):
    """Creates expired offers in two tenants -> both correctly expired."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)

    prereqs_a = await _seed_expiry_prereqs(
        admin_session, tenant_a["id"],
        response_deadline=date(2025, 1, 1),
    )
    prereqs_b = await _seed_expiry_prereqs(
        admin_session, tenant_b["id"],
        response_deadline=date(2025, 6, 1),
    )

    from app.tasks.offer_expiry import _expire_offers_for_tenant

    # Process Tenant A
    await admin_session.execute(
        text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
        {"tid": str(tenant_a["id"])},
    )
    count_a = await _expire_offers_for_tenant(admin_session, str(tenant_a["id"]))
    await admin_session.flush()
    await admin_session.execute(text("SELECT clear_tenant_context()"))

    # Process Tenant B
    await admin_session.execute(
        text("SELECT set_tenant_context(CAST(:tid AS uuid))"),
        {"tid": str(tenant_b["id"])},
    )
    count_b = await _expire_offers_for_tenant(admin_session, str(tenant_b["id"]))
    await admin_session.flush()
    await admin_session.execute(text("SELECT clear_tenant_context()"))

    assert count_a == 1
    assert count_b == 1

    status_a = await _get_app_status(admin_session, prereqs_a["app_id"])
    status_b = await _get_app_status(admin_session, prereqs_b["app_id"])
    assert status_a == "expired"
    assert status_b == "expired"
