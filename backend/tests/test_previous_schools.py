"""
Tests for previous schools and structured medical data (Phase 3).

Covers: add, list, update, delete, IDOR prevention,
structured medical storage and sanitization.
Uses two-engine pattern (admin for seeding, app for RLS queries).
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


async def _seed_prev_school_prereqs(admin_session, tenant_id):
    """Seed school and student. Returns dict with IDs."""
    school_id = uuid4()
    student_id = uuid4()

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
            INSERT INTO students (id, tenant_id, school_id, student_id,
                first_name, last_name, date_of_birth, gender, status,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :stuid, 'Yaa', 'Adomako', '2012-11-05', 'female', 'active',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(student_id), "tid": str(tenant_id), "sid": str(school_id),
            "stuid": f"STU-{uuid4().hex[:8]}",
        },
    )

    await admin_session.commit()
    return {
        "school_id": school_id,
        "student_id": student_id,
    }


# --- Tests ---


async def test_add_previous_school(app_session, admin_session):
    """Create a previous school record with all fields."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prev_school_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)
    record = await svc.add_previous_school(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        school_name="Achimota Primary School",
        school_address="Accra, Ghana",
        last_class="Primary 4",
        years_attended="2019-2023",
        transfer_reason="Family moved",
        leaving_certificate_ref="LC-2023-001",
    )

    assert record.id is not None
    assert record.school_name == "Achimota Primary School"
    assert record.last_class == "Primary 4"
    assert record.years_attended == "2019-2023"
    assert record.transfer_reason == "Family moved"
    assert record.leaving_certificate_ref == "LC-2023-001"


async def test_list_previous_schools(app_session, admin_session):
    """List returns records ordered by created_at DESC."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prev_school_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)

    # Add two records
    await svc.add_previous_school(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        school_name="First School",
    )
    await svc.add_previous_school(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        school_name="Second School",
    )

    records = await svc.list_previous_schools(tenant["id"], prereqs["student_id"])
    assert len(records) == 2
    # Most recent first (DESC order)
    assert records[0].school_name == "Second School"
    assert records[1].school_name == "First School"


async def test_update_previous_school(app_session, admin_session):
    """Partial update of previous school record."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prev_school_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)
    record = await svc.add_previous_school(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        school_name="Original Name",
    )

    updated = await svc.update_previous_school(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        record_id=record.id,
        school_name="Updated Name",
        last_class="Primary 6",
    )
    assert updated.school_name == "Updated Name"
    assert updated.last_class == "Primary 6"


async def test_delete_previous_school(app_session, admin_session):
    """Hard delete removes the record entirely."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prev_school_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)
    record = await svc.add_previous_school(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        school_name="To Delete",
    )

    result = await svc.delete_previous_school(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        record_id=record.id,
    )
    assert result is True

    # Should be gone
    records = await svc.list_previous_schools(tenant["id"], prereqs["student_id"])
    assert len(records) == 0


async def test_delete_previous_school_idor(app_session, admin_session):
    """Delete rejects if record belongs to a different student."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prev_school_prereqs(admin_session, tenant["id"])

    # Create a second student
    student2_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO students (id, tenant_id, school_id, student_id,
                first_name, last_name, date_of_birth, gender, status,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :stuid, 'Kofi', 'Mensah', '2012-02-02', 'male', 'active',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(student2_id), "tid": str(tenant["id"]),
            "sid": str(prereqs["school_id"]),
            "stuid": f"STU-{uuid4().hex[:8]}",
        },
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.services.student._shared import StudentServiceError

    svc = StudentService(app_session)

    # Add record for student 1
    record = await svc.add_previous_school(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        school_name="Student 1 school",
    )

    # Try to delete using student 2's ID
    with pytest.raises(StudentServiceError) as exc_info:
        await svc.delete_previous_school(
            tenant_id=tenant["id"],
            student_id=student2_id,
            record_id=record.id,
        )
    assert exc_info.value.code == "previous_school_not_found"


async def test_structured_medical_update(app_session, admin_session):
    """Store and retrieve structured medical JSONB data."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prev_school_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)
    medical_data = {
        "blood_group": "O+",
        "conditions": [
            {"name": "Asthma", "severity": "moderate", "medication": "Ventolin"},
        ],
        "allergies": [
            {"name": "Peanuts", "severity": "severe"},
        ],
        "vaccinations": [
            {"name": "BCG", "date": "2013-01-15"},
        ],
        "emergency_protocol": "Call parent immediately. Administer inhaler.",
    }

    student = await svc.update_structured_medical(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        medical_data=medical_data,
    )

    assert student.structured_medical is not None
    assert student.structured_medical["blood_group"] == "O+"
    assert len(student.structured_medical["conditions"]) == 1
    assert student.structured_medical["conditions"][0]["name"] == "Asthma"
    # Legacy column sync
    assert student.blood_group == "O+"
    assert student.medical_conditions == "Asthma"
    assert student.allergies == "Peanuts"


async def test_structured_medical_empty_conditions(app_session, admin_session):
    """Medical data with empty conditions still stores correctly."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_prev_school_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)
    medical_data = {
        "blood_group": "AB-",
        "conditions": [],
        "allergies": [],
    }

    student = await svc.update_structured_medical(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        medical_data=medical_data,
    )

    assert student.structured_medical["blood_group"] == "AB-"
    assert student.structured_medical["conditions"] == []
    assert student.blood_group == "AB-"
