"""
Tests for AdmissionsAnalyticsService -- funnel, trends, lead sources,
attrition, and re-enrollment rates.

Covers: empty data graceful fallback, funnel stage counts, conversion rates,
lead source effectiveness, attrition analysis, re-enrollment rates,
academic year filtering, and tenant isolation.
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
    clear_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_prereqs(admin_session, tenant_id):
    """Seed school, academic year, class, admission period. Returns dict of IDs."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()

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
            INSERT INTO admission_periods (
                id, tenant_id, school_id, academic_year_id,
                name, start_date, end_date, status,
                application_fee_amount, application_fee_required,
                entrance_exam_required, target_classes,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid),
                :name, '2025-01-01', '2027-12-31', 'open',
                0, false, false, '[]',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(period_id), "tid": str(tenant_id), "sid": str(school_id),
            "ayid": str(year_id), "name": f"P-{uuid4().hex[:6]}",
        },
    )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "year_id": year_id,
        "class_id": class_id,
        "period_id": period_id,
    }


async def _seed_application(admin_session, tenant_id, school_id, period_id, class_id, status):
    """Seed an application with a given status. Returns application_id."""
    app_id = uuid4()
    tracking = f"APP-{uuid4().hex[:8]}"
    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                status, target_class_id,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tc, :fn, :ln, :status, CAST(:cid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant_id),
            "sid": str(school_id), "pid": str(period_id),
            "tc": tracking,
            "fn": f"Applicant-{uuid4().hex[:6]}", "ln": f"Last-{uuid4().hex[:4]}",
            "status": status, "cid": str(class_id),
        },
    )
    return app_id


async def _seed_inquiry(admin_session, tenant_id, school_id, *, source="website", status="new"):
    """Seed an inquiry row. Returns inquiry_id."""
    inquiry_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO inquiries (
                id, tenant_id, school_id, source, status,
                first_name, last_name, guardian_name, guardian_phone,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :source, :status,
                :fn, :ln, :gn, :gp,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(inquiry_id), "tid": str(tenant_id),
            "sid": str(school_id), "source": source, "status": status,
            "fn": f"Inq-{uuid4().hex[:4]}", "ln": f"Last-{uuid4().hex[:4]}",
            "gn": f"Guardian-{uuid4().hex[:4]}", "gp": f"024{uuid4().hex[:7]}",
        },
    )
    return inquiry_id


async def _seed_return_intent_campaign(admin_session, tenant_id, school_id, year_id):
    """Seed a return intent campaign. Returns campaign_id."""
    campaign_id = uuid4()
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
    return campaign_id


async def _seed_return_intent(
    admin_session, tenant_id, school_id, campaign_id, year_id, student_id,
    *, intent="returning", reason=None,
):
    """Seed a return intent. Returns intent_id."""
    intent_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO return_intents (
                id, tenant_id, school_id, campaign_id,
                student_id, academic_year_id,
                intent, reason,
                re_enrollment_confirmed, outstanding_fees_checked,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:cid AS uuid), CAST(:stid AS uuid), CAST(:ayid AS uuid),
                :intent, :reason,
                false, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(intent_id), "tid": str(tenant_id),
            "sid": str(school_id), "cid": str(campaign_id),
            "stid": str(student_id), "ayid": str(year_id),
            "intent": intent, "reason": reason,
        },
    )
    return intent_id


async def _seed_student(admin_session, tenant_id, school_id, class_id, *, status="active"):
    """Seed a student. Returns student_id."""
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
                '2015-01-01', :status,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(student_id), "tid": str(tenant_id),
            "sid": str(school_id), "cid": str(class_id),
            "stuid": f"STU-{uuid4().hex[:8]}", "fn": f"F-{uuid4().hex[:4]}",
            "ln": f"L-{uuid4().hex[:4]}", "status": status,
        },
    )
    return student_id


# --- Tests ---


class TestFunnel:
    """Admissions funnel: inquiry -> application -> offered -> accepted -> enrolled."""

    async def test_funnel_empty(self, admin_session, app_session):
        """No data -> all zeros."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_prereqs(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.analytics_service import AdmissionsAnalyticsService

        svc = AdmissionsAnalyticsService(app_session)
        result = await svc.get_full_funnel(
            tenant["id"], ids["school_id"],
        )

        # All stage counts should be 0
        for stage in result["stages"]:
            assert stage["count"] == 0

    async def test_funnel_with_data(self, admin_session, app_session):
        """Create data at each stage -> correct counts."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_prereqs(admin_session, tenant["id"])

        # Seed inquiries
        await _seed_inquiry(admin_session, tenant["id"], ids["school_id"])
        await _seed_inquiry(admin_session, tenant["id"], ids["school_id"])
        await _seed_inquiry(admin_session, tenant["id"], ids["school_id"])

        # Seed applications at various stages
        await _seed_application(
            admin_session, tenant["id"], ids["school_id"],
            ids["period_id"], ids["class_id"], "submitted",
        )
        await _seed_application(
            admin_session, tenant["id"], ids["school_id"],
            ids["period_id"], ids["class_id"], "offered",
        )
        await _seed_application(
            admin_session, tenant["id"], ids["school_id"],
            ids["period_id"], ids["class_id"], "accepted",
        )
        await _seed_application(
            admin_session, tenant["id"], ids["school_id"],
            ids["period_id"], ids["class_id"], "enrolled",
        )

        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.analytics_service import AdmissionsAnalyticsService

        svc = AdmissionsAnalyticsService(app_session)
        result = await svc.get_full_funnel(
            tenant["id"], ids["school_id"],
        )

        stages = {s["stage"]: s["count"] for s in result["stages"]}
        assert stages["inquiry"] == 3
        assert stages["application"] == 4  # all 4 applications
        # offered includes offered + accepted + enrolled
        assert stages["offered"] == 3
        # accepted includes accepted + enrolled
        assert stages["accepted"] == 2
        assert stages["enrolled"] == 1

    async def test_funnel_conversion_rates(self, admin_session, app_session):
        """Conversion rates calculated correctly."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_prereqs(admin_session, tenant["id"])

        # 10 inquiries
        for _ in range(10):
            await _seed_inquiry(admin_session, tenant["id"], ids["school_id"])

        # 5 applications, 2 offered, 1 accepted, 1 enrolled
        for _ in range(2):
            await _seed_application(
                admin_session, tenant["id"], ids["school_id"],
                ids["period_id"], ids["class_id"], "submitted",
            )
        await _seed_application(
            admin_session, tenant["id"], ids["school_id"],
            ids["period_id"], ids["class_id"], "offered",
        )
        await _seed_application(
            admin_session, tenant["id"], ids["school_id"],
            ids["period_id"], ids["class_id"], "accepted",
        )
        await _seed_application(
            admin_session, tenant["id"], ids["school_id"],
            ids["period_id"], ids["class_id"], "enrolled",
        )

        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.analytics_service import AdmissionsAnalyticsService

        svc = AdmissionsAnalyticsService(app_session)
        result = await svc.get_full_funnel(
            tenant["id"], ids["school_id"],
        )

        stages = {s["stage"]: s for s in result["stages"]}

        # application rate = 5 apps / 10 inquiries = 50%
        assert stages["application"]["conversion_rate"] == 50.0
        # offered = 3 (offered+accepted+enrolled) / 5 apps = 60%
        assert stages["offered"]["conversion_rate"] == 60.0


class TestEnrollmentTrends:
    """Year-over-year enrollment counts."""

    async def test_enrollment_trends(self, admin_session, app_session):
        """Multi-year data -> correct per-year counts."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_prereqs(admin_session, tenant["id"])

        # Seed some enrolled applications for this year
        await _seed_application(
            admin_session, tenant["id"], ids["school_id"],
            ids["period_id"], ids["class_id"], "enrolled",
        )
        await _seed_application(
            admin_session, tenant["id"], ids["school_id"],
            ids["period_id"], ids["class_id"], "enrolled",
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.analytics_service import AdmissionsAnalyticsService

        svc = AdmissionsAnalyticsService(app_session)
        result = await svc.get_enrollment_trends(
            tenant["id"], ids["school_id"], year_count=3,
        )

        assert len(result["years"]) >= 1
        # The year with our period should have enrolled counts
        year_data = result["years"][0]
        assert year_data["total_enrolled"] == 2


class TestLeadSource:
    """Lead source effectiveness analytics."""

    async def test_lead_source_effectiveness(self, admin_session, app_session):
        """Inquiries by source -> conversion rates."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_prereqs(admin_session, tenant["id"])

        # Seed inquiries from different sources
        for _ in range(5):
            await _seed_inquiry(
                admin_session, tenant["id"], ids["school_id"],
                source="website", status="new",
            )
        for _ in range(3):
            await _seed_inquiry(
                admin_session, tenant["id"], ids["school_id"],
                source="referral", status="applied",
            )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.analytics_service import AdmissionsAnalyticsService

        svc = AdmissionsAnalyticsService(app_session)
        result = await svc.get_lead_source_effectiveness(
            tenant["id"], ids["school_id"],
        )

        sources = {s["source"]: s for s in result["sources"]}
        assert "website" in sources
        assert sources["website"]["inquiry_count"] == 5
        assert "referral" in sources
        assert sources["referral"]["inquiry_count"] == 3
        # Referral inquiries are "applied" -> application_count should be 3
        assert sources["referral"]["application_count"] == 3

    async def test_lead_source_no_inquiries(self, admin_session, app_session):
        """No inquiries -> graceful empty list."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_prereqs(admin_session, tenant["id"])

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.analytics_service import AdmissionsAnalyticsService

        svc = AdmissionsAnalyticsService(app_session)
        result = await svc.get_lead_source_effectiveness(
            tenant["id"], ids["school_id"],
        )

        assert result["sources"] == []


class TestAttrition:
    """Attrition analysis: withdrawn + not_returning."""

    async def test_attrition_analysis(self, admin_session, app_session):
        """Return intents -> correct returning/withdrawn counts."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_prereqs(admin_session, tenant["id"])

        # Seed withdrawn students
        for _ in range(2):
            await _seed_student(
                admin_session, tenant["id"], ids["school_id"],
                ids["class_id"], status="withdrawn",
            )

        # Seed not_returning intents
        campaign_id = await _seed_return_intent_campaign(
            admin_session, tenant["id"], ids["school_id"], ids["year_id"],
        )
        for i in range(3):
            stu_id = await _seed_student(
                admin_session, tenant["id"], ids["school_id"], ids["class_id"],
            )
            reason = "relocation" if i < 2 else "fees"
            await _seed_return_intent(
                admin_session, tenant["id"], ids["school_id"],
                campaign_id, ids["year_id"], stu_id,
                intent="not_returning", reason=reason,
            )

        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.analytics_service import AdmissionsAnalyticsService

        svc = AdmissionsAnalyticsService(app_session)
        result = await svc.get_attrition_analysis(
            tenant["id"], ids["school_id"],
            academic_year_id=ids["year_id"],
        )

        assert result["withdrawn_count"] == 2
        assert result["not_returning_count"] == 3
        assert result["total_attrition"] == 5
        # Reasons grouped
        reasons = {r["reason"]: r["count"] for r in result["not_returning_reasons"]}
        assert reasons["relocation"] == 2
        assert reasons["fees"] == 1


class TestReEnrollmentRates:
    """Re-enrollment rates over academic years."""

    async def test_re_enrollment_rates(self, admin_session, app_session):
        """Confirmed/pending/not_returning counts."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_prereqs(admin_session, tenant["id"])

        campaign_id = await _seed_return_intent_campaign(
            admin_session, tenant["id"], ids["school_id"], ids["year_id"],
        )

        # 5 returning intents
        for _ in range(5):
            stu = await _seed_student(
                admin_session, tenant["id"], ids["school_id"], ids["class_id"],
            )
            await _seed_return_intent(
                admin_session, tenant["id"], ids["school_id"],
                campaign_id, ids["year_id"], stu,
                intent="returning",
            )

        # 2 not_returning intents
        for _ in range(2):
            stu = await _seed_student(
                admin_session, tenant["id"], ids["school_id"], ids["class_id"],
            )
            await _seed_return_intent(
                admin_session, tenant["id"], ids["school_id"],
                campaign_id, ids["year_id"], stu,
                intent="not_returning", reason="relocation",
            )

        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.analytics_service import AdmissionsAnalyticsService

        svc = AdmissionsAnalyticsService(app_session)
        result = await svc.get_re_enrollment_rates(
            tenant["id"], ids["school_id"], year_count=3,
        )

        assert len(result["years"]) >= 1
        year = result["years"][0]
        assert year["total_students"] == 7
        assert year["returning_count"] == 5
        assert year["re_enrollment_rate"] == pytest.approx(71.4, abs=0.1)


class TestAnalyticsFiltering:
    """Academic year filter on analytics."""

    async def test_analytics_academic_year_filter(self, admin_session, app_session):
        """Filter by period -> only matching data in funnel."""
        tenant = await create_test_tenant(admin_session)
        ids = await _seed_prereqs(admin_session, tenant["id"])

        # Seed apps in the known period
        await _seed_application(
            admin_session, tenant["id"], ids["school_id"],
            ids["period_id"], ids["class_id"], "enrolled",
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        from app.services.admissions.analytics_service import AdmissionsAnalyticsService

        svc = AdmissionsAnalyticsService(app_session)

        # With the period filter
        result_filtered = await svc.get_full_funnel(
            tenant["id"], ids["school_id"], period_id=ids["period_id"],
        )
        stages = {s["stage"]: s["count"] for s in result_filtered["stages"]}
        assert stages["enrolled"] == 1

        # With a random period -> no data
        result_empty = await svc.get_full_funnel(
            tenant["id"], ids["school_id"], period_id=uuid4(),
        )
        stages_empty = {s["stage"]: s["count"] for s in result_empty["stages"]}
        assert stages_empty["enrolled"] == 0


class TestAnalyticsTenantIsolation:
    """Tenant A's analytics must not leak into Tenant B's results."""

    async def test_analytics_tenant_isolation(self, admin_session, app_session):
        """Only own tenant data in results."""
        tenant_a = await create_test_tenant(admin_session, subdomain=f"an-a-{uuid4().hex[:8]}")
        tenant_b = await create_test_tenant(admin_session, subdomain=f"an-b-{uuid4().hex[:8]}")

        ids_a = await _seed_prereqs(admin_session, tenant_a["id"])
        ids_b = await _seed_prereqs(admin_session, tenant_b["id"])

        # Seed data only in Tenant A
        for _ in range(3):
            await _seed_inquiry(admin_session, tenant_a["id"], ids_a["school_id"])
        await _seed_application(
            admin_session, tenant_a["id"], ids_a["school_id"],
            ids_a["period_id"], ids_a["class_id"], "enrolled",
        )
        await admin_session.commit()

        # Tenant B's funnel should be empty
        await set_app_tenant_context(app_session, tenant_b["id"])
        from app.services.admissions.analytics_service import AdmissionsAnalyticsService

        svc_b = AdmissionsAnalyticsService(app_session)
        result_b = await svc_b.get_full_funnel(
            tenant_b["id"], ids_b["school_id"],
        )

        for stage in result_b["stages"]:
            assert stage["count"] == 0
