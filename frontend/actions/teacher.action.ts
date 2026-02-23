"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  TeacherDashboardData,
  TeacherProfile,
  TeacherProfileUpdate,
  TeacherWeeklySchedule,
  TeacherScheduleEntry,
  TeacherClassSummary,
  TeacherClassDetail,
  TeacherClassStudentListResponse,
  TeacherStudentDetail,
  TeacherClassAttendanceSummary,
  TeacherAttendanceSection,
  TeacherBulkAttendanceSubmit,
  TeacherBulkAttendanceResult,
  TeacherPendingScoreEntry,
  TeacherBulkScoreEntryResponse,
  TeacherClassGradeSummary,
  TeacherScoreSheet,
  TeacherScoreSave,
  TeacherScoreSaveResult,
  TeacherNoteItem,
  TeacherNoteCreate,
  TeacherNoteListResponse,
  TeacherReportComment,
  TeacherReportCommentListResponse,
  TeacherLessonPlan,
  TeacherLessonPlanListResponse,
  TeacherLessonPlanCreate,
  TeacherLessonPlanUpdate,
  TeacherClassBroadcastRequest,
  TeacherClassBroadcastResponse,
  TeacherPerformanceSummary,
  HeadTeacherOverview,
  HeadTeacherPerformanceData,
  TeacherNotificationList,
  TeacherGradingSubject,
} from "@/types/teacher.type";

// =========================
// Auth Context Helper
// =========================

/**
 * Get auth context from cookies with token refresh.
 * Reuses the established pattern from parent/boarding actions.
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
 * Get teacher dashboard data.
 * Backend: GET /teacher/dashboard -> TeacherDashboard
 */
export async function getTeacherDashboard(): Promise<ActionResult<TeacherDashboardData>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TeacherDashboardData>("/teacher/dashboard", {
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
// Profile
// =========================

/**
 * Get current teacher's profile.
 *
 * NOTE: The backend has no dedicated /teacher/profile endpoint. This action
 * currently calls a nonexistent endpoint and will 404. The profile page should
 * be refactored to use the dashboard endpoint or the session user context.
 * Kept as a stub for the profile page to compile.
 */
export async function getTeacherProfile(): Promise<ActionResult<TeacherProfile>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // TODO: Replace with actual endpoint when backend adds /teacher/profile
    const response = await apiGet<TeacherProfile>("/teacher/profile", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch profile",
    };
  }
}

/**
 * Update teacher's own profile (phone, photo).
 *
 * NOTE: Same caveat as getTeacherProfile -- no backend endpoint exists yet.
 */
export async function updateTeacherProfile(
  data: TeacherProfileUpdate
): Promise<ActionResult<TeacherProfile>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<TeacherProfile>(
      "/teacher/profile",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update profile",
    };
  }
}

// =========================
// Schedule
// =========================

/**
 * Get today's schedule entries for the teacher.
 * Backend: GET /teacher/schedule/today -> list[ScheduleEntry]
 */
export async function getTeacherTodaySchedule(): Promise<ActionResult<TeacherScheduleEntry[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TeacherScheduleEntry[]>("/teacher/schedule/today", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch today's schedule",
    };
  }
}

/**
 * Get the teacher's full weekly timetable.
 * Backend: GET /teacher/schedule/week -> WeekSchedule { days }
 */
export async function getTeacherSchedule(): Promise<ActionResult<TeacherWeeklySchedule>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TeacherWeeklySchedule>("/teacher/schedule/week", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch schedule",
    };
  }
}

// =========================
// Classes
// =========================

/**
 * Get list of classes assigned to the teacher.
 * Backend: GET /teacher/classes -> list[TeacherClassSummary]
 */
export async function getTeacherClasses(): Promise<ActionResult<TeacherClassSummary[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TeacherClassSummary[]>("/teacher/classes", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch classes",
    };
  }
}

/**
 * Get overview of a specific class the teacher teaches.
 * Backend: GET /teacher/classes/{classId}?section_id=... -> ClassOverview
 */
export async function getTeacherClassDetail(
  classId: string,
  sectionId?: string
): Promise<ActionResult<TeacherClassDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = sectionId ? `?section_id=${sectionId}` : "";
    const response = await apiGet<TeacherClassDetail>(
      `/teacher/classes/${classId}${params}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch class details",
    };
  }
}

/**
 * Get the list of students in a class.
 * Backend: GET /teacher/classes/{classId}/students?section_id=... -> ClassStudentListResponse
 */
export async function getTeacherClassStudents(
  classId: string,
  sectionId?: string
): Promise<ActionResult<TeacherClassStudentListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = sectionId ? `?section_id=${sectionId}` : "";
    const response = await apiGet<TeacherClassStudentListResponse>(
      `/teacher/classes/${classId}/students${params}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch class students",
    };
  }
}

/**
 * Get detail for a specific student within the teacher's class.
 *
 * NOTE: The backend has no dedicated student detail endpoint. This action
 * currently calls a nonexistent route. The student detail page should compose
 * data from the class students list and notes endpoints.
 * Kept as a stub for the student detail page to compile.
 */
export async function getTeacherStudentDetail(
  classId: string,
  studentId: string
): Promise<ActionResult<TeacherStudentDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // TODO: Replace with actual endpoint or compose from multiple endpoints
    const response = await apiGet<TeacherStudentDetail>(
      `/teacher/classes/${classId}/students/${studentId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student details",
    };
  }
}

// =========================
// Attendance
// =========================

/**
 * Get attendance summary for a class.
 * Backend: GET /teacher/attendance/classes/{classId}/summary?section_id=...&date_from=...&date_to=...
 *   -> ClassAttendanceSummary
 */
export async function getTeacherClassAttendanceSummary(
  classId: string,
  options?: { sectionId?: string; dateFrom?: string; dateTo?: string }
): Promise<ActionResult<TeacherClassAttendanceSummary>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (options?.sectionId) params.set("section_id", options.sectionId);
    if (options?.dateFrom) params.set("date_from", options.dateFrom);
    if (options?.dateTo) params.set("date_to", options.dateTo);
    const qs = params.toString() ? `?${params.toString()}` : "";
    const response = await apiGet<TeacherClassAttendanceSummary>(
      `/teacher/attendance/classes/${classId}/summary${qs}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch attendance summary",
    };
  }
}

/**
 * Get attendance data for a section on a specific date.
 *
 * NOTE: The backend has no teacher-specific attendance marking endpoint.
 * Attendance marking is handled by the existing /attendance module.
 * This action is kept as a stub for the attendance page to compile.
 * It should be replaced with calls to the /attendance endpoints.
 */
export async function getTeacherAttendance(
  sectionId: string,
  date: string
): Promise<ActionResult<TeacherAttendanceSection>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // TODO: Replace with actual /attendance endpoint
    const response = await apiGet<TeacherAttendanceSection>(
      `/teacher/attendance?section_id=${sectionId}&date=${date}`,
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
 * Submit bulk attendance records for a section.
 *
 * NOTE: Same caveat as getTeacherAttendance -- should use /attendance endpoints.
 */
export async function submitTeacherAttendance(
  data: TeacherBulkAttendanceSubmit
): Promise<ActionResult<TeacherBulkAttendanceResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // TODO: Replace with actual /attendance endpoint
    const response = await apiPost<TeacherBulkAttendanceResult>(
      "/teacher/attendance",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to submit attendance",
    };
  }
}

// =========================
// Grading
// =========================

/**
 * Get list of exam subjects with pending score entry.
 * Backend: GET /teacher/grading/pending -> list[PendingScoreEntry]
 */
export async function getTeacherGradingSubjects(): Promise<ActionResult<TeacherPendingScoreEntry[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TeacherPendingScoreEntry[]>("/teacher/grading/pending", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch grading subjects",
    };
  }
}

/**
 * Enter scores for an exam subject.
 * Backend: POST /teacher/grading/exam-subjects/{examSubjectId}/scores
 *   -> BulkScoreEntryResponse
 */
export async function saveTeacherScores(
  examSubjectId: string,
  scores: { student_id: string; score: number | null; is_absent: boolean; teacher_remark?: string }[]
): Promise<ActionResult<TeacherBulkScoreEntryResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<TeacherBulkScoreEntryResponse>(
      `/teacher/grading/exam-subjects/${examSubjectId}/scores`,
      { scores },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to save scores",
    };
  }
}

/**
 * Get grade summary for a class-subject combination.
 * Backend: GET /teacher/grading/classes/{classId}/subjects/{subjectId}/summary?term_id=...
 *   -> ClassGradeSummary
 */
export async function getTeacherClassGradeSummary(
  classId: string,
  subjectId: string,
  termId?: string
): Promise<ActionResult<TeacherClassGradeSummary>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = termId ? `?term_id=${termId}` : "";
    const response = await apiGet<TeacherClassGradeSummary>(
      `/teacher/grading/classes/${classId}/subjects/${subjectId}/summary${params}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch grade summary",
    };
  }
}

/**
 * Get the score sheet for a specific class and subject.
 *
 * NOTE: The backend has no dedicated "score sheet" endpoint that returns a
 * pre-populated student list with existing scores. This action calls a
 * nonexistent route. The score entry page should be refactored to use
 * getTeacherClassStudents + existing scores from the grading summary.
 * Kept as a stub for the score entry page to compile.
 */
export async function getTeacherScoreSheet(
  classId: string,
  subjectId: string
): Promise<ActionResult<TeacherScoreSheet>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // TODO: Replace with composition of class students + grade summary endpoints
    const response = await apiGet<TeacherScoreSheet>(
      `/teacher/grading/classes/${classId}/subjects/${subjectId}/scores`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch score sheet",
    };
  }
}

// =========================
// Notes
// =========================

/**
 * Get notes created by the current teacher.
 * Backend: GET /teacher/notes?student_id=...&note_type=...&limit=...&offset=...
 *   -> TeacherNoteListResponse { notes, total }
 *
 * Backend uses limit/offset pagination (not page/page_size).
 */
export async function getTeacherNotes(
  page: number = 1,
  studentId?: string
): Promise<ActionResult<TeacherNoteListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const limit = 20;
    const offset = (page - 1) * limit;
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    if (studentId) params.set("student_id", studentId);
    const response = await apiGet<TeacherNoteListResponse>(
      `/teacher/notes?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch notes",
    };
  }
}

/**
 * Create a new student note.
 * Backend: POST /teacher/notes -> TeacherNoteResponse (status 201)
 */
export async function createTeacherNote(
  data: TeacherNoteCreate
): Promise<ActionResult<TeacherNoteItem>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<TeacherNoteItem>(
      "/teacher/notes",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create note",
    };
  }
}

// =========================
// Reports (Comments)
// =========================

/**
 * Get report comments for a term.
 * Backend: GET /teacher/reports/comments?term_id=...&section_id=...
 *   -> ReportCommentListResponse { comments, total }
 */
export async function getTeacherReportComments(
  termId?: string,
  sectionId?: string
): Promise<ActionResult<TeacherReportCommentListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (termId) params.set("term_id", termId);
    if (sectionId) params.set("section_id", sectionId);
    const qs = params.toString() ? `?${params.toString()}` : "";
    const response = await apiGet<TeacherReportCommentListResponse>(
      `/teacher/reports/comments${qs}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch report comments",
    };
  }
}

/**
 * Write or update a class teacher comment for a student.
 * Backend: POST /teacher/reports/comments/students/{studentId}?term_id=...
 *   -> ReportCommentResponse
 */
export async function writeClassTeacherComment(
  studentId: string,
  comment: string,
  termId?: string
): Promise<ActionResult<TeacherReportComment>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = termId ? `?term_id=${termId}` : "";
    const response = await apiPost<TeacherReportComment>(
      `/teacher/reports/comments/students/${studentId}${params}`,
      { class_teacher_comment: comment },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to save comment",
    };
  }
}

/**
 * Sign a class teacher comment.
 * Backend: POST /teacher/reports/comments/students/{studentId}/sign?term_id=...
 *   -> ReportCommentResponse
 */
export async function signClassTeacherComment(
  studentId: string,
  termId?: string
): Promise<ActionResult<TeacherReportComment>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = termId ? `?term_id=${termId}` : "";
    const response = await apiPost<TeacherReportComment>(
      `/teacher/reports/comments/students/${studentId}/sign${params}`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to sign comment",
    };
  }
}

/**
 * Write or update a head teacher comment for a student.
 * Backend: POST /teacher/reports/comments/students/{studentId}/head-teacher?term_id=...
 *   -> ReportCommentResponse
 */
export async function writeHeadTeacherComment(
  studentId: string,
  comment: string,
  termId?: string
): Promise<ActionResult<TeacherReportComment>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = termId ? `?term_id=${termId}` : "";
    const response = await apiPost<TeacherReportComment>(
      `/teacher/reports/comments/students/${studentId}/head-teacher${params}`,
      { head_teacher_comment: comment },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to save head teacher comment",
    };
  }
}

/**
 * Sign a head teacher comment.
 * Backend: POST /teacher/reports/comments/students/{studentId}/head-teacher/sign?term_id=...
 *   -> ReportCommentResponse
 */
export async function signHeadTeacherComment(
  studentId: string,
  termId?: string
): Promise<ActionResult<TeacherReportComment>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = termId ? `?term_id=${termId}` : "";
    const response = await apiPost<TeacherReportComment>(
      `/teacher/reports/comments/students/${studentId}/head-teacher/sign${params}`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to sign head teacher comment",
    };
  }
}

// =========================
// Lesson Plans
// =========================

/**
 * List teacher's lesson plans.
 * Backend: GET /teacher/lessons?class_id=...&subject_id=...&date_from=...&date_to=...&status=...&limit=...&offset=...
 *   -> LessonPlanListResponse { plans, total }
 */
export async function getTeacherLessonPlans(
  options?: {
    classId?: string;
    subjectId?: string;
    dateFrom?: string;
    dateTo?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }
): Promise<ActionResult<TeacherLessonPlanListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (options?.classId) params.set("class_id", options.classId);
    if (options?.subjectId) params.set("subject_id", options.subjectId);
    if (options?.dateFrom) params.set("date_from", options.dateFrom);
    if (options?.dateTo) params.set("date_to", options.dateTo);
    if (options?.status) params.set("status", options.status);
    params.set("limit", String(options?.limit ?? 50));
    params.set("offset", String(options?.offset ?? 0));
    const response = await apiGet<TeacherLessonPlanListResponse>(
      `/teacher/lessons?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch lesson plans",
    };
  }
}

/**
 * Get a single lesson plan.
 * Backend: GET /teacher/lessons/{planId} -> LessonPlanResponse
 */
export async function getTeacherLessonPlan(
  planId: string
): Promise<ActionResult<TeacherLessonPlan>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TeacherLessonPlan>(
      `/teacher/lessons/${planId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch lesson plan",
    };
  }
}

/**
 * Create a new lesson plan.
 * Backend: POST /teacher/lessons -> LessonPlanResponse (status 201)
 */
export async function createTeacherLessonPlan(
  data: TeacherLessonPlanCreate
): Promise<ActionResult<TeacherLessonPlan>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<TeacherLessonPlan>(
      "/teacher/lessons",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create lesson plan",
    };
  }
}

/**
 * Update an existing lesson plan.
 * Backend: PATCH /teacher/lessons/{planId} -> LessonPlanResponse
 */
export async function updateTeacherLessonPlan(
  planId: string,
  data: TeacherLessonPlanUpdate
): Promise<ActionResult<TeacherLessonPlan>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<TeacherLessonPlan>(
      `/teacher/lessons/${planId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update lesson plan",
    };
  }
}

/**
 * Delete (soft-delete) a lesson plan.
 * Backend: DELETE /teacher/lessons/{planId} -> 204 No Content
 */
export async function deleteTeacherLessonPlan(
  planId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete<void>(
      `/teacher/lessons/${planId}`,
      { token, subdomain }
    );
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete lesson plan",
    };
  }
}

// =========================
// Communication
// =========================

/**
 * Send a broadcast announcement to all parents in a class.
 * Backend: POST /teacher/communication/broadcast -> ClassBroadcastResponse (status 201)
 */
export async function sendClassBroadcast(
  data: TeacherClassBroadcastRequest
): Promise<ActionResult<TeacherClassBroadcastResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<TeacherClassBroadcastResponse>(
      "/teacher/communication/broadcast",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to send broadcast",
    };
  }
}

// =========================
// Head Teacher
// =========================

/**
 * Get head teacher overview.
 *
 * NOTE: The backend has no /teacher/head-teacher/overview endpoint.
 * The only head teacher endpoint is /teacher/head-teacher/performance
 * which returns TeacherPerformanceSummary. This action calls a
 * nonexistent route. Kept as a stub for the overview page to compile.
 */
export async function getHeadTeacherOverview(): Promise<ActionResult<HeadTeacherOverview>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // TODO: Replace with actual endpoint or compose from multiple endpoints
    const response = await apiGet<HeadTeacherOverview>("/teacher/head-teacher/overview", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch head teacher overview",
    };
  }
}

/**
 * Get teacher performance summary.
 * Backend: GET /teacher/head-teacher/performance?term_id=...
 *   -> TeacherPerformanceSummary
 *
 * Note: The backend returns teacher-centric performance metrics
 * (per-teacher stats), NOT the class-centric HeadTeacherPerformanceData
 * the frontend page currently expects. The performance page will need
 * to be updated to display the actual response shape.
 */
export async function getHeadTeacherPerformance(
  termId?: string
): Promise<ActionResult<TeacherPerformanceSummary>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = termId ? `?term_id=${termId}` : "";
    const response = await apiGet<TeacherPerformanceSummary>(
      `/teacher/head-teacher/performance${params}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch performance data",
    };
  }
}

// =========================
// Notifications
// =========================

/**
 * Get teacher notifications list.
 *
 * NOTE: The backend has no /teacher/notifications endpoint.
 * Kept as a stub for the notifications page to compile.
 */
export async function getTeacherNotifications(
  page: number = 1
): Promise<ActionResult<TeacherNotificationList>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TeacherNotificationList>(
      `/teacher/notifications?page=${page}&page_size=20`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch notifications",
    };
  }
}

/**
 * Mark a notification as read.
 *
 * NOTE: The backend has no /teacher/notifications endpoint.
 */
export async function markTeacherNotificationRead(
  notificationId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiPatch<void>(
      `/teacher/notifications/${notificationId}/read`,
      {},
      { token, subdomain }
    );
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to mark notification as read",
    };
  }
}

/**
 * Mark all notifications as read.
 *
 * NOTE: The backend has no /teacher/notifications endpoint.
 */
export async function markAllTeacherNotificationsRead(): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiPost<void>(
      "/teacher/notifications/read-all",
      {},
      { token, subdomain }
    );
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to mark all as read",
    };
  }
}

// =========================
// Legacy / Stub Actions
// =========================

/**
 * @deprecated Use getTeacherReportComments instead.
 * Legacy stub kept for backwards compatibility with existing pages.
 */
export async function getTeacherReports(
  classId: string,
  termId?: string
): Promise<ActionResult<TeacherReportComment[]>> {
  try {
    const result = await getTeacherReportComments(termId);
    if (result.success) {
      return { success: true, data: result.data.comments };
    }
    return { success: false, error: result.error };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch reports",
    };
  }
}

/**
 * @deprecated Use writeClassTeacherComment for individual student comments.
 * Legacy stub kept for backwards compatibility with existing pages.
 */
export async function submitTeacherRemarks(
  data: { remarks: { report_id: string; class_teacher_remark: string }[] }
): Promise<ActionResult<{ updated: number }>> {
  try {
    let updated = 0;
    for (const remark of data.remarks) {
      // report_id here corresponds to student_id in the new API
      const result = await writeClassTeacherComment(remark.report_id, remark.class_teacher_remark);
      if (result.success) updated++;
    }
    return { success: true, data: { updated } };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to submit remarks",
    };
  }
}

/**
 * @deprecated No backend endpoint exists for CA entry through the teacher portal.
 * CA should be entered through the existing /exams CA endpoints.
 */
export async function submitTeacherCA(
  data: unknown
): Promise<ActionResult<{ created: number; updated: number; failed: number; errors: unknown[] }>> {
  return {
    success: false,
    error: "CA entry through the teacher portal is not yet implemented. Use the exam module.",
  };
}

/**
 * @deprecated No backend endpoint for note updates through the teacher portal.
 */
export async function updateTeacherNote(
  noteId: string,
  data: unknown
): Promise<ActionResult<TeacherNoteItem>> {
  return {
    success: false,
    error: "Note updates through the teacher portal are not yet implemented.",
  };
}
