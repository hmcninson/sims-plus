"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  PaginatedResponse,
  StudentAttendance,
  StudentAttendanceListItem,
  StudentAttendanceMark,
  BulkStudentAttendanceMark,
  StudentAttendanceSummary,
  SectionAttendanceSummary,
  DailyAttendanceReport,
  BulkAttendanceResult,
  StaffAttendance,
  StaffAttendanceMark,
  BulkStaffAttendanceMark,
  StaffAttendanceSummary,
} from "@/types";

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
// Student Attendance Actions
// =========================

export async function markStudentAttendance(
  data: StudentAttendanceMark
): Promise<ActionResult<StudentAttendance>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StudentAttendance>("/attendance/students", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to mark attendance",
    };
  }
}

export async function bulkMarkStudentAttendance(
  data: BulkStudentAttendanceMark
): Promise<ActionResult<BulkAttendanceResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    console.log("[Attendance] Saving bulk attendance:", {
      section_id: data.section_id,
      date: data.date,
      records_count: data.records.length,
      has_token: !!token,
      subdomain,
    });
    const response = await apiPost<BulkAttendanceResult>(
      "/attendance/students/bulk",
      data,
      { token, subdomain }
    );
    console.log("[Attendance] Save successful:", response);
    return { success: true, data: response };
  } catch (error) {
    console.error("[Attendance] Save failed:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to mark attendance",
    };
  }
}

export async function getStudentsForAttendance(
  sectionId: string,
  date: string
): Promise<ActionResult<StudentAttendanceListItem[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StudentAttendanceListItem[]>(
      `/attendance/students/section/${sectionId}?attendance_date=${date}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch students for attendance",
    };
  }
}

export async function getSectionAttendanceSummary(
  sectionId: string,
  date: string
): Promise<ActionResult<SectionAttendanceSummary>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<SectionAttendanceSummary>(
      `/attendance/students/section/${sectionId}/summary?attendance_date=${date}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch section attendance summary",
    };
  }
}

export async function getStudentAttendanceSummary(
  studentId: string,
  options?: {
    term_id?: string;
    start_date?: string;
    end_date?: string;
  }
): Promise<ActionResult<StudentAttendanceSummary>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (options?.term_id) params.append("term_id", options.term_id);
    if (options?.start_date) params.append("start_date", options.start_date);
    if (options?.end_date) params.append("end_date", options.end_date);

    const url = `/attendance/students/${studentId}/summary${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<StudentAttendanceSummary>(url, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student attendance summary",
    };
  }
}

export interface StudentAttendanceFilters {
  student_id?: string;
  section_id?: string;
  term_id?: string;
  start_date?: string;
  end_date?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

export async function listStudentAttendance(
  filters: StudentAttendanceFilters = {}
): Promise<ActionResult<PaginatedResponse<StudentAttendance>>> {
  try {
    const { token, subdomain } = await getAuthContext();

    const params = new URLSearchParams();
    if (filters.student_id) params.append("student_id", filters.student_id);
    if (filters.section_id) params.append("section_id", filters.section_id);
    if (filters.term_id) params.append("term_id", filters.term_id);
    if (filters.start_date) params.append("start_date", filters.start_date);
    if (filters.end_date) params.append("end_date", filters.end_date);
    if (filters.status) params.append("status", filters.status);
    if (filters.page) params.append("page", String(filters.page));
    if (filters.page_size) params.append("page_size", String(filters.page_size));

    const url = `/attendance/students${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<PaginatedResponse<StudentAttendance>>(url, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student attendance",
    };
  }
}

export async function deleteStudentAttendance(
  attendanceId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/attendance/students/${attendanceId}`, {
      token,
      subdomain,
    });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete attendance record",
    };
  }
}

// =========================
// Daily Reports
// =========================

export async function getDailyAttendanceReport(
  date: string,
  school_id?: string
): Promise<ActionResult<DailyAttendanceReport>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    params.append("attendance_date", date);
    if (school_id) params.append("school_id", school_id);

    const response = await apiGet<DailyAttendanceReport>(
      `/attendance/reports/daily?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch daily attendance report",
    };
  }
}

// =========================
// Staff Attendance Actions
// =========================

export async function markStaffAttendance(
  data: StaffAttendanceMark
): Promise<ActionResult<StaffAttendance>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StaffAttendance>("/attendance/staff", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to mark staff attendance",
    };
  }
}

export async function bulkMarkStaffAttendance(
  data: BulkStaffAttendanceMark
): Promise<ActionResult<BulkAttendanceResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<BulkAttendanceResult>(
      "/attendance/staff/bulk",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to mark staff attendance",
    };
  }
}

export async function getStaffAttendanceSummary(
  staffId: string,
  options?: {
    term_id?: string;
    start_date?: string;
    end_date?: string;
  }
): Promise<ActionResult<StaffAttendanceSummary>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (options?.term_id) params.append("term_id", options.term_id);
    if (options?.start_date) params.append("start_date", options.start_date);
    if (options?.end_date) params.append("end_date", options.end_date);

    const url = `/attendance/staff/${staffId}/summary${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<StaffAttendanceSummary>(url, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch staff attendance summary",
    };
  }
}

export interface StaffAttendanceFilters {
  staff_id?: string;
  term_id?: string;
  start_date?: string;
  end_date?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

export async function listStaffAttendance(
  filters: StaffAttendanceFilters = {}
): Promise<ActionResult<PaginatedResponse<StaffAttendance>>> {
  try {
    const { token, subdomain } = await getAuthContext();

    const params = new URLSearchParams();
    if (filters.staff_id) params.append("staff_id", filters.staff_id);
    if (filters.term_id) params.append("term_id", filters.term_id);
    if (filters.start_date) params.append("start_date", filters.start_date);
    if (filters.end_date) params.append("end_date", filters.end_date);
    if (filters.status) params.append("status", filters.status);
    if (filters.page) params.append("page", String(filters.page));
    if (filters.page_size) params.append("page_size", String(filters.page_size));

    const url = `/attendance/staff${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<PaginatedResponse<StaffAttendance>>(url, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch staff attendance",
    };
  }
}

export async function deleteStaffAttendance(
  attendanceId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/attendance/staff/${attendanceId}`, {
      token,
      subdomain,
    });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete staff attendance record",
    };
  }
}
