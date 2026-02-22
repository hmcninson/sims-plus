"""
SIMS Plus - Parent Access Isolation Tests

THE MOST CRITICAL test file for the parent portal.
Tests that parents can ONLY access data for their own children.

Setup creates:
- Tenant A with 2 parent users and 3 students
- Tenant B with 1 parent user and 1 student
- student_1 and student_3 linked to parent_a (via guardian email match)
- student_2 linked to parent_b
- Test data: teacher notes, announcements

Test priorities:
1. Parent A sees only their children (student_1, student_3)
2. Parent A CANNOT see Parent B's child (student_2)
3. Cross-tenant isolation: Parent from Tenant B cannot access Tenant A data
4. Non-parent roles cannot access parent-only endpoints
5. Unauthenticated requests return 401
"""

from datetime import datetime, UTC
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from unittest.mock import patch

from app.core.security import create_access_token
from app.main import app
from app.api.deps import get_db, get_unscoped_db
from tests.conftest import (
    admin_engine,
    admin_session_maker,
    app_engine,
    app_session_maker,
)


# Session maker for middleware tenant lookup in test DB
_test_mw_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)


# =====================================================================
# Fixtures
# =====================================================================


@pytest_asyncio.fixture
async def parent_portal_data():
    """Seed a full parent portal scenario across 2 tenants.

    Tenant A:
      - school_a
      - parent_a (user, role=parent, email=parent_a@...)
      - parent_b (user, role=parent, email=parent_b@...)
      - teacher_a (user, role=teacher)
      - guardian_a (email matches parent_a) linked to student_1 and student_3
      - guardian_b (email matches parent_b) linked to student_2
      - student_1, student_2, student_3
      - teacher_note on student_1 (visible to parent)
      - teacher_note on student_2 (visible to parent)
      - announcement (all_parents, published)

    Tenant B:
      - school_b
      - parent_c (user, role=parent, email=parent_c@...)
      - guardian_c linked to student_4
      - student_4
    """
    suffix = uuid4().hex[:8]

    # IDs
    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    school_a_id = uuid4()
    school_b_id = uuid4()
    parent_a_id = uuid4()
    parent_b_id = uuid4()
    parent_c_id = uuid4()
    teacher_a_id = uuid4()
    guardian_a_id = uuid4()
    guardian_b_id = uuid4()
    guardian_c_id = uuid4()
    student_1_id = uuid4()
    student_2_id = uuid4()
    student_3_id = uuid4()
    student_4_id = uuid4()
    sg_1_id = uuid4()
    sg_2_id = uuid4()
    sg_3_id = uuid4()
    sg_4_id = uuid4()
    note_1_id = uuid4()
    note_2_id = uuid4()
    announcement_id = uuid4()

    sub_a = f"pa-{suffix}"
    sub_b = f"pb-{suffix}"
    email_a = f"parent-a-{suffix}@test.com"
    email_b = f"parent-b-{suffix}@test.com"
    email_c = f"parent-c-{suffix}@test.com"
    teacher_email = f"teacher-{suffix}@test.com"

    async with admin_session_maker() as s:
        # --- Tenants ---
        for tid, sub in [(tenant_a_id, sub_a), (tenant_b_id, sub_b)]:
            await s.execute(text("""
                INSERT INTO tenants (id, subdomain, slug, name, is_active,
                    tenant_type, subscription_tier, max_students, max_staff, status)
                VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                    true, 'single_school', 'professional', 1000, 100, 'active')
            """), {"id": str(tid), "sub": sub, "slug": sub, "name": f"School {sub}"})

        # --- Schools ---
        await s.execute(text("""
            INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'TST', 'basic')
        """), {"id": str(school_a_id), "tid": str(tenant_a_id), "name": f"School A {suffix}", "slug": sub_a})

        await s.execute(text("""
            INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'TST', 'basic')
        """), {"id": str(school_b_id), "tid": str(tenant_b_id), "name": f"School B {suffix}", "slug": sub_b})

        # --- Users ---
        user_sql = text("""
            INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                role, status, email_verified, mfa_enabled, failed_login_attempts, timezone,
                school_id)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email,
                '$argon2id$v=19$m=65536,t=2,p=1$fake_hash',
                :fn, :ln, :role, 'active', true, false, 0, 'Africa/Accra',
                CAST(:sid AS uuid))
        """)
        # Parent A (tenant A)
        await s.execute(user_sql, {"id": str(parent_a_id), "tid": str(tenant_a_id),
            "email": email_a, "fn": "ParentA", "ln": "Test", "role": "parent", "sid": str(school_a_id)})
        # Parent B (tenant A)
        await s.execute(user_sql, {"id": str(parent_b_id), "tid": str(tenant_a_id),
            "email": email_b, "fn": "ParentB", "ln": "Test", "role": "parent", "sid": str(school_a_id)})
        # Teacher (tenant A)
        await s.execute(user_sql, {"id": str(teacher_a_id), "tid": str(tenant_a_id),
            "email": teacher_email, "fn": "Teacher", "ln": "Test", "role": "teacher", "sid": str(school_a_id)})
        # Parent C (tenant B)
        await s.execute(user_sql, {"id": str(parent_c_id), "tid": str(tenant_b_id),
            "email": email_c, "fn": "ParentC", "ln": "Test", "role": "parent", "sid": str(school_b_id)})

        # --- Students ---
        student_sql = text("""
            INSERT INTO students (id, tenant_id, student_id, first_name, last_name,
                date_of_birth, gender, status, school_id)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, :fn, :ln,
                '2015-01-15', 'male', 'active', CAST(:school_id AS uuid))
        """)
        await s.execute(student_sql, {"id": str(student_1_id), "tid": str(tenant_a_id),
            "sid": f"S1-{suffix}", "fn": "Child1", "ln": "A", "school_id": str(school_a_id)})
        await s.execute(student_sql, {"id": str(student_2_id), "tid": str(tenant_a_id),
            "sid": f"S2-{suffix}", "fn": "Child2", "ln": "B", "school_id": str(school_a_id)})
        await s.execute(student_sql, {"id": str(student_3_id), "tid": str(tenant_a_id),
            "sid": f"S3-{suffix}", "fn": "Child3", "ln": "A", "school_id": str(school_a_id)})
        await s.execute(student_sql, {"id": str(student_4_id), "tid": str(tenant_b_id),
            "sid": f"S4-{suffix}", "fn": "Child4", "ln": "C", "school_id": str(school_b_id)})

        # --- Guardians (email must match user email for parent resolution) ---
        guardian_sql = text("""
            INSERT INTO guardians (id, tenant_id, first_name, last_name, phone, email)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :fn, :ln, '0241234567', :email)
        """)
        await s.execute(guardian_sql, {"id": str(guardian_a_id), "tid": str(tenant_a_id),
            "fn": "ParentA", "ln": "Test", "email": email_a})
        await s.execute(guardian_sql, {"id": str(guardian_b_id), "tid": str(tenant_a_id),
            "fn": "ParentB", "ln": "Test", "email": email_b})
        await s.execute(guardian_sql, {"id": str(guardian_c_id), "tid": str(tenant_b_id),
            "fn": "ParentC", "ln": "Test", "email": email_c})

        # --- Student-Guardian links ---
        sg_sql = text("""
            INSERT INTO student_guardians (id, tenant_id, student_id, guardian_id,
                relationship, is_primary, is_emergency_contact, can_pickup)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:gid AS uuid), 'father', :primary, true, true)
        """)
        # Parent A linked to student_1 (primary) and student_3
        await s.execute(sg_sql, {"id": str(sg_1_id), "tid": str(tenant_a_id),
            "sid": str(student_1_id), "gid": str(guardian_a_id), "primary": True})
        await s.execute(sg_sql, {"id": str(sg_3_id), "tid": str(tenant_a_id),
            "sid": str(student_3_id), "gid": str(guardian_a_id), "primary": True})
        # Parent B linked to student_2
        await s.execute(sg_sql, {"id": str(sg_2_id), "tid": str(tenant_a_id),
            "sid": str(student_2_id), "gid": str(guardian_b_id), "primary": True})
        # Parent C linked to student_4 (tenant B)
        await s.execute(sg_sql, {"id": str(sg_4_id), "tid": str(tenant_b_id),
            "sid": str(student_4_id), "gid": str(guardian_c_id), "primary": True})

        # --- Teacher notes ---
        note_sql = text("""
            INSERT INTO teacher_notes (id, tenant_id, school_id, student_id, teacher_id,
                note_type, content, is_visible_to_parent, parent_acknowledged)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:stud_id AS uuid), CAST(:teach_id AS uuid),
                'positive', :content, true, false)
        """)
        await s.execute(note_sql, {"id": str(note_1_id), "tid": str(tenant_a_id),
            "sid": str(school_a_id), "stud_id": str(student_1_id),
            "teach_id": str(teacher_a_id), "content": "Great work in math!"})
        await s.execute(note_sql, {"id": str(note_2_id), "tid": str(tenant_a_id),
            "sid": str(school_a_id), "stud_id": str(student_2_id),
            "teach_id": str(teacher_a_id), "content": "Needs improvement in reading."})

        # --- Announcement (published, all_parents) ---
        await s.execute(text("""
            INSERT INTO announcements (id, tenant_id, school_id, title, content,
                target_audience, priority, published_at, is_pinned, author_id)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :title, :content, 'all_parents', 'normal',
                CURRENT_TIMESTAMP, false, CAST(:author_id AS uuid))
        """), {"id": str(announcement_id), "tid": str(tenant_a_id),
            "sid": str(school_a_id), "title": "Term 2 starts Monday",
            "content": "Please ensure uniforms are ready.",
            "author_id": str(teacher_a_id)})

        await s.commit()

    data = {
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "school_a_id": school_a_id,
        "school_b_id": school_b_id,
        "subdomain_a": sub_a,
        "subdomain_b": sub_b,
        "parent_a_id": parent_a_id,
        "parent_a_email": email_a,
        "parent_b_id": parent_b_id,
        "parent_b_email": email_b,
        "parent_c_id": parent_c_id,
        "parent_c_email": email_c,
        "teacher_a_id": teacher_a_id,
        "teacher_email": teacher_email,
        "student_1_id": student_1_id,
        "student_2_id": student_2_id,
        "student_3_id": student_3_id,
        "student_4_id": student_4_id,
        "note_1_id": note_1_id,
        "note_2_id": note_2_id,
        "announcement_id": announcement_id,
    }

    yield data

    # Cleanup
    async with admin_session_maker() as s:
        for tid in [tenant_a_id, tenant_b_id]:
            for table in [
                "teacher_notes", "announcements", "parent_notification_preferences",
                "student_guardians", "guardians", "students",
                "users", "schools",
            ]:
                await s.execute(
                    text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                    {"tid": str(tid)},
                )
            await s.execute(
                text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
                {"tid": str(tid)},
            )
        await s.commit()


def _make_parent_token(user_id, tenant_id, school_id, email):
    """Create a JWT for a parent user with parent permissions."""
    return create_access_token(
        subject=str(user_id),
        tenant_id=str(tenant_id),
        school_id=str(school_id),
        role="parent",
        permissions=[
            "parent.children.read",
            "parent.grades.read",
            "parent.attendance.read",
            "parent.finance.read",
            "parent.communication.read",
        ],
        extra_claims={"email": email},
    )


def _make_teacher_token(user_id, tenant_id, school_id, email):
    """Create a JWT for a teacher user (no parent permissions)."""
    return create_access_token(
        subject=str(user_id),
        tenant_id=str(tenant_id),
        school_id=str(school_id),
        role="teacher",
        permissions=["students.read", "attendance.mark", "exams.scores"],
        extra_claims={"email": email},
    )


def _setup_db_overrides():
    """Set up dependency overrides for get_db and get_unscoped_db."""

    async def override_get_db(request: Request):
        async with app_session_maker() as session:
            try:
                req_state = getattr(request, "state", None)
                tid = getattr(req_state, "tenant_id", None) if req_state else None
                if tid:
                    await session.execute(
                        text("SELECT set_tenant_context(CAST(:tenant_id AS uuid))"),
                        {"tenant_id": str(tid)},
                    )
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                try:
                    await session.execute(text("SELECT clear_tenant_context()"))
                except Exception:
                    pass
                await session.close()

    async def override_get_unscoped_db():
        async with admin_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_unscoped_db] = override_get_unscoped_db


def _clear_db_overrides():
    """Remove dependency overrides."""
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


@pytest_asyncio.fixture
async def parent_a_client(parent_portal_data):
    """HTTP client authenticated as Parent A (tenant A)."""
    d = parent_portal_data
    token = _make_parent_token(
        d["parent_a_id"], d["tenant_a_id"], d["school_a_id"], d["parent_a_email"],
    )
    _setup_db_overrides()
    with patch("app.middleware.tenant.async_session_maker", _test_mw_session_maker), \
         patch("app.main.async_session_maker", _test_mw_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": d["subdomain_a"],
            },
        ) as client:
            yield client
    _clear_db_overrides()


@pytest_asyncio.fixture
async def parent_b_client(parent_portal_data):
    """HTTP client authenticated as Parent B (tenant A)."""
    d = parent_portal_data
    token = _make_parent_token(
        d["parent_b_id"], d["tenant_a_id"], d["school_a_id"], d["parent_b_email"],
    )
    _setup_db_overrides()
    with patch("app.middleware.tenant.async_session_maker", _test_mw_session_maker), \
         patch("app.main.async_session_maker", _test_mw_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": d["subdomain_a"],
            },
        ) as client:
            yield client
    _clear_db_overrides()


@pytest_asyncio.fixture
async def parent_c_client(parent_portal_data):
    """HTTP client authenticated as Parent C (tenant B)."""
    d = parent_portal_data
    token = _make_parent_token(
        d["parent_c_id"], d["tenant_b_id"], d["school_b_id"], d["parent_c_email"],
    )
    _setup_db_overrides()
    with patch("app.middleware.tenant.async_session_maker", _test_mw_session_maker), \
         patch("app.main.async_session_maker", _test_mw_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": d["subdomain_b"],
            },
        ) as client:
            yield client
    _clear_db_overrides()


@pytest_asyncio.fixture
async def teacher_client(parent_portal_data):
    """HTTP client authenticated as a teacher (no parent permissions)."""
    d = parent_portal_data
    token = _make_teacher_token(
        d["teacher_a_id"], d["tenant_a_id"], d["school_a_id"], d["teacher_email"],
    )
    _setup_db_overrides()
    with patch("app.middleware.tenant.async_session_maker", _test_mw_session_maker), \
         patch("app.main.async_session_maker", _test_mw_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": d["subdomain_a"],
            },
        ) as client:
            yield client
    _clear_db_overrides()


@pytest_asyncio.fixture
async def unauthenticated_client():
    """HTTP client with no auth token."""
    with patch("app.middleware.tenant.async_session_maker", _test_mw_session_maker), \
         patch("app.main.async_session_maker", _test_mw_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client


# =====================================================================
# Tests: Parent sees only their own children
# =====================================================================


@pytest.mark.asyncio
async def test_parent_a_sees_only_own_children(parent_a_client, parent_portal_data):
    """Parent A should see student_1 and student_3, NOT student_2."""
    d = parent_portal_data
    client = parent_a_client
    response = await client.get("/api/v1/parent/children")

    assert response.status_code == 200
    children = response.json()
    child_ids = [c["id"] for c in children]

    assert str(d["student_1_id"]) in child_ids
    assert str(d["student_3_id"]) in child_ids
    assert str(d["student_2_id"]) not in child_ids
    assert len(children) == 2


@pytest.mark.asyncio
async def test_parent_b_sees_only_own_child(parent_b_client, parent_portal_data):
    """Parent B should see only student_2."""
    d = parent_portal_data
    client = parent_b_client
    response = await client.get("/api/v1/parent/children")

    assert response.status_code == 200
    children = response.json()
    child_ids = [c["id"] for c in children]

    assert str(d["student_2_id"]) in child_ids
    assert len(children) == 1


# =====================================================================
# Tests: Parent CANNOT access another parent's child data
# =====================================================================


@pytest.mark.asyncio
async def test_parent_a_cannot_view_overview_of_student_2(parent_a_client, parent_portal_data):
    """Parent A should get 403 when requesting overview for student_2 (Parent B's child)."""
    d = parent_portal_data
    client = parent_a_client
    response = await client.get(
        f"/api/v1/parent/children/{d['student_2_id']}/overview"
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_parent_a_cannot_view_notes_of_student_2(parent_a_client, parent_portal_data):
    """Parent A should get 403 when requesting teacher notes for student_2."""
    d = parent_portal_data
    client = parent_a_client
    response = await client.get(
        f"/api/v1/parent/children/{d['student_2_id']}/notes"
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_parent_a_cannot_acknowledge_note_for_student_2(parent_a_client, parent_portal_data):
    """Parent A should get 403 when acknowledging a note on student_2."""
    d = parent_portal_data
    client = parent_a_client
    response = await client.post(
        f"/api/v1/parent/children/{d['student_2_id']}/notes/{d['note_2_id']}/acknowledge"
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_parent_a_cannot_view_invoices_of_student_2(parent_a_client, parent_portal_data):
    """Parent A should get 403 when requesting invoices for student_2."""
    d = parent_portal_data
    client = parent_a_client
    response = await client.get(
        f"/api/v1/parent/children/{d['student_2_id']}/invoices"
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_parent_a_cannot_view_attendance_of_student_2(parent_a_client, parent_portal_data):
    """Parent A should get 403 when requesting attendance for student_2."""
    d = parent_portal_data
    client = parent_a_client
    response = await client.get(
        f"/api/v1/parent/children/{d['student_2_id']}/attendance?month=2026-02"
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_parent_a_cannot_view_grades_of_student_2(parent_a_client, parent_portal_data):
    """Parent A should get 403 when requesting grades for student_2."""
    d = parent_portal_data
    # Need a fake term_id since it is a required query param
    fake_term_id = uuid4()
    client = parent_a_client
    response = await client.get(
        f"/api/v1/parent/children/{d['student_2_id']}/grades?term_id={fake_term_id}"
    )

    assert response.status_code == 403


# =====================================================================
# Tests: Parent CAN access their own child's data
# =====================================================================


@pytest.mark.asyncio
async def test_parent_a_can_view_overview_of_own_child(parent_a_client, parent_portal_data):
    """Parent A should get 200 for their own child's overview."""
    d = parent_portal_data
    client = parent_a_client
    response = await client.get(
        f"/api/v1/parent/children/{d['student_1_id']}/overview"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["child"]["id"] == str(d["student_1_id"])
    assert data["child"]["first_name"] == "Child1"


@pytest.mark.asyncio
async def test_parent_a_can_view_notes_of_own_child(parent_a_client, parent_portal_data):
    """Parent A should see teacher notes for their own child."""
    d = parent_portal_data
    client = parent_a_client
    response = await client.get(
        f"/api/v1/parent/children/{d['student_1_id']}/notes"
    )

    assert response.status_code == 200
    notes = response.json()
    assert len(notes) == 1
    assert notes[0]["content"] == "Great work in math!"


@pytest.mark.asyncio
async def test_parent_a_can_acknowledge_own_childs_note(parent_a_client, parent_portal_data):
    """Parent A should be able to acknowledge a note on their own child."""
    d = parent_portal_data
    client = parent_a_client
    response = await client.post(
        f"/api/v1/parent/children/{d['student_1_id']}/notes/{d['note_1_id']}/acknowledge"
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_parent_a_acknowledge_is_idempotent(parent_a_client, parent_portal_data):
    """Acknowledging the same note twice should succeed (idempotent)."""
    d = parent_portal_data
    client = parent_a_client
    response1 = await client.post(
        f"/api/v1/parent/children/{d['student_1_id']}/notes/{d['note_1_id']}/acknowledge"
    )
    response2 = await client.post(
        f"/api/v1/parent/children/{d['student_1_id']}/notes/{d['note_1_id']}/acknowledge"
    )

    assert response1.status_code == 204
    assert response2.status_code == 204


# =====================================================================
# Tests: Announcements
# =====================================================================


@pytest.mark.asyncio
async def test_parent_a_sees_all_parents_announcement(parent_a_client, parent_portal_data):
    """Parent A should see the all_parents announcement."""
    client = parent_a_client
    response = await client.get("/api/v1/parent/announcements")

    assert response.status_code == 200
    announcements = response.json()
    assert len(announcements) >= 1
    titles = [a["title"] for a in announcements]
    assert "Term 2 starts Monday" in titles


# =====================================================================
# Tests: Cross-tenant isolation
# =====================================================================


@pytest.mark.asyncio
async def test_cross_tenant_parent_cannot_see_other_tenant_children(
    parent_c_client, parent_portal_data
):
    """Parent C (tenant B) should see only student_4, not tenant A students."""
    d = parent_portal_data
    client = parent_c_client
    response = await client.get("/api/v1/parent/children")

    assert response.status_code == 200
    children = response.json()
    child_ids = [c["id"] for c in children]

    assert str(d["student_4_id"]) in child_ids
    assert str(d["student_1_id"]) not in child_ids
    assert str(d["student_2_id"]) not in child_ids
    assert str(d["student_3_id"]) not in child_ids


# =====================================================================
# Tests: Non-parent role rejected
# =====================================================================


@pytest.mark.asyncio
async def test_teacher_cannot_access_parent_children_endpoint(
    teacher_client, parent_portal_data
):
    """A teacher should get 403 on /parent/children (missing parent.* permissions)."""
    client = teacher_client
    response = await client.get("/api/v1/parent/children")

    assert response.status_code == 403


# =====================================================================
# Tests: Unauthenticated access
# =====================================================================


@pytest.mark.asyncio
async def test_unauthenticated_cannot_access_children(unauthenticated_client):
    """Unauthenticated request without subdomain returns 400 (tenant context required).

    The tenant middleware rejects the request before the auth layer runs,
    because no X-Subdomain header is present.
    """
    response = await unauthenticated_client.get("/api/v1/parent/children")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_unauthenticated_cannot_access_announcements(unauthenticated_client):
    """Unauthenticated request without subdomain returns 400 (tenant context required).

    The tenant middleware rejects the request before the auth layer runs,
    because no X-Subdomain header is present.
    """
    response = await unauthenticated_client.get("/api/v1/parent/announcements")
    assert response.status_code == 400


# =====================================================================
# Tests: Nonexistent student
# =====================================================================


@pytest.mark.asyncio
async def test_parent_a_gets_403_for_nonexistent_student(parent_a_client, parent_portal_data):
    """Requesting overview for a random UUID should return 403 (access denied, not 404).

    The access check runs before the student lookup, so the parent simply
    doesn't have access to a random UUID. 403 is more secure than 404
    because it does not reveal whether the student exists.
    """
    fake_id = uuid4()
    client = parent_a_client
    response = await client.get(f"/api/v1/parent/children/{fake_id}/overview")

    assert response.status_code == 403
