"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  LearningArea,
  LearningAreaCreate,
  LearningAreaUpdate,
  DevelopmentalSkill,
  DevelopmentalSkillCreate,
  DevelopmentalSkillUpdate,
  PreschoolRatingScale,
  PreschoolRatingScaleCreate,
  PreschoolRatingScaleUpdate,
  StudentSkillAssessment,
  StudentSkillAssessmentCreate,
  StudentSkillAssessmentBulk,
  ProgressObservation,
  ProgressObservationCreate,
  ProgressObservationUpdate,
  DailyActivityLog,
  DailyActivityLogCreate,
  DailyActivityLogUpdate,
  PreschoolReport,
  PreschoolReportCreate,
  PreschoolReportUpdate,
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
// Learning Area Actions
// =========================

export async function getLearningAreas(
  includeInactive: boolean = false
): Promise<ActionResult<LearningArea[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    console.log("[getLearningAreas] token:", token ? "present" : "missing", "subdomain:", subdomain);
    const response = await apiGet<LearningArea[]>(
      `/preschool/learning-areas?include_inactive=${includeInactive}`,
      { token, subdomain }
    );
    console.log("[getLearningAreas] response:", response);
    return { success: true, data: response };
  } catch (error) {
    console.error("[getLearningAreas] error:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch learning areas",
    };
  }
}

export async function getLearningArea(id: string): Promise<ActionResult<LearningArea>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<LearningArea>(`/preschool/learning-areas/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch learning area",
    };
  }
}

export async function getLearningAreaWithSkills(
  id: string
): Promise<ActionResult<LearningArea>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<LearningArea>(
      `/preschool/learning-areas/${id}/skills`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch learning area with skills",
    };
  }
}

export async function createLearningArea(
  data: LearningAreaCreate
): Promise<ActionResult<LearningArea>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<LearningArea>("/preschool/learning-areas", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create learning area",
    };
  }
}

export async function updateLearningArea(
  id: string,
  data: LearningAreaUpdate
): Promise<ActionResult<LearningArea>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<LearningArea>(`/preschool/learning-areas/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update learning area",
    };
  }
}

export async function deleteLearningArea(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/preschool/learning-areas/${id}`, { token, subdomain });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete learning area",
    };
  }
}

export async function seedLearningAreas(
  includeSkills: boolean = true
): Promise<ActionResult<LearningArea[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<LearningArea[]>(
      "/preschool/seed/learning-areas",
      { include_skills: includeSkills },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to seed learning areas",
    };
  }
}

// =========================
// Developmental Skill Actions
// =========================

export async function getSkillsByLearningArea(
  learningAreaId: string,
  includeInactive: boolean = false
): Promise<ActionResult<DevelopmentalSkill[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // API returns LearningAreaWithSkills object, extract skills array
    const response = await apiGet<{ skills: DevelopmentalSkill[] }>(
      `/preschool/learning-areas/${learningAreaId}/skills?include_inactive=${includeInactive}`,
      { token, subdomain }
    );
    return { success: true, data: response.skills || [] };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch skills",
    };
  }
}

export async function getSkill(id: string): Promise<ActionResult<DevelopmentalSkill>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<DevelopmentalSkill>(`/preschool/skills/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch skill",
    };
  }
}

export async function createSkill(
  data: DevelopmentalSkillCreate
): Promise<ActionResult<DevelopmentalSkill>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<DevelopmentalSkill>("/preschool/skills", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create skill",
    };
  }
}

export async function updateSkill(
  id: string,
  data: DevelopmentalSkillUpdate
): Promise<ActionResult<DevelopmentalSkill>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<DevelopmentalSkill>(`/preschool/skills/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update skill",
    };
  }
}

export async function deleteSkill(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/preschool/skills/${id}`, { token, subdomain });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete skill",
    };
  }
}

// =========================
// Rating Scale Actions
// =========================

export async function getRatingScales(): Promise<ActionResult<PreschoolRatingScale[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<PreschoolRatingScale[]>("/preschool/rating-scales", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch rating scales",
    };
  }
}

export async function getRatingScale(id: string): Promise<ActionResult<PreschoolRatingScale>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<PreschoolRatingScale>(`/preschool/rating-scales/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch rating scale",
    };
  }
}

export async function createRatingScale(
  data: PreschoolRatingScaleCreate
): Promise<ActionResult<PreschoolRatingScale>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PreschoolRatingScale>("/preschool/rating-scales", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create rating scale",
    };
  }
}

export async function updateRatingScale(
  id: string,
  data: PreschoolRatingScaleUpdate
): Promise<ActionResult<PreschoolRatingScale>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<PreschoolRatingScale>(
      `/preschool/rating-scales/${id}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update rating scale",
    };
  }
}

export async function deleteRatingScale(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/preschool/rating-scales/${id}`, { token, subdomain });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete rating scale",
    };
  }
}

export async function seedRatingScale(
  setAsDefault: boolean = true
): Promise<ActionResult<PreschoolRatingScale>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PreschoolRatingScale>(
      "/preschool/seed/rating-scale",
      { set_as_default: setAsDefault },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to seed rating scale",
    };
  }
}

// =========================
// Student Skill Assessment Actions
// =========================

export async function getStudentAssessments(
  studentId: string,
  academicYearId?: string,
  termId?: string,
  learningAreaId?: string
): Promise<ActionResult<StudentSkillAssessment[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (academicYearId) params.append("academic_year_id", academicYearId);
    if (termId) params.append("term_id", termId);
    if (learningAreaId) params.append("learning_area_id", learningAreaId);

    const response = await apiGet<StudentSkillAssessment[]>(
      `/preschool/students/${studentId}/assessments?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch assessments",
    };
  }
}

export async function getAssessmentsByTerm(
  termId: string,
  learningAreaId?: string
): Promise<ActionResult<StudentSkillAssessment[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    params.append("term_id", termId);
    if (learningAreaId) params.append("learning_area_id", learningAreaId);

    const response = await apiGet<StudentSkillAssessment[]>(
      `/preschool/assessments?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch assessments",
    };
  }
}

export async function createAssessment(
  data: StudentSkillAssessmentCreate
): Promise<ActionResult<StudentSkillAssessment>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StudentSkillAssessment>("/preschool/assessments", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create assessment",
    };
  }
}

export async function bulkUpdateAssessments(
  data: StudentSkillAssessmentBulk
): Promise<ActionResult<{ created: number; updated: number }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<{ created: number; updated: number }>(
      "/preschool/assessments/bulk",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update assessments",
    };
  }
}

// =========================
// Progress Observation Actions
// =========================

export async function getStudentObservations(
  studentId: string,
  observationType?: string,
  learningAreaId?: string,
  startDate?: string,
  endDate?: string
): Promise<ActionResult<ProgressObservation[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (observationType) params.append("observation_type", observationType);
    if (learningAreaId) params.append("learning_area_id", learningAreaId);
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);

    const response = await apiGet<ProgressObservation[]>(
      `/preschool/observations/student/${studentId}?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch observations",
    };
  }
}

export async function createObservation(
  data: ProgressObservationCreate
): Promise<ActionResult<ProgressObservation>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ProgressObservation>("/preschool/observations", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create observation",
    };
  }
}

export async function updateObservation(
  id: string,
  data: ProgressObservationUpdate
): Promise<ActionResult<ProgressObservation>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<ProgressObservation>(
      `/preschool/observations/${id}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update observation",
    };
  }
}

export async function deleteObservation(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/preschool/observations/${id}`, { token, subdomain });
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete observation",
    };
  }
}

// =========================
// Daily Activity Log Actions
// =========================

export async function getStudentDailyLogs(
  studentId: string,
  startDate?: string,
  endDate?: string
): Promise<ActionResult<DailyActivityLog[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);

    const response = await apiGet<DailyActivityLog[]>(
      `/preschool/daily-logs/student/${studentId}?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch daily logs",
    };
  }
}

export async function getDailyLog(
  studentId: string,
  date: string
): Promise<ActionResult<DailyActivityLog | null>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // Fetch logs for the student and filter by date
    const response = await apiGet<DailyActivityLog[]>(
      `/preschool/daily-logs/student/${studentId}`,
      { token, subdomain }
    );
    // Find the log for the specific date
    const log = response.find((l) => l.log_date === date);
    return { success: true, data: log || null };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch daily log",
    };
  }
}

export async function createDailyLog(
  data: DailyActivityLogCreate
): Promise<ActionResult<DailyActivityLog>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<DailyActivityLog>("/preschool/daily-logs", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create daily log",
    };
  }
}

export async function updateDailyLog(
  id: string,
  data: DailyActivityLogUpdate
): Promise<ActionResult<DailyActivityLog>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<DailyActivityLog>(`/preschool/daily-logs/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update daily log",
    };
  }
}

// =========================
// Preschool Report Actions
// =========================

export async function getStudentReports(
  studentId: string,
  academicYearId?: string,
  termId?: string
): Promise<ActionResult<PreschoolReport[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    params.append("student_id", studentId);
    if (academicYearId) params.append("academic_year_id", academicYearId);
    if (termId) params.append("term_id", termId);

    const response = await apiGet<PreschoolReport[]>(
      `/preschool/reports?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch reports",
    };
  }
}

export async function getClassReports(
  classId: string,
  termId?: string
): Promise<ActionResult<PreschoolReport[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    params.append("class_id", classId);
    if (termId) params.append("term_id", termId);

    const response = await apiGet<PreschoolReport[]>(
      `/preschool/reports?${params.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch reports",
    };
  }
}

export async function getPreschoolReport(id: string): Promise<ActionResult<PreschoolReport>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<PreschoolReport>(`/preschool/reports/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch report",
    };
  }
}

export async function generatePreschoolReports(
  classId: string,
  academicYearId: string,
  termId: string
): Promise<ActionResult<{ generated: number }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<{ generated: number }>(
      "/preschool/reports/generate",
      { class_id: classId, academic_year_id: academicYearId, term_id: termId },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to generate reports",
    };
  }
}

export async function updatePreschoolReport(
  id: string,
  data: PreschoolReportUpdate
): Promise<ActionResult<PreschoolReport>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<PreschoolReport>(`/preschool/reports/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update report",
    };
  }
}

export async function publishPreschoolReports(
  reportIds: string[]
): Promise<ActionResult<{ published: number }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<{ published: number }>(
      "/preschool/reports/publish",
      { report_ids: reportIds },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to publish reports",
    };
  }
}

export async function getReportPdfDownloadInfo(
  reportId: string
): Promise<ActionResult<{ url: string; token: string; subdomain: string }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    // Use public API URL for browser access (not Docker internal URL)
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    return {
      success: true,
      data: {
        url: `${apiUrl}/preschool/reports/${reportId}/pdf`,
        token: token || "",
        subdomain: subdomain || "",
      },
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to get download info",
    };
  }
}
