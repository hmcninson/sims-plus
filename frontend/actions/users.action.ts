"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiPatch, apiDelete, apiUpload } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  User,
  UserCreate,
  UserUpdate,
  UserListResponse,
  UserImportResult,
  UserRole,
  UserStatus,
  MySchoolRole,
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
// User CRUD Actions
// =========================

export interface ListUsersParams {
  page?: number;
  page_size?: number;
  search?: string;
  role?: UserRole;
  status?: UserStatus;
  school_id?: string;
}

export async function listUsers(
  params: ListUsersParams = {}
): Promise<ActionResult<UserListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();

    const queryParams = new URLSearchParams();
    if (params.page) queryParams.set("page", params.page.toString());
    if (params.page_size) queryParams.set("page_size", params.page_size.toString());
    if (params.search) queryParams.set("search", params.search);
    if (params.role) queryParams.set("role", params.role);
    if (params.status) queryParams.set("status", params.status);
    if (params.school_id) queryParams.set("school_id", params.school_id);

    const url = `/users${queryParams.toString() ? `?${queryParams.toString()}` : ""}`;
    const response = await apiGet<UserListResponse>(url, { token, subdomain });

    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch users",
    };
  }
}

export async function getUser(id: string): Promise<ActionResult<User>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<User>(`/users/${id}`, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch user",
    };
  }
}

export async function createUser(data: UserCreate): Promise<ActionResult<User>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<User>("/users", data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create user",
    };
  }
}

export async function updateUser(
  id: string,
  data: UserUpdate
): Promise<ActionResult<User>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<User>(`/users/${id}`, data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update user",
    };
  }
}

export async function deleteUser(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/users/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete user",
    };
  }
}

// =========================
// Self-Service Actions
// =========================

export async function getMySchools(): Promise<ActionResult<MySchoolRole[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<MySchoolRole[]>("/users/me/schools", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch school roles",
    };
  }
}

// =========================
// Role & Status Actions
// =========================

export async function updateUserRole(
  id: string,
  role: UserRole
): Promise<ActionResult<User>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<User>(
      `/users/${id}/role`,
      { role },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update user role",
    };
  }
}

export async function updateUserStatus(
  id: string,
  status: UserStatus
): Promise<ActionResult<User>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<User>(
      `/users/${id}/status`,
      { status },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update user status",
    };
  }
}

export async function resetUserPassword(
  id: string,
  newPassword: string,
  sendEmail: boolean = true
): Promise<ActionResult<User>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<User>(
      `/users/${id}/reset-password`,
      { new_password: newPassword, send_email: sendEmail },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to reset password",
    };
  }
}

// =========================
// Stats Actions
// =========================

export async function getUserStatsByRole(): Promise<ActionResult<Record<string, number>>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<Record<string, number>>("/users/stats/by-role", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch user stats",
    };
  }
}

// =========================
// Bulk Import Actions
// =========================

/**
 * Preview a bulk user import (validation only, no creation).
 */
export async function previewUserImport(
  formData: FormData,
): Promise<ActionResult<UserImportResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // Ensure preview flag is set
    formData.set("preview", "true");
    const response = await apiUpload<UserImportResult>("/users/import", formData, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Preview failed",
    };
  }
}

/**
 * Execute a bulk user import (creates users).
 *
 * The credentials field in the response is one-time only.
 * It is NOT stored anywhere. If the admin misses the download,
 * they must use individual password reset per user.
 */
export async function importUsers(
  formData: FormData,
): Promise<ActionResult<UserImportResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiUpload<UserImportResult>("/users/import", formData, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Import failed",
    };
  }
}
