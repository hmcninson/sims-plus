"use server";

import { cookies } from "next/headers";
import { apiGet } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult, AuditLogListResponse } from "@/types";

async function getAuthContext() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  return {
    token: token || undefined,
    subdomain: cookieStore.get("x-subdomain")?.value,
  };
}

export interface AuditLogFilters {
  event_type?: string;
  user_id?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export async function getAuditLogs(
  filters: AuditLogFilters = {}
): Promise<ActionResult<AuditLogListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (filters.event_type) params.append("event_type", filters.event_type);
    if (filters.user_id) params.append("user_id", filters.user_id);
    if (filters.date_from) params.append("date_from", filters.date_from);
    if (filters.date_to) params.append("date_to", filters.date_to);
    if (filters.page) params.append("page", String(filters.page));
    if (filters.page_size) params.append("page_size", String(filters.page_size));

    const url = `/audit-logs${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<AuditLogListResponse>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch audit logs",
    };
  }
}
