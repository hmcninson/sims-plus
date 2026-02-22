"""
SIMS Plus - Finance Module Integration Tests

Tests exercise full request-response cycles through FastAPI finance endpoints
with a real PostgreSQL database. They verify fee type management, fee structure
creation, invoice generation, and payment recording through the middleware +
service layer stack.

Key behaviors tested:
- Create fee type
- Create fee structure with fee items
- Generate invoice for a student
- Record payment against an invoice
- Verify invoice status updates on payment

NOTES:
- The `client` fixture overrides get_db with admin_session_maker (superuser),
  so RLS is NOT active. These tests validate service-layer tenant_id filtering.
- TenantMiddleware resolves X-Subdomain header via its own DB session.
- Finance endpoints require "finance.*" permissions; SCHOOL_ADMIN has wildcard.
- Finance operations require a school (via get_school_for_tenant helper).
- Invoices require an academic_year_id and term_id, which must exist in the DB.
"""

import pytest
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password


# SQL templates for test data seeding.
_TENANT_INSERT = text("""
    INSERT INTO tenants (id, subdomain, slug, name, is_active,
        tenant_type, subscription_tier, max_students,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), :sub, :slug, :name, true,
        'single_school', 'trial', 50,
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

_SCHOOL_INSERT = text("""
    INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
        student_id_prefix, staff_id_prefix, is_active,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
        'basic', 'active', 'STU', 'STF', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_ACADEMIC_YEAR_INSERT = text("""
    INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
        status, is_current, created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
        :start_date, :end_date, 'active', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_TERM_INSERT = text("""
    INSERT INTO terms (id, tenant_id, academic_year_id, name, short_name,
        sequence, start_date, end_date, status, is_current,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:ay_id AS uuid),
        :name, :short_name, :seq, :start_date, :end_date,
        'active', true,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")

_STUDENT_INSERT = text("""
    INSERT INTO students (id, tenant_id, student_id, first_name,
        last_name, date_of_birth, gender, status,
        created_at, updated_at)
    VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid,
        :fn, :ln, '2012-03-10', 'female', 'active',
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
""")


async def _seed_tenant(
    session: AsyncSession, tenant_id: UUID, subdomain: str, name: str,
) -> None:
    """Insert a tenant row with all required NOT NULL columns."""
    await session.execute(
        _TENANT_INSERT,
        {"id": str(tenant_id), "sub": subdomain, "slug": subdomain, "name": name},
    )


async def _seed_school(
    session: AsyncSession, school_id: UUID, tenant_id: UUID,
    name: str, slug: str,
) -> None:
    """Insert a school row with all required NOT NULL columns."""
    await session.execute(
        _SCHOOL_INSERT,
        {"id": str(school_id), "tid": str(tenant_id), "name": name, "slug": slug},
    )


async def _seed_user(
    session: AsyncSession,
    tenant_id: UUID,
    email: str,
    password: str,
    *,
    role: str = "school_admin",
) -> UUID:
    """Insert a user row. Returns the user ID."""
    user_id = uuid4()
    password_hash = hash_password(password)
    await session.execute(
        _USER_INSERT,
        {
            "id": str(user_id),
            "tid": str(tenant_id),
            "email": email,
            "pw": password_hash,
            "fn": "Finance",
            "ln": "Admin",
            "role": role,
            "status": "active",
        },
    )
    return user_id


async def _seed_academic_year(
    session: AsyncSession, ay_id: UUID, tenant_id: UUID,
) -> None:
    """Insert an academic year row."""
    await session.execute(
        _ACADEMIC_YEAR_INSERT,
        {
            "id": str(ay_id),
            "tid": str(tenant_id),
            "name": "2025/2026",
            "start_date": date(2025, 9, 1),
            "end_date": date(2026, 7, 31),
        },
    )


async def _seed_term(
    session: AsyncSession, term_id: UUID, tenant_id: UUID, ay_id: UUID,
) -> None:
    """Insert a term row."""
    await session.execute(
        _TERM_INSERT,
        {
            "id": str(term_id),
            "tid": str(tenant_id),
            "ay_id": str(ay_id),
            "name": "First Term",
            "short_name": "T1",
            "seq": 1,
            "start_date": date(2025, 9, 1),
            "end_date": date(2025, 12, 20),
        },
    )


async def _seed_student(
    session: AsyncSession, student_id: UUID, tenant_id: UUID,
    sid: str, first_name: str, last_name: str,
) -> None:
    """Insert a student row."""
    await session.execute(
        _STUDENT_INSERT,
        {
            "id": str(student_id),
            "tid": str(tenant_id),
            "sid": sid,
            "fn": first_name,
            "ln": last_name,
        },
    )


async def _login(client, subdomain: str, email: str) -> str:
    """Login and return the access token."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecureP@ss1"},
        headers={"X-Subdomain": subdomain},
    )
    assert response.status_code == 200, (
        f"Login failed for {email} on {subdomain}: {response.text}"
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
@pytest.mark.integration
class TestFinanceModule:
    """Tests for fee type, fee structure, invoice, and payment operations.

    Each test creates its own isolated tenant + school + admin user.
    Finance tests require academic year and term data because invoices
    reference them as NOT NULL foreign keys.
    """

    async def test_create_fee_type(self, client, admin_session):
        """POST /api/v1/finance/fee-types creates a fee type.

        Fee types are categories of fees (tuition, examination, facilities, etc.).
        Verifies the response contains the correct name, category, and is_active.
        """
        tenant_id = uuid4()
        subdomain = f"ftype{uuid4().hex[:6]}"
        school_id = uuid4()
        await _seed_tenant(admin_session, tenant_id, subdomain, "Fee Type School")
        await _seed_school(admin_session, school_id, tenant_id, "Fee Type School", subdomain)
        await _seed_user(admin_session, tenant_id, "feetype@school.com", "SecureP@ss1")
        await admin_session.commit()

        token = await _login(client, subdomain, "feetype@school.com")

        response = await client.post(
            "/api/v1/finance/fee-types",
            json={
                "name": "Tuition Fee",
                "description": "Annual tuition fee",
                "category": "tuition",
                "is_active": True,
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        )
        assert response.status_code == 201, (
            f"Expected 201 for fee type creation, got {response.status_code}: "
            f"{response.text}"
        )
        data = response.json()
        assert data["name"] == "Tuition Fee"
        assert data["category"] == "tuition"
        assert data["is_active"] is True
        assert data["tenant_id"] == str(tenant_id)
        assert data["school_id"] == str(school_id)

    async def test_create_fee_structure_with_items(self, client, admin_session):
        """POST /api/v1/finance/fee-structures creates a fee structure with items.

        Fee structures define the fee breakdown for a class/level/term.
        Verifies the response includes items with correct amounts and totals.
        """
        tenant_id = uuid4()
        subdomain = f"fstru{uuid4().hex[:6]}"
        school_id = uuid4()
        ay_id = uuid4()
        term_id = uuid4()

        await _seed_tenant(admin_session, tenant_id, subdomain, "Fee Structure School")
        await _seed_school(admin_session, school_id, tenant_id, "FS School", subdomain)
        await _seed_user(admin_session, tenant_id, "feestru@school.com", "SecureP@ss1")
        await _seed_academic_year(admin_session, ay_id, tenant_id)
        await _seed_term(admin_session, term_id, tenant_id, ay_id)
        await admin_session.commit()

        token = await _login(client, subdomain, "feestru@school.com")

        response = await client.post(
            "/api/v1/finance/fee-structures",
            json={
                "name": "JHS 1 First Term Fees",
                "description": "Complete fee breakdown for JHS 1",
                "academic_year_id": str(ay_id),
                "term_id": str(term_id),
                "level_category": "jhs",
                "student_type": "all",
                "is_active": True,
                "items": [
                    {
                        "name": "Tuition",
                        "amount": "500.00",
                        "is_optional": False,
                        "sequence": 1,
                    },
                    {
                        "name": "Exam Fee",
                        "amount": "50.00",
                        "is_optional": False,
                        "sequence": 2,
                    },
                    {
                        "name": "Library Fee",
                        "amount": "30.00",
                        "is_optional": True,
                        "sequence": 3,
                    },
                ],
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": subdomain,
            },
        )
        assert response.status_code == 201, (
            f"Expected 201 for fee structure creation, got {response.status_code}: "
            f"{response.text}"
        )
        data = response.json()
        assert data["name"] == "JHS 1 First Term Fees"
        assert data["level_category"] == "jhs"
        assert "items" in data
        assert len(data["items"]) == 3

        # total_amount should sum non-optional items (500 + 50 = 550)
        assert Decimal(str(data["total_amount"])) == Decimal("550.00"), (
            f"Expected total 550.00 (non-optional items), got {data['total_amount']}"
        )

    async def test_generate_invoice_for_student(self, client, admin_session):
        """POST /api/v1/finance/invoices generates an invoice for a student.

        Creates a fee structure, then generates an invoice referencing it.
        Verifies the invoice contains the correct student, amounts, and status.
        """
        tenant_id = uuid4()
        subdomain = f"finv{uuid4().hex[:6]}"
        school_id = uuid4()
        ay_id = uuid4()
        term_id = uuid4()
        student_id = uuid4()

        await _seed_tenant(admin_session, tenant_id, subdomain, "Invoice School")
        await _seed_school(admin_session, school_id, tenant_id, "Invoice School", subdomain)
        await _seed_user(admin_session, tenant_id, "invoice@school.com", "SecureP@ss1")
        await _seed_academic_year(admin_session, ay_id, tenant_id)
        await _seed_term(admin_session, term_id, tenant_id, ay_id)
        await _seed_student(
            admin_session, student_id, tenant_id,
            "STU-INV-001", "Ama", "Darko",
        )
        await admin_session.commit()

        token = await _login(client, subdomain, "invoice@school.com")
        auth_headers = {
            "Authorization": f"Bearer {token}",
            "X-Subdomain": subdomain,
        }

        # First create a fee structure
        fs_response = await client.post(
            "/api/v1/finance/fee-structures",
            json={
                "name": "Invoice Test Fees",
                "academic_year_id": str(ay_id),
                "term_id": str(term_id),
                "student_type": "all",
                "is_active": True,
                "items": [
                    {"name": "Tuition", "amount": "600.00", "is_optional": False, "sequence": 1},
                    {"name": "Exam Fee", "amount": "100.00", "is_optional": False, "sequence": 2},
                ],
            },
            headers=auth_headers,
        )
        assert fs_response.status_code == 201, fs_response.text
        fee_structure_id = fs_response.json()["id"]

        # Generate invoice for the student
        inv_response = await client.post(
            "/api/v1/finance/invoices",
            json={
                "student_id": str(student_id),
                "fee_structure_id": fee_structure_id,
                "academic_year_id": str(ay_id),
                "term_id": str(term_id),
                "due_date": "2026-01-15",
            },
            headers=auth_headers,
        )
        assert inv_response.status_code == 201, (
            f"Expected 201 for invoice creation, got {inv_response.status_code}: "
            f"{inv_response.text}"
        )
        inv_data = inv_response.json()
        assert inv_data["student_id"] == str(student_id)
        assert inv_data["academic_year_id"] == str(ay_id)
        assert inv_data["term_id"] == str(term_id)
        # Total should be sum of fee items (600 + 100 = 700)
        assert Decimal(str(inv_data["total_amount"])) == Decimal("700.00"), (
            f"Expected invoice total 700.00, got {inv_data['total_amount']}"
        )
        assert "invoice_number" in inv_data  # Auto-generated invoice number
        assert inv_data["status"] in ("draft", "issued")

    async def test_record_payment(self, client, admin_session):
        """POST /api/v1/finance/payments records a payment for a student.

        Creates a fee structure + invoice, then records a cash payment.
        Verifies the payment response has correct amount, method, and student.
        """
        tenant_id = uuid4()
        subdomain = f"fpay{uuid4().hex[:6]}"
        school_id = uuid4()
        ay_id = uuid4()
        term_id = uuid4()
        student_id = uuid4()

        await _seed_tenant(admin_session, tenant_id, subdomain, "Payment School")
        await _seed_school(admin_session, school_id, tenant_id, "Payment School", subdomain)
        await _seed_user(admin_session, tenant_id, "payment@school.com", "SecureP@ss1")
        await _seed_academic_year(admin_session, ay_id, tenant_id)
        await _seed_term(admin_session, term_id, tenant_id, ay_id)
        await _seed_student(
            admin_session, student_id, tenant_id,
            "STU-PAY-001", "Kofi", "Mensah",
        )
        await admin_session.commit()

        token = await _login(client, subdomain, "payment@school.com")
        auth_headers = {
            "Authorization": f"Bearer {token}",
            "X-Subdomain": subdomain,
        }

        # Create fee structure
        fs_response = await client.post(
            "/api/v1/finance/fee-structures",
            json={
                "name": "Payment Test Fees",
                "academic_year_id": str(ay_id),
                "term_id": str(term_id),
                "student_type": "all",
                "is_active": True,
                "items": [
                    {"name": "Tuition", "amount": "800.00", "is_optional": False, "sequence": 1},
                ],
            },
            headers=auth_headers,
        )
        assert fs_response.status_code == 201, fs_response.text
        fee_structure_id = fs_response.json()["id"]

        # Generate invoice
        inv_response = await client.post(
            "/api/v1/finance/invoices",
            json={
                "student_id": str(student_id),
                "fee_structure_id": fee_structure_id,
                "academic_year_id": str(ay_id),
                "term_id": str(term_id),
            },
            headers=auth_headers,
        )
        assert inv_response.status_code == 201, inv_response.text
        invoice_id = inv_response.json()["id"]

        # Record a partial payment
        pay_response = await client.post(
            "/api/v1/finance/payments",
            json={
                "student_id": str(student_id),
                "invoice_id": invoice_id,
                "amount": "300.00",
                "payment_method": "cash",
                "payer_name": "Mr. Mensah",
                "payer_phone": "+233244123456",
            },
            headers=auth_headers,
        )
        assert pay_response.status_code == 201, (
            f"Expected 201 for payment, got {pay_response.status_code}: "
            f"{pay_response.text}"
        )
        pay_data = pay_response.json()
        assert Decimal(str(pay_data["amount"])) == Decimal("300.00")
        assert pay_data["payment_method"] == "cash"
        assert pay_data["student_id"] == str(student_id)

    async def test_invoice_status_updates_on_payment(self, client, admin_session):
        """After full payment, invoice status should transition to 'paid'.

        Creates a fee structure + invoice (total = 500), then records a
        full payment of 500. Verifies the invoice balance becomes 0 and
        the status transitions to 'paid'.
        """
        tenant_id = uuid4()
        subdomain = f"fstat{uuid4().hex[:6]}"
        school_id = uuid4()
        ay_id = uuid4()
        term_id = uuid4()
        student_id = uuid4()

        await _seed_tenant(admin_session, tenant_id, subdomain, "Status School")
        await _seed_school(admin_session, school_id, tenant_id, "Status School", subdomain)
        await _seed_user(admin_session, tenant_id, "status@school.com", "SecureP@ss1")
        await _seed_academic_year(admin_session, ay_id, tenant_id)
        await _seed_term(admin_session, term_id, tenant_id, ay_id)
        await _seed_student(
            admin_session, student_id, tenant_id,
            "STU-STAT-001", "Abena", "Osei",
        )
        await admin_session.commit()

        token = await _login(client, subdomain, "status@school.com")
        auth_headers = {
            "Authorization": f"Bearer {token}",
            "X-Subdomain": subdomain,
        }

        # Create fee structure
        fs_response = await client.post(
            "/api/v1/finance/fee-structures",
            json={
                "name": "Status Test Fees",
                "academic_year_id": str(ay_id),
                "term_id": str(term_id),
                "student_type": "all",
                "is_active": True,
                "items": [
                    {"name": "Tuition", "amount": "500.00", "is_optional": False, "sequence": 1},
                ],
            },
            headers=auth_headers,
        )
        assert fs_response.status_code == 201, fs_response.text
        fee_structure_id = fs_response.json()["id"]

        # Generate invoice
        inv_response = await client.post(
            "/api/v1/finance/invoices",
            json={
                "student_id": str(student_id),
                "fee_structure_id": fee_structure_id,
                "academic_year_id": str(ay_id),
                "term_id": str(term_id),
            },
            headers=auth_headers,
        )
        assert inv_response.status_code == 201, inv_response.text
        invoice_id = inv_response.json()["id"]

        # Issue the invoice (draft -> issued) before payment can update status
        issue_response = await client.post(
            f"/api/v1/finance/invoices/{invoice_id}/issue",
            json={"issue_date": "2025-09-01"},
            headers=auth_headers,
        )
        assert issue_response.status_code == 200, issue_response.text

        # Record full payment
        pay_response = await client.post(
            "/api/v1/finance/payments",
            json={
                "student_id": str(student_id),
                "invoice_id": invoice_id,
                "amount": "500.00",
                "payment_method": "cash",
            },
            headers=auth_headers,
        )
        assert pay_response.status_code == 201, pay_response.text

        # Fetch the invoice again to check updated status
        inv_get_response = await client.get(
            f"/api/v1/finance/invoices/{invoice_id}",
            headers=auth_headers,
        )
        assert inv_get_response.status_code == 200, inv_get_response.text
        updated_inv = inv_get_response.json()

        # Invoice should now be fully paid
        assert Decimal(str(updated_inv["balance"])) == Decimal("0.00"), (
            f"Expected balance 0.00 after full payment, got {updated_inv['balance']}"
        )
        assert updated_inv["status"] == "paid", (
            f"Expected status 'paid' after full payment, got '{updated_inv['status']}'"
        )
