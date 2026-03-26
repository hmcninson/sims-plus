"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  LeaveType,
  LeaveTypeCreate,
  LeaveTypeUpdate,
  LeaveBalance,
  LeaveBalanceAdjust,
  LeaveBalanceInitialize,
  LeaveRequest,
  LeaveRequestCreate,
  LeaveRequestUpdate,
  LeaveApproval,
  LeaveCalendarEntry,
} from "@/types/leave.type";

/**
 * Get auth context from cookies with token refresh
 */
async function getAuthContext() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  const subdomain = cookieStore.get("x-subdomain")?.value;
  return {
    token: token || undefined,
    subdomain,
  };
}

// =========================
// Leave Type Actions
// =========================

export async function getLeaveTypes(
  activeOnly: boolean = true
): Promise<ActionResult<LeaveType[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (!activeOnly) params.append("active_only", "false");
    const url = `/leave/types${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<LeaveType[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch leave types",
    };
  }
}

export async function createLeaveType(
  data: LeaveTypeCreate
): Promise<ActionResult<LeaveType>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<LeaveType>("/leave/types", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create leave type",
    };
  }
}

export async function updateLeaveType(
  id: string,
  data: LeaveTypeUpdate
): Promise<ActionResult<LeaveType>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<LeaveType>(`/leave/types/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update leave type",
    };
  }
}

export async function deleteLeaveType(
  id: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/leave/types/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete leave type",
    };
  }
}

// =========================
// Leave Balance Actions
// =========================

export interface LeaveBalanceFilters {
  academic_year_id?: string;
  leave_type_id?: string;
}

export async function getLeaveBalances(
  filters: LeaveBalanceFilters = {}
): Promise<ActionResult<LeaveBalance[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (filters.academic_year_id) params.append("academic_year_id", filters.academic_year_id);
    if (filters.leave_type_id) params.append("leave_type_id", filters.leave_type_id);
    const url = `/leave/balances${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<LeaveBalance[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch leave balances",
    };
  }
}

export async function getStaffLeaveBalances(
  staffId: string,
  academicYearId?: string
): Promise<ActionResult<LeaveBalance[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (academicYearId) params.append("academic_year_id", academicYearId);
    const url = `/leave/balances/${staffId}${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<LeaveBalance[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch staff leave balances",
    };
  }
}

export async function adjustLeaveBalance(
  balanceId: string,
  data: LeaveBalanceAdjust
): Promise<ActionResult<LeaveBalance>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<LeaveBalance>(`/leave/balances/${balanceId}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to adjust leave balance",
    };
  }
}

export async function initializeLeaveBalances(
  data: LeaveBalanceInitialize
): Promise<ActionResult<{ created: number; message: string }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<{ created: number; message: string }>(
      "/leave/balances/initialize",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to initialize leave balances",
    };
  }
}

// =========================
// Leave Request Actions
// =========================

export interface LeaveRequestFilters {
  status?: string;
  staff_id?: string;
  leave_type_id?: string;
  start_date?: string;
  end_date?: string;
}

export async function submitLeaveRequest(
  data: LeaveRequestCreate
): Promise<ActionResult<LeaveRequest>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<LeaveRequest>("/leave/requests", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to submit leave request",
    };
  }
}

export async function getLeaveRequests(
  filters: LeaveRequestFilters = {}
): Promise<ActionResult<LeaveRequest[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (filters.status) params.append("status", filters.status);
    if (filters.staff_id) params.append("staff_id", filters.staff_id);
    if (filters.leave_type_id) params.append("leave_type_id", filters.leave_type_id);
    if (filters.start_date) params.append("start_date", filters.start_date);
    if (filters.end_date) params.append("end_date", filters.end_date);
    const url = `/leave/requests${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<LeaveRequest[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch leave requests",
    };
  }
}

export async function getLeaveRequest(
  id: string
): Promise<ActionResult<LeaveRequest>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<LeaveRequest>(`/leave/requests/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch leave request",
    };
  }
}

export async function updateLeaveRequest(
  id: string,
  data: LeaveRequestUpdate
): Promise<ActionResult<LeaveRequest>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<LeaveRequest>(`/leave/requests/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update leave request",
    };
  }
}

export async function approveLeaveRequest(
  id: string,
  data: LeaveApproval = {}
): Promise<ActionResult<LeaveRequest>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<LeaveRequest>(
      `/leave/requests/${id}/approve`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to approve leave request",
    };
  }
}

export async function rejectLeaveRequest(
  id: string,
  data: LeaveApproval = {}
): Promise<ActionResult<LeaveRequest>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<LeaveRequest>(
      `/leave/requests/${id}/reject`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to reject leave request",
    };
  }
}

export async function cancelLeaveRequest(
  id: string
): Promise<ActionResult<LeaveRequest>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<LeaveRequest>(
      `/leave/requests/${id}/cancel`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to cancel leave request",
    };
  }
}

// =========================
// Leave Calendar Actions
// =========================

export async function getLeaveCalendar(
  startDate: string,
  endDate: string
): Promise<ActionResult<LeaveCalendarEntry[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
    });
    const response = await apiGet<LeaveCalendarEntry[]>(
      `/leave/calendar?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch leave calendar",
    };
  }
}
