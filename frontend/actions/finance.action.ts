"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  // Fee Types
  FeeType,
  FeeTypeCreate,
  FeeTypeUpdate,
  FeeTypeListResponse,
  // Fee Structures
  FeeStructureWithItems,
  FeeStructureCreate,
  FeeStructureUpdate,
  FeeStructureListResponse,
  FeeItem,
  FeeItemCreate,
  FeeItemUpdate,
  // Invoices
  InvoiceWithDetails,
  InvoiceCreate,
  InvoiceUpdate,
  InvoiceListResponse,
  InvoiceBulkGenerate,
  InvoiceBulkResult,
  InvoiceIssue,
  InvoiceCancel,
  // Payments
  PaymentWithDetails,
  PaymentCreate,
  PaymentListResponse,
  PaymentVoid,
  PaymentReceipt,
  // Scholarships
  ScholarshipWithStats,
  ScholarshipCreate,
  ScholarshipUpdate,
  ScholarshipListResponse,
  ScholarshipAward,
  ScholarshipBulkAward,
  ScholarshipBulkAwardResult,
  ScholarshipRevoke,
  StudentScholarshipWithDetails,
  StudentScholarshipListResponse,
  // Dashboard
  FinanceDashboard,
  // Invoice Email
  InvoiceEmailRequest,
  InvoiceEmailResponse,
  // Missing Invoices
  StudentsMissingInvoicesResponse,
  // Invoice Sync
  InvoiceSyncRequest,
  InvoiceSyncPreview,
  InvoiceSyncResult,
  // Credit Notes
  CreditNoteWithDetails,
  CreditNoteCreate,
  CreditNoteUpdate,
  CreditNoteApply,
  CreditNoteRefund,
  CreditNoteCancel,
  CreditNoteListResponse,
  StudentCreditBalance,
} from "@/types";

/**
 * Get auth context from cookies with token refresh
 */
async function getAuthContext() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  return {
    token: token || undefined,
    subdomain: cookieStore.get("x-subdomain")?.value,
  };
}

// =========================
// Dashboard Actions
// =========================

export async function getFinanceDashboard(
  academicYearId?: string,
  termId?: string
): Promise<ActionResult<FinanceDashboard>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (academicYearId) params.append("academic_year_id", academicYearId);
    if (termId) params.append("term_id", termId);
    const query = params.toString() ? `?${params.toString()}` : "";
    const response = await apiGet<FinanceDashboard>(`/finance/dashboard${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch finance dashboard",
    };
  }
}

// =========================
// Fee Type Actions
// =========================

export async function getFeeTypes(params?: {
  search?: string;
  category?: string;
  isActive?: boolean;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<FeeTypeListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.append("search", params.search);
    if (params?.category) searchParams.append("category", params.category);
    if (params?.isActive !== undefined) searchParams.append("is_active", String(params.isActive));
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<FeeTypeListResponse>(`/finance/fee-types${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch fee types",
    };
  }
}

export async function searchFeeTypes(query: string): Promise<ActionResult<FeeType[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    searchParams.append("q", query);
    const response = await apiGet<FeeType[]>(`/finance/fee-types/search?${searchParams.toString()}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to search fee types",
    };
  }
}

export async function getFeeType(id: string): Promise<ActionResult<FeeType>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<FeeType>(`/finance/fee-types/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch fee type",
    };
  }
}

export async function createFeeType(data: FeeTypeCreate): Promise<ActionResult<FeeType>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<FeeType>("/finance/fee-types", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create fee type",
    };
  }
}

export async function updateFeeType(id: string, data: FeeTypeUpdate): Promise<ActionResult<FeeType>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<FeeType>(`/finance/fee-types/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update fee type",
    };
  }
}

export async function deleteFeeType(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/finance/fee-types/${id}`, { token, subdomain });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete fee type",
    };
  }
}

// =========================
// Fee Structure Actions
// =========================

export async function getFeeStructures(params?: {
  academicYearId?: string;
  termId?: string;
  isActive?: boolean;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<FeeStructureListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.academicYearId) searchParams.append("academic_year_id", params.academicYearId);
    if (params?.termId) searchParams.append("term_id", params.termId);
    if (params?.isActive !== undefined) searchParams.append("is_active", String(params.isActive));
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<FeeStructureListResponse>(`/finance/fee-structures${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch fee structures",
    };
  }
}

export async function getFeeStructure(id: string): Promise<ActionResult<FeeStructureWithItems>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<FeeStructureWithItems>(`/finance/fee-structures/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch fee structure",
    };
  }
}

export async function createFeeStructure(
  data: FeeStructureCreate
): Promise<ActionResult<FeeStructureWithItems>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<FeeStructureWithItems>("/finance/fee-structures", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create fee structure",
    };
  }
}

export async function updateFeeStructure(
  id: string,
  data: FeeStructureUpdate
): Promise<ActionResult<FeeStructureWithItems>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<FeeStructureWithItems>(`/finance/fee-structures/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update fee structure",
    };
  }
}

export async function deleteFeeStructure(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/finance/fee-structures/${id}`, { token, subdomain });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete fee structure",
    };
  }
}

export async function addFeeItem(
  feeStructureId: string,
  data: FeeItemCreate
): Promise<ActionResult<FeeItem>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<FeeItem>(
      `/finance/fee-structures/${feeStructureId}/items`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to add fee item",
    };
  }
}

export async function updateFeeItem(
  feeStructureId: string,
  itemId: string,
  data: FeeItemUpdate
): Promise<ActionResult<FeeItem>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<FeeItem>(
      `/finance/fee-structures/${feeStructureId}/items/${itemId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update fee item",
    };
  }
}

export async function deleteFeeItem(
  feeStructureId: string,
  itemId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/finance/fee-structures/${feeStructureId}/items/${itemId}`, {
      token,
      subdomain,
    });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete fee item",
    };
  }
}

export async function copyFeeStructure(
  feeStructureId: string,
  params: {
    newName: string;
    academicYearId?: string;
    termId?: string;
  }
): Promise<ActionResult<FeeStructureWithItems>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    searchParams.append("new_name", params.newName);
    if (params.academicYearId) searchParams.append("academic_year_id", params.academicYearId);
    if (params.termId) searchParams.append("term_id", params.termId);
    const response = await apiPost<FeeStructureWithItems>(
      `/finance/fee-structures/${feeStructureId}/copy?${searchParams.toString()}`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to copy fee structure",
    };
  }
}

// =========================
// Invoice Actions
// =========================

export async function getInvoices(params?: {
  studentId?: string;
  academicYearId?: string;
  termId?: string;
  status?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<InvoiceListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.studentId) searchParams.append("student_id", params.studentId);
    if (params?.academicYearId) searchParams.append("academic_year_id", params.academicYearId);
    if (params?.termId) searchParams.append("term_id", params.termId);
    if (params?.status) searchParams.append("status", params.status);
    if (params?.search) searchParams.append("search", params.search);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<InvoiceListResponse>(`/finance/invoices${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch invoices",
    };
  }
}

export async function getInvoice(id: string): Promise<ActionResult<InvoiceWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<InvoiceWithDetails>(`/finance/invoices/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch invoice",
    };
  }
}

export async function createInvoice(
  data: InvoiceCreate
): Promise<ActionResult<InvoiceWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<InvoiceWithDetails>("/finance/invoices", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create invoice",
    };
  }
}

export async function updateInvoice(
  id: string,
  data: InvoiceUpdate
): Promise<ActionResult<InvoiceWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<InvoiceWithDetails>(`/finance/invoices/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update invoice",
    };
  }
}

export async function deleteInvoice(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/finance/invoices/${id}`, { token, subdomain });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete invoice",
    };
  }
}

export async function issueInvoice(
  id: string,
  data?: InvoiceIssue
): Promise<ActionResult<InvoiceWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<InvoiceWithDetails>(
      `/finance/invoices/${id}/issue`,
      data || {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to issue invoice",
    };
  }
}

export async function cancelInvoice(
  id: string,
  data: InvoiceCancel
): Promise<ActionResult<InvoiceWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<InvoiceWithDetails>(
      `/finance/invoices/${id}/cancel`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to cancel invoice",
    };
  }
}

export async function bulkGenerateInvoices(
  data: InvoiceBulkGenerate
): Promise<ActionResult<InvoiceBulkResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<InvoiceBulkResult>(
      "/finance/invoices/bulk-generate",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to generate invoices",
    };
  }
}

export async function getStudentsMissingInvoices(params: {
  feeStructureId: string;
  academicYearId: string;
  termId: string;
  classId?: string;
  sectionId?: string;
}): Promise<ActionResult<StudentsMissingInvoicesResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    searchParams.append("fee_structure_id", params.feeStructureId);
    searchParams.append("academic_year_id", params.academicYearId);
    searchParams.append("term_id", params.termId);
    if (params.classId) searchParams.append("class_id", params.classId);
    if (params.sectionId) searchParams.append("section_id", params.sectionId);
    const query = `?${searchParams.toString()}`;
    const response = await apiGet<StudentsMissingInvoicesResponse>(
      `/finance/invoices/missing${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch students missing invoices",
    };
  }
}

export async function getInvoiceSyncPreview(params: {
  feeStructureId: string;
  academicYearId: string;
  termId: string;
}): Promise<ActionResult<InvoiceSyncPreview>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    searchParams.append("fee_structure_id", params.feeStructureId);
    searchParams.append("academic_year_id", params.academicYearId);
    searchParams.append("term_id", params.termId);
    const query = `?${searchParams.toString()}`;
    const response = await apiGet<InvoiceSyncPreview>(
      `/finance/invoices/sync-preview${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to get sync preview",
    };
  }
}

export async function syncInvoicesWithFeeStructure(
  data: InvoiceSyncRequest
): Promise<ActionResult<InvoiceSyncResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<InvoiceSyncResult>(
      "/finance/invoices/sync",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to sync invoices",
    };
  }
}

export async function syncSingleInvoice(
  invoiceId: string,
  feeStructureId: string
): Promise<ActionResult<InvoiceSyncResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<InvoiceSyncResult>(
      "/finance/invoices/sync",
      {
        fee_structure_id: feeStructureId,
        invoice_ids: [invoiceId],
      },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to sync invoice",
    };
  }
}

export async function getStudentInvoices(
  studentId: string,
  academicYearId?: string,
  page?: number,
  pageSize?: number
): Promise<ActionResult<InvoiceListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (academicYearId) searchParams.append("academic_year_id", academicYearId);
    if (page) searchParams.append("page", String(page));
    if (pageSize) searchParams.append("page_size", String(pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<InvoiceListResponse>(
      `/finance/students/${studentId}/invoices${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student invoices",
    };
  }
}

// =========================
// Payment Actions
// =========================

export async function getPayments(params?: {
  studentId?: string;
  invoiceId?: string;
  academicYearId?: string;
  termId?: string;
  status?: string;
  paymentMethod?: string;
  search?: string;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<PaymentListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.studentId) searchParams.append("student_id", params.studentId);
    if (params?.invoiceId) searchParams.append("invoice_id", params.invoiceId);
    if (params?.academicYearId) searchParams.append("academic_year_id", params.academicYearId);
    if (params?.termId) searchParams.append("term_id", params.termId);
    if (params?.status) searchParams.append("status", params.status);
    if (params?.paymentMethod) searchParams.append("payment_method", params.paymentMethod);
    if (params?.search) searchParams.append("search", params.search);
    if (params?.dateFrom) searchParams.append("date_from", params.dateFrom);
    if (params?.dateTo) searchParams.append("date_to", params.dateTo);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<PaymentListResponse>(`/finance/payments${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch payments",
    };
  }
}

export async function getPayment(id: string): Promise<ActionResult<PaymentWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<PaymentWithDetails>(`/finance/payments/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch payment",
    };
  }
}

export async function recordPayment(
  data: PaymentCreate
): Promise<ActionResult<PaymentWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PaymentWithDetails>("/finance/payments", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to record payment",
    };
  }
}

export async function voidPayment(
  id: string,
  data: PaymentVoid
): Promise<ActionResult<PaymentWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PaymentWithDetails>(
      `/finance/payments/${id}/void`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to void payment",
    };
  }
}

export async function getStudentPayments(
  studentId: string,
  page?: number,
  pageSize?: number
): Promise<ActionResult<PaymentListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (page) searchParams.append("page", String(page));
    if (pageSize) searchParams.append("page_size", String(pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<PaymentListResponse>(
      `/finance/students/${studentId}/payments${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student payments",
    };
  }
}

export async function getPaymentReceipt(
  paymentId: string
): Promise<ActionResult<PaymentReceipt>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<PaymentReceipt>(
      `/finance/payments/${paymentId}/receipt`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch payment receipt",
    };
  }
}

// =========================
// Scholarship Actions
// =========================

export async function getScholarships(params?: {
  academicYearId?: string;
  scholarshipType?: string;
  isActive?: boolean;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<ScholarshipListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.academicYearId) searchParams.append("academic_year_id", params.academicYearId);
    if (params?.scholarshipType) searchParams.append("scholarship_type", params.scholarshipType);
    if (params?.isActive !== undefined) searchParams.append("is_active", String(params.isActive));
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<ScholarshipListResponse>(`/finance/scholarships${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch scholarships",
    };
  }
}

export async function getScholarship(id: string): Promise<ActionResult<ScholarshipWithStats>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ScholarshipWithStats>(`/finance/scholarships/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch scholarship",
    };
  }
}

export async function createScholarship(
  data: ScholarshipCreate
): Promise<ActionResult<ScholarshipWithStats>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ScholarshipWithStats>("/finance/scholarships", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create scholarship",
    };
  }
}

export async function updateScholarship(
  id: string,
  data: ScholarshipUpdate
): Promise<ActionResult<ScholarshipWithStats>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<ScholarshipWithStats>(`/finance/scholarships/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update scholarship",
    };
  }
}

export async function deleteScholarship(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/finance/scholarships/${id}`, { token, subdomain });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete scholarship",
    };
  }
}

export async function awardScholarship(
  scholarshipId: string,
  data: ScholarshipAward
): Promise<ActionResult<StudentScholarshipWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StudentScholarshipWithDetails>(
      `/finance/scholarships/${scholarshipId}/award`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to award scholarship",
    };
  }
}

export async function bulkAwardScholarship(
  scholarshipId: string,
  data: ScholarshipBulkAward
): Promise<ActionResult<ScholarshipBulkAwardResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ScholarshipBulkAwardResult>(
      `/finance/scholarships/${scholarshipId}/award-bulk`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to bulk award scholarship",
    };
  }
}

export async function revokeScholarship(
  scholarshipId: string,
  studentScholarshipId: string,
  data: ScholarshipRevoke
): Promise<ActionResult<StudentScholarshipWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StudentScholarshipWithDetails>(
      `/finance/scholarships/${scholarshipId}/recipients/${studentScholarshipId}/revoke`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to revoke scholarship",
    };
  }
}

export async function getScholarshipRecipients(
  scholarshipId: string,
  params?: {
    academicYearId?: string;
    status?: string;
    page?: number;
    pageSize?: number;
  }
): Promise<ActionResult<StudentScholarshipListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.academicYearId) searchParams.append("academic_year_id", params.academicYearId);
    if (params?.status) searchParams.append("status", params.status);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<StudentScholarshipListResponse>(
      `/finance/scholarships/${scholarshipId}/recipients${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch scholarship recipients",
    };
  }
}

export async function getStudentScholarships(
  studentId: string,
  params?: {
    academicYearId?: string;
    status?: string;
    page?: number;
    pageSize?: number;
  }
): Promise<ActionResult<StudentScholarshipListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.academicYearId) searchParams.append("academic_year_id", params.academicYearId);
    if (params?.status) searchParams.append("status", params.status);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<StudentScholarshipListResponse>(
      `/finance/students/${studentId}/scholarships${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student scholarships",
    };
  }
}

// =========================
// Invoice PDF Actions
// =========================

/**
 * Get authorization context for invoice PDF download.
 * Returns the token and subdomain needed for API requests.
 */
export async function getInvoicePdfAuthContext(): Promise<ActionResult<{ token: string; subdomain: string }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    if (!token || !subdomain) {
      return {
        success: false,
        error: "Authentication required to download invoice",
      };
    }
    return {
      success: true,
      data: { token, subdomain },
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to get auth context",
    };
  }
}

// =========================
// Invoice Email Actions
// =========================

export async function emailInvoice(
  invoiceId: string,
  data: InvoiceEmailRequest
): Promise<ActionResult<InvoiceEmailResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<InvoiceEmailResponse>(
      `/finance/invoices/${invoiceId}/email`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to send invoice email",
    };
  }
}

// =========================
// Credit Note Actions
// =========================

export async function getCreditNotes(params?: {
  studentId?: string;
  status?: string;
  type?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<CreditNoteListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.studentId) searchParams.append("student_id", params.studentId);
    if (params?.status) searchParams.append("status", params.status);
    if (params?.type) searchParams.append("type", params.type);
    if (params?.search) searchParams.append("search", params.search);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<CreditNoteListResponse>(
      `/finance/credit-notes${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch credit notes",
    };
  }
}

export async function getCreditNote(creditNoteId: string): Promise<ActionResult<CreditNoteWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<CreditNoteWithDetails>(
      `/finance/credit-notes/${creditNoteId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch credit note",
    };
  }
}

export async function createCreditNote(data: CreditNoteCreate): Promise<ActionResult<CreditNoteWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<CreditNoteWithDetails>(
      "/finance/credit-notes",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create credit note",
    };
  }
}

export async function updateCreditNote(
  creditNoteId: string,
  data: CreditNoteUpdate
): Promise<ActionResult<CreditNoteWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<CreditNoteWithDetails>(
      `/finance/credit-notes/${creditNoteId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update credit note",
    };
  }
}

export async function issueCreditNote(
  creditNoteId: string,
  autoApply: boolean = false
): Promise<ActionResult<CreditNoteWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const url = autoApply
      ? `/finance/credit-notes/${creditNoteId}/issue?auto_apply=true`
      : `/finance/credit-notes/${creditNoteId}/issue`;
    const response = await apiPost<CreditNoteWithDetails>(
      url,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to issue credit note",
    };
  }
}

export async function applyCreditNote(
  creditNoteId: string,
  data: CreditNoteApply
): Promise<ActionResult<CreditNoteWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<CreditNoteWithDetails>(
      `/finance/credit-notes/${creditNoteId}/apply`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to apply credit note",
    };
  }
}

export async function refundCreditNote(
  creditNoteId: string,
  data: CreditNoteRefund
): Promise<ActionResult<CreditNoteWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<CreditNoteWithDetails>(
      `/finance/credit-notes/${creditNoteId}/refund`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to refund credit note",
    };
  }
}

export async function cancelCreditNote(
  creditNoteId: string,
  data: CreditNoteCancel
): Promise<ActionResult<CreditNoteWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<CreditNoteWithDetails>(
      `/finance/credit-notes/${creditNoteId}/cancel`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to cancel credit note",
    };
  }
}

export async function deleteCreditNote(creditNoteId: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/finance/credit-notes/${creditNoteId}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete credit note",
    };
  }
}

export async function getStudentCreditBalance(studentId: string): Promise<ActionResult<StudentCreditBalance>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StudentCreditBalance>(
      `/finance/students/${studentId}/credit-balance`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student credit balance",
    };
  }
}

export async function getStudentCreditNotes(
  studentId: string,
  params?: {
    includeCancelled?: boolean;
    page?: number;
    pageSize?: number;
  }
): Promise<ActionResult<CreditNoteListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.includeCancelled) searchParams.append("include_cancelled", String(params.includeCancelled));
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<CreditNoteListResponse>(
      `/finance/students/${studentId}/credit-notes${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student credit notes",
    };
  }
}
