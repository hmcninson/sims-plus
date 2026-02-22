"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  TimetableEntry,
  TimetableEntryCreate,
  TimetableEntryUpdate,
  TimetableBulkCreate,
  TimetableWeek,
  SchoolPeriod,
  SchoolPeriodCreate,
  SchoolPeriodUpdate,
  SchoolPeriodBulkCreate,
  SchoolHoliday,
  SchoolHolidayCreate,
  SchoolHolidayUpdate,
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
// Timetable Actions
// =========================

/**
 * Get timetable for a class/section
 * @param classId - The class ID
 * @param academicYearId - The academic year ID
 * @param sectionId - Optional section ID to filter by
 * @param termId - Optional term ID. If set, returns timetable for that term only.
 *                 If not set, returns the year-wide timetable (term_id is NULL).
 */
export async function getClassTimetable(
  classId: string,
  academicYearId: string,
  sectionId?: string,
  termId?: string
): Promise<ActionResult<TimetableWeek>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({
      academic_year_id: academicYearId,
    });
    if (sectionId) {
      params.append("section_id", sectionId);
    }
    if (termId) {
      params.append("term_id", termId);
    }
    const response = await apiGet<TimetableWeek>(
      `/timetable/class/${classId}?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch timetable",
    };
  }
}

/**
 * Get timetable for a teacher
 * @param teacherId - The teacher (staff) ID
 * @param academicYearId - The academic year ID
 * @param termId - Optional term ID. If set, returns timetable for that term only.
 *                 If not set, returns all timetable entries for the academic year.
 */
export async function getTeacherTimetable(
  teacherId: string,
  academicYearId: string,
  termId?: string
): Promise<ActionResult<TimetableEntry[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({
      academic_year_id: academicYearId,
    });
    if (termId) {
      params.append("term_id", termId);
    }
    const response = await apiGet<TimetableEntry[]>(
      `/timetable/teacher/${teacherId}?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch teacher timetable",
    };
  }
}

/**
 * Get a single timetable entry
 */
export async function getTimetableEntry(
  entryId: string
): Promise<ActionResult<TimetableEntry>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TimetableEntry>(
      `/timetable/${entryId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch timetable entry",
    };
  }
}

/**
 * Create a new timetable entry
 */
export async function createTimetableEntry(
  data: TimetableEntryCreate
): Promise<ActionResult<TimetableEntry>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<TimetableEntry>(
      "/timetable",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create timetable entry",
    };
  }
}

/**
 * Update a timetable entry
 */
export async function updateTimetableEntry(
  entryId: string,
  data: TimetableEntryUpdate
): Promise<ActionResult<TimetableEntry>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<TimetableEntry>(
      `/timetable/${entryId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update timetable entry",
    };
  }
}

/**
 * Delete a timetable entry
 */
export async function deleteTimetableEntry(
  entryId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/timetable/${entryId}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete timetable entry",
    };
  }
}

/**
 * Bulk create/update timetable for a class/section
 * This replaces the entire timetable for the specified class/section/term.
 *
 * @param data - The timetable data including:
 *   - class_id: The class ID
 *   - section_id: Optional section ID
 *   - academic_year_id: The academic year ID
 *   - term_id: Optional term ID. If set, only replaces timetable for that term.
 *              If not set, replaces year-wide timetable entries (term_id is NULL).
 *   - entries: Array of timetable entries
 */
export async function bulkUpdateTimetable(
  data: TimetableBulkCreate
): Promise<ActionResult<TimetableEntry[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<TimetableEntry[]>(
      "/timetable/bulk",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update timetable",
    };
  }
}

// =========================
// School Period Actions
// =========================

/**
 * Get school periods with hierarchy support
 *
 * Returns periods in order of specificity:
 * 1. Section-specific periods (if sectionId provided and found)
 * 2. Class-specific periods (if classId provided and found)
 * 3. School-wide periods (default)
 */
export async function getSchoolPeriods(
  classId?: string,
  sectionId?: string,
  activeOnly: boolean = true
): Promise<ActionResult<SchoolPeriod[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({ active_only: String(activeOnly) });
    if (classId) params.append("class_id", classId);
    if (sectionId) params.append("section_id", sectionId);

    const response = await apiGet<SchoolPeriod[]>(
      `/timetable/periods?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch school periods",
    };
  }
}

/**
 * Create a new school period
 */
export async function createSchoolPeriod(
  data: SchoolPeriodCreate
): Promise<ActionResult<SchoolPeriod>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<SchoolPeriod>(
      "/timetable/periods",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create school period",
    };
  }
}

/**
 * Update a school period
 */
export async function updateSchoolPeriod(
  periodId: string,
  data: SchoolPeriodUpdate
): Promise<ActionResult<SchoolPeriod>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<SchoolPeriod>(
      `/timetable/periods/${periodId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update school period",
    };
  }
}

/**
 * Delete a school period
 */
export async function deleteSchoolPeriod(
  periodId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/timetable/periods/${periodId}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete school period",
    };
  }
}

/**
 * Bulk create school periods at a specific level (replaces existing periods at that level)
 *
 * - class_id=null, section_id=null: Replaces school-wide periods
 * - class_id set, section_id=null: Replaces class-specific periods
 * - class_id set, section_id set: Replaces section-specific periods
 */
export async function bulkCreateSchoolPeriods(
  data: SchoolPeriodBulkCreate
): Promise<ActionResult<SchoolPeriod[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<SchoolPeriod[]>(
      "/timetable/periods/bulk",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create school periods",
    };
  }
}

// =========================
// School Holiday Actions
// =========================

/**
 * Get all school holidays for the current tenant
 */
export async function getSchoolHolidays(
  academicYearId?: string
): Promise<ActionResult<SchoolHoliday[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = academicYearId ? `?academic_year_id=${academicYearId}` : "";
    const response = await apiGet<SchoolHoliday[]>(
      `/timetable/holidays${params}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch school holidays",
    };
  }
}

/**
 * Create a new school holiday
 */
export async function createSchoolHoliday(
  data: SchoolHolidayCreate
): Promise<ActionResult<SchoolHoliday>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<SchoolHoliday>(
      "/timetable/holidays",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create school holiday",
    };
  }
}

/**
 * Update a school holiday
 */
export async function updateSchoolHoliday(
  holidayId: string,
  data: SchoolHolidayUpdate
): Promise<ActionResult<SchoolHoliday>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<SchoolHoliday>(
      `/timetable/holidays/${holidayId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update school holiday",
    };
  }
}

/**
 * Delete a school holiday
 */
export async function deleteSchoolHoliday(
  holidayId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/timetable/holidays/${holidayId}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete school holiday",
    };
  }
}
