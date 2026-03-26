"""
Tests for ReturnIntentService.confirm_re_enrollment and get_re_enrollment_summary.

Covers: confirm returning intent, double-confirm error, wrong intent error,
and re-enrollment summary counts.
Uses two-engine pattern (admin for seed, app for RLS-scoped service calls).
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


async def _seed_full_prereqs(admin_session, tenant_id):
    """Seed school, academic year, class, campaign, students, and intents.

    Returns dict with all IDs needed.
    """
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    campaign_id = uuid4()

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
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO academic_years (
                id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31',
                'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(year_id), "tid": str(tenant_id), "name": f"AY-{uuid4().hex[:6]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO classes (
                id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"C-{uuid4().hex[:6]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO return_intent_campaigns (
                id, tenant_id, school_id, academic_year_id,
                name, target_classes, status, sent_count,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid),
                :name, '[]', 'sent', 0,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(campaign_id), "tid": str(tenant_id),
            "sid": str(school_id), "ayid": str(year_id),
            "name": f"Campaign-{uuid4().hex[:6]}",
        },
    )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "year_id": year_id,
        "class_id": class_id,
        "campaign_id": campaign_id,
    }


async def _seed_student(admin_session, tenant_id, school_id, class_id):
    """Seed an active student. Returns student_id."""
    student_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO students (
                id, tenant_id, school_id, class_id,
                student_id, first_name, last_name, gender,
                date_of_birth, status, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:sid AS uuid), CAST(:cid AS uuid),
                :stuid, :fn, :ln, 'male',
                '2015-01-01', 'active',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(student_id), "tid": str(tenant_id),
            "sid": str(school_id), "cid": str(class_id),
            "stuid": f"STU-{uuid4().hex[:8]}",
            "fn": f"F-{uuid4().hex[:4]}", "ln": f"L-{uuid4().hex[:4]}",
        },
    )
    return student_id


async def _seed_intent(admin_session, tenant_id, school_id, campaign_id, year_id, student_id,
                        *, intent="returning"):
    """Seed a return intent. Returns intent_id."""
    intent_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO return_intents (
                id, tenant_id, school_id, campaign_id,
                student_id, academic_year_id,
                intent, re_enrollment_confirmed, outstanding_fees_checked,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:cid AS uuid), CAST(:stid AS uuid), CAST(:ayid AS uuid),
                :intent, false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(intent_id), "tid": str(tenant_id),
            "sid": str(school_id), "cid": str(campaign_id),
            "stid": str(student_id), "ayid": str(year_id),
            "intent": intent,
        },
    )
    return intent_id


# --- Tests ---


class TestConfirmReEnrollment:
    """Confirm re-enrollment for returning students."""

    async def test_confirm_re_enrollment(self, admin_session, app_session):
        """Confirm returning intent -> confirmed=true, timestamp set."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        ids = await _seed_full_prereqs(admin_session, tenant["id"])

        stu = await _seed_student(
            admin_session, tenant["id"], ids["school_id"], ids["class_id"],
        )
        intent_id = await _seed_intent(
            admin_session, tenant["id"], ids["school_id"],
            ids["campaign_id"], ids["year_id"], stu,
            intent="returning",
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.return_intent_service import ReturnIntentService

        svc = ReturnIntentService(app_session)
        confirmed = await svc.confirm_re_enrollment(
            tenant["id"], intent_id, user_id=user["id"],
        )

        assert confirmed.re_enrollment_confirmed is True
        assert confirmed.re_enrollment_confirmed_at is not None
        assert confirmed.outstanding_fees_checked is True

    async def test_confirm_already_confirmed(self, admin_session, app_session):
        """Double confirm -> error."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        ids = await _seed_full_prereqs(admin_session, tenant["id"])

        stu = await _seed_student(
            admin_session, tenant["id"], ids["school_id"], ids["class_id"],
        )
        intent_id = await _seed_intent(
            admin_session, tenant["id"], ids["school_id"],
            ids["campaign_id"], ids["year_id"], stu,
            intent="returning",
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.return_intent_service import (
            ReturnIntentService, ReturnIntentError,
        )

        svc = ReturnIntentService(app_session)
        await svc.confirm_re_enrollment(tenant["id"], intent_id, user_id=user["id"])

        with pytest.raises(ReturnIntentError) as exc_info:
            await svc.confirm_re_enrollment(tenant["id"], intent_id, user_id=user["id"])
        assert exc_info.value.code == "ALREADY_CONFIRMED"

    async def test_confirm_wrong_intent(self, admin_session, app_session):
        """Not_returning intent -> error."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        ids = await _seed_full_prereqs(admin_session, tenant["id"])

        stu = await _seed_student(
            admin_session, tenant["id"], ids["school_id"], ids["class_id"],
        )
        intent_id = await _seed_intent(
            admin_session, tenant["id"], ids["school_id"],
            ids["campaign_id"], ids["year_id"], stu,
            intent="not_returning",
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.return_intent_service import (
            ReturnIntentService, ReturnIntentError,
        )

        svc = ReturnIntentService(app_session)
        with pytest.raises(ReturnIntentError) as exc_info:
            await svc.confirm_re_enrollment(tenant["id"], intent_id, user_id=user["id"])
        assert exc_info.value.code == "INVALID_INTENT_STATE"


class TestReEnrollmentSummary:
    """Re-enrollment summary for a campaign."""

    async def test_re_enrollment_summary(self, admin_session, app_session):
        """GET summary -> correct counts per status."""
        tenant = await create_test_tenant(admin_session)
        user = await create_test_user(admin_session, tenant["id"])
        ids = await _seed_full_prereqs(admin_session, tenant["id"])

        # 3 returning (1 will be confirmed), 2 not_returning, 1 undecided
        returning_ids = []
        for _ in range(3):
            stu = await _seed_student(
                admin_session, tenant["id"], ids["school_id"], ids["class_id"],
            )
            iid = await _seed_intent(
                admin_session, tenant["id"], ids["school_id"],
                ids["campaign_id"], ids["year_id"], stu,
                intent="returning",
            )
            returning_ids.append(iid)

        for _ in range(2):
            stu = await _seed_student(
                admin_session, tenant["id"], ids["school_id"], ids["class_id"],
            )
            await _seed_intent(
                admin_session, tenant["id"], ids["school_id"],
                ids["campaign_id"], ids["year_id"], stu,
                intent="not_returning",
            )

        stu_u = await _seed_student(
            admin_session, tenant["id"], ids["school_id"], ids["class_id"],
        )
        await _seed_intent(
            admin_session, tenant["id"], ids["school_id"],
            ids["campaign_id"], ids["year_id"], stu_u,
            intent="undecided",
        )

        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.return_intent_service import ReturnIntentService

        svc = ReturnIntentService(app_session)

        # Confirm one returning intent
        await svc.confirm_re_enrollment(
            tenant["id"], returning_ids[0], user_id=user["id"],
        )

        summary = await svc.get_re_enrollment_summary(
            tenant["id"], ids["school_id"], ids["campaign_id"],
        )

        assert summary["total_intents"] == 6
        assert summary["confirmed_count"] == 1
        assert summary["pending_count"] == 2  # returning but not confirmed
        assert summary["not_returning_count"] == 2
        assert summary["undecided_count"] == 1
