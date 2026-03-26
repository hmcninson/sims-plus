"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  Inquiry,
  InquiryCreate,
  InquiryUpdate,
  InquiryListResponse,
  InquiryStats,
  Communication,
  CommunicationCreate,
  FollowUp,
  FollowUpCreate,
  BulkImportRequest,
  BulkImportResponse,
  DuplicateCheckResponse,
  InquiryConvert,
} from "@/types/inquiry.type";

const BASE = "/admissions/inquiries";

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
// CRUD
// =========================

export async function createInquiry(
  data: InquiryCreate
): Promise<ActionResult<Inquiry>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Inquiry>(BASE, data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to create inquiry",
    };
  }
}

export async function getInquiries(params?: {
  page?: number;
  page_size?: number;
  status?: string;
  source?: string;
  search?: string;
  assigned_to?: string;
  sort_by?: string;
  sort_order?: string;
}): Promise<ActionResult<InquiryListResponse>> {
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
    const response = await apiGet<InquiryListResponse>(
      `${BASE}${qs ? `?${qs}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to fetch inquiries",
    };
  }
}

export async function getInquiry(
  id: string
): Promise<ActionResult<Inquiry>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<Inquiry>(`${BASE}/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to fetch inquiry",
    };
  }
}

export async function updateInquiry(
  id: string,
  data: InquiryUpdate
): Promise<ActionResult<Inquiry>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<Inquiry>(`${BASE}/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to update inquiry",
    };
  }
}

export async function deleteInquiry(
  id: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`${BASE}/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to delete inquiry",
    };
  }
}

// =========================
// Status & Assignment
// =========================

export async function updateInquiryStatus(
  id: string,
  status: string
): Promise<ActionResult<Inquiry>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<Inquiry>(`${BASE}/${id}/status`, { status }, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to update status",
    };
  }
}

export async function assignInquiry(
  id: string,
  userId: string
): Promise<ActionResult<Inquiry>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<Inquiry>(
      `${BASE}/${id}/assign`,
      { assigned_to: userId },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to assign inquiry",
    };
  }
}

export async function convertInquiry(
  id: string,
  data: InquiryConvert
): Promise<ActionResult<Inquiry>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Inquiry>(
      `${BASE}/${id}/convert`,
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
          : "Failed to convert inquiry to application",
    };
  }
}

// =========================
// Communications
// =========================

export async function addCommunication(
  inquiryId: string,
  data: CommunicationCreate
): Promise<ActionResult<Communication>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Communication>(
      `${BASE}/${inquiryId}/communications`,
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
          : "Failed to add communication",
    };
  }
}

export async function getCommunications(
  inquiryId: string
): Promise<ActionResult<Communication[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<Communication[]>(
      `${BASE}/${inquiryId}/communications`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch communications",
    };
  }
}

// =========================
// Follow-Ups
// =========================

export async function createFollowUp(
  inquiryId: string,
  data: FollowUpCreate
): Promise<ActionResult<FollowUp>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<FollowUp>(
      `${BASE}/${inquiryId}/follow-ups`,
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
          : "Failed to create follow-up",
    };
  }
}

export async function completeFollowUp(
  followUpId: string,
  notes?: string
): Promise<ActionResult<FollowUp>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<FollowUp>(
      `${BASE}/follow-ups/${followUpId}/complete`,
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
          : "Failed to complete follow-up",
    };
  }
}

export async function getPendingFollowUps(params?: {
  page?: number;
  page_size?: number;
  assigned_to?: string;
  overdue_only?: boolean;
}): Promise<ActionResult<FollowUp[]>> {
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
    const response = await apiGet<FollowUp[]>(
      `${BASE}/follow-ups/pending${qs ? `?${qs}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch pending follow-ups",
    };
  }
}

// =========================
// Bulk Import & Duplicate Check
// =========================

export async function bulkImportInquiries(
  data: BulkImportRequest
): Promise<ActionResult<BulkImportResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<BulkImportResponse>(
      `${BASE}/bulk-import`,
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
          : "Failed to import inquiries",
    };
  }
}

export async function checkDuplicate(params: {
  guardian_phone?: string;
  guardian_email?: string;
}): Promise<ActionResult<DuplicateCheckResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = new URLSearchParams();
    if (params.guardian_phone)
      query.set("guardian_phone", params.guardian_phone);
    if (params.guardian_email)
      query.set("guardian_email", params.guardian_email);
    const qs = query.toString();
    const response = await apiGet<DuplicateCheckResponse>(
      `${BASE}/duplicate-check${qs ? `?${qs}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to check for duplicates",
    };
  }
}

// =========================
// Stats
// =========================

export async function getInquiryStats(): Promise<ActionResult<InquiryStats>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<InquiryStats>(`${BASE}/stats`, {
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
          : "Failed to fetch inquiry stats",
    };
  }
}
