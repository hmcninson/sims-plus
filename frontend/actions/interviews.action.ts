"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  Interview,
  InterviewCreate,
  InterviewUpdate,
  InterviewFeedback,
  InterviewListResponse,
  ScreeningItem,
  ScreeningItemCreate,
  ScreeningItemBulkCreate,
  ScreeningProgress,
} from "@/types/interview.type";

const BASE = "/admissions/interviews";
const SCREENING_BASE = "/admissions/screening";

// =========================
// Helpers
// =========================

async function getAuthContext(): Promise<{
  token: string;
  subdomain: string | undefined;
}> {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  return {
    token: token || "",
    subdomain: cookieStore.get("x-subdomain")?.value,
  };
}

// =========================
// Interviews
// =========================

export async function scheduleInterview(
  data: InterviewCreate
): Promise<ActionResult<Interview>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Interview>(BASE, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to schedule interview",
    };
  }
}

export async function getInterviews(params?: {
  page?: number;
  page_size?: number;
  status?: string;
  interviewer_id?: string;
  date_from?: string;
  date_to?: string;
}): Promise<ActionResult<InterviewListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") {
          query.set(k, String(v));
        }
      });
    }
    const qs = query.toString();
    const response = await apiGet<InterviewListResponse>(
      `${BASE}${qs ? `?${qs}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch interviews",
    };
  }
}

export async function getInterview(
  id: string
): Promise<ActionResult<Interview>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<Interview>(`${BASE}/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch interview",
    };
  }
}

export async function updateInterview(
  id: string,
  data: InterviewUpdate
): Promise<ActionResult<Interview>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<Interview>(`${BASE}/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to update interview",
    };
  }
}

export async function recordInterviewFeedback(
  id: string,
  data: InterviewFeedback
): Promise<ActionResult<Interview>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<Interview>(
      `${BASE}/${id}/feedback`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to record interview feedback",
    };
  }
}

export async function cancelInterview(
  id: string
): Promise<ActionResult<Interview>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<Interview>(
      `${BASE}/${id}/cancel`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to cancel interview",
    };
  }
}

// =========================
// Screening Checklist
// =========================

export async function addScreeningItem(
  applicationId: string,
  data: ScreeningItemCreate
): Promise<ActionResult<ScreeningItem>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ScreeningItem>(
      `${SCREENING_BASE}/${applicationId}/items`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to add screening item",
    };
  }
}

export async function bulkAddScreeningItems(
  applicationId: string,
  data: ScreeningItemBulkCreate
): Promise<ActionResult<ScreeningItem[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ScreeningItem[]>(
      `${SCREENING_BASE}/${applicationId}/items/bulk`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to add screening items",
    };
  }
}

export async function completeScreeningItem(
  itemId: string,
  notes?: string
): Promise<ActionResult<ScreeningItem>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<ScreeningItem>(
      `${SCREENING_BASE}/items/${itemId}/complete`,
      { notes },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to complete screening item",
    };
  }
}

export async function getScreeningProgress(
  applicationId: string
): Promise<ActionResult<ScreeningProgress>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ScreeningProgress>(
      `${SCREENING_BASE}/${applicationId}/progress`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch screening progress",
    };
  }
}
