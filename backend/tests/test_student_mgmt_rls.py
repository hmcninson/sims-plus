"""
RLS Isolation Tests for Student Management Gap Closure Phase 1.

Verifies:
1. student_class_history: Tenant B cannot see Tenant A's records
2. student_status_changes: Tenant B cannot see Tenant A's records
3. student_class_history: DELETE is denied (audit table — SELECT, INSERT, UPDATE only)
4. student_status_changes: UPDATE and DELETE are denied (append-only — SELECT, INSERT only)

Uses two-engine pattern (admin for seeding, app for RLS assertions).
"""

import pytest
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
    clear_app_tenant_context,
    TENANT_SCOPED_TABLES,
)

pytestmark = [
    pytest.mark.rls,
    pytest.mark.asyncio,
]


# --- Helpers ---


async def _seed_two_tenants_with_data(admin_session):
    """Create two tenants, each with a school, student, class, academic year,
    and one record in student_class_history + student_status_changes.

    Returns dict with tenant_a and tenant_b sub-dicts.
    """
    result = {}
    for label in ("a", "b"):
        tenant = await create_test_tenant(
            admin_session,
            subdomain=f"rls-{label}-{uuid4().hex[:8]}",
        )
        tid = tenant["id"]
        school_id = uuid4()
        class_id = uuid4()
        ay_id = uuid4()
        student_id = uuid4()

        await admin_session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, school_type,
                    student_id_prefix, is_active, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                    'basic', 'STU', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(school_id), "tid": str(tid),
             "name": f"School-{label}", "slug": f"school-{label}-{uuid4().hex[:8]}"},
        )
        await admin_session.execute(
            text("""
                INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                    status, is_current, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                    '2025-09-01', '2026-07-31', 'active', true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(ay_id), "tid": str(tid), "name": f"AY-{label}-{uuid4().hex[:6]}"},
        )
        await admin_session.execute(
            text("""
                INSERT INTO classes (id, tenant_id, name, level, sequence,
                    is_active, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                    'primary', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(class_id), "tid": str(tid),
             "name": f"Class-{label}-{uuid4().hex[:6]}"},
        )
        await admin_session.execute(
            text("""
                INSERT INTO students (id, tenant_id, school_id, student_id,
                    first_name, last_name, date_of_birth, gender, status,
                    class_id, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :stuid, :fn, 'Test', '2012-01-01', 'male', 'active',
                    CAST(:cid AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(student_id), "tid": str(tid), "sid": str(school_id),
             "stuid": f"STU-{label}-{uuid4().hex[:6]}", "fn": f"Student-{label}",
             "cid": str(class_id)},
        )

        # class history record
        ch_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO student_class_history (id, tenant_id, student_id, school_id,
                    class_id, academic_year_id, enrolled_date, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:stuid AS uuid),
                    CAST(:sid AS uuid), CAST(:cid AS uuid), CAST(:ayid AS uuid),
                    '2025-09-01', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(ch_id), "tid": str(tid), "stuid": str(student_id),
             "sid": str(school_id), "cid": str(class_id), "ayid": str(ay_id)},
        )

        # status change record
        sc_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO student_status_changes (id, tenant_id, student_id, school_id,
                    to_status, effective_date, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:stuid AS uuid),
                    CAST(:sid AS uuid), 'active', '2025-09-01',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(sc_id), "tid": str(tid), "stuid": str(student_id),
             "sid": str(school_id)},
        )

        result[f"tenant_{label}"] = {
            "tenant_id": tid,
            "school_id": school_id,
            "class_id": class_id,
            "ay_id": ay_id,
            "student_id": student_id,
            "ch_id": ch_id,
            "sc_id": sc_id,
        }

    await admin_session.commit()
    return result


# --- Tests ---


async def test_new_tables_in_tenant_scoped_list():
    """Verify student_class_history and student_status_changes are in TENANT_SCOPED_TABLES."""
    assert "student_class_history" in TENANT_SCOPED_TABLES
    assert "student_status_changes" in TENANT_SCOPED_TABLES


async def test_class_history_rls(app_session, admin_session):
    """Tenant B cannot see Tenant A's class history records."""
    data = await _seed_two_tenants_with_data(admin_session)
    a = data["tenant_a"]
    b = data["tenant_b"]

    # As Tenant A: should see 1 record
    await set_app_tenant_context(app_session, a["tenant_id"])
    result_a = await app_session.execute(
        text("SELECT id FROM student_class_history")
    )
    rows_a = result_a.fetchall()
    a_ids = {str(r[0]) for r in rows_a}
    assert str(a["ch_id"]) in a_ids

    # As Tenant B: should see only B's record, NOT A's
    await clear_app_tenant_context(app_session)
    await set_app_tenant_context(app_session, b["tenant_id"])
    result_b = await app_session.execute(
        text("SELECT id FROM student_class_history")
    )
    rows_b = result_b.fetchall()
    b_ids = {str(r[0]) for r in rows_b}
    assert str(b["ch_id"]) in b_ids
    assert str(a["ch_id"]) not in b_ids


async def test_status_changes_rls(app_session, admin_session):
    """Tenant B cannot see Tenant A's status change records."""
    data = await _seed_two_tenants_with_data(admin_session)
    a = data["tenant_a"]
    b = data["tenant_b"]

    # As Tenant A
    await set_app_tenant_context(app_session, a["tenant_id"])
    result_a = await app_session.execute(
        text("SELECT id FROM student_status_changes")
    )
    a_ids = {str(r[0]) for r in result_a.fetchall()}
    assert str(a["sc_id"]) in a_ids

    # As Tenant B
    await clear_app_tenant_context(app_session)
    await set_app_tenant_context(app_session, b["tenant_id"])
    result_b = await app_session.execute(
        text("SELECT id FROM student_status_changes")
    )
    b_ids = {str(r[0]) for r in result_b.fetchall()}
    assert str(b["sc_id"]) in b_ids
    assert str(a["sc_id"]) not in b_ids


async def test_class_history_no_delete(app_session, admin_session):
    """DELETE is denied on student_class_history when grants are restricted.

    The migration grants SELECT, INSERT, UPDATE (no DELETE) to sims_app_user.
    However, the test DB's ALTER DEFAULT PRIVILEGES gives full CRUD to all tables.
    This test first revokes DELETE to simulate production, then verifies the restriction.
    """
    data = await _seed_two_tenants_with_data(admin_session)
    a = data["tenant_a"]

    # Revoke DELETE to match the migration's intended grant
    await admin_session.execute(
        text("REVOKE DELETE ON student_class_history FROM sims_app_user")
    )
    await admin_session.commit()

    try:
        await set_app_tenant_context(app_session, a["tenant_id"])

        with pytest.raises(ProgrammingError, match="permission denied"):
            await app_session.execute(
                text("DELETE FROM student_class_history WHERE id = CAST(:id AS uuid)"),
                {"id": str(a["ch_id"])},
            )
        await app_session.rollback()
    finally:
        # Restore for other tests
        await admin_session.execute(
            text("GRANT DELETE ON student_class_history TO sims_app_user")
        )
        await admin_session.commit()


async def test_status_changes_no_update_no_delete(app_session, admin_session):
    """UPDATE and DELETE are denied on student_status_changes when grants are restricted.

    The migration grants SELECT, INSERT only (append-only) to sims_app_user.
    However, the test DB's ALTER DEFAULT PRIVILEGES gives full CRUD to all tables.
    This test first revokes UPDATE+DELETE to simulate production, then verifies.
    """
    data = await _seed_two_tenants_with_data(admin_session)
    a = data["tenant_a"]

    # Revoke UPDATE and DELETE to match the migration's intended grant
    await admin_session.execute(
        text("REVOKE UPDATE, DELETE ON student_status_changes FROM sims_app_user")
    )
    await admin_session.commit()

    try:
        await set_app_tenant_context(app_session, a["tenant_id"])

        # UPDATE should be denied
        with pytest.raises(ProgrammingError, match="permission denied"):
            await app_session.execute(
                text("""
                    UPDATE student_status_changes
                    SET reason = 'hacked'
                    WHERE id = CAST(:id AS uuid)
                """),
                {"id": str(a["sc_id"])},
            )
        await app_session.rollback()

        # Re-set context after rollback
        await set_app_tenant_context(app_session, a["tenant_id"])

        # DELETE should be denied
        with pytest.raises(ProgrammingError, match="permission denied"):
            await app_session.execute(
                text("DELETE FROM student_status_changes WHERE id = CAST(:id AS uuid)"),
                {"id": str(a["sc_id"])},
            )
        await app_session.rollback()
    finally:
        # Restore for other tests
        await admin_session.execute(
            text("GRANT UPDATE, DELETE ON student_status_changes TO sims_app_user")
        )
        await admin_session.commit()


# --- Phase 2-3 RLS Tests ---


async def _seed_phase23_data(admin_session):
    """Create two tenants with withdrawal_clearances, student_documents,
    previous_schools, and promotion_rules records.

    Returns dict with tenant_a and tenant_b sub-dicts.
    """
    result = {}
    for label in ("a", "b"):
        tenant = await create_test_tenant(
            admin_session,
            subdomain=f"rls23-{label}-{uuid4().hex[:8]}",
        )
        tid = tenant["id"]
        school_id = uuid4()
        student_id = uuid4()
        ay_id = uuid4()

        await admin_session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, school_type,
                    student_id_prefix, is_active, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                    'basic', 'STU', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(school_id), "tid": str(tid),
             "name": f"School-{label}", "slug": f"school-rls23-{label}-{uuid4().hex[:8]}"},
        )
        await admin_session.execute(
            text("""
                INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                    status, is_current, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                    '2025-09-01', '2026-07-31', 'active', true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(ay_id), "tid": str(tid),
             "name": f"AY-rls23-{label}-{uuid4().hex[:6]}"},
        )
        await admin_session.execute(
            text("""
                INSERT INTO students (id, tenant_id, school_id, student_id,
                    first_name, last_name, date_of_birth, gender, status,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :stuid, :fn, 'Test', '2012-01-01', 'male', 'active',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(student_id), "tid": str(tid), "sid": str(school_id),
             "stuid": f"STU-{label}-{uuid4().hex[:6]}", "fn": f"Student-{label}"},
        )

        # withdrawal_clearances
        wc_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO withdrawal_clearances (id, tenant_id, student_id, school_id,
                    type, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:stuid AS uuid),
                    CAST(:sid AS uuid), 'withdrawal',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(wc_id), "tid": str(tid),
             "stuid": str(student_id), "sid": str(school_id)},
        )

        # student_documents
        doc_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO student_documents (id, tenant_id, student_id, school_id,
                    document_type, title, file_url, file_size, mime_type,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:stuid AS uuid),
                    CAST(:sid AS uuid), 'birth_certificate', 'BC', 'fake/key', 1024,
                    'application/pdf', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(doc_id), "tid": str(tid),
             "stuid": str(student_id), "sid": str(school_id)},
        )

        # previous_schools
        ps_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO previous_schools (id, tenant_id, student_id, school_id,
                    school_name, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:stuid AS uuid),
                    CAST(:sid AS uuid), :sname,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(ps_id), "tid": str(tid),
             "stuid": str(student_id), "sid": str(school_id),
             "sname": f"PrevSchool-{label}"},
        )

        # promotion_rules
        pr_id = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO promotion_rules (id, tenant_id, school_id,
                    academic_year_id, min_average,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                    CAST(:sid AS uuid), CAST(:ayid AS uuid), 50.00,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(pr_id), "tid": str(tid), "sid": str(school_id),
             "ayid": str(ay_id)},
        )

        result[f"tenant_{label}"] = {
            "tenant_id": tid,
            "wc_id": wc_id,
            "doc_id": doc_id,
            "ps_id": ps_id,
            "pr_id": pr_id,
        }

    await admin_session.commit()
    return result


async def test_phase23_tables_in_tenant_scoped_list():
    """Verify Phase 2-3 tables are in TENANT_SCOPED_TABLES."""
    assert "withdrawal_clearances" in TENANT_SCOPED_TABLES
    assert "student_documents" in TENANT_SCOPED_TABLES
    assert "previous_schools" in TENANT_SCOPED_TABLES
    assert "promotion_rules" in TENANT_SCOPED_TABLES


async def test_withdrawal_clearances_rls(app_session, admin_session):
    """Tenant B cannot see Tenant A's withdrawal clearances."""
    data = await _seed_phase23_data(admin_session)
    a = data["tenant_a"]
    b = data["tenant_b"]

    await set_app_tenant_context(app_session, a["tenant_id"])
    result_a = await app_session.execute(
        text("SELECT id FROM withdrawal_clearances")
    )
    a_ids = {str(r[0]) for r in result_a.fetchall()}
    assert str(a["wc_id"]) in a_ids

    await clear_app_tenant_context(app_session)
    await set_app_tenant_context(app_session, b["tenant_id"])
    result_b = await app_session.execute(
        text("SELECT id FROM withdrawal_clearances")
    )
    b_ids = {str(r[0]) for r in result_b.fetchall()}
    assert str(b["wc_id"]) in b_ids
    assert str(a["wc_id"]) not in b_ids


async def test_student_documents_rls(app_session, admin_session):
    """Tenant B cannot see Tenant A's student documents."""
    data = await _seed_phase23_data(admin_session)
    a = data["tenant_a"]
    b = data["tenant_b"]

    await set_app_tenant_context(app_session, a["tenant_id"])
    result_a = await app_session.execute(
        text("SELECT id FROM student_documents")
    )
    a_ids = {str(r[0]) for r in result_a.fetchall()}
    assert str(a["doc_id"]) in a_ids

    await clear_app_tenant_context(app_session)
    await set_app_tenant_context(app_session, b["tenant_id"])
    result_b = await app_session.execute(
        text("SELECT id FROM student_documents")
    )
    b_ids = {str(r[0]) for r in result_b.fetchall()}
    assert str(b["doc_id"]) in b_ids
    assert str(a["doc_id"]) not in b_ids


async def test_previous_schools_rls(app_session, admin_session):
    """Tenant B cannot see Tenant A's previous school records."""
    data = await _seed_phase23_data(admin_session)
    a = data["tenant_a"]
    b = data["tenant_b"]

    await set_app_tenant_context(app_session, a["tenant_id"])
    result_a = await app_session.execute(
        text("SELECT id FROM previous_schools")
    )
    a_ids = {str(r[0]) for r in result_a.fetchall()}
    assert str(a["ps_id"]) in a_ids

    await clear_app_tenant_context(app_session)
    await set_app_tenant_context(app_session, b["tenant_id"])
    result_b = await app_session.execute(
        text("SELECT id FROM previous_schools")
    )
    b_ids = {str(r[0]) for r in result_b.fetchall()}
    assert str(b["ps_id"]) in b_ids
    assert str(a["ps_id"]) not in b_ids


async def test_promotion_rules_rls(app_session, admin_session):
    """Tenant B cannot see Tenant A's promotion rules."""
    data = await _seed_phase23_data(admin_session)
    a = data["tenant_a"]
    b = data["tenant_b"]

    await set_app_tenant_context(app_session, a["tenant_id"])
    result_a = await app_session.execute(
        text("SELECT id FROM promotion_rules")
    )
    a_ids = {str(r[0]) for r in result_a.fetchall()}
    assert str(a["pr_id"]) in a_ids

    await clear_app_tenant_context(app_session)
    await set_app_tenant_context(app_session, b["tenant_id"])
    result_b = await app_session.execute(
        text("SELECT id FROM promotion_rules")
    )
    b_ids = {str(r[0]) for r in result_b.fetchall()}
    assert str(b["pr_id"]) in b_ids
    assert str(a["pr_id"]) not in b_ids
