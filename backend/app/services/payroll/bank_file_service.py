"""
SIMS Plus - Bank File Generation Service

Generates bank payment files (CSV, pipe-delimited, etc.) from payroll run
data using the bank_file_configs column_mapping. Uploads to S3 and returns
presigned download URLs.

SECURITY:
- CSV injection protection: cells starting with =, +, -, @ get leading apostrophe
- header_template/footer_template use string.Template.safe_substitute() (NOT str.format())
- column_mapping source field validated against ALLOWED_COLUMN_SOURCES whitelist
- All queries filter by tenant_id (defense-in-depth on top of RLS)
"""

import calendar
import io
import re
import string
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.payroll import (
    BankFileConfig,
    PayrollItem,
    PayrollRun,
    PayrollRunStatus,
)
from app.services.s3 import get_s3_service

logger = structlog.get_logger()

# Presigned URL expiry for bank file downloads (5 minutes per spec Section 9.3)
_PRESIGNED_EXPIRY_SECONDS = 300

# Dangerous template patterns that could enable injection
_DANGEROUS_TEMPLATE_PATTERNS = re.compile(r"(\{%|{{|__|{0)")

# Characters that trigger CSV formula injection in Excel/Sheets
_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@")


def _escape_csv_cell(value: str) -> str:
    """
    Escape CSV cell values to prevent formula injection.

    If a cell starts with =, +, -, or @, prefix with a single quote
    so spreadsheet applications treat it as text, not a formula.
    """
    if value and value[0] in _CSV_INJECTION_PREFIXES:
        return "'" + value
    return value


def _safe_template_render(
    template_str: Optional[str],
    variables: dict,
) -> Optional[str]:
    """
    Render a template string using string.Template.safe_substitute().

    SECURITY: Uses safe_substitute (not str.format) to prevent arbitrary
    attribute/item access. Rejects templates containing dangerous patterns
    like {%, {{, __, or {0.
    """
    if not template_str:
        return None

    # Reject dangerous patterns before rendering
    if _DANGEROUS_TEMPLATE_PATTERNS.search(template_str):
        logger.warning(
            "bank_file_template_rejected",
            reason="dangerous_pattern_detected",
        )
        return template_str

    try:
        tmpl = string.Template(template_str)
        return tmpl.safe_substitute(variables)
    except Exception:
        logger.exception("bank_file_template_render_failed")
        return template_str


class BankFileService:
    """Service for generating bank payment files."""

    def __init__(self, db: AsyncSession):
        self.db = db

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    async def generate_bank_file(
        self,
        tenant_id: UUID,
        run_id: UUID,
        config_id: Optional[UUID] = None,
        bank_name: Optional[str] = None,
    ) -> dict:
        """
        Generate a bank payment file for a payroll run.

        Uses the column_mapping from a BankFileConfig to produce a CSV or
        delimited file. If no config_id or bank_name is provided, uses the
        default config. Filters items by payment method (bank_transfer for
        bank files, mobile_money for MoMo files).

        Returns:
            dict with download_url, bank_name, file_format, record_count,
            total_amount, and expires_in_seconds.
        """
        run = await self._get_run(tenant_id, run_id)

        # Bank files can only be generated for approved or paid runs
        if run.status not in (PayrollRunStatus.APPROVED, PayrollRunStatus.PAID):
            raise self.Error(
                "Bank files can only be generated for approved or paid runs", 409
            )

        # Fetch the bank file config
        config = await self._get_config(tenant_id, config_id, bank_name)

        # Fetch payroll items with earnings/deductions for this run
        items = await self._get_run_items(tenant_id, run_id)

        # Filter items by payment method based on bank config
        # Mobile Money configs only include mobile_money payments;
        # all others default to bank_transfer
        is_momo = "mobile" in config.bank_name.lower() or "momo" in config.bank_name.lower()
        if is_momo:
            filtered_items = [i for i in items if i.payment_method == "mobile_money"]
        else:
            filtered_items = [i for i in items if i.payment_method in ("bank_transfer", None)]

        if not filtered_items:
            raise self.Error(
                f"No items found with matching payment method for '{config.bank_name}'",
                404,
            )

        month_name = calendar.month_name[run.month]
        template_vars = {
            "month_name": month_name,
            "month": str(run.month).zfill(2),
            "year": str(run.year),
            "month_short": month_name[:3].upper(),
        }

        # Build the file content
        file_content = self._build_file_content(
            config=config,
            items=filtered_items,
            template_vars=template_vars,
        )

        # Calculate total amount for response metadata
        total_amount = sum(i.net_salary for i in filtered_items)

        # Upload to S3
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_bank_name = re.sub(r"[^a-zA-Z0-9_-]", "_", config.bank_name.lower())
        month_str = f"{run.month:02d}"
        s3_key = (
            f"tenants/{tenant_id}/payroll/{run.year}/{month_str}"
            f"/bank_file_{safe_bank_name}_{timestamp}.csv"
        )

        s3_service = get_s3_service()
        s3_service.upload_file(
            file_content=file_content.encode(config.encoding or "utf-8"),
            key=s3_key,
            content_type="text/csv",
        )

        download_url = s3_service.generate_presigned_url(
            key=s3_key,
            expires_in=_PRESIGNED_EXPIRY_SECONDS,
        )

        logger.info(
            "bank_file_generated",
            run_id=str(run_id),
            bank_name=config.bank_name,
            record_count=len(filtered_items),
            total_amount=str(total_amount),
            s3_key=s3_key,
            tenant_id=str(tenant_id),
        )

        return {
            "download_url": download_url,
            "bank_name": config.bank_name,
            "file_format": config.file_format,
            "record_count": len(filtered_items),
            "total_amount": total_amount,
            "expires_in_seconds": _PRESIGNED_EXPIRY_SECONDS,
        }

    def _build_file_content(
        self,
        config: BankFileConfig,
        items: list[PayrollItem],
        template_vars: dict,
    ) -> str:
        """
        Build the complete file content from config and payroll items.

        Applies column_mapping to each item, handles header/footer templates,
        and escapes cells for CSV injection protection.
        """
        lines: list[str] = []
        delimiter = config.delimiter or ","

        # Header template (rendered with safe_substitute)
        header_text = _safe_template_render(config.header_template, template_vars)
        if header_text:
            lines.append(header_text)

        # Column header row
        if config.include_header_row:
            headers = [col["header"] for col in config.column_mapping]
            lines.append(delimiter.join(headers))

        # Data rows
        for item in items:
            row_values: list[str] = []
            for col in config.column_mapping:
                raw_value = self._render_column_value(
                    source=col["source"],
                    item=item,
                    template_str=col.get("template"),
                    template_vars=template_vars,
                    fmt=col.get("format"),
                )
                # CSV injection protection
                escaped = _escape_csv_cell(raw_value)
                row_values.append(escaped)
            lines.append(delimiter.join(row_values))

        # Footer template
        footer_text = _safe_template_render(config.footer_template, template_vars)
        if footer_text:
            lines.append(footer_text)

        return "\n".join(lines) + "\n"

    def _render_column_value(
        self,
        source: str,
        item: PayrollItem,
        template_str: Optional[str],
        template_vars: dict,
        fmt: Optional[str],
    ) -> str:
        """
        Map a column source to the actual value from the PayrollItem.

        Handles the 'template' source (uses safe_substitute with template_vars
        plus item-derived variables) and direct attribute lookups.
        """
        # Runtime whitelist check to prevent arbitrary attribute access on PayrollItem
        from app.schemas.payroll import ALLOWED_COLUMN_SOURCES

        if source != "template" and source not in ALLOWED_COLUMN_SOURCES:
            logger.warning("bank_file_invalid_source", source=source)
            return ""

        if source == "template" and template_str:
            # Merge item data into template variables
            combined_vars = {
                **template_vars,
                "staff_name": item.staff_name,
                "staff_code": item.staff_code,
                "net_salary": str(item.net_salary),
            }
            rendered = _safe_template_render(template_str, combined_vars)
            return rendered or ""

        # Direct attribute lookup on PayrollItem (source already validated above)
        value = getattr(item, source, None)

        if value is None:
            return ""

        # Format decimal values
        if isinstance(value, Decimal):
            if fmt == "decimal_2":
                return f"{value:.2f}"
            return str(value)

        return str(value)

    async def _get_run(self, tenant_id: UUID, run_id: UUID) -> PayrollRun:
        """Fetch payroll run, validating tenant ownership."""
        result = await self.db.execute(
            select(PayrollRun)
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(PayrollRun.tenant_id == tenant_id)
            .where(PayrollRun.id == run_id)
            .where(PayrollRun.deleted_at.is_(None))
        )
        run = result.scalar_one_or_none()
        if not run:
            raise self.Error("Payroll run not found", 404)
        return run

    async def _get_config(
        self,
        tenant_id: UUID,
        config_id: Optional[UUID] = None,
        bank_name: Optional[str] = None,
    ) -> BankFileConfig:
        """
        Fetch the bank file config by ID, bank_name, or default.

        Priority: config_id > bank_name > default > first available.
        """
        if config_id:
            result = await self.db.execute(
                select(BankFileConfig)
                .where(BankFileConfig.tenant_id == tenant_id)
                .where(BankFileConfig.id == config_id)
                .where(BankFileConfig.deleted_at.is_(None))
            )
            config = result.scalar_one_or_none()
            if not config:
                raise self.Error("Bank file configuration not found", 404)
            return config

        if bank_name:
            result = await self.db.execute(
                select(BankFileConfig)
                .where(BankFileConfig.tenant_id == tenant_id)
                .where(BankFileConfig.bank_name == bank_name)
                .where(BankFileConfig.deleted_at.is_(None))
            )
            config = result.scalar_one_or_none()
            if not config:
                raise self.Error(
                    f"No bank file configuration found for '{bank_name}'", 404
                )
            return config

        # Fall back to default, then first available
        result = await self.db.execute(
            select(BankFileConfig)
            .where(BankFileConfig.tenant_id == tenant_id)
            .where(BankFileConfig.deleted_at.is_(None))
            .order_by(BankFileConfig.is_default.desc(), BankFileConfig.bank_name)
            .limit(1)
        )
        config = result.scalar_one_or_none()
        if not config:
            raise self.Error(
                "No bank file configurations found. Create one in payroll settings.",
                404,
            )
        return config

    async def _get_run_items(
        self, tenant_id: UUID, run_id: UUID
    ) -> list[PayrollItem]:
        """Fetch all payroll items for a run."""
        result = await self.db.execute(
            select(PayrollItem)
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .where(PayrollItem.tenant_id == tenant_id)
            .where(PayrollItem.payroll_run_id == run_id)
            .order_by(PayrollItem.staff_name)
        )
        return list(result.scalars().all())
