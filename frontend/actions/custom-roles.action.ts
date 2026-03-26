"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  CustomRole,
  CustomRoleCreate,
  CustomRoleUpdate,
  CustomRoleListResponse,
  PermissionsCatalog,
} from "@/types/custom-role.type";

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
// Custom Role CRUD Actions
// =========================

/**
 * List all custom roles for the current tenant, including user counts.
 */
export async function listCustomRoles(): Promise<ActionResult<CustomRoleListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<CustomRoleListResponse>("/custom-roles", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to load custom roles",
    };
  }
}

/**
 * Create a new custom role.
 */
export async function createCustomRole(
  data: CustomRoleCreate
): Promise<ActionResult<CustomRole>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<CustomRole>("/custom-roles", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create custom role",
    };
  }
}

/**
 * Update an existing custom role. Cannot change base_role.
 */
export async function updateCustomRole(
  id: string,
  data: CustomRoleUpdate
): Promise<ActionResult<CustomRole>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<CustomRole>(`/custom-roles/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update custom role",
    };
  }
}

/**
 * Delete a custom role. Fails if users are still assigned.
 */
export async function deleteCustomRole(
  id: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/custom-roles/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete custom role",
    };
  }
}

// =========================
// Permissions Catalog
// =========================

/**
 * Get the permissions catalog, optionally filtered by base role.
 * When baseRole is specified, only permissions within that role's ceiling are returned.
 */
export async function getPermissionsCatalog(
  baseRole?: string
): Promise<ActionResult<PermissionsCatalog>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const url = baseRole
      ? `/custom-roles/permissions/catalog?base_role=${encodeURIComponent(baseRole)}`
      : "/custom-roles/permissions/catalog";
    const response = await apiGet<PermissionsCatalog>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to load permissions catalog",
    };
  }
}

// =========================
// User Custom Role Assignment
// =========================

/**
 * Assign a custom role to a user (or remove by passing null).
 */
export async function assignCustomRole(
  userId: string,
  customRoleId: string | null
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiPut(`/users/${userId}/custom-role`, { custom_role_id: customRoleId }, {
      token,
      subdomain,
    });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to assign custom role",
    };
  }
}
