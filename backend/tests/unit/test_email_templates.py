"""
SIMS Plus - Email Service Template Rendering Tests

Tests that all email methods produce valid HTML without errors.
No SMTP connection is needed -- we mock aiosmtplib and verify that
the rendered HTML contains the expected dynamic content.

Two categories of email methods exist in the service:
  1. Jinja2 template-based: welcome, password_reset (files in app/templates/email/)
  2. Inline f-string-based: attendance_alert, exam_results, fee_reminder,
     user_invite, user_credentials, invoice_email

Both categories are covered here. For Jinja2 templates we also test
rendering directly through the jinja_env to catch template syntax errors
independently of the send path.

Location: tests/unit/test_email_templates.py
Requires: No database. Runs in the tests/unit/ subdirectory which has its
own conftest.py that overrides DB-dependent autouse fixtures.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.email import EmailService, email_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Resolve template directory from the EmailService module, not from __file__,
# so the path is correct regardless of which test directory we run from.
TEMPLATE_DIR = Path(email_service.jinja_env.loader.searchpath[0])


def _dev_email_service() -> EmailService:
    """Return the singleton email_service, which runs in dev mode during tests."""
    return email_service


# ---------------------------------------------------------------------------
# 1. Jinja2 template file existence
# ---------------------------------------------------------------------------


class TestTemplateFilesExist:
    """Verify that all expected Jinja2 template files are present on disk."""

    def test_welcome_template_exists(self):
        assert (TEMPLATE_DIR / "welcome.html").exists(), (
            "welcome.html template is missing from app/templates/email/"
        )

    def test_password_reset_template_exists(self):
        assert (TEMPLATE_DIR / "password_reset.html").exists(), (
            "password_reset.html template is missing from app/templates/email/"
        )

    def test_template_directory_exists(self):
        assert TEMPLATE_DIR.is_dir(), (
            "Email template directory does not exist at app/templates/email/"
        )


# ---------------------------------------------------------------------------
# 2. Jinja2 template rendering (direct, no SMTP)
# ---------------------------------------------------------------------------


class TestJinja2TemplateRendering:
    """
    Render Jinja2 templates directly through the EmailService jinja_env.
    This catches syntax errors and missing variable references before they
    reach the send path.
    """

    def test_welcome_template_renders_all_variables(self):
        svc = _dev_email_service()
        template = svc.jinja_env.get_template("welcome.html")
        html = template.render(
            admin_name="Kwame Asante",
            school_name="Achimota School",
            subdomain="achimota",
            portal_url="https://achimota.simsplus.io",
            admin_email="admin@achimota.edu.gh",
            trial_ends_at="March 20, 2026",
            current_year=2026,
        )
        # Dynamic variables should appear in the rendered output
        assert "Kwame Asante" in html
        assert "Achimota School" in html
        assert "achimota.simsplus.io" in html
        assert "admin@achimota.edu.gh" in html
        assert "March 20, 2026" in html
        assert "2026" in html

    def test_welcome_template_renders_without_trial(self):
        """The trial_ends_at block is conditional; verify it renders without it."""
        svc = _dev_email_service()
        template = svc.jinja_env.get_template("welcome.html")
        html = template.render(
            admin_name="Ama Mensah",
            school_name="Wesley Girls",
            subdomain="wesleyg",
            portal_url="https://wesleyg.simsplus.io",
            admin_email="ama@wesleyg.edu.gh",
            trial_ends_at=None,
            current_year=2026,
        )
        assert "Ama Mensah" in html
        assert "Wesley Girls" in html
        # The trial notice should NOT appear
        assert "Free Trial" not in html

    def test_password_reset_template_renders_all_variables(self):
        svc = _dev_email_service()
        template = svc.jinja_env.get_template("password_reset.html")
        html = template.render(
            user_name="Kofi Owusu",
            reset_url="https://presec.simsplus.io/reset?token=abc123",
            expires_in_hours=24,
            current_year=2026,
        )
        assert "Kofi Owusu" in html
        assert "https://presec.simsplus.io/reset?token=abc123" in html
        assert "24 hours" in html
        assert "2026" in html

    def test_password_reset_template_renders_custom_expiry(self):
        svc = _dev_email_service()
        template = svc.jinja_env.get_template("password_reset.html")
        html = template.render(
            user_name="Efua Boateng",
            reset_url="https://achimota.simsplus.io/reset?token=xyz789",
            expires_in_hours=1,
            current_year=2026,
        )
        assert "1 hours" in html
        assert "Efua Boateng" in html


# ---------------------------------------------------------------------------
# 3. Inline f-string email methods (Sprint 5-6 additions)
#
# These methods build HTML via f-strings, so we test them by calling the
# async method with SMTP mocked out. In dev mode (ENVIRONMENT=development,
# no SMTP_HOST) the service logs instead of sending, so we just verify the
# method returns True and does not raise.
# ---------------------------------------------------------------------------


class TestAttendanceAlertEmail:
    """send_attendance_alert: inline HTML for parent attendance notifications."""

    async def test_renders_and_sends_successfully(self):
        svc = _dev_email_service()

        with patch("app.services.email.settings") as mock_settings:
            mock_settings.is_development = True
            mock_settings.SMTP_HOST = None
            mock_settings.is_production = False
            mock_settings.SMTP_FROM_EMAIL = "noreply@simsplus.io"
            mock_settings.SMTP_FROM_NAME = "SIMS Plus"

            result = await svc.send_attendance_alert(
                to_email="parent@example.com",
                student_name="Kwame Asante",
                date="20/02/2026",
                status="absent",
                school_name="Presec Legon",
            )
            assert result is True

    async def test_subject_contains_student_and_school(self):
        """Verify the subject line includes student name and school."""
        svc = _dev_email_service()
        calls = []

        # Capture the send_email call to inspect arguments
        original_send = svc.send_email

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send) as _:
            await svc.send_attendance_alert(
                to_email="parent@example.com",
                student_name="Ama Mensah",
                date="15/01/2026",
                status="late",
                school_name="Achimota School",
            )

        assert len(calls) == 1
        assert "Ama Mensah" in calls[0]["subject"]
        assert "Achimota School" in calls[0]["subject"]
        assert "Ama Mensah" in calls[0]["html_content"]
        assert "late" in calls[0]["html_content"]
        assert "15/01/2026" in calls[0]["html_content"]

    async def test_html_contains_all_dynamic_content(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_attendance_alert(
                to_email="guardian@test.com",
                student_name="Yaw Boateng",
                date="03/03/2026",
                status="sick",
                school_name="Wesley Girls",
            )

        html = calls[0]["html_content"]
        assert "Yaw Boateng" in html
        assert "sick" in html
        assert "03/03/2026" in html
        assert "Wesley Girls" in html


class TestExamResultsNotificationEmail:
    """send_exam_results_notification: inline HTML for exam results alerts."""

    async def test_renders_and_sends_successfully(self):
        svc = _dev_email_service()

        with patch("app.services.email.settings") as mock_settings:
            mock_settings.is_development = True
            mock_settings.SMTP_HOST = None
            mock_settings.is_production = False
            mock_settings.SMTP_FROM_EMAIL = "noreply@simsplus.io"
            mock_settings.SMTP_FROM_NAME = "SIMS Plus"

            result = await svc.send_exam_results_notification(
                to_email="parent@example.com",
                student_name="Akua Serwaa",
                exam_name="End of Term 1 Exams",
                school_name="Presec Legon",
            )
            assert result is True

    async def test_html_contains_exam_and_student_details(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_exam_results_notification(
                to_email="parent@example.com",
                student_name="Kofi Mensah",
                exam_name="Mid-Term Examination 2026",
                school_name="Achimota School",
            )

        html = calls[0]["html_content"]
        assert "Kofi Mensah" in html
        assert "Mid-Term Examination 2026" in html
        assert "Achimota School" in html

    async def test_subject_line_format(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_exam_results_notification(
                to_email="parent@example.com",
                student_name="Esi Appiah",
                exam_name="BECE Mock",
                school_name="Presec Legon",
            )

        subject = calls[0]["subject"]
        assert "Esi Appiah" in subject
        assert "Presec Legon" in subject


class TestFeeReminderEmail:
    """send_fee_reminder: inline HTML for outstanding fee notifications."""

    async def test_renders_and_sends_successfully(self):
        svc = _dev_email_service()

        with patch("app.services.email.settings") as mock_settings:
            mock_settings.is_development = True
            mock_settings.SMTP_HOST = None
            mock_settings.is_production = False
            mock_settings.SMTP_FROM_EMAIL = "noreply@simsplus.io"
            mock_settings.SMTP_FROM_NAME = "SIMS Plus"

            result = await svc.send_fee_reminder(
                to_email="parent@example.com",
                student_name="Kwabena Osei",
                amount_due=1500.00,
                currency="GHS",
                due_date="28/02/2026",
                school_name="Achimota School",
            )
            assert result is True

    async def test_html_contains_financial_details(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_fee_reminder(
                to_email="parent@example.com",
                student_name="Ama Darko",
                amount_due=2750.50,
                currency="GHS",
                due_date="15/03/2026",
                school_name="Wesley Girls",
            )

        html = calls[0]["html_content"]
        assert "Ama Darko" in html
        assert "2,750.50" in html
        assert "GHS" in html
        assert "15/03/2026" in html
        assert "Wesley Girls" in html

    async def test_amount_formatted_with_commas(self):
        """Verify large amounts are formatted with comma separators."""
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_fee_reminder(
                to_email="parent@example.com",
                student_name="Yaw Mensah",
                amount_due=12500.00,
                currency="GHS",
                due_date="01/04/2026",
                school_name="Presec Legon",
            )

        html = calls[0]["html_content"]
        # f-string uses :,.2f so 12500.00 becomes 12,500.00
        assert "12,500.00" in html

    async def test_subject_contains_student_and_school(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_fee_reminder(
                to_email="parent@example.com",
                student_name="Efua Ansah",
                amount_due=500.00,
                currency="GHS",
                due_date="30/03/2026",
                school_name="Achimota School",
            )

        subject = calls[0]["subject"]
        assert "Efua Ansah" in subject
        assert "Achimota School" in subject


class TestUserInviteEmail:
    """send_user_invite: inline HTML for new user account invitations."""

    async def test_renders_and_sends_successfully(self):
        svc = _dev_email_service()

        with patch("app.services.email.settings") as mock_settings:
            mock_settings.is_development = True
            mock_settings.SMTP_HOST = None
            mock_settings.is_production = False
            mock_settings.SMTP_FROM_EMAIL = "noreply@simsplus.io"
            mock_settings.SMTP_FROM_NAME = "SIMS Plus"

            result = await svc.send_user_invite(
                to_email="teacher@presec.edu.gh",
                inviter_name="Admin User",
                school_name="Presec Legon",
                temp_password="TempPass123!",
                role="Teacher",
                portal_url="https://presec.simsplus.io",
            )
            assert result is True

    async def test_html_contains_invite_details(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_user_invite(
                to_email="newteacher@achimota.edu.gh",
                inviter_name="Dr. Mensah",
                school_name="Achimota School",
                temp_password="Xk9#mPw2!",
                role="Academic Head",
                portal_url="https://achimota.simsplus.io",
            )

        html = calls[0]["html_content"]
        assert "Dr. Mensah" in html
        assert "Achimota School" in html
        assert "Xk9#mPw2!" in html
        assert "Academic Head" in html
        assert "https://achimota.simsplus.io" in html
        assert "newteacher@achimota.edu.gh" in html

    async def test_contains_password_change_warning(self):
        """Invite emails must warn users to change their temporary password."""
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_user_invite(
                to_email="staff@school.edu.gh",
                inviter_name="Admin",
                school_name="Test School",
                temp_password="Abc12345!",
                role="Finance Officer",
                portal_url="http://localhost:3000",
            )

        html = calls[0]["html_content"]
        # The inline template includes a password change warning
        assert "change your password" in html.lower()

    async def test_subject_contains_school_name(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_user_invite(
                to_email="staff@school.edu.gh",
                inviter_name="Admin",
                school_name="Presec Legon",
                temp_password="Abc12345!",
                role="Teacher",
                portal_url="http://localhost:3000",
            )

        subject = calls[0]["subject"]
        assert "Presec Legon" in subject


# ---------------------------------------------------------------------------
# 4. Additional template-based send methods (welcome, password_reset)
# ---------------------------------------------------------------------------


class TestWelcomeEmailSendMethod:
    """
    send_welcome_email: uses Jinja2 welcome.html template.
    Verify the full send path produces correct HTML.
    """

    async def test_renders_via_jinja_template(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_welcome_email(
                to_email="admin@presec.edu.gh",
                admin_name="John Mensah",
                school_name="Presec Legon",
                subdomain="presec",
                trial_ends_at=datetime(2026, 4, 20),
            )

        assert len(calls) == 1
        html = calls[0]["html_content"]
        assert "John Mensah" in html
        assert "Presec Legon" in html
        # Jinja2-rendered template should contain the subdomain portal link
        assert "presec.simsplus.io" in html
        assert "admin@presec.edu.gh" in html
        # Trial date formatted by strftime as "April 20, 2026"
        assert "April 20, 2026" in html

    async def test_renders_without_trial_date(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_welcome_email(
                to_email="admin@achimota.edu.gh",
                admin_name="Ama Boateng",
                school_name="Achimota School",
                subdomain="achimota",
                trial_ends_at=None,
            )

        html = calls[0]["html_content"]
        assert "Ama Boateng" in html
        assert "Free Trial" not in html

    async def test_subject_contains_school_name(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_welcome_email(
                to_email="admin@school.edu.gh",
                admin_name="Test Admin",
                school_name="Wesley Girls",
                subdomain="wesleyg",
            )

        subject = calls[0]["subject"]
        assert "Wesley Girls" in subject


class TestPasswordResetEmailSendMethod:
    """
    send_password_reset_email: uses Jinja2 password_reset.html template.
    """

    async def test_renders_via_jinja_template(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_password_reset_email(
                to_email="user@presec.edu.gh",
                user_name="Kofi Owusu",
                reset_url="https://presec.simsplus.io/reset?token=abc123",
                expires_in_hours=24,
            )

        assert len(calls) == 1
        html = calls[0]["html_content"]
        assert "Kofi Owusu" in html
        assert "https://presec.simsplus.io/reset?token=abc123" in html
        assert "24 hours" in html

    async def test_custom_expiry_hours(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_password_reset_email(
                to_email="user@school.edu.gh",
                user_name="Efua Mensah",
                reset_url="https://achimota.simsplus.io/reset?token=xyz",
                expires_in_hours=1,
            )

        html = calls[0]["html_content"]
        assert "1 hours" in html


# ---------------------------------------------------------------------------
# 5. Invoice email (inline HTML with attachments)
# ---------------------------------------------------------------------------


class TestInvoiceEmailRendering:
    """send_invoice_email: inline HTML with PDF attachment and optional CC."""

    async def test_renders_with_all_fields(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_invoice_email(
                to_email="parent@example.com",
                recipient_name="Mrs. Asante",
                student_name="Kwame Asante",
                invoice_number="INV-2026-001",
                total_amount=3500.00,
                balance_due=1500.00,
                currency="GHS",
                due_date="28/02/2026",
                school_name="Presec Legon",
                pdf_data=b"%PDF-1.4 fake",
                pdf_filename="INV-2026-001.pdf",
            )

        assert len(calls) == 1
        html = calls[0]["html_content"]
        assert "Mrs. Asante" in html
        assert "Kwame Asante" in html
        assert "INV-2026-001" in html
        assert "3,500.00" in html
        assert "1,500.00" in html
        assert "GHS" in html
        assert "28/02/2026" in html
        assert "Presec Legon" in html

    async def test_renders_paid_status_when_balance_zero(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_invoice_email(
                to_email="parent@example.com",
                recipient_name="Mr. Mensah",
                student_name="Ama Mensah",
                invoice_number="INV-2026-002",
                total_amount=2000.00,
                balance_due=0.00,
                currency="GHS",
                due_date=None,
                school_name="Achimota School",
                pdf_data=b"%PDF-1.4 fake",
                pdf_filename="INV-2026-002.pdf",
            )

        html = calls[0]["html_content"]
        assert "PAID" in html

    async def test_includes_pdf_attachment(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            pdf_bytes = b"%PDF-1.4 test content"
            await svc.send_invoice_email(
                to_email="parent@example.com",
                recipient_name="Mrs. Boateng",
                student_name="Yaw Boateng",
                invoice_number="INV-2026-003",
                total_amount=1000.00,
                balance_due=1000.00,
                currency="GHS",
                due_date="15/03/2026",
                school_name="Wesley Girls",
                pdf_data=pdf_bytes,
                pdf_filename="INV-2026-003.pdf",
            )

        # Verify attachment was passed through
        attachments = calls[0]["attachments"]
        assert len(attachments) == 1
        assert attachments[0][0] == pdf_bytes
        assert attachments[0][1] == "INV-2026-003.pdf"
        assert attachments[0][2] == "application/pdf"

    async def test_includes_cc_emails(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_invoice_email(
                to_email="parent@example.com",
                recipient_name="Mr. Appiah",
                student_name="Efua Appiah",
                invoice_number="INV-2026-004",
                total_amount=5000.00,
                balance_due=5000.00,
                currency="GHS",
                due_date="30/03/2026",
                school_name="Presec Legon",
                pdf_data=b"%PDF fake",
                pdf_filename="INV-2026-004.pdf",
                cc_emails=["finance@presec.edu.gh", "head@presec.edu.gh"],
            )

        assert calls[0]["cc_emails"] == ["finance@presec.edu.gh", "head@presec.edu.gh"]

    async def test_includes_plain_text_version(self):
        """Invoice email should include a plain text alternative."""
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_invoice_email(
                to_email="parent@example.com",
                recipient_name="Mrs. Owusu",
                student_name="Kofi Owusu",
                invoice_number="INV-2026-005",
                total_amount=3000.00,
                balance_due=3000.00,
                currency="GHS",
                due_date="01/04/2026",
                school_name="Achimota School",
                pdf_data=b"%PDF fake",
                pdf_filename="INV-2026-005.pdf",
            )

        text_content = calls[0]["text_content"]
        assert text_content is not None
        assert "Kofi Owusu" in text_content
        assert "INV-2026-005" in text_content
        assert "3,000.00" in text_content


# ---------------------------------------------------------------------------
# 6. User credentials email (inline HTML, no Jinja2 template)
# ---------------------------------------------------------------------------


class TestUserCredentialsEmailRendering:
    """send_user_credentials_email: inline HTML for newly created users."""

    async def test_renders_with_all_fields(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_user_credentials_email(
                to_email="teacher@presec.edu.gh",
                user_name="Kwame Mensah",
                password="TempPass123!",
                role="Teacher",
                school_name="Presec Legon",
                portal_url="https://presec.simsplus.io",
            )

        assert len(calls) == 1
        html = calls[0]["html_content"]
        assert "Kwame Mensah" in html
        assert "teacher@presec.edu.gh" in html
        assert "TempPass123!" in html
        assert "Teacher" in html
        assert "Presec Legon" in html
        assert "https://presec.simsplus.io" in html

    async def test_contains_password_change_warning(self):
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_user_credentials_email(
                to_email="staff@school.edu.gh",
                user_name="Ama Boateng",
                password="SecurePass1!",
                role="Finance Officer",
                school_name="Test School",
                portal_url="http://localhost:3000",
            )

        html = calls[0]["html_content"]
        assert "change your password" in html.lower()


# ---------------------------------------------------------------------------
# 7. Edge cases and defensive checks
# ---------------------------------------------------------------------------


class TestEmailEdgeCases:
    """Edge cases: special characters, empty strings, HTML escaping."""

    async def test_attendance_alert_with_special_characters_in_name(self):
        """Names with apostrophes or accents should not break rendering."""
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_attendance_alert(
                to_email="parent@example.com",
                student_name="O'Brien Nana-Kwame",
                date="20/02/2026",
                status="absent",
                school_name="St. Mary's School",
            )

        html = calls[0]["html_content"]
        # f-strings pass through special chars as-is
        assert "O'Brien Nana-Kwame" in html
        assert "St. Mary's School" in html

    def test_welcome_template_escapes_html_in_variables(self):
        """
        Jinja2 autoescaping should prevent XSS in template variables.
        The welcome template uses autoescape for HTML/XML.
        """
        svc = _dev_email_service()
        template = svc.jinja_env.get_template("welcome.html")
        html = template.render(
            admin_name='<script>alert("xss")</script>',
            school_name="Test School",
            subdomain="test",
            portal_url="http://localhost:3000",
            admin_email="admin@test.com",
            trial_ends_at=None,
            current_year=2026,
        )
        # Jinja2 autoescape should escape the script tag
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_password_reset_template_escapes_html_in_variables(self):
        svc = _dev_email_service()
        template = svc.jinja_env.get_template("password_reset.html")
        html = template.render(
            user_name='<img src=x onerror=alert(1)>',
            reset_url="https://test.simsplus.io/reset?token=safe",
            expires_in_hours=24,
            current_year=2026,
        )
        assert "<img src=x" not in html
        assert "&lt;img" in html

    async def test_fee_reminder_with_zero_amount(self):
        """Zero balance should render without errors."""
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_fee_reminder(
                to_email="parent@example.com",
                student_name="Test Student",
                amount_due=0.00,
                currency="GHS",
                due_date="01/01/2026",
                school_name="Test School",
            )

        html = calls[0]["html_content"]
        assert "0.00" in html

    async def test_invoice_without_due_date(self):
        """Invoice with no due_date should render the due_date section as empty."""
        svc = _dev_email_service()
        calls = []

        async def capture_send(**kwargs):
            calls.append(kwargs)
            return True

        with patch.object(svc, "send_email", side_effect=capture_send):
            await svc.send_invoice_email(
                to_email="parent@example.com",
                recipient_name="Mrs. Test",
                student_name="Test Student",
                invoice_number="INV-TEST",
                total_amount=100.00,
                balance_due=100.00,
                currency="GHS",
                due_date=None,
                school_name="Test School",
                pdf_data=b"fake",
                pdf_filename="test.pdf",
            )

        html = calls[0]["html_content"]
        # When due_date is None, the due_date_section should be empty
        assert "Due Date:" not in html


# ---------------------------------------------------------------------------
# 8. MIME message construction
# ---------------------------------------------------------------------------


class TestMimeMessageConstruction:
    """Test _create_message builds correct MIME structures."""

    def test_creates_alternative_message_without_attachments(self):
        svc = _dev_email_service()

        with patch("app.services.email.settings") as mock_settings:
            mock_settings.SMTP_FROM_EMAIL = "noreply@simsplus.io"
            mock_settings.SMTP_FROM_NAME = "SIMS Plus"

            msg = svc._create_message(
                to_email="test@example.com",
                subject="Test Subject",
                html_content="<p>Hello</p>",
            )

        assert msg["Subject"] == "Test Subject"
        assert msg["To"] == "test@example.com"
        assert "SIMS Plus" in msg["From"]
        assert msg.get_content_type() == "multipart/alternative"

    def test_creates_mixed_message_with_attachments(self):
        svc = _dev_email_service()

        with patch("app.services.email.settings") as mock_settings:
            mock_settings.SMTP_FROM_EMAIL = "noreply@simsplus.io"
            mock_settings.SMTP_FROM_NAME = "SIMS Plus"

            msg = svc._create_message(
                to_email="test@example.com",
                subject="Invoice",
                html_content="<p>Invoice attached</p>",
                attachments=[(b"pdf-bytes", "invoice.pdf", "application/pdf")],
            )

        assert msg.get_content_type() == "multipart/mixed"

    def test_includes_cc_header(self):
        svc = _dev_email_service()

        with patch("app.services.email.settings") as mock_settings:
            mock_settings.SMTP_FROM_EMAIL = "noreply@simsplus.io"
            mock_settings.SMTP_FROM_NAME = "SIMS Plus"

            msg = svc._create_message(
                to_email="test@example.com",
                subject="Test",
                html_content="<p>Hi</p>",
                cc_emails=["cc1@example.com", "cc2@example.com"],
            )

        assert msg["Cc"] == "cc1@example.com, cc2@example.com"

    def test_no_cc_header_when_no_cc_emails(self):
        svc = _dev_email_service()

        with patch("app.services.email.settings") as mock_settings:
            mock_settings.SMTP_FROM_EMAIL = "noreply@simsplus.io"
            mock_settings.SMTP_FROM_NAME = "SIMS Plus"

            msg = svc._create_message(
                to_email="test@example.com",
                subject="Test",
                html_content="<p>Hi</p>",
            )

        assert msg["Cc"] is None

    def test_includes_text_and_html_parts(self):
        svc = _dev_email_service()

        with patch("app.services.email.settings") as mock_settings:
            mock_settings.SMTP_FROM_EMAIL = "noreply@simsplus.io"
            mock_settings.SMTP_FROM_NAME = "SIMS Plus"

            msg = svc._create_message(
                to_email="test@example.com",
                subject="Test",
                html_content="<p>Hello HTML</p>",
                text_content="Hello Plain",
            )

        # multipart/alternative should have two sub-parts: text and html
        payloads = msg.get_payload()
        content_types = [p.get_content_type() for p in payloads]
        assert "text/plain" in content_types
        assert "text/html" in content_types
