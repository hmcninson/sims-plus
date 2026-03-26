"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiPatch, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  PaginatedResponse,
  Student,
  StudentListItem,
  StudentWithGuardians,
  StudentCreate,
  StudentUpdate,
  StudentStats,
  StudentBulkResponse,
  Guardian,
  GuardianCreate,
  GuardianUpdate,
  StudentGuardianLink,
  StudentGuardianCreate,
  GuardianWithRelationship,
  StudentGuardianUpdate,
  ClassHistoryListResponse,
  StatusHistoryListResponse,
  EnrollmentAnalyticsResponse,
  OutstandingFeeCheckResponse,
  WithdrawalInitiateRequest,
  WithdrawalClearanceResponse,
  ClearanceUpdateRequest,
  WithdrawalCompleteResponse,
  TransferInitiateRequest,
  ChainTransferRequest,
  ChainTransferResponse,
  DocumentListResponse,
  StudentDocumentResponse,
  DocumentDownloadResponse,
  PreviousSchoolRecord,
  PreviousSchoolCreate,
  PreviousSchoolUpdate,
  PromotionRule,
  PromotionRuleCreate,
  PromotionRuleUpdate,
  PromotionRuleListResponse,
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
// Student Actions
// =========================

export interface StudentFilters {
  search?: string;
  class_id?: string;
  section_id?: string;
  school_id?: string;
  status?: string;
  gender?: string;
  is_boarder?: boolean;
  page?: number;
  page_size?: number;
}

export async function getStudents(
  filters: StudentFilters = {}
): Promise<ActionResult<PaginatedResponse<StudentListItem>>> {
  try {
    const { token, subdomain } = await getAuthContext();

    const params = new URLSearchParams();
    if (filters.search) params.append("search", filters.search);
    if (filters.class_id) params.append("class_id", filters.class_id);
    if (filters.section_id) params.append("section_id", filters.section_id);
    if (filters.school_id) params.append("school_id", filters.school_id);
    if (filters.status) params.append("status", filters.status);
    if (filters.gender) params.append("gender", filters.gender);
    if (filters.is_boarder !== undefined)
      params.append("is_boarder", String(filters.is_boarder));
    if (filters.page) params.append("page", String(filters.page));
    if (filters.page_size) params.append("page_size", String(filters.page_size));

    const url = `/students${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<PaginatedResponse<StudentListItem>>(url, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch students",
    };
  }
}

export async function getStudent(
  id: string
): Promise<ActionResult<StudentWithGuardians>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StudentWithGuardians>(
      `/students/${id}?include_guardians=true`,
      {
        token,
        subdomain,
      }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student",
    };
  }
}

export async function generateStudentId(): Promise<ActionResult<string>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<{ student_id: string }>("/students/generate-id", {
      token,
      subdomain,
    });
    return { success: true, data: response.student_id };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to generate student ID",
    };
  }
}

export async function createStudent(
  data: StudentCreate
): Promise<ActionResult<Student>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Student>("/students", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create student",
    };
  }
}

export async function updateStudent(
  id: string,
  data: StudentUpdate
): Promise<ActionResult<Student>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<Student>(`/students/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update student",
    };
  }
}

export async function deleteStudent(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/students/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete student",
    };
  }
}

export async function getStudentStats(): Promise<ActionResult<StudentStats>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StudentStats>("/students/stats", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student stats",
    };
  }
}

export async function bulkCreateStudents(
  students: StudentCreate[]
): Promise<ActionResult<StudentBulkResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StudentBulkResponse>(
      "/students/bulk",
      { students },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to bulk create students",
    };
  }
}

// =========================
// Student Guardian Actions
// =========================

export async function getStudentGuardians(
  studentId: string
): Promise<ActionResult<StudentGuardianLink[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StudentGuardianLink[]>(
      `/students/${studentId}/guardians`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch guardians",
    };
  }
}

export async function addGuardianToStudent(
  studentId: string,
  data: GuardianWithRelationship
): Promise<ActionResult<StudentGuardianLink>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StudentGuardianLink>(
      `/students/${studentId}/guardians`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to add guardian",
    };
  }
}

export async function linkExistingGuardian(
  studentId: string,
  data: StudentGuardianCreate
): Promise<ActionResult<StudentGuardianLink>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StudentGuardianLink>(
      `/students/${studentId}/guardians/link`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to link guardian",
    };
  }
}

export async function updateGuardianLink(
  studentId: string,
  guardianId: string,
  data: StudentGuardianUpdate
): Promise<ActionResult<StudentGuardianLink>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<StudentGuardianLink>(
      `/students/${studentId}/guardians/${guardianId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update guardian link",
    };
  }
}

export async function unlinkGuardian(
  studentId: string,
  guardianId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/students/${studentId}/guardians/${guardianId}`, {
      token,
      subdomain,
    });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to unlink guardian",
    };
  }
}

// =========================
// Guardian Actions
// =========================

export async function getGuardians(
  search?: string,
  page: number = 1,
  page_size: number = 20
): Promise<ActionResult<PaginatedResponse<Guardian>>> {
  try {
    const { token, subdomain } = await getAuthContext();

    const params = new URLSearchParams();
    if (search) params.append("search", search);
    params.append("page", String(page));
    params.append("page_size", String(page_size));

    const url = `/guardians?${params.toString()}`;
    const response = await apiGet<PaginatedResponse<Guardian>>(url, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch guardians",
    };
  }
}

export async function getGuardian(id: string): Promise<ActionResult<Guardian>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<Guardian>(`/guardians/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch guardian",
    };
  }
}

export async function createGuardian(
  data: GuardianCreate
): Promise<ActionResult<Guardian>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Guardian>("/guardians", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create guardian",
    };
  }
}

export async function updateGuardian(
  id: string,
  data: GuardianUpdate
): Promise<ActionResult<Guardian>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<Guardian>(`/guardians/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update guardian",
    };
  }
}

export async function deleteGuardian(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/guardians/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete guardian",
    };
  }
}

export async function getGuardianStudents(
  guardianId: string
): Promise<ActionResult<StudentListItem[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StudentListItem[]>(
      `/guardians/${guardianId}/students`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to fetch guardian's students",
    };
  }
}

// =========================
// Student History Actions
// =========================

export async function getClassHistory(
  studentId: string
): Promise<ActionResult<ClassHistoryListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ClassHistoryListResponse>(
      `/students/${studentId}/class-history`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch class history",
    };
  }
}

export async function getStatusHistory(
  studentId: string
): Promise<ActionResult<StatusHistoryListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StatusHistoryListResponse>(
      `/students/${studentId}/status-history`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch status history",
    };
  }
}

export async function getEnrollmentAnalytics(
  schoolId?: string
): Promise<ActionResult<EnrollmentAnalyticsResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = schoolId ? `?school_id=${schoolId}` : "";
    const response = await apiGet<EnrollmentAnalyticsResponse>(
      `/students/enrollment-analytics${params}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch enrollment analytics",
    };
  }
}

// =========================
// Import/Export Actions
// =========================

export interface ImportTemplate {
  headers: string[];
  required_fields: string[];
  example_row: Record<string, string>;
}

export interface ImportPreviewResult {
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  preview: Record<string, unknown>[];
  errors: Array<{ row: number; field: string; message: string }>;
}

export interface ImportResult {
  total_rows: number;
  created: number;
  failed: number;
  errors: Array<{ row: number; error: string }>;
}

export async function getImportTemplate(): Promise<ActionResult<ImportTemplate>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ImportTemplate>("/students/import/template", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to get import template",
    };
  }
}

export async function importStudentsPreview(
  formData: FormData
): Promise<ActionResult<ImportPreviewResult>> {
  try {
    const { token, subdomain } = await getAuthContext();

    // Add preview flag - student IDs are always auto-generated
    formData.append("preview", "true");
    formData.append("auto_generate_ids", "true");

    const response = await fetch(
      `${process.env.API_URL || "http://localhost:8000/api/v1"}/students/import`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Subdomain": subdomain || "",
        },
        body: formData,
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Import preview failed");
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to preview import",
    };
  }
}

export async function importStudents(
  formData: FormData
): Promise<ActionResult<ImportResult>> {
  try {
    const { token, subdomain } = await getAuthContext();

    // Add import flag - student IDs are always auto-generated
    formData.append("preview", "false");
    formData.append("auto_generate_ids", "true");

    const response = await fetch(
      `${process.env.API_URL || "http://localhost:8000/api/v1"}/students/import`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Subdomain": subdomain || "",
        },
        body: formData,
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Import failed");
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to import students",
    };
  }
}

export async function exportStudents(
  filters: StudentFilters = {}
): Promise<ActionResult<StudentListItem[]>> {
  try {
    const { token, subdomain } = await getAuthContext();

    if (!token || !subdomain) {
      return { success: false, error: "Not authenticated" };
    }

    // Paginate through all results (backend limits page_size to 100)
    const allStudents: StudentListItem[] = [];
    let page = 1;
    let hasMore = true;

    while (hasMore) {
      const params = new URLSearchParams();
      if (filters.search) params.append("search", filters.search);
      if (filters.class_id) params.append("class_id", filters.class_id);
      if (filters.status) params.append("status", filters.status);
      params.append("page", String(page));
      params.append("page_size", "100");

      const url = `/students?${params.toString()}`;
      const response = await apiGet<PaginatedResponse<StudentListItem>>(url, {
        token,
        subdomain,
      });

      allStudents.push(...(response.items || []));
      hasMore = response.has_next;
      page++;

      // Safety limit to prevent infinite loops
      if (page > 100) break;
    }

    return { success: true, data: allStudents };
  } catch (error: unknown) {
    let errorMessage = "Failed to export students";
    if (error instanceof Error) {
      errorMessage = error.message;
    } else if (typeof error === "string") {
      errorMessage = error;
    } else if (error && typeof error === "object" && "message" in error) {
      errorMessage = String((error as { message: unknown }).message);
    }
    return { success: false, error: errorMessage };
  }
}

// =========================
// Withdrawal & Transfer Actions
// =========================

export async function checkOutstandingFees(
  studentId: string
): Promise<ActionResult<OutstandingFeeCheckResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<OutstandingFeeCheckResponse>(
      `/students/${studentId}/outstanding-fees`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to check outstanding fees",
    };
  }
}

export async function initiateWithdrawal(
  studentId: string,
  data: WithdrawalInitiateRequest
): Promise<ActionResult<{ clearance_id: string; has_outstanding_fees: boolean; outstanding_amount: number; fee_override: boolean }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<{ clearance_id: string; has_outstanding_fees: boolean; outstanding_amount: number; fee_override: boolean }>(
      `/students/${studentId}/withdraw`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to initiate withdrawal",
    };
  }
}

export async function getWithdrawalClearance(
  studentId: string
): Promise<ActionResult<WithdrawalClearanceResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<WithdrawalClearanceResponse>(
      `/students/${studentId}/withdrawal-clearance`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch withdrawal clearance",
    };
  }
}

export async function updateClearance(
  studentId: string,
  clearanceId: string,
  data: ClearanceUpdateRequest
): Promise<ActionResult<WithdrawalClearanceResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<WithdrawalClearanceResponse>(
      `/students/${studentId}/withdrawal-clearance/${clearanceId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update clearance",
    };
  }
}

export async function completeWithdrawal(
  studentId: string
): Promise<ActionResult<WithdrawalCompleteResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<WithdrawalCompleteResponse>(
      `/students/${studentId}/complete-withdrawal`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to complete withdrawal",
    };
  }
}

export async function initiateTransfer(
  studentId: string,
  data: TransferInitiateRequest
): Promise<ActionResult<{ status_change_id: string; clearance_id: string; has_outstanding_fees: boolean; outstanding_amount: number; fee_override: boolean }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<{ status_change_id: string; clearance_id: string; has_outstanding_fees: boolean; outstanding_amount: number; fee_override: boolean }>(
      `/students/${studentId}/transfer`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to initiate transfer",
    };
  }
}

export async function completeTransfer(
  studentId: string
): Promise<ActionResult<Student>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Student>(
      `/students/${studentId}/complete-transfer`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to complete transfer",
    };
  }
}

export async function chainTransfer(
  studentId: string,
  data: ChainTransferRequest
): Promise<ActionResult<ChainTransferResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ChainTransferResponse>(
      `/students/${studentId}/chain-transfer`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to process chain transfer",
    };
  }
}

export async function downloadTransferCertificate(
  studentId: string
): Promise<ActionResult<Blob>> {
  try {
    const { token, subdomain } = await getAuthContext();

    const response = await fetch(
      `${process.env.API_URL || "http://localhost:8000/api/v1"}/students/${studentId}/transfer-certificate`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Subdomain": subdomain || "",
        },
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(
        (error as Record<string, string>).detail || "Failed to download transfer certificate"
      );
    }

    const blob = await response.blob();
    return { success: true, data: blob };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to download transfer certificate",
    };
  }
}

export async function exportStudentRecord(
  studentId: string,
  format: "json" | "pdf"
): Promise<ActionResult<Blob | Record<string, unknown>>> {
  try {
    const { token, subdomain } = await getAuthContext();

    const response = await fetch(
      `${process.env.API_URL || "http://localhost:8000/api/v1"}/students/${studentId}/export-record?format=${format}`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Subdomain": subdomain || "",
        },
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(
        (error as Record<string, string>).detail || "Failed to export student record"
      );
    }

    if (format === "pdf") {
      const blob = await response.blob();
      return { success: true, data: blob };
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to export student record",
    };
  }
}

// =========================
// Student Documents Actions
// =========================

export async function getStudentDocuments(
  studentId: string,
  documentType?: string
): Promise<ActionResult<DocumentListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (documentType) params.append("document_type", documentType);
    const url = `/students/${studentId}/documents${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<DocumentListResponse>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch documents",
    };
  }
}

export async function uploadStudentDocument(
  studentId: string,
  formData: FormData
): Promise<ActionResult<StudentDocumentResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();

    const response = await fetch(
      `${process.env.API_URL || "http://localhost:8000/api/v1"}/students/${studentId}/documents`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Subdomain": subdomain || "",
        },
        body: formData,
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(
        (error as Record<string, string>).detail || "Failed to upload document"
      );
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to upload document",
    };
  }
}

export async function deleteStudentDocument(
  studentId: string,
  documentId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/students/${studentId}/documents/${documentId}`, {
      token,
      subdomain,
    });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete document",
    };
  }
}

export async function getDocumentDownloadUrl(
  studentId: string,
  documentId: string
): Promise<ActionResult<DocumentDownloadResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<DocumentDownloadResponse>(
      `/students/${studentId}/documents/${documentId}/download`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to get download URL",
    };
  }
}

// =========================
// Previous Schools Actions
// =========================

export async function getPreviousSchools(
  studentId: string
): Promise<ActionResult<PreviousSchoolRecord[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<PreviousSchoolRecord[]>(
      `/students/${studentId}/previous-schools`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch previous schools",
    };
  }
}

export async function createPreviousSchool(
  studentId: string,
  data: PreviousSchoolCreate
): Promise<ActionResult<PreviousSchoolRecord>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PreviousSchoolRecord>(
      `/students/${studentId}/previous-schools`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to add previous school",
    };
  }
}

export async function updatePreviousSchool(
  studentId: string,
  recordId: string,
  data: PreviousSchoolUpdate
): Promise<ActionResult<PreviousSchoolRecord>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<PreviousSchoolRecord>(
      `/students/${studentId}/previous-schools/${recordId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update previous school",
    };
  }
}

export async function deletePreviousSchool(
  studentId: string,
  recordId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/students/${studentId}/previous-schools/${recordId}`, {
      token,
      subdomain,
    });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete previous school",
    };
  }
}

// =========================
// Promotion Rules Actions
// =========================

export async function getPromotionRules(
  academicYearId?: string
): Promise<ActionResult<PromotionRuleListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (academicYearId) params.append("academic_year_id", academicYearId);
    const url = `/promotions/rules${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<PromotionRuleListResponse>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch promotion rules",
    };
  }
}

export async function createPromotionRule(
  data: PromotionRuleCreate
): Promise<ActionResult<PromotionRule>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PromotionRule>(
      "/promotions/rules",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create promotion rule",
    };
  }
}

export async function updatePromotionRule(
  ruleId: string,
  data: PromotionRuleUpdate
): Promise<ActionResult<PromotionRule>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<PromotionRule>(
      `/promotions/rules/${ruleId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update promotion rule",
    };
  }
}

export async function deletePromotionRule(
  ruleId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/promotions/rules/${ruleId}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete promotion rule",
    };
  }
}

export async function downloadGraduationCertificate(
  studentId: string
): Promise<ActionResult<Blob>> {
  try {
    const { token, subdomain } = await getAuthContext();

    const response = await fetch(
      `${process.env.API_URL || "http://localhost:8000/api/v1"}/promotions/graduation-certificate/${studentId}`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Subdomain": subdomain || "",
        },
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(
        (error as Record<string, string>).detail || "Failed to download graduation certificate"
      );
    }

    const blob = await response.blob();
    return { success: true, data: blob };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to download graduation certificate",
    };
  }
}
