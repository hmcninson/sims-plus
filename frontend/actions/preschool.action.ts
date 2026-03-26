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
  PreschoolIncident,
  PreschoolIncidentCreate,
  PreschoolIncidentUpdate,
  AuthorizedPickup,
  AuthorizedPickupCreate,
  AuthorizedPickupUpdate,
  PickupLog,
  PickupLogCreate,
  DietaryRequirements,
  AllergyAlertResponse,
  LearningStory,
  LearningStoryCreate,
  LearningStoryUpdate,
  ExtendedCareSession,
  ExtendedCareBillingSummary,
  CaregiverRatio,
  TimelineEntry,
  PreschoolSupply,
  PreschoolSupplyCreate,
  PreschoolSupplyUpdate,
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
    const response = await apiGet<LearningArea[]>(
      `/preschool/learning-areas?include_inactive=${includeInactive}`,
      { token, subdomain }
    );
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
    return { success: true, data: undefined };
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
    return { success: true, data: undefined };
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
    return { success: true, data: undefined };
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
    return { success: true, data: undefined };
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

// =========================
// Incident Actions
// =========================

export async function listIncidents(
  params?: {
    student_id?: string;
    class_id?: string;
    status?: string;
    severity?: string;
    date_from?: string;
    date_to?: string;
  }
): Promise<ActionResult<PreschoolIncident[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.student_id) searchParams.set("student_id", params.student_id);
    if (params?.class_id) searchParams.set("class_id", params.class_id);
    if (params?.status) searchParams.set("status", params.status);
    if (params?.severity) searchParams.set("severity", params.severity);
    if (params?.date_from) searchParams.set("date_from", params.date_from);
    if (params?.date_to) searchParams.set("date_to", params.date_to);
    const query = searchParams.toString();
    const response = await apiGet<PreschoolIncident[]>(
      `/preschool/incidents${query ? `?${query}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch incidents",
    };
  }
}

export async function createIncident(
  data: PreschoolIncidentCreate
): Promise<ActionResult<PreschoolIncident>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PreschoolIncident>("/preschool/incidents", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create incident",
    };
  }
}

export async function getIncident(id: string): Promise<ActionResult<PreschoolIncident>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<PreschoolIncident>(`/preschool/incidents/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch incident",
    };
  }
}

export async function updateIncident(
  id: string,
  data: PreschoolIncidentUpdate
): Promise<ActionResult<PreschoolIncident>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<PreschoolIncident>(`/preschool/incidents/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update incident",
    };
  }
}

export async function notifyParentIncident(
  id: string
): Promise<ActionResult<PreschoolIncident>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PreschoolIncident>(
      `/preschool/incidents/${id}/notify-parent`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to notify parent",
    };
  }
}

export async function resolveIncident(
  id: string,
  follow_up_notes?: string
): Promise<ActionResult<PreschoolIncident>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PreschoolIncident>(
      `/preschool/incidents/${id}/resolve`,
      { follow_up_notes },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to resolve incident",
    };
  }
}

// =========================
// Authorized Pickup Actions
// =========================

export async function listAuthorizedPickups(
  studentId: string
): Promise<ActionResult<AuthorizedPickup[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<AuthorizedPickup[]>(
      `/preschool/students/${studentId}/authorized-pickups`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch authorized pickups",
    };
  }
}

export async function addAuthorizedPickup(
  studentId: string,
  data: AuthorizedPickupCreate
): Promise<ActionResult<AuthorizedPickup>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<AuthorizedPickup>(
      `/preschool/students/${studentId}/authorized-pickups`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to add authorized pickup",
    };
  }
}

export async function updateAuthorizedPickup(
  id: string,
  data: AuthorizedPickupUpdate
): Promise<ActionResult<AuthorizedPickup>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<AuthorizedPickup>(
      `/preschool/authorized-pickups/${id}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update authorized pickup",
    };
  }
}

export async function deleteAuthorizedPickup(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/preschool/authorized-pickups/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete authorized pickup",
    };
  }
}

// =========================
// Pickup Log Actions
// =========================

export async function recordPickup(
  data: PickupLogCreate
): Promise<ActionResult<PickupLog>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PickupLog>("/preschool/pickup-logs", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to record pickup",
    };
  }
}

export async function listPickupLogs(
  params?: { student_id?: string; class_id?: string; date_from?: string; date_to?: string }
): Promise<ActionResult<PickupLog[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.student_id) searchParams.set("student_id", params.student_id);
    if (params?.class_id) searchParams.set("class_id", params.class_id);
    if (params?.date_from) searchParams.set("date_from", params.date_from);
    if (params?.date_to) searchParams.set("date_to", params.date_to);
    const query = searchParams.toString();
    const response = await apiGet<PickupLog[]>(
      `/preschool/pickup-logs${query ? `?${query}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch pickup logs",
    };
  }
}

// =========================
// Allergy / Dietary Actions
// =========================

export async function getStudentDietaryRequirements(
  studentId: string
): Promise<ActionResult<DietaryRequirements | null>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<DietaryRequirements | null>(
      `/preschool/students/${studentId}/dietary-requirements`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch dietary requirements",
    };
  }
}

export async function updateDietaryRequirements(
  studentId: string,
  data: DietaryRequirements | null
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiPut(
      `/preschool/students/${studentId}/dietary-requirements`,
      { dietary_requirements: data },
      { token, subdomain }
    );
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update dietary requirements",
    };
  }
}

export async function getClassAllergyAlerts(
  classId: string
): Promise<ActionResult<AllergyAlertResponse[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<AllergyAlertResponse[]>(
      `/preschool/allergy-alerts?class_id=${classId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch allergy alerts",
    };
  }
}

// =========================
// Learning Story Actions (Phase 2)
// =========================

export async function listLearningStories(
  params?: {
    student_id?: string;
    class_id?: string;
    term_id?: string;
    is_shared?: boolean;
  }
): Promise<ActionResult<LearningStory[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.student_id) searchParams.set("student_id", params.student_id);
    if (params?.class_id) searchParams.set("class_id", params.class_id);
    if (params?.term_id) searchParams.set("term_id", params.term_id);
    if (params?.is_shared !== undefined) searchParams.set("is_shared", String(params.is_shared));
    const query = searchParams.toString();
    const response = await apiGet<LearningStory[]>(
      `/preschool/learning-stories${query ? `?${query}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch learning stories",
    };
  }
}

export async function createLearningStory(
  data: LearningStoryCreate
): Promise<ActionResult<LearningStory>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<LearningStory>("/preschool/learning-stories", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create learning story",
    };
  }
}

export async function getLearningStory(id: string): Promise<ActionResult<LearningStory>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<LearningStory>(`/preschool/learning-stories/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch learning story",
    };
  }
}

export async function updateLearningStory(
  id: string,
  data: LearningStoryUpdate
): Promise<ActionResult<LearningStory>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<LearningStory>(`/preschool/learning-stories/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update learning story",
    };
  }
}

export async function deleteLearningStory(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/preschool/learning-stories/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete learning story",
    };
  }
}

// =========================
// Extended Care Actions (Phase 2)
// =========================

export async function checkInExtendedCare(
  data: {
    student_id: string;
    session_type: "before_care" | "after_care";
    check_in_time?: string;
    notes?: string;
  }
): Promise<ActionResult<ExtendedCareSession>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ExtendedCareSession>(
      "/preschool/extended-care/check-in",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to check in student",
    };
  }
}

export async function checkOutExtendedCare(
  sessionId: string,
  notes?: string
): Promise<ActionResult<ExtendedCareSession>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ExtendedCareSession>(
      `/preschool/extended-care/${sessionId}/check-out`,
      { notes },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to check out student",
    };
  }
}

export async function listExtendedCareSessions(
  params?: {
    class_id?: string;
    session_type?: string;
    date_from?: string;
    date_to?: string;
  }
): Promise<ActionResult<ExtendedCareSession[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.class_id) searchParams.set("class_id", params.class_id);
    if (params?.session_type) searchParams.set("session_type", params.session_type);
    if (params?.date_from) searchParams.set("date_from", params.date_from);
    if (params?.date_to) searchParams.set("date_to", params.date_to);
    const query = searchParams.toString();
    const response = await apiGet<ExtendedCareSession[]>(
      `/preschool/extended-care/sessions${query ? `?${query}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch extended care sessions",
    };
  }
}

export async function getExtendedCareBillingSummary(
  params: { date_from: string; date_to: string; class_id?: string }
): Promise<ActionResult<ExtendedCareBillingSummary[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    searchParams.set("date_from", params.date_from);
    searchParams.set("date_to", params.date_to);
    if (params.class_id) searchParams.set("class_id", params.class_id);
    const response = await apiGet<ExtendedCareBillingSummary[]>(
      `/preschool/extended-care/billing-summary?${searchParams.toString()}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch billing summary",
    };
  }
}

// =========================
// Caregiver Ratio Actions (Phase 2)
// =========================

export async function listCaregiverRatios(
  academicYearId?: string
): Promise<ActionResult<CaregiverRatio[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = academicYearId ? `?academic_year_id=${academicYearId}` : "";
    const response = await apiGet<CaregiverRatio[]>(
      `/preschool/caregiver-ratios${params}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch caregiver ratios",
    };
  }
}

export async function setCaregiverRatio(
  classId: string,
  data: { max_children_per_caregiver: number; current_caregiver_count: number }
): Promise<ActionResult<CaregiverRatio>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<CaregiverRatio>(
      `/preschool/caregiver-ratios/${classId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update caregiver ratio",
    };
  }
}

// =========================
// Timeline Actions (Phase 2)
// =========================

export async function getStudentTimeline(
  studentId: string,
  params?: { date_from?: string; date_to?: string }
): Promise<ActionResult<TimelineEntry[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.date_from) searchParams.set("date_from", params.date_from);
    if (params?.date_to) searchParams.set("date_to", params.date_to);
    const query = searchParams.toString();
    const response = await apiGet<TimelineEntry[]>(
      `/preschool/students/${studentId}/timeline${query ? `?${query}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student timeline",
    };
  }
}

// =========================
// Daily Report Sending Actions (Phase 2)
// =========================

export async function sendDailyLogToParents(
  logId: string
): Promise<ActionResult<{ sent_count: number }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<{ sent_count: number }>(
      `/preschool/daily-logs/${logId}/send-to-parents`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to send daily report",
    };
  }
}

export async function bulkSendDailyLogs(
  classId: string,
  logDate: string
): Promise<ActionResult<{ total: number; sent: number }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<{ total: number; sent: number }>(
      "/preschool/daily-logs/bulk-send",
      { class_id: classId, log_date: logDate },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to send daily reports",
    };
  }
}

// =========================
// Supplies Actions (Phase 3)
// =========================

export async function listSupplies(
  studentId: string
): Promise<ActionResult<PreschoolSupply[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<PreschoolSupply[]>(
      `/preschool/students/${studentId}/supplies`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch supplies",
    };
  }
}

export async function addSupply(
  studentId: string,
  data: PreschoolSupplyCreate
): Promise<ActionResult<PreschoolSupply>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PreschoolSupply>(
      `/preschool/students/${studentId}/supplies`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to add supply",
    };
  }
}

export async function updateSupply(
  id: string,
  data: PreschoolSupplyUpdate
): Promise<ActionResult<PreschoolSupply>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<PreschoolSupply>(
      `/preschool/supplies/${id}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update supply",
    };
  }
}

export async function useSupply(
  id: string,
  quantity: number = 1
): Promise<ActionResult<PreschoolSupply>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PreschoolSupply>(
      `/preschool/supplies/${id}/use`,
      { quantity },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to use supply",
    };
  }
}

export async function restockSupply(
  id: string,
  quantity: number
): Promise<ActionResult<PreschoolSupply>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PreschoolSupply>(
      `/preschool/supplies/${id}/restock`,
      { quantity },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to restock supply",
    };
  }
}
