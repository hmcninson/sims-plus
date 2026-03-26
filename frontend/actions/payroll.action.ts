"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  SalaryGrade,
  SalaryGradeCreate,
  SalaryGradeUpdate,
  AllowanceType,
  AllowanceTypeCreate,
  AllowanceTypeUpdate,
  DeductionType,
  DeductionTypeCreate,
  DeductionTypeUpdate,
  TaxBracket,
  TaxBracketUpdate,
  TaxBracketSeedRequest,
  BankFileConfig,
  BankFileConfigCreate,
  BankFileConfigUpdate,
  StaffSalaryConfig,
  StaffSalaryConfigCreate,
  BulkSalaryGradeAssign,
  BulkSalaryAssignResult,
  SalaryHistoryEntry,
  PayrollRun,
  PayrollRunCreate,
  PayrollItem,
  PayrollItemDetail,
  PayrollRunSummary,
  PayrollItemAdjustment,
  MonthlySummary,
  SSNITReturnReport,
  PAYEReturnReport,
  DepartmentSummaryReport,
  YearToDateReport,
  PayrollAuditLogResponse,
  BulkPayslipStatus,
  BankFileResult,
} from "@/types/payroll.type";

/**
 * Get auth context from cookies with token refresh
 */
async function getAuthContext() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  const subdomain = cookieStore.get("x-subdomain")?.value;
  return {
    token: token || undefined,
    subdomain,
  };
}

// =========================
// Salary Grade Actions
// =========================

export async function getSalaryGrades(
  activeOnly: boolean = false
): Promise<ActionResult<SalaryGrade[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (activeOnly) params.append("active_only", "true");
    const url = `/payroll/salary-grades${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<SalaryGrade[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch salary grades",
    };
  }
}

export async function createSalaryGrade(
  data: SalaryGradeCreate
): Promise<ActionResult<SalaryGrade>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<SalaryGrade>(
      "/payroll/salary-grades",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create salary grade",
    };
  }
}

export async function updateSalaryGrade(
  id: string,
  data: SalaryGradeUpdate
): Promise<ActionResult<SalaryGrade>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<SalaryGrade>(
      `/payroll/salary-grades/${id}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update salary grade",
    };
  }
}

export async function deleteSalaryGrade(
  id: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/payroll/salary-grades/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete salary grade",
    };
  }
}

// =========================
// Allowance Type Actions
// =========================

export async function getAllowanceTypes(
  activeOnly: boolean = false
): Promise<ActionResult<AllowanceType[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (activeOnly) params.append("active_only", "true");
    const url = `/payroll/allowance-types${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<AllowanceType[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch allowance types",
    };
  }
}

export async function createAllowanceType(
  data: AllowanceTypeCreate
): Promise<ActionResult<AllowanceType>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<AllowanceType>(
      "/payroll/allowance-types",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create allowance type",
    };
  }
}

export async function updateAllowanceType(
  id: string,
  data: AllowanceTypeUpdate
): Promise<ActionResult<AllowanceType>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<AllowanceType>(
      `/payroll/allowance-types/${id}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update allowance type",
    };
  }
}

export async function deleteAllowanceType(
  id: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/payroll/allowance-types/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete allowance type",
    };
  }
}

// =========================
// Deduction Type Actions
// =========================

export async function getDeductionTypes(
  activeOnly: boolean = false
): Promise<ActionResult<DeductionType[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (activeOnly) params.append("active_only", "true");
    const url = `/payroll/deduction-types${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<DeductionType[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch deduction types",
    };
  }
}

export async function createDeductionType(
  data: DeductionTypeCreate
): Promise<ActionResult<DeductionType>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<DeductionType>(
      "/payroll/deduction-types",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create deduction type",
    };
  }
}

export async function updateDeductionType(
  id: string,
  data: DeductionTypeUpdate
): Promise<ActionResult<DeductionType>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<DeductionType>(
      `/payroll/deduction-types/${id}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update deduction type",
    };
  }
}

export async function deleteDeductionType(
  id: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/payroll/deduction-types/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete deduction type",
    };
  }
}

// =========================
// Tax Bracket Actions
// =========================

export async function getTaxBrackets(
  year?: number
): Promise<ActionResult<TaxBracket[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (year) params.append("effective_year", String(year));
    const url = `/payroll/tax-brackets${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<TaxBracket[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch tax brackets",
    };
  }
}

export async function seedTaxBrackets(
  data: TaxBracketSeedRequest
): Promise<ActionResult<TaxBracket[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<TaxBracket[]>(
      "/payroll/tax-brackets/seed",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to seed tax brackets",
    };
  }
}

export async function updateTaxBracket(
  id: string,
  data: TaxBracketUpdate
): Promise<ActionResult<TaxBracket>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<TaxBracket>(
      `/payroll/tax-brackets/${id}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update tax bracket",
    };
  }
}

// =========================
// Bank File Config Actions
// =========================

export async function getBankFileConfigs(): Promise<ActionResult<BankFileConfig[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<BankFileConfig[]>(
      "/payroll/bank-file-configs",
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch bank file configs",
    };
  }
}

export async function createBankFileConfig(
  data: BankFileConfigCreate
): Promise<ActionResult<BankFileConfig>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<BankFileConfig>(
      "/payroll/bank-file-configs",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create bank file config",
    };
  }
}

export async function updateBankFileConfig(
  id: string,
  data: BankFileConfigUpdate
): Promise<ActionResult<BankFileConfig>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<BankFileConfig>(
      `/payroll/bank-file-configs/${id}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update bank file config",
    };
  }
}

export async function deleteBankFileConfig(
  id: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/payroll/bank-file-configs/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete bank file config",
    };
  }
}

// =========================
// Staff Salary Actions
// =========================

export async function getStaffSalary(
  staffId: string
): Promise<ActionResult<StaffSalaryConfig>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StaffSalaryConfig>(
      `/payroll/staff/${staffId}/salary`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch staff salary",
    };
  }
}

export async function updateStaffSalary(
  staffId: string,
  data: StaffSalaryConfigCreate
): Promise<ActionResult<StaffSalaryConfig>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StaffSalaryConfig>(
      `/payroll/staff/${staffId}/salary`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update staff salary",
    };
  }
}

export async function bulkAssignSalaryGrade(
  data: BulkSalaryGradeAssign
): Promise<ActionResult<BulkSalaryAssignResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<BulkSalaryAssignResult>(
      "/payroll/staff/salary/bulk",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to bulk assign salary grade",
    };
  }
}

export async function getStaffSalaryHistory(
  staffId: string
): Promise<ActionResult<SalaryHistoryEntry[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<SalaryHistoryEntry[]>(
      `/payroll/staff/${staffId}/salary/history`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch salary history",
    };
  }
}

// =========================
// Payroll Run Actions
// =========================

export async function getPayrollRuns(params?: {
  year?: number;
  status?: string;
  limit?: number;
}): Promise<ActionResult<PayrollRun[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.year) searchParams.append("year", String(params.year));
    if (params?.status) searchParams.append("status", params.status);
    if (params?.limit) searchParams.append("limit", String(params.limit));
    const url = `/payroll/runs${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
    const response = await apiGet<PayrollRun[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch payroll runs",
    };
  }
}

export async function createPayrollRun(
  data: PayrollRunCreate
): Promise<ActionResult<PayrollRun>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PayrollRun>(
      "/payroll/runs",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create payroll run",
    };
  }
}

export async function getPayrollRun(
  id: string
): Promise<ActionResult<PayrollRun>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<PayrollRun>(
      `/payroll/runs/${id}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch payroll run",
    };
  }
}

export async function calculatePayrollRun(
  id: string
): Promise<ActionResult<PayrollRun>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PayrollRun>(
      `/payroll/runs/${id}/calculate`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to calculate payroll run",
    };
  }
}

export async function submitPayrollRun(
  id: string
): Promise<ActionResult<PayrollRun>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PayrollRun>(
      `/payroll/runs/${id}/submit`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to submit payroll run",
    };
  }
}

export async function approvePayrollRun(
  id: string,
  comments?: string
): Promise<ActionResult<PayrollRun>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PayrollRun>(
      `/payroll/runs/${id}/approve`,
      { action: "approve", comments },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to approve payroll run",
    };
  }
}

export async function rejectPayrollRun(
  id: string,
  comments: string
): Promise<ActionResult<PayrollRun>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PayrollRun>(
      `/payroll/runs/${id}/approve`,
      { action: "reject", comments },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to reject payroll run",
    };
  }
}

export async function markPayrollRunPaid(
  id: string
): Promise<ActionResult<PayrollRun>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PayrollRun>(
      `/payroll/runs/${id}/mark-paid`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to mark payroll run as paid",
    };
  }
}

export async function cancelPayrollRun(
  id: string
): Promise<ActionResult<PayrollRun>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PayrollRun>(
      `/payroll/runs/${id}/cancel`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to cancel payroll run",
    };
  }
}

export async function getPayrollRunItems(
  runId: string
): Promise<ActionResult<PayrollItem[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<PayrollItem[]>(
      `/payroll/runs/${runId}/items`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch payroll items",
    };
  }
}

export async function getPayrollRunItem(
  runId: string,
  itemId: string
): Promise<ActionResult<PayrollItemDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<PayrollItemDetail>(
      `/payroll/runs/${runId}/items/${itemId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch payroll item detail",
    };
  }
}

export async function adjustPayrollItem(
  runId: string,
  itemId: string,
  data: PayrollItemAdjustment
): Promise<ActionResult<PayrollItemDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PayrollItemDetail>(
      `/payroll/runs/${runId}/items/${itemId}/adjust`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to adjust payroll item",
    };
  }
}

export async function getPayrollRunSummary(
  runId: string
): Promise<ActionResult<PayrollRunSummary>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<PayrollRunSummary>(
      `/payroll/runs/${runId}/summary`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch payroll run summary",
    };
  }
}

// =========================
// Phase 4C: Payslips, Bank Files, Reports, Audit
// =========================

export async function getPayslipUrl(
  runId: string,
  staffId: string
): Promise<ActionResult<{ url: string }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<{ url: string }>(
      `/payroll/runs/${runId}/payslips/${staffId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to get payslip URL",
    };
  }
}

export async function generateBulkPayslips(
  runId: string
): Promise<ActionResult<BulkPayslipStatus>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<BulkPayslipStatus>(
      `/payroll/runs/${runId}/payslips/bulk`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to generate bulk payslips",
    };
  }
}

export async function generateBankFile(
  runId: string,
  bankName?: string
): Promise<ActionResult<BankFileResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const url = bankName
      ? `/payroll/runs/${runId}/bank-file/${encodeURIComponent(bankName)}`
      : `/payroll/runs/${runId}/bank-file`;
    const response = await apiGet<BankFileResult>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to generate bank file",
    };
  }
}

export async function getMonthlySummary(
  year: number,
  month: number
): Promise<ActionResult<MonthlySummary>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({ year: String(year), month: String(month) });
    const response = await apiGet<MonthlySummary>(
      `/payroll/reports/monthly-summary?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch monthly summary",
    };
  }
}

export async function getSSNITReturns(
  year: number,
  month: number
): Promise<ActionResult<SSNITReturnReport>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({ year: String(year), month: String(month) });
    const response = await apiGet<SSNITReturnReport>(
      `/payroll/reports/ssnit-returns?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch SSNIT returns",
    };
  }
}

export async function exportSSNITReturns(
  year: number,
  month: number
): Promise<ActionResult<{ url: string }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<{ url: string }>(
      "/payroll/reports/ssnit-returns/export",
      { year, month },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to export SSNIT returns",
    };
  }
}

export async function getPAYEReturns(
  year: number,
  month: number
): Promise<ActionResult<PAYEReturnReport>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({ year: String(year), month: String(month) });
    const response = await apiGet<PAYEReturnReport>(
      `/payroll/reports/paye-returns?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch PAYE returns",
    };
  }
}

export async function exportPAYEReturns(
  year: number,
  month: number
): Promise<ActionResult<{ url: string }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<{ url: string }>(
      "/payroll/reports/paye-returns/export",
      { year, month },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to export PAYE returns",
    };
  }
}

export async function getDepartmentSummary(
  year: number,
  month: number
): Promise<ActionResult<DepartmentSummaryReport>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({ year: String(year), month: String(month) });
    const response = await apiGet<DepartmentSummaryReport>(
      `/payroll/reports/department-summary?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch department summary",
    };
  }
}

export async function getYearToDate(
  staffId: string,
  year: number
): Promise<ActionResult<YearToDateReport>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({ year: String(year) });
    const response = await apiGet<YearToDateReport>(
      `/payroll/reports/year-to-date/${staffId}?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch year-to-date report",
    };
  }
}

export async function getPayrollAuditLog(params?: {
  page?: number;
  page_size?: number;
  entity_type?: string;
  date_from?: string;
  date_to?: string;
}): Promise<ActionResult<PayrollAuditLogResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.page_size) searchParams.append("page_size", String(params.page_size));
    if (params?.entity_type) searchParams.append("entity_type", params.entity_type);
    if (params?.date_from) searchParams.append("date_from", params.date_from);
    if (params?.date_to) searchParams.append("date_to", params.date_to);
    const url = `/payroll/audit-log${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
    const response = await apiGet<PayrollAuditLogResponse>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch payroll audit log",
    };
  }
}
