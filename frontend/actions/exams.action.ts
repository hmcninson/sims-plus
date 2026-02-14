"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete, apiPatch } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  PaginatedResponse,
  Exam,
  ExamCreate,
  ExamUpdate,
  ExamWithContext,
  ExamSubject,
  ExamSubjectWithDetails,
  ExamSubjectCreate,
  ExamSubjectBulkCreate,
  ExamSubjectAutoPopulate,
  ExamSubjectUpdate,
  ExamScore,
  ExamScoreWithStudent,
  ExamScoreBulkCreate,
  ExamScoreUpdate,
  ScoreEntryForm,
  BulkScoreResult,
  ContinuousAssessment,
  CAWithDetails,
  CACreate,
  CABulkCreate,
  CAUpdate,
  CASummary,
  TermReport,
  TermReportWithDetails,
  TermReportGenerate,
  TermReportRemarksUpdate,
  ClassResultsResponse,
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
// Exam Actions
// =========================

export interface ExamFilters {
  academic_year_id?: string;
  term_id?: string;
  exam_type?: string;
  status?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

export async function getExams(
  filters: ExamFilters = {}
): Promise<ActionResult<PaginatedResponse<Exam>>> {
  try {
    const { token, subdomain } = await getAuthContext();

    const params = new URLSearchParams();
    if (filters.academic_year_id) params.append("academic_year_id", filters.academic_year_id);
    if (filters.term_id) params.append("term_id", filters.term_id);
    if (filters.exam_type) params.append("exam_type", filters.exam_type);
    if (filters.status) params.append("status", filters.status);
    if (filters.search) params.append("search", filters.search);
    if (filters.page) params.append("page", String(filters.page));
    if (filters.page_size) params.append("page_size", String(filters.page_size));

    const url = `/exams${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<PaginatedResponse<Exam>>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch exams",
    };
  }
}

export async function getExam(id: string): Promise<ActionResult<ExamWithContext>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ExamWithContext>(`/exams/${id}`, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch exam",
    };
  }
}

export async function createExam(data: ExamCreate): Promise<ActionResult<Exam>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Exam>("/exams", data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create exam",
    };
  }
}

export async function updateExam(id: string, data: ExamUpdate): Promise<ActionResult<Exam>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<Exam>(`/exams/${id}`, data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update exam",
    };
  }
}

export async function deleteExam(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/exams/${id}`, { token, subdomain });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete exam",
    };
  }
}

export async function updateExamStatus(
  id: string,
  status: string
): Promise<ActionResult<Exam>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<Exam>(`/exams/${id}/status?status=${status}`, {}, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update exam status",
    };
  }
}

export async function publishExamResults(id: string): Promise<ActionResult<{ published_subjects: number }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<{ published_subjects: number }>(`/exams/${id}/publish`, {}, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to publish exam results",
    };
  }
}

// =========================
// Exam Subject Actions
// =========================

export async function getExamSubjects(
  examId: string,
  classId?: string
): Promise<ActionResult<ExamSubjectWithDetails[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = classId ? `?class_id=${classId}` : "";
    const response = await apiGet<ExamSubjectWithDetails[]>(
      `/exams/${examId}/subjects${params}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch exam subjects",
    };
  }
}

export async function addExamSubjects(
  examId: string,
  data: ExamSubjectBulkCreate
): Promise<ActionResult<ExamSubject[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ExamSubject[]>(
      `/exams/${examId}/subjects`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to add exam subjects",
    };
  }
}

export async function autoPopulateExamSubjects(
  examId: string,
  data: ExamSubjectAutoPopulate
): Promise<ActionResult<ExamSubjectWithDetails[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ExamSubjectWithDetails[]>(
      `/exams/${examId}/subjects/auto-populate`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to auto-populate exam subjects",
    };
  }
}

export async function updateExamSubject(
  examId: string,
  examSubjectId: string,
  data: ExamSubjectUpdate
): Promise<ActionResult<ExamSubject>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<ExamSubject>(
      `/exams/${examId}/subjects/${examSubjectId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update exam subject",
    };
  }
}

export async function removeExamSubject(
  examId: string,
  examSubjectId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/exams/${examId}/subjects/${examSubjectId}`, { token, subdomain });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to remove exam subject",
    };
  }
}

export async function submitExamSubjectScores(
  examId: string,
  examSubjectId: string
): Promise<ActionResult<ExamSubject>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ExamSubject>(
      `/exams/${examId}/subjects/${examSubjectId}/submit`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to submit scores",
    };
  }
}

// =========================
// Score Entry Actions
// =========================

export async function getScoreEntryForm(
  examId: string,
  examSubjectId: string,
  sectionId?: string
): Promise<ActionResult<ScoreEntryForm>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = sectionId ? `?section_id=${sectionId}` : "";
    const response = await apiGet<ScoreEntryForm>(
      `/exams/${examId}/subjects/${examSubjectId}/scores${params}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch score entry form",
    };
  }
}

export async function bulkEnterScores(
  examId: string,
  examSubjectId: string,
  data: ExamScoreBulkCreate
): Promise<ActionResult<BulkScoreResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<BulkScoreResult>(
      `/exams/${examId}/subjects/${examSubjectId}/scores`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to enter scores",
    };
  }
}

export async function updateScore(
  scoreId: string,
  data: ExamScoreUpdate
): Promise<ActionResult<ExamScore>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<ExamScore>(`/exams/scores/${scoreId}`, data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update score",
    };
  }
}

// =========================
// Results Actions
// =========================

export async function getClassResults(
  examId: string,
  classId: string,
  sectionId?: string
): Promise<ActionResult<ClassResultsResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = sectionId ? `?section_id=${sectionId}` : "";
    const response = await apiGet<ClassResultsResponse>(
      `/exams/${examId}/results/class/${classId}${params}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch class results",
    };
  }
}

export async function getStudentExamResults(
  examId: string,
  studentId: string
): Promise<ActionResult<ClassResultsResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ClassResultsResponse>(
      `/exams/${examId}/results/student/${studentId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student exam results",
    };
  }
}

// =========================
// Continuous Assessment Actions
// =========================

export interface CAFilters {
  academic_year_id?: string;
  term_id?: string;
  class_id?: string;
  subject_id?: string;
  student_id?: string;
  assessment_type?: string;
  page?: number;
  page_size?: number;
}

export async function getContinuousAssessments(
  filters: CAFilters = {}
): Promise<ActionResult<CAWithDetails[]>> {
  try {
    const { token, subdomain } = await getAuthContext();

    const params = new URLSearchParams();
    // Note: academic_year_id is not supported by backend, filter is done via term_id
    if (filters.term_id) params.append("term_id", filters.term_id);
    if (filters.class_id) params.append("class_id", filters.class_id);
    if (filters.subject_id) params.append("subject_id", filters.subject_id);
    if (filters.student_id) params.append("student_id", filters.student_id);
    if (filters.assessment_type) params.append("assessment_type", filters.assessment_type);
    if (filters.page) params.append("page", String(filters.page));
    if (filters.page_size) params.append("page_size", String(filters.page_size));

    const url = `/exams/ca${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<CAWithDetails[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch continuous assessments",
    };
  }
}

export async function createCA(data: CACreate): Promise<ActionResult<ContinuousAssessment>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ContinuousAssessment>("/exams/ca", data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create continuous assessment",
    };
  }
}

export async function bulkCreateCA(data: CABulkCreate): Promise<ActionResult<BulkScoreResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<BulkScoreResult>("/exams/ca/bulk", data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create bulk continuous assessments",
    };
  }
}

export async function updateCA(
  id: string,
  data: CAUpdate
): Promise<ActionResult<ContinuousAssessment>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<ContinuousAssessment>(`/exams/ca/${id}`, data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update continuous assessment",
    };
  }
}

export async function deleteCA(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/exams/ca/${id}`, { token, subdomain });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete continuous assessment",
    };
  }
}

export async function getCASummary(
  termId: string,
  classId: string,
  subjectId: string
): Promise<ActionResult<CASummary[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({
      term_id: termId,
      class_id: classId,
      subject_id: subjectId,
    });

    const response = await apiGet<CASummary[]>(`/exams/ca/summary?${params.toString()}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch CA summary",
    };
  }
}

// =========================
// Term Report Actions
// =========================

export interface TermReportFilters {
  academic_year_id?: string; // Not used by backend but kept for UI filtering
  term_id?: string;
  class_id?: string;
  section_id?: string;
  is_published?: boolean;
  page?: number;
  page_size?: number;
}

export async function getTermReports(
  filters: TermReportFilters = {}
): Promise<ActionResult<PaginatedResponse<TermReportWithDetails>>> {
  try {
    const { token, subdomain } = await getAuthContext();

    const params = new URLSearchParams();
    // Note: academic_year_id is not supported by backend - filter by term_id instead
    if (filters.term_id) params.append("term_id", filters.term_id);
    if (filters.class_id) params.append("class_id", filters.class_id);
    if (filters.section_id) params.append("section_id", filters.section_id);
    if (filters.is_published !== undefined) params.append("is_published", String(filters.is_published));
    if (filters.page) params.append("page", String(filters.page));
    if (filters.page_size) params.append("page_size", String(filters.page_size));

    const url = `/exams/reports/term${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<PaginatedResponse<TermReportWithDetails>>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch term reports",
    };
  }
}

export async function getTermReport(id: string): Promise<ActionResult<TermReportWithDetails>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TermReportWithDetails>(`/exams/reports/term/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch term report",
    };
  }
}

/**
 * Get the URL for downloading a term report PDF
 * This returns credentials needed to fetch the PDF from the client
 */
export async function getTermReportPdfUrl(id: string): Promise<ActionResult<{ url: string; token: string; subdomain: string }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    if (!token || !subdomain) {
      return { success: false, error: "Not authenticated" };
    }
    // Return the URL and credentials for client-side fetch
    // NEXT_PUBLIC_API_URL already includes /api/v1
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    return {
      success: true,
      data: {
        url: `${baseUrl}/exams/reports/term/${id}/pdf`,
        token,
        subdomain,
      },
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to get PDF URL",
    };
  }
}

export async function generateTermReports(
  data: TermReportGenerate
): Promise<ActionResult<{ generated: number; updated: number }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<{ generated: number; updated: number }>(
      "/exams/reports/term/generate",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to generate term reports",
    };
  }
}

export async function updateTermReportRemarks(
  id: string,
  data: TermReportRemarksUpdate
): Promise<ActionResult<TermReport>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<TermReport>(`/exams/reports/term/${id}/remarks`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update term report remarks",
    };
  }
}

export async function publishTermReports(
  termId: string,
  classId?: string
): Promise<ActionResult<{ published: number }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({ term_id: termId });
    if (classId) params.append("class_id", classId);

    const response = await apiPost<{ published: number }>(
      `/exams/reports/term/publish?${params.toString()}`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to publish term reports",
    };
  }
}

// =========================
// Analytics Actions
// =========================

export interface GradeCount {
  grade: string;
  count: number;
  percentage: number;
}

export interface GradeDistribution {
  exam_id: string;
  exam_name: string;
  class_id: string;
  class_name: string;
  subject_id?: string;
  subject_name?: string;
  total_students: number;
  graded_students: number;
  absent_students: number;
  grades: GradeCount[];
}

export interface PassFailStatistics {
  total_students: number;
  passed: number;
  failed: number;
  absent: number;
  pass_rate: number;
  fail_rate: number;
}

export interface ClassStatistics {
  exam_id: string;
  exam_name: string;
  class_id: string;
  class_name: string;
  section_id?: string;
  section_name?: string;
  total_students: number;
  students_with_scores: number;
  class_average?: number;
  highest_score?: number;
  lowest_score?: number;
  median_score?: number;
  pass_fail: PassFailStatistics;
  grade_distribution: GradeCount[];
}

export interface SubjectStatistics {
  subject_id: string;
  subject_name: string;
  subject_code?: string;
  total_students: number;
  students_with_scores: number;
  absent_students: number;
  average_score?: number;
  highest_score?: number;
  lowest_score?: number;
  median_score?: number;
  pass_rate: number;
  grade_distribution: GradeCount[];
}

export interface SubjectRankingStudent {
  student_id: string;
  student_name: string;
  student_id_number: string;
  score?: number;
  grade?: string;
  position: number;
}

export interface SubjectRankings {
  exam_id: string;
  exam_name: string;
  subject_id: string;
  subject_name: string;
  class_id: string;
  class_name: string;
  total_students: number;
  rankings: SubjectRankingStudent[];
}

export async function getGradeDistribution(
  examId: string,
  classId: string,
  subjectId?: string
): Promise<ActionResult<GradeDistribution>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({ class_id: classId });
    if (subjectId) params.append("subject_id", subjectId);

    const response = await apiGet<GradeDistribution>(
      `/exams/${examId}/analytics/grade-distribution?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch grade distribution",
    };
  }
}

export async function getClassStatistics(
  examId: string,
  classId: string,
  sectionId?: string
): Promise<ActionResult<ClassStatistics>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({ class_id: classId });
    if (sectionId) params.append("section_id", sectionId);

    const response = await apiGet<ClassStatistics>(
      `/exams/${examId}/analytics/class-statistics?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch class statistics",
    };
  }
}

export async function getSubjectStatistics(
  examId: string,
  classId: string,
  sectionId?: string
): Promise<ActionResult<SubjectStatistics[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({ class_id: classId });
    if (sectionId) params.append("section_id", sectionId);

    const response = await apiGet<SubjectStatistics[]>(
      `/exams/${examId}/analytics/subject-statistics?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch subject statistics",
    };
  }
}

export async function getSubjectRankings(
  examId: string,
  subjectId: string,
  classId: string,
  sectionId?: string
): Promise<ActionResult<SubjectRankings>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({ class_id: classId });
    if (sectionId) params.append("section_id", sectionId);

    const response = await apiGet<SubjectRankings>(
      `/exams/${examId}/analytics/subject-rankings/${subjectId}?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch subject rankings",
    };
  }
}

// =========================
// Timetabling Actions
// =========================

export interface TimetableEntry {
  exam_subject_id: string;
  subject_id: string;
  subject_name: string;
  subject_code?: string;
  class_id: string;
  class_name: string;
  section_id?: string;
  section_name?: string;
  exam_date?: string;
  exam_time?: string;
  duration_minutes?: number;
  venue?: string;
  max_score: number;
  status: string;
}

export interface ExamTimetable {
  exam_id: string;
  exam_name: string;
  exam_type: string;
  start_date?: string;
  end_date?: string;
  entries: TimetableEntry[];
  total_subjects: number;
  scheduled_subjects: number;
  unscheduled_subjects: number;
}

export interface TimetableConflict {
  conflict_type: string;
  severity: string;
  message: string;
  exam_subject_1_id: string;
  exam_subject_1_name: string;
  exam_subject_2_id?: string;
  exam_subject_2_name?: string;
}

export interface TimetableConflicts {
  exam_id: string;
  has_conflicts: boolean;
  total_conflicts: number;
  conflicts: TimetableConflict[];
}

export interface TimetableEntryUpdate {
  exam_subject_id: string;
  exam_date?: string;
  exam_time?: string;
  duration_minutes?: number;
  venue?: string;
}

export interface BulkTimetableUpdateResult {
  updated: number;
  failed: number;
  errors: Array<{ exam_subject_id: string; error: string }>;
  conflicts: TimetableConflict[];
}

export async function getExamTimetable(
  examId: string
): Promise<ActionResult<ExamTimetable>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ExamTimetable>(
      `/exams/${examId}/timetable`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch exam timetable",
    };
  }
}

export async function checkTimetableConflicts(
  examId: string
): Promise<ActionResult<TimetableConflicts>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TimetableConflicts>(
      `/exams/${examId}/timetable/conflicts`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to check timetable conflicts",
    };
  }
}

export async function bulkUpdateTimetable(
  examId: string,
  entries: TimetableEntryUpdate[]
): Promise<ActionResult<BulkTimetableUpdateResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<BulkTimetableUpdateResult>(
      `/exams/${examId}/timetable/bulk`,
      { entries },
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
