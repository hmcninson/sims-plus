"""
Tests for email_log RLS policies.

Uses the two-engine pattern:
- admin_engine (postgres superuser) inserts data bypassing RLS
- app_engine (sims_app_user) reads data with RLS enforced

Verifies that email_log rows are tenant-isolated and that the table
is properly listed in TENANT_SCOPED_TABLES with RLS enabled.
"""

import pytest
import pytest_asyncio
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    TENANT_SCOPED_TABLES,
    admin_session_maker,
    app_session_maker,
    create_test_tenant,
    set_app_tenant_context,
    clear_app_tenant_context,
)


# ===========================
# Fixtures
# ===========================


@pytest_asyncio.fixture
async def rls_data(admin_session):
    """
    Seed two tenants with email_log entries for RLS testing.

    Tenant A has 2 emails, Tenant B has 1 email.
    """
    tenant_a = await create_test_tenant(admin_session, subdomain=f"rls-eml-a-{uuid4().hex[:8]}")
    tenant_b = await create_test_tenant(admin_session, subdomain=f"rls-eml-b-{uuid4().hex[:8]}")
    tenant_a_id = tenant_a["id"]
    tenant_b_id = tenant_b["id"]

    school_a_id = uuid4()
    school_b_id = uuid4()

    # Schools
    for school_id, tid, name, slug in [
        (school_a_id, tenant_a_id, "RLS School A", f"rls-a-{uuid4().hex[:8]}"),
        (school_b_id, tenant_b_id, "RLS School B", f"rls-b-{uuid4().hex[:8]}"),
    ]:
        await admin_session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'RL', 'basic')
            """),
            {"id": str(school_id), "tid": str(tid), "name": name, "slug": slug},
        )

    # Email log entries for Tenant A
    email_a1_id = uuid4()
    email_a2_id = uuid4()
    for eid, recipient in [(email_a1_id, "parent-a1@test.com"), (email_a2_id, "parent-a2@test.com")]:
        await admin_session.execute(
            text("""
                INSERT INTO email_log (id, tenant_id, school_id, recipient_email, subject, body, status)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    :email, 'Test Subject A', 'Test Body A', 'sent')
            """),
            {"id": str(eid), "tid": str(tenant_a_id), "sid": str(school_a_id), "email": recipient},
        )

    # Email log entries for Tenant B
    email_b1_id = uuid4()
    await admin_session.execute(
        text("""
            INSERT INTO email_log (id, tenant_id, school_id, recipient_email, subject, body, status)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :email, 'Test Subject B', 'Test Body B', 'sent')
        """),
        {"id": str(email_b1_id), "tid": str(tenant_b_id), "sid": str(school_b_id), "email": "parent-b1@test.com"},
    )

    await admin_session.commit()

    yield {
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "school_a_id": school_a_id,
        "school_b_id": school_b_id,
        "email_a1_id": email_a1_id,
        "email_a2_id": email_a2_id,
        "email_b1_id": email_b1_id,
    }

    # Cleanup
    async with admin_session_maker() as cleanup_sess:
        for tid in [str(tenant_a_id), str(tenant_b_id)]:
            for table in ["email_log", "schools"]:
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
async def test_email_log_rls_tenant_a_sees_own_data(rls_data, app_session):
    """With Tenant A context, only Tenant A's email_log rows are visible."""
    d = rls_data
    await set_app_tenant_context(app_session, d["tenant_a_id"])

    result = await app_session.execute(text("SELECT id FROM email_log"))
    rows = result.fetchall()

    visible_ids = {str(row[0]) for row in rows}
    assert str(d["email_a1_id"]) in visible_ids
    assert str(d["email_a2_id"]) in visible_ids
    assert str(d["email_b1_id"]) not in visible_ids

    await clear_app_tenant_context(app_session)


@pytest.mark.asyncio
async def test_email_log_rls_tenant_b_sees_own_data(rls_data, app_session):
    """With Tenant B context, only Tenant B's email_log rows are visible."""
    d = rls_data
    await set_app_tenant_context(app_session, d["tenant_b_id"])

    result = await app_session.execute(text("SELECT id FROM email_log"))
    rows = result.fetchall()

    visible_ids = {str(row[0]) for row in rows}
    assert str(d["email_b1_id"]) in visible_ids
    assert str(d["email_a1_id"]) not in visible_ids
    assert str(d["email_a2_id"]) not in visible_ids

    await clear_app_tenant_context(app_session)


@pytest.mark.asyncio
async def test_email_log_rls_insert_wrong_tenant_rejected(rls_data, app_session):
    """INSERT into email_log with a tenant_id different from the context should be rejected."""
    d = rls_data

    # Set context to Tenant A
    await set_app_tenant_context(app_session, d["tenant_a_id"])

    # Try to insert a row with Tenant B's ID -- RLS WITH CHECK should reject
    with pytest.raises(Exception):
        await app_session.execute(
            text("""
                INSERT INTO email_log (id, tenant_id, school_id, recipient_email, subject, body, status)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                    'rls-inject@test.com', 'Injected', 'Body', 'sent')
            """),
            {
                "id": str(uuid4()),
                "tid": str(d["tenant_b_id"]),  # wrong tenant
                "sid": str(d["school_b_id"]),
            },
        )
        await app_session.flush()

    await app_session.rollback()
    await clear_app_tenant_context(app_session)


@pytest.mark.asyncio
async def test_email_log_in_tenant_scoped_tables_and_rls_enabled(admin_session):
    """email_log must be in TENANT_SCOPED_TABLES and have RLS enabled in the database."""
    # Check TENANT_SCOPED_TABLES constant
    assert "email_log" in TENANT_SCOPED_TABLES, "email_log missing from TENANT_SCOPED_TABLES"

    # Check database: RLS must be enabled (relrowsecurity = true)
    result = await admin_session.execute(
        text("""
            SELECT relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = 'email_log'
        """)
    )
    row = result.fetchone()
    assert row is not None, "email_log table not found in pg_class"
    assert row[0] is True, "email_log does not have RLS enabled (relrowsecurity is False)"
    assert row[1] is True, "email_log does not have FORCE RLS (relforcerowsecurity is False)"
