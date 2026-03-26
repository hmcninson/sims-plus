"""
SIMS Plus - Email Service

Handles sending emails via SMTP with template support.
"""

from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import html
import re

import aiosmtplib
import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from app.config import settings

logger = structlog.get_logger()

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "email"

# Validates that a color string is a safe hex value (e.g. #1B4F72)
# to prevent CSS injection via background-color property
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3,6}$")


class EmailError(Exception):
    """Email operation failed."""

    def __init__(self, message: str, code: str = "email_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class EmailService:
    """
    Service for sending emails via SMTP.

    Uses aiosmtplib for async SMTP operations.
    In development mode, logs emails instead of sending.
    """

    def __init__(self):
        self._jinja_env: Optional[Environment] = None

    @property
    def jinja_env(self) -> Environment:
        """Get Jinja2 environment for templates."""
        if self._jinja_env is None:
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(TEMPLATE_DIR)),
                autoescape=select_autoescape(["html", "xml"]),
            )
        return self._jinja_env

    def _render_template(self, template_name: str, **context) -> str:
        """Render an email template with context."""
        template = self.jinja_env.get_template(template_name)
        return template.render(**context)

    def render_branded_email(
        self,
        body_html: str,
        school_name: str,
        school_logo_url: Optional[str] = None,
        school_primary_color: Optional[str] = None,
    ) -> str:
        """
        Wrap raw HTML body content in the branded email base template.

        This allows admin-composed emails (from the messaging module) to
        include consistent school branding — header bar with logo/name and
        a standard footer — without requiring each caller to build the
        full HTML scaffold.

        Args:
            body_html: The inner HTML content (already escaped or trusted).
            school_name: School name for the header.
            school_logo_url: Optional logo URL for the header.
            school_primary_color: Optional hex color for the header bar.

        Returns:
            Complete HTML email string with branding wrapper.
        """
        try:
            # Sanitize color to prevent CSS injection (e.g. "red; background-image: url(…)")
            if school_primary_color and not _HEX_COLOR_RE.match(school_primary_color):
                school_primary_color = None  # fall back to template default #1B4F72

            # Build a school-like context dict for the template
            school_ctx = {
                "name": school_name,
                "logo_url": school_logo_url,
                "primary_color": school_primary_color,
            }

            # The body_html is pre-composed content, so we render the base
            # template with a special content block override via a child
            # template string approach. Since Jinja2 block inheritance
            # requires file-based templates, we use a simpler approach:
            # render the base template and inject the body via a variable.
            wrapper_source = (
                '{%- extends "_email_base.html" -%}'
                "{% block content %}{{ body_content }}{% endblock %}"
            )
            wrapper_template = self.jinja_env.from_string(wrapper_source)
            return wrapper_template.render(
                school=school_ctx,
                # Mark body_html as safe since it is pre-composed HTML from
                # the admin compose form, not raw user input. The compose
                # endpoint controls what HTML is accepted.
                body_content=Markup(body_html),
                current_year=datetime.now().year,
            )
        except Exception:
            logger.warning(
                "branded_email_render_failed",
                school_name=school_name,
                exc_info=True,
            )
            # Graceful fallback: return the raw body without branding
            return body_html

    def _create_message(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        attachments: Optional[list[tuple[bytes, str, str]]] = None,
        cc_emails: Optional[list[str]] = None,
    ) -> MIMEMultipart:
        """
        Create a MIME message for sending.

        Args:
            to_email: Recipient email
            subject: Email subject
            html_content: HTML body
            text_content: Plain text body (fallback)
            attachments: List of (data, filename, mime_type) tuples
            cc_emails: List of CC email addresses
        """
        # Use mixed for attachments, alternative for content only
        if attachments:
            message = MIMEMultipart("mixed")
            # Create alternative part for text/html
            alt_part = MIMEMultipart("alternative")
            if text_content:
                text_part = MIMEText(text_content, "plain", "utf-8")
                alt_part.attach(text_part)
            html_part = MIMEText(html_content, "html", "utf-8")
            alt_part.attach(html_part)
            message.attach(alt_part)

            # Add attachments
            for data, filename, mime_type in attachments:
                main_type, sub_type = mime_type.split("/", 1)
                attachment = MIMEApplication(data, _subtype=sub_type)
                attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=filename,
                )
                message.attach(attachment)
        else:
            message = MIMEMultipart("alternative")
            if text_content:
                text_part = MIMEText(text_content, "plain", "utf-8")
                message.attach(text_part)
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)

        message["Subject"] = subject
        message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        message["To"] = to_email
        if cc_emails:
            message["Cc"] = ", ".join(cc_emails)

        return message

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        attachments: Optional[list[tuple[bytes, str, str]]] = None,
        cc_emails: Optional[list[str]] = None,
    ) -> bool:
        """
        Send an email via SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML body content
            text_content: Optional plain text body
            attachments: Optional list of (data, filename, mime_type) tuples
            cc_emails: Optional list of CC email addresses

        Returns:
            True if sent successfully
        """
        # In development, log the email instead of sending
        if settings.is_development and not settings.SMTP_HOST:
            attachment_info = ""
            cc_info = ""
            if attachments:
                attachment_info = f"Attachments: {[a[1] for a in attachments]}\n"
            if cc_emails:
                cc_info = f"CC: {', '.join(cc_emails)}\n"
            logger.info(
                "dev_email_skipped",
                to=to_email,
                subject=subject,
                cc=cc_emails or [],
                attachments=[a[1] for a in attachments] if attachments else [],
            )
            return True

        # Check if SMTP is configured
        if not settings.SMTP_HOST:
            logger.warning("smtp_not_configured", to=to_email)
            return False

        try:
            message = self._create_message(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
                attachments=attachments,
                cc_emails=cc_emails,
            )

            # Build list of all recipients (To + CC)
            all_recipients = [to_email]
            if cc_emails:
                all_recipients.extend(cc_emails)

            # Send via SMTP
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USERNAME,
                password=settings.SMTP_PASSWORD,
                use_tls=settings.SMTP_USE_TLS,
                start_tls=settings.SMTP_START_TLS,
                recipients=all_recipients,
            )

            logger.info("email_sent", to=to_email, cc=cc_emails or [])
            return True

        except aiosmtplib.SMTPException:
            logger.error("smtp_error", to=to_email, exc_info=True)
            return False
        except Exception:
            logger.exception("email_send_failed", to=to_email)
            return False

    async def send_welcome_email(
        self,
        to_email: str,
        admin_name: str,
        school_name: str,
        subdomain: str,
        trial_ends_at: Optional[datetime] = None,
    ) -> bool:
        """
        Send welcome email after school registration.

        Args:
            to_email: Admin email address
            admin_name: Admin's full name
            school_name: Name of the school
            subdomain: School's subdomain
            trial_ends_at: Trial end date (if applicable)

        Returns:
            True if sent successfully
        """
        # Build portal URL
        if settings.is_production:
            portal_url = f"https://{subdomain}.simsplus.io"
        else:
            portal_url = f"http://localhost:3000"

        # Format trial end date
        trial_end_str = None
        if trial_ends_at:
            trial_end_str = trial_ends_at.strftime("%B %d, %Y")

        # Render email template
        try:
            html_content = self._render_template(
                "welcome.html",
                admin_name=admin_name,
                school_name=school_name,
                subdomain=subdomain,
                portal_url=portal_url,
                admin_email=to_email,
                trial_ends_at=trial_end_str,
                current_year=datetime.now().year,
            )
        except Exception:
            logger.error("welcome_email_template_render_failed", exc_info=True)
            # Fallback to plain text
            html_content = self._get_welcome_email_fallback(
                admin_name=admin_name,
                school_name=school_name,
                portal_url=portal_url,
                admin_email=to_email,
                trial_ends_at=trial_end_str,
            )

        subject = f"Welcome to SIMS Plus - {school_name} is Ready!"

        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
        )

    def _get_welcome_email_fallback(
        self,
        admin_name: str,
        school_name: str,
        portal_url: str,
        admin_email: str,
        trial_ends_at: Optional[str] = None,
    ) -> str:
        """Get fallback HTML content if template fails."""
        safe_name = html.escape(admin_name)
        safe_school = html.escape(school_name)
        safe_email = html.escape(admin_email)

        trial_section = ""
        if trial_ends_at:
            safe_trial = html.escape(trial_ends_at)
            trial_section = f"<p>Your free trial ends on <strong>{safe_trial}</strong>.</p>"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Welcome to SIMS Plus</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #1B4F72;">Welcome to SIMS Plus!</h1>

                <p>Dear {safe_name},</p>

                <p>Congratulations! Your school <strong>{safe_school}</strong> has been
                successfully registered on SIMS Plus.</p>

                <h2 style="color: #1B4F72;">Your School Portal</h2>
                <p>
                    <a href="{portal_url}"
                       style="display: inline-block; padding: 12px 24px;
                              background-color: #1B4F72; color: white;
                              text-decoration: none; border-radius: 4px;">
                        Access Your Portal
                    </a>
                </p>
                <p>Portal URL: <a href="{portal_url}">{html.escape(portal_url)}</a></p>

                <h2 style="color: #1B4F72;">Login Details</h2>
                <p>
                    <strong>Email:</strong> {safe_email}<br>
                    <strong>Password:</strong> The password you created during registration
                </p>

                {trial_section}

                <h2 style="color: #1B4F72;">Getting Started</h2>
                <ol>
                    <li>Login to your portal</li>
                    <li>Complete your school profile</li>
                    <li>Set up academic year and terms</li>
                    <li>Add your classes and subjects</li>
                    <li>Start adding students and staff</li>
                </ol>

                <p>If you need any help, please contact us at
                <a href="mailto:support@simsplus.io">support@simsplus.io</a></p>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

                <p style="color: #666; font-size: 12px;">
                    This email was sent by SIMS Plus.<br>
                    &copy; {datetime.now().year} SIMS Plus. All rights reserved.
                </p>
            </div>
        </body>
        </html>
        """

    async def send_user_credentials_email(
        self,
        to_email: str,
        user_name: str,
        password: str,
        role: str,
        school_name: str,
        portal_url: str,
    ) -> bool:
        """
        Send login credentials to a newly created user.

        Args:
            to_email: User's email address
            user_name: User's full name
            password: Temporary password
            role: User's role
            school_name: Name of the school
            portal_url: URL to access the portal

        Returns:
            True if sent successfully
        """
        safe_user = html.escape(user_name)
        safe_school = html.escape(school_name)
        safe_email = html.escape(to_email)
        safe_password = html.escape(password)
        safe_role = html.escape(role)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Your SIMS Plus Account</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #1B4F72;">Welcome to SIMS Plus!</h1>

                <p>Dear {safe_user},</p>

                <p>An account has been created for you at <strong>{safe_school}</strong> on SIMS Plus.</p>

                <h2 style="color: #1B4F72;">Your Login Credentials</h2>
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 4px; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Email:</strong> {safe_email}</p>
                    <p style="margin: 5px 0;"><strong>Password:</strong> {safe_password}</p>
                    <p style="margin: 5px 0;"><strong>Role:</strong> {safe_role}</p>
                </div>

                <p>
                    <a href="{portal_url}"
                       style="display: inline-block; padding: 12px 24px;
                              background-color: #1B4F72; color: white;
                              text-decoration: none; border-radius: 4px;">
                        Login to Your Account
                    </a>
                </p>

                <p style="color: #e74c3c; font-weight: bold;">
                    Important: Please change your password after your first login.
                </p>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

                <p style="color: #666; font-size: 12px;">
                    This email was sent by SIMS Plus.<br>
                    If you did not expect this email, please contact your school administrator.<br>
                    &copy; {datetime.now().year} SIMS Plus. All rights reserved.
                </p>
            </div>
        </body>
        </html>
        """

        return await self.send_email(
            to_email=to_email,
            subject=f"Your SIMS Plus Account - {school_name}",
            html_content=html_content,
        )

    async def send_password_reset_email(
        self,
        to_email: str,
        user_name: str,
        reset_url: str,
        expires_in_hours: int = 24,
    ) -> bool:
        """
        Send password reset email.

        Args:
            to_email: User's email address
            user_name: User's name
            reset_url: Password reset URL with token
            expires_in_hours: Hours until link expires

        Returns:
            True if sent successfully
        """
        try:
            html_content = self._render_template(
                "password_reset.html",
                user_name=user_name,
                reset_url=reset_url,
                expires_in_hours=expires_in_hours,
                current_year=datetime.now().year,
            )
        except Exception:
            # Fallback
            safe_user = html.escape(user_name)
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h1 style="color: #1B4F72;">Password Reset Request</h1>
                    <p>Dear {safe_user},</p>
                    <p>We received a request to reset your password. Click the button below to reset it:</p>
                    <p>
                        <a href="{reset_url}"
                           style="display: inline-block; padding: 12px 24px;
                                  background-color: #1B4F72; color: white;
                                  text-decoration: none; border-radius: 4px;">
                            Reset Password
                        </a>
                    </p>
                    <p>This link will expire in {expires_in_hours} hours.</p>
                    <p>If you didn't request this, please ignore this email.</p>
                    <p style="color: #666; font-size: 12px;">
                        &copy; {datetime.now().year} SIMS Plus
                    </p>
                </div>
            </body>
            </html>
            """

        return await self.send_email(
            to_email=to_email,
            subject="Reset Your SIMS Plus Password",
            html_content=html_content,
        )

    async def send_attendance_alert(
        self,
        to_email: str,
        student_name: str,
        date: str,
        status: str,
        school_name: str,
    ) -> bool:
        """Send attendance alert to parent/guardian."""
        safe_school = html.escape(school_name)
        safe_student = html.escape(student_name)
        safe_status = html.escape(status)
        safe_date = html.escape(date)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>Attendance Alert</title></head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #1B4F72; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">{safe_school}</h1>
                    <p style="margin: 5px 0 0 0; opacity: 0.9;">Attendance Notification</p>
                </div>
                <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none;">
                    <p>Dear Parent/Guardian,</p>
                    <p>This is to inform you that <strong>{safe_student}</strong> was marked as
                    <strong style="color: #dc2626;">{safe_status}</strong> on <strong>{safe_date}</strong>.</p>
                    <p>If you believe this is an error, please contact the school administration.</p>
                    <p>Best regards,<br><strong>{safe_school}</strong></p>
                </div>
                <div style="text-align: center; padding: 20px; color: #666; font-size: 12px;">
                    <p>&copy; {datetime.now().year} SIMS Plus</p>
                </div>
            </div>
        </body>
        </html>
        """
        return await self.send_email(
            to_email=to_email,
            subject=f"Attendance Alert - {student_name} | {school_name}",
            html_content=html_content,
        )

    async def send_exam_results_notification(
        self,
        to_email: str,
        student_name: str,
        exam_name: str,
        school_name: str,
    ) -> bool:
        """Send exam results availability notification."""
        safe_school = html.escape(school_name)
        safe_student = html.escape(student_name)
        safe_exam = html.escape(exam_name)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>Exam Results</title></head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #1B4F72; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">{safe_school}</h1>
                    <p style="margin: 5px 0 0 0; opacity: 0.9;">Exam Results Notification</p>
                </div>
                <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none;">
                    <p>Dear Parent/Guardian,</p>
                    <p>The results for <strong>{safe_exam}</strong> are now available for <strong>{safe_student}</strong>.</p>
                    <p>Please log in to the parent portal to view the detailed results and report card.</p>
                    <p>Best regards,<br><strong>{safe_school}</strong></p>
                </div>
                <div style="text-align: center; padding: 20px; color: #666; font-size: 12px;">
                    <p>&copy; {datetime.now().year} SIMS Plus</p>
                </div>
            </div>
        </body>
        </html>
        """
        return await self.send_email(
            to_email=to_email,
            subject=f"Exam Results Available - {student_name} | {school_name}",
            html_content=html_content,
        )

    async def send_fee_reminder(
        self,
        to_email: str,
        student_name: str,
        amount_due: float,
        currency: str,
        due_date: str,
        school_name: str,
    ) -> bool:
        """Send fee payment reminder."""
        safe_school = html.escape(school_name)
        safe_student = html.escape(student_name)
        safe_currency = html.escape(currency)
        safe_due_date = html.escape(due_date)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>Fee Reminder</title></head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #1B4F72; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">{safe_school}</h1>
                    <p style="margin: 5px 0 0 0; opacity: 0.9;">Fee Payment Reminder</p>
                </div>
                <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none;">
                    <p>Dear Parent/Guardian,</p>
                    <p>This is a reminder that there is an outstanding balance for <strong>{safe_student}</strong>.</p>
                    <div style="background-color: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">
                        <p style="color: #666; margin: 0;">Amount Due</p>
                        <p style="font-size: 28px; font-weight: bold; color: #dc2626; margin: 10px 0;">{safe_currency} {amount_due:,.2f}</p>
                        <p style="color: #666; margin: 0;">Due by: {safe_due_date}</p>
                    </div>
                    <p>Please make payment at your earliest convenience to avoid any disruption.</p>
                    <p>Best regards,<br><strong>{safe_school}</strong></p>
                </div>
                <div style="text-align: center; padding: 20px; color: #666; font-size: 12px;">
                    <p>&copy; {datetime.now().year} SIMS Plus</p>
                </div>
            </div>
        </body>
        </html>
        """
        return await self.send_email(
            to_email=to_email,
            subject=f"Fee Payment Reminder - {student_name} | {school_name}",
            html_content=html_content,
        )

    async def send_user_invite(
        self,
        to_email: str,
        inviter_name: str,
        school_name: str,
        temp_password: str,
        role: str,
        portal_url: str,
    ) -> bool:
        """Send account invitation email to a new user."""
        safe_inviter = html.escape(inviter_name)
        safe_school = html.escape(school_name)
        safe_email = html.escape(to_email)
        safe_password = html.escape(temp_password)
        safe_role = html.escape(role)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>Account Invitation</title></head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #1B4F72; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">You're Invited!</h1>
                    <p style="margin: 5px 0 0 0; opacity: 0.9;">{safe_school} on SIMS Plus</p>
                </div>
                <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none;">
                    <p>Hello,</p>
                    <p><strong>{safe_inviter}</strong> has invited you to join <strong>{safe_school}</strong> on SIMS Plus as a <strong>{safe_role}</strong>.</p>
                    <div style="background-color: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin: 20px 0;">
                        <h3 style="color: #1B4F72; margin-top: 0;">Your Login Credentials</h3>
                        <p><strong>Email:</strong> {safe_email}</p>
                        <p><strong>Temporary Password:</strong> {safe_password}</p>
                    </div>
                    <p style="text-align: center;">
                        <a href="{portal_url}"
                           style="display: inline-block; padding: 12px 24px;
                                  background-color: #1B4F72; color: white;
                                  text-decoration: none; border-radius: 4px;">
                            Login to SIMS Plus
                        </a>
                    </p>
                    <p style="color: #e74c3c; font-weight: bold;">Please change your password after your first login.</p>
                    <p>Best regards,<br><strong>{safe_school}</strong></p>
                </div>
                <div style="text-align: center; padding: 20px; color: #666; font-size: 12px;">
                    <p>&copy; {datetime.now().year} SIMS Plus</p>
                </div>
            </div>
        </body>
        </html>
        """
        return await self.send_email(
            to_email=to_email,
            subject=f"You're Invited to {school_name} | SIMS Plus",
            html_content=html_content,
        )

    async def send_invoice_email(
        self,
        to_email: str,
        recipient_name: str,
        student_name: str,
        invoice_number: str,
        total_amount: float,
        balance_due: float,
        currency: str,
        due_date: Optional[str],
        school_name: str,
        pdf_data: bytes,
        pdf_filename: str,
        cc_emails: Optional[list[str]] = None,
    ) -> bool:
        """
        Send invoice email with PDF attachment.

        Args:
            to_email: Recipient email address
            recipient_name: Recipient's name (guardian/parent)
            student_name: Student's full name
            invoice_number: Invoice number
            total_amount: Total invoice amount
            balance_due: Outstanding balance
            currency: Currency code (e.g., GHS)
            due_date: Due date string (formatted)
            school_name: Name of the school
            pdf_data: PDF file bytes
            pdf_filename: PDF filename
            cc_emails: Optional list of CC email addresses

        Returns:
            True if sent successfully
        """
        safe_school = html.escape(school_name)
        safe_recipient = html.escape(recipient_name)
        safe_student = html.escape(student_name)
        safe_invoice = html.escape(invoice_number)
        safe_currency = html.escape(currency)

        due_date_section = ""
        if due_date:
            safe_due_date = html.escape(due_date)
            due_date_section = f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Due Date:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{safe_due_date}</td>
            </tr>
            """

        status_color = "#22c55e" if balance_due <= 0 else "#f59e0b"
        status_text = "PAID" if balance_due <= 0 else f"{safe_currency} {balance_due:,.2f}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Invoice from {safe_school}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <!-- Header -->
                <div style="background-color: #1B4F72; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">{safe_school}</h1>
                    <p style="margin: 5px 0 0 0; opacity: 0.9;">Invoice Notification</p>
                </div>

                <!-- Content -->
                <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none;">
                    <p>Dear {safe_recipient},</p>

                    <p>Please find attached the invoice for <strong>{safe_student}</strong>.</p>

                    <!-- Invoice Summary Box -->
                    <div style="background-color: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin: 20px 0;">
                        <h2 style="color: #1B4F72; margin-top: 0; font-size: 18px; border-bottom: 2px solid #1B4F72; padding-bottom: 10px;">
                            Invoice Summary
                        </h2>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Invoice Number:</strong></td>
                                <td style="padding: 8px; border-bottom: 1px solid #eee;">{safe_invoice}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Student:</strong></td>
                                <td style="padding: 8px; border-bottom: 1px solid #eee;">{safe_student}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Total Amount:</strong></td>
                                <td style="padding: 8px; border-bottom: 1px solid #eee;">{safe_currency} {total_amount:,.2f}</td>
                            </tr>
                            {due_date_section}
                            <tr>
                                <td style="padding: 8px;"><strong>Balance Due:</strong></td>
                                <td style="padding: 8px; color: {status_color}; font-weight: bold; font-size: 16px;">{status_text}</td>
                            </tr>
                        </table>
                    </div>

                    <p>The detailed invoice is attached to this email as a PDF document.</p>

                    <p style="color: #666;">
                        If you have any questions about this invoice, please contact the school administration.
                    </p>

                    <p>Thank you for your continued support.</p>

                    <p>
                        Best regards,<br>
                        <strong>{safe_school}</strong>
                    </p>
                </div>

                <!-- Footer -->
                <div style="text-align: center; padding: 20px; color: #666; font-size: 12px;">
                    <p style="margin: 0;">This email was sent by SIMS Plus on behalf of {safe_school}</p>
                    <p style="margin: 5px 0 0 0;">&copy; {datetime.now().year} SIMS Plus. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Plain text version (no HTML escaping needed for plain text)
        text_content = f"""
Dear {recipient_name},

Please find attached the invoice for {student_name}.

Invoice Summary:
- Invoice Number: {invoice_number}
- Student: {student_name}
- Total Amount: {currency} {total_amount:,.2f}
- Balance Due: {"PAID" if balance_due <= 0 else f"{currency} {balance_due:,.2f}"}
{f"- Due Date: {due_date}" if due_date else ""}

The detailed invoice is attached to this email as a PDF document.

If you have any questions about this invoice, please contact the school administration.

Thank you for your continued support.

Best regards,
{school_name}
        """

        # Prepare attachment
        attachments = [(pdf_data, pdf_filename, "application/pdf")]

        return await self.send_email(
            to_email=to_email,
            subject=f"Invoice {invoice_number} from {school_name}",
            html_content=html_content,
            text_content=text_content,
            attachments=attachments,
            cc_emails=cc_emails,
        )


# Singleton instance
email_service = EmailService()
