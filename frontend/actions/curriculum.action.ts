"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete, apiUpload, ApiError } from "@/lib/api";
import { getValidAccessToken, refreshAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  CurriculumProfile,
  CurriculumProfileDetail,
  CurriculumProfileCreate,
  CurriculumProfileUpdate,
  CurriculumTemplateInfo,
  AssessmentStructure,
  AssessmentStructureCreate,
  AssessmentComponent,
  AssessmentComponentCreate,
  AssessmentComponentUpdate,
  ReportCardConfig,
  ReportCardConfigUpdate,
  ValidateStructureResponse,
  GradeEquivalency,
  GradeEquivalencyCreate,
  GradeConvertRequest,
  SubjectCurriculumMapping,
  SubjectCurriculumMappingCreate,
  SubjectCurriculumMappingUpdate,
  ExternalExamRegistration,
  ExternalExamRegistrationCreate,
  ExternalExamRegistrationUpdate,
  ResultsImportPreview,
  ResultsImportCommit,
  PredictedGrade,
  PredictedGradeCreate,
  PredictedGradeBulk,
  CreditRecord,
  StudentGPA,
  TranscriptData,
} from "@/types/curriculum.type";

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

/**
 * Execute an API call with automatic retry on 401 (expired token).
 */
async function withAuthRetry<T>(
  apiFn: (opts: { token?: string; subdomain?: string }) => Promise<T>,
): Promise<T> {
  const ctx = await getAuthContext();
  try {
    return await apiFn(ctx);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      const newToken = await refreshAccessToken();
      if (newToken) {
        return await apiFn({ ...ctx, token: newToken });
      }
    }
    throw error;
  }
}

// =========================
// Profile CRUD
// =========================

export async function getCurriculumProfiles(): Promise<ActionResult<CurriculumProfile[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<{ items: CurriculumProfile[]; total: number }>(
      "/curriculum/profiles",
      { token, subdomain },
    );
    return { success: true, data: response.items };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch curriculum profiles",
    };
  }
}

export async function getCurriculumProfile(
  id: string,
): Promise<ActionResult<CurriculumProfileDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<CurriculumProfileDetail>(
      `/curriculum/profiles/${id}`,
      { token, subdomain },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch curriculum profile",
    };
  }
}

export async function createCurriculumProfile(
  data: CurriculumProfileCreate,
): Promise<ActionResult<CurriculumProfile>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<CurriculumProfile>("/curriculum/profiles", data, opts),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create curriculum profile",
    };
  }
}

export async function updateCurriculumProfile(
  id: string,
  data: CurriculumProfileUpdate,
): Promise<ActionResult<CurriculumProfile>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPut<CurriculumProfile>(`/curriculum/profiles/${id}`, data, opts),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update curriculum profile",
    };
  }
}

export async function deleteCurriculumProfile(
  id: string,
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/curriculum/profiles/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete curriculum profile",
    };
  }
}

export async function setDefaultProfile(
  id: string,
): Promise<ActionResult<CurriculumProfile>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<CurriculumProfile>(`/curriculum/profiles/${id}/set-default`, {}, opts),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to set default profile",
    };
  }
}

// =========================
// Templates
// =========================

export async function getCurriculumTemplates(): Promise<ActionResult<CurriculumTemplateInfo[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<CurriculumTemplateInfo[]>("/curriculum/profiles/templates", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch curriculum templates",
    };
  }
}

export async function createFromTemplate(
  templateKey: string,
  nameOverride?: string,
): Promise<ActionResult<CurriculumProfileDetail>> {
  try {
    const body = nameOverride ? { name_override: nameOverride } : {};
    const response = await withAuthRetry((opts) =>
      apiPost<CurriculumProfileDetail>(
        `/curriculum/profiles/from-template?template_key=${encodeURIComponent(templateKey)}`,
        body,
        opts,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create profile from template",
    };
  }
}

// =========================
// Assessment Structure
// =========================

export async function getAssessmentStructure(
  profileId: string,
  academicYearId?: string,
): Promise<ActionResult<AssessmentStructure | null>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (academicYearId) params.append("academic_year_id", academicYearId);
    const qs = params.toString();
    const response = await apiGet<AssessmentStructure | null>(
      `/curriculum/profiles/${profileId}/assessment-structures${qs ? `?${qs}` : ""}`,
      { token, subdomain },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch assessment structure",
    };
  }
}

export async function createAssessmentStructure(
  profileId: string,
  data: AssessmentStructureCreate,
): Promise<ActionResult<AssessmentStructure>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<AssessmentStructure>(
        `/curriculum/profiles/${profileId}/assessment-structures`,
        data,
        opts,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create assessment structure",
    };
  }
}

export async function updateAssessmentStructure(
  structureId: string,
  data: { name?: string; description?: string; is_active?: boolean },
): Promise<ActionResult<AssessmentStructure>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPut<AssessmentStructure>(
        `/curriculum/assessment-structures/${structureId}`,
        data,
        opts,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update assessment structure",
    };
  }
}

export async function deleteAssessmentStructure(
  structureId: string,
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/curriculum/assessment-structures/${structureId}`, {
      token,
      subdomain,
    });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete assessment structure",
    };
  }
}

export async function addAssessmentComponent(
  structureId: string,
  data: AssessmentComponentCreate,
): Promise<ActionResult<AssessmentComponent>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<AssessmentComponent>(
        `/curriculum/assessment-structures/${structureId}/components`,
        data,
        opts,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to add assessment component",
    };
  }
}

export async function updateAssessmentComponent(
  componentId: string,
  data: AssessmentComponentUpdate,
): Promise<ActionResult<AssessmentComponent>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPut<AssessmentComponent>(
        `/curriculum/assessment-components/${componentId}`,
        data,
        opts,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update assessment component",
    };
  }
}

export async function deleteAssessmentComponent(
  componentId: string,
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/curriculum/assessment-components/${componentId}`, {
      token,
      subdomain,
    });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete assessment component",
    };
  }
}

/**
 * Bulk sync assessment components for a structure.
 * Replaces all components in a single request instead of individual
 * add/update/delete calls that triggered rate limiting.
 *
 * Backend: PUT /curriculum/assessment-structures/{structureId}/components/sync
 * Body: { components: [...] }
 */
export async function syncAssessmentComponents(
  structureId: string,
  components: Array<{
    id?: string;
    component_type: string;
    name: string;
    weight: number;
    max_score?: number;
    is_external?: boolean;
    sequence?: number;
    maps_to_ca?: boolean;
    maps_to_exam?: boolean;
    config?: Record<string, unknown>;
  }>,
): Promise<ActionResult<AssessmentStructure>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPut<AssessmentStructure>(
        `/curriculum/assessment-structures/${structureId}/components/sync`,
        { components },
        opts,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to sync assessment components",
    };
  }
}

export async function validateAssessmentStructure(
  structureId: string,
): Promise<ActionResult<ValidateStructureResponse>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<ValidateStructureResponse>(
        `/curriculum/assessment-structures/${structureId}/validate`,
        {},
        opts,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to validate assessment structure",
    };
  }
}

export async function reorderAssessmentComponents(
  structureId: string,
  componentIds: string[],
): Promise<ActionResult<AssessmentComponent[]>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPut<AssessmentComponent[]>(
        `/curriculum/assessment-structures/${structureId}/reorder`,
        { component_ids: componentIds },
        opts,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to reorder assessment components",
    };
  }
}

// =========================
// Report Card Config
// =========================

export async function getReportConfig(
  profileId: string,
): Promise<ActionResult<ReportCardConfig | null>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ReportCardConfig | null>(
      `/curriculum/profiles/${profileId}/report-config`,
      { token, subdomain },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch report card config",
    };
  }
}

export async function updateReportConfig(
  profileId: string,
  data: ReportCardConfigUpdate,
): Promise<ActionResult<ReportCardConfig>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPut<ReportCardConfig>(
        `/curriculum/profiles/${profileId}/report-config`,
        data,
        opts,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update report card config",
    };
  }
}

// =========================
// Grade Equivalencies
// =========================

export async function getGradeEquivalencies(params?: {
  source_scale_id?: string;
  target_scale_id?: string;
  page?: number;
  page_size?: number;
}): Promise<ActionResult<{ items: GradeEquivalency[]; total: number }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.source_scale_id) searchParams.append("source_scale_id", params.source_scale_id);
    if (params?.target_scale_id) searchParams.append("target_scale_id", params.target_scale_id);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.page_size) searchParams.append("page_size", String(params.page_size));
    const qs = searchParams.toString();
    const response = await apiGet<{ items: GradeEquivalency[]; total: number }>(
      `/curriculum/grade-equivalencies${qs ? `?${qs}` : ""}`,
      { token, subdomain },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch grade equivalencies",
    };
  }
}

export async function createGradeEquivalencies(
  data: GradeEquivalencyCreate,
): Promise<ActionResult<GradeEquivalency[]>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<GradeEquivalency[]>("/curriculum/grade-equivalencies", data, opts),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create grade equivalencies",
    };
  }
}

export async function deleteGradeEquivalency(
  id: string,
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/curriculum/grade-equivalencies/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete grade equivalency",
    };
  }
}

/**
 * Convert a grade from one grading scale to another.
 * Backend: POST /curriculum/grade-equivalencies/convert
 * Body: { source_grade_id, source_grading_scale_id, target_grading_scale_id }
 */
export async function convertGrade(
  data: GradeConvertRequest,
): Promise<ActionResult<GradeEquivalency | null>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<GradeEquivalency | null>("/curriculum/grade-equivalencies/convert", data, opts),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to convert grade",
    };
  }
}

// =========================
// Subject Curriculum Mappings
// =========================

export async function getSubjectMappings(params?: {
  curriculum_profile_id?: string;
  subject_id?: string;
  page?: number;
  page_size?: number;
}): Promise<ActionResult<{ items: SubjectCurriculumMapping[]; total: number }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.curriculum_profile_id) searchParams.append("curriculum_profile_id", params.curriculum_profile_id);
    if (params?.subject_id) searchParams.append("subject_id", params.subject_id);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.page_size) searchParams.append("page_size", String(params.page_size));
    const qs = searchParams.toString();
    const response = await apiGet<{ items: SubjectCurriculumMapping[]; total: number }>(
      `/curriculum/subject-mappings${qs ? `?${qs}` : ""}`,
      { token, subdomain },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch subject mappings",
    };
  }
}

export async function createSubjectMapping(
  data: SubjectCurriculumMappingCreate,
): Promise<ActionResult<SubjectCurriculumMapping>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<SubjectCurriculumMapping>("/curriculum/subject-mappings", data, opts),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create subject mapping",
    };
  }
}

export async function updateSubjectMapping(
  id: string,
  data: SubjectCurriculumMappingUpdate,
): Promise<ActionResult<SubjectCurriculumMapping>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPut<SubjectCurriculumMapping>(`/curriculum/subject-mappings/${id}`, data, opts),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update subject mapping",
    };
  }
}

export async function deleteSubjectMapping(
  id: string,
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/curriculum/subject-mappings/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete subject mapping",
    };
  }
}

// =========================
// External Exam Registrations
// =========================

export async function getExternalExamRegistrations(filters?: {
  student_id?: string;
  exam_board?: string;
  exam_session?: string;
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<ActionResult<{ items: ExternalExamRegistration[]; total: number }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (filters?.student_id) searchParams.append("student_id", filters.student_id);
    if (filters?.exam_board) searchParams.append("exam_board", filters.exam_board);
    if (filters?.exam_session) searchParams.append("exam_session", filters.exam_session);
    if (filters?.status) searchParams.append("status", filters.status);
    if (filters?.page) searchParams.append("page", String(filters.page));
    if (filters?.page_size) searchParams.append("page_size", String(filters.page_size));
    const qs = searchParams.toString();
    const response = await apiGet<{ items: ExternalExamRegistration[]; total: number }>(
      `/curriculum/external-exams/registrations${qs ? `?${qs}` : ""}`,
      { token, subdomain },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch external exam registrations",
    };
  }
}

export async function getExternalExamRegistration(
  id: string,
): Promise<ActionResult<ExternalExamRegistration>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ExternalExamRegistration>(
      `/curriculum/external-exams/registrations/${id}`,
      { token, subdomain },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch external exam registration",
    };
  }
}

export async function createExternalExamRegistration(
  data: ExternalExamRegistrationCreate,
): Promise<ActionResult<ExternalExamRegistration>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<ExternalExamRegistration>(
        "/curriculum/external-exams/registrations",
        data,
        opts,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create external exam registration",
    };
  }
}

export async function updateExternalExamRegistration(
  id: string,
  data: ExternalExamRegistrationUpdate,
): Promise<ActionResult<ExternalExamRegistration>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPut<ExternalExamRegistration>(
        `/curriculum/external-exams/registrations/${id}`,
        data,
        opts,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update external exam registration",
    };
  }
}

export async function deleteExternalExamRegistration(
  id: string,
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/curriculum/external-exams/registrations/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete external exam registration",
    };
  }
}

/**
 * Bulk register students for external exams.
 * Backend: POST /curriculum/external-exams/registrations/bulk
 * Body: { registrations: [...] }
 */
export async function bulkRegisterExternalExam(
  registrations: ExternalExamRegistrationCreate[],
): Promise<ActionResult<ExternalExamRegistration[]>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<ExternalExamRegistration[]>(
        "/curriculum/external-exams/registrations/bulk",
        { registrations },
        opts,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to bulk register external exams",
    };
  }
}

/**
 * Import exam results from a CSV file.
 * Backend: POST /curriculum/external-exams/results/import
 * Uses multipart/form-data for file upload.
 * Query params: exam_board, exam_session, dry_run
 */
export async function importExternalExamResults(
  examBoard: string,
  examSession: string,
  file: File,
  dryRun: boolean,
): Promise<ActionResult<ResultsImportPreview | ResultsImportCommit>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const formData = new FormData();
    formData.append("file", file);
    const params = new URLSearchParams({
      exam_board: examBoard,
      exam_session: examSession,
      dry_run: String(dryRun),
    });
    const response = await apiUpload<ResultsImportPreview | ResultsImportCommit>(
      `/curriculum/external-exams/results/import?${params.toString()}`,
      formData,
      { token, subdomain },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to import external exam results",
    };
  }
}

/**
 * Export external exam registration data.
 * Backend: GET /curriculum/external-exams/export?exam_board=...&exam_session=...
 */
export async function exportExternalExamRegistrations(
  examBoard: string,
  examSession: string,
): Promise<ActionResult<unknown>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams({
      exam_board: examBoard,
      exam_session: examSession,
    });
    const response = await apiGet<unknown>(
      `/curriculum/external-exams/export?${params.toString()}`,
      { token, subdomain },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to export exam registrations",
    };
  }
}

// =========================
// Predicted Grades
// =========================

export async function getPredictedGrades(filters?: {
  student_id?: string;
  subject_id?: string;
  academic_year_id?: string;
  page?: number;
  page_size?: number;
}): Promise<ActionResult<{ items: PredictedGrade[]; total: number }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (filters?.student_id) searchParams.append("student_id", filters.student_id);
    if (filters?.subject_id) searchParams.append("subject_id", filters.subject_id);
    if (filters?.academic_year_id) searchParams.append("academic_year_id", filters.academic_year_id);
    if (filters?.page) searchParams.append("page", String(filters.page));
    if (filters?.page_size) searchParams.append("page_size", String(filters.page_size));
    const qs = searchParams.toString();
    const response = await apiGet<{ items: PredictedGrade[]; total: number }>(
      `/curriculum/predicted-grades${qs ? `?${qs}` : ""}`,
      { token, subdomain },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch predicted grades",
    };
  }
}

export async function createPredictedGrade(
  data: PredictedGradeCreate,
): Promise<ActionResult<PredictedGrade>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<PredictedGrade>("/curriculum/predicted-grades", data, opts),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create predicted grade",
    };
  }
}

export async function updatePredictedGrade(
  id: string,
  data: { predicted_grade?: string; target_grade?: string; predicted_score?: number; notes?: string },
): Promise<ActionResult<PredictedGrade>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPut<PredictedGrade>(`/curriculum/predicted-grades/${id}`, data, opts),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update predicted grade",
    };
  }
}

export async function deletePredictedGrade(
  id: string,
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/curriculum/predicted-grades/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete predicted grade",
    };
  }
}

/**
 * Bulk create predicted grades.
 * Backend: POST /curriculum/predicted-grades/bulk
 * Body: { predictions: [...] }
 */
export async function bulkSetPredictedGrades(
  data: PredictedGradeBulk,
): Promise<ActionResult<PredictedGrade[]>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<PredictedGrade[]>("/curriculum/predicted-grades/bulk", data, opts),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to bulk set predicted grades",
    };
  }
}

// =========================
// Credits & GPA
// =========================

/**
 * Get student credit records.
 * Backend: GET /curriculum/credits?student_id=...&profile_id=...&academic_year_id=...
 */
export async function getStudentCredits(
  studentId: string,
  profileId: string,
  academicYearId?: string,
): Promise<ActionResult<{ items: CreditRecord[]; total: number }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams({
      student_id: studentId,
      profile_id: profileId,
    });
    if (academicYearId) searchParams.append("academic_year_id", academicYearId);
    const response = await apiGet<{ items: CreditRecord[]; total: number }>(
      `/curriculum/credits?${searchParams.toString()}`,
      { token, subdomain },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student credits",
    };
  }
}

/**
 * Get student GPA.
 * Backend: GET /curriculum/credits/gpa/{student_id}?profile_id=...
 */
export async function getStudentGPA(
  studentId: string,
  profileId: string,
  academicYearId?: string,
  termId?: string,
): Promise<ActionResult<StudentGPA>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams({ profile_id: profileId });
    if (academicYearId) searchParams.append("academic_year_id", academicYearId);
    if (termId) searchParams.append("term_id", termId);
    const response = await apiGet<StudentGPA>(
      `/curriculum/credits/gpa/${studentId}?${searchParams.toString()}`,
      { token, subdomain },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student GPA",
    };
  }
}

/**
 * Get student transcript.
 * Backend: GET /curriculum/credits/transcript/{student_id}?profile_id=...
 */
export async function getStudentTranscript(
  studentId: string,
  profileId: string,
): Promise<ActionResult<TranscriptData>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TranscriptData>(
      `/curriculum/credits/transcript/${studentId}?profile_id=${encodeURIComponent(profileId)}`,
      { token, subdomain },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch student transcript",
    };
  }
}

/**
 * Recalculate student credits.
 * Backend: POST /curriculum/credits/recalculate/{student_id}?profile_id=...
 */
export async function recalculateStudentCredits(
  studentId: string,
  profileId: string,
): Promise<ActionResult<{ records_updated: number }>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<{ records_updated: number }>(
        `/curriculum/credits/recalculate/${studentId}?profile_id=${encodeURIComponent(profileId)}`,
        {},
        opts,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to recalculate student credits",
    };
  }
}
