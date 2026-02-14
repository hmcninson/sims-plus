"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  PaginatedResponse,
  Staff,
  StaffListItem,
  StaffWithAssignments,
  StaffCreate,
  StaffUpdate,
  StaffStats,
  StaffAssignment,
} from "@/types";

/**
 * Get auth context from cookies with token refresh
 */
async function getAuthContext() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  const subdomain = cookieStore.get("x-subdomain")?.value;
  console.log("[Staff.action] getAuthContext:", { hasToken: !!token, tokenLength: token?.length, subdomain });
  return {
    token: token || undefined,
    subdomain,
  };
}

// =========================
// Staff Actions
// =========================

export interface StaffFilters {
  search?: string;
  staff_type?: string;
  status?: string;
  gender?: string;
  department?: string;
  school_id?: string;
  page?: number;
  page_size?: number;
}

export async function getStaff(
  filters: StaffFilters = {}
): Promise<ActionResult<PaginatedResponse<StaffListItem>>> {
  try {
    const { token, subdomain } = await getAuthContext();

    const params = new URLSearchParams();
    if (filters.search) params.append("search", filters.search);
    if (filters.staff_type) params.append("staff_type", filters.staff_type);
    if (filters.status) params.append("status", filters.status);
    if (filters.gender) params.append("gender", filters.gender);
    if (filters.department) params.append("department", filters.department);
    if (filters.school_id) params.append("school_id", filters.school_id);
    if (filters.page) params.append("page", String(filters.page));
    if (filters.page_size) params.append("page_size", String(filters.page_size));

    const url = `/staff${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<PaginatedResponse<StaffListItem>>(url, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch staff",
    };
  }
}

export async function getStaffMember(
  id: string
): Promise<ActionResult<StaffWithAssignments>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StaffWithAssignments>(
      `/staff/${id}?include_assignments=true`,
      {
        token,
        subdomain,
      }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch staff member",
    };
  }
}

export async function generateStaffId(): Promise<ActionResult<string>> {
  try {
    const { token, subdomain } = await getAuthContext();
    console.log("[Staff.action] generateStaffId called:", { hasToken: !!token, subdomain });
    const response = await apiGet<{ staff_id: string }>("/staff/generate-id", {
      token,
      subdomain,
    });
    console.log("[Staff.action] generateStaffId response:", response);
    return { success: true, data: response.staff_id };
  } catch (error) {
    console.error("[Staff.action] generateStaffId error:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to generate staff ID",
    };
  }
}

export async function createStaff(
  data: StaffCreate
): Promise<ActionResult<Staff>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Staff>("/staff", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create staff member",
    };
  }
}

export async function updateStaff(
  id: string,
  data: StaffUpdate
): Promise<ActionResult<Staff>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<Staff>(`/staff/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update staff member",
    };
  }
}

export async function deleteStaff(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/staff/${id}`, { token, subdomain });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete staff member",
    };
  }
}

export async function getStaffStats(): Promise<ActionResult<StaffStats>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StaffStats>("/staff/stats", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch staff stats",
    };
  }
}

export async function getTeachingStaff(
  school_id?: string
): Promise<ActionResult<StaffListItem[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = school_id ? `?school_id=${school_id}` : "";
    const response = await apiGet<StaffListItem[]>(`/staff/teaching${params}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch teaching staff",
    };
  }
}

// =========================
// Staff Assignment Actions
// =========================

export interface StaffAssignmentCreate {
  section_id: string;
  is_class_teacher?: boolean;
  subject_id?: string;
}

export interface StaffAssignmentUpdate {
  is_class_teacher?: boolean;
  subject_id?: string;
}

export async function getStaffAssignments(
  staffId: string
): Promise<ActionResult<StaffAssignment[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StaffAssignment[]>(
      `/staff/${staffId}/assignments`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch staff assignments",
    };
  }
}

export async function getSectionStaff(
  sectionId: string
): Promise<ActionResult<StaffAssignment[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StaffAssignment[]>(
      `/staff/by-section/${sectionId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch section staff",
    };
  }
}

export async function assignStaffToSection(
  staffId: string,
  data: StaffAssignmentCreate
): Promise<ActionResult<StaffAssignment>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StaffAssignment>(
      `/staff/${staffId}/assignments`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to assign staff to section",
    };
  }
}

export async function updateStaffAssignment(
  staffId: string,
  assignmentId: string,
  data: StaffAssignmentUpdate
): Promise<ActionResult<StaffAssignment>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<StaffAssignment>(
      `/staff/${staffId}/assignments/${assignmentId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update staff assignment",
    };
  }
}

export async function removeStaffFromSection(
  staffId: string,
  sectionId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/staff/${staffId}/assignments/${sectionId}`, {
      token,
      subdomain,
    });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to remove staff from section",
    };
  }
}

// =========================
// Department Actions
// =========================

export interface Department {
  id: string;
  name: string;
  code?: string;
  description?: string;
  head_id?: string;
  head_name?: string;
  staff_count: number;
  created_at?: string;
  updated_at?: string;
}

export interface DepartmentCreate {
  name: string;
  code?: string;
  description?: string;
  head_id?: string;
}

export interface DepartmentUpdate {
  name?: string;
  code?: string;
  description?: string;
  head_id?: string;
}

export async function getDepartments(
  search?: string
): Promise<ActionResult<Department[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    console.log("[Departments] Fetching departments:", { subdomain, hasToken: !!token });
    const params = search ? `?search=${encodeURIComponent(search)}` : "";
    const response = await apiGet<Department[]>(`/staff/departments${params}`, {
      token,
      subdomain,
    });
    console.log("[Departments] Fetch response:", response);
    return { success: true, data: response };
  } catch (error) {
    console.error("[Departments] Fetch error:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch departments",
    };
  }
}

export async function getDepartment(
  id: string
): Promise<ActionResult<Department>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<Department>(`/staff/departments/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch department",
    };
  }
}

export async function createDepartment(
  data: DepartmentCreate
): Promise<ActionResult<Department>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Department>("/staff/departments", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create department",
    };
  }
}

export async function updateDepartment(
  id: string,
  data: DepartmentUpdate
): Promise<ActionResult<Department>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<Department>(`/staff/departments/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update department",
    };
  }
}

export async function deleteDepartment(
  id: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/staff/departments/${id}`, {
      token,
      subdomain,
    });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete department",
    };
  }
}

// =========================
// Import/Export Actions
// =========================

export interface StaffImportPreviewRow {
  row: number;
  parsed: {
    first_name: string;
    middle_name: string | null;
    last_name: string;
    email: string;
    phone: string;
    gender: string;
    date_of_birth: string | null;
    job_title: string;
    staff_type: string;
    status: string;
    department: string | null;
    employment_date: string;
  };
  valid: boolean;
  errors: string[];
}

export interface StaffImportPreviewResult {
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  preview: StaffImportPreviewRow[];
  errors: Array<{ row: number; error: string }>;
}

export interface StaffImportResult {
  total: number;
  success: number;
  failed: number;
  errors: Array<{ row: number; error: string }>;
}

/**
 * Export staff to CSV
 */
export async function exportStaff(filters?: {
  status?: string;
  staff_type?: string;
  department?: string;
}): Promise<ActionResult<Blob>> {
  try {
    const { token, subdomain } = await getAuthContext();

    if (!token || !subdomain) {
      return { success: false, error: "Not authenticated" };
    }

    const params = new URLSearchParams();
    if (filters?.status) params.append("status", filters.status);
    if (filters?.staff_type) params.append("staff_type", filters.staff_type);
    if (filters?.department) params.append("department", filters.department);

    const url = `${process.env.API_URL || "http://localhost:8000/api/v1"}/staff/export${params.toString() ? `?${params.toString()}` : ""}`;

    const response = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Subdomain": subdomain,
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Export failed");
    }

    const blob = await response.blob();
    return { success: true, data: blob };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to export staff",
    };
  }
}

/**
 * Download staff import template
 */
export async function downloadImportTemplate(): Promise<ActionResult<Blob>> {
  try {
    const { token, subdomain } = await getAuthContext();

    if (!token || !subdomain) {
      return { success: false, error: "Not authenticated" };
    }

    const url = `${process.env.API_URL || "http://localhost:8000/api/v1"}/staff/export/template`;

    const response = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Subdomain": subdomain,
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Download failed");
    }

    const blob = await response.blob();
    return { success: true, data: blob };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to download template",
    };
  }
}

/**
 * Preview staff import from CSV (validates without saving)
 */
export async function previewStaffImport(
  formData: FormData
): Promise<ActionResult<StaffImportPreviewResult>> {
  try {
    const { token, subdomain } = await getAuthContext();

    if (!token || !subdomain) {
      return { success: false, error: "Not authenticated" };
    }

    // Add preview flag
    formData.append("preview", "true");

    const url = `${process.env.API_URL || "http://localhost:8000/api/v1"}/staff/import`;

    const response = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Subdomain": subdomain,
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Preview failed");
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

/**
 * Import staff from CSV
 */
export async function importStaff(
  formData: FormData
): Promise<ActionResult<StaffImportResult>> {
  try {
    const { token, subdomain } = await getAuthContext();

    if (!token || !subdomain) {
      return { success: false, error: "Not authenticated" };
    }

    // Add preview flag (false for actual import)
    formData.append("preview", "false");

    const url = `${process.env.API_URL || "http://localhost:8000/api/v1"}/staff/import`;

    const response = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Subdomain": subdomain,
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Import failed");
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to import staff",
    };
  }
}
