"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  SMSSendRequest,
  SMSBulkRequest,
  SMSHistoryResponse,
  SMSStats,
  SMSLogEntry,
  EmailSendRequest,
  EmailBulkRequest,
  EmailHistoryResponse,
  EmailStats,
  EmailLogEntry,
  RecipientListResponse,
  RecipientType,
} from "@/types/messaging.type";

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
// SMS Actions
// =========================

export async function sendSMS(
  data: SMSSendRequest
): Promise<ActionResult<SMSLogEntry[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<SMSLogEntry[]>(
      "/messaging/sms/send",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to send SMS",
    };
  }
}

export async function sendBulkSMS(
  data: SMSBulkRequest
): Promise<ActionResult<SMSLogEntry[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<SMSLogEntry[]>(
      "/messaging/sms/bulk",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to send bulk SMS",
    };
  }
}

export async function getSMSHistory(
  page?: number,
  pageSize?: number,
  status?: string
): Promise<ActionResult<SMSHistoryResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (page) params.append("page", String(page));
    if (pageSize) params.append("page_size", String(pageSize));
    if (status) params.append("status", status);
    const query = params.toString() ? `?${params.toString()}` : "";
    const response = await apiGet<SMSHistoryResponse>(
      `/messaging/sms/history${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch SMS history",
    };
  }
}

export async function getSMSStats(): Promise<ActionResult<SMSStats>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<SMSStats>("/messaging/sms/stats", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch SMS stats",
    };
  }
}

// =========================
// Email Actions
// =========================

export async function sendEmail(
  data: EmailSendRequest
): Promise<ActionResult<EmailLogEntry[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<EmailLogEntry[]>(
      "/messaging/email/send",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to send email",
    };
  }
}

export async function sendBulkEmail(
  data: EmailBulkRequest
): Promise<ActionResult<EmailLogEntry[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<EmailLogEntry[]>(
      "/messaging/email/bulk",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to send bulk email",
    };
  }
}

export async function getEmailHistory(
  page?: number,
  pageSize?: number,
  status?: string
): Promise<ActionResult<EmailHistoryResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (page) params.append("page", String(page));
    if (pageSize) params.append("page_size", String(pageSize));
    if (status) params.append("status", status);
    const query = params.toString() ? `?${params.toString()}` : "";
    const response = await apiGet<EmailHistoryResponse>(
      `/messaging/email/history${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch email history",
    };
  }
}

export async function getEmailStats(): Promise<ActionResult<EmailStats>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<EmailStats>("/messaging/email/stats", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch email stats",
    };
  }
}

// =========================
// Recipient Actions (shared)
// =========================

export async function resolveRecipients(
  audience: RecipientType,
  classId?: string
): Promise<ActionResult<RecipientListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    params.append("audience", audience);
    if (classId) params.append("class_id", classId);
    const response = await apiGet<RecipientListResponse>(
      `/messaging/recipients/resolve?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to resolve recipients",
    };
  }
}
