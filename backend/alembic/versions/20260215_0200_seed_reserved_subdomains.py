"""Seed reserved subdomains table.

Populates the reserved_subdomains table with 35 entries that prevent schools
from registering subdomains that conflict with system URLs (www, api, admin, etc.).

Uses ON CONFLICT (subdomain) DO NOTHING so this migration is idempotent and safe
to re-run.

Revision ID: seed_reserved_subdomains
Revises: hardened_rls_policies
"""
from alembic import op
from sqlalchemy import text

revision = "seed_reserved_subdomains"
down_revision = "hardened_rls_policies"
branch_labels = None
depends_on = None

RESERVED_SUBDOMAINS = [
    ("www", "Main website"),
    ("app", "Application portal"),
    ("api", "API endpoint"),
    ("admin", "Admin portal"),
    ("mail", "Email services"),
    ("ftp", "FTP services"),
    ("status", "Status page"),
    ("blog", "Blog"),
    ("help", "Help center"),
    ("support", "Support portal"),
    ("docs", "Documentation"),
    ("cdn", "Content delivery"),
    ("assets", "Static assets"),
    ("staging", "Staging environment"),
    ("dev", "Development environment"),
    ("test", "Testing environment"),
    ("demo", "Demo environment"),
    ("sandbox", "Sandbox environment"),
    ("beta", "Beta environment"),
    ("alpha", "Alpha environment"),
    ("portal", "Generic portal"),
    ("login", "Login page"),
    ("register", "Registration page"),
    ("signup", "Signup page"),
    ("dashboard", "Dashboard"),
    ("billing", "Billing portal"),
    ("payments", "Payments"),
    ("webhooks", "Webhook endpoints"),
    ("graphql", "GraphQL endpoint"),
    ("ws", "WebSocket endpoint"),
    ("static", "Static files"),
    ("media", "Media files"),
    ("images", "Image files"),
    ("files", "File storage"),
    ("downloads", "Downloads"),
    ("uploads", "Uploads"),
]


def upgrade() -> None:
    connection = op.get_bind()
    for subdomain, reason in RESERVED_SUBDOMAINS:
        connection.execute(
            text("""
                INSERT INTO reserved_subdomains (id, subdomain, reason, created_at, updated_at)
                VALUES (gen_random_uuid(), :subdomain, :reason, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (subdomain) DO NOTHING
            """),
            {"subdomain": subdomain, "reason": reason},
        )


def downgrade() -> None:
    connection = op.get_bind()
    subdomains = [s[0] for s in RESERVED_SUBDOMAINS]
    for sub in subdomains:
        connection.execute(
            text("DELETE FROM reserved_subdomains WHERE subdomain = :sub"),
            {"sub": sub},
        )
