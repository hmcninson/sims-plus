"use server";

/**
 * SIMS Plus - User Profile Server Actions
 *
 * Server actions for user profile management.
 */

import { cookies } from "next/headers";
import { apiPost, apiPut, apiUpload } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";

/**
 * User profile update request
 */
export interface ProfileUpdate {
  first_name?: string;
  last_name?: string;
  phone?: string;
  avatar_url?: string;
}

/**
 * User profile response
 */
export interface UserProfile {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  role: string;
  status: string;
  tenant_id: string;
  school_id?: string;
  avatar_url?: string;
  email_verified: boolean;
  mfa_enabled: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * File upload response
 */
export interface FileUploadResponse {
  url: string;
  key: string;
  filename: string;
  content_type: string;
  size: number;
}

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
 * Update current user's profile
 */
export async function updateProfile(
  data: ProfileUpdate
): Promise<ActionResult<UserProfile>> {
  const { token, subdomain } = await getAuthContext();

  if (!token) {
    return { success: false, error: "Not authenticated" };
  }

  try {
    const response = await apiPut<UserProfile>("/auth/profile", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update profile",
    };
  }
}

/**
 * Upload user avatar to S3
 */
export async function uploadAvatar(
  formData: FormData
): Promise<ActionResult<FileUploadResponse>> {
  const { token, subdomain } = await getAuthContext();

  if (!token) {
    return { success: false, error: "Not authenticated" };
  }

  try {
    const response = await apiUpload<FileUploadResponse>("/media/upload/avatar", formData, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to upload avatar",
    };
  }
}

/**
 * Upload avatar and immediately save to profile
 */
export async function uploadAndSaveAvatar(
  formData: FormData
): Promise<ActionResult<UserProfile>> {
  const { token, subdomain } = await getAuthContext();

  if (!token) {
    return { success: false, error: "Not authenticated" };
  }

  try {
    // Upload avatar to S3
    const uploadResult = await apiUpload<FileUploadResponse>("/media/upload/avatar", formData, {
      token,
      subdomain,
    });

    // Save avatar URL to profile
    const profileResult = await apiPut<UserProfile>("/auth/profile", {
      avatar_url: uploadResult.url,
    }, {
      token,
      subdomain,
    });

    return { success: true, data: profileResult };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to upload avatar",
    };
  }
}

/**
 * Change password request
 */
export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

/**
 * Change user's password
 */
export async function changePassword(
  data: ChangePasswordRequest
): Promise<ActionResult<void>> {
  const { token, subdomain } = await getAuthContext();

  if (!token) {
    return { success: false, error: "Not authenticated" };
  }

  try {
    await apiPost<void>("/auth/change-password", data, {
      token,
      subdomain,
    });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to change password",
    };
  }
}

/**
 * Logout from all sessions (invalidate all tokens)
 */
export async function logoutAllSessions(): Promise<ActionResult<void>> {
  const { token, subdomain } = await getAuthContext();

  if (!token) {
    return { success: false, error: "Not authenticated" };
  }

  try {
    await apiPost<void>("/auth/logout-all", {}, {
      token,
      subdomain,
    });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to logout from all sessions",
    };
  }
}
