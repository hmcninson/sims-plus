"use server";

import { cookies } from "next/headers";
import { apiGet, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  NotificationListResponse,
  UnreadCountResponse,
} from "@/types";

async function getAuthContext() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  return {
    token: token || undefined,
    subdomain: cookieStore.get("x-subdomain")?.value,
  };
}

export interface NotificationFilters {
  is_read?: boolean;
  category?: string;
  page?: number;
  page_size?: number;
}

export async function getNotifications(
  filters: NotificationFilters = {}
): Promise<ActionResult<NotificationListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (filters.is_read !== undefined) params.append("is_read", String(filters.is_read));
    if (filters.category) params.append("category", filters.category);
    if (filters.page) params.append("page", String(filters.page));
    if (filters.page_size) params.append("page_size", String(filters.page_size));

    const url = `/notifications${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<NotificationListResponse>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch notifications",
    };
  }
}

export async function getUnreadCount(): Promise<ActionResult<UnreadCountResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<UnreadCountResponse>("/notifications/unread-count", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch unread count",
    };
  }
}

export async function markAsRead(
  notificationId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiPut(`/notifications/${notificationId}/read`, {}, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to mark notification as read",
    };
  }
}

export async function markAllAsRead(): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiPut("/notifications/mark-all-read", {}, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to mark all as read",
    };
  }
}

export async function deleteNotification(
  notificationId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/notifications/${notificationId}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete notification",
    };
  }
}
