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
  return {
    token: token || undefined,
    subdomain: cookieStore.get("x-subdomain")?.value,
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
