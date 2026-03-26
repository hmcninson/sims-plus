"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  LoanType,
  LoanTypeCreate,
  LoanTypeUpdate,
  StaffLoan,
  StaffLoanCreate,
  StaffLoanUpdate,
  StaffLoanListItem,
  StaffLoanListResponse,
  LoanInstallment,
  LoanPayment,
  LoanGuarantor,
  LoanGuarantorInput,
  LoanPortfolio,
  LoanAgingResponse,
  LoanEligibility,
  LoanRejectPayload,
  EarlyRepaymentPayload,
  LoanRestructurePayload,
  LoanWriteOffPayload,
} from "@/types/loan.type";

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
// Loan Type Actions
// =========================

export async function getLoanTypes(
  activeOnly: boolean = false
): Promise<ActionResult<LoanType[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (activeOnly) params.append("active_only", "true");
    const url = `/payroll/loan-types${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<LoanType[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch loan types",
    };
  }
}

export async function createLoanType(
  data: LoanTypeCreate
): Promise<ActionResult<LoanType>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<LoanType>(
      "/payroll/loan-types",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create loan type",
    };
  }
}

export async function updateLoanType(
  id: string,
  data: LoanTypeUpdate
): Promise<ActionResult<LoanType>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<LoanType>(
      `/payroll/loan-types/${id}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update loan type",
    };
  }
}

export async function deleteLoanType(
  id: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/payroll/loan-types/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete loan type",
    };
  }
}

// =========================
// Staff Loan Actions
// =========================

export async function getLoans(params?: {
  status?: string;
  loan_type_id?: string;
  staff_id?: string;
  school_id?: string;
  limit?: number;
  offset?: number;
}): Promise<ActionResult<StaffLoanListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.status && params.status !== "all") searchParams.append("status", params.status);
    if (params?.loan_type_id && params.loan_type_id !== "all") searchParams.append("loan_type_id", params.loan_type_id);
    if (params?.staff_id) searchParams.append("staff_id", params.staff_id);
    if (params?.school_id) searchParams.append("school_id", params.school_id);
    if (params?.limit) searchParams.append("limit", String(params.limit));
    if (params?.offset) searchParams.append("offset", String(params.offset));
    const url = `/payroll/loans${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
    const response = await apiGet<StaffLoanListResponse>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch loans",
    };
  }
}

export async function getLoan(
  id: string
): Promise<ActionResult<StaffLoan>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StaffLoan>(
      `/payroll/loans/${id}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch loan",
    };
  }
}

export async function createLoan(
  data: StaffLoanCreate
): Promise<ActionResult<StaffLoan>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StaffLoan>(
      "/payroll/loans",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create loan",
    };
  }
}

export async function updateLoan(
  id: string,
  data: StaffLoanUpdate
): Promise<ActionResult<StaffLoan>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<StaffLoan>(
      `/payroll/loans/${id}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update loan",
    };
  }
}

export async function deleteLoan(
  id: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/payroll/loans/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete loan",
    };
  }
}

// =========================
// Loan Lifecycle Actions
// =========================

export async function submitLoan(
  id: string
): Promise<ActionResult<StaffLoan>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StaffLoan>(
      `/payroll/loans/${id}/submit`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to submit loan",
    };
  }
}

export async function approveLoan(
  id: string
): Promise<ActionResult<StaffLoan>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // Backend approve endpoint takes no body — it uses the authenticated
    // user's identity for the approver
    const response = await apiPost<StaffLoan>(
      `/payroll/loans/${id}/approve`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to approve loan",
    };
  }
}

export async function rejectLoan(
  id: string,
  data: LoanRejectPayload
): Promise<ActionResult<StaffLoan>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StaffLoan>(
      `/payroll/loans/${id}/reject`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to reject loan",
    };
  }
}

export async function disburseLoan(
  id: string
): Promise<ActionResult<StaffLoan>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // Backend disburse endpoint takes no body
    const response = await apiPost<StaffLoan>(
      `/payroll/loans/${id}/disburse`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to disburse loan",
    };
  }
}

export async function earlyRepayment(
  id: string,
  data: EarlyRepaymentPayload
): Promise<ActionResult<StaffLoan>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StaffLoan>(
      `/payroll/loans/${id}/early-repayment`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to process early repayment",
    };
  }
}

export async function restructureLoan(
  id: string,
  data: LoanRestructurePayload
): Promise<ActionResult<StaffLoan>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StaffLoan>(
      `/payroll/loans/${id}/restructure`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to restructure loan",
    };
  }
}

export async function writeOffLoan(
  id: string,
  data: LoanWriteOffPayload
): Promise<ActionResult<StaffLoan>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StaffLoan>(
      `/payroll/loans/${id}/write-off`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to write off loan",
    };
  }
}

export async function getLoanStatement(
  id: string
): Promise<ActionResult<{ url: string }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<{ url: string }>(
      `/payroll/loans/${id}/statement`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to get loan statement",
    };
  }
}

// =========================
// Loan Installments & Payments
// =========================

export async function getLoanInstallments(
  loanId: string
): Promise<ActionResult<LoanInstallment[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<LoanInstallment[]>(
      `/payroll/loans/${loanId}/installments`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch installments",
    };
  }
}

export async function getLoanPayments(
  loanId: string
): Promise<ActionResult<LoanPayment[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<LoanPayment[]>(
      `/payroll/loans/${loanId}/payments`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch loan payments",
    };
  }
}

// =========================
// Guarantor Actions
// =========================

export async function addGuarantor(
  loanId: string,
  data: LoanGuarantorInput
): Promise<ActionResult<LoanGuarantor>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<LoanGuarantor>(
      `/payroll/loans/${loanId}/guarantors`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to add guarantor",
    };
  }
}

export async function removeGuarantor(
  loanId: string,
  guarantorId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/payroll/loans/${loanId}/guarantors/${guarantorId}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to remove guarantor",
    };
  }
}

export async function recordGuarantorConsent(
  loanId: string,
  guarantorId: string,
  consentGiven: boolean = true,
  notes?: string
): Promise<ActionResult<LoanGuarantor>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // Backend uses PUT (not POST) for consent updates
    const response = await apiPut<LoanGuarantor>(
      `/payroll/loans/${loanId}/guarantors/${guarantorId}/consent`,
      { consent_given: consentGiven, notes },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to record consent",
    };
  }
}

// =========================
// Staff-specific Loan Actions
// =========================

export async function getStaffLoans(
  staffId: string
): Promise<ActionResult<StaffLoanListItem[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StaffLoanListItem[]>(
      `/payroll/staff/${staffId}/loans`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch staff loans",
    };
  }
}

export async function checkLoanEligibility(
  staffId: string,
  loanTypeId?: string
): Promise<ActionResult<LoanEligibility>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // Backend uses query param, not path param for loan_type_id
    const params = new URLSearchParams();
    if (loanTypeId) params.append("loan_type_id", loanTypeId);
    const url = `/payroll/staff/${staffId}/loan-eligibility${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<LoanEligibility>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to check loan eligibility",
    };
  }
}

// =========================
// Portfolio & Analytics
// =========================

export async function getLoanPortfolio(
  schoolId?: string
): Promise<ActionResult<LoanPortfolio>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (schoolId) params.append("school_id", schoolId);
    const url = `/payroll/loans/portfolio${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<LoanPortfolio>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch loan portfolio",
    };
  }
}

export async function exportPortfolio(
  schoolId?: string
): Promise<ActionResult<Blob>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // Backend uses GET for portfolio export (returns CSV stream)
    const params = new URLSearchParams();
    if (schoolId) params.append("school_id", schoolId);
    const url = `/payroll/loans/portfolio/export${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<Blob>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to export portfolio",
    };
  }
}

export async function getLoanAging(
  schoolId?: string
): Promise<ActionResult<LoanAgingResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // Backend aging endpoint is at /reports/loan-aging (not /loans/aging)
    const params = new URLSearchParams();
    if (schoolId) params.append("school_id", schoolId);
    const url = `/payroll/reports/loan-aging${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<LoanAgingResponse>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch loan aging",
    };
  }
}

export async function exportLoanAging(
  schoolId?: string
): Promise<ActionResult<Blob>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // Backend aging export is GET at /reports/loan-aging/export
    const params = new URLSearchParams();
    if (schoolId) params.append("school_id", schoolId);
    const url = `/payroll/reports/loan-aging/export${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<Blob>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to export loan aging",
    };
  }
}
