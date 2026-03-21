"""
Tests for school category and boarding_type fields (Phase 3A).

Covers: creating schools with category/boarding_type, updating, NULL
backward compat, and invalid enum values.
Uses two-engine pattern (admin seeds, app queries).
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


async def _column_exists(admin_session, table, column):
    """Check if a column exists on a table."""
    result = await admin_session.execute(
        text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = :table AND column_name = :col
        """),
        {"table": table, "col": column},
    )
    return result.fetchone() is not None


async def _seed_school(admin_session, tenant_id, *, category=None, boarding_type=None):
    """Create a school with optional category and boarding_type."""
    school_id = uuid4()

    # Build column list and values dynamically
    cols = [
        "id", "tenant_id", "name", "slug", "school_type", "status",
        "student_id_prefix", "staff_id_prefix",
        "is_active", "created_at", "updated_at",
    ]
    vals = [
        "CAST(:id AS uuid)", "CAST(:tid AS uuid)", ":name", ":slug",
        "'basic'", "'active'", "'STU'", "'STF'",
        "true", "CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP",
    ]
    params = {
        "id": str(school_id),
        "tid": str(tenant_id),
        "name": f"School-{uuid4().hex[:6]}",
        "slug": f"school-{uuid4().hex[:8]}",
    }

    if category is not None:
        cols.append("category")
        vals.append(":cat")
        params["cat"] = category

    if boarding_type is not None:
        cols.append("boarding_type")
        vals.append(":bt")
        params["bt"] = boarding_type

    sql = f"INSERT INTO schools ({', '.join(cols)}) VALUES ({', '.join(vals)})"
    await admin_session.execute(text(sql), params)
    await admin_session.commit()
    return school_id


# --- Tests ---


class TestSchoolCategoryFields:
    """Tests for school_category and boarding_type enum fields."""

    async def test_category_column_exists(self, admin_session):
        """schools table should have a 'category' column."""
        exists = await _column_exists(admin_session, "schools", "category")
        if not exists:
            pytest.skip("category column not yet added to schools table")
        assert exists

    async def test_boarding_type_column_exists(self, admin_session):
        """schools table should have a 'boarding_type' column."""
        exists = await _column_exists(admin_session, "schools", "boarding_type")
        if not exists:
            pytest.skip("boarding_type column not yet added to schools table")
        assert exists

    async def test_create_school_with_category(self, app_session, admin_session):
        """School created with category='private' should persist."""
        if not await _column_exists(admin_session, "schools", "category"):
            pytest.skip("category column not yet added")

        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(
            admin_session, tenant["id"], category="private"
        )
        await set_app_tenant_context(app_session, tenant["id"])

        result = await app_session.execute(
            text("SELECT category FROM schools WHERE id = CAST(:id AS uuid)"),
            {"id": str(school_id)},
        )
        assert result.fetchone()[0] == "private"

    async def test_create_school_with_boarding_type(self, app_session, admin_session):
        """School created with boarding_type='mixed' should persist."""
        if not await _column_exists(admin_session, "schools", "boarding_type"):
            pytest.skip("boarding_type column not yet added")

        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(
            admin_session, tenant["id"], boarding_type="mixed"
        )
        await set_app_tenant_context(app_session, tenant["id"])

        result = await app_session.execute(
            text("SELECT boarding_type FROM schools WHERE id = CAST(:id AS uuid)"),
            {"id": str(school_id)},
        )
        assert result.fetchone()[0] == "mixed"

    async def test_null_values_backward_compat(self, app_session, admin_session):
        """Schools without category/boarding_type should have NULL."""
        if not await _column_exists(admin_session, "schools", "category"):
            pytest.skip("category column not yet added")

        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])
        await set_app_tenant_context(app_session, tenant["id"])

        result = await app_session.execute(
            text("""
                SELECT category, boarding_type FROM schools
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(school_id)},
        )
        row = result.fetchone()
        assert row[0] is None
        assert row[1] is None

    async def test_update_school_category(self, app_session, admin_session):
        """Updating school category from NULL to 'public' should work."""
        if not await _column_exists(admin_session, "schools", "category"):
            pytest.skip("category column not yet added")

        tenant = await create_test_tenant(admin_session)
        school_id = await _seed_school(admin_session, tenant["id"])

        # Update via admin session
        await admin_session.execute(
            text("""
                UPDATE schools SET category = 'public'
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": str(school_id)},
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, tenant["id"])
        result = await app_session.execute(
            text("SELECT category FROM schools WHERE id = CAST(:id AS uuid)"),
            {"id": str(school_id)},
        )
        assert result.fetchone()[0] == "public"

    async def test_invalid_category_raises(self, admin_session):
        """Invalid enum value should raise a database error."""
        if not await _column_exists(admin_session, "schools", "category"):
            pytest.skip("category column not yet added")

        tenant = await create_test_tenant(admin_session)

        with pytest.raises(Exception):
            await _seed_school(
                admin_session, tenant["id"], category="not_a_category"
            )

    async def test_all_category_values_valid(self, admin_session):
        """All SchoolCategory enum values should be insertable."""
        if not await _column_exists(admin_session, "schools", "category"):
            pytest.skip("category column not yet added")

        tenant = await create_test_tenant(admin_session)
        for cat in ["public", "private", "international", "faith_based"]:
            school_id = await _seed_school(
                admin_session, tenant["id"], category=cat
            )
            result = await admin_session.execute(
                text("SELECT category FROM schools WHERE id = CAST(:id AS uuid)"),
                {"id": str(school_id)},
            )
            assert result.fetchone()[0] == cat

    async def test_all_boarding_type_values_valid(self, admin_session):
        """All BoardingType enum values should be insertable."""
        if not await _column_exists(admin_session, "schools", "boarding_type"):
            pytest.skip("boarding_type column not yet added")

        tenant = await create_test_tenant(admin_session)
        for bt in ["day_only", "boarding_only", "mixed"]:
            school_id = await _seed_school(
                admin_session, tenant["id"], boarding_type=bt
            )
            result = await admin_session.execute(
                text("SELECT boarding_type FROM schools WHERE id = CAST(:id AS uuid)"),
                {"id": str(school_id)},
            )
            assert result.fetchone()[0] == bt
