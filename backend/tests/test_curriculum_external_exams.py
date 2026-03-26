"""
Tests for ExternalExamService.

Covers: create registration, plan limits, bulk register (incl. limit),
update with immutable field rejection, soft delete, CSV import (WAEC dry run),
CSV row count limit, CSV formula injection prevention, and school_id assignment.
"""

import pytest
from uuid import uuid4
from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

from app.services.curriculum.external_exam_service import ExternalExamService, _sanitize_csv_cell
from app.services.curriculum._shared import CurriculumServiceError


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

async def _create_tenant_with_tier(admin_session, tier: str):
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


async def _seed_school_and_student(admin_session, tenant_id):
    school_id = uuid4()
    student_id = uuid4()
    class_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"School-{uuid4().hex[:6]}", "slug": f"sch-{uuid4().hex[:8]}"},
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
                :student_id, 'Test', 'Student', '2008-01-15', 'male', 'active',
                CAST(:cid AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(student_id), "tid": str(tenant_id), "sid": str(school_id),
         "student_id": f"STU-{uuid4().hex[:6]}", "cid": str(class_id)},
    )

    return {"school_id": school_id, "student_id": student_id}


def _make_registration_data(student_id):
    """Build a dict matching ExternalExamRegistrationCreate fields."""
    return {
        "student_id": student_id,
        "exam_board": "waec",
        "exam_session": "May 2026",
        "subjects": [
            {"subject_code": "0580", "subject_name": "Mathematics"},
        ],
        "candidate_number": f"WC-{uuid4().hex[:6]}",
    }


class TestCreateRegistration:
    """Test external exam registration creation."""

    async def test_create_registration_happy_path(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_school_and_student(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ExternalExamService(app_session)

        data = _make_registration_data(prereqs["student_id"])
        reg = await svc.create_registration(tenant["id"], prereqs["school_id"], data)

        assert reg.exam_board.value == "waec"
        assert reg.exam_session == "May 2026"
        assert reg.registration_status == "pending"
        assert reg.school_id == prereqs["school_id"]

    async def test_trial_tenant_blocked(self, app_session, admin_session):
        tenant = await create_test_tenant(admin_session)  # trial
        prereqs = await _seed_school_and_student(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ExternalExamService(app_session)

        data = _make_registration_data(prereqs["student_id"])
        with pytest.raises(CurriculumServiceError) as exc:
            await svc.create_registration(tenant["id"], prereqs["school_id"], data)
        assert exc.value.code == "plan_limit"


class TestBulkRegister:
    """Test bulk registration creation."""

    async def test_bulk_register_up_to_200(self, app_session, admin_session):
        """Bulk register with 2 students succeeds."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_school_and_student(admin_session, tenant["id"])

        # Create a second student
        student2_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO students (id, tenant_id, school_id, student_id,
                    first_name, last_name, date_of_birth, gender, status,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :student_id, 'Jane', 'Doe', '2008-06-20', 'female', 'active',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(student2_id), "tid": str(tenant["id"]),
             "sid": str(prereqs["school_id"]),
             "student_id": f"STU-{uuid4().hex[:6]}"},
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ExternalExamService(app_session)

        registrations = [
            _make_registration_data(prereqs["student_id"]),
            _make_registration_data(student2_id),
        ]
        results = await svc.bulk_register(
            tenant["id"], prereqs["school_id"], registrations,
        )
        assert len(results) == 2

    async def test_bulk_register_over_200_fails(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_school_and_student(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ExternalExamService(app_session)

        # Create 201 registration dicts (all for same student for simplicity)
        registrations = [_make_registration_data(prereqs["student_id"]) for _ in range(201)]

        with pytest.raises(CurriculumServiceError) as exc:
            await svc.bulk_register(tenant["id"], prereqs["school_id"], registrations)
        assert exc.value.code == "bulk_limit_exceeded"


class TestUpdateRegistration:
    """Test registration updates with immutable field rejection."""

    async def test_update_mutable_fields(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_school_and_student(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ExternalExamService(app_session)

        data = _make_registration_data(prereqs["student_id"])
        reg = await svc.create_registration(tenant["id"], prereqs["school_id"], data)
        reg_id = reg.id

        updated = await svc.update_registration(
            tenant["id"], reg_id,
            {"candidate_number": "NEW-123", "registration_status": "confirmed"},
        )
        assert updated.candidate_number == "NEW-123"
        assert updated.registration_status == "confirmed"

    async def test_update_immutable_field_rejected(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_school_and_student(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ExternalExamService(app_session)

        data = _make_registration_data(prereqs["student_id"])
        reg = await svc.create_registration(tenant["id"], prereqs["school_id"], data)
        reg_id = reg.id

        with pytest.raises(CurriculumServiceError) as exc:
            await svc.update_registration(
                tenant["id"], reg_id,
                {"student_id": str(uuid4())},
            )
        assert exc.value.code == "immutable_field"


class TestSoftDelete:
    """Test registration soft deletion."""

    async def test_soft_delete_registration(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_school_and_student(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ExternalExamService(app_session)

        data = _make_registration_data(prereqs["student_id"])
        reg = await svc.create_registration(tenant["id"], prereqs["school_id"], data)
        reg_id = reg.id

        await svc.soft_delete_registration(tenant["id"], reg_id)

        with pytest.raises(CurriculumServiceError) as exc:
            await svc.get_registration(tenant["id"], reg_id)
        assert exc.value.code == "not_found"


class TestCSVImport:
    """Test CSV results import."""

    async def test_waec_format_dry_run(self, app_session, admin_session):
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        prereqs = await _seed_school_and_student(admin_session, tenant["id"])
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ExternalExamService(app_session)

        # Create a registration with a known candidate number
        data = _make_registration_data(prereqs["student_id"])
        data["candidate_number"] = "CAND001"
        await svc.create_registration(tenant["id"], prereqs["school_id"], data)

        csv_content = (
            "CandidateNumber,SubjectCode,SubjectName,Grade,Score\n"
            "CAND001,0580,Mathematics,A1,85\n"
            "CAND001,0610,Biology,B2,72\n"
        )

        result = await svc.import_results_csv(
            tenant["id"], "waec", "May 2026", csv_content, dry_run=True,
        )

        assert result.total_rows == 2
        assert result.matched == 1  # CAND001 matched
        assert len(result.errors) == 0

    async def test_csv_row_count_limit(self, app_session, admin_session):
        """CSV with >5000 rows should error."""
        tenant = await _create_tenant_with_tier(admin_session, "professional")
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        svc = ExternalExamService(app_session)

        # Build a CSV with 5001 data rows
        header = "CandidateNumber,SubjectCode,SubjectName,Grade,Score\n"
        rows = "".join(
            f"CAND{i:04d},0580,Mathematics,A1,85\n" for i in range(5001)
        )
        csv_content = header + rows

        result = await svc.import_results_csv(
            tenant["id"], "waec", "May 2026", csv_content, dry_run=True,
        )

        assert any("exceeds maximum" in e for e in result.errors)


class TestCSVFormulaInjection:
    """Test CSV cell sanitization."""

    def test_formula_injection_prefixed(self):
        """Cells starting with = get prefixed with apostrophe."""
        assert _sanitize_csv_cell("=CMD()") == "'=CMD()"
        assert _sanitize_csv_cell("+1234") == "'+1234"
        assert _sanitize_csv_cell("-DROP TABLE") == "'-DROP TABLE"
        assert _sanitize_csv_cell("@SUM(A1)") == "'@SUM(A1)"

    def test_safe_cells_unchanged(self):
        assert _sanitize_csv_cell("Mathematics") == "Mathematics"
        assert _sanitize_csv_cell("A1") == "A1"
        assert _sanitize_csv_cell("85") == "85"
        assert _sanitize_csv_cell("") == ""
