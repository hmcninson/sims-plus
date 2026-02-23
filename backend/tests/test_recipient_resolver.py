"""
Tests for the RecipientResolver service.

Uses the two-engine pattern: admin_engine seeds data, app_engine runs queries
under RLS. Verifies audience resolution for all_parents, all_staff,
class_parents, deduplication, empty results, tenant isolation, and filtering.
"""

import pytest
import pytest_asyncio
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    admin_session_maker,
    app_session_maker,
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
    clear_app_tenant_context,
)
from app.services.messaging.recipient_resolver import (
    RecipientResolver,
    RecipientResolverError,
)


# ===========================
# Fixtures
# ===========================


@pytest_asyncio.fixture
async def resolver_data(admin_session, app_session):
    """
    Seed data for resolver tests:
    - Tenant A with a school, class, 2 students, 2 guardians (1 shared), 2 staff
    - Tenant B with a school and 1 staff (for isolation test)
    """
    # ---- Tenant A ----
    tenant_a = await create_test_tenant(admin_session, subdomain=f"resolver-a-{uuid4().hex[:8]}")
    tenant_a_id = tenant_a["id"]
    school_a_id = uuid4()
    class_a_id = uuid4()
    section_a_id = uuid4()
    student_1_id = uuid4()
    student_2_id = uuid4()
    guardian_1_id = uuid4()
    guardian_2_id = uuid4()
    staff_1_id = uuid4()
    staff_2_id = uuid4()

    # School
    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Resolver School A', 'resolver-a', 'RA', 'basic')
        """),
        {"id": str(school_a_id), "tid": str(tenant_a_id)},
    )

    # Class
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, school_id, name, level)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid), 'Class 1', 'primary_1')
        """),
        {"id": str(class_a_id), "tid": str(tenant_a_id), "sid": str(school_a_id)},
    )

    # Students (active, linked to class and school)
    for sid, sname, student_id_code in [(student_1_id, "Kwame", "RA-001"), (student_2_id, "Ama", "RA-002")]:
        await admin_session.execute(
            text("""
                INSERT INTO students (id, tenant_id, school_id, class_id, student_id,
                    first_name, last_name, date_of_birth, gender, status)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:cid AS uuid), :student_id, :fn, 'Test', '2015-01-01', 'male', 'active')
            """),
            {
                "id": str(sid), "tid": str(tenant_a_id), "sid": str(school_a_id),
                "cid": str(class_a_id), "student_id": student_id_code, "fn": sname,
            },
        )

    # Guardians
    await admin_session.execute(
        text("""
            INSERT INTO guardians (id, tenant_id, school_id, first_name, last_name, phone, email)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'Kofi', 'Parent', '+233241111111', 'kofi@test.com')
        """),
        {"id": str(guardian_1_id), "tid": str(tenant_a_id), "sid": str(school_a_id)},
    )
    await admin_session.execute(
        text("""
            INSERT INTO guardians (id, tenant_id, school_id, first_name, last_name, phone, email)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'Akua', 'Parent', '+233242222222', 'akua@test.com')
        """),
        {"id": str(guardian_2_id), "tid": str(tenant_a_id), "sid": str(school_a_id)},
    )

    # Student-Guardian links
    # Guardian 1 is parent of BOTH students (tests deduplication)
    for student_id in [student_1_id, student_2_id]:
        await admin_session.execute(
            text("""
                INSERT INTO student_guardians (id, tenant_id, school_id, student_id, guardian_id,
                    relationship, is_primary, is_emergency_contact)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:stid AS uuid), CAST(:gid AS uuid), 'father', true, true)
            """),
            {
                "id": str(uuid4()), "tid": str(tenant_a_id), "sid": str(school_a_id),
                "stid": str(student_id), "gid": str(guardian_1_id),
            },
        )

    # Guardian 2 is parent of only student 2
    await admin_session.execute(
        text("""
            INSERT INTO student_guardians (id, tenant_id, school_id, student_id, guardian_id,
                relationship, is_primary, is_emergency_contact)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:stid AS uuid), CAST(:gid AS uuid), 'mother', false, false)
        """),
        {
            "id": str(uuid4()), "tid": str(tenant_a_id), "sid": str(school_a_id),
            "stid": str(student_2_id), "gid": str(guardian_2_id),
        },
    )

    # Staff (2 active, in tenant A)
    for sid, sname, semail, sphone in [
        (staff_1_id, "Teacher", "teacher1@test.com", "+233243333333"),
        (staff_2_id, "Admin", "admin1@test.com", "+233244444444"),
    ]:
        await admin_session.execute(
            text("""
                INSERT INTO staff (id, tenant_id, school_id, staff_id, first_name, last_name,
                    email, phone, gender, job_title, staff_type, status, employment_date)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :staff_code, :fn, 'Staff', :email, :phone, 'male', 'Teacher',
                    'teaching', 'active', '2024-01-01')
            """),
            {
                "id": str(sid), "tid": str(tenant_a_id), "sid": str(school_a_id),
                "staff_code": f"RS-{sname}", "fn": sname, "email": semail, "phone": sphone,
            },
        )

    # ---- Tenant B (for isolation) ----
    tenant_b = await create_test_tenant(admin_session, subdomain=f"resolver-b-{uuid4().hex[:8]}")
    tenant_b_id = tenant_b["id"]
    school_b_id = uuid4()
    staff_b_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Resolver School B', 'resolver-b', 'RB', 'basic')
        """),
        {"id": str(school_b_id), "tid": str(tenant_b_id)},
    )

    await admin_session.execute(
        text("""
            INSERT INTO staff (id, tenant_id, school_id, staff_id, first_name, last_name,
                email, phone, gender, job_title, staff_type, status, employment_date)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                'RB-001', 'Tenant', 'B-Staff', 'tenantb@test.com', '+233245555555',
                'male', 'Teacher', 'teaching', 'active', '2024-01-01')
        """),
        {"id": str(staff_b_id), "tid": str(tenant_b_id), "sid": str(school_b_id)},
    )

    await admin_session.commit()

    yield {
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "school_a_id": school_a_id,
        "school_b_id": school_b_id,
        "class_a_id": class_a_id,
        "student_1_id": student_1_id,
        "student_2_id": student_2_id,
        "guardian_1_id": guardian_1_id,
        "guardian_2_id": guardian_2_id,
        "staff_1_id": staff_1_id,
        "staff_2_id": staff_2_id,
        "staff_b_id": staff_b_id,
    }

    # Cleanup (no rollback needed since admin_session fixture handles that,
    # but since we committed, we need to clean explicitly)
    async with admin_session_maker() as cleanup_sess:
        for tid in [str(tenant_a_id), str(tenant_b_id)]:
            for table in [
                "student_guardians", "guardians", "students",
                "staff", "class_sections", "classes",
                "schools", "users",
            ]:
                await cleanup_sess.execute(
                    text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                    {"tid": tid},
                )
            await cleanup_sess.execute(
                text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
                {"tid": tid},
            )
        await cleanup_sess.commit()


# ===========================
# Tests
# ===========================


@pytest.mark.asyncio
async def test_resolve_all_parents_returns_unique_guardians(resolver_data, app_session):
    """all_parents should return de-duplicated guardians with phones."""
    d = resolver_data
    await set_app_tenant_context(app_session, d["tenant_a_id"])

    resolver = RecipientResolver(app_session)
    result = await resolver.resolve(tenant_id=d["tenant_a_id"], audience="all_parents")

    # Should have exactly 2 guardians (guardian_1 de-duplicated despite 2 students)
    assert len(result) == 2
    phones = {r["phone"] for r in result}
    assert "+233241111111" in phones
    assert "+233242222222" in phones

    await clear_app_tenant_context(app_session)


@pytest.mark.asyncio
async def test_resolve_all_parents_deduplicates(resolver_data, app_session):
    """Guardian linked to multiple students should appear only once."""
    d = resolver_data
    await set_app_tenant_context(app_session, d["tenant_a_id"])

    resolver = RecipientResolver(app_session)
    result = await resolver.resolve(tenant_id=d["tenant_a_id"], audience="all_parents")

    # Guardian 1 (Kofi) is linked to 2 students but should appear once
    kofi_entries = [r for r in result if r["phone"] == "+233241111111"]
    assert len(kofi_entries) == 1

    await clear_app_tenant_context(app_session)


@pytest.mark.asyncio
async def test_resolve_all_staff_returns_active(resolver_data, app_session):
    """all_staff should return active staff with phone and email."""
    d = resolver_data
    await set_app_tenant_context(app_session, d["tenant_a_id"])

    resolver = RecipientResolver(app_session)
    result = await resolver.resolve(tenant_id=d["tenant_a_id"], audience="all_staff")

    assert len(result) == 2
    emails = {r["email"] for r in result}
    assert "teacher1@test.com" in emails
    assert "admin1@test.com" in emails
    assert all(r["type"] == "staff" for r in result)

    await clear_app_tenant_context(app_session)


@pytest.mark.asyncio
async def test_resolve_class_parents_filters_by_class(resolver_data, app_session):
    """class_parents should return only guardians of students in the specified class."""
    d = resolver_data
    await set_app_tenant_context(app_session, d["tenant_a_id"])

    resolver = RecipientResolver(app_session)
    result = await resolver.resolve(
        tenant_id=d["tenant_a_id"],
        audience="class_parents",
        class_id=d["class_a_id"],
    )

    # Both students are in class_a, so both guardians should be returned
    assert len(result) == 2

    await clear_app_tenant_context(app_session)


@pytest.mark.asyncio
async def test_resolve_empty_result(resolver_data, app_session):
    """Resolving for a tenant with no matching data should return empty list."""
    d = resolver_data
    # Use Tenant B context -- it has staff but no students/guardians
    await set_app_tenant_context(app_session, d["tenant_b_id"])

    resolver = RecipientResolver(app_session)
    result = await resolver.resolve(tenant_id=d["tenant_b_id"], audience="all_parents")

    assert result == []

    await clear_app_tenant_context(app_session)


@pytest.mark.asyncio
async def test_resolve_tenant_isolation(resolver_data, app_session):
    """Tenant B's resolver must not see Tenant A's staff."""
    d = resolver_data
    await set_app_tenant_context(app_session, d["tenant_b_id"])

    resolver = RecipientResolver(app_session)
    result = await resolver.resolve(tenant_id=d["tenant_b_id"], audience="all_staff")

    # Tenant B should only see its own 1 staff member
    assert len(result) == 1
    assert result[0]["email"] == "tenantb@test.com"

    await clear_app_tenant_context(app_session)


@pytest.mark.asyncio
async def test_resolve_all_staff_excludes_inactive(resolver_data, admin_session, app_session):
    """Terminated staff should not appear in all_staff resolution."""
    d = resolver_data

    # Terminate one staff member in Tenant A
    await admin_session.execute(
        text("""
            UPDATE staff SET status = 'terminated'
            WHERE id = CAST(:id AS uuid)
        """),
        {"id": str(d["staff_2_id"])},
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, d["tenant_a_id"])

    resolver = RecipientResolver(app_session)
    result = await resolver.resolve(tenant_id=d["tenant_a_id"], audience="all_staff")

    # Only 1 active staff member should remain
    assert len(result) == 1
    assert result[0]["email"] == "teacher1@test.com"

    await clear_app_tenant_context(app_session)


@pytest.mark.asyncio
async def test_resolve_class_parents_requires_class_id(resolver_data, app_session):
    """class_parents without class_id should raise RecipientResolverError."""
    d = resolver_data
    await set_app_tenant_context(app_session, d["tenant_a_id"])

    resolver = RecipientResolver(app_session)
    with pytest.raises(RecipientResolverError) as exc_info:
        await resolver.resolve(tenant_id=d["tenant_a_id"], audience="class_parents")

    assert "class_id" in str(exc_info.value.message).lower()

    await clear_app_tenant_context(app_session)
