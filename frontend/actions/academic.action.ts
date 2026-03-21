"use server";

import { cache } from "react";
import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api";
import { getValidAccessToken, refreshAccessToken } from "./auth.action";
import type {
  ActionResult,
  AcademicYear,
  AcademicYearCreate,
  AcademicYearUpdate,
  Term,
  TermCreate,
  TermUpdate,
  Class,
  ClassCreate,
  ClassUpdate,
  ClassSection,
  ClassSectionCreate,
  ClassSectionUpdate,
  Subject,
  SubjectCreate,
  SubjectUpdate,
  ClassSubject,
  ClassSubjectCreate,
  GradingScale,
  GradingScaleCreate,
  GradingScaleUpdate,
  GradeCreate,
  AssessmentWeight,
  AssessmentWeightCreate,
  AcademicSettings,
  AcademicSettingsUpdate,
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

/**
 * Execute an API call with automatic retry on 401 (expired token).
 *
 * If the first attempt returns 401, we refresh the access token and
 * retry exactly once. This handles the edge case where the JWT expires
 * between `getAuthContext()` and the actual API call, or when the
 * cookie TTL and JWT `exp` are slightly out of sync.
 */
async function withAuthRetry<T>(
  apiFn: (opts: { token?: string; subdomain?: string }) => Promise<T>,
): Promise<T> {
  const ctx = await getAuthContext();
  try {
    return await apiFn(ctx);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      // Token may have just expired -- refresh and retry once
      const newToken = await refreshAccessToken();
      if (newToken) {
        return await apiFn({ ...ctx, token: newToken });
      }
    }
    throw error;
  }
}

// =========================
// Academic Year Actions
// =========================

export async function getAcademicYears(includeTerms: boolean = true): Promise<ActionResult<AcademicYear[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<AcademicYear[]>(
      `/academic/academic-years?include_terms=${includeTerms}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch academic years",
    };
  }
}

/**
 * Cached version of getAcademicYears for React server component deduplication.
 * Import this (instead of getAcademicYears) in server components that share a
 * render pass, so the fetch executes only once across layout + page.
 */
export const getCachedAcademicYears = cache(getAcademicYears);

export async function getAcademicYear(id: string): Promise<ActionResult<AcademicYear>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<AcademicYear>(`/academic/academic-years/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch academic year",
    };
  }
}

export async function getCurrentAcademicYear(): Promise<ActionResult<AcademicYear>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<AcademicYear[]>(
      `/academic/academic-years?include_terms=true`,
      { token, subdomain }
    );
    // Find the current academic year (is_current === true or status === "active")
    const currentYear = response.find((year) => year.is_current || year.status === "active");
    if (!currentYear) {
      return {
        success: false,
        error: "No current academic year found",
      };
    }
    return { success: true, data: currentYear };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch current academic year",
    };
  }
}

export async function createAcademicYear(
  data: AcademicYearCreate
): Promise<ActionResult<AcademicYear>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<AcademicYear>("/academic/academic-years", data, opts),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create academic year",
    };
  }
}

export async function updateAcademicYear(
  id: string,
  data: AcademicYearUpdate
): Promise<ActionResult<AcademicYear>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<AcademicYear>(`/academic/academic-years/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update academic year",
    };
  }
}

export async function deleteAcademicYear(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/academic/academic-years/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete academic year",
    };
  }
}

export async function archiveAcademicYear(
  yearId: string,
): Promise<ActionResult<AcademicYear>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<AcademicYear>(`/academic/academic-years/${yearId}/archive`, {}, opts),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to archive academic year",
    };
  }
}

// =========================
// Term Actions
// =========================

export async function getTerms(academicYearId?: string): Promise<ActionResult<Term[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const url = academicYearId
      ? `/academic/terms?academic_year_id=${academicYearId}`
      : "/academic/terms";
    const response = await apiGet<Term[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch terms",
    };
  }
}

export async function getTerm(id: string): Promise<ActionResult<Term>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<Term>(`/academic/terms/${id}`, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch term",
    };
  }
}

export async function createTerm(data: TermCreate): Promise<ActionResult<Term>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Term>("/academic/terms", data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create term",
    };
  }
}

export async function updateTerm(id: string, data: TermUpdate): Promise<ActionResult<Term>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<Term>(`/academic/terms/${id}`, data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update term",
    };
  }
}

export async function deleteTerm(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/academic/terms/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete term",
    };
  }
}

export async function getCurrentTerm(): Promise<ActionResult<Term>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<Term[]>("/academic/terms", { token, subdomain });
    // Find the current term (status === "active")
    const currentTerm = response.find((term) => term.status === "active");
    if (!currentTerm) {
      return {
        success: false,
        error: "No current term found",
      };
    }
    return { success: true, data: currentTerm };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch current term",
    };
  }
}

// =========================
// Class Actions
// =========================

export async function getClasses(includeSections: boolean = false): Promise<ActionResult<Class[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const url = includeSections ? "/academic/classes?include_sections=true" : "/academic/classes";
    const response = await apiGet<Class[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch classes",
    };
  }
}

/**
 * Cached version of getClasses for React server component deduplication.
 * React.cache() deduplicates by arguments, so getCachedClasses() and
 * getCachedClasses(true) remain separate calls — correct since they return
 * different data (without vs with sections).
 */
export const getCachedClasses = cache(getClasses);

export async function getClass(id: string): Promise<ActionResult<Class>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<Class>(`/academic/classes/${id}`, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch class",
    };
  }
}

export async function createClass(data: ClassCreate): Promise<ActionResult<Class>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<Class>("/academic/classes", data, opts),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create class",
    };
  }
}

export async function updateClass(id: string, data: ClassUpdate): Promise<ActionResult<Class>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<Class>(`/academic/classes/${id}`, data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update class",
    };
  }
}

export async function deleteClass(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/academic/classes/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete class",
    };
  }
}

// =========================
// Class Section Actions
// =========================

export async function getSections(classId?: string): Promise<ActionResult<ClassSection[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const url = classId ? `/academic/sections?class_id=${classId}` : "/academic/sections";
    const response = await apiGet<ClassSection[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch sections",
    };
  }
}

export async function getSection(id: string): Promise<ActionResult<ClassSection>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ClassSection>(`/academic/sections/${id}`, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch section",
    };
  }
}

export async function createSection(data: ClassSectionCreate): Promise<ActionResult<ClassSection>> {
  try {
    const response = await withAuthRetry((opts) =>
      apiPost<ClassSection>("/academic/sections", data, opts),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create section",
    };
  }
}

export async function updateSection(
  id: string,
  data: ClassSectionUpdate
): Promise<ActionResult<ClassSection>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<ClassSection>(`/academic/sections/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update section",
    };
  }
}

export async function deleteSection(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/academic/sections/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete section",
    };
  }
}

// =========================
// Subject Actions
// =========================

export async function getSubjects(classLevel?: string): Promise<ActionResult<Subject[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    if (classLevel) {
      params.append("class_level", classLevel);
    }
    const url = `/academic/subjects${params.toString() ? `?${params.toString()}` : ""}`;
    const response = await apiGet<Subject[]>(url, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch subjects",
    };
  }
}

export async function getSubject(id: string): Promise<ActionResult<Subject>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<Subject>(`/academic/subjects/${id}`, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch subject",
    };
  }
}

export async function createSubject(data: SubjectCreate): Promise<ActionResult<Subject>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Subject>("/academic/subjects", data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create subject",
    };
  }
}

export async function updateSubject(
  id: string,
  data: SubjectUpdate
): Promise<ActionResult<Subject>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<Subject>(`/academic/subjects/${id}`, data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update subject",
    };
  }
}

export async function deleteSubject(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/academic/subjects/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete subject",
    };
  }
}

// =========================
// Class Subject Assignment Actions
// =========================

export async function getClassSubjects(classId: string): Promise<ActionResult<ClassSubject[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ClassSubject[]>(`/academic/classes/${classId}/subjects`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch class subjects",
    };
  }
}

export async function getSubjectsForClasses(classIds: string[]): Promise<ActionResult<ClassSubject[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ClassSubject[]>(`/academic/classes/subjects/bulk`, classIds, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch subjects for classes",
    };
  }
}

export async function assignSubjectToClass(
  data: ClassSubjectCreate
): Promise<ActionResult<ClassSubject>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ClassSubject>(
      `/academic/classes/${data.class_id}/subjects`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to assign subject",
    };
  }
}

export async function removeSubjectFromClass(
  classId: string,
  subjectId: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/academic/classes/${classId}/subjects/${subjectId}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to remove subject",
    };
  }
}

// =========================
// Grading Scale Actions
// =========================

export async function getGradingScales(): Promise<ActionResult<GradingScale[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<GradingScale[]>("/academic/grading-scales?include_grades=true", { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch grading scales",
    };
  }
}

export async function getGradingScale(id: string): Promise<ActionResult<GradingScale>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<GradingScale>(`/academic/grading-scales/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch grading scale",
    };
  }
}

export async function createGradingScale(
  data: GradingScaleCreate
): Promise<ActionResult<GradingScale>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<GradingScale>("/academic/grading-scales", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create grading scale",
    };
  }
}

export async function updateGradingScale(
  id: string,
  data: GradingScaleUpdate
): Promise<ActionResult<GradingScale>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<GradingScale>(`/academic/grading-scales/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update grading scale",
    };
  }
}

export async function deleteGradingScale(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/academic/grading-scales/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete grading scale",
    };
  }
}

export async function addGradeToScale(
  scaleId: string,
  data: GradeCreate
): Promise<ActionResult<GradingScale>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<GradingScale>(
      `/academic/grading-scales/${scaleId}/grades`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to add grade",
    };
  }
}

// =========================
// Assessment Weight Actions
// =========================

export async function getAssessmentWeights(): Promise<ActionResult<AssessmentWeight>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<AssessmentWeight>("/academic/assessment-weights", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch assessment weights",
    };
  }
}

export async function setAssessmentWeights(
  data: AssessmentWeightCreate
): Promise<ActionResult<AssessmentWeight>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<AssessmentWeight>("/academic/assessment-weights", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to set assessment weights",
    };
  }
}

// =========================
// Academic Settings Actions
// =========================

export async function getAcademicSettings(): Promise<ActionResult<AcademicSettings>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<AcademicSettings>("/academic/settings", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch academic settings",
    };
  }
}

export async function updateAcademicSettings(
  data: AcademicSettingsUpdate
): Promise<ActionResult<AcademicSettings>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<AcademicSettings>("/academic/settings", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update academic settings",
    };
  }
}

// =========================
// Subject Template Actions
// =========================

export async function initializeSubjectsFromTemplate(
  schoolType: string,
  programmes?: string[],
): Promise<ActionResult<{ created: number; skipped: number; subjects: { name: string; code: string; category: string }[] }>> {
  try {
    const response = await withAuthRetry((ctx) =>
      apiPost<{ created: number; skipped: number; subjects: { name: string; code: string; category: string }[] }>(
        "/academic/subject-templates/init",
        { school_type: schoolType, programmes },
        ctx,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to initialize subjects from template",
    };
  }
}

export async function getSubjectTemplates(
  schoolType: string,
): Promise<ActionResult<{ name: string; code: string; category: string; applicable_levels: string[] }[]>> {
  try {
    const response = await withAuthRetry((ctx) =>
      apiGet<{ name: string; code: string; category: string; applicable_levels: string[] }[]>(
        `/academic/subject-templates?school_type=${encodeURIComponent(schoolType)}`,
        ctx,
      ),
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch subject templates",
    };
  }
}

export async function getAvailableProgrammes(): Promise<ActionResult<string[]>> {
  try {
    const response = await withAuthRetry((ctx) =>
      apiGet<{ programmes: string[] }>(
        "/academic/subject-templates/programmes",
        ctx,
      ),
    );
    return { success: true, data: response.programmes };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch available programmes",
    };
  }
}
