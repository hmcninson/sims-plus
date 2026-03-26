"""
SIMS Plus - Payroll Configuration & Salary Endpoints

22 endpoints for payroll configuration (salary grades, allowance/deduction types,
tax brackets, bank file configs) and staff salary management.

All endpoints gated by hr_payroll feature flag and payroll.* permissions.

IMPORTANT: Do NOT use `from __future__ import annotations` here.
It breaks 204 No Content responses with AssertionError.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    DatabaseSession,
    RequestTenant,
    ValidatedUser,
    require_feature,
    require_permissions,
)
from app.schemas.payroll import (
    AllowanceTypeCreate,
    AllowanceTypeResponse,
    AllowanceTypeUpdate,
    BankFileConfigCreate,
    BankFileConfigResponse,
    BankFileConfigUpdate,
    BulkSalaryAssignRequest,
    BulkSalaryAssignResponse,
    DeductionTypeCreate,
    DeductionTypeResponse,
    DeductionTypeUpdate,
    PayrollAuditLogResponse,
    SalaryGradeCreate,
    SalaryGradeResponse,
    SalaryGradeUpdate,
    StaffAllowanceResponse,
    StaffDeductionResponse,
    StaffSalaryConfigCreate,
    StaffSalaryConfigResponse,
    TaxBracketResponse,
    TaxBracketSeedRequest,
    TaxBracketSeedResponse,
    TaxBracketUpdate,
)
from app.services.payroll import (
    PayrollAuditService,
    PayrollConfigService,
    SalaryService,
)


router = APIRouter()


# ======================================================================
# Helper: build salary config response with nested denormalized fields
# ======================================================================


def _build_salary_response(config) -> StaffSalaryConfigResponse:
    """
    Build a StaffSalaryConfigResponse from a StaffSalaryConfig ORM object
    with eagerly loaded relationships (allowances, deductions, salary_grade).
    """
    allowances = []
    for a in config.allowances:
        allowances.append(
            StaffAllowanceResponse(
                id=a.id,
                allowance_type_id=a.allowance_type_id,
                amount=a.amount,
                calculation_method=a.calculation_method,
                allowance_type_name=(
                    a.allowance_type.name if a.allowance_type else None
                ),
                allowance_type_code=(
                    a.allowance_type.code if a.allowance_type else None
                ),
            )
        )

    deductions = []
    for d in config.deductions:
        deductions.append(
            StaffDeductionResponse(
                id=d.id,
                deduction_type_id=d.deduction_type_id,
                amount=d.amount,
                calculation_method=d.calculation_method,
                deduction_type_name=(
                    d.deduction_type.name if d.deduction_type else None
                ),
                deduction_type_code=(
                    d.deduction_type.code if d.deduction_type else None
                ),
            )
        )

    return StaffSalaryConfigResponse(
        id=config.id,
        tenant_id=config.tenant_id,
        school_id=config.school_id,
        staff_id=config.staff_id,
        salary_grade_id=config.salary_grade_id,
        basic_salary=config.basic_salary,
        effective_date=config.effective_date,
        end_date=config.end_date,
        payment_method=(
            config.payment_method.value
            if config.payment_method and hasattr(config.payment_method, "value")
            else config.payment_method
        ),
        bank_name=config.bank_name,
        bank_branch=config.bank_branch,
        account_number=config.account_number,  # Masked by schema validator
        mobile_money_number=config.mobile_money_number,
        mobile_money_provider=config.mobile_money_provider,
        tin_number=config.tin_number,
        ssnit_number=config.ssnit_number,
        notes=config.notes,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
        allowances=allowances,
        deductions=deductions,
        salary_grade_name=(
            config.salary_grade.name if config.salary_grade else None
        ),
    )


# ======================================================================
# Salary Grades
# ======================================================================


@router.get(
    "/salary-grades",
    response_model=list[SalaryGradeResponse],
    summary="List salary grades",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def list_salary_grades(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    active_only: bool = Query(True, description="Only return active grades"),
) -> list[SalaryGradeResponse]:
    """List all salary grades for the current tenant."""
    service = PayrollConfigService(db)
    grades = await service.list_salary_grades(
        tenant_id=tenant.tenant_id,
        active_only=active_only,
    )
    return [SalaryGradeResponse.model_validate(g) for g in grades]


@router.post(
    "/salary-grades",
    response_model=SalaryGradeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create salary grade",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def create_salary_grade(
    data: SalaryGradeCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> SalaryGradeResponse:
    """Create a new salary grade (pay scale)."""
    service = PayrollConfigService(db)
    try:
        grade = await service.create_salary_grade(
            tenant_id=tenant.tenant_id,
            data=data.model_dump(),
        )
        return SalaryGradeResponse.model_validate(grade)
    except PayrollConfigService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.put(
    "/salary-grades/{grade_id}",
    response_model=SalaryGradeResponse,
    summary="Update salary grade",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def update_salary_grade(
    grade_id: UUID,
    data: SalaryGradeUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> SalaryGradeResponse:
    """Update a salary grade."""
    service = PayrollConfigService(db)
    try:
        grade = await service.update_salary_grade(
            tenant_id=tenant.tenant_id,
            grade_id=grade_id,
            data=data.model_dump(exclude_unset=True),
        )
        return SalaryGradeResponse.model_validate(grade)
    except PayrollConfigService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.delete(
    "/salary-grades/{grade_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete salary grade",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def delete_salary_grade(
    grade_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Soft-delete a salary grade."""
    service = PayrollConfigService(db)
    try:
        await service.delete_salary_grade(
            tenant_id=tenant.tenant_id,
            grade_id=grade_id,
        )
    except PayrollConfigService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# Allowance Types
# ======================================================================


@router.get(
    "/allowance-types",
    response_model=list[AllowanceTypeResponse],
    summary="List allowance types",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def list_allowance_types(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    active_only: bool = Query(True),
) -> list[AllowanceTypeResponse]:
    """List all allowance types."""
    service = PayrollConfigService(db)
    types = await service.list_allowance_types(
        tenant_id=tenant.tenant_id,
        active_only=active_only,
    )
    return [AllowanceTypeResponse.model_validate(t) for t in types]


@router.post(
    "/allowance-types",
    response_model=AllowanceTypeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create allowance type",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def create_allowance_type(
    data: AllowanceTypeCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> AllowanceTypeResponse:
    """Create a new allowance type (e.g., Housing, Responsibility)."""
    service = PayrollConfigService(db)
    try:
        allowance = await service.create_allowance_type(
            tenant_id=tenant.tenant_id,
            data=data.model_dump(),
        )
        return AllowanceTypeResponse.model_validate(allowance)
    except PayrollConfigService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.put(
    "/allowance-types/{allowance_id}",
    response_model=AllowanceTypeResponse,
    summary="Update allowance type",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def update_allowance_type(
    allowance_id: UUID,
    data: AllowanceTypeUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> AllowanceTypeResponse:
    """Update an allowance type."""
    service = PayrollConfigService(db)
    try:
        allowance = await service.update_allowance_type(
            tenant_id=tenant.tenant_id,
            allowance_id=allowance_id,
            data=data.model_dump(exclude_unset=True),
        )
        return AllowanceTypeResponse.model_validate(allowance)
    except PayrollConfigService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.delete(
    "/allowance-types/{allowance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete allowance type",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def delete_allowance_type(
    allowance_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Soft-delete an allowance type."""
    service = PayrollConfigService(db)
    try:
        await service.delete_allowance_type(
            tenant_id=tenant.tenant_id,
            allowance_id=allowance_id,
        )
    except PayrollConfigService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# Deduction Types
# ======================================================================


@router.get(
    "/deduction-types",
    response_model=list[DeductionTypeResponse],
    summary="List deduction types",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def list_deduction_types(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    active_only: bool = Query(True),
) -> list[DeductionTypeResponse]:
    """List all deduction types."""
    service = PayrollConfigService(db)
    types = await service.list_deduction_types(
        tenant_id=tenant.tenant_id,
        active_only=active_only,
    )
    return [DeductionTypeResponse.model_validate(t) for t in types]


@router.post(
    "/deduction-types",
    response_model=DeductionTypeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create deduction type",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def create_deduction_type(
    data: DeductionTypeCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> DeductionTypeResponse:
    """Create a new deduction type (e.g., SSNIT Employee, Staff Welfare)."""
    service = PayrollConfigService(db)
    try:
        deduction = await service.create_deduction_type(
            tenant_id=tenant.tenant_id,
            data=data.model_dump(),
        )
        return DeductionTypeResponse.model_validate(deduction)
    except PayrollConfigService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.put(
    "/deduction-types/{deduction_id}",
    response_model=DeductionTypeResponse,
    summary="Update deduction type",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def update_deduction_type(
    deduction_id: UUID,
    data: DeductionTypeUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> DeductionTypeResponse:
    """Update a deduction type."""
    service = PayrollConfigService(db)
    try:
        deduction = await service.update_deduction_type(
            tenant_id=tenant.tenant_id,
            deduction_id=deduction_id,
            data=data.model_dump(exclude_unset=True),
        )
        return DeductionTypeResponse.model_validate(deduction)
    except PayrollConfigService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.delete(
    "/deduction-types/{deduction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete deduction type",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def delete_deduction_type(
    deduction_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Soft-delete a deduction type."""
    service = PayrollConfigService(db)
    try:
        await service.delete_deduction_type(
            tenant_id=tenant.tenant_id,
            deduction_id=deduction_id,
        )
    except PayrollConfigService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# Tax Brackets
# ======================================================================


@router.get(
    "/tax-brackets",
    response_model=list[TaxBracketResponse],
    summary="List tax brackets",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def list_tax_brackets(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    effective_year: Optional[int] = Query(None, ge=2020, le=2100),
) -> list[TaxBracketResponse]:
    """List tax brackets, optionally filtered by year."""
    service = PayrollConfigService(db)
    brackets = await service.list_tax_brackets(
        tenant_id=tenant.tenant_id,
        effective_year=effective_year,
    )
    return [TaxBracketResponse.model_validate(b) for b in brackets]


@router.post(
    "/tax-brackets/seed",
    response_model=TaxBracketSeedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Seed GRA tax brackets",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def seed_tax_brackets(
    data: TaxBracketSeedRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> TaxBracketSeedResponse:
    """
    Seed GRA 2024 PAYE tax brackets for the tenant. Idempotent: if brackets
    already exist for the year, returns a message indicating no action taken.
    """
    service = PayrollConfigService(db)
    try:
        count = await service.seed_tax_brackets(
            tenant_id=tenant.tenant_id,
            effective_year=data.effective_year,
            school_id=data.school_id,
        )
        if count == 0:
            return TaxBracketSeedResponse(
                brackets_created=0,
                effective_year=data.effective_year,
                message=f"Tax brackets for {data.effective_year} already exist",
            )
        return TaxBracketSeedResponse(
            brackets_created=count,
            effective_year=data.effective_year,
            message=f"Seeded {count} GRA tax brackets for {data.effective_year}",
        )
    except PayrollConfigService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.put(
    "/tax-brackets/{bracket_id}",
    response_model=TaxBracketResponse,
    summary="Update tax bracket",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def update_tax_bracket(
    bracket_id: UUID,
    data: TaxBracketUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> TaxBracketResponse:
    """
    Update a single tax bracket. Validates contiguity of the entire year's
    brackets after the update to prevent calculation errors.
    """
    service = PayrollConfigService(db)
    try:
        bracket = await service.update_tax_bracket(
            tenant_id=tenant.tenant_id,
            bracket_id=bracket_id,
            data=data.model_dump(exclude_unset=True),
        )
        return TaxBracketResponse.model_validate(bracket)
    except PayrollConfigService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# Bank File Configs
# ======================================================================


@router.get(
    "/bank-file-configs",
    response_model=list[BankFileConfigResponse],
    summary="List bank file configs",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def list_bank_file_configs(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[BankFileConfigResponse]:
    """List all bank file configurations."""
    service = PayrollConfigService(db)
    configs = await service.list_bank_file_configs(tenant_id=tenant.tenant_id)
    return [BankFileConfigResponse.model_validate(c) for c in configs]


@router.post(
    "/bank-file-configs",
    response_model=BankFileConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create bank file config",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def create_bank_file_config(
    data: BankFileConfigCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> BankFileConfigResponse:
    """Create a bank file configuration for payroll file generation."""
    service = PayrollConfigService(db)
    try:
        config = await service.create_bank_file_config(
            tenant_id=tenant.tenant_id,
            data=data.model_dump(),
        )
        return BankFileConfigResponse.model_validate(config)
    except PayrollConfigService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.put(
    "/bank-file-configs/{config_id}",
    response_model=BankFileConfigResponse,
    summary="Update bank file config",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def update_bank_file_config(
    config_id: UUID,
    data: BankFileConfigUpdate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> BankFileConfigResponse:
    """Update a bank file configuration."""
    service = PayrollConfigService(db)
    try:
        config = await service.update_bank_file_config(
            tenant_id=tenant.tenant_id,
            config_id=config_id,
            data=data.model_dump(exclude_unset=True),
        )
        return BankFileConfigResponse.model_validate(config)
    except PayrollConfigService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.delete(
    "/bank-file-configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete bank file config",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.configure")),
    ],
)
async def delete_bank_file_config(
    config_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> None:
    """Soft-delete a bank file configuration."""
    service = PayrollConfigService(db)
    try:
        await service.delete_bank_file_config(
            tenant_id=tenant.tenant_id,
            config_id=config_id,
        )
    except PayrollConfigService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# Staff Salary Config
# ======================================================================


@router.get(
    "/staff/{staff_id}/salary",
    response_model=StaffSalaryConfigResponse,
    summary="Get staff salary config",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def get_staff_salary(
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> StaffSalaryConfigResponse:
    """Get the current active salary configuration for a staff member."""
    service = SalaryService(db)
    try:
        config = await service.get_staff_salary(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
        )
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active salary configuration found for this staff member",
            )
        return _build_salary_response(config)
    except SalaryService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/staff/{staff_id}/salary",
    response_model=StaffSalaryConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create/update staff salary config",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.manage")),
    ],
)
async def create_staff_salary(
    staff_id: UUID,
    data: StaffSalaryConfigCreate,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> StaffSalaryConfigResponse:
    """
    Create a new salary configuration for a staff member. If an active
    config already exists, it is deactivated and a new one is created.
    """
    service = SalaryService(db)
    try:
        config = await service.create_or_update_salary(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
            data=data.model_dump(),
            performed_by=UUID(current_user["user_id"]),
        )

        # Audit trail for salary assignment
        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="staff_salary_config",
            entity_id=config.id,
            action="created",
            performed_by=UUID(current_user["user_id"]),
            new_value=str(config.basic_salary),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return _build_salary_response(config)
    except SalaryService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


@router.post(
    "/staff/salary/bulk",
    response_model=BulkSalaryAssignResponse,
    summary="Bulk assign salary grade",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.manage")),
    ],
)
async def bulk_assign_salary_grade(
    data: BulkSalaryAssignRequest,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    request: Request,
) -> BulkSalaryAssignResponse:
    """
    Bulk assign a salary grade to multiple staff members. Creates new
    salary configs using the grade's basic_salary for each staff member.
    """
    service = SalaryService(db)
    try:
        result = await service.bulk_assign_salary_grade(
            tenant_id=tenant.tenant_id,
            staff_ids=data.staff_ids,
            salary_grade_id=data.salary_grade_id,
            effective_date=data.effective_date,
            school_id=data.school_id,
        )

        # Audit trail for bulk assignment
        audit = PayrollAuditService(db)
        await audit.log_event(
            tenant_id=tenant.tenant_id,
            entity_type="salary_grade",
            entity_id=data.salary_grade_id,
            action="bulk_assigned",
            performed_by=UUID(current_user["user_id"]),
            metadata={
                "staff_count": result["assigned_count"],
                "skipped_count": result["skipped_count"],
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        return BulkSalaryAssignResponse(**result)
    except SalaryService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# Salary History
# ======================================================================


@router.get(
    "/staff/{staff_id}/salary/history",
    response_model=list[StaffSalaryConfigResponse],
    summary="Staff salary history",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.read")),
    ],
)
async def get_salary_history(
    staff_id: UUID,
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
) -> list[StaffSalaryConfigResponse]:
    """Get all salary configurations for a staff member, most recent first."""
    service = SalaryService(db)
    try:
        configs = await service.get_salary_history(
            tenant_id=tenant.tenant_id,
            staff_id=staff_id,
        )
        return [_build_salary_response(c) for c in configs]
    except SalaryService.Error as e:
        raise HTTPException(status_code=e.code, detail=e.message)


# ======================================================================
# Audit Log
# ======================================================================


@router.get(
    "/audit-log",
    response_model=list[PayrollAuditLogResponse],
    summary="Payroll audit log",
    dependencies=[
        Depends(require_feature("hr_payroll")),
        Depends(require_permissions("payroll.audit")),
    ],
)
async def list_payroll_audit_log(
    tenant: RequestTenant,
    db: DatabaseSession,
    current_user: ValidatedUser,
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[PayrollAuditLogResponse]:
    """Query the payroll audit trail with optional filters."""
    service = PayrollAuditService(db)
    entries = await service.list_audit_log(
        tenant_id=tenant.tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return [PayrollAuditLogResponse.model_validate(e) for e in entries]
