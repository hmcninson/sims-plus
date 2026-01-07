"use server";

import { cookies } from "next/headers";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";

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

export interface FileUploadResponse {
  url: string;
  key: string;
  filename: string;
  content_type: string;
  size: number;
}

/**
 * Upload student photo
 */
export async function uploadStudentPhoto(
  studentId: string,
  formData: FormData
): Promise<ActionResult<FileUploadResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();

    if (!token || !subdomain) {
      return { success: false, error: "Not authenticated" };
    }

    const response = await fetch(
      `${process.env.API_URL || "http://localhost:8000/api/v1"}/media/upload/student-photo/${studentId}`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Subdomain": subdomain,
        },
        body: formData,
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Upload failed");
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to upload photo",
    };
  }
}

/**
 * Upload school logo
 */
export async function uploadSchoolLogo(
  formData: FormData
): Promise<ActionResult<FileUploadResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();

    if (!token || !subdomain) {
      return { success: false, error: "Not authenticated" };
    }

    const response = await fetch(
      `${process.env.API_URL || "http://localhost:8000/api/v1"}/media/upload/logo`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Subdomain": subdomain,
        },
        body: formData,
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Upload failed");
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to upload logo",
    };
  }
}

/**
 * Upload user avatar
 */
export async function uploadUserAvatar(
  formData: FormData
): Promise<ActionResult<FileUploadResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();

    if (!token || !subdomain) {
      return { success: false, error: "Not authenticated" };
    }

    const response = await fetch(
      `${process.env.API_URL || "http://localhost:8000/api/v1"}/media/upload/avatar`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Subdomain": subdomain,
        },
        body: formData,
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Upload failed");
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to upload avatar",
    };
  }
}
