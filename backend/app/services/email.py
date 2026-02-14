"""
SIMS Plus - Email Service

Handles sending emails via SMTP with template support.
"""

import logging
from datetime import datetime
from email.mime.application import MIMEApplication
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
                f"\n{'='*60}\n"
                f"[DEV EMAIL] Would send email:\n"
                f"To: {to_email}\n"
                f"{cc_info}"
                f"Subject: {subject}\n"
                f"{attachment_info}"
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

            cc_log = f" (CC: {', '.join(cc_emails)})" if cc_emails else ""
            logger.info(f"Email sent successfully to {to_email}{cc_log}")
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

                <p>Dear {user_name},</p>

                <p>An account has been created for you at <strong>{school_name}</strong> on SIMS Plus.</p>

                <h2 style="color: #1B4F72;">Your Login Credentials</h2>
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 4px; margin: 20px 0;">
                    <p style="margin: 5px 0;"><strong>Email:</strong> {to_email}</p>
                    <p style="margin: 5px 0;"><strong>Password:</strong> {password}</p>
                    <p style="margin: 5px 0;"><strong>Role:</strong> {role}</p>
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
        due_date_section = ""
        if due_date:
            due_date_section = f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Due Date:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{due_date}</td>
            </tr>
            """

        status_color = "#22c55e" if balance_due <= 0 else "#f59e0b"
        status_text = "PAID" if balance_due <= 0 else f"{currency} {balance_due:,.2f}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Invoice from {school_name}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <!-- Header -->
                <div style="background-color: #1B4F72; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">{school_name}</h1>
                    <p style="margin: 5px 0 0 0; opacity: 0.9;">Invoice Notification</p>
                </div>

                <!-- Content -->
                <div style="background-color: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none;">
                    <p>Dear {recipient_name},</p>

                    <p>Please find attached the invoice for <strong>{student_name}</strong>.</p>

                    <!-- Invoice Summary Box -->
                    <div style="background-color: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin: 20px 0;">
                        <h2 style="color: #1B4F72; margin-top: 0; font-size: 18px; border-bottom: 2px solid #1B4F72; padding-bottom: 10px;">
                            Invoice Summary
                        </h2>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Invoice Number:</strong></td>
                                <td style="padding: 8px; border-bottom: 1px solid #eee;">{invoice_number}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Student:</strong></td>
                                <td style="padding: 8px; border-bottom: 1px solid #eee;">{student_name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Total Amount:</strong></td>
                                <td style="padding: 8px; border-bottom: 1px solid #eee;">{currency} {total_amount:,.2f}</td>
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
                        <strong>{school_name}</strong>
                    </p>
                </div>

                <!-- Footer -->
                <div style="text-align: center; padding: 20px; color: #666; font-size: 12px;">
                    <p style="margin: 0;">This email was sent by SIMS Plus on behalf of {school_name}</p>
                    <p style="margin: 5px 0 0 0;">&copy; {datetime.now().year} SIMS Plus. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Plain text version
        text_content = f"""
Dear {recipient_name},

Please find attached the invoice for {student_name}.

Invoice Summary:
- Invoice Number: {invoice_number}
- Student: {student_name}
- Total Amount: {currency} {total_amount:,.2f}
- Balance Due: {status_text}
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
