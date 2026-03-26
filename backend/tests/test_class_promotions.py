"""
Tests for ClassPromotionService.

Covers: batch creation, preview generation, entry updates, batch execution,
status validations, tenant isolation. Uses two-engine pattern.
"""

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

async def _seed_promotion_prereqs(admin_session, tenant_id, *, num_classes=3, students_per_class=2):
    """Seed school, 2 academic years, N classes (sequence 1..N), and students.
    Returns dict with IDs."""
    school_id = uuid4()
    source_year_id = uuid4()
    target_year_id = uuid4()
    user_id = uuid4()

    await admin_session.execute(
        text("""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"S-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
    )

    for year_id, year_name, start, end in [
        (source_year_id, f"AY-src-{uuid4().hex[:6]}", date(2025, 9, 1), date(2026, 7, 31)),
        (target_year_id, f"AY-tgt-{uuid4().hex[:6]}", date(2026, 9, 1), date(2027, 7, 31)),
    ]:
        await admin_session.execute(
            text("""
                INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                    status, is_current, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                    :start, :end, 'active', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(year_id), "tid": str(tenant_id), "name": year_name,
             "start": start, "end": end},
        )

    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Promoter', 'User', 'school_admin', 'active',
                true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"promoter-{uuid4().hex[:6]}@test.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
    )

    # Create classes with sequential ordering
    class_ids = []
    for seq in range(1, num_classes + 1):
        cid = uuid4()
        await admin_session.execute(
            text("""
                INSERT INTO classes (id, tenant_id, name, level, sequence,
                    is_active, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                    'primary', :seq, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(cid), "tid": str(tenant_id),
             "name": f"Class {seq}", "seq": seq},
        )
        class_ids.append(cid)

    # Create students in each class
    student_ids = {}  # class_id -> [student_ids]
    for cid in class_ids:
        student_ids[cid] = []
        for i in range(students_per_class):
            sid = uuid4()
            await admin_session.execute(
                text("""
                    INSERT INTO students (id, tenant_id, school_id, student_id,
                        first_name, last_name, date_of_birth, gender, status,
                        class_id, created_at, updated_at)
                    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:scid AS uuid),
                        :student_id, :fn, :ln, '2012-01-01', 'male', 'active',
                        CAST(:cid AS uuid), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """),
                {
                    "id": str(sid), "tid": str(tenant_id), "scid": str(school_id),
                    "student_id": f"STU-{uuid4().hex[:8]}",
                    "fn": f"Student-{seq}-{i}", "ln": "Promo",
                    "cid": str(cid),
                },
            )
            student_ids[cid].append(sid)

    await admin_session.commit()
    return {
        "school_id": school_id,
        "source_year_id": source_year_id,
        "target_year_id": target_year_id,
        "user_id": user_id,
        "class_ids": class_ids,
        "student_ids": student_ids,
    }


# --- Tests ---


async def test_create_batch(app_session, admin_session):
    """Create promotion batch -> draft status."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_promotion_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ClassPromotionService

    svc = ClassPromotionService(app_session)
    batch = await svc.create_batch(
        tenant["id"], prereqs["school_id"],
        source_academic_year_id=prereqs["source_year_id"],
        target_academic_year_id=prereqs["target_year_id"],
        name="2025/2026 Promotion",
    )
    assert batch.status == "draft"
    assert batch.name == "2025/2026 Promotion"


async def test_create_batch_same_year_rejected(app_session, admin_session):
    """Source == target academic year -> SAME_YEAR error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_promotion_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ClassPromotionService, ClassPromotionError

    svc = ClassPromotionService(app_session)
    with pytest.raises(ClassPromotionError) as exc_info:
        await svc.create_batch(
            tenant["id"], prereqs["school_id"],
            source_academic_year_id=prereqs["source_year_id"],
            target_academic_year_id=prereqs["source_year_id"],  # Same!
            name="Bad Batch",
        )
    assert exc_info.value.code == "SAME_YEAR"


async def test_create_batch_duplicate_rejected(app_session, admin_session):
    """Duplicate batch for same year combination -> BATCH_EXISTS error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_promotion_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ClassPromotionService, ClassPromotionError

    svc = ClassPromotionService(app_session)
    await svc.create_batch(
        tenant["id"], prereqs["school_id"],
        source_academic_year_id=prereqs["source_year_id"],
        target_academic_year_id=prereqs["target_year_id"],
        name="First Batch",
    )

    with pytest.raises(ClassPromotionError) as exc_info:
        await svc.create_batch(
            tenant["id"], prereqs["school_id"],
            source_academic_year_id=prereqs["source_year_id"],
            target_academic_year_id=prereqs["target_year_id"],
            name="Duplicate Batch",
        )
    assert exc_info.value.code == "BATCH_EXISTS"


async def test_generate_preview(app_session, admin_session):
    """Preview generation creates entries for all students with default actions."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_promotion_prereqs(admin_session, tenant["id"], num_classes=3, students_per_class=2)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ClassPromotionService

    svc = ClassPromotionService(app_session)
    batch = await svc.create_batch(
        tenant["id"], prereqs["school_id"],
        source_academic_year_id=prereqs["source_year_id"],
        target_academic_year_id=prereqs["target_year_id"],
        name="Preview Test",
    )
    batch_id = batch.id

    batch = await svc.generate_preview(tenant["id"], batch_id)
    assert batch.status == "preview"
    assert batch.total_students == 6  # 3 classes x 2 students

    # Students in Class 1 and 2 should be 'promote', Class 3 (terminal) should be 'graduate'
    entries, total = await svc.get_entries(tenant["id"], batch_id)
    actions = {e.action for e in entries}
    assert "promote" in actions
    assert "graduate" in actions


async def test_preview_only_from_draft(app_session, admin_session):
    """Preview generation from non-draft batch -> INVALID_STATUS error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_promotion_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ClassPromotionService, ClassPromotionError

    svc = ClassPromotionService(app_session)
    batch = await svc.create_batch(
        tenant["id"], prereqs["school_id"],
        source_academic_year_id=prereqs["source_year_id"],
        target_academic_year_id=prereqs["target_year_id"],
        name="Status Test",
    )
    batch_id = batch.id

    # Generate preview (draft -> preview)
    await svc.generate_preview(tenant["id"], batch_id)

    # Try again (preview -> preview: invalid)
    with pytest.raises(ClassPromotionError) as exc_info:
        await svc.generate_preview(tenant["id"], batch_id)
    assert exc_info.value.code == "INVALID_STATUS"


async def test_update_entry_action(app_session, admin_session):
    """Update an entry action from promote to repeat."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_promotion_prereqs(admin_session, tenant["id"], num_classes=2, students_per_class=1)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ClassPromotionService

    svc = ClassPromotionService(app_session)
    batch = await svc.create_batch(
        tenant["id"], prereqs["school_id"],
        source_academic_year_id=prereqs["source_year_id"],
        target_academic_year_id=prereqs["target_year_id"],
        name="Update Test",
    )
    await svc.generate_preview(tenant["id"], batch.id)

    entries, _ = await svc.get_entries(tenant["id"], batch.id)
    # Find a promote entry
    promote_entry = next(e for e in entries if e.action == "promote")
    entry_id = promote_entry.id

    updated = await svc.update_entry(
        tenant["id"], entry_id,
        action="repeat",
        reason="Needs to improve",
    )
    assert updated.action == "repeat"
    assert updated.reason == "Needs to improve"


async def test_update_entry_invalid_action(app_session, admin_session):
    """Invalid action value -> INVALID_ACTION error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_promotion_prereqs(admin_session, tenant["id"], num_classes=2, students_per_class=1)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ClassPromotionService, ClassPromotionError

    svc = ClassPromotionService(app_session)
    batch = await svc.create_batch(
        tenant["id"], prereqs["school_id"],
        source_academic_year_id=prereqs["source_year_id"],
        target_academic_year_id=prereqs["target_year_id"],
        name="Invalid Action Test",
    )
    await svc.generate_preview(tenant["id"], batch.id)

    entries, _ = await svc.get_entries(tenant["id"], batch.id)
    entry_id = entries[0].id

    with pytest.raises(ClassPromotionError) as exc_info:
        await svc.update_entry(tenant["id"], entry_id, action="skip")
    assert exc_info.value.code == "INVALID_ACTION"


async def test_execute_batch(app_session, admin_session):
    """Execute batch -> students promoted/graduated, batch completed."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_promotion_prereqs(admin_session, tenant["id"], num_classes=2, students_per_class=1)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ClassPromotionService

    svc = ClassPromotionService(app_session)
    batch = await svc.create_batch(
        tenant["id"], prereqs["school_id"],
        source_academic_year_id=prereqs["source_year_id"],
        target_academic_year_id=prereqs["target_year_id"],
        name="Execute Test",
    )
    await svc.generate_preview(tenant["id"], batch.id)
    batch_id = batch.id

    batch = await svc.execute_batch(tenant["id"], batch_id, prereqs["user_id"])
    assert batch.status == "completed"
    assert batch.promoted_count + batch.graduated_count == 2

    # Verify the Class 1 student was promoted to Class 2
    class_1_students = prereqs["student_ids"][prereqs["class_ids"][0]]
    r = await app_session.execute(
        text("SELECT class_id FROM students WHERE id = CAST(:id AS uuid)"),
        {"id": str(class_1_students[0])},
    )
    new_class = r.scalar()
    assert str(new_class) == str(prereqs["class_ids"][1])  # Promoted to Class 2

    # Verify the terminal class student was graduated
    terminal_students = prereqs["student_ids"][prereqs["class_ids"][-1]]
    r = await app_session.execute(
        text("SELECT status FROM students WHERE id = CAST(:id AS uuid)"),
        {"id": str(terminal_students[0])},
    )
    assert r.scalar() == "graduated"


async def test_execute_only_preview(app_session, admin_session):
    """Execute on draft batch -> INVALID_STATUS error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_promotion_prereqs(admin_session, tenant["id"])
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ClassPromotionService, ClassPromotionError

    svc = ClassPromotionService(app_session)
    batch = await svc.create_batch(
        tenant["id"], prereqs["school_id"],
        source_academic_year_id=prereqs["source_year_id"],
        target_academic_year_id=prereqs["target_year_id"],
        name="Execute Draft Test",
    )

    with pytest.raises(ClassPromotionError) as exc_info:
        await svc.execute_batch(tenant["id"], batch.id, prereqs["user_id"])
    assert exc_info.value.code == "INVALID_STATUS"


async def test_bulk_update_entries(app_session, admin_session):
    """Bulk update entries: valid and invalid actions."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_promotion_prereqs(admin_session, tenant["id"], num_classes=2, students_per_class=2)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ClassPromotionService

    svc = ClassPromotionService(app_session)
    batch = await svc.create_batch(
        tenant["id"], prereqs["school_id"],
        source_academic_year_id=prereqs["source_year_id"],
        target_academic_year_id=prereqs["target_year_id"],
        name="Bulk Update Test",
    )
    await svc.generate_preview(tenant["id"], batch.id)

    entries, _ = await svc.get_entries(tenant["id"], batch.id)

    updates = [
        {"entry_id": str(entries[0].id), "action": "repeat", "reason": "Low grades"},
        {"entry_id": str(entries[1].id), "action": "badvalue"},  # Invalid
    ]

    result = await svc.bulk_update_entries(tenant["id"], batch.id, updates)
    assert result["succeeded"] == 1
    assert len(result["failed"]) == 1


async def test_promotion_tenant_isolation(app_session, admin_session):
    """Promotion batch from Tenant A is invisible to Tenant B."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    prereqs = await _seed_promotion_prereqs(admin_session, tenant_a["id"])
    await set_app_tenant_context(app_session, tenant_a["id"])

    from app.services.admissions import ClassPromotionService

    svc = ClassPromotionService(app_session)
    await svc.create_batch(
        tenant_a["id"], prereqs["school_id"],
        source_academic_year_id=prereqs["source_year_id"],
        target_academic_year_id=prereqs["target_year_id"],
        name="Isolation Test",
    )

    # Switch to Tenant B
    await set_app_tenant_context(app_session, tenant_b["id"])
    result = await app_session.execute(text("SELECT count(*) FROM class_promotions"))
    assert result.scalar() == 0, "Tenant B must NOT see Tenant A's promotions"
