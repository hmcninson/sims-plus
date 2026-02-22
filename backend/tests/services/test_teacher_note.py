"""
SIMS Plus - Teacher Note Service Tests

Tests for TeacherNoteService CRUD lifecycle:
- Create, update, delete note
- Only creating teacher can update their note
- Parent can only see notes with is_visible_to_parent=True
- Acknowledge note with IDOR check (note must belong to student)
- Acknowledge is idempotent
- Soft-deleted notes excluded
- Tenant isolation at service level
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.parent import (
    TeacherNoteCreate,
    TeacherNoteUpdate,
    NoteTypeEnum,
)
from app.services.teacher_note import (
    TeacherNoteService,
    TeacherNoteServiceError,
)
from tests.conftest import (
    admin_session_maker,
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)


# =====================================================================
# Fixtures
# =====================================================================


@pytest_asyncio.fixture
async def note_env(admin_session: AsyncSession, app_session: AsyncSession):
    """Seed a tenant + school + 2 teachers + 2 students for note tests."""
    suffix = uuid4().hex[:8]
    tenant = await create_test_tenant(admin_session, subdomain=f"note-{suffix}")
    tenant_id = tenant["id"]

    school_id = uuid4()
    await admin_session.execute(text("""
        INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Note School', :slug, 'NTS', 'basic')
    """), {"id": str(school_id), "tid": str(tenant_id), "slug": f"note-{suffix}"})

    # Teacher A
    teacher_a = await create_test_user(admin_session, tenant_id, email=f"teacher-a-{suffix}@test.com")
    # Teacher B (different teacher)
    teacher_b = await create_test_user(admin_session, tenant_id, email=f"teacher-b-{suffix}@test.com")

    # Students
    student_1_id = uuid4()
    student_2_id = uuid4()
    student_sql = text("""
        INSERT INTO students (id, tenant_id, student_id, first_name, last_name,
            date_of_birth, gender, status, school_id)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, :fn, :ln,
            '2015-01-15', 'male', 'active', CAST(:school_id AS uuid))
    """)
    await admin_session.execute(student_sql, {
        "id": str(student_1_id), "tid": str(tenant_id),
        "sid": f"NS1-{suffix}", "fn": "NoteStudent1", "ln": "A", "school_id": str(school_id),
    })
    await admin_session.execute(student_sql, {
        "id": str(student_2_id), "tid": str(tenant_id),
        "sid": f"NS2-{suffix}", "fn": "NoteStudent2", "ln": "B", "school_id": str(school_id),
    })

    # CRITICAL: commit so app_session (separate connection) can see the data
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant_id)

    yield {
        "tenant_id": tenant_id,
        "school_id": school_id,
        "teacher_a_id": teacher_a["id"],
        "teacher_b_id": teacher_b["id"],
        "student_1_id": student_1_id,
        "student_2_id": student_2_id,
        "app_session": app_session,
    }

    # CRITICAL: rollback app_session to release any row locks before cleanup
    await app_session.rollback()

    # Cleanup: remove seeded data (resilient to connection drops during long runs)
    try:
        async with admin_session_maker() as cleanup:
            for table in ["teacher_notes", "announcements", "parent_notification_preferences",
                           "students", "users", "schools"]:
                await cleanup.execute(
                    text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                    {"tid": str(tenant_id)},
                )
            await cleanup.execute(
                text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
                {"tid": str(tenant_id)},
            )
            await cleanup.commit()
    except Exception:
        pass  # Best-effort cleanup; test DB is ephemeral


# =====================================================================
# Tests: Create
# =====================================================================


@pytest.mark.asyncio
async def test_create_note(note_env):
    """Creating a note should persist with correct fields."""
    env = note_env
    service = TeacherNoteService(env["app_session"])

    data = TeacherNoteCreate(
        student_id=env["student_1_id"],
        note_type=NoteTypeEnum.POSITIVE,
        content="Excellent participation in class today!",
        is_visible_to_parent=True,
    )

    note = await service.create_note(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        teacher_id=env["teacher_a_id"],
        data=data,
    )

    assert note.id is not None
    assert note.student_id == env["student_1_id"]
    assert note.teacher_id == env["teacher_a_id"]
    assert note.content == "Excellent participation in class today!"
    assert note.is_visible_to_parent is True
    assert note.parent_acknowledged is False


@pytest.mark.asyncio
async def test_create_note_for_nonexistent_student_fails(note_env):
    """Creating a note for a nonexistent student should raise an error."""
    env = note_env
    service = TeacherNoteService(env["app_session"])

    data = TeacherNoteCreate(
        student_id=uuid4(),
        note_type=NoteTypeEnum.CONCERN,
        content="Should fail.",
    )

    with pytest.raises(TeacherNoteServiceError) as exc_info:
        await service.create_note(
            tenant_id=env["tenant_id"],
            school_id=env["school_id"],
            teacher_id=env["teacher_a_id"],
            data=data,
        )

    assert exc_info.value.code == "student_not_found"


# =====================================================================
# Tests: Update
# =====================================================================


@pytest.mark.asyncio
async def test_update_own_note(note_env):
    """Teacher A should be able to update their own note."""
    env = note_env
    service = TeacherNoteService(env["app_session"])

    create_data = TeacherNoteCreate(
        student_id=env["student_1_id"],
        note_type=NoteTypeEnum.INFORMATION,
        content="Original content.",
    )
    note = await service.create_note(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        teacher_id=env["teacher_a_id"],
        data=create_data,
    )

    update_data = TeacherNoteUpdate(content="Updated content.")
    updated = await service.update_note(
        tenant_id=env["tenant_id"],
        note_id=note.id,
        teacher_id=env["teacher_a_id"],
        data=update_data,
    )

    assert updated.content == "Updated content."


@pytest.mark.asyncio
async def test_other_teacher_cannot_update_note(note_env):
    """Teacher B should NOT be able to update Teacher A's note."""
    env = note_env
    service = TeacherNoteService(env["app_session"])

    create_data = TeacherNoteCreate(
        student_id=env["student_1_id"],
        note_type=NoteTypeEnum.CONCERN,
        content="Teacher A's note.",
    )
    note = await service.create_note(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        teacher_id=env["teacher_a_id"],
        data=create_data,
    )

    update_data = TeacherNoteUpdate(content="Teacher B tries to edit.")
    with pytest.raises(TeacherNoteServiceError) as exc_info:
        await service.update_note(
            tenant_id=env["tenant_id"],
            note_id=note.id,
            teacher_id=env["teacher_b_id"],
            data=update_data,
        )

    assert exc_info.value.code == "forbidden"


# =====================================================================
# Tests: Delete
# =====================================================================


@pytest.mark.asyncio
async def test_delete_own_note(note_env):
    """Teacher A can delete their own note."""
    env = note_env
    service = TeacherNoteService(env["app_session"])

    data = TeacherNoteCreate(
        student_id=env["student_1_id"],
        note_type=NoteTypeEnum.POSITIVE,
        content="To be deleted.",
    )
    note = await service.create_note(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        teacher_id=env["teacher_a_id"],
        data=data,
    )

    await service.delete_note(
        tenant_id=env["tenant_id"],
        note_id=note.id,
        requesting_user_id=env["teacher_a_id"],
    )

    with pytest.raises(TeacherNoteServiceError) as exc_info:
        await service.get_note(env["tenant_id"], note.id)

    assert exc_info.value.code == "not_found"


@pytest.mark.asyncio
async def test_other_teacher_cannot_delete_note(note_env):
    """Teacher B cannot delete Teacher A's note (unless admin)."""
    env = note_env
    service = TeacherNoteService(env["app_session"])

    data = TeacherNoteCreate(
        student_id=env["student_1_id"],
        note_type=NoteTypeEnum.CONCERN,
        content="Protected note.",
    )
    note = await service.create_note(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        teacher_id=env["teacher_a_id"],
        data=data,
    )

    with pytest.raises(TeacherNoteServiceError) as exc_info:
        await service.delete_note(
            tenant_id=env["tenant_id"],
            note_id=note.id,
            requesting_user_id=env["teacher_b_id"],
            is_admin=False,
        )

    assert exc_info.value.code == "forbidden"


@pytest.mark.asyncio
async def test_admin_can_delete_any_note(note_env):
    """An admin (is_admin=True) can delete any teacher's note."""
    env = note_env
    service = TeacherNoteService(env["app_session"])

    data = TeacherNoteCreate(
        student_id=env["student_1_id"],
        note_type=NoteTypeEnum.INFORMATION,
        content="Admin deletable.",
    )
    note = await service.create_note(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        teacher_id=env["teacher_a_id"],
        data=data,
    )

    # Teacher B acts as admin
    await service.delete_note(
        tenant_id=env["tenant_id"],
        note_id=note.id,
        requesting_user_id=env["teacher_b_id"],
        is_admin=True,
    )

    with pytest.raises(TeacherNoteServiceError):
        await service.get_note(env["tenant_id"], note.id)


# =====================================================================
# Tests: Parent visibility
# =====================================================================


@pytest.mark.asyncio
async def test_list_notes_for_parent_excludes_hidden_notes(note_env):
    """list_notes_for_parent should only return notes with is_visible_to_parent=True."""
    env = note_env
    service = TeacherNoteService(env["app_session"])

    # Create visible note
    visible_data = TeacherNoteCreate(
        student_id=env["student_1_id"],
        note_type=NoteTypeEnum.POSITIVE,
        content="Visible to parent.",
        is_visible_to_parent=True,
    )
    await service.create_note(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        teacher_id=env["teacher_a_id"],
        data=visible_data,
    )

    # Create hidden note
    hidden_data = TeacherNoteCreate(
        student_id=env["student_1_id"],
        note_type=NoteTypeEnum.CONCERN,
        content="Internal only.",
        is_visible_to_parent=False,
    )
    await service.create_note(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        teacher_id=env["teacher_a_id"],
        data=hidden_data,
    )

    result = await service.list_notes_for_parent(
        tenant_id=env["tenant_id"],
        student_id=env["student_1_id"],
    )

    contents = [n.content for n in result["items"]]
    assert "Visible to parent." in contents
    assert "Internal only." not in contents


# =====================================================================
# Tests: Acknowledge
# =====================================================================


@pytest.mark.asyncio
async def test_acknowledge_note(note_env):
    """Acknowledging a visible note should set parent_acknowledged=True."""
    env = note_env
    service = TeacherNoteService(env["app_session"])

    data = TeacherNoteCreate(
        student_id=env["student_1_id"],
        note_type=NoteTypeEnum.ACTION_REQUIRED,
        content="Please sign permission slip.",
        is_visible_to_parent=True,
    )
    note = await service.create_note(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        teacher_id=env["teacher_a_id"],
        data=data,
    )
    assert note.parent_acknowledged is False

    acked = await service.acknowledge_note(
        tenant_id=env["tenant_id"],
        note_id=note.id,
        student_id=env["student_1_id"],
    )

    assert acked.parent_acknowledged is True
    assert acked.parent_acknowledged_at is not None


@pytest.mark.asyncio
async def test_acknowledge_is_idempotent(note_env):
    """Acknowledging the same note twice should succeed without error."""
    env = note_env
    service = TeacherNoteService(env["app_session"])

    data = TeacherNoteCreate(
        student_id=env["student_1_id"],
        note_type=NoteTypeEnum.POSITIVE,
        content="Idempotent ack test.",
        is_visible_to_parent=True,
    )
    note = await service.create_note(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        teacher_id=env["teacher_a_id"],
        data=data,
    )

    ack1 = await service.acknowledge_note(env["tenant_id"], note.id, env["student_1_id"])
    ack2 = await service.acknowledge_note(env["tenant_id"], note.id, env["student_1_id"])

    assert ack1.parent_acknowledged is True
    assert ack2.parent_acknowledged is True


@pytest.mark.asyncio
async def test_acknowledge_note_idor_check(note_env):
    """Acknowledging a note with the wrong student_id should fail (IDOR prevention)."""
    env = note_env
    service = TeacherNoteService(env["app_session"])

    # Note belongs to student_1
    data = TeacherNoteCreate(
        student_id=env["student_1_id"],
        note_type=NoteTypeEnum.INFORMATION,
        content="IDOR test note.",
        is_visible_to_parent=True,
    )
    note = await service.create_note(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        teacher_id=env["teacher_a_id"],
        data=data,
    )

    # Try to acknowledge with student_2's ID (IDOR attempt)
    with pytest.raises(TeacherNoteServiceError) as exc_info:
        await service.acknowledge_note(
            tenant_id=env["tenant_id"],
            note_id=note.id,
            student_id=env["student_2_id"],
        )

    assert exc_info.value.code == "not_found"


@pytest.mark.asyncio
async def test_acknowledge_hidden_note_fails(note_env):
    """Acknowledging a note that is not visible to parents should fail."""
    env = note_env
    service = TeacherNoteService(env["app_session"])

    data = TeacherNoteCreate(
        student_id=env["student_1_id"],
        note_type=NoteTypeEnum.CONCERN,
        content="Internal note, not parent-visible.",
        is_visible_to_parent=False,
    )
    note = await service.create_note(
        tenant_id=env["tenant_id"],
        school_id=env["school_id"],
        teacher_id=env["teacher_a_id"],
        data=data,
    )

    with pytest.raises(TeacherNoteServiceError) as exc_info:
        await service.acknowledge_note(
            tenant_id=env["tenant_id"],
            note_id=note.id,
            student_id=env["student_1_id"],
        )

    assert exc_info.value.code == "not_visible"


# =====================================================================
# Tests: Unacknowledged count
# =====================================================================


@pytest.mark.asyncio
async def test_unacknowledged_count(note_env):
    """get_unacknowledged_count should count visible, unacknowledged notes."""
    env = note_env
    service = TeacherNoteService(env["app_session"])

    # Create 2 visible notes
    for content in ["Note 1", "Note 2"]:
        data = TeacherNoteCreate(
            student_id=env["student_1_id"],
            note_type=NoteTypeEnum.INFORMATION,
            content=content,
            is_visible_to_parent=True,
        )
        await service.create_note(
            tenant_id=env["tenant_id"],
            school_id=env["school_id"],
            teacher_id=env["teacher_a_id"],
            data=data,
        )

    count = await service.get_unacknowledged_count(
        tenant_id=env["tenant_id"],
        student_id=env["student_1_id"],
    )

    assert count >= 2  # Could be more from other tests, but at least these 2


# =====================================================================
# Tests: Tenant isolation
# =====================================================================


@pytest.mark.asyncio
async def test_note_not_visible_across_tenants(
    admin_session: AsyncSession, app_session: AsyncSession
):
    """A note from tenant A should NOT be accessible via tenant B."""
    suffix = uuid4().hex[:8]
    tenant_a = await create_test_tenant(admin_session, subdomain=f"nta-{suffix}")
    tenant_b = await create_test_tenant(admin_session, subdomain=f"ntb-{suffix}")

    # School + teacher + student in tenant A
    school_a_id = uuid4()
    student_a_id = uuid4()
    await admin_session.execute(text("""
        INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'A', :slug, 'A', 'basic')
    """), {"id": str(school_a_id), "tid": str(tenant_a["id"]), "slug": f"a-{suffix}"})

    teacher_a = await create_test_user(admin_session, tenant_a["id"])

    await admin_session.execute(text("""
        INSERT INTO students (id, tenant_id, student_id, first_name, last_name,
            date_of_birth, gender, status, school_id)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, 'SA', 'T',
            '2015-01-01', 'male', 'active', CAST(:school_id AS uuid))
    """), {"id": str(student_a_id), "tid": str(tenant_a["id"]),
           "sid": f"SA-{suffix}", "school_id": str(school_a_id)})

    # CRITICAL: commit so app_session can see the data
    await admin_session.commit()

    try:
        # Create note in tenant A
        await set_app_tenant_context(app_session, tenant_a["id"])
        service = TeacherNoteService(app_session)

        data = TeacherNoteCreate(
            student_id=student_a_id,
            note_type=NoteTypeEnum.POSITIVE,
            content="Tenant A only.",
            is_visible_to_parent=True,
        )
        note = await service.create_note(
            tenant_id=tenant_a["id"],
            school_id=school_a_id,
            teacher_id=teacher_a["id"],
            data=data,
        )
        note_id = note.id

        # Switch to tenant B -- note should not be findable
        await set_app_tenant_context(app_session, tenant_b["id"])
        service_b = TeacherNoteService(app_session)

        with pytest.raises(TeacherNoteServiceError) as exc_info:
            await service_b.get_note(tenant_b["id"], note_id)

        assert exc_info.value.code == "not_found"
    finally:
        # CRITICAL: rollback app_session to release row locks before cleanup
        await app_session.rollback()

        # Cleanup committed data (resilient to connection drops during long runs)
        try:
            async with admin_session_maker() as cleanup:
                for tid in [str(tenant_a["id"]), str(tenant_b["id"])]:
                    for table in ["teacher_notes", "students", "users", "schools"]:
                        await cleanup.execute(
                            text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                            {"tid": tid},
                        )
                    await cleanup.execute(
                        text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
                        {"tid": tid},
                    )
                await cleanup.commit()
        except Exception:
            pass  # Best-effort cleanup; test DB is ephemeral
