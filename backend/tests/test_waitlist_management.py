"""
Tests for waitlist management (DecisionService).

Covers: list_waitlisted, reorder_waitlist, promote_from_waitlist,
waitlist rank updates, advisory lock concurrency, tenant isolation.
Uses two-engine pattern.
"""

import pytest
import secrets
from datetime import date
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---

async def _seed_waitlist_prereqs(admin_session, tenant_id, *, num_waitlisted=3):
    """Seed school, year, class, period, user, and N waitlisted applications+decisions.
    Returns dict with IDs and list of (app_id, decision_id) tuples."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()
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
                'Waitlist', 'Manager', 'school_admin', 'active',
                true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"wl-{uuid4().hex[:6]}@test.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
    )

    entries = []
    for i in range(num_waitlisted):
        app_id = uuid4()
        decision_id = uuid4()

        await admin_session.execute(
            text("""
                INSERT INTO applications (id, tenant_id, school_id, admission_period_id,
                    tracking_code, applicant_first_name, applicant_last_name,
                    date_of_birth, gender, target_class_id, status,
                    custom_fields, fee_waived, exam_waived, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:pid AS uuid), :tc, :fn, 'WaitlistTest',
                    '2012-01-01', 'male', CAST(:cid AS uuid), 'waitlisted',
                    '{}', false, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(app_id), "tid": str(tenant_id),
                "sid": str(school_id), "pid": str(period_id),
                "tc": secrets.token_urlsafe(48), "cid": str(class_id),
                "fn": f"WL-Applicant-{i}",
            },
        )
        await admin_session.execute(
            text("""
                INSERT INTO admission_decisions (id, tenant_id, application_id,
                    decision_type, decided_by,
                    decision_date, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                    'waitlisted', CAST(:uid AS uuid),
                    CURRENT_DATE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(decision_id), "tid": str(tenant_id),
                "aid": str(app_id), "uid": str(user_id),
            },
        )
        entries.append({"app_id": app_id, "decision_id": decision_id})

    await admin_session.commit()
    return {
        "school_id": school_id, "period_id": period_id,
        "class_id": class_id, "user_id": user_id,
        "entries": entries,
    }


# --- List Waitlist Tests ---


async def test_list_waitlisted(app_session, admin_session):
    """List waitlisted decisions returns all waitlisted entries."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_waitlist_prereqs(admin_session, tenant["id"], num_waitlisted=3)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    items, total = await svc.list_waitlisted(
        tenant["id"], prereqs["school_id"],
    )
    assert total == 3
    assert len(items) == 3


async def test_list_waitlisted_filter_period(app_session, admin_session):
    """List waitlisted with period_id filter returns only that period's entries."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_waitlist_prereqs(admin_session, tenant["id"], num_waitlisted=2)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    items, total = await svc.list_waitlisted(
        tenant["id"], prereqs["school_id"],
        period_id=prereqs["period_id"],
    )
    assert total == 2

    # With a random period_id -> 0 results
    items2, total2 = await svc.list_waitlisted(
        tenant["id"], prereqs["school_id"],
        period_id=uuid4(),  # Nonexistent period
    )
    assert total2 == 0


# --- Reorder Waitlist Tests ---


async def test_reorder_waitlist(app_session, admin_session):
    """Reorder waitlist assigns sequential ranks in the specified order."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_waitlist_prereqs(admin_session, tenant["id"], num_waitlisted=3)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)

    # Reorder: put last one first
    ordered_ids = [
        prereqs["entries"][2]["decision_id"],
        prereqs["entries"][0]["decision_id"],
        prereqs["entries"][1]["decision_id"],
    ]
    updated = await svc.reorder_waitlist(
        tenant["id"], prereqs["school_id"],
        period_id=prereqs["period_id"],
        ordered_decision_ids=ordered_ids,
    )
    assert len(updated) == 3

    # Verify ranks match order
    rank_map = {d.id: d.waitlist_rank for d in updated}
    assert rank_map[prereqs["entries"][2]["decision_id"]] == 1
    assert rank_map[prereqs["entries"][0]["decision_id"]] == 2
    assert rank_map[prereqs["entries"][1]["decision_id"]] == 3


async def test_reorder_missing_ids(app_session, admin_session):
    """Reorder with IDs not all waitlisted -> NOT_FOUND."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_waitlist_prereqs(admin_session, tenant["id"], num_waitlisted=1)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService, DecisionServiceError

    svc = DecisionService(app_session)
    with pytest.raises(DecisionServiceError) as exc_info:
        await svc.reorder_waitlist(
            tenant["id"], prereqs["school_id"],
            period_id=prereqs["period_id"],
            ordered_decision_ids=[
                prereqs["entries"][0]["decision_id"],
                uuid4(),  # Nonexistent
            ],
        )
    assert exc_info.value.code == "NOT_FOUND"


async def test_reorder_concurrency(app_session, admin_session):
    """Reorder uses pg_advisory_xact_lock -- at minimum it does not error out."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_waitlist_prereqs(admin_session, tenant["id"], num_waitlisted=2)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    ordered_ids = [e["decision_id"] for e in prereqs["entries"]]

    # Call reorder twice in sequence -- both should succeed without deadlock
    await svc.reorder_waitlist(
        tenant["id"], prereqs["school_id"],
        period_id=prereqs["period_id"],
        ordered_decision_ids=ordered_ids,
    )
    # Reverse order
    await svc.reorder_waitlist(
        tenant["id"], prereqs["school_id"],
        period_id=prereqs["period_id"],
        ordered_decision_ids=list(reversed(ordered_ids)),
    )

    # Verify final ranks
    items, _ = await svc.list_waitlisted(
        tenant["id"], prereqs["school_id"],
        period_id=prereqs["period_id"],
    )
    ranks = [item["waitlist_rank"] for item in items]
    assert sorted(ranks) == [1, 2]


# --- Promote from Waitlist Tests ---


async def test_promote_from_waitlist(app_session, admin_session):
    """Promote waitlisted -> decision_type becomes 'accepted', app status 'offered'."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_waitlist_prereqs(admin_session, tenant["id"], num_waitlisted=1)
    entry = prereqs["entries"][0]
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    decision = await svc.promote_from_waitlist(
        tenant["id"], entry["decision_id"],
        offered_class_id=prereqs["class_id"],
        response_deadline=date(2026, 9, 1),
        promoted_by=prereqs["user_id"],
    )
    assert decision.decision_type == "accepted"
    assert decision.offered_class_id == prereqs["class_id"]

    # Verify application status
    result = await app_session.execute(
        text("SELECT status FROM applications WHERE id = CAST(:id AS uuid)"),
        {"id": str(entry["app_id"])},
    )
    assert result.scalar() == "offered"


async def test_promote_clears_rank(app_session, admin_session):
    """After promotion, waitlist_rank and waitlist_notes are cleared."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_waitlist_prereqs(admin_session, tenant["id"], num_waitlisted=1)
    entry = prereqs["entries"][0]

    # First set a rank and notes
    await admin_session.execute(
        text("""
            UPDATE admission_decisions
            SET waitlist_rank = 1, waitlist_notes = 'Priority candidate'
            WHERE id = CAST(:id AS uuid)
        """),
        {"id": str(entry["decision_id"])},
    )
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    decision = await svc.promote_from_waitlist(
        tenant["id"], entry["decision_id"],
        offered_class_id=prereqs["class_id"],
        promoted_by=prereqs["user_id"],
    )
    assert decision.waitlist_rank is None
    assert decision.waitlist_notes is None


async def test_promote_non_waitlisted(app_session, admin_session):
    """Promoting an accepted (non-waitlisted) decision -> INVALID_DECISION_TYPE."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_waitlist_prereqs(admin_session, tenant["id"], num_waitlisted=1)
    entry = prereqs["entries"][0]

    # Change decision type to 'accepted' (not waitlisted)
    await admin_session.execute(
        text("""
            UPDATE admission_decisions SET decision_type = 'accepted'
            WHERE id = CAST(:id AS uuid)
        """),
        {"id": str(entry["decision_id"])},
    )
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService, DecisionServiceError

    svc = DecisionService(app_session)
    with pytest.raises(DecisionServiceError) as exc_info:
        await svc.promote_from_waitlist(
            tenant["id"], entry["decision_id"],
            offered_class_id=prereqs["class_id"],
            promoted_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "INVALID_DECISION_TYPE"


async def test_promote_sets_deadline(app_session, admin_session):
    """Promoted decision has response_deadline set."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_waitlist_prereqs(admin_session, tenant["id"], num_waitlisted=1)
    entry = prereqs["entries"][0]
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    deadline = date(2026, 10, 15)
    decision = await svc.promote_from_waitlist(
        tenant["id"], entry["decision_id"],
        offered_class_id=prereqs["class_id"],
        response_deadline=deadline,
        promoted_by=prereqs["user_id"],
    )
    assert decision.response_deadline == deadline


async def test_waitlist_tenant_isolation(app_session, admin_session):
    """Tenant A's waitlisted decisions are invisible to Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    prereqs = await _seed_waitlist_prereqs(admin_session, tenant_a["id"], num_waitlisted=2)

    # Create a school for tenant B so list_waitlisted has valid params
    school_b = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_b), "tid": str(tenant_b["id"]),
         "name": f"S-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
    )
    await admin_session.commit()

    # Switch to Tenant B
    await set_app_tenant_context(app_session, tenant_b["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    items, total = await svc.list_waitlisted(tenant_b["id"], school_b)
    assert total == 0, "Tenant B must NOT see Tenant A's waitlisted decisions"
