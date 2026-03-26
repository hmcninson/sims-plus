"""
Tests for admission and rejection letter generation (DecisionService).

Covers: generate_admission_letter, generate_rejection_letter,
PDF color/logo validation, idempotent regeneration, wrong decision type errors.
Uses two-engine pattern with mocked S3.
"""

import pytest
import secrets
from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy import text

from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)

pytestmark = pytest.mark.asyncio


# --- Helpers ---

async def _seed_letter_prereqs(admin_session, tenant_id, *, decision_type="accepted",
                                app_status="offered", primary_color=None, logo_url=None):
    """Seed school, year, class, period, user, application, and decision.
    Returns dict with all IDs including decision_id."""
    school_id = uuid4()
    year_id = uuid4()
    class_id = uuid4()
    period_id = uuid4()
    app_id = uuid4()
    user_id = uuid4()
    decision_id = uuid4()

    color_sql = f"'{primary_color}'" if primary_color else "NULL"
    logo_sql = f"'{logo_url}'" if logo_url else "NULL"

    await admin_session.execute(
        text(f"""
            INSERT INTO schools (id, tenant_id, name, slug, school_type, status,
                student_id_prefix, staff_id_prefix, is_active,
                primary_color, logo_url,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                'basic', 'active', 'STU', 'STF', true,
                {color_sql}, {logo_sql},
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(school_id), "tid": str(tenant_id),
         "name": f"S-{uuid4().hex[:6]}", "slug": f"s-{uuid4().hex[:8]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, name, start_date, end_date,
                status, is_current, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                '2025-09-01', '2026-07-31', 'active', true,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(year_id), "tid": str(tenant_id), "name": f"AY-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO classes (id, tenant_id, name, level, sequence,
                is_active, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                'primary', 1, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(class_id), "tid": str(tenant_id), "name": f"C-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO admission_periods (id, tenant_id, school_id, academic_year_id,
                name, start_date, end_date, status,
                application_fee_amount, application_fee_required,
                entrance_exam_required, target_classes, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid), :name, '2025-01-01', '2027-12-31', 'open',
                0, false, false, '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(period_id), "tid": str(tenant_id), "sid": str(school_id),
         "ayid": str(year_id), "name": f"P-{uuid4().hex[:6]}"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO users (id, tenant_id, email, password_hash,
                first_name, last_name, role, status,
                email_verified, mfa_enabled, failed_login_attempts, timezone,
                created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :email, :pw,
                'Letter', 'Maker', 'school_admin', 'active',
                true, false, 0, 'Africa/Accra', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {"id": str(user_id), "tid": str(tenant_id),
         "email": f"letter-{uuid4().hex[:6]}@test.com",
         "pw": "$argon2id$v=19$m=65536,t=2,p=1$fake"},
    )
    await admin_session.execute(
        text("""
            INSERT INTO applications (id, tenant_id, school_id, admission_period_id,
                tracking_code, applicant_first_name, applicant_last_name,
                date_of_birth, gender, target_class_id, status,
                custom_fields, fee_waived, exam_waived, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:pid AS uuid), :tc, 'Kofi', 'Mensah',
                '2012-01-01', 'male', CAST(:cid AS uuid), :status,
                '{}', false, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(app_id), "tid": str(tenant_id),
            "sid": str(school_id), "pid": str(period_id),
            "tc": secrets.token_urlsafe(48), "cid": str(class_id),
            "status": app_status,
        },
    )

    # Create decision record
    await admin_session.execute(
        text("""
            INSERT INTO admission_decisions (id, tenant_id, application_id,
                decision_type, decided_by, offered_class_id,
                decision_date, response_deadline, created_at, updated_at)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:aid AS uuid),
                :dtype, CAST(:uid AS uuid), CAST(:cid AS uuid),
                CURRENT_DATE, '2026-08-15', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """),
        {
            "id": str(decision_id), "tid": str(tenant_id), "aid": str(app_id),
            "dtype": decision_type, "uid": str(user_id), "cid": str(class_id),
        },
    )

    await admin_session.commit()
    return {
        "school_id": school_id, "period_id": period_id,
        "class_id": class_id, "app_id": app_id, "user_id": user_id,
        "decision_id": decision_id, "year_id": year_id,
    }


def _mock_s3():
    """Create a mock S3 service that simulates upload and presigned URL."""
    mock = MagicMock()
    mock.upload_file.return_value = None
    mock.generate_presigned_url.return_value = "https://s3.example.com/fake-presigned-url"
    return mock


# --- Admission Letter Tests ---


async def test_generate_admission_letter(app_session, admin_session):
    """Generate admission letter for an accepted decision -> returns URL."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_letter_prereqs(
        admin_session, tenant["id"], decision_type="accepted", app_status="offered",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    mock_s3 = _mock_s3()

    with patch("app.services.admissions.decision_service.get_s3_service", return_value=mock_s3), \
         patch.object(DecisionService, "_render_pdf", return_value=b"%PDF-fake"):
        url = await svc.generate_admission_letter(
            tenant["id"], prereqs["decision_id"],
        )

    assert url == "https://s3.example.com/fake-presigned-url"
    mock_s3.upload_file.assert_called_once()
    # Verify the S3 key format
    call_args = mock_s3.upload_file.call_args
    assert "admission.pdf" in call_args[0][1]


async def test_generate_admission_letter_wrong_type(app_session, admin_session):
    """Generating admission letter for a rejected decision -> INVALID_DECISION_TYPE."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_letter_prereqs(
        admin_session, tenant["id"], decision_type="rejected", app_status="rejected",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService, DecisionServiceError

    svc = DecisionService(app_session)
    with pytest.raises(DecisionServiceError) as exc_info:
        await svc.generate_admission_letter(tenant["id"], prereqs["decision_id"])
    assert exc_info.value.code == "INVALID_DECISION_TYPE"


async def test_generate_admission_letter_not_found(app_session, admin_session):
    """Generating admission letter for nonexistent decision -> NOT_FOUND."""
    tenant = await create_test_tenant(admin_session)
    await admin_session.commit()
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService, DecisionServiceError

    svc = DecisionService(app_session)
    with pytest.raises(DecisionServiceError) as exc_info:
        await svc.generate_admission_letter(tenant["id"], uuid4())
    assert exc_info.value.code == "NOT_FOUND"


async def test_admission_letter_url_persisted(app_session, admin_session):
    """After generation, decision_letter_url is saved on the decision record."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_letter_prereqs(
        admin_session, tenant["id"], decision_type="accepted", app_status="offered",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    mock_s3 = _mock_s3()

    with patch("app.services.admissions.decision_service.get_s3_service", return_value=mock_s3), \
         patch.object(DecisionService, "_render_pdf", return_value=b"%PDF-fake"):
        await svc.generate_admission_letter(tenant["id"], prereqs["decision_id"])

    # Verify the S3 key was persisted on the decision record
    result = await app_session.execute(
        text("SELECT decision_letter_url FROM admission_decisions WHERE id = CAST(:id AS uuid)"),
        {"id": str(prereqs["decision_id"])},
    )
    letter_url = result.scalar()
    assert letter_url is not None
    assert "admission.pdf" in letter_url


# --- Rejection Letter Tests ---


async def test_generate_rejection_letter(app_session, admin_session):
    """Generate rejection letter for a rejected decision -> returns URL."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_letter_prereqs(
        admin_session, tenant["id"], decision_type="rejected", app_status="rejected",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    mock_s3 = _mock_s3()

    with patch("app.services.admissions.decision_service.get_s3_service", return_value=mock_s3), \
         patch.object(DecisionService, "_render_pdf", return_value=b"%PDF-fake"):
        url = await svc.generate_rejection_letter(
            tenant["id"], prereqs["decision_id"],
        )

    assert url == "https://s3.example.com/fake-presigned-url"
    mock_s3.upload_file.assert_called_once()
    call_args = mock_s3.upload_file.call_args
    assert "rejection.pdf" in call_args[0][1]


async def test_generate_rejection_letter_with_reason(app_session, admin_session):
    """Rejection letter with reason -> reason persisted on decision."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_letter_prereqs(
        admin_session, tenant["id"], decision_type="rejected", app_status="rejected",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    mock_s3 = _mock_s3()

    with patch("app.services.admissions.decision_service.get_s3_service", return_value=mock_s3), \
         patch.object(DecisionService, "_render_pdf", return_value=b"%PDF-fake"):
        await svc.generate_rejection_letter(
            tenant["id"], prereqs["decision_id"],
            rejection_reason="Academic requirements not met",
        )

    # Verify rejection_reason persisted
    result = await app_session.execute(
        text("SELECT rejection_reason FROM admission_decisions WHERE id = CAST(:id AS uuid)"),
        {"id": str(prereqs["decision_id"])},
    )
    assert result.scalar() == "Academic requirements not met"


async def test_generate_rejection_letter_wrong_type(app_session, admin_session):
    """Generating rejection letter for an accepted decision -> INVALID_DECISION_TYPE."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_letter_prereqs(
        admin_session, tenant["id"], decision_type="accepted", app_status="offered",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService, DecisionServiceError

    svc = DecisionService(app_session)
    with pytest.raises(DecisionServiceError) as exc_info:
        await svc.generate_rejection_letter(tenant["id"], prereqs["decision_id"])
    assert exc_info.value.code == "INVALID_DECISION_TYPE"


async def test_rejection_letter_url_persisted(app_session, admin_session):
    """After generation, rejection_letter_url is saved on the decision record."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_letter_prereqs(
        admin_session, tenant["id"], decision_type="rejected", app_status="rejected",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    mock_s3 = _mock_s3()

    with patch("app.services.admissions.decision_service.get_s3_service", return_value=mock_s3), \
         patch.object(DecisionService, "_render_pdf", return_value=b"%PDF-fake"):
        await svc.generate_rejection_letter(tenant["id"], prereqs["decision_id"])

    result = await app_session.execute(
        text("SELECT rejection_letter_url FROM admission_decisions WHERE id = CAST(:id AS uuid)"),
        {"id": str(prereqs["decision_id"])},
    )
    letter_url = result.scalar()
    assert letter_url is not None
    assert "rejection.pdf" in letter_url


# --- PDF Safety Tests ---


async def test_pdf_safe_color_validation():
    """Invalid hex color replaced with default."""
    from app.services.admissions.decision_service import DecisionService

    # Valid color passes through
    assert DecisionService._safe_color("#1B4F72") == "#1B4F72"
    assert DecisionService._safe_color("#aabbcc") == "#aabbcc"

    # Invalid colors get default
    assert DecisionService._safe_color(None) == "#1B4F72"
    assert DecisionService._safe_color("not-a-color") == "#1B4F72"
    assert DecisionService._safe_color("#12345") == "#1B4F72"  # Too short
    assert DecisionService._safe_color("javascript:alert(1)") == "#1B4F72"


async def test_pdf_safe_logo_validation():
    """Non-https logo URL excluded, https passes through."""
    from app.services.admissions.decision_service import DecisionService

    # HTTPS URLs pass
    assert DecisionService._safe_logo_url("https://cdn.example.com/logo.png") == "https://cdn.example.com/logo.png"

    # Non-HTTPS or None excluded
    assert DecisionService._safe_logo_url(None) is None
    assert DecisionService._safe_logo_url("http://evil.com/logo.png") is None
    assert DecisionService._safe_logo_url("javascript:alert(1)") is None
    assert DecisionService._safe_logo_url("data:image/png;base64,abc") is None


async def test_letter_idempotent(app_session, admin_session):
    """Generating admission letter twice overwrites URL (no duplicates)."""
    tenant = await create_test_tenant(admin_session)
    prereqs = await _seed_letter_prereqs(
        admin_session, tenant["id"], decision_type="accepted", app_status="offered",
    )
    await set_app_tenant_context(app_session, tenant["id"])

    from app.services.admissions import DecisionService

    svc = DecisionService(app_session)
    mock_s3 = _mock_s3()

    with patch("app.services.admissions.decision_service.get_s3_service", return_value=mock_s3), \
         patch.object(DecisionService, "_render_pdf", return_value=b"%PDF-fake"):
        url1 = await svc.generate_admission_letter(tenant["id"], prereqs["decision_id"])
        url2 = await svc.generate_admission_letter(tenant["id"], prereqs["decision_id"])

    # Both calls succeed and return a URL (idempotent)
    assert url1 == url2
    # S3 upload called twice (overwrites)
    assert mock_s3.upload_file.call_count == 2


async def test_letter_tenant_isolation(app_session, admin_session):
    """Tenant A's decision is invisible to Tenant B for letter generation."""
    tenant_a = await create_test_tenant(admin_session)
    tenant_b = await create_test_tenant(admin_session)
    prereqs = await _seed_letter_prereqs(
        admin_session, tenant_a["id"], decision_type="accepted", app_status="offered",
    )
    decision_id = prereqs["decision_id"]

    # Switch to Tenant B -- should NOT see Tenant A's decision
    await set_app_tenant_context(app_session, tenant_b["id"])

    from app.services.admissions import DecisionService, DecisionServiceError

    svc = DecisionService(app_session)
    with pytest.raises(DecisionServiceError) as exc_info:
        await svc.generate_admission_letter(tenant_b["id"], decision_id)
    assert exc_info.value.code == "NOT_FOUND"
