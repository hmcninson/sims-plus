"""
Tests for student transfer workflows (Phase 2).

Covers: external transfer initiation, completion, chain transfers,
validation errors, class assignment updates, and export.
Uses two-engine pattern (admin for seeding, app for RLS queries).
"""

import json
import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---


async def _seed_transfer_prereqs(admin_session, tenant_id, *, two_schools=False):
    """Seed school(s), academic year, class, student, user.

    If two_schools=True, creates a second school with its own class and section
    (for chain transfer tests).

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
         "name": f"SchoolA-{uuid4().hex[:6]}", "slug": f"school-a-{uuid4().hex[:8]}"},
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
         "name": f"ClassA-{uuid4().hex[:6]}"},
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
                :stuid, 'Ama', 'Mensah', '2012-05-20', 'female', 'active',
                CAST(:cid AS uuid), CAST(:secid AS uuid),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(student_id), "tid": str(tenant_id), "sid": str(school_id),
            "stuid": f"STU-{uuid4().hex[:8]}",
            "cid": str(class_id), "secid": str(section_id),
        },
    )

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

    # Active class assignment
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

    result = {
        "school_id": school_id,
        "ay_id": ay_id,
        "class_id": class_id,
        "section_id": section_id,
        "student_id": student_id,
        "user_id": user_id,
        "ch_id": ch_id,
    }

    if two_schools:
        school2_id = uuid4()
        class2_id = uuid4()
        section2_id = uuid4()

        await admin_session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, school_type,
                    student_id_prefix, is_active, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                    'basic', 'STU', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(school2_id), "tid": str(tenant_id),
             "name": f"SchoolB-{uuid4().hex[:6]}", "slug": f"school-b-{uuid4().hex[:8]}"},
        )

        await admin_session.execute(
            text("""
                INSERT INTO classes (id, tenant_id, name, level, sequence,
                    is_active, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                    'primary', 2, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(class2_id), "tid": str(tenant_id),
             "name": f"ClassB-{uuid4().hex[:6]}"},
        )

        await admin_session.execute(
            text("""
                INSERT INTO class_sections (id, tenant_id, class_id, name,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:cid AS uuid), 'B', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(section2_id), "tid": str(tenant_id), "cid": str(class2_id)},
        )

        result["school2_id"] = school2_id
        result["class2_id"] = class2_id
        result["section2_id"] = section2_id

    await admin_session.commit()
    return result


# --- Tests ---


async def test_initiate_external_transfer(app_session, admin_session):
    """Initiate transfer creates clearance with type='transfer'."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_transfer_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)
    result = await svc.initiate_transfer(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        destination_school="International School of Accra",
        reason="Family relocation",
        effective_date=date(2026, 3, 25),
        performed_by=prereqs["user_id"],
    )

    assert result["clearance_id"] is not None
    assert result["type"] == "transfer"
    assert result["destination_school"] == "International School of Accra"


async def test_complete_transfer(app_session, admin_session):
    """Complete transfer sets student status to 'transferred'."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_transfer_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)

    # Initiate with fee_override to skip clearance items
    await svc.initiate_transfer(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        destination_school="Another School",
        reason="Opportunity",
        effective_date=date(2026, 3, 25),
        performed_by=prereqs["user_id"],
        fee_override=True,
    )

    student = await svc.complete_transfer(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        performed_by=prereqs["user_id"],
    )
    assert student.status.value == "transferred"


async def test_chain_transfer(app_session, admin_session):
    """Chain transfer keeps student active but changes school/class."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_transfer_prereqs(
        admin_session, tenant["id"], two_schools=True,
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)

    # Capture IDs before transfer
    orig_school = prereqs["school_id"]
    dest_school = prereqs["school2_id"]
    dest_class = prereqs["class2_id"]
    dest_section = prereqs["section2_id"]

    student = await svc.transfer_within_chain(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        from_school_id=orig_school,
        to_school_id=dest_school,
        to_class_id=dest_class,
        to_section_id=dest_section,
        reason="Chain transfer",
        effective_date=date(2026, 3, 25),
        performed_by=prereqs["user_id"],
        fee_override=True,
    )

    # Student stays active, school/class/section changed
    assert student.status.value == "active"
    assert student.school_id == dest_school
    assert student.class_id == dest_class
    assert student.section_id == dest_section


async def test_chain_transfer_wrong_source_school(app_session, admin_session):
    """Chain transfer rejected if student is not at the from_school."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_transfer_prereqs(
        admin_session, tenant["id"], two_schools=True,
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.services.student._shared import StudentServiceError

    svc = StudentService(app_session)

    # Use school2 as from_school (student is at school1)
    with pytest.raises(StudentServiceError) as exc_info:
        await svc.transfer_within_chain(
            tenant_id=tenant["id"],
            student_id=prereqs["student_id"],
            from_school_id=prereqs["school2_id"],
            to_school_id=prereqs["school_id"],
            to_class_id=prereqs["class_id"],
            to_section_id=prereqs["section_id"],
            reason="Wrong source",
            effective_date=date(2026, 3, 25),
            performed_by=prereqs["user_id"],
            fee_override=True,
        )
    assert exc_info.value.code == "wrong_source_school"


async def test_chain_transfer_invalid_destination_school(app_session, admin_session):
    """Chain transfer rejected for nonexistent destination school."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_transfer_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.services.student._shared import StudentServiceError

    svc = StudentService(app_session)

    with pytest.raises(StudentServiceError) as exc_info:
        await svc.transfer_within_chain(
            tenant_id=tenant["id"],
            student_id=prereqs["student_id"],
            from_school_id=prereqs["school_id"],
            to_school_id=uuid4(),  # nonexistent
            to_class_id=prereqs["class_id"],
            to_section_id=prereqs["section_id"],
            reason="Bad destination",
            effective_date=date(2026, 3, 25),
            performed_by=prereqs["user_id"],
            fee_override=True,
        )
    assert exc_info.value.code == "invalid_destination_school"


async def test_transfer_closes_class_assignment(app_session, admin_session):
    """External transfer closes the student's active class assignment."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_transfer_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)

    await svc.initiate_transfer(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        destination_school="Other School",
        reason="Moving",
        effective_date=date(2026, 3, 25),
        performed_by=prereqs["user_id"],
        fee_override=True,
    )

    await svc.complete_transfer(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        performed_by=prereqs["user_id"],
    )

    # Check class history has left_date
    history = await svc.get_class_history(tenant["id"], prereqs["student_id"])
    assert len(history) >= 1
    closed = [h for h in history if h["left_date"] is not None]
    assert len(closed) >= 1
    assert closed[0]["reason"] == "transferred"


async def test_chain_transfer_creates_new_assignment(app_session, admin_session):
    """Chain transfer creates a new class history record at destination."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_transfer_prereqs(
        admin_session, tenant["id"], two_schools=True,
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)

    await svc.transfer_within_chain(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        from_school_id=prereqs["school_id"],
        to_school_id=prereqs["school2_id"],
        to_class_id=prereqs["class2_id"],
        to_section_id=prereqs["section2_id"],
        reason="Chain move",
        effective_date=date(2026, 3, 25),
        performed_by=prereqs["user_id"],
        fee_override=True,
    )

    # Verify class history: should have old (closed) + new (open)
    history = await svc.get_class_history(tenant["id"], prereqs["student_id"])
    assert len(history) >= 2

    # One should be closed (left_date set), one should be open (no left_date)
    closed = [h for h in history if h["left_date"] is not None]
    open_records = [h for h in history if h["left_date"] is None]
    assert len(closed) >= 1
    assert len(open_records) >= 1
    assert closed[0]["reason"] == "chain_transfer"


async def test_export_record_json(app_session, admin_session):
    """Export student record returns valid JSON with expected fields."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_transfer_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService

    svc = StudentService(app_session)
    result_bytes = await svc.export_student_record(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        format="json",
    )

    record = json.loads(result_bytes.decode("utf-8"))
    assert "student" in record
    assert record["student"]["first_name"] == "Ama"
    assert record["student"]["last_name"] == "Mensah"
    assert record["student"]["status"] == "active"
    assert "class_history" in record
    assert "status_history" in record
    assert "finance_summary" in record
    assert "exported_at" in record


async def test_chain_transfer_outstanding_fees_blocks(app_session, admin_session):
    """Chain transfer without fee_override raises when student has outstanding fees."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_transfer_prereqs(
        admin_session, tenant["id"], two_schools=True,
    )

    # Add an outstanding invoice (needs academic_year_id and term_id)
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
        {"id": str(term_id), "tid": str(tenant["id"]), "ayid": str(prereqs["ay_id"])},
    )
    await admin_session.execute(
        text("""
            INSERT INTO invoices (id, tenant_id, student_id, school_id,
                academic_year_id, term_id,
                invoice_number, total_amount, amount_paid, status,
                due_date, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:stuid AS uuid),
                CAST(:sid AS uuid), CAST(:ayid AS uuid), CAST(:termid AS uuid),
                :inv_num, 300.00, 0.00, 'issued',
                '2026-06-30', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(invoice_id), "tid": str(tenant["id"]),
         "stuid": str(prereqs["student_id"]), "sid": str(prereqs["school_id"]),
         "ayid": str(prereqs["ay_id"]), "termid": str(term_id),
         "inv_num": f"INV-{uuid4().hex[:8]}"},
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.services.student._shared import StudentServiceError

    svc = StudentService(app_session)

    with pytest.raises(StudentServiceError) as exc_info:
        await svc.transfer_within_chain(
            tenant_id=tenant["id"],
            student_id=prereqs["student_id"],
            from_school_id=prereqs["school_id"],
            to_school_id=prereqs["school2_id"],
            to_class_id=prereqs["class2_id"],
            to_section_id=prereqs["section2_id"],
            reason="Transfer",
            effective_date=date(2026, 3, 25),
            performed_by=prereqs["user_id"],
            fee_override=False,
        )
    assert exc_info.value.code == "outstanding_fees"


async def test_complete_transfer_wrong_clearance_type(app_session, admin_session):
    """complete_transfer rejected if pending clearance is type='withdrawal'."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_transfer_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.student import StudentService
    from app.services.student._shared import StudentServiceError

    svc = StudentService(app_session)

    # Initiate a WITHDRAWAL, then try to complete as TRANSFER
    await svc.initiate_withdrawal(
        tenant_id=tenant["id"],
        student_id=prereqs["student_id"],
        school_id=prereqs["school_id"],
        reason="Wrong type test",
        effective_date=date(2026, 3, 25),
        performed_by=prereqs["user_id"],
        fee_override=True,
    )

    with pytest.raises(StudentServiceError) as exc_info:
        await svc.complete_transfer(
            tenant_id=tenant["id"],
            student_id=prereqs["student_id"],
            performed_by=prereqs["user_id"],
        )
    assert exc_info.value.code == "wrong_clearance_type"
