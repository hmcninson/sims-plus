"""
Tests for Sprint 17-18 Parent Multi-School Display.

Covers:
1. ChildSummary schema includes school_name and school_id fields
2. ParentService.get_my_children() loads school relationship for chain tenants
3. ParentService.get_child_detail() returns school_id and school_name
"""

import pytest
import pytest_asyncio
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.parent import ChildSummary, ChildDetail
from app.services.parent.parent_service import ParentService

from tests.conftest import (
    admin_session_maker,
    app_session_maker,
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)


# ==========================
# Schema Tests (no DB needed)
# ==========================

class TestChildSummarySchema:
    """ChildSummary schema includes school context fields."""

    def test_child_summary_has_school_id_field(self):
        """ChildSummary schema has school_id field."""
        data = {
            "id": str(uuid4()),
            "first_name": "Ama",
            "last_name": "Mensah",
            "school_id": str(uuid4()),
            "school_name": "Presec Campus A",
        }
        summary = ChildSummary(**data)
        assert summary.school_id is not None
        assert summary.school_name == "Presec Campus A"

    def test_child_summary_school_fields_optional(self):
        """school_id and school_name default to None (backward compat)."""
        data = {
            "id": str(uuid4()),
            "first_name": "Ama",
            "last_name": "Mensah",
        }
        summary = ChildSummary(**data)
        assert summary.school_id is None
        assert summary.school_name is None

    def test_child_detail_inherits_school_fields(self):
        """ChildDetail (extends ChildSummary) also has school fields."""
        data = {
            "id": str(uuid4()),
            "first_name": "Kofi",
            "last_name": "Owusu",
            "school_id": str(uuid4()),
            "school_name": "Branch School",
        }
        detail = ChildDetail(**data)
        assert detail.school_name == "Branch School"


# ==========================
# Service-Level Tests (DB required)
# ==========================

@pytest.fixture
async def chain_tenant_with_children(admin_session: AsyncSession):
    """Seed a chain tenant with two schools and a parent linked to children
    in both schools."""
    tenant = await create_test_tenant(admin_session, subdomain=f"chain-{uuid4().hex[:8]}")
    tid = str(tenant["id"])

    # Create two schools
    school_a_id = str(uuid4())
    school_b_id = str(uuid4())
    for sid, name in [(school_a_id, "School A"), (school_b_id, "School B")]:
        await admin_session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, school_type, status, is_active,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'basic', 'active', true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": sid, "tid": tid, "name": name, "slug": name.lower().replace(" ", "-")},
        )

    # Create parent user (email will be used for guardian matching)
    parent_email = f"parent-{uuid4().hex[:8]}@test.com"
    parent_user = await create_test_user(admin_session, tenant["id"], email=parent_email)

    # Create guardian with same email (phone is NOT NULL)
    guardian_id = str(uuid4())
    await admin_session.execute(
        text("""
            INSERT INTO guardians (id, tenant_id, email, first_name, last_name,
                phone, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, 'Parent', 'User',
                '0241234567', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": guardian_id, "tid": tid, "email": parent_email},
    )

    # Create two students in different schools
    # Students require: date_of_birth (NOT NULL), gender (NOT NULL)
    student_a_id = str(uuid4())
    student_b_id = str(uuid4())
    for s_id, school_sid, s_name, s_sid in [
        (student_a_id, school_a_id, "Ama", "STD-A-001"),
        (student_b_id, school_b_id, "Kofi", "STD-B-001"),
    ]:
        await admin_session.execute(
            text("""
                INSERT INTO students (id, tenant_id, school_id, student_id,
                    first_name, last_name, date_of_birth, gender, status,
                    created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:school_id AS uuid),
                    :student_id, :first_name, 'Student', '2015-03-15', 'male', 'active',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": s_id, "tid": tid, "school_id": school_sid,
                "student_id": s_sid, "first_name": s_name,
            },
        )

    # Link guardian to both students (DB column is "relationship")
    for s_id in [student_a_id, student_b_id]:
        await admin_session.execute(
            text("""
                INSERT INTO student_guardians (id, tenant_id, student_id, guardian_id,
                    relationship, is_primary, created_at, updated_at)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    CAST(:gid AS uuid), 'father', true,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {"id": str(uuid4()), "tid": tid, "sid": s_id, "gid": guardian_id},
        )

    await admin_session.commit()

    return {
        "tenant_id": tenant["id"],
        "parent_user_id": parent_user["id"],
        "school_a_id": school_a_id,
        "school_b_id": school_b_id,
        "student_a_id": student_a_id,
        "student_b_id": student_b_id,
    }


@pytest.mark.asyncio
async def test_get_my_children_includes_school_info(
    app_session: AsyncSession,
    chain_tenant_with_children: dict,
):
    """ParentService.get_my_children loads school relationship so
    ChildSummary can include school_name/school_id."""
    data = chain_tenant_with_children
    await set_app_tenant_context(app_session, data["tenant_id"])

    service = ParentService(app_session)
    children = await service.get_my_children(
        user_id=data["parent_user_id"],
        tenant_id=data["tenant_id"],
    )

    assert len(children) == 2

    # Each student should have a school loaded (via selectinload)
    school_ids = set()
    for child in children:
        assert child.school_id is not None
        # Access the school relationship -- should NOT raise (was loaded)
        assert child.school is not None
        assert child.school.name in ("School A", "School B")
        school_ids.add(str(child.school_id))

    # Students are in different schools
    assert data["school_a_id"] in school_ids
    assert data["school_b_id"] in school_ids


@pytest.mark.asyncio
async def test_get_child_detail_includes_school_name(
    app_session: AsyncSession,
    chain_tenant_with_children: dict,
):
    """ParentService.get_child_detail returns school_id and school_name."""
    data = chain_tenant_with_children
    await set_app_tenant_context(app_session, data["tenant_id"])

    service = ParentService(app_session)
    detail = await service.get_child_detail(
        user_id=data["parent_user_id"],
        student_id=data["student_a_id"],
        tenant_id=data["tenant_id"],
    )

    assert detail["school_id"] is not None
    assert detail["school_name"] == "School A"
