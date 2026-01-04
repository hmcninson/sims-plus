"""
SIMS Plus - Reserved Subdomain Model

Stores subdomains that cannot be used by tenants (e.g., www, api, admin).
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReservedSubdomain(Base):
    """
    Reserved subdomain model.

    Stores subdomains that are reserved for system use
    and cannot be registered by schools.
    """

    __tablename__ = "reserved_subdomains"

    subdomain: Mapped[str] = mapped_column(
        String(63),
        unique=True,
        nullable=False,
        index=True,
        comment="Reserved subdomain (e.g., www, api, admin)",
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for reservation",
    )

    def __repr__(self) -> str:
        return f"<ReservedSubdomain(subdomain='{self.subdomain}')>"


# Default reserved subdomains to seed
DEFAULT_RESERVED_SUBDOMAINS = [
    {"subdomain": "www", "reason": "Main website"},
    {"subdomain": "api", "reason": "API endpoint"},
    {"subdomain": "app", "reason": "Application portal"},
    {"subdomain": "admin", "reason": "Admin portal"},
    {"subdomain": "mail", "reason": "Email services"},
    {"subdomain": "ftp", "reason": "FTP services"},
    {"subdomain": "status", "reason": "Status page"},
    {"subdomain": "blog", "reason": "Blog"},
    {"subdomain": "help", "reason": "Help center"},
    {"subdomain": "support", "reason": "Support portal"},
    {"subdomain": "docs", "reason": "Documentation"},
    {"subdomain": "cdn", "reason": "Content delivery"},
    {"subdomain": "assets", "reason": "Static assets"},
    {"subdomain": "staging", "reason": "Staging environment"},
    {"subdomain": "dev", "reason": "Development environment"},
    {"subdomain": "test", "reason": "Testing environment"},
    {"subdomain": "demo", "reason": "Demo environment"},
    {"subdomain": "sandbox", "reason": "Sandbox environment"},
    {"subdomain": "beta", "reason": "Beta environment"},
    {"subdomain": "alpha", "reason": "Alpha environment"},
    {"subdomain": "portal", "reason": "Generic portal"},
    {"subdomain": "login", "reason": "Login page"},
    {"subdomain": "register", "reason": "Registration page"},
    {"subdomain": "signup", "reason": "Signup page"},
    {"subdomain": "dashboard", "reason": "Dashboard"},
    {"subdomain": "billing", "reason": "Billing portal"},
    {"subdomain": "payments", "reason": "Payments"},
    {"subdomain": "webhooks", "reason": "Webhook endpoints"},
    {"subdomain": "graphql", "reason": "GraphQL endpoint"},
    {"subdomain": "ws", "reason": "WebSocket endpoint"},
    {"subdomain": "static", "reason": "Static files"},
    {"subdomain": "media", "reason": "Media files"},
    {"subdomain": "images", "reason": "Image files"},
    {"subdomain": "files", "reason": "File storage"},
    {"subdomain": "downloads", "reason": "Downloads"},
    {"subdomain": "uploads", "reason": "Uploads"},
]
