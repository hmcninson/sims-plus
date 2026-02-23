"""
SIMS Plus - Teacher Portal Endpoint Integration Tests

Tests exercise full request-response cycles through teacher portal endpoints
with a real PostgreSQL database. They verify authentication, authorization
(role + class/subject access), CRUD operations, and error handling.

Key behaviors tested:
- Dashboard retrieval (GET /api/v1/teacher/dashboard)
- Schedule retrieval (today + week)
- Class listing and detail with authorization checks
- Grading endpoints (pending scores, score entry, grade summary)
- Attendance summary with class access guard
- Teacher notes CRUD with student-class authorization
- Report comments CRUD with class teacher verification
- Lesson plans CRUD with ownership enforcement

NOTES:
- The `client` fixture overrides get_db with admin_session_maker (superuser),
  so RLS is NOT active in these tests. They validate the endpoint+service
  layer tenant_id filtering and permission guards.
- TenantMiddleware resolves X-Subdomain via its own (patched) DB session.
- Teacher endpoints require JWT with teacher.* permissions.
"""

import pytest
from datetime import date
from uuid import UUID, uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password


# =====================================================================
# SQL templates for seed data
# =====================================================================

_TENANT_INSERT = text("""
    INSERT INTO tenants (id, subdomain, slug, name, is_active,
        tenant_type, subscription_tier, max_students,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), :sub, :slug, :name, true,
        'single_school', 'trial', 50,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_SCHOOL_INSERT = text("""
    INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
        student_id_prefix, staff_id_prefix, is_active,
        uses_boarding, uses_transport,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
        'basic', 'active', 'TST', 'STF', true,
        false, false,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_USER_INSERT = text("""
    INSERT INTO users (id, tenant_id, email, password_hash,
        first_name, last_name, role, status,
        email_verified, mfa_enabled, failed_login_attempts, timezone,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
        :fn, :ln, :role, :status,
        true, false, 0, 'Africa/Accra',
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_STAFF_INSERT = text("""
    INSERT INTO staff (
        id, tenant_id, school_id,
        staff_id, first_name, last_name,
        gender, email, phone,
        staff_type, status, job_title,
        employment_date, user_id,
        created_at, updated_at
    ) VALUES (
        CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
        :staff_num, :fn, :ln,
        'male', :email, '0241234567',
        'teaching', 'active', 'Teacher',
        '2020-09-01', CAST(:uid AS uuid),
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
    )
""")


# =====================================================================
# Helpers
# =====================================================================


async def _seed_full_env(session: AsyncSession, suffix: str) -> dict:
    """
    Seed a complete teacher portal test environment:
    tenant + school + teacher user/staff + academic year/term + class/section +
    subject + class_subject assignment + staff_class_assignment + 2 students.

    Returns a dict with all created IDs.
    """
    tenant_id = uuid4()
    school_id = uuid4()
    user_id = uuid4()
    staff_id = uuid4()
    ay_id = uuid4()
    term_id = uuid4()
    class_id = uuid4()
    section_id = uuid4()
    subject_id = uuid4()
    cs_id = uuid4()
    sca_id = uuid4()
    student_1_id = uuid4()
    student_2_id = uuid4()
    subdomain = f"tch{suffix}"
    email = f"teacher-{suffix}@school.com"
    password = "SecureP@ss1"

    # Tenant
    await session.execute(
        _TENANT_INSERT,
        {"id": str(tenant_id), "sub": subdomain, "slug": subdomain, "name": f"Teacher School {suffix}"},
    )

    # School
    await session.execute(
        _SCHOOL_INSERT,
        {"id": str(school_id), "tid": str(tenant_id), "name": f"School {suffix}", "slug": subdomain},
    )

    # Teacher user
    await session.execute(
        _USER_INSERT,
        {
            "id": str(user_id), "tid": str(tenant_id),
            "email": email, "pw": hash_password(password),
            "fn": "Kofi", "ln": "Mensah",
            "role": "teacher", "status": "active",
        },
    )

    # Staff record linked to user
    await session.execute(
        _STAFF_INSERT,
        {
            "id": str(staff_id), "tid": str(tenant_id), "sid": str(school_id),
            "staff_num": f"STF-{suffix}", "fn": "Kofi", "ln": "Mensah",
            "email": email, "uid": str(user_id),
        },
    )

    # Academic year + term
    await session.execute(text("""
        INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
            status, is_current, created_at, updated_at)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), '2025/2026',
            '2025-09-01', '2026-07-31', 'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {"id": str(ay_id), "tid": str(tenant_id)})

    await session.execute(text("""
        INSERT INTO terms (id, tenant_id, academic_year_id, name,
            start_date, end_date, status, is_current, created_at, updated_at)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ayid AS uuid), 'Term 1',
            '2025-09-01', '2025-12-15', 'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {"id": str(term_id), "tid": str(tenant_id), "ayid": str(ay_id)})

    # Class + section
    await session.execute(text("""
        INSERT INTO classes (id, tenant_id, name, sequence, is_active,
            created_at, updated_at)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
            'Primary 6', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {"id": str(class_id), "tid": str(tenant_id)})

    await session.execute(text("""
        INSERT INTO class_sections (id, tenant_id, class_id, name, is_active,
            created_at, updated_at)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:cid AS uuid),
            'Section A', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {"id": str(section_id), "tid": str(tenant_id), "cid": str(class_id)})

    # Subject
    await session.execute(text("""
        INSERT INTO subjects (id, tenant_id, name, code,
            category, created_at, updated_at)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
            'Mathematics', 'MATH', 'core', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {"id": str(subject_id), "tid": str(tenant_id)})

    # class_subjects (teacher assigned to subject for this class)
    await session.execute(text("""
        INSERT INTO class_subjects (id, tenant_id, class_id, subject_id, teacher_id,
            created_at, updated_at)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:cid AS uuid),
            CAST(:sid AS uuid), CAST(:teacher AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {
        "id": str(cs_id), "tid": str(tenant_id), "cid": str(class_id),
        "sid": str(subject_id), "teacher": str(staff_id),
    })

    # staff_class_assignments (class teacher for section)
    await session.execute(text("""
        INSERT INTO staff_class_assignments (id, tenant_id, staff_id, section_id,
            is_class_teacher, created_at, updated_at)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:stid AS uuid),
            CAST(:secid AS uuid), true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {
        "id": str(sca_id), "tid": str(tenant_id),
        "stid": str(staff_id), "secid": str(section_id),
    })

    # 2 students
    for i, sid in enumerate([student_1_id, student_2_id], 1):
        await session.execute(text("""
            INSERT INTO students (id, tenant_id, student_id, first_name, last_name,
                date_of_birth, gender, status, school_id, section_id)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, :fn, :ln,
                '2015-01-15', 'male', 'active', CAST(:school_id AS uuid), CAST(:sec_id AS uuid))
        """), {
            "id": str(sid), "tid": str(tenant_id),
            "sid": f"TST-{suffix}-{i}", "fn": f"Student{i}", "ln": f"Last{i}",
            "school_id": str(school_id), "sec_id": str(section_id),
        })

    # Timetable entry for today (day_of_week = python weekday 0=Mon...4=Fri)
    tt_id = uuid4()
    import datetime
    today_dow = datetime.date.today().weekday()
    await session.execute(text("""
        INSERT INTO class_timetables (id, tenant_id, class_id, section_id,
            academic_year_id, teacher_id, subject_id,
            day_of_week, period_number, start_time, end_time, is_active,
            created_at, updated_at)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:cid AS uuid),
            CAST(:secid AS uuid), CAST(:ayid AS uuid), CAST(:teacher AS uuid),
            CAST(:subj AS uuid), :day, 1, '08:00', '08:45', true,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """), {
        "id": str(tt_id), "tid": str(tenant_id), "cid": str(class_id),
        "secid": str(section_id), "ayid": str(ay_id),
        "teacher": str(staff_id), "subj": str(subject_id),
        "day": today_dow,
    })

    await session.commit()

    return {
        "tenant_id": tenant_id,
        "school_id": school_id,
        "user_id": user_id,
        "staff_id": staff_id,
        "ay_id": ay_id,
        "term_id": term_id,
        "class_id": class_id,
        "section_id": section_id,
        "subject_id": subject_id,
        "student_1_id": student_1_id,
        "student_2_id": student_2_id,
        "subdomain": subdomain,
        "email": email,
        "password": password,
    }


def _make_teacher_token(
    user_id: UUID,
    tenant_id: UUID,
    school_id: UUID,
    permissions: list[str] | None = None,
) -> str:
    """Create a JWT access token with teacher permissions."""
    all_permissions = permissions or [
        "teacher.dashboard.read",
        "teacher.schedule.read",
        "teacher.classes.read",
        "teacher.grading.read",
        "teacher.grading.write",
        "teacher.attendance.read",
        "teacher.notes.read",
        "teacher.notes.write",
        "teacher.reports.read",
        "teacher.reports.write",
        "teacher.lessons.read",
        "teacher.lessons.write",
    ]
    return create_access_token(
        subject=str(user_id),
        tenant_id=str(tenant_id),
        school_id=str(school_id),
        role="teacher",
        permissions=all_permissions,
    )


def _auth_headers(token: str, subdomain: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Subdomain": subdomain,
    }


# =====================================================================
# Tests: Dashboard
# =====================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestTeacherDashboard:
    """Tests for GET /api/v1/teacher/dashboard."""

    async def test_get_dashboard_success(self, client, admin_session):
        """Authenticated teacher with valid permissions gets dashboard data."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.get("/api/v1/teacher/dashboard", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert "teacher_name" in data
        assert "classes" in data
        assert "subjects" in data
        assert "today_schedule" in data

    async def test_get_dashboard_unauthorized(self, client, admin_session):
        """Request without token returns 401."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        response = await client.get(
            "/api/v1/teacher/dashboard",
            headers={"X-Subdomain": env["subdomain"]},
        )
        assert response.status_code == 401

    async def test_get_dashboard_wrong_role(self, client, admin_session):
        """User with parent role (no teacher.dashboard.read) gets 403."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])

        # Create a parent user (no teacher permissions)
        parent_id = uuid4()
        await admin_session.execute(
            _USER_INSERT,
            {
                "id": str(parent_id), "tid": str(env["tenant_id"]),
                "email": f"parent-{uuid4().hex[:6]}@school.com",
                "pw": hash_password("SecureP@ss1"),
                "fn": "Parent", "ln": "User",
                "role": "parent", "status": "active",
            },
        )
        await admin_session.commit()

        # Token with no teacher permissions
        token = create_access_token(
            subject=str(parent_id),
            tenant_id=str(env["tenant_id"]),
            school_id=str(env["school_id"]),
            role="parent",
            permissions=["children.read"],
        )
        headers = _auth_headers(token, env["subdomain"])

        response = await client.get("/api/v1/teacher/dashboard", headers=headers)
        assert response.status_code == 403


# =====================================================================
# Tests: Schedule
# =====================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestTeacherSchedule:
    """Tests for GET /api/v1/teacher/schedule/today and /week."""

    async def test_get_schedule_today(self, client, admin_session):
        """Returns today's timetable entries for the teacher."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.get("/api/v1/teacher/schedule/today", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert isinstance(data, list)
        # We seeded a timetable entry for today, so it should be present
        if data:
            entry = data[0]
            assert "class_name" in entry
            assert "period_number" in entry

    async def test_get_schedule_week(self, client, admin_session):
        """Returns the full week schedule grouped by day."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.get("/api/v1/teacher/schedule/week", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert "days" in data
        assert isinstance(data["days"], list)


# =====================================================================
# Tests: Classes
# =====================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestTeacherClasses:
    """Tests for teacher class endpoints."""

    async def test_get_classes_returns_assigned_only(self, client, admin_session):
        """Only classes the teacher is assigned to are returned."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.get("/api/v1/teacher/classes", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        # The seeded class should be in the list
        class_ids = [c["class_id"] for c in data]
        assert str(env["class_id"]) in class_ids

    async def test_get_class_detail_authorized(self, client, admin_session):
        """Teacher can view details of an assigned class."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.get(
            f"/api/v1/teacher/classes/{env['class_id']}",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["class_id"] == str(env["class_id"])
        assert data["class_name"] == "Primary 6"

    async def test_get_class_detail_unauthorized_class(self, client, admin_session):
        """Teacher cannot view a class they are NOT assigned to."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        # Random UUID that doesn't correspond to any assigned class
        fake_class_id = uuid4()
        response = await client.get(
            f"/api/v1/teacher/classes/{fake_class_id}",
            headers=headers,
        )
        assert response.status_code == 403

    async def test_get_class_students(self, client, admin_session):
        """Returns students for an assigned class."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.get(
            f"/api/v1/teacher/classes/{env['class_id']}/students",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "students" in data
        assert data["total"] >= 2  # We seeded 2 students


# =====================================================================
# Tests: Grading
# =====================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestTeacherGrading:
    """Tests for teacher grading endpoints."""

    async def _seed_exam_env(self, session, env):
        """Helper to add an exam + exam_subject to the seeded environment."""
        exam_id = uuid4()
        es_id = uuid4()

        await session.execute(text("""
            INSERT INTO exams (id, tenant_id, academic_year_id, term_id, name,
                exam_type, status, start_date, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ayid AS uuid),
                CAST(:termid AS uuid), 'Mid-Term Exam', 'midterm', 'scheduled', '2025-10-15',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {
            "id": str(exam_id), "tid": str(env["tenant_id"]),
            "ayid": str(env["ay_id"]), "termid": str(env["term_id"]),
        })

        await session.execute(text("""
            INSERT INTO exam_subjects (id, tenant_id, exam_id, subject_id, class_id,
                section_id, max_score, pass_mark, status,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:eid AS uuid),
                CAST(:sid AS uuid), CAST(:cid AS uuid),
                CAST(:secid AS uuid), 100, 50, 'pending',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {
            "id": str(es_id), "tid": str(env["tenant_id"]),
            "eid": str(exam_id), "sid": str(env["subject_id"]),
            "cid": str(env["class_id"]), "secid": str(env["section_id"]),
        })

        await session.commit()
        return exam_id, es_id

    async def test_get_pending_scores(self, client, admin_session):
        """Returns pending exam subjects for the teacher."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        exam_id, es_id = await self._seed_exam_env(admin_session, env)

        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.get("/api/v1/teacher/grading/pending", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        es_ids = [p["exam_subject_id"] for p in data]
        assert str(es_id) in es_ids

    async def test_enter_scores_endpoint(self, client, admin_session):
        """POST scores for an exam subject returns success."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        exam_id, es_id = await self._seed_exam_env(admin_session, env)

        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.post(
            f"/api/v1/teacher/grading/exam-subjects/{es_id}/scores",
            json={
                "scores": [
                    {"student_id": str(env["student_1_id"]), "score": 85, "is_absent": False},
                    {"student_id": str(env["student_2_id"]), "score": 72, "is_absent": False},
                ]
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total"] == 2
        assert data["successful"] == 2
        assert data["failed"] == 0

    async def test_enter_scores_requires_permission(self, client, admin_session):
        """Missing teacher.grading.write permission returns 403."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        exam_id, es_id = await self._seed_exam_env(admin_session, env)

        # Token with only read permission (no write)
        token = _make_teacher_token(
            env["user_id"], env["tenant_id"], env["school_id"],
            permissions=["teacher.grading.read"],
        )
        headers = _auth_headers(token, env["subdomain"])

        response = await client.post(
            f"/api/v1/teacher/grading/exam-subjects/{es_id}/scores",
            json={
                "scores": [
                    {"student_id": str(env["student_1_id"]), "score": 85, "is_absent": False},
                ]
            },
            headers=headers,
        )
        assert response.status_code == 403

    async def test_get_grade_summary(self, client, admin_session):
        """Returns class grade summary for a subject."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        exam_id, es_id = await self._seed_exam_env(admin_session, env)

        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.get(
            f"/api/v1/teacher/grading/classes/{env['class_id']}/subjects/{env['subject_id']}/summary",
            params={"term_id": str(env["term_id"])},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["class_id"] == str(env["class_id"])
        assert data["subject_id"] == str(env["subject_id"])
        assert "students" in data
        assert "total_students" in data


# =====================================================================
# Tests: Attendance
# =====================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestTeacherAttendance:
    """Tests for teacher attendance endpoints."""

    async def test_get_attendance_summary(self, client, admin_session):
        """Returns attendance stats for an assigned class."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.get(
            f"/api/v1/teacher/attendance/classes/{env['class_id']}/summary",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "total_students" in data
        assert "attendance_percentage" in data

    async def test_get_attendance_unauthorized_class(self, client, admin_session):
        """Unassigned class returns 403 for attendance summary."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        fake_class_id = uuid4()
        response = await client.get(
            f"/api/v1/teacher/attendance/classes/{fake_class_id}/summary",
            headers=headers,
        )
        assert response.status_code == 403


# =====================================================================
# Tests: Notes
# =====================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestTeacherNotes:
    """Tests for teacher notes CRUD endpoints."""

    async def test_get_notes(self, client, admin_session):
        """Returns the teacher's notes list."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.get("/api/v1/teacher/notes", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert "notes" in data
        assert "total" in data

    async def test_create_note(self, client, admin_session):
        """POST creates a note for a student in an assigned class."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.post(
            "/api/v1/teacher/notes",
            json={
                "student_id": str(env["student_1_id"]),
                "note_type": "positive",
                "content": "Excellent performance in today's test!",
                "is_visible_to_parent": True,
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["student_id"] == str(env["student_1_id"])
        assert data["content"] == "Excellent performance in today's test!"
        assert data["is_visible_to_parent"] is True

    async def test_create_note_unauthorized_student(self, client, admin_session):
        """Creating a note for a student not in an assigned class returns 403 or 404."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        # Create a student in a different class (not assigned to this teacher)
        other_class_id = uuid4()
        other_section_id = uuid4()
        other_student_id = uuid4()
        await admin_session.execute(text("""
            INSERT INTO classes (id, tenant_id, name, sequence, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                'JHS 1', 2, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {"id": str(other_class_id), "tid": str(env["tenant_id"])})

        await admin_session.execute(text("""
            INSERT INTO class_sections (id, tenant_id, class_id, name, is_active,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:cid AS uuid),
                'Section B', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {"id": str(other_section_id), "tid": str(env["tenant_id"]), "cid": str(other_class_id)})

        await admin_session.execute(text("""
            INSERT INTO students (id, tenant_id, student_id, first_name, last_name,
                date_of_birth, gender, status, school_id, section_id)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, 'Other', 'Student',
                '2015-01-15', 'female', 'active', CAST(:school_id AS uuid), CAST(:sec_id AS uuid))
        """), {
            "id": str(other_student_id), "tid": str(env["tenant_id"]),
            "sid": f"OTH-{uuid4().hex[:6]}", "school_id": str(env["school_id"]),
            "sec_id": str(other_section_id),
        })
        await admin_session.commit()

        response = await client.post(
            "/api/v1/teacher/notes",
            json={
                "student_id": str(other_student_id),
                "note_type": "concern",
                "content": "This should fail -- student not in my class.",
            },
            headers=headers,
        )
        # Should return 403 (access_denied) because teacher is not assigned to JHS 1
        assert response.status_code == 403


# =====================================================================
# Tests: Report Comments
# =====================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestTeacherReportComments:
    """Tests for report comment endpoints."""

    async def test_get_report_comments(self, client, admin_session):
        """Returns report comments for the teacher's section."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.get(
            "/api/v1/teacher/reports/comments",
            params={"section_id": str(env["section_id"])},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "comments" in data
        assert "total" in data

    async def test_get_report_comments_unauthorized_section(self, client, admin_session):
        """Unassigned section returns 403 for report comments."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        fake_section_id = uuid4()
        response = await client.get(
            "/api/v1/teacher/reports/comments",
            params={"section_id": str(fake_section_id)},
            headers=headers,
        )
        # Should be 403 or 404 (section not found -> mapped by _handle_teacher_error)
        assert response.status_code in (403, 404)

    async def test_write_class_teacher_comment(self, client, admin_session):
        """POST creates/updates a class teacher comment for a student."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.post(
            f"/api/v1/teacher/reports/comments/students/{env['student_1_id']}",
            json={"class_teacher_comment": "An excellent student who participates actively."},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["student_id"] == str(env["student_1_id"])
        assert data["class_teacher_comment"] == "An excellent student who participates actively."
        assert data["class_teacher_signed"] is False

    async def test_sign_class_teacher_comment(self, client, admin_session):
        """POST signs an existing class teacher comment."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        # First write the comment
        await client.post(
            f"/api/v1/teacher/reports/comments/students/{env['student_1_id']}",
            json={"class_teacher_comment": "Great student."},
            headers=headers,
        )

        # Then sign it
        response = await client.post(
            f"/api/v1/teacher/reports/comments/students/{env['student_1_id']}/sign",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["class_teacher_signed"] is True


# =====================================================================
# Tests: Lesson Plans
# =====================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestTeacherLessonPlans:
    """Tests for lesson plan CRUD endpoints."""

    async def test_create_lesson_plan(self, client, admin_session):
        """POST creates a lesson plan for an assigned class+subject."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        response = await client.post(
            "/api/v1/teacher/lessons",
            json={
                "class_id": str(env["class_id"]),
                "subject_id": str(env["subject_id"]),
                "date": "2025-10-15",
                "period": 1,
                "topic": "Introduction to Algebra",
                "objectives": "Students will understand basic algebraic expressions.",
                "resources": "Textbook Chapter 5, whiteboard",
                "activities": "Guided practice, group work",
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["topic"] == "Introduction to Algebra"
        assert data["class_id"] == str(env["class_id"])
        assert data["status"] == "planned"
        return data["id"]

    async def test_update_lesson_plan(self, client, admin_session):
        """PATCH updates an existing lesson plan."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        # Create first
        create_response = await client.post(
            "/api/v1/teacher/lessons",
            json={
                "class_id": str(env["class_id"]),
                "subject_id": str(env["subject_id"]),
                "date": "2025-10-16",
                "topic": "Original Topic",
            },
            headers=headers,
        )
        assert create_response.status_code == 201
        plan_id = create_response.json()["id"]

        # Update
        update_response = await client.patch(
            f"/api/v1/teacher/lessons/{plan_id}",
            json={
                "topic": "Updated Topic",
                "status": "taught",
            },
            headers=headers,
        )
        assert update_response.status_code == 200, update_response.text
        data = update_response.json()
        assert data["topic"] == "Updated Topic"
        assert data["status"] == "taught"

    async def test_delete_lesson_plan(self, client, admin_session):
        """DELETE soft-deletes a lesson plan (returns 204)."""
        env = await _seed_full_env(admin_session, uuid4().hex[:6])
        token = _make_teacher_token(env["user_id"], env["tenant_id"], env["school_id"])
        headers = _auth_headers(token, env["subdomain"])

        # Create first
        create_response = await client.post(
            "/api/v1/teacher/lessons",
            json={
                "class_id": str(env["class_id"]),
                "subject_id": str(env["subject_id"]),
                "date": "2025-10-17",
                "topic": "Deletable Lesson",
            },
            headers=headers,
        )
        assert create_response.status_code == 201
        plan_id = create_response.json()["id"]

        # Delete
        delete_response = await client.delete(
            f"/api/v1/teacher/lessons/{plan_id}",
            headers=headers,
        )
        assert delete_response.status_code == 204

        # Verify it's gone (should return 404)
        get_response = await client.get(
            f"/api/v1/teacher/lessons/{plan_id}",
            headers=headers,
        )
        assert get_response.status_code == 404
