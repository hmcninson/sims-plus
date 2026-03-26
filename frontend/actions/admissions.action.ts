"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiPatch, apiDelete, apiUpload } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  // Public types
  PublicSchoolInfo,
  PublicPeriodListResponse,
  PublicFormConfig,
  ApplicationSubmitData,
  ApplicationSubmitResponse,
  ApplicationStatusCheck,
  DocumentUploadData,
  DocumentUploadResponse,
  PaymentInitiateData,
  PaymentInitiateResponse,
  // Admin — Periods
  AdmissionPeriod,
  AdmissionPeriodCreate,
  AdmissionPeriodUpdate,
  AdmissionPeriodListResponse,
  // Admin — Form Config
  FormConfig,
  FormConfigUpdate,
  // Admin — Applications
  ApplicationDetail,
  ApplicationListResponse,
  ApplicationNote,
  // Admin — Entrance Exams
  EntranceExam,
  EntranceExamCreate,
  EntranceExamListResponse,
  ExamRegistration,
  ExamResult,
  ExamResultEntry,
  // Admin — Decisions
  AdmissionDecision,
  DecisionCreate,
  BulkDecisionRequest,
  BulkDecisionResponse,
  // Admin — Enrollment
  EnrollRequest,
  EnrollResponse,
  BulkEnrollRequest,
  BulkEnrollResponse,
  // Admin — Promotions
  ClassPromotion,
  ClassPromotionCreate,
  ClassPromotionListResponse,
  ClassPromotionEntry,
  ClassPromotionEntryListResponse,
  PromotionEntryUpdate,
  BulkPromotionUpdateResponse,
  // Admin — Return Intent
  ReturnIntentCampaign,
  ReturnIntentCampaignCreate,
  ReturnIntentCampaignListResponse,
  // Admin — Dashboard
  AdmissionsDashboardStats,
  AdmissionsDemographicsData,
  // Phase 2 — Letters, Offers, Waitlist
  GenerateLetterResponse,
  WaitlistListResponse,
  WaitlistPromoteData,
  WaitlistReorderData,
  ReminderConfigUpdate,
  OfferDetail,
  OfferResponse,
  // Phase 3 — Enrollment Checklist + CSSPS
  EnrollmentChecklist,
  EnrollmentDepositResponse,
  BoardingStatusResponse,
  ConfirmationLetterResponse,
  WelcomePackResponse,
  CSSPSPreviewResponse,
  CSSPSImportResponse,
} from "@/types/admissions.type";

const PUBLIC_BASE = "/admissions/public";
const ADMIN_BASE = "/admissions";

// =========================
// Helpers
// =========================

/**
 * Get subdomain from cookies for tenant resolution.
 * Public endpoints use subdomain-based tenant resolution (no auth token).
 */
async function getSubdomain(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get("x-subdomain")?.value;
}

/**
 * Get auth context: token + subdomain for authenticated admin actions.
 */
async function getAuthContext(): Promise<{
  token: string;
  subdomain: string | undefined;
}> {
  const token = await getValidAccessToken();
  const subdomain = await getSubdomain();
  return { token: token || "", subdomain };
}

// =========================
// Public Actions (No Auth)
// =========================

/**
 * Fetch public school info for the admissions portal branding.
 * No auth token needed -- tenant resolved from subdomain.
 */
export async function getPublicSchoolInfo(): Promise<
  ActionResult<PublicSchoolInfo>
> {
  try {
    const subdomain = await getSubdomain();
    const response = await apiGet<PublicSchoolInfo>(
      `${PUBLIC_BASE}/school-info`,
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch school information",
    };
  }
}

/**
 * Fetch open admission periods with school branding.
 * No auth token needed -- tenant resolved from subdomain.
 */
export async function getPublicPeriods(): Promise<
  ActionResult<PublicPeriodListResponse>
> {
  try {
    const subdomain = await getSubdomain();
    const response = await apiGet<PublicPeriodListResponse>(
      `${PUBLIC_BASE}/periods`,
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch admission periods",
    };
  }
}

/**
 * Fetch form configuration for a specific admission period.
 */
export async function getPublicFormConfig(
  periodId: string
): Promise<ActionResult<PublicFormConfig>> {
  try {
    const subdomain = await getSubdomain();
    const response = await apiGet<PublicFormConfig>(
      `${PUBLIC_BASE}/periods/${periodId}/form`,
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch form configuration",
    };
  }
}

/**
 * Submit a new application.
 */
export async function submitApplication(
  data: ApplicationSubmitData
): Promise<ActionResult<ApplicationSubmitResponse>> {
  try {
    const subdomain = await getSubdomain();
    const response = await apiPost<ApplicationSubmitResponse>(
      `${PUBLIC_BASE}/applications`,
      data,
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to submit application",
    };
  }
}

/**
 * Check application status by tracking code.
 */
export async function checkApplicationStatus(
  trackingCode: string
): Promise<ActionResult<ApplicationStatusCheck>> {
  try {
    const subdomain = await getSubdomain();
    const response = await apiGet<ApplicationStatusCheck>(
      `${PUBLIC_BASE}/applications/${encodeURIComponent(trackingCode)}/status`,
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to check application status",
    };
  }
}

/**
 * Request presigned URL for document upload.
 */
export async function requestDocumentUpload(
  trackingCode: string,
  data: DocumentUploadData
): Promise<ActionResult<DocumentUploadResponse>> {
  try {
    const subdomain = await getSubdomain();
    const response = await apiPost<DocumentUploadResponse>(
      `${PUBLIC_BASE}/applications/${encodeURIComponent(trackingCode)}/documents`,
      data,
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to prepare document upload",
    };
  }
}

/**
 * Initiate application fee payment via Paystack.
 */
export async function initiatePayment(
  trackingCode: string,
  data: PaymentInitiateData
): Promise<ActionResult<PaymentInitiateResponse>> {
  try {
    const subdomain = await getSubdomain();
    const response = await apiPost<PaymentInitiateResponse>(
      `${PUBLIC_BASE}/applications/${encodeURIComponent(trackingCode)}/pay`,
      data,
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to initiate payment",
    };
  }
}

// =========================
// Admin Actions (Authenticated)
// =========================

// --- Periods ---

export async function getAdmissionPeriods(params?: {
  page?: number;
  page_size?: number;
  status?: string;
  academic_year_id?: string;
}): Promise<ActionResult<AdmissionPeriodListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    if (params?.status) query.set("status", params.status);
    if (params?.academic_year_id)
      query.set("academic_year_id", params.academic_year_id);
    const qs = query.toString();
    const response = await apiGet<AdmissionPeriodListResponse>(
      `${ADMIN_BASE}/periods${qs ? `?${qs}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch admission periods",
    };
  }
}

export async function createAdmissionPeriod(
  data: AdmissionPeriodCreate
): Promise<ActionResult<AdmissionPeriod>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<AdmissionPeriod>(
      `${ADMIN_BASE}/periods`,
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
          : "Failed to create admission period",
    };
  }
}

export async function updateAdmissionPeriod(
  periodId: string,
  data: AdmissionPeriodUpdate
): Promise<ActionResult<AdmissionPeriod>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<AdmissionPeriod>(
      `${ADMIN_BASE}/periods/${periodId}`,
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
          : "Failed to update admission period",
    };
  }
}

export async function changeAdmissionPeriodStatus(
  periodId: string,
  status: string
): Promise<ActionResult<AdmissionPeriod>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<AdmissionPeriod>(
      `${ADMIN_BASE}/periods/${periodId}/status`,
      { status },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to update period status",
    };
  }
}

export async function updateFormConfig(
  periodId: string,
  data: FormConfigUpdate
): Promise<ActionResult<FormConfig>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<FormConfig>(
      `${ADMIN_BASE}/periods/${periodId}/form-config`,
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
          : "Failed to update form configuration",
    };
  }
}

// --- Applications ---

export async function getApplications(params?: {
  page?: number;
  page_size?: number;
  status?: string;
  admission_period_id?: string;
  target_class_id?: string;
  search?: string;
  sort_by?: string;
  sort_order?: string;
}): Promise<ActionResult<ApplicationListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") {
          query.set(k, String(v));
        }
      });
    }
    const qs = query.toString();
    const response = await apiGet<ApplicationListResponse>(
      `${ADMIN_BASE}/applications${qs ? `?${qs}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch applications",
    };
  }
}

export async function getApplicationDetail(
  applicationId: string
): Promise<ActionResult<ApplicationDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ApplicationDetail>(
      `${ADMIN_BASE}/applications/${applicationId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch application details",
    };
  }
}

export async function changeApplicationStatus(
  applicationId: string,
  status: string,
  reason?: string
): Promise<ActionResult<ApplicationDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<ApplicationDetail>(
      `${ADMIN_BASE}/applications/${applicationId}/status`,
      { status, reason },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to update application status",
    };
  }
}

export async function addApplicationNote(
  applicationId: string,
  content: string,
  isInternal?: boolean
): Promise<ActionResult<ApplicationNote>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ApplicationNote>(
      `${ADMIN_BASE}/applications/${applicationId}/notes`,
      { content, is_internal: isInternal ?? true },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to add note",
    };
  }
}

export async function waiveApplicationFee(
  applicationId: string,
  reason: string
): Promise<ActionResult<ApplicationDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<ApplicationDetail>(
      `${ADMIN_BASE}/applications/${applicationId}/waive-fee`,
      { reason },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to waive fee",
    };
  }
}

export async function waiveApplicationExam(
  applicationId: string,
  reason: string
): Promise<ActionResult<ApplicationDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<ApplicationDetail>(
      `${ADMIN_BASE}/applications/${applicationId}/waive-exam`,
      { reason },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to waive exam",
    };
  }
}

// --- Entrance Exams ---

export async function getEntranceExams(params?: {
  page?: number;
  page_size?: number;
  admission_period_id?: string;
  status?: string;
}): Promise<ActionResult<EntranceExamListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    if (params?.admission_period_id)
      query.set("admission_period_id", params.admission_period_id);
    if (params?.status) query.set("status", params.status);
    const qs = query.toString();
    const response = await apiGet<EntranceExamListResponse>(
      `${ADMIN_BASE}/exams${qs ? `?${qs}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch entrance exams",
    };
  }
}

export async function createEntranceExam(
  data: EntranceExamCreate
): Promise<ActionResult<EntranceExam>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<EntranceExam>(
      `${ADMIN_BASE}/exams`,
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
          : "Failed to create entrance exam",
    };
  }
}

export async function getEntranceExamDetail(
  examId: string
): Promise<ActionResult<EntranceExam>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<EntranceExam>(
      `${ADMIN_BASE}/exams/${examId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch exam details",
    };
  }
}

export async function registerApplicantsForExam(
  examId: string,
  applicationIds: string[]
): Promise<ActionResult<ExamRegistration[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ExamRegistration[]>(
      `${ADMIN_BASE}/exams/${examId}/register`,
      { application_ids: applicationIds },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to register applicants",
    };
  }
}

export async function submitExamResults(
  examId: string,
  results: ExamResultEntry[]
): Promise<ActionResult<ExamResult[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ExamResult[]>(
      `${ADMIN_BASE}/exams/${examId}/results`,
      { results },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to submit exam results",
    };
  }
}

/**
 * Alias for submitExamResults -- used by exam detail page.
 */
export async function recordExamResults(
  examId: string,
  results: ExamResultEntry[]
): Promise<ActionResult<ExamResult[]>> {
  return submitExamResults(examId, results);
}

export async function getExamRegistrations(
  examId: string
): Promise<ActionResult<ExamRegistration[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ExamRegistration[]>(
      `${ADMIN_BASE}/exams/${examId}/registrations`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch exam registrations",
    };
  }
}

export async function getExamResults(
  examId: string
): Promise<ActionResult<ExamResult[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ExamResult[]>(
      `${ADMIN_BASE}/exams/${examId}/results`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch exam results",
    };
  }
}

export async function markExamAttendance(
  examId: string,
  registrationId: string,
  attended: boolean
): Promise<ActionResult<ExamRegistration>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<ExamRegistration>(
      `${ADMIN_BASE}/exams/${examId}/registrations/${registrationId}/attendance`,
      { attended },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to mark attendance",
    };
  }
}

// --- Decisions ---

export async function makeDecision(
  data: DecisionCreate
): Promise<ActionResult<AdmissionDecision>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<AdmissionDecision>(
      `${ADMIN_BASE}/decisions`,
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
          : "Failed to make admission decision",
    };
  }
}

export async function bulkDecision(
  data: BulkDecisionRequest
): Promise<ActionResult<BulkDecisionResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<BulkDecisionResponse>(
      `${ADMIN_BASE}/decisions/bulk`,
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
          : "Failed to process bulk decisions",
    };
  }
}

// --- Enrollment ---

export async function enrollApplicant(
  applicationId: string,
  data?: EnrollRequest
): Promise<ActionResult<EnrollResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<EnrollResponse>(
      `${ADMIN_BASE}/applications/${applicationId}/enroll`,
      data ?? { generate_invoice: true },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to enroll applicant",
    };
  }
}

export async function bulkEnroll(
  data: BulkEnrollRequest
): Promise<ActionResult<BulkEnrollResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<BulkEnrollResponse>(
      `${ADMIN_BASE}/enroll/bulk`,
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
          : "Failed to process bulk enrollment",
    };
  }
}

// --- Class Promotions ---

export async function getPromotionBatches(params?: {
  page?: number;
  page_size?: number;
}): Promise<ActionResult<ClassPromotionListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    const qs = query.toString();
    const response = await apiGet<ClassPromotionListResponse>(
      `${ADMIN_BASE}/promotions${qs ? `?${qs}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch promotion batches",
    };
  }
}

export async function createPromotionBatch(
  data: ClassPromotionCreate
): Promise<ActionResult<ClassPromotion>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ClassPromotion>(
      `${ADMIN_BASE}/promotions`,
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
          : "Failed to create promotion batch",
    };
  }
}

export async function getPromotionDetail(
  promotionId: string
): Promise<ActionResult<ClassPromotion>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ClassPromotion>(
      `${ADMIN_BASE}/promotions/${promotionId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch promotion details",
    };
  }
}

export async function generatePromotionPreview(
  promotionId: string
): Promise<ActionResult<ClassPromotion>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ClassPromotion>(
      `${ADMIN_BASE}/promotions/${promotionId}/preview`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to generate promotion preview",
    };
  }
}

export async function getPromotionEntries(
  promotionId: string,
  params?: {
    source_class_id?: string;
    action?: string;
    page?: number;
    page_size?: number;
  }
): Promise<ActionResult<ClassPromotionEntryListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = new URLSearchParams();
    if (params?.source_class_id)
      query.set("source_class_id", params.source_class_id);
    if (params?.action) query.set("action", params.action);
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    const qs = query.toString();
    const response = await apiGet<ClassPromotionEntryListResponse>(
      `${ADMIN_BASE}/promotions/${promotionId}/entries${qs ? `?${qs}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch promotion entries",
    };
  }
}

export async function updatePromotionEntry(
  entryId: string,
  data: PromotionEntryUpdate
): Promise<ActionResult<ClassPromotionEntry>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<ClassPromotionEntry>(
      `${ADMIN_BASE}/promotions/entries/${entryId}`,
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
          : "Failed to update promotion entry",
    };
  }
}

export async function bulkUpdatePromotionEntries(
  promotionId: string,
  updates: Array<{ entry_id: string; action: string; target_class_id?: string; target_section_id?: string; reason?: string }>
): Promise<ActionResult<BulkPromotionUpdateResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<BulkPromotionUpdateResponse>(
      `${ADMIN_BASE}/promotions/${promotionId}/entries/bulk`,
      { updates },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to bulk update entries",
    };
  }
}

export async function executePromotionBatch(
  promotionId: string
): Promise<ActionResult<ClassPromotion>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ClassPromotion>(
      `${ADMIN_BASE}/promotions/${promotionId}/execute`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to execute promotion batch",
    };
  }
}

// --- Return Intent Surveys ---

export async function getReturnIntentCampaigns(params?: {
  page?: number;
  page_size?: number;
}): Promise<ActionResult<ReturnIntentCampaignListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    const qs = query.toString();
    const response = await apiGet<ReturnIntentCampaignListResponse>(
      `${ADMIN_BASE}/return-intents/campaigns${qs ? `?${qs}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch return intent campaigns",
    };
  }
}

export async function createReturnIntentCampaign(
  data: ReturnIntentCampaignCreate
): Promise<ActionResult<ReturnIntentCampaign>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ReturnIntentCampaign>(
      `${ADMIN_BASE}/return-intents/campaigns`,
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
          : "Failed to create return intent campaign",
    };
  }
}

export async function getCampaignDetail(
  campaignId: string
): Promise<ActionResult<ReturnIntentCampaign>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ReturnIntentCampaign>(
      `${ADMIN_BASE}/return-intents/campaigns/${campaignId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch campaign details",
    };
  }
}

export async function sendReturnIntentCampaign(
  campaignId: string
): Promise<ActionResult<ReturnIntentCampaign>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ReturnIntentCampaign>(
      `${ADMIN_BASE}/return-intents/campaigns/${campaignId}/send`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to send campaign",
    };
  }
}

// --- Dashboard / Analytics ---

export async function getAdmissionsDashboard(
  admissionPeriodId?: string
): Promise<ActionResult<AdmissionsDashboardStats>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = admissionPeriodId
      ? `?admission_period_id=${admissionPeriodId}`
      : "";
    const response = await apiGet<AdmissionsDashboardStats>(
      `${ADMIN_BASE}/dashboard/stats${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch admissions dashboard",
    };
  }
}

export async function getAdmissionsDemographics(
  admissionPeriodId?: string
): Promise<ActionResult<AdmissionsDemographicsData>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = admissionPeriodId
      ? `?admission_period_id=${admissionPeriodId}`
      : "";
    const response = await apiGet<AdmissionsDemographicsData>(
      `${ADMIN_BASE}/dashboard/demographics${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch demographics data",
    };
  }
}

// =========================
// Phase 2: Letter Generation
// =========================

export async function generateAdmissionLetter(
  decisionId: string
): Promise<ActionResult<GenerateLetterResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<GenerateLetterResponse>(
      `${ADMIN_BASE}/decisions/${decisionId}/generate-admission-letter`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to generate admission letter",
    };
  }
}

export async function generateRejectionLetter(
  decisionId: string,
  rejectionReason?: string
): Promise<ActionResult<GenerateLetterResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<GenerateLetterResponse>(
      `${ADMIN_BASE}/decisions/${decisionId}/generate-rejection-letter`,
      { rejection_reason: rejectionReason },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to generate rejection letter",
    };
  }
}

// =========================
// Phase 2: Waitlist Management
// =========================

export async function getWaitlist(params?: {
  period_id?: string;
  page?: number;
  page_size?: number;
}): Promise<ActionResult<WaitlistListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = new URLSearchParams();
    if (params?.period_id) query.set("period_id", params.period_id);
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    const qs = query.toString();
    const response = await apiGet<WaitlistListResponse>(
      `${ADMIN_BASE}/decisions/waitlist${qs ? `?${qs}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch waitlist",
    };
  }
}

export async function reorderWaitlist(
  data: WaitlistReorderData
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiPost(
      `${ADMIN_BASE}/decisions/reorder-waitlist`,
      data,
      { token, subdomain }
    );
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to reorder waitlist",
    };
  }
}

export async function promoteFromWaitlist(
  decisionId: string,
  data: WaitlistPromoteData
): Promise<ActionResult<AdmissionDecision>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<AdmissionDecision>(
      `${ADMIN_BASE}/decisions/${decisionId}/promote-waitlist`,
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
          : "Failed to promote from waitlist",
    };
  }
}

// =========================
// Phase 2: Reminder Config
// =========================

export async function updateReminderConfig(
  periodId: string,
  data: ReminderConfigUpdate
): Promise<ActionResult<AdmissionPeriod>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<AdmissionPeriod>(
      `${ADMIN_BASE}/periods/${periodId}/reminder-config`,
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
          : "Failed to update reminder configuration",
    };
  }
}

// =========================
// Phase 2: Offer Response (Applicant Portal)
// =========================

export async function getOfferDetails(
  applicationId: string
): Promise<ActionResult<OfferDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<OfferDetail>(
      `${ADMIN_BASE}/applicant/offers/${applicationId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch offer details",
    };
  }
}

export async function respondToOffer(
  applicationId: string,
  response: OfferResponse,
  notes?: string
): Promise<ActionResult<OfferDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const result = await apiPost<OfferDetail>(
      `${ADMIN_BASE}/applicant/offers/${applicationId}/respond`,
      { response, notes },
      { token, subdomain }
    );
    return { success: true, data: result };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to respond to offer",
    };
  }
}

// =========================
// Phase 3: Enrollment Checklist
// =========================

export async function createEnrollmentChecklist(
  applicationId: string,
  checklistType?: string
): Promise<ActionResult<EnrollmentChecklist>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const body = checklistType ? { checklist_type: checklistType } : {};
    const response = await apiPost<EnrollmentChecklist>(
      `${ADMIN_BASE}/applications/${applicationId}/enrollment-checklist`,
      body,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to create enrollment checklist",
    };
  }
}

export async function getEnrollmentChecklist(
  applicationId: string
): Promise<ActionResult<EnrollmentChecklist>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<EnrollmentChecklist>(
      `${ADMIN_BASE}/applications/${applicationId}/enrollment-checklist`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch enrollment checklist",
    };
  }
}

export async function completeChecklistItem(
  itemId: string,
  notes?: string,
  metadata?: Record<string, unknown>
): Promise<ActionResult<EnrollmentChecklist>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const body: Record<string, unknown> = {};
    if (notes) body.notes = notes;
    if (metadata) body.metadata = metadata;
    const response = await apiPatch<EnrollmentChecklist>(
      `${ADMIN_BASE}/checklist-items/${itemId}/complete`,
      body,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to complete checklist item",
    };
  }
}

export async function recordEnrollmentDeposit(
  applicationId: string,
  amount: number,
  reference: string
): Promise<ActionResult<EnrollmentDepositResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<EnrollmentDepositResponse>(
      `${ADMIN_BASE}/applications/${applicationId}/enrollment-deposit`,
      { amount, reference },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to record enrollment deposit",
    };
  }
}

export async function updateBoardingStatus(
  applicationId: string,
  boardingStatus: string
): Promise<ActionResult<BoardingStatusResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<BoardingStatusResponse>(
      `${ADMIN_BASE}/applications/${applicationId}/boarding-status`,
      { boarding_status: boardingStatus },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to update boarding status",
    };
  }
}

export async function generateEnrollmentConfirmation(
  applicationId: string
): Promise<ActionResult<ConfirmationLetterResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<ConfirmationLetterResponse>(
      `${ADMIN_BASE}/applications/${applicationId}/enrollment-confirmation`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to generate enrollment confirmation",
    };
  }
}

export async function sendWelcomePack(
  applicationId: string
): Promise<ActionResult<WelcomePackResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<WelcomePackResponse>(
      `${ADMIN_BASE}/applications/${applicationId}/welcome-pack`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to send welcome pack",
    };
  }
}

// =========================
// Phase 3: CSSPS Import
// =========================

export async function previewCSSPSImport(
  formData: FormData
): Promise<ActionResult<CSSPSPreviewResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiUpload<CSSPSPreviewResponse>(
      `${ADMIN_BASE}/cssps/preview`,
      formData,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to preview CSSPS file",
    };
  }
}

export async function executeCSSPSImport(
  formData: FormData
): Promise<ActionResult<CSSPSImportResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiUpload<CSSPSImportResponse>(
      `${ADMIN_BASE}/cssps/import`,
      formData,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to import CSSPS data",
    };
  }
}

export async function downloadCSSPSTemplate(): Promise<ActionResult<Blob>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<Blob>(
      `${ADMIN_BASE}/cssps/template`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to download CSSPS template",
    };
  }
}

// =========================
// Phase 4: Enrollment Analytics
// =========================

/**
 * Get admissions funnel (inquiry -> application -> decision -> enrollment).
 */
export async function getAdmissionsFunnel(
  periodId?: string
): Promise<ActionResult<import("@/types/admissions.type").FunnelResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = periodId ? `?period_id=${encodeURIComponent(periodId)}` : "";
    const response = await apiGet<import("@/types/admissions.type").FunnelResponse>(
      `${ADMIN_BASE}/analytics/funnel${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch admissions funnel",
    };
  }
}

/**
 * Get year-over-year enrollment trends.
 */
export async function getEnrollmentTrends(
  yearCount?: number
): Promise<ActionResult<import("@/types/admissions.type").TrendsResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = yearCount ? `?year_count=${yearCount}` : "";
    const response = await apiGet<import("@/types/admissions.type").TrendsResponse>(
      `${ADMIN_BASE}/analytics/trends${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch enrollment trends",
    };
  }
}

/**
 * Get lead source effectiveness metrics.
 */
export async function getLeadSourceEffectiveness(
  periodId?: string
): Promise<ActionResult<import("@/types/admissions.type").SourceEffectivenessResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = periodId ? `?period_id=${encodeURIComponent(periodId)}` : "";
    const response = await apiGet<import("@/types/admissions.type").SourceEffectivenessResponse>(
      `${ADMIN_BASE}/analytics/lead-sources${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch lead source data",
    };
  }
}

/**
 * Get re-enrollment rates year-over-year.
 */
export async function getReEnrollmentRates(
  yearCount?: number
): Promise<ActionResult<import("@/types/admissions.type").ReEnrollmentResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = yearCount ? `?year_count=${yearCount}` : "";
    const response = await apiGet<import("@/types/admissions.type").ReEnrollmentResponse>(
      `${ADMIN_BASE}/analytics/re-enrollment${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch re-enrollment rates",
    };
  }
}

/**
 * Get attrition analysis (withdrawn + not-returning with reasons).
 */
export async function getAttritionAnalysis(
  academicYearId?: string
): Promise<ActionResult<import("@/types/admissions.type").AttritionResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const query = academicYearId
      ? `?academic_year_id=${encodeURIComponent(academicYearId)}`
      : "";
    const response = await apiGet<import("@/types/admissions.type").AttritionResponse>(
      `${ADMIN_BASE}/analytics/attrition${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch attrition analysis",
    };
  }
}

/**
 * Get enrollment vs capacity comparison.
 */
export async function getEnrollmentVsCapacity(
  academicYearId: string
): Promise<ActionResult<import("@/types/admissions.type").EnrollmentVsCapacityResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<import("@/types/admissions.type").EnrollmentVsCapacityResponse>(
      `${ADMIN_BASE}/analytics/capacity?academic_year_id=${encodeURIComponent(academicYearId)}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch enrollment vs capacity",
    };
  }
}

// =========================
// Phase 4: Re-enrollment Confirmation
// =========================

/**
 * Confirm re-enrollment for a returning student intent.
 */
export async function confirmReEnrollment(
  intentId: string
): Promise<ActionResult<import("@/types/admissions.type").ReturnIntentRecord>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<import("@/types/admissions.type").ReturnIntentRecord>(
      `${ADMIN_BASE}/return-intents/${encodeURIComponent(intentId)}/confirm`,
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to confirm re-enrollment",
    };
  }
}

/**
 * Get re-enrollment summary for a return intent campaign.
 */
export async function getReEnrollmentSummary(
  campaignId: string
): Promise<ActionResult<import("@/types/admissions.type").ReEnrollmentSummaryResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<import("@/types/admissions.type").ReEnrollmentSummaryResponse>(
      `${ADMIN_BASE}/return-intents/campaigns/${encodeURIComponent(campaignId)}/summary`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch re-enrollment summary",
    };
  }
}
