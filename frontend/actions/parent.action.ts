"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPatch } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  ChildSummary,
  ChildOverview,
  TermGrades,
  GradeTrend,
  AttendanceSummary,
  AttendanceTrend,
  ParentInvoiceSummary,
  ParentInvoiceDetail,
  FeeStatement,
  ParentPaymentRecord,
  Announcement,
  TeacherNote,
  NotificationPreferences,
  NotificationPreferencesUpdate,
  PaymentInitiateRequest,
  PaymentInitiateResponse,
  PaymentVerifyResponse,
  ParentDashboardData,
  ChildBoardingInfo,
  ChildTransportInfo,
  ParentOnboardingStatus,
  ParentProfileCompletion,
} from "@/types/parent.type";

// =========================
// Auth Context Helper
// =========================

/**
 * Get auth context from cookies with token refresh.
 * Reuses the established pattern from boarding/transport actions.
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
// Dashboard
// =========================

/**
 * Get parent dashboard data (children list, overview for first child,
 * recent announcements, and upcoming events).
 */
export async function getParentDashboard(): Promise<ActionResult<ParentDashboardData>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ParentDashboardData>("/parent/dashboard", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch dashboard data",
    };
  }
}

// =========================
// Children
// =========================

/**
 * Get all children linked to the current parent.
 */
export async function getMyChildren(): Promise<ActionResult<ChildSummary[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ChildSummary[]>("/parent/children", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch children",
    };
  }
}

/**
 * Get detailed overview for a specific child, including quick stats
 * and recent activity.
 */
export async function getChildOverview(
  studentId: string
): Promise<ActionResult<ChildOverview>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ChildOverview>(
      `/parent/children/${studentId}/overview`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch child overview",
    };
  }
}

// =========================
// Grades
// =========================

/**
 * Get term grades for a specific child.
 */
export async function getChildGrades(
  studentId: string,
  termId: string
): Promise<ActionResult<TermGrades>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TermGrades>(
      `/parent/children/${studentId}/grades?term_id=${termId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch grades",
    };
  }
}

/**
 * Get grade trend across terms for a child.
 */
export async function getChildGradeTrend(
  studentId: string
): Promise<ActionResult<GradeTrend[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<GradeTrend[]>(
      `/parent/children/${studentId}/grades/trend`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch grade trend",
    };
  }
}

/**
 * Download report card PDF for a specific child and term.
 * Returns the download URL from the backend.
 */
export async function downloadReportCard(
  studentId: string,
  termId: string
): Promise<ActionResult<{ url: string }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<{ url: string }>(
      `/parent/children/${studentId}/report-card/${termId}/download`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to download report card",
    };
  }
}

// =========================
// Finance
// =========================

/**
 * Get all invoices for a specific child.
 */
export async function getChildInvoices(
  studentId: string
): Promise<ActionResult<ParentInvoiceSummary[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ParentInvoiceSummary[]>(
      `/parent/children/${studentId}/invoices`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch invoices",
    };
  }
}

/**
 * Get detailed invoice with line items and payment history.
 */
export async function getChildInvoiceDetail(
  studentId: string,
  invoiceId: string
): Promise<ActionResult<ParentInvoiceDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ParentInvoiceDetail>(
      `/parent/children/${studentId}/invoices/${invoiceId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch invoice details",
    };
  }
}

/**
 * Get fee statement for a child, optionally filtered by term.
 */
export async function getChildFeeStatement(
  studentId: string,
  termId?: string
): Promise<ActionResult<FeeStatement>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (termId) params.set("term_id", termId);
    const query = params.toString();
    const response = await apiGet<FeeStatement>(
      `/parent/children/${studentId}/fee-statement${query ? `?${query}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch fee statement",
    };
  }
}

/**
 * Get payment history for a specific child.
 */
export async function getChildPaymentHistory(
  studentId: string
): Promise<ActionResult<ParentPaymentRecord[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ParentPaymentRecord[]>(
      `/parent/children/${studentId}/payments`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch payment history",
    };
  }
}

/**
 * Initiate an online payment (Mobile Money or card).
 * Returns an authorization URL to redirect the parent to.
 */
export async function initiatePayment(
  studentId: string,
  data: PaymentInitiateRequest
): Promise<ActionResult<PaymentInitiateResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PaymentInitiateResponse>(
      `/parent/children/${studentId}/payments/initiate`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to initiate payment",
    };
  }
}

/**
 * Verify payment status after callback from payment provider.
 */
export async function verifyPayment(
  reference: string
): Promise<ActionResult<PaymentVerifyResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<PaymentVerifyResponse>(
      `/parent/payments/verify/${reference}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to verify payment",
    };
  }
}

// =========================
// Attendance
// =========================

/**
 * Get attendance summary for a child in a given month (YYYY-MM format).
 */
export async function getChildAttendance(
  studentId: string,
  month: string
): Promise<ActionResult<AttendanceSummary>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<AttendanceSummary>(
      `/parent/children/${studentId}/attendance?month=${month}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch attendance",
    };
  }
}

/**
 * Get monthly attendance trend for a child (rates over recent months).
 */
export async function getChildAttendanceTrend(
  studentId: string
): Promise<ActionResult<AttendanceTrend[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<AttendanceTrend[]>(
      `/parent/children/${studentId}/attendance/trend`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch attendance trend",
    };
  }
}

// =========================
// Communication
// =========================

/**
 * Get school announcements visible to the parent.
 */
export async function getAnnouncements(): Promise<ActionResult<Announcement[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<Announcement[]>("/parent/announcements", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch announcements",
    };
  }
}

/**
 * Get teacher notes for a specific child (visible to parent).
 */
export async function getChildTeacherNotes(
  studentId: string
): Promise<ActionResult<TeacherNote[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TeacherNote[]>(
      `/parent/children/${studentId}/notes`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch teacher notes",
    };
  }
}

/**
 * Acknowledge a teacher note (mark as read by parent).
 */
export async function acknowledgeTeacherNote(
  studentId: string,
  noteId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiPost<void>(
      `/parent/children/${studentId}/notes/${noteId}/acknowledge`,
      {},
      { token, subdomain }
    );
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to acknowledge note",
    };
  }
}

// =========================
// Notification Preferences
// =========================

/**
 * Get the parent's notification preferences.
 */
export async function getNotificationPreferences(): Promise<
  ActionResult<NotificationPreferences>
> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<NotificationPreferences>(
      "/parent/notification-preferences",
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch notification preferences",
    };
  }
}

/**
 * Update the parent's notification preferences.
 */
export async function updateNotificationPreferences(
  data: NotificationPreferencesUpdate
): Promise<ActionResult<NotificationPreferences>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<NotificationPreferences>(
      "/parent/notification-preferences",
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
          : "Failed to update notification preferences",
    };
  }
}

// =========================
// Boarding & Transport
// =========================

/**
 * Get boarding information for a specific child (house, dormitory, roll calls, exeats).
 */
export async function getChildBoardingInfo(
  studentId: string
): Promise<ActionResult<ChildBoardingInfo>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ChildBoardingInfo>(
      `/parent/children/${studentId}/boarding`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch boarding info",
    };
  }
}

/**
 * Get transport information for a specific child (route, stops, driver).
 */
export async function getChildTransportInfo(
  studentId: string
): Promise<ActionResult<ChildTransportInfo>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ChildTransportInfo>(
      `/parent/children/${studentId}/transport`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch transport info",
    };
  }
}

// =========================
// Onboarding
// =========================

/**
 * Get the parent's onboarding status (profile completion, password set, etc.).
 */
export async function getParentOnboardingStatus(): Promise<
  ActionResult<ParentOnboardingStatus>
> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ParentOnboardingStatus>(
      "/parent/onboarding/status",
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch onboarding status",
    };
  }
}

/**
 * Complete the parent's profile during onboarding.
 */
export async function completeParentProfile(
  data: ParentProfileCompletion
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiPost<void>("/parent/onboarding/complete", data, {
      token,
      subdomain,
    });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to complete profile",
    };
  }
}
