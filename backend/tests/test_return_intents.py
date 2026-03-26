"""
Tests for ReturnIntentService.

Covers: campaign creation, send, respond, stats,
invalid transitions, tenant isolation. Uses two-engine pattern.
"""

import pytest
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---

async def _seed_return_intent_prereqs(admin_session, tenant_id, *, num_students=3):
    """Seed school, academic year, class, students, guardians, and user.
    Returns dict with all IDs."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    user_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"S-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2026-09-01', '2027-07-31', 'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Parent', 'User', 'parent', 'active',
                true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"parent-{uuid4().hex[:6]}@test.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
    )

    # Create students in the class
    student_ids = []
    for i in range(num_students):
        sid = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO students (id, tenant_id, school_id, student_id,
                    first_name, last_name, date_of_birth, gender, status,
                    class_id, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:scid AS uuid),
                    :student_id, :fn, :ln, '2014-03-15', 'female', 'active',
                    CAST(:cid AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": str(sid), "tid": str(tenant_id), "scid": str(school_id),
                "student_id": f"STU-{uuid4().hex[:8]}",
                "fn": f"Student-{i}", "ln": "Return",
                "cid": str(class_id),
            },
        )
        student_ids.append(sid)

    await admin_session.commit()
    return {
        "school_id": school_id,
        "year_id": year_id,
        "class_id": class_id,
        "user_id": user_id,
        "student_ids": student_ids,
    }


# --- Tests ---


async def test_create_campaign(app_session, admin_session):
    """Create return intent campaign -> draft status."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_return_intent_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ReturnIntentService

    svc = ReturnIntentService(app_session)
    campaign = await svc.create_campaign(
        tenant["id"], prereqs["school_id"],
        academic_year_id=prereqs["year_id"],
        name="2026/2027 Return Survey",
        target_classes=[str(prereqs["class_id"])],
    )
    assert campaign.status == "draft"
    assert campaign.name == "2026/2027 Return Survey"


async def test_create_campaign_no_classes(app_session, admin_session):
    """Empty target_classes -> NO_TARGET_CLASSES error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_return_intent_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ReturnIntentService, ReturnIntentError

    svc = ReturnIntentService(app_session)
    with pytest.raises(ReturnIntentError) as exc_info:
        await svc.create_campaign(
            tenant["id"], prereqs["school_id"],
            academic_year_id=prereqs["year_id"],
            name="Bad Campaign",
            target_classes=[],
        )
    assert exc_info.value.code == "NO_TARGET_CLASSES"


async def test_send_campaign(app_session, admin_session):
    """Send campaign -> creates intent records for students, status becomes sent."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_return_intent_prereqs(admin_session, tenant["id"], num_students=3)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ReturnIntentService

    svc = ReturnIntentService(app_session)
    campaign = await svc.create_campaign(
        tenant["id"], prereqs["school_id"],
        academic_year_id=prereqs["year_id"],
        name="Send Test",
        target_classes=[str(prereqs["class_id"])],
    )

    count = await svc.send_campaign(tenant["id"], campaign.id)
    assert count == 3  # 3 students

    # Verify campaign status
    updated = await svc.get_campaign(tenant["id"], campaign.id)
    assert updated.status == "sent"


async def test_send_campaign_twice_rejected(app_session, admin_session):
    """Sending already-sent campaign -> CAMPAIGN_ALREADY_SENT error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_return_intent_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ReturnIntentService, ReturnIntentError

    svc = ReturnIntentService(app_session)
    campaign = await svc.create_campaign(
        tenant["id"], prereqs["school_id"],
        academic_year_id=prereqs["year_id"],
        name="Double Send",
        target_classes=[str(prereqs["class_id"])],
    )
    await svc.send_campaign(tenant["id"], campaign.id)

    with pytest.raises(ReturnIntentError) as exc_info:
        await svc.send_campaign(tenant["id"], campaign.id)
    assert exc_info.value.code == "CAMPAIGN_ALREADY_SENT"


async def test_respond_to_intent(app_session, admin_session):
    """Parent responds to return intent survey."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_return_intent_prereqs(admin_session, tenant["id"], num_students=1)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ReturnIntentService

    svc = ReturnIntentService(app_session)
    campaign = await svc.create_campaign(
        tenant["id"], prereqs["school_id"],
        academic_year_id=prereqs["year_id"],
        name="Respond Test",
        target_classes=[str(prereqs["class_id"])],
    )
    await svc.send_campaign(tenant["id"], campaign.id)

    # Get the intent record
    intents, _ = await svc.list_intents(tenant["id"], campaign.id)
    assert len(intents) == 1
    intent_id = intents[0].id

    # Respond
    updated = await svc.respond(
        tenant["id"], intent_id,
        intent="returning",
        responded_by=prereqs["user_id"],
    )
    assert updated.intent == "returning"
    assert updated.responded_at is not None


async def test_respond_invalid_intent(app_session, admin_session):
    """Invalid intent value -> INVALID_INTENT error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_return_intent_prereqs(admin_session, tenant["id"], num_students=1)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ReturnIntentService, ReturnIntentError

    svc = ReturnIntentService(app_session)
    campaign = await svc.create_campaign(
        tenant["id"], prereqs["school_id"],
        academic_year_id=prereqs["year_id"],
        name="Invalid Intent Test",
        target_classes=[str(prereqs["class_id"])],
    )
    await svc.send_campaign(tenant["id"], campaign.id)

    intents, _ = await svc.list_intents(tenant["id"], campaign.id)
    intent_id = intents[0].id

    with pytest.raises(ReturnIntentError) as exc_info:
        await svc.respond(
            tenant["id"], intent_id,
            intent="maybe",
            responded_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "INVALID_INTENT"


async def test_campaign_stats(app_session, admin_session):
    """Campaign stats reflect response counts accurately."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_return_intent_prereqs(admin_session, tenant["id"], num_students=3)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ReturnIntentService

    svc = ReturnIntentService(app_session)
    campaign = await svc.create_campaign(
        tenant["id"], prereqs["school_id"],
        academic_year_id=prereqs["year_id"],
        name="Stats Test",
        target_classes=[str(prereqs["class_id"])],
    )
    await svc.send_campaign(tenant["id"], campaign.id)

    intents, _ = await svc.list_intents(tenant["id"], campaign.id)
    assert len(intents) == 3

    # Respond to 2 of 3
    await svc.respond(
        tenant["id"], intents[0].id,
        intent="returning", responded_by=prereqs["user_id"],
    )
    await svc.respond(
        tenant["id"], intents[1].id,
        intent="not_returning", responded_by=prereqs["user_id"],
        reason="Relocating",
    )

    stats = await svc.get_campaign_stats(tenant["id"], campaign.id)
    assert stats["total"] == 3
    assert stats["returning"] == 1
    assert stats["not_returning"] == 1
    assert stats["pending"] == 1


async def test_campaign_tenant_isolation(app_session, admin_session):
    """Campaign from Tenant A is invisible to Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    prereqs = await _seed_return_intent_prereqs(admin_session, tenant_a["id"])
    await set_app_tenant_context(app_session, tenant_a["id"])

    from app.services.admissions import ReturnIntentService

    svc = ReturnIntentService(app_session)
    await svc.create_campaign(
        tenant_a["id"], prereqs["school_id"],
        academic_year_id=prereqs["year_id"],
        name="Isolation Test",
        target_classes=[str(prereqs["class_id"])],
    )

    # Switch to Tenant B
    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(text("SELECT count(*) FROM return_intent_campaigns"))
    assert result.scalar() == 0, "Tenant B must NOT see Tenant A's campaigns"
