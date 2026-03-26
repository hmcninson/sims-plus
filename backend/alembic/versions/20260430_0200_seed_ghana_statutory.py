"""Staff HR Gap Closure Phase 4A: Seed Ghana Statutory Data

Seeds per-tenant:
  - 7 PAYE tax brackets (GRA 2024 monthly rates)
  - 5 bank file config presets (GCB, Ecobank, Stanbic, Fidelity, CalBank)

Revision ID: 20260430_0200
Revises: 20260430_0100
Create Date: 2026-04-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260430_0200"
down_revision: Union[str, None] = "20260430_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # Seed PAYE tax brackets (GRA 2024 monthly rates) for all tenants
    # ------------------------------------------------------------------
    conn.execute(sa.text("""
        INSERT INTO tax_brackets (
            id, tenant_id, effective_year, band_number,
            lower_limit, upper_limit, rate, cumulative_tax, is_active
        )
        SELECT
            gen_random_uuid(),
            t.id,
            2024,
            b.band_number,
            b.lower_limit,
            b.upper_limit,
            b.rate,
            b.cumulative_tax,
            true
        FROM tenants t
        CROSS JOIN (
            VALUES
                (1, 0.00,       490.00,     0.0000, 0.00),
                (2, 490.00,     600.00,     0.0500, 0.00),
                (3, 600.00,     730.00,     0.1000, 5.50),
                (4, 730.00,     3896.67,    0.1750, 18.50),
                (5, 3896.67,    19896.67,   0.2500, 572.67),
                (6, 19896.67,   50290.00,   0.3000, 4572.67),
                (7, 50290.00,   NULL,       0.3500, 13690.67)
        ) AS b(band_number, lower_limit, upper_limit, rate, cumulative_tax)
        WHERE t.status IN ('active', 'trial')
        ON CONFLICT (tenant_id, effective_year, band_number) DO NOTHING
    """))

    # ------------------------------------------------------------------
    # Seed bank file config presets for all tenants
    # ------------------------------------------------------------------

    # GCB Bank (CSV)
    conn.execute(sa.text("""
        INSERT INTO bank_file_configs (
            id, tenant_id, bank_name, file_format, delimiter,
            column_mapping, include_header_row, date_format, amount_format,
            encoding, is_default
        )
        SELECT
            gen_random_uuid(),
            t.id,
            'GCB Bank',
            'csv',
            ',',
            '[
                {"header": "Beneficiary Name", "source": "staff_name", "width": null},
                {"header": "Account Number", "source": "account_number", "width": null},
                {"header": "Bank Code", "source": "template", "template": "040", "width": null},
                {"header": "Branch Code", "source": "template", "template": "001", "width": null},
                {"header": "Amount", "source": "net_salary", "format": "decimal_2", "width": null},
                {"header": "Narration", "source": "template", "template": "{month_name} {year} Salary", "width": null}
            ]'::jsonb,
            true,
            'YYYY-MM-DD',
            'decimal',
            'utf-8',
            true
        FROM tenants t
        WHERE t.status IN ('active', 'trial')
        ON CONFLICT DO NOTHING
    """))

    # Ecobank (CSV)
    conn.execute(sa.text("""
        INSERT INTO bank_file_configs (
            id, tenant_id, bank_name, file_format, delimiter,
            column_mapping, include_header_row, date_format, amount_format,
            encoding, is_default
        )
        SELECT
            gen_random_uuid(),
            t.id,
            'Ecobank',
            'csv',
            ',',
            '[
                {"header": "Account Number", "source": "account_number", "width": null},
                {"header": "Beneficiary Name", "source": "staff_name", "width": null},
                {"header": "Amount", "source": "net_salary", "format": "decimal_2", "width": null},
                {"header": "Currency", "source": "template", "template": "GHS", "width": null},
                {"header": "Reference", "source": "template", "template": "{month_short}{year}-SAL-{staff_code}", "width": null}
            ]'::jsonb,
            true,
            'YYYY-MM-DD',
            'decimal',
            'utf-8',
            false
        FROM tenants t
        WHERE t.status IN ('active', 'trial')
        ON CONFLICT DO NOTHING
    """))

    # Stanbic Bank (pipe-delimited)
    conn.execute(sa.text("""
        INSERT INTO bank_file_configs (
            id, tenant_id, bank_name, file_format, delimiter,
            column_mapping, include_header_row, header_template,
            date_format, amount_format, encoding, is_default
        )
        SELECT
            gen_random_uuid(),
            t.id,
            'Stanbic Bank',
            'csv',
            '|',
            '[
                {"header": "Type", "source": "template", "template": "CR", "width": null},
                {"header": "Account Number", "source": "account_number", "width": null},
                {"header": "Amount", "source": "net_salary", "format": "decimal_2", "width": null},
                {"header": "Currency", "source": "template", "template": "GHS", "width": null},
                {"header": "Beneficiary Name", "source": "staff_name", "width": null},
                {"header": "Narration", "source": "template", "template": "SALARY", "width": null}
            ]'::jsonb,
            false,
            'DR|{school_account}|{total_amount}|GHS|SALARY {month_name_upper} {year}',
            'YYYY-MM-DD',
            'decimal',
            'utf-8',
            false
        FROM tenants t
        WHERE t.status IN ('active', 'trial')
        ON CONFLICT DO NOTHING
    """))

    # Fidelity Bank (CSV)
    conn.execute(sa.text("""
        INSERT INTO bank_file_configs (
            id, tenant_id, bank_name, file_format, delimiter,
            column_mapping, include_header_row, date_format, amount_format,
            encoding, is_default
        )
        SELECT
            gen_random_uuid(),
            t.id,
            'Fidelity Bank',
            'csv',
            ',',
            '[
                {"header": "Account Number", "source": "account_number", "width": null},
                {"header": "Account Name", "source": "staff_name", "width": null},
                {"header": "Amount", "source": "net_salary", "format": "decimal_2", "width": null},
                {"header": "Reference", "source": "template", "template": "{month_name} {year} Salary", "width": null}
            ]'::jsonb,
            true,
            'YYYY-MM-DD',
            'decimal',
            'utf-8',
            false
        FROM tenants t
        WHERE t.status IN ('active', 'trial')
        ON CONFLICT DO NOTHING
    """))

    # CalBank (CSV)
    conn.execute(sa.text("""
        INSERT INTO bank_file_configs (
            id, tenant_id, bank_name, file_format, delimiter,
            column_mapping, include_header_row, date_format, amount_format,
            encoding, is_default
        )
        SELECT
            gen_random_uuid(),
            t.id,
            'CalBank',
            'csv',
            ',',
            '[
                {"header": "Beneficiary Name", "source": "staff_name", "width": null},
                {"header": "Account Number", "source": "account_number", "width": null},
                {"header": "Amount", "source": "net_salary", "format": "decimal_2", "width": null},
                {"header": "Currency", "source": "template", "template": "GHS", "width": null},
                {"header": "Description", "source": "template", "template": "{month_name} {year} Salary Payment", "width": null}
            ]'::jsonb,
            true,
            'YYYY-MM-DD',
            'decimal',
            'utf-8',
            false
        FROM tenants t
        WHERE t.status IN ('active', 'trial')
        ON CONFLICT DO NOTHING
    """))


def downgrade() -> None:
    conn = op.get_bind()

    # Remove seeded bank file configs (no custom ones exist yet)
    conn.execute(sa.text("""
        DELETE FROM bank_file_configs
        WHERE bank_name IN ('GCB Bank', 'Ecobank', 'Stanbic Bank', 'Fidelity Bank', 'CalBank')
    """))

    # Remove seeded tax brackets (2024 only)
    conn.execute(sa.text("""
        DELETE FROM tax_brackets WHERE effective_year = 2024
    """))
