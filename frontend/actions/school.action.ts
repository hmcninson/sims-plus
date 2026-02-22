"use server";

/**
 * SIMS Plus - School Server Actions
 *
 * Server actions for school profile management.
 */

import { cookies } from "next/headers";
import { apiGet, apiPut, apiFetch, apiUpload } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  SchoolProfile,
  SchoolProfileUpdate,
  SchoolBrandingUpdate,
  FileUploadResponse,
  PreschoolSettings,
  PreschoolSettingsUpdate,
} from "@/types/school.type";

/**
 * Get auth token and subdomain from cookies with token refresh
 */
async function getAuthContext() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  const subdomain = cookieStore.get("x-subdomain")?.value;
  return { token: token || undefined, subdomain };
}

/**
 * Get current school profile
 */
export async function getSchoolProfile(): Promise<ActionResult<SchoolProfile>> {
  const { token, subdomain } = await getAuthContext();

  if (!token) {
    return { success: false, error: "Not authenticated" };
  }

  try {
    const response = await apiGet<SchoolProfile>("/schools/current", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch school profile",
    };
  }
}

/**
 * Update school profile
 */
export async function updateSchoolProfile(
  data: SchoolProfileUpdate
): Promise<ActionResult<SchoolProfile>> {
  const { token, subdomain } = await getAuthContext();

  if (!token) {
    return { success: false, error: "Not authenticated" };
  }

  try {
    const response = await apiPut<SchoolProfile>("/schools/current", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update school profile",
    };
  }
}

/**
 * Update school branding only
 */
export async function updateSchoolBranding(
  data: SchoolBrandingUpdate
): Promise<ActionResult<SchoolProfile>> {
  const { token, subdomain } = await getAuthContext();

  if (!token) {
    return { success: false, error: "Not authenticated" };
  }

  try {
    const response = await apiFetch<SchoolProfile>("/schools/current/branding", {
      method: "PATCH",
      body: JSON.stringify(data),
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update branding",
    };
  }
}

/**
 * Upload school logo to S3
 */
export async function uploadSchoolLogo(
  formData: FormData
): Promise<ActionResult<FileUploadResponse>> {
  const { token, subdomain } = await getAuthContext();

  if (!token) {
    return { success: false, error: "Not authenticated" };
  }

  try {
    const response = await apiUpload<FileUploadResponse>("/media/upload/logo", formData, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to upload logo",
    };
  }
}

/**
 * Get preschool settings
 */
export async function getPreschoolSettings(): Promise<ActionResult<PreschoolSettings>> {
  const { token, subdomain } = await getAuthContext();

  if (!token) {
    return { success: false, error: "Not authenticated" };
  }

  try {
    const response = await apiGet<PreschoolSettings>("/schools/current/preschool-settings", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch preschool settings",
    };
  }
}

/**
 * Update preschool settings
 */
export async function updatePreschoolSettings(
  data: PreschoolSettingsUpdate
): Promise<ActionResult<PreschoolSettings>> {
  const { token, subdomain } = await getAuthContext();

  if (!token) {
    return { success: false, error: "Not authenticated" };
  }

  try {
    const response = await apiFetch<PreschoolSettings>("/schools/current/preschool-settings", {
      method: "PATCH",
      body: JSON.stringify(data),
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update preschool settings",
    };
  }
}
