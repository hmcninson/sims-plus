"""
SIMS Plus - Email Service

Handles sending emails via SMTP with template support.
"""

import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "email"


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

    def _create_message(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> MIMEMultipart:
        """Create a MIME message for sending."""
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        message["To"] = to_email

        # Add plain text part (fallback)
        if text_content:
            text_part = MIMEText(text_content, "plain", "utf-8")
            message.attach(text_part)

        # Add HTML part
        html_part = MIMEText(html_content, "html", "utf-8")
        message.attach(html_part)

        return message

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """
        Send an email via SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML body content
            text_content: Optional plain text body

        Returns:
            True if sent successfully
        """
        # In development, log the email instead of sending
        if settings.is_development and not settings.SMTP_HOST:
            logger.info(
                f"\n{'='*60}\n"
                f"[DEV EMAIL] Would send email:\n"
                f"To: {to_email}\n"
                f"Subject: {subject}\n"
                f"{'='*60}\n"
                f"{html_content[:1000]}...\n"
                f"{'='*60}\n"
            )
            return True

        # Check if SMTP is configured
        if not settings.SMTP_HOST:
            logger.warning("SMTP not configured. Email not sent.")
            return False

        try:
            message = self._create_message(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
            )

            # Send via SMTP
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USERNAME,
                password=settings.SMTP_PASSWORD,
                use_tls=settings.SMTP_USE_TLS,
                start_tls=settings.SMTP_START_TLS,
            )

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except aiosmtplib.SMTPException as e:
            logger.error(f"SMTP error sending email to {to_email}: {e}")
            return False
        except Exception as e:
            logger.exception(f"Failed to send email to {to_email}: {e}")
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
        except Exception as e:
            logger.error(f"Failed to render welcome email template: {e}")
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
        trial_section = ""
        if trial_ends_at:
            trial_section = f"<p>Your free trial ends on <strong>{trial_ends_at}</strong>.</p>"

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

                <p>Dear {admin_name},</p>

                <p>Congratulations! Your school <strong>{school_name}</strong> has been
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
                <p>Portal URL: <a href="{portal_url}">{portal_url}</a></p>

                <h2 style="color: #1B4F72;">Login Details</h2>
                <p>
                    <strong>Email:</strong> {admin_email}<br>
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
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h1 style="color: #1B4F72;">Password Reset Request</h1>
                    <p>Dear {user_name},</p>
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


# Singleton instance
email_service = EmailService()
