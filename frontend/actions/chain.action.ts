"use server";

/**
 * SIMS Plus - Chain Management Server Actions
 *
 * Server actions for school chain operations: listing schools,
 * adding schools, managing user-school assignments, and fetching
 * the chain dashboard. Only accessible to chain_admin and
 * platform_admin roles.
 */

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  ChainSchool,
  ChainDashboard,
  AddSchoolData,
  AssignUserToSchoolData,
  RemoveUserFromSchoolData,
  ChainUser,
  ChainUserListResponse,
  SwitcherSchool,
} from "@/types/chain.type";

/**
 * Get auth context from cookies with token refresh.
 * The X-Active-School header is automatically included by api.ts
 * from the x-active-school cookie — no need to pass it explicitly.
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
// School Switcher Data
// =========================

/**
 * Get the list of schools accessible to the current user.
 * Used by SchoolProvider for the switcher dropdown.
 * Returns lightweight SwitcherSchool objects.
 */
export async function getAccessibleSchools(): Promise<ActionResult<SwitcherSchool[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<SwitcherSchool[]>("/chain/accessible", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch accessible schools",
    };
  }
}

// =========================
// Chain Dashboard
// =========================

/**
 * Get the chain-level dashboard with aggregated metrics per school.
 */
export async function getChainDashboard(
  academicYearId?: string,
  termId?: string
): Promise<ActionResult<ChainDashboard>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (academicYearId) params.append("academic_year_id", academicYearId);
    if (termId) params.append("term_id", termId);
    const query = params.toString() ? `?${params.toString()}` : "";
    const response = await apiGet<ChainDashboard>(`/chain/dashboard${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch chain dashboard",
    };
  }
}

// =========================
// School Management
// =========================

/**
 * List all schools in the chain tenant.
 */
export async function getChainSchools(
  page: number = 1,
  pageSize: number = 20,
  search?: string
): Promise<ActionResult<{ items: ChainSchool[]; total: number }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    params.append("page", String(page));
    params.append("page_size", String(pageSize));
    if (search) params.append("search", search);
    const response = await apiGet<{ items: ChainSchool[]; total: number }>(
      `/chain/schools?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch chain schools",
    };
  }
}

/**
 * Get details for a single school in the chain.
 */
export async function getChainSchool(schoolId: string): Promise<ActionResult<ChainSchool>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ChainSchool>(`/chain/schools/${schoolId}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch school details",
    };
  }
}

/**
 * Add a new school to the chain.
 */
export async function addSchoolToChain(data: AddSchoolData): Promise<ActionResult<ChainSchool>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ChainSchool>("/chain/schools", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to add school",
    };
  }
}

/**
 * Update a school in the chain.
 */
export async function updateChainSchool(
  schoolId: string,
  data: Partial<AddSchoolData>
): Promise<ActionResult<ChainSchool>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<ChainSchool>(`/chain/schools/${schoolId}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update school",
    };
  }
}

// =========================
// User-School Assignment
// =========================

/**
 * List users in the chain with their school assignments.
 */
export async function getChainUsers(
  page: number = 1,
  pageSize: number = 20,
  search?: string,
  schoolId?: string
): Promise<ActionResult<ChainUserListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    params.append("page", String(page));
    params.append("page_size", String(pageSize));
    if (search) params.append("search", search);
    if (schoolId) params.append("school_id", schoolId);
    const response = await apiGet<ChainUserListResponse>(
      `/chain/users?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch chain users",
    };
  }
}

/**
 * Assign a user to a school within the chain.
 */
export async function assignUserToSchool(
  data: AssignUserToSchoolData
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiPost("/chain/user-schools", data, {
      token,
      subdomain,
    });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to assign user to school",
    };
  }
}

/**
 * Remove a user's access to a specific school.
 */
export async function removeUserFromSchool(
  data: RemoveUserFromSchoolData
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(
      `/chain/user-schools/${data.user_id}/${data.school_id}`,
      { token, subdomain }
    );
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to remove user from school",
    };
  }
}
