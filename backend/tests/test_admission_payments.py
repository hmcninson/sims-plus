"""
Tests for ApplicationPaymentService.

Covers: payment initialization (mocked Paystack), webhook processing,
idempotency, fee waiver rejection. Uses two-engine pattern.
"""

import hashlib
import hmac
import json
import pytest
import secrets
from datetime import datetime, UTC
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch, AsyncMock, MagicMock

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---

async def _seed_payment_prereqs(admin_session, tenant_id, *, fee_waived=False, status="draft"):
    """Seed school, period, application, guardian for payment tests. Returns dict of IDs."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()
    app_id = uuid4()
    tracking_code = secrets.token_urlsafe(48)

    await admin_session.execute(
        text("""
            INSERT INTO schools (
                id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF',
                true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"S-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO academic_years (
                id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31',
                'active', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(year_id), "tid": str(tenant_id), "name": f"AY-{uuid4().hex[:6]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO classes (
                id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"C-{uuid4().hex[:6]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO admission_periods (
                id, tenant_id, school_id, academic_year_id,
                name, start_date, end_date, status,
                application_fee_amount, application_fee_required,
                entrance_exam_required, target_classes,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid),
                :name, '2025-01-01', '2027-12-31', 'open',
                50.00, true, false, '[]',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(period_id), "tid": str(tenant_id), "sid": str(school_id),
         "ayid": str(year_id), "name": f"P-{uuid4().hex[:6]}"},
    )

    await admin_session.execute(
        text("""
            INSERT INTO applications (
                id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid),
                :tc, 'Pay', 'Test',
                '2012-01-01', 'male', CAST(:cid AS uuid), :status,
                '{}', :fee_waived, false,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(app_id), "tid": str(tenant_id),
            "sid": str(school_id), "pid": str(period_id),
            "tc": tracking_code, "cid": str(class_id),
            "fee_waived": fee_waived, "status": status,
        },
    )

    # Seed a primary guardian
    await admin_session.execute(
        text("""
            INSERT INTO application_guardians (
                id, tenant_id, application_id,
                first_name, last_name, phone, email, relationship, is_primary,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                'Parent', 'One', '0241234567', 'parent@test.com', 'father', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {"id": str(uuid4()), "tid": str(tenant_id), "aid": str(app_id)},
    )

    await admin_session.commit()
    return {
        "school_id": school_id, "period_id": period_id,
        "app_id": app_id, "tracking_code": tracking_code,
        "class_id": class_id,
    }


# --- Tests ---


async def test_initiate_payment_fee_waived(app_session, admin_session):
    """Application with fee_waived=true -> FEE_WAIVED error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_payment_prereqs(admin_session, tenant["id"], fee_waived=True)
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationPaymentService, ApplicationPaymentError

    svc = ApplicationPaymentService(app_session)
    with pytest.raises(ApplicationPaymentError) as exc_info:
        await svc.initialize_payment(
            tenant["id"], prereqs["school_id"], prereqs["app_id"], prereqs["tracking_code"],
        )
    assert exc_info.value.code == "FEE_WAIVED"


async def test_initiate_payment_wrong_status(app_session, admin_session):
    """Application not in draft -> INVALID_STATUS."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_payment_prereqs(admin_session, tenant["id"], status="submitted")
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationPaymentService, ApplicationPaymentError

    svc = ApplicationPaymentService(app_session)
    with pytest.raises(ApplicationPaymentError) as exc_info:
        await svc.initialize_payment(
            tenant["id"], prereqs["school_id"], prereqs["app_id"], prereqs["tracking_code"],
        )
    assert exc_info.value.code == "INVALID_STATUS"


async def test_process_webhook_success(app_session, admin_session):
    """Webhook processing transitions draft application to submitted."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_payment_prereqs(admin_session, tenant["id"], status="draft")

    # Seed a pending payment record
    payment_id = uuid4()
    reference = f"ref-{uuid4().hex[:12]}"
    await admin_session.execute(
        text("""
            INSERT INTO application_payments (
                id, tenant_id, application_id,
                amount, currency, status, provider_reference,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                50.00, 'GHS', 'pending', :ref,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(payment_id), "tid": str(tenant["id"]),
            "aid": str(prereqs["app_id"]), "ref": reference,
        },
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationPaymentService

    svc = ApplicationPaymentService(app_session)
    await svc.process_webhook(
        provider_reference=reference,
        amount=50.00,
        payment_method="mobile_money",
        metadata={"paystack_reference": reference},
    )

    # Verify payment status
    result = await app_session.execute(
        text("SELECT status FROM application_payments WHERE id = CAST(:id AS uuid)"),
        {"id": str(payment_id)},
    )
    assert result.scalar() == "completed"

    # Verify application status
    result = await app_session.execute(
        text("SELECT status FROM applications WHERE id = CAST(:id AS uuid)"),
        {"id": str(prereqs["app_id"])},
    )
    assert result.scalar() == "submitted"


async def test_process_webhook_idempotent(app_session, admin_session):
    """Processing same webhook twice does not duplicate or error."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_payment_prereqs(admin_session, tenant["id"], status="draft")

    payment_id = uuid4()
    reference = f"ref-{uuid4().hex[:12]}"
    await admin_session.execute(
        text("""
            INSERT INTO application_payments (
                id, tenant_id, application_id,
                amount, currency, status, provider_reference,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                50.00, 'GHS', 'pending', :ref,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": str(payment_id), "tid": str(tenant["id"]),
            "aid": str(prereqs["app_id"]), "ref": reference,
        },
    )
    await admin_session.commit()

    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationPaymentService

    svc = ApplicationPaymentService(app_session)

    # First call
    await svc.process_webhook(
        provider_reference=reference, amount=50.00,
        payment_method="card", metadata={},
    )

    # Second call -- should not raise
    await svc.process_webhook(
        provider_reference=reference, amount=50.00,
        payment_method="card", metadata={},
    )

    # Still only one completed payment
    result = await app_session.execute(
        text("SELECT status FROM application_payments WHERE id = CAST(:id AS uuid)"),
        {"id": str(payment_id)},
    )
    assert result.scalar() == "completed"


async def test_process_webhook_unknown_reference(app_session, admin_session):
    """Webhook with nonexistent reference -> NOT_FOUND error."""
    tenant = await create_test_tenant(admin_session)
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import ApplicationPaymentService, ApplicationPaymentError

    svc = ApplicationPaymentService(app_session)
    with pytest.raises(ApplicationPaymentError) as exc_info:
        await svc.process_webhook(
            provider_reference="nonexistent-ref",
            amount=50.00, payment_method="card", metadata={},
        )
    assert exc_info.value.code == "NOT_FOUND"
