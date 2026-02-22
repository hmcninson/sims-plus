"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  Announcement,
  AnnouncementCreate,
  AnnouncementUpdate,
  AnnouncementListResponse,
} from "@/types/parent.type";

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
// Announcement Actions
// =========================

export async function getAnnouncements(params?: {
  search?: string;
  priority?: string;
  target?: string;
  status?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<AnnouncementListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.append("search", params.search);
    if (params?.priority) searchParams.append("priority", params.priority);
    if (params?.target) searchParams.append("target_audience", params.target);
    if (params?.status) searchParams.append("status", params.status);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<AnnouncementListResponse>(
      `/announcements${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch announcements",
    };
  }
}

export async function getAnnouncement(id: string): Promise<ActionResult<Announcement>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<Announcement>(`/announcements/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch announcement",
    };
  }
}

export async function createAnnouncement(
  data: AnnouncementCreate
): Promise<ActionResult<Announcement>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Announcement>("/announcements", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create announcement",
    };
  }
}

export async function updateAnnouncement(
  id: string,
  data: AnnouncementUpdate
): Promise<ActionResult<Announcement>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<Announcement>(`/announcements/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update announcement",
    };
  }
}

export async function publishAnnouncement(
  id: string
): Promise<ActionResult<Announcement>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Announcement>(
      `/announcements/${id}/publish`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to publish announcement",
    };
  }
}

export async function deleteAnnouncement(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/announcements/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete announcement",
    };
  }
}
