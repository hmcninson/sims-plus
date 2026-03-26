"""
RLS Isolation Tests for Multi-Curriculum Module (9 tables).

Verifies that tenant B cannot see, modify, or delete tenant A's data.
Uses the two-engine test pattern (admin_session for seeding, app_session for RLS queries).

If any test here fails, tenant data is leaking across tenants.
"""

import pytest
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
    TENANT_SCOPED_TABLES,
)

pytestmark = [
    pytest.mark.rls,
    pytest.mark.asyncio,
    pytest.mark.xdist_group("rls_serial"),
]

# All 9 curriculum tables that must have RLS
CURRICULUM_TABLES = [
    "curriculum_profiles",
    "assessment_structures",
    "assessment_components",
    "report_card_configs",
    "grade_equivalencies",
    "subject_curriculum_mappings",
    "external_exam_registrations",
    "student_credit_accumulations",
    "predicted_grades",
]


async def _seed_curriculum_prerequisites(admin_session, tenant_id):
    """Seed school, student, user, academic_year, subject, grading_scale, grade.

    Returns dict with all IDs needed to populate curriculum tables.
    """
    school_id = uuid4()
    student_id = uuid4()
    user_id = uuid4()
    academic_year_id = uuid4()
    subject_id = uuid4()
    grading_scale_id = uuid4()
    grade_id = uuid4()
    class_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School {uuid4().hex[:6]}", "slug": f"school-{uuid4().hex[:8]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31', 'active', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(academic_year_id), "tid": str(tenant_id),
         "name": f"AY-{uuid4().hex[:6]}"},
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
            INSERT INTO students (id, tenant_id, school_id, student_id,
                first_name, last_name, date_of_birth, gender, status, class_id,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :student_id, 'Test', 'Student', '2012-05-15', 'male', 'active',
                CAST(:cid AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(student_id), "tid": str(tenant_id), "sid": str(school_id),
         "student_id": f"STU-{uuid4().hex[:6]}", "cid": str(class_id)},
    )

    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email,
                '$argon2id$v=19$m=65536,t=2,p=1$fake_hash',
                'Admin', 'User', 'school_admin', 'active',
                true, false, 0, 'Africa/Accra',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"admin-{uuid4().hex[:6]}@test.com"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO subjects (id, tenant_id, name, code, category,
                is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :code,
                'core', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(subject_id), "tid": str(tenant_id),
         "name": f"Maths-{uuid4().hex[:6]}", "code": f"MTH{uuid4().hex[:4]}".upper()},
    )

    await admin_session.execute(
        text("""
            INSERT INTO grading_scales (id, tenant_id, name, is_default,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(grading_scale_id), "tid": str(tenant_id),
         "name": f"Scale-{uuid4().hex[:6]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO grades (id, tenant_id, grading_scale_id,
                grade, min_score, max_score, grade_point,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:gsid AS uuid), 'A', 80, 100, 4.0,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(grade_id), "tid": str(tenant_id),
         "gsid": str(grading_scale_id)},
    )

    return {
        "school_id": school_id,
        "student_id": student_id,
        "user_id": user_id,
        "academic_year_id": academic_year_id,
        "subject_id": subject_id,
        "grading_scale_id": grading_scale_id,
        "grade_id": grade_id,
        "class_id": class_id,
    }


async def _seed_curriculum_profile(admin_session, tenant_id, school_id):
    """Seed a curriculum profile. Returns profile_id."""
    profile_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO curriculum_profiles (
                id, tenant_id, school_id, name, curriculum_type,
                academic_calendar_type, periods_per_year,
                score_display_mode, show_position, show_class_average,
                use_gpa, use_credits, use_criterion_grading,
                is_default, is_active,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :name, 'ges', 'terms', 3, 'grade_and_score',
                true, true, false, false, false, false, true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(profile_id), "tid": str(tenant_id),
         "sid": str(school_id), "name": f"Profile-{uuid4().hex[:6]}"},
    )
    return profile_id


class TestCurriculumTablesInTenantScopedList:
    """All 9 curriculum tables must be registered in TENANT_SCOPED_TABLES."""

    async def test_all_9_curriculum_tables_in_tenant_scoped_list(self):
        for table in CURRICULUM_TABLES:
            assert table in TENANT_SCOPED_TABLES, (
                f"Curriculum table '{table}' is missing from TENANT_SCOPED_TABLES"
            )


class TestRLSEnabledOnCurriculumTables:
    """Verify RLS is enabled and forced on all curriculum tables."""

    async def test_rls_enabled_on_all_curriculum_tables(self, app_session):
        result = await app_session.execute(
            text("""
                SELECT tablename, rowsecurity
                FROM pg_tables
                WHERE schemaname = 'public' AND tablename = ANY(:tables)
            """),
            {"tables": CURRICULUM_TABLES},
        )
        rows = result.fetchall()

        found_tables = {row.tablename for row in rows}
        missing = set(CURRICULUM_TABLES) - found_tables
        assert not missing, (
            f"Curriculum tables not found in database: {missing}. "
            f"Run 'alembic upgrade head' on the test database."
        )

        for row in rows:
            assert row.rowsecurity is True, (
                f"RLS not enabled on curriculum table '{row.tablename}'"
            )

    async def test_force_rls_on_all_curriculum_tables(self, app_session):
        result = await app_session.execute(
            text("""
                SELECT relname, relforcerowsecurity
                FROM pg_class WHERE relname = ANY(:tables)
            """),
            {"tables": CURRICULUM_TABLES},
        )
        for row in result.fetchall():
            assert row.relforcerowsecurity is True, (
                f"FORCE RLS not set on '{row.relname}'"
            )

    async def test_tenant_isolation_policy_on_all_curriculum_tables(self, app_session):
        for table_name in CURRICULUM_TABLES:
            result = await app_session.execute(
                text("""
                    SELECT policyname, qual, with_check
                    FROM pg_policies
                    WHERE schemaname = 'public' AND tablename = :table_name
                """),
                {"table_name": table_name},
            )
            policies = result.fetchall()
            assert len(policies) > 0, f"No RLS policies on '{table_name}'"

            has_tenant_policy = any(
                "get_current_tenant_id" in (row.qual or "")
                and "get_current_tenant_id" in (row.with_check or "")
                for row in policies
            )
            assert has_tenant_policy, (
                f"'{table_name}' has no policy using get_current_tenant_id() "
                f"in both USING and WITH CHECK"
            )


class TestCurriculumProfileIsolation:
    """Tenant B must not see Tenant A's curriculum profiles."""

    async def test_tenant_b_cannot_see_tenant_a_profiles(self, app_session, admin_session):
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs = await _seed_curriculum_prerequisites(admin_session, tenant_a["id"])
        await _seed_curriculum_profile(admin_session, tenant_a["id"], prereqs["school_id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_a["id"])
        result = await app_session.execute(text("SELECT count(*) FROM curriculum_profiles"))
        assert result.scalar() >= 1, "Tenant A should see its own profile"

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM curriculum_profiles"))
        assert result.scalar() == 0, "Tenant B must NOT see Tenant A's profiles"

    async def test_tenant_b_cannot_update_tenant_a_profiles(self, app_session, admin_session):
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs = await _seed_curriculum_prerequisites(admin_session, tenant_a["id"])
        profile_id = await _seed_curriculum_profile(admin_session, tenant_a["id"], prereqs["school_id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("UPDATE curriculum_profiles SET name = 'hacked' WHERE id = CAST(:id AS uuid)"),
            {"id": str(profile_id)},
        )
        assert result.rowcount == 0, "Tenant B must NOT update Tenant A's profiles"


class TestAssessmentStructureIsolation:
    """Assessment structures must be invisible across tenants."""

    async def test_tenant_b_cannot_see_tenant_a_structures(self, app_session, admin_session):
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs = await _seed_curriculum_prerequisites(admin_session, tenant_a["id"])
        profile_id = await _seed_curriculum_profile(admin_session, tenant_a["id"], prereqs["school_id"])

        structure_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO assessment_structures (
                    id, tenant_id, school_id, curriculum_profile_id,
                    name, is_active, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:pid AS uuid), :name, true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {"id": str(structure_id), "tid": str(tenant_a["id"]),
             "sid": str(prereqs["school_id"]), "pid": str(profile_id),
             "name": f"Struct-{uuid4().hex[:6]}"},
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM assessment_structures"))
        assert result.scalar() == 0


class TestAssessmentComponentIsolation:
    """Assessment components must be invisible across tenants."""

    async def test_tenant_b_cannot_see_tenant_a_components(self, app_session, admin_session):
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs = await _seed_curriculum_prerequisites(admin_session, tenant_a["id"])
        profile_id = await _seed_curriculum_profile(admin_session, tenant_a["id"], prereqs["school_id"])

        structure_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO assessment_structures (
                    id, tenant_id, school_id, curriculum_profile_id,
                    name, is_active, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:pid AS uuid), :name, true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {"id": str(structure_id), "tid": str(tenant_a["id"]),
             "sid": str(prereqs["school_id"]), "pid": str(profile_id),
             "name": f"Struct-{uuid4().hex[:6]}"},
        )

        await admin_session.execute(
            text("""
                INSERT INTO assessment_components (
                    id, tenant_id, school_id, assessment_structure_id,
                    component_type, name, weight, sequence,
                    is_external, maps_to_ca, maps_to_exam,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:stid AS uuid), 'exam', 'Final Exam', 100, 1,
                    false, false, true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {"id": str(uuid4()), "tid": str(tenant_a["id"]),
             "sid": str(prereqs["school_id"]), "stid": str(structure_id)},
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM assessment_components"))
        assert result.scalar() == 0


class TestGradeEquivalencyIsolation:
    """Grade equivalencies must be invisible across tenants."""

    async def test_tenant_b_cannot_see_tenant_a_equivalencies(self, app_session, admin_session):
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs = await _seed_curriculum_prerequisites(admin_session, tenant_a["id"])

        # Create a second grading scale + grade for target
        target_scale_id = uuid4()
        target_grade_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO grading_scales (id, tenant_id, name, is_default, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, false,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(target_scale_id), "tid": str(tenant_a["id"]),
             "name": f"Target-{uuid4().hex[:6]}"},
        )
        await admin_session.execute(
            text("""
                INSERT INTO grades (id, tenant_id, grading_scale_id,
                    grade, min_score, max_score, grade_point,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:gsid AS uuid), 'A*', 90, 100, 4.0,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(target_grade_id), "tid": str(tenant_a["id"]),
             "gsid": str(target_scale_id)},
        )

        await admin_session.execute(
            text("""
                INSERT INTO grade_equivalencies (
                    id, tenant_id, source_grading_scale_id, target_grading_scale_id,
                    source_grade_id, target_grade_id,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:src_scale AS uuid), CAST(:tgt_scale AS uuid),
                    CAST(:src_grade AS uuid), CAST(:tgt_grade AS uuid),
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {"id": str(uuid4()), "tid": str(tenant_a["id"]),
             "src_scale": str(prereqs["grading_scale_id"]),
             "tgt_scale": str(target_scale_id),
             "src_grade": str(prereqs["grade_id"]),
             "tgt_grade": str(target_grade_id)},
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM grade_equivalencies"))
        assert result.scalar() == 0


class TestExternalExamRegistrationIsolation:
    """External exam registrations must be invisible across tenants."""

    async def test_tenant_b_cannot_see_tenant_a_registrations(self, app_session, admin_session):
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs = await _seed_curriculum_prerequisites(admin_session, tenant_a["id"])

        await admin_session.execute(
            text("""
                INSERT INTO external_exam_registrations (
                    id, tenant_id, school_id, student_id,
                    exam_board, exam_session, registration_status,
                    subjects, created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:stid AS uuid),
                    'waec', 'May 2026', 'pending',
                    '[{"subject_code": "0580", "subject_name": "Maths"}]'::jsonb,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {"id": str(uuid4()), "tid": str(tenant_a["id"]),
             "sid": str(prereqs["school_id"]),
             "stid": str(prereqs["student_id"])},
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM external_exam_registrations")
        )
        assert result.scalar() == 0


class TestStudentCreditAccumulationIsolation:
    """Student credit accumulations must be invisible across tenants."""

    async def test_tenant_b_cannot_see_tenant_a_credits(self, app_session, admin_session):
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs = await _seed_curriculum_prerequisites(admin_session, tenant_a["id"])
        profile_id = await _seed_curriculum_profile(admin_session, tenant_a["id"], prereqs["school_id"])

        await admin_session.execute(
            text("""
                INSERT INTO student_credit_accumulations (
                    id, tenant_id, school_id, student_id,
                    curriculum_profile_id, academic_year_id,
                    subject_id, credits_attempted, credits_earned,
                    grade_points, is_ap, is_honors,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:stid AS uuid), CAST(:pid AS uuid),
                    CAST(:ayid AS uuid), CAST(:subid AS uuid),
                    4.0, 4.0, 3.5, false, false,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {"id": str(uuid4()), "tid": str(tenant_a["id"]),
             "sid": str(prereqs["school_id"]),
             "stid": str(prereqs["student_id"]),
             "pid": str(profile_id),
             "ayid": str(prereqs["academic_year_id"]),
             "subid": str(prereqs["subject_id"])},
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(
            text("SELECT count(*) FROM student_credit_accumulations")
        )
        assert result.scalar() == 0


class TestPredictedGradeIsolation:
    """Predicted grades must be invisible across tenants."""

    async def test_tenant_b_cannot_see_tenant_a_predictions(self, app_session, admin_session):
        tenant_a = await create_test_tenant(admin_session)
        tenant_b = await create_test_tenant(admin_session)
        prereqs = await _seed_curriculum_prerequisites(admin_session, tenant_a["id"])

        await admin_session.execute(
            text("""
                INSERT INTO predicted_grades (
                    id, tenant_id, school_id, student_id,
                    subject_id, academic_year_id,
                    predicted_grade, predicted_by, predicted_at,
                    created_at, updated_at
                ) VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:stid AS uuid), CAST(:subid AS uuid),
                    CAST(:ayid AS uuid),
                    'A*', CAST(:uid AS uuid), CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {"id": str(uuid4()), "tid": str(tenant_a["id"]),
             "sid": str(prereqs["school_id"]),
             "stid": str(prereqs["student_id"]),
             "subid": str(prereqs["subject_id"]),
             "ayid": str(prereqs["academic_year_id"]),
             "uid": str(prereqs["user_id"])},
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant_b["id"])
        result = await app_session.execute(text("SELECT count(*) FROM predicted_grades"))
        assert result.scalar() == 0
