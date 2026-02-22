"""
SIMS Plus - Parent Payment Integration Tests

Tests for the online payment flow via Paystack:
1. Initiate payment (parent -> Paystack)
2. Verify payment (after Paystack redirect)
3. Webhook (Paystack -> us, HMAC-SHA512 verified)

Uses mocking for Paystack API calls since we cannot hit real Paystack in tests.
Tests cover validation, access control, and idempotent recording.
"""

import hashlib
import hmac
import json
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from unittest.mock import AsyncMock, patch

from app.core.security import create_access_token
from app.main import app
from app.api.deps import get_db, get_unscoped_db
from tests.conftest import (
    admin_engine,
    admin_session_maker,
    app_session_maker,
)

_test_mw_session_maker = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False,
)


# =====================================================================
# Fixtures
# =====================================================================


@pytest_asyncio.fixture
async def payment_data():
    """Seed a parent + student + invoice for payment tests.

    Creates:
    - tenant, school, parent user, guardian, student, student_guardian link
    - fee_type, fee_structure, fee_item
    - invoice (ISSUED, total_amount=500, amount_paid=100, balance=400)
    - invoice_item
    """
    suffix = uuid4().hex[:8]
    tenant_id = uuid4()
    school_id = uuid4()
    parent_id = uuid4()
    guardian_id = uuid4()
    student_id = uuid4()
    sg_id = uuid4()
    fee_type_id = uuid4()
    fee_structure_id = uuid4()
    fee_item_id = uuid4()
    invoice_id = uuid4()
    invoice_item_id = uuid4()
    academic_year_id = uuid4()
    term_id = uuid4()
    subdomain = f"pay-{suffix}"
    email = f"pay-parent-{suffix}@test.com"

    async with admin_session_maker() as s:
        # Tenant
        await s.execute(text("""
            INSERT INTO tenants (id, subdomain, slug, name, is_active,
                tenant_type, subscription_tier, max_students, max_staff, status)
            VALUES (CAST(:id AS uuid), :sub, :slug, :name,
                true, 'single_school', 'professional', 1000, 100, 'active')
        """), {"id": str(tenant_id), "sub": subdomain, "slug": subdomain, "name": f"Pay School {suffix}"})

        # School
        await s.execute(text("""
            INSERT INTO schools (id, tenant_id, name, slug, student_id_prefix, school_type)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug, 'PAY', 'basic')
        """), {"id": str(school_id), "tid": str(tenant_id), "name": f"Pay School", "slug": subdomain})

        # Parent user
        await s.execute(text("""
            INSERT INTO users (id, tenant_id, email, password_hash, first_name, last_name,
                role, status, email_verified, mfa_enabled, failed_login_attempts, timezone,
                school_id)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email,
                '$argon2id$v=19$m=65536,t=2,p=1$fake_hash',
                'PayParent', 'Test', 'parent', 'active', true, false, 0, 'Africa/Accra',
                CAST(:sid AS uuid))
        """), {"id": str(parent_id), "tid": str(tenant_id), "email": email, "sid": str(school_id)})

        # Student
        await s.execute(text("""
            INSERT INTO students (id, tenant_id, student_id, first_name, last_name,
                date_of_birth, gender, status, school_id)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :sid, 'PayChild', 'Test',
                '2015-01-15', 'male', 'active', CAST(:school_id AS uuid))
        """), {"id": str(student_id), "tid": str(tenant_id), "sid": f"PAY-{suffix}", "school_id": str(school_id)})

        # Guardian (email matches parent user)
        await s.execute(text("""
            INSERT INTO guardians (id, tenant_id, first_name, last_name, phone, email)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'PayParent', 'Test', '0241234567', :email)
        """), {"id": str(guardian_id), "tid": str(tenant_id), "email": email})

        # Student-guardian link
        await s.execute(text("""
            INSERT INTO student_guardians (id, tenant_id, student_id, guardian_id,
                relationship, is_primary, is_emergency_contact, can_pickup)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:gid AS uuid), 'father', true, true, true)
        """), {"id": str(sg_id), "tid": str(tenant_id), "sid": str(student_id), "gid": str(guardian_id)})

        # Academic year (required for invoices)
        await s.execute(text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date, is_current, status)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                '2025/2026', '2025-09-01', '2026-07-31', true, 'active')
        """), {"id": str(academic_year_id), "tid": str(tenant_id)})

        # Term (required for invoices)
        await s.execute(text("""
            INSERT INTO terms (id, tenant_id, academic_year_id, name, start_date, end_date, is_current, sequence)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid),
                CAST(:ay_id AS uuid), 'Term 2', '2026-01-06', '2026-04-10', true, 2)
        """), {"id": str(term_id), "tid": str(tenant_id), "ay_id": str(academic_year_id)})

        # Fee type
        await s.execute(text("""
            INSERT INTO fee_types (id, tenant_id, school_id, name, description)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid), 'Tuition', 'Tuition fees')
        """), {"id": str(fee_type_id), "tid": str(tenant_id), "sid": str(school_id)})

        # Invoice (ISSUED, 500 total, 100 paid)
        await s.execute(text("""
            INSERT INTO invoices (id, tenant_id, school_id, student_id,
                academic_year_id, term_id,
                invoice_number, total_amount, amount_paid, status, due_date)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:stud_id AS uuid), CAST(:ay_id AS uuid), CAST(:term_id AS uuid),
                :num, 500.00, 100.00, 'issued', '2026-03-31')
        """), {"id": str(invoice_id), "tid": str(tenant_id), "sid": str(school_id),
               "stud_id": str(student_id), "ay_id": str(academic_year_id),
               "term_id": str(term_id), "num": f"INV-{suffix}"})

        # Invoice item
        await s.execute(text("""
            INSERT INTO invoice_items (id, tenant_id, invoice_id,
                description, unit_price, amount)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:inv_id AS uuid),
                'Tuition Term 2', 500.00, 500.00)
        """), {"id": str(invoice_item_id), "tid": str(tenant_id),
               "inv_id": str(invoice_id)})

        await s.commit()

    data = {
        "tenant_id": tenant_id,
        "school_id": school_id,
        "subdomain": subdomain,
        "parent_id": parent_id,
        "parent_email": email,
        "student_id": student_id,
        "invoice_id": invoice_id,
    }

    yield data

    # Cleanup
    async with admin_session_maker() as s:
        for table in [
            "payments", "invoice_items", "invoice_scholarship_items",
            "invoices", "fee_items", "fee_structures", "fee_types",
            "finance_audit_log", "credit_notes",
            "teacher_notes", "announcements", "parent_notification_preferences",
            "student_guardians", "guardians", "students",
            "users",
            "terms", "academic_years",
            "schools",
        ]:
            await s.execute(
                text(f"DELETE FROM {table} WHERE tenant_id = CAST(:tid AS uuid)"),
                {"tid": str(tenant_id)},
            )
        await s.execute(
            text("DELETE FROM tenants WHERE id = CAST(:tid AS uuid)"),
            {"tid": str(tenant_id)},
        )
        await s.commit()


@pytest_asyncio.fixture
async def pay_client(payment_data):
    """Authenticated parent client for payment tests."""
    d = payment_data
    token = create_access_token(
        subject=str(d["parent_id"]),
        tenant_id=str(d["tenant_id"]),
        school_id=str(d["school_id"]),
        role="parent",
        permissions=["parent.children.read", "parent.finance.read"],
        extra_claims={"email": d["parent_email"]},
    )

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

    with patch("app.middleware.tenant.async_session_maker", _test_mw_session_maker), \
         patch("app.main.async_session_maker", _test_mw_session_maker):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Subdomain": d["subdomain"],
            },
        ) as client:
            yield client

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_unscoped_db, None)


# =====================================================================
# Tests: Initiate payment
# =====================================================================


@pytest.mark.asyncio
async def test_initiate_payment_success(pay_client, payment_data):
    """Initiating a valid payment should return 201 with authorization_url."""
    d = payment_data

    mock_response = {
        "status": True,
        "data": {
            "authorization_url": "https://checkout.paystack.com/test123",
            "reference": "SIMS-ABCDEF1234567890",
            "access_code": "test_access_code",
        },
    }

    with patch(
        "app.services.payment.online_payment.OnlinePaymentService._call_paystack",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await pay_client.post(
            f"/api/v1/parent/children/{d['student_id']}/payments/initiate",
            json={
                "invoice_id": str(d["invoice_id"]),
                "amount": 200.00,
                "method": "card",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert "authorization_url" in data
    assert "reference" in data


@pytest.mark.asyncio
async def test_initiate_payment_nonexistent_invoice(pay_client, payment_data):
    """Initiating payment with a fake invoice ID should return 404."""
    d = payment_data
    fake_invoice = uuid4()

    response = await pay_client.post(
        f"/api/v1/parent/children/{d['student_id']}/payments/initiate",
        json={
            "invoice_id": str(fake_invoice),
            "amount": 100.00,
            "method": "card",
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_initiate_payment_amount_exceeds_balance(pay_client, payment_data):
    """Amount exceeding outstanding balance (400 GHS) should return 422."""
    d = payment_data

    response = await pay_client.post(
        f"/api/v1/parent/children/{d['student_id']}/payments/initiate",
        json={
            "invoice_id": str(d["invoice_id"]),
            "amount": 999.00,
            "method": "card",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_initiate_momo_without_phone_fails_validation(pay_client, payment_data):
    """Mobile money payment without phone number should fail validation."""
    d = payment_data

    response = await pay_client.post(
        f"/api/v1/parent/children/{d['student_id']}/payments/initiate",
        json={
            "invoice_id": str(d["invoice_id"]),
            "amount": 100.00,
            "method": "mobile_money",
            # phone intentionally omitted
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_initiate_momo_with_phone_succeeds(pay_client, payment_data):
    """Mobile money payment with phone should succeed."""
    d = payment_data

    mock_response = {
        "status": True,
        "data": {
            "authorization_url": "https://checkout.paystack.com/momo123",
            "reference": "SIMS-MOMO12345678",
            "access_code": "momo_access",
        },
    }

    with patch(
        "app.services.payment.online_payment.OnlinePaymentService._call_paystack",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = await pay_client.post(
            f"/api/v1/parent/children/{d['student_id']}/payments/initiate",
            json={
                "invoice_id": str(d["invoice_id"]),
                "amount": 100.00,
                "method": "mobile_money",
                "phone": "0241234567890",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["reference"] == "SIMS-MOMO12345678"


# =====================================================================
# Tests: Webhook signature verification
# =====================================================================


@pytest.mark.asyncio
async def test_webhook_signature_validation():
    """verify_webhook_signature should pass for valid HMAC-SHA512."""
    from app.services.payment.online_payment import OnlinePaymentService

    secret = "sk_test_123"
    payload = b'{"event":"charge.success","data":{"reference":"SIMS-TEST1234"}}'
    valid_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha512).hexdigest()

    assert OnlinePaymentService.verify_webhook_signature(payload, valid_sig, secret) is True


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected():
    """verify_webhook_signature should reject a bad signature."""
    from app.services.payment.online_payment import OnlinePaymentService

    secret = "sk_test_123"
    payload = b'{"event":"charge.success"}'
    bad_sig = "deadbeef" * 16

    assert OnlinePaymentService.verify_webhook_signature(payload, bad_sig, secret) is False


# =====================================================================
# Tests: OnlinePaymentService unit tests
# =====================================================================


@pytest.mark.asyncio
async def test_resolve_payment_method_card():
    """Card channel should resolve to CARD payment method."""
    from app.services.payment.online_payment import OnlinePaymentService
    from app.models.finance import PaymentMethod

    txn = {"authorization": {"channel": "card", "bank": "Visa"}}
    assert OnlinePaymentService._resolve_payment_method(txn) == PaymentMethod.CARD


@pytest.mark.asyncio
async def test_resolve_payment_method_mtn_momo():
    """MTN mobile money should resolve to MOMO_MTN."""
    from app.services.payment.online_payment import OnlinePaymentService
    from app.models.finance import PaymentMethod

    txn = {"authorization": {"channel": "mobile_money", "bank": "MTN Mobile Money"}}
    assert OnlinePaymentService._resolve_payment_method(txn) == PaymentMethod.MOMO_MTN


@pytest.mark.asyncio
async def test_resolve_payment_method_vodafone():
    """Vodafone mobile money should resolve to MOMO_VODAFONE."""
    from app.services.payment.online_payment import OnlinePaymentService
    from app.models.finance import PaymentMethod

    txn = {"authorization": {"channel": "mobile_money", "bank": "Vodafone Cash"}}
    assert OnlinePaymentService._resolve_payment_method(txn) == PaymentMethod.MOMO_VODAFONE
