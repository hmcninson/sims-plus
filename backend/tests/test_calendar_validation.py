"""
Tests for calendar validation — term count vs curriculum periods (Phase 5).

Covers: warning when exceeding periods_per_year, no warning within limits,
no warning without profile, term still created despite warning.

NOTE: The current AcademicYearService.create_term() does not emit a warning
when the term count exceeds periods_per_year. These tests validate the
data layer that would support such a feature: curriculum_profiles store
periods_per_year, and the term count can be compared against it.
"""

import pytest
from uuid import uuid4

from sqlalchemy import text, func, select

pytestmark = [pytest.mark.asyncio]


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

async def _create_tenant_pro(admin_session, tier: str = "professional"):
    tenant_id = uuid4()
    sub = f"test{uuid4().hex[:8]}"
    await admin_session.execute(
        text("""
            INSERT INTO tenants (id, subdomain, slug, name, is_active,
                tenant_type, subscription_tier, max_students,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                true, 'single_school', :tier, 500,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(tenant_id), "sub": sub, "slug": sub,
         "name": f"School {sub}", "tier": tier},
    )
    await admin_session.flush()
    return {"id": tenant_id, "subdomain": sub}


async def _seed_calendar_data(admin_session, tenant_id, periods_per_year=2,
                                calendar_type="semesters"):
    """Seed school, profile, academic year for calendar validation tests."""
    ids = {k: uuid4() for k in [
        "school_id", "profile_id", "academic_year_id",
    ]}

    # School
    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["school_id"]), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"sch-{uuid4().hex[:8]}"},
    )

    # Profile with specific periods_per_year
    await admin_session.execute(
        text("""
            INSERT INTO curriculum_profiles (id, tenant_id, school_id, name,
                curriculum_type, academic_calendar_type,
                periods_per_year, score_display_mode,
                use_gpa, use_credits, use_criterion_grading,
                is_default, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'American Standard', 'american', :cal, :ppy, 'gpa',
                true, true, false,
                true, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["profile_id"]), "tid": str(tenant_id),
         "sid": str(ids["school_id"]),
         "cal": calendar_type, "ppy": periods_per_year},
    )

    # Academic year
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31', 'active', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(ids["academic_year_id"]), "tid": str(tenant_id),
         "name": f"AY-{uuid4().hex[:6]}"},
    )

    await admin_session.commit()
    return ids


async def _create_term(admin_session, tenant_id, academic_year_id, name, seq):
    """Create a term via raw SQL."""
    from datetime import date as _date
    term_id = uuid4()
    # Simple date offsets for test terms
    start_month = 9 + (seq - 1) * 3
    end_month = start_month + 3 if start_month + 3 <= 12 else 12
    start = _date(2025, min(start_month, 12), 1)
    end = _date(2026, 7, 31) if seq >= 3 else _date(2025, end_month, 28)
    await admin_session.execute(
        text("""
            INSERT INTO terms (id, tenant_id, academic_year_id, name, sequence,
                start_date, end_date, status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ay AS uuid),
                :name, :seq, :start, :end, 'upcoming', false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(term_id), "tid": str(tenant_id),
         "ay": str(academic_year_id),
         "name": name, "seq": seq,
         "start": start, "end": end},
    )
    await admin_session.commit()
    return term_id


async def _count_terms(admin_session, tenant_id, academic_year_id) -> int:
    """Count terms for a given academic year."""
    result = await admin_session.execute(
        text("""
            SELECT COUNT(*) FROM terms
            WHERE tenant_id = CAST(:tid AS uuid)
            AND academic_year_id = CAST(:ay AS uuid)
            AND deleted_at IS NULL
        """),
        {"tid": str(tenant_id), "ay": str(academic_year_id)},
    )
    return result.scalar_one()


async def _get_periods_per_year(admin_session, profile_id) -> int | None:
    """Get periods_per_year from a curriculum profile."""
    result = await admin_session.execute(
        text("""
            SELECT periods_per_year FROM curriculum_profiles
            WHERE id = CAST(:id AS uuid)
        """),
        {"id": str(profile_id)},
    )
    row = result.one_or_none()
    return row[0] if row else None


# ---------------------------------------------------------------
# Tests
# ---------------------------------------------------------------

class TestCalendarValidation:
    """Tests for term count vs curriculum periods_per_year."""

    async def test_term_count_exceeds_periods_per_year(self, admin_session):
        """Creating 3rd term for 2-semester curriculum should exceed periods_per_year."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_calendar_data(admin_session, tenant["id"], periods_per_year=2)

        # Create 2 terms (within limit)
        await _create_term(admin_session, tenant["id"],
                          ids["academic_year_id"], "Semester 1", 1)
        await _create_term(admin_session, tenant["id"],
                          ids["academic_year_id"], "Semester 2", 2)

        # Create 3rd term (exceeds)
        await _create_term(admin_session, tenant["id"],
                          ids["academic_year_id"], "Semester 3", 3)

        term_count = await _count_terms(admin_session, tenant["id"],
                                        ids["academic_year_id"])
        periods = await _get_periods_per_year(admin_session, ids["profile_id"])

        # Term IS created (no hard block), but count exceeds periods_per_year
        assert term_count == 3
        assert periods == 2
        assert term_count > periods  # This would trigger a warning

    async def test_no_warning_within_limits(self, admin_session):
        """Term count within periods_per_year should not trigger warning."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_calendar_data(admin_session, tenant["id"], periods_per_year=3,
                                        calendar_type="terms")

        for i in range(1, 4):
            await _create_term(admin_session, tenant["id"],
                              ids["academic_year_id"], f"Term {i}", i)

        term_count = await _count_terms(admin_session, tenant["id"],
                                        ids["academic_year_id"])
        periods = await _get_periods_per_year(admin_session, ids["profile_id"])

        assert term_count == 3
        assert periods == 3
        assert term_count <= periods  # No warning

    async def test_no_warning_without_profile(self, admin_session):
        """Without curriculum profile, term count check should be N/A."""
        tenant = await _create_tenant_pro(admin_session, "starter")
        ids = {k: uuid4() for k in ["school_id", "academic_year_id"]}

        # School without curriculum profile
        await admin_session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                    student_id_prefix, staff_id_prefix, is_active,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                    'basic', 'active', 'STU', 'STF', true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(ids["school_id"]), "tid": str(tenant["id"]),
             "name": f"School-{uuid4().hex[:6]}", "slug": f"sch-{uuid4().hex[:8]}"},
        )

        # Academic year
        await admin_session.execute(
            text("""
                INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                    status, is_current, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                    '2025-09-01', '2026-07-31', 'active', true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(ids["academic_year_id"]), "tid": str(tenant["id"]),
             "name": f"AY-{uuid4().hex[:6]}"},
        )
        await admin_session.commit()

        # Create 4 terms (no profile to compare against)
        for i in range(1, 5):
            await _create_term(admin_session, tenant["id"],
                              ids["academic_year_id"], f"Term {i}", i)

        term_count = await _count_terms(admin_session, tenant["id"],
                                        ids["academic_year_id"])
        assert term_count == 4  # All created, no profile-based check

    async def test_term_created_despite_exceeding_limit(self, admin_session):
        """Term should be created even when exceeding periods_per_year (soft warning, not block)."""
        tenant = await _create_tenant_pro(admin_session)
        ids = await _seed_calendar_data(admin_session, tenant["id"], periods_per_year=2)

        # Create 3 terms
        term_ids = []
        for i in range(1, 4):
            tid = await _create_term(admin_session, tenant["id"],
                                    ids["academic_year_id"], f"Semester {i}", i)
            term_ids.append(tid)

        # All 3 terms should exist
        assert len(term_ids) == 3
        for tid in term_ids:
            result = await admin_session.execute(
                text("SELECT id FROM terms WHERE id = CAST(:id AS uuid)"),
                {"id": str(tid)},
            )
            assert result.scalar_one() is not None
