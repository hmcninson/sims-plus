# Phase 2: Frontend — Public Application Portal

**Sprint:** 19-20 (parallel with backend Agent 3)
**Agent:** 4 (UI Agent)
**Depends on:** Backend public endpoints (Agent 3 task 3.2) for data fetching
**Produces:** Public-facing application form pages, payment flow, status check, types, actions

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 4.1 | Create TypeScript types | `frontend/types/admissions.type.ts` | 0.5d |
| 4.2 | Create Server Actions (public) | `frontend/actions/admissions.action.ts` | 1d |
| 4.3 | Create branded layout | `frontend/app/(auth)/apply/layout.tsx` | 0.5d |
| 4.4 | Create landing page | `frontend/app/(auth)/apply/page.tsx` | 0.5d |
| 4.5 | Create application form wizard | `frontend/app/(auth)/apply/[periodId]/page.tsx` | 3d |
| 4.6 | Create application form components | `frontend/components/admissions/application-form-wizard.tsx` | (included in 4.5) |
| 4.7 | Create status check page | `frontend/app/(auth)/apply/status/page.tsx` | 0.5d |
| 4.8 | Create Paystack callback page | `frontend/app/(auth)/apply/pay/callback/page.tsx` | 0.5d |
| 4.9 | Create application status badge | `frontend/components/admissions/application-status-badge.tsx` | 0.25d |

---

## 4.1 TypeScript Types

**File:** `frontend/types/admissions.type.ts`

```typescript
/**
 * SIMS Plus - Admissions Portal Type Definitions
 */

// =========================
// Enums
// =========================

export type ApplicationStatus =
  | "draft"
  | "submitted"
  | "under_review"
  | "shortlisted"
  | "exam_scheduled"
  | "exam_completed"
  | "offered"
  | "accepted"
  | "waitlisted"
  | "rejected"
  | "enrolled"
  | "withdrawn"
  | "expired"
  | "deferred";

export type AdmissionPeriodStatus = "draft" | "open" | "closed" | "archived";

export type EntranceExamStatus = "scheduled" | "in_progress" | "completed" | "cancelled";

export type DecisionType = "accepted" | "rejected" | "waitlisted" | "deferred";

// =========================
// Public Types
// =========================

export interface PublicSchoolInfo {
  school_name: string;
  logo_url?: string;
  primary_color?: string;
  secondary_color?: string;
  motto?: string;
  address?: string;
  phone?: string;
  email?: string;
}

export interface PublicTargetClass {
  id: string;
  name: string;
  level?: string;
}

export interface PublicPeriod {
  id: string;
  name: string;
  description?: string;
  start_date: string;
  end_date: string;
  application_fee_amount?: number;
  application_fee_required: boolean;
  entrance_exam_required: boolean;
  target_classes: PublicTargetClass[];
}

export interface PublicPeriodListResponse {
  items: PublicPeriod[];
  school: PublicSchoolInfo;
}

export interface PublicFormConfig {
  admission_period_id: string;
  period_name: string;
  form_schema: Record<string, unknown>;
  required_documents: string[];
  application_fee_amount?: number;
  application_fee_required: boolean;
  target_classes: PublicTargetClass[];
}

export interface GuardianSubmit {
  first_name: string;
  last_name: string;
  phone: string;
  email?: string;
  relationship: "father" | "mother" | "guardian" | "other";
  is_primary: boolean;
  occupation?: string;
  address?: string;
}

export interface ApplicationSubmitData {
  admission_period_id: string;
  applicant_first_name: string;
  applicant_last_name: string;
  applicant_other_names?: string;
  date_of_birth: string; // YYYY-MM-DD
  gender: "male" | "female";
  nationality?: string;
  target_class_id: string;
  previous_school?: string;
  medical_info?: string;
  custom_fields: Record<string, unknown>;
  guardians: GuardianSubmit[];
  turnstile_token: string;
}

export interface ApplicationSubmitResponse {
  tracking_code: string;
  application_id: string;
  status: string;
  message: string;
  payment_required: boolean;
  application_fee_amount?: number;
}

export interface ApplicationStatusCheck {
  status: ApplicationStatus;
  applicant_first_name: string;
  submitted_at?: string;
  last_updated_at: string;
}

export interface DocumentUploadData {
  document_type: string;
  file_name: string;
  mime_type: string;
  file_size: number;
}

export interface DocumentUploadResponse {
  document_id: string;
  upload_url: string;
  s3_key: string;
  expires_in: number;
}

export interface PaymentInitiateData {
  callback_url: string;
  payment_method?: "mobile_money" | "card";
}

export interface PaymentInitiateResponse {
  payment_id: string;
  authorization_url: string;
  access_code: string;
  reference: string;
  amount: number;
  currency: string;
}

// =========================
// Admin Types
// =========================

export interface AdmissionPeriod {
  id: string;
  tenant_id: string;
  school_id: string;
  academic_year_id: string;
  name: string;
  description?: string;
  start_date: string;
  end_date: string;
  status: AdmissionPeriodStatus;
  application_fee_amount?: number;
  application_fee_required: boolean;
  entrance_exam_required: boolean;
  max_applications?: number;
  target_classes: string[];
  application_count?: number;
  created_at: string;
  updated_at: string;
}

export interface AdmissionPeriodCreate {
  name: string;
  description?: string;
  academic_year_id: string;
  start_date: string;
  end_date: string;
  application_fee_amount?: number;
  application_fee_required?: boolean;
  entrance_exam_required?: boolean;
  max_applications?: number;
  target_classes?: string[];
}

export interface AdmissionPeriodUpdate {
  name?: string;
  description?: string;
  start_date?: string;
  end_date?: string;
  application_fee_amount?: number;
  application_fee_required?: boolean;
  entrance_exam_required?: boolean;
  max_applications?: number;
  target_classes?: string[];
}

export interface AdmissionPeriodListResponse {
  items: AdmissionPeriod[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface FormConfig {
  id: string;
  admission_period_id: string;
  form_schema: Record<string, unknown>;
  required_documents: string[];
  created_at: string;
  updated_at: string;
}

export interface FormConfigUpdate {
  form_schema: Record<string, unknown>;
  required_documents: string[];
}

export interface ApplicationGuardianInfo {
  id: string;
  first_name: string;
  last_name: string;
  phone: string;
  email?: string;
  relationship: string;
  is_primary: boolean;
  occupation?: string;
  address?: string;
}

export interface ApplicationDocument {
  id: string;
  document_type: string;
  file_name: string;
  s3_key: string;
  file_size: number;
  mime_type: string;
  download_url?: string;
  created_at: string;
}

export interface ApplicationPayment {
  id: string;
  amount: number;
  currency: string;
  payment_method?: string;
  provider_reference?: string;
  status: string;
  paid_at?: string;
  created_at: string;
}

export interface ApplicationNote {
  id: string;
  author_id: string;
  author_name?: string;
  content: string;
  is_internal: boolean;
  created_at: string;
}

export interface StatusHistoryEntry {
  id: string;
  from_status?: string;
  to_status: string;
  changed_by?: string;
  changed_by_name?: string;
  reason?: string;
  created_at: string;
}

export interface ExamResult {
  id: string;
  entrance_exam_id: string;
  application_id: string;
  applicant_name?: string;
  score: number;
  max_score: number;
  grade?: string;
  passed: boolean;
  remarks?: string;
  scored_by?: string;
  created_at: string;
}

export interface AdmissionDecision {
  id: string;
  application_id: string;
  decision_type: DecisionType;
  decided_by: string;
  decided_by_name?: string;
  offered_class_id?: string;
  offered_class_name?: string;
  conditions?: string;
  decision_date: string;
  response_deadline?: string;
  decision_letter_url?: string;
  created_at: string;
}

export interface ApplicationDetail {
  id: string;
  tenant_id: string;
  school_id: string;
  admission_period_id: string;
  tracking_code: string;
  applicant_first_name: string;
  applicant_last_name: string;
  applicant_other_names?: string;
  date_of_birth: string;
  gender: string;
  nationality?: string;
  target_class_id: string;
  target_class_name?: string;
  status: ApplicationStatus;
  custom_fields: Record<string, unknown>;
  fee_waived: boolean;
  exam_waived: boolean;
  converted_student_id?: string;
  applicant_photo_url?: string;
  previous_school?: string;
  medical_info?: string;
  submitted_at?: string;
  created_at: string;
  updated_at: string;
  guardians: ApplicationGuardianInfo[];
  documents: ApplicationDocument[];
  payments: ApplicationPayment[];
  notes: ApplicationNote[];
  status_history: StatusHistoryEntry[];
  exam_results: ExamResult[];
  decision?: AdmissionDecision;
}

export interface ApplicationListItem {
  id: string;
  tracking_code: string;
  applicant_first_name: string;
  applicant_last_name: string;
  date_of_birth: string;
  gender: string;
  target_class_name?: string;
  status: ApplicationStatus;
  fee_waived: boolean;
  exam_waived: boolean;
  submitted_at?: string;
  created_at: string;
}

export interface ApplicationListResponse {
  items: ApplicationListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Entrance Exams
export interface EntranceExam {
  id: string;
  tenant_id: string;
  school_id: string;
  admission_period_id: string;
  name: string;
  exam_date: string;
  start_time?: string;
  end_time?: string;
  venue: string;
  capacity: number;
  status: EntranceExamStatus;
  instructions?: string;
  registered_count?: number;
  attended_count?: number;
  created_at: string;
  updated_at: string;
}

export interface EntranceExamCreate {
  admission_period_id: string;
  name: string;
  exam_date: string;
  start_time?: string;
  end_time?: string;
  venue: string;
  capacity: number;
  instructions?: string;
}

export interface EntranceExamListResponse {
  items: EntranceExam[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Decisions
export interface DecisionCreate {
  application_id: string;
  decision_type: DecisionType;
  offered_class_id?: string;
  conditions?: string;
  response_deadline?: string;
}

export interface BulkDecisionRequest {
  application_ids: string[];
  decision_type: DecisionType;
  offered_class_id?: string;
  conditions?: string;
  response_deadline?: string;
}

export interface BulkDecisionResponse {
  succeeded: Array<{ application_id: string; decision_id: string }>;
  failed: Array<{ application_id: string; error: string }>;
  total_succeeded: number;
  total_failed: number;
}

// Enrollment
export interface EnrollRequest {
  generate_invoice?: boolean;
  class_section_id?: string;
}

export interface EnrollResponse {
  application_id: string;
  student_id: string;
  student_number: string;
  guardian_ids: string[];
  invoice_id?: string;
  parent_account_created: boolean;
  message: string;
}

export interface BulkEnrollRequest {
  application_ids: string[];
  generate_invoice?: boolean;
}

export interface BulkEnrollResponse {
  succeeded: EnrollResponse[];
  failed: Array<{ application_id: string; error: string }>;
  total_succeeded: number;
  total_failed: number;
}

// Class Promotion
export interface ClassPromotion {
  id: string;
  tenant_id: string;
  school_id: string;
  source_academic_year_id: string;
  source_academic_year_name?: string;
  target_academic_year_id: string;
  target_academic_year_name?: string;
  name: string;
  status: string; // draft, preview, in_progress, completed, failed
  total_students: number;
  promoted_count: number;
  repeated_count: number;
  graduated_count: number;
  withdrawn_count: number;
  executed_at?: string;
  executed_by?: string;
  executed_by_name?: string;
  created_at: string;
  updated_at: string;
}

export interface ClassPromotionCreate {
  source_academic_year_id: string;
  target_academic_year_id: string;
  name: string;
}

export interface ClassPromotionListResponse {
  items: ClassPromotion[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ClassPromotionEntry {
  id: string;
  promotion_id: string;
  student_id: string;
  student_name?: string;
  student_number?: string;
  source_class_id: string;
  source_class_name?: string;
  source_section_id?: string;
  source_section_name?: string;
  target_class_id?: string;
  target_class_name?: string;
  target_section_id?: string;
  target_section_name?: string;
  action: string; // promote, repeat, graduate, withdraw
  reason?: string;
  processed: boolean;
}

export interface ClassPromotionEntryListResponse {
  items: ClassPromotionEntry[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface PromotionEntryUpdate {
  action: string;
  target_class_id?: string;
  target_section_id?: string;
  reason?: string;
}

// Return Intent Survey (optional)
export interface ReturnIntentCampaign {
  id: string;
  tenant_id: string;
  school_id: string;
  academic_year_id: string;
  name: string;
  target_classes: string[];
  message_template?: string;
  status: string; // draft, sent, completed
  sent_at?: string;
  sent_count: number;
  deadline?: string;
  total_students?: number;
  returning_count?: number;
  not_returning_count?: number;
  undecided_count?: number;
  pending_count?: number;
  created_at: string;
  updated_at: string;
}

export interface ReturnIntentCampaignCreate {
  name: string;
  academic_year_id: string;
  target_classes: string[];
  message_template?: string;
  deadline?: string;
}

export interface ReturnIntentCampaignListResponse {
  items: ReturnIntentCampaign[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ReturnIntentRecord {
  id: string;
  student_id: string;
  student_name?: string;
  current_class_name?: string;
  intent: string; // pending, returning, not_returning, undecided
  responded_at?: string;
  responded_by?: string;
  reason?: string;
}

// Dashboard
export interface DashboardStats {
  total_applications: number;
  by_status: Record<string, number>;
  by_class: Array<{ class_name: string; count: number }>;
  by_period: Array<{ period_name: string; count: number }>;
  conversion_rate?: number;
  pending_decisions: number;
  pending_enrollment: number;
  recent_applications: ApplicationListItem[];
}

export interface DemographicsData {
  by_gender: Record<string, number>;
  by_nationality: Array<{ nationality: string; count: number }>;
  by_previous_school: Array<{ school: string; count: number }>;
  age_distribution: Array<{ age_range: string; count: number }>;
}
```

---

## 4.2 Server Actions (Public Endpoints)

**File:** `frontend/actions/admissions.action.ts`

This file covers both public and admin actions. Public actions do **not** send auth tokens — they use subdomain-based tenant resolution only.

```typescript
"use server";

import { apiGet, apiPost, apiPut } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  PublicPeriodListResponse,
  PublicFormConfig,
  ApplicationSubmitData,
  ApplicationSubmitResponse,
  ApplicationStatusCheck,
  DocumentUploadData,
  DocumentUploadResponse,
  PaymentInitiateData,
  PaymentInitiateResponse,
  // Admin types (used by admin pages, imported later)
  AdmissionPeriod,
  AdmissionPeriodCreate,
  AdmissionPeriodUpdate,
  AdmissionPeriodListResponse,
  FormConfig,
  FormConfigUpdate,
  ApplicationDetail,
  ApplicationListResponse,
  EntranceExam,
  EntranceExamCreate,
  EntranceExamListResponse,
  AdmissionDecision,
  DecisionCreate,
  BulkDecisionRequest,
  BulkDecisionResponse,
  EnrollRequest,
  EnrollResponse,
  BulkEnrollRequest,
  BulkEnrollResponse,
  ClassPromotion,
  ClassPromotionCreate,
  ClassPromotionListResponse,
  ClassPromotionEntry,
  ClassPromotionEntryListResponse,
  PromotionEntryUpdate,
  ReturnIntentCampaign,
  ReturnIntentCampaignCreate,
  ReturnIntentCampaignListResponse,
  ReturnIntentRecord,
  DashboardStats,
  DemographicsData,
} from "@/types/admissions.type";

const PUBLIC_BASE = "/admissions/public";
const ADMIN_BASE = "/admissions";

// =========================
// Public Actions (No Auth)
// =========================

/**
 * Fetch open admission periods with school branding.
 * No auth token needed — tenant resolved from subdomain.
 */
export async function getPublicPeriods(): Promise<ActionResult<PublicPeriodListResponse>> {
  try {
    const response = await apiGet<PublicPeriodListResponse>(
      `${PUBLIC_BASE}/periods`,
      { noAuth: true }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch admission periods",
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
    const response = await apiGet<PublicFormConfig>(
      `${PUBLIC_BASE}/periods/${periodId}/form`,
      { noAuth: true }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch form configuration",
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
    const response = await apiPost<ApplicationSubmitResponse>(
      `${PUBLIC_BASE}/applications`,
      data,
      { noAuth: true }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to submit application",
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
    const response = await apiGet<ApplicationStatusCheck>(
      `${PUBLIC_BASE}/applications/${trackingCode}/status`,
      { noAuth: true }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to check application status",
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
    const response = await apiPost<DocumentUploadResponse>(
      `${PUBLIC_BASE}/applications/${trackingCode}/documents`,
      data,
      { noAuth: true }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to prepare document upload",
    };
  }
}

/**
 * Initiate application fee payment.
 */
export async function initiatePayment(
  trackingCode: string,
  data: PaymentInitiateData
): Promise<ActionResult<PaymentInitiateResponse>> {
  try {
    const response = await apiPost<PaymentInitiateResponse>(
      `${PUBLIC_BASE}/applications/${trackingCode}/pay`,
      data,
      { noAuth: true }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to initiate payment",
    };
  }
}

// =========================
// Admin Actions (Authenticated)
// =========================
// These actions use getValidAccessToken() and send Authorization header.
// They are called by admin dashboard pages.

// --- Periods ---
export async function createAdmissionPeriod(
  data: AdmissionPeriodCreate
): Promise<ActionResult<AdmissionPeriod>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPost<AdmissionPeriod>(
      `${ADMIN_BASE}/periods`, data, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to create period" };
  }
}

export async function getAdmissionPeriods(params?: {
  page?: number; page_size?: number; status?: string; academic_year_id?: string;
}): Promise<ActionResult<AdmissionPeriodListResponse>> {
  try {
    const token = await getValidAccessToken();
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    if (params?.status) query.set("status", params.status);
    if (params?.academic_year_id) query.set("academic_year_id", params.academic_year_id);
    const response = await apiGet<AdmissionPeriodListResponse>(
      `${ADMIN_BASE}/periods?${query}`, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch periods" };
  }
}

export async function updateAdmissionPeriod(
  periodId: string, data: AdmissionPeriodUpdate
): Promise<ActionResult<AdmissionPeriod>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPut<AdmissionPeriod>(
      `${ADMIN_BASE}/periods/${periodId}`, data, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to update period" };
  }
}

export async function changeAdmissionPeriodStatus(
  periodId: string, status: string
): Promise<ActionResult<AdmissionPeriod>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPut<AdmissionPeriod>(
      `${ADMIN_BASE}/periods/${periodId}/status`, { status }, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to update status" };
  }
}

export async function updateFormConfig(
  periodId: string, data: FormConfigUpdate
): Promise<ActionResult<FormConfig>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPut<FormConfig>(
      `${ADMIN_BASE}/periods/${periodId}/form-config`, data, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to update form config" };
  }
}

// --- Applications ---
export async function getApplications(params?: {
  page?: number; page_size?: number; status?: string;
  admission_period_id?: string; target_class_id?: string;
  search?: string; sort_by?: string; sort_order?: string;
}): Promise<ActionResult<ApplicationListResponse>> {
  try {
    const token = await getValidAccessToken();
    const query = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => { if (v) query.set(k, String(v)); });
    }
    const response = await apiGet<ApplicationListResponse>(
      `${ADMIN_BASE}/applications?${query}`, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch applications" };
  }
}

export async function getApplicationDetail(
  applicationId: string
): Promise<ActionResult<ApplicationDetail>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiGet<ApplicationDetail>(
      `${ADMIN_BASE}/applications/${applicationId}`, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch application" };
  }
}

export async function changeApplicationStatus(
  applicationId: string, status: string, reason?: string
): Promise<ActionResult<ApplicationDetail>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPut<ApplicationDetail>(
      `${ADMIN_BASE}/applications/${applicationId}/status`,
      { status, reason }, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to update status" };
  }
}

export async function addApplicationNote(
  applicationId: string, content: string, is_internal?: boolean
): Promise<ActionResult<{ id: string }>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPost<{ id: string }>(
      `${ADMIN_BASE}/applications/${applicationId}/notes`,
      { content, is_internal: is_internal ?? true }, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to add note" };
  }
}

export async function waiveApplicationFee(
  applicationId: string, reason: string
): Promise<ActionResult<ApplicationDetail>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPut<ApplicationDetail>(
      `${ADMIN_BASE}/applications/${applicationId}/waive-fee`,
      { reason }, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to waive fee" };
  }
}

export async function waiveApplicationExam(
  applicationId: string, reason: string
): Promise<ActionResult<ApplicationDetail>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPut<ApplicationDetail>(
      `${ADMIN_BASE}/applications/${applicationId}/waive-exam`,
      { reason }, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to waive exam" };
  }
}

// --- Decisions ---
export async function makeDecision(
  data: DecisionCreate
): Promise<ActionResult<AdmissionDecision>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPost<AdmissionDecision>(
      `${ADMIN_BASE}/decisions`, data, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to make decision" };
  }
}

export async function bulkDecision(
  data: BulkDecisionRequest
): Promise<ActionResult<BulkDecisionResponse>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPost<BulkDecisionResponse>(
      `${ADMIN_BASE}/decisions/bulk`, data, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to process decisions" };
  }
}

// --- Enrollment ---
export async function enrollApplicant(
  applicationId: string, data?: EnrollRequest
): Promise<ActionResult<EnrollResponse>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPost<EnrollResponse>(
      `${ADMIN_BASE}/applications/${applicationId}/enroll`,
      data ?? { generate_invoice: true }, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to enroll applicant" };
  }
}

export async function bulkEnroll(
  data: BulkEnrollRequest
): Promise<ActionResult<BulkEnrollResponse>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPost<BulkEnrollResponse>(
      `${ADMIN_BASE}/enroll/bulk`, data, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to process enrollments" };
  }
}

// --- Class Promotion ---
export async function createPromotionBatch(
  data: ClassPromotionCreate
): Promise<ActionResult<ClassPromotion>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPost<ClassPromotion>(
      `${ADMIN_BASE}/promotions`, data, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to create promotion batch" };
  }
}

export async function getPromotionBatches(params?: {
  page?: number; page_size?: number;
}): Promise<ActionResult<ClassPromotionListResponse>> {
  try {
    const token = await getValidAccessToken();
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    const response = await apiGet<ClassPromotionListResponse>(
      `${ADMIN_BASE}/promotions?${query}`, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch promotion batches" };
  }
}

export async function generatePromotionPreview(
  promotionId: string
): Promise<ActionResult<ClassPromotion>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPost<ClassPromotion>(
      `${ADMIN_BASE}/promotions/${promotionId}/preview`, {}, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to generate preview" };
  }
}

export async function getPromotionEntries(
  promotionId: string, params?: { source_class_id?: string; action?: string; page?: number; page_size?: number; }
): Promise<ActionResult<ClassPromotionEntryListResponse>> {
  try {
    const token = await getValidAccessToken();
    const query = new URLSearchParams();
    if (params?.source_class_id) query.set("source_class_id", params.source_class_id);
    if (params?.action) query.set("action", params.action);
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    const response = await apiGet<ClassPromotionEntryListResponse>(
      `${ADMIN_BASE}/promotions/${promotionId}/entries?${query}`, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch entries" };
  }
}

export async function updatePromotionEntry(
  entryId: string, data: PromotionEntryUpdate
): Promise<ActionResult<ClassPromotionEntry>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPut<ClassPromotionEntry>(
      `${ADMIN_BASE}/promotions/entries/${entryId}`, data, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to update entry" };
  }
}

export async function executePromotionBatch(
  promotionId: string
): Promise<ActionResult<ClassPromotion>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPost<ClassPromotion>(
      `${ADMIN_BASE}/promotions/${promotionId}/execute`, {}, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to execute promotion" };
  }
}

// --- Return Intent Survey (optional) ---
export async function createReturnIntentCampaign(
  data: ReturnIntentCampaignCreate
): Promise<ActionResult<ReturnIntentCampaign>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPost<ReturnIntentCampaign>(
      `${ADMIN_BASE}/return-intents/campaigns`, data, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to create campaign" };
  }
}

export async function getReturnIntentCampaigns(params?: {
  page?: number; page_size?: number;
}): Promise<ActionResult<ReturnIntentCampaignListResponse>> {
  try {
    const token = await getValidAccessToken();
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    const response = await apiGet<ReturnIntentCampaignListResponse>(
      `${ADMIN_BASE}/return-intents/campaigns?${query}`, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch campaigns" };
  }
}

export async function sendReturnIntentCampaign(
  campaignId: string
): Promise<ActionResult<ReturnIntentCampaign>> {
  try {
    const token = await getValidAccessToken();
    const response = await apiPost<ReturnIntentCampaign>(
      `${ADMIN_BASE}/return-intents/campaigns/${campaignId}/send`, {}, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to send campaign" };
  }
}

// --- Dashboard ---
export async function getAdmissionsDashboard(
  admissionPeriodId?: string
): Promise<ActionResult<DashboardStats>> {
  try {
    const token = await getValidAccessToken();
    const query = admissionPeriodId ? `?admission_period_id=${admissionPeriodId}` : "";
    const response = await apiGet<DashboardStats>(
      `${ADMIN_BASE}/dashboard/stats${query}`, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch dashboard" };
  }
}

export async function getAdmissionsDemographics(
  admissionPeriodId?: string
): Promise<ActionResult<DemographicsData>> {
  try {
    const token = await getValidAccessToken();
    const query = admissionPeriodId ? `?admission_period_id=${admissionPeriodId}` : "";
    const response = await apiGet<DemographicsData>(
      `${ADMIN_BASE}/dashboard/demographics${query}`, { token }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch demographics" };
  }
}
```

**Note on `noAuth` option:** The `apiGet`/`apiPost` helpers in `lib/api.ts` need to support an optional `noAuth: true` flag that skips the Authorization header. If this doesn't exist, add it:

```typescript
// In lib/api.ts, modify the fetch wrapper to check for noAuth option
interface FetchOptions {
  token?: string;
  noAuth?: boolean;
}

// In the fetch call: skip Authorization header if noAuth is true
```

---

## 4.3 Branded Layout

**File:** `frontend/app/(auth)/apply/layout.tsx`

The public application form uses the existing `(auth)` route group which wraps content in `TenantProvider`. The apply layout adds school branding (logo, colors) fetched from the public school-info endpoint.

```tsx
/**
 * SIMS Plus - Public Application Form Layout
 *
 * Branded layout for the admissions portal.
 * Fetches school branding from public API (no auth needed).
 * Uses TenantProvider from parent (auth) layout.
 */

import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";

export default function ApplyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-muted/30">
      <Suspense fallback={<Skeleton className="h-screen w-full" />}>
        {children}
      </Suspense>
    </div>
  );
}
```

---

## 4.4 Landing Page

**File:** `frontend/app/(auth)/apply/page.tsx`

Lists open admission periods for the current school with school branding.

```tsx
/**
 * SIMS Plus - Admissions Landing Page
 *
 * Displays open admission periods for prospective parents.
 * Path: {school}.simsplus.io/apply
 */

import Link from "next/link";
import { getPublicPeriods } from "@/actions/admissions.action";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CalendarDays, GraduationCap } from "lucide-react";

export default async function ApplyPage() {
  const result = await getPublicPeriods();

  if (!result.success) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6 text-center">
            <p className="text-muted-foreground">Unable to load admissions information.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { items: periods, school } = result.data;

  return (
    <div className="container mx-auto max-w-4xl px-4 py-8">
      {/* School Header */}
      <div className="text-center mb-8">
        {school.logo_url && (
          <img
            src={school.logo_url}
            alt={school.school_name}
            className="h-20 w-20 mx-auto mb-4 rounded-full object-cover"
          />
        )}
        <h1 className="text-3xl font-bold">{school.school_name}</h1>
        {school.motto && (
          <p className="text-muted-foreground mt-1 italic">{school.motto}</p>
        )}
        <p className="text-lg mt-4">Admissions Portal</p>
      </div>

      {/* Open Periods */}
      {periods.length === 0 ? (
        <Card>
          <CardContent className="pt-6 text-center">
            <GraduationCap className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-lg font-medium">No Open Admissions</p>
            <p className="text-muted-foreground mt-2">
              There are no admission periods currently open. Please check back later.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Open Admissions</h2>
          {periods.map((period) => (
            <Card key={period.id} className="hover:border-primary/50 transition-colors">
              <CardHeader>
                <CardTitle>{period.name}</CardTitle>
                {period.description && (
                  <CardDescription>{period.description}</CardDescription>
                )}
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-4 mb-4">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <CalendarDays className="h-4 w-4" />
                    <span>
                      {new Date(period.start_date).toLocaleDateString("en-GB")} —{" "}
                      {new Date(period.end_date).toLocaleDateString("en-GB")}
                    </span>
                  </div>
                  {period.application_fee_required && period.application_fee_amount && (
                    <Badge variant="secondary">
                      Application Fee: GHS {period.application_fee_amount.toFixed(2)}
                    </Badge>
                  )}
                  {period.entrance_exam_required && (
                    <Badge variant="outline">Entrance Exam Required</Badge>
                  )}
                </div>
                <div className="flex flex-wrap gap-2 mb-4">
                  {period.target_classes.map((cls) => (
                    <Badge key={cls.id} variant="outline">{cls.name}</Badge>
                  ))}
                </div>
                <Link href={`/apply/${period.id}`}>
                  <Button className="w-full sm:w-auto">Apply Now</Button>
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Status Check Link */}
      <div className="text-center mt-8">
        <p className="text-sm text-muted-foreground">
          Already applied?{" "}
          <Link href="/apply/status" className="text-primary underline">
            Check your application status
          </Link>
        </p>
      </div>

      {/* School Contact */}
      {(school.phone || school.email) && (
        <div className="text-center mt-4 text-sm text-muted-foreground">
          <p>
            Contact: {school.phone && <span>{school.phone}</span>}
            {school.phone && school.email && " | "}
            {school.email && <span>{school.email}</span>}
          </p>
        </div>
      )}
    </div>
  );
}
```

---

## 4.5 Multi-Step Application Form

**File:** `frontend/app/(auth)/apply/[periodId]/page.tsx`

This is the most complex frontend component. It's a 4-step wizard:
1. **Personal Info** — Name, DOB, gender, nationality, target class, previous school, medical, custom fields
2. **Guardian Info** — 1-5 guardians with name, phone, email, relationship
3. **Documents** — Upload required documents (presigned S3 URLs)
4. **Review & Pay** — Review all info, submit, then pay if required

```tsx
/**
 * SIMS Plus - Multi-Step Application Form
 *
 * Path: {school}.simsplus.io/apply/{periodId}
 *
 * 4-step wizard:
 * 1. Personal Information (+ custom fields from form_schema)
 * 2. Guardian Information (1-5 guardians)
 * 3. Document Upload (presigned S3 URLs)
 * 4. Review & Submit (+ payment if required)
 *
 * Key integration points:
 * - Cloudflare Turnstile for bot protection
 * - Dynamic form fields from JSON Schema (form_schema)
 * - Direct S3 upload via presigned URLs
 * - Paystack redirect for payment
 */

"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";

import {
  getPublicFormConfig,
  submitApplication,
  requestDocumentUpload,
  initiatePayment,
} from "@/actions/admissions.action";
import type { PublicFormConfig, ApplicationSubmitResponse } from "@/types/admissions.type";

// Zod schema for step 1 (personal info)
const personalInfoSchema = z.object({
  applicant_first_name: z.string().min(1, "First name is required").max(100),
  applicant_last_name: z.string().min(1, "Last name is required").max(100),
  applicant_other_names: z.string().max(100).optional(),
  date_of_birth: z.string().min(1, "Date of birth is required"),
  gender: z.enum(["male", "female"], { required_error: "Gender is required" }),
  nationality: z.string().max(100).optional(),
  target_class_id: z.string().min(1, "Target class is required"),
  previous_school: z.string().max(255).optional(),
  medical_info: z.string().optional(),
});

// Zod schema for step 2 (guardian info)
const guardianSchema = z.object({
  first_name: z.string().min(1, "First name is required").max(100),
  last_name: z.string().min(1, "Last name is required").max(100),
  phone: z.string().min(10, "Valid phone number required").max(20),
  email: z.string().email("Valid email required").optional().or(z.literal("")),
  relationship: z.enum(["father", "mother", "guardian", "other"]),
  is_primary: z.boolean(),
  occupation: z.string().max(255).optional(),
  address: z.string().optional(),
});

const guardiansSchema = z.object({
  guardians: z.array(guardianSchema).min(1, "At least one guardian required").max(5),
});

// Steps: ["Personal Info", "Guardian Info", "Documents", "Review & Submit"]
const STEPS = [
  { id: 1, title: "Personal Information", description: "Applicant details" },
  { id: 2, title: "Guardian Information", description: "Parent/guardian contacts" },
  { id: 3, title: "Documents", description: "Upload required documents" },
  { id: 4, title: "Review & Submit", description: "Confirm and submit" },
];

export default function ApplicationFormPage() {
  const params = useParams();
  const router = useRouter();
  const periodId = params.periodId as string;

  const [currentStep, setCurrentStep] = useState(1);
  const [formConfig, setFormConfig] = useState<PublicFormConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<ApplicationSubmitResponse | null>(null);
  const [uploadedDocs, setUploadedDocs] = useState<Array<{ type: string; name: string }>>([]);
  const [customFieldValues, setCustomFieldValues] = useState<Record<string, unknown>>({});

  // Step 1 form
  const personalForm = useForm({
    resolver: zodResolver(personalInfoSchema),
    defaultValues: {
      applicant_first_name: "",
      applicant_last_name: "",
      applicant_other_names: "",
      date_of_birth: "",
      gender: "" as "male" | "female",
      nationality: "Ghanaian",
      target_class_id: "",
      previous_school: "",
      medical_info: "",
    },
  });

  // Step 2 form
  const guardianForm = useForm({
    resolver: zodResolver(guardiansSchema),
    defaultValues: {
      guardians: [
        {
          first_name: "",
          last_name: "",
          phone: "",
          email: "",
          relationship: "father" as const,
          is_primary: true,
          occupation: "",
          address: "",
        },
      ],
    },
  });

  const { fields, append, remove } = useFieldArray({
    control: guardianForm.control,
    name: "guardians",
  });

  useEffect(() => {
    async function loadFormConfig() {
      const result = await getPublicFormConfig(periodId);
      if (result.success) {
        setFormConfig(result.data);
      } else {
        toast.error("Failed to load application form");
        router.push("/apply");
      }
      setLoading(false);
    }
    loadFormConfig();
  }, [periodId, router]);

  async function handleSubmit() {
    // This function handles the final submission in Step 4
    // It includes Turnstile token verification
    setSubmitting(true);

    try {
      // Get Turnstile token from the widget
      const turnstileToken = (window as any).turnstile?.getResponse?.() || "";
      if (!turnstileToken) {
        toast.error("Please complete the security check");
        setSubmitting(false);
        return;
      }

      const personalData = personalForm.getValues();
      const guardianData = guardianForm.getValues();

      const result = await submitApplication({
        admission_period_id: periodId,
        ...personalData,
        custom_fields: customFieldValues,
        guardians: guardianData.guardians.map((g) => ({
          ...g,
          email: g.email || undefined,
        })),
        turnstile_token: turnstileToken,
      });

      if (result.success) {
        setSubmitResult(result.data);
        toast.success("Application submitted successfully!");

        // If payment required, redirect to Paystack
        if (result.data.payment_required) {
          const payResult = await initiatePayment(result.data.tracking_code, {
            callback_url: `${window.location.origin}/apply/pay/callback`,
          });
          if (payResult.success) {
            window.location.href = payResult.data.authorization_url;
            return;
          }
          toast.error("Payment initiation failed. You can pay later using your tracking code.");
        }
      } else {
        toast.error(result.error || "Failed to submit application");
      }
    } catch {
      toast.error("An error occurred. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="container mx-auto max-w-3xl px-4 py-8">
        <Card>
          <CardContent className="pt-6">
            <div className="animate-pulse space-y-4">
              <div className="h-8 bg-muted rounded w-1/3" />
              <div className="h-4 bg-muted rounded w-2/3" />
              <div className="h-64 bg-muted rounded" />
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (submitResult && !submitResult.payment_required) {
    // Success page — show tracking code
    return (
      <div className="container mx-auto max-w-md px-4 py-8">
        <Card>
          <CardHeader className="text-center">
            <CardTitle className="text-green-600">Application Submitted!</CardTitle>
          </CardHeader>
          <CardContent className="text-center space-y-4">
            <p>Your application has been received.</p>
            <div className="bg-muted p-4 rounded-lg">
              <p className="text-sm text-muted-foreground">Your tracking code:</p>
              <p className="text-2xl font-mono font-bold mt-1">
                {submitResult.tracking_code}
              </p>
            </div>
            <p className="text-sm text-muted-foreground">
              Save this tracking code to check your application status.
            </p>
            <Button variant="outline" onClick={() => router.push("/apply/status")}>
              Check Status
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-2xl font-bold mb-2">{formConfig?.period_name}</h1>

      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-8 overflow-x-auto">
        {STEPS.map((step) => (
          <div
            key={step.id}
            className={`flex items-center gap-2 ${
              step.id === currentStep
                ? "text-primary font-medium"
                : step.id < currentStep
                ? "text-muted-foreground"
                : "text-muted-foreground/50"
            }`}
          >
            <div
              className={`h-8 w-8 rounded-full flex items-center justify-center text-sm ${
                step.id === currentStep
                  ? "bg-primary text-primary-foreground"
                  : step.id < currentStep
                  ? "bg-primary/20 text-primary"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {step.id < currentStep ? "✓" : step.id}
            </div>
            <span className="hidden sm:inline text-sm">{step.title}</span>
            {step.id < STEPS.length && (
              <Separator className="w-8 hidden sm:block" />
            )}
          </div>
        ))}
      </div>

      {/* Step content rendered conditionally */}
      {/* Step 1: Personal Info */}
      {/* Step 2: Guardian Info (useFieldArray for 1-5 guardians) */}
      {/* Step 3: Documents (presigned upload) */}
      {/* Step 4: Review + Turnstile + Submit */}

      {/*
        IMPLEMENTATION NOTES FOR DEVELOPERS:

        Step 1: Render personalForm fields + dynamic custom fields from formConfig.form_schema.
                The form_schema is a JSON Schema — iterate its properties to render inputs.
                Use input types based on schema field type (string→Input, boolean→Checkbox, etc.)

        Step 2: Render guardian fields with useFieldArray.
                "Add Guardian" button (max 5). "Remove" button (min 1).
                First guardian defaults to is_primary=true.

        Step 3: For each entry in formConfig.required_documents:
                - Show file input (accept=".pdf,.jpg,.jpeg,.png")
                - On file select: call requestDocumentUpload() to get presigned URL
                - Upload file directly to S3 using fetch(uploadUrl, {method:'PUT', body:file})
                - Track uploaded docs in uploadedDocs state

        Step 4: Show read-only summary of all data.
                Include Cloudflare Turnstile widget:
                  <div id="turnstile-container"></div>
                  Load script: <Script src="https://challenges.cloudflare.com/turnstile/v0/api.js" />
                  Render widget: turnstile.render('#turnstile-container', {
                    sitekey: process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY,
                  })
                Submit button calls handleSubmit().
      */}

      {/* Navigation buttons */}
      <div className="flex justify-between mt-8">
        <Button
          variant="outline"
          onClick={() => setCurrentStep((s) => Math.max(1, s - 1))}
          disabled={currentStep === 1}
        >
          Previous
        </Button>
        {currentStep < 4 ? (
          <Button
            onClick={async () => {
              // Validate current step before proceeding
              if (currentStep === 1) {
                const valid = await personalForm.trigger();
                if (!valid) return;
              } else if (currentStep === 2) {
                const valid = await guardianForm.trigger();
                if (!valid) return;
              }
              setCurrentStep((s) => s + 1);
            }}
          >
            Next
          </Button>
        ) : (
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Submitting..." : "Submit Application"}
          </Button>
        )}
      </div>
    </div>
  );
}
```

### Cloudflare Turnstile Integration

Add the Turnstile site key to the frontend environment:

```env
# frontend/.env.local
NEXT_PUBLIC_TURNSTILE_SITE_KEY=0x4AAAAAAA...  # Get from Cloudflare dashboard
```

Load the Turnstile script in the application form page or layout:

```tsx
import Script from "next/script";

// In the Review step (Step 4):
<Script
  src="https://challenges.cloudflare.com/turnstile/v0/api.js"
  async
  defer
/>
<div
  className="cf-turnstile"
  data-sitekey={process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY}
/>
```

---

## 4.7 Status Check Page

**File:** `frontend/app/(auth)/apply/status/page.tsx`

```tsx
/**
 * SIMS Plus - Application Status Check
 *
 * Path: {school}.simsplus.io/apply/status
 * Allows applicants to check their application status using tracking code.
 */

"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApplicationStatusBadge } from "@/components/admissions/application-status-badge";

import { checkApplicationStatus } from "@/actions/admissions.action";
import type { ApplicationStatusCheck } from "@/types/admissions.type";

export default function StatusCheckPage() {
  const [trackingCode, setTrackingCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ApplicationStatusCheck | null>(null);

  async function handleCheck() {
    if (!trackingCode.trim()) {
      toast.error("Please enter your tracking code");
      return;
    }

    setLoading(true);
    const response = await checkApplicationStatus(trackingCode.trim());

    if (response.success) {
      setResult(response.data);
    } else {
      toast.error(response.error || "Application not found");
      setResult(null);
    }
    setLoading(false);
  }

  return (
    <div className="container mx-auto max-w-md px-4 py-8">
      <Card>
        <CardHeader className="text-center">
          <CardTitle>Check Application Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="tracking-code">Tracking Code</Label>
            <Input
              id="tracking-code"
              placeholder="Enter your tracking code"
              value={trackingCode}
              onChange={(e) => setTrackingCode(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCheck()}
            />
          </div>
          <Button onClick={handleCheck} disabled={loading} className="w-full">
            {loading ? "Checking..." : "Check Status"}
          </Button>

          {result && (
            <div className="mt-6 space-y-3 pt-4 border-t">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Applicant:</span>
                <span className="font-medium">{result.applicant_first_name}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Status:</span>
                <ApplicationStatusBadge status={result.status} />
              </div>
              {result.submitted_at && (
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Submitted:</span>
                  <span className="text-sm">
                    {new Date(result.submitted_at).toLocaleDateString("en-GB")}
                  </span>
                </div>
              )}
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Last Updated:</span>
                <span className="text-sm">
                  {new Date(result.last_updated_at).toLocaleDateString("en-GB")}
                </span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

---

## 4.8 Paystack Callback Page

**File:** `frontend/app/(auth)/apply/pay/callback/page.tsx`

```tsx
/**
 * SIMS Plus - Paystack Payment Callback
 *
 * Path: {school}.simsplus.io/apply/pay/callback
 * Paystack redirects here after payment. Shows payment result.
 */

"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";

export default function PaymentCallbackPage() {
  const searchParams = useSearchParams();
  const reference = searchParams.get("reference");
  const trxref = searchParams.get("trxref");
  const [status, setStatus] = useState<"loading" | "success" | "failed">("loading");

  useEffect(() => {
    // Payment verification happens via webhook (server-side).
    // The callback page simply shows a success message based on
    // the presence of the reference parameter.
    // The actual payment status is confirmed by the webhook handler.
    if (reference || trxref) {
      setStatus("success");
    } else {
      setStatus("failed");
    }
  }, [reference, trxref]);

  return (
    <div className="container mx-auto max-w-md px-4 py-8">
      <Card>
        <CardHeader className="text-center">
          <CardTitle>Payment Status</CardTitle>
        </CardHeader>
        <CardContent className="text-center space-y-4">
          {status === "loading" && (
            <>
              <Loader2 className="h-12 w-12 mx-auto animate-spin text-primary" />
              <p>Verifying payment...</p>
            </>
          )}

          {status === "success" && (
            <>
              <CheckCircle className="h-12 w-12 mx-auto text-green-600" />
              <p className="text-lg font-medium">Payment Received!</p>
              <p className="text-sm text-muted-foreground">
                Your application fee has been received. Your application is now being processed.
              </p>
              <p className="text-xs text-muted-foreground">Reference: {reference || trxref}</p>
              <Link href="/apply/status">
                <Button variant="outline" className="mt-4">Check Application Status</Button>
              </Link>
            </>
          )}

          {status === "failed" && (
            <>
              <XCircle className="h-12 w-12 mx-auto text-destructive" />
              <p className="text-lg font-medium">Payment Not Confirmed</p>
              <p className="text-sm text-muted-foreground">
                We could not confirm your payment. If you believe this is an error,
                please check your application status or contact the school.
              </p>
              <Link href="/apply/status">
                <Button variant="outline" className="mt-4">Check Application Status</Button>
              </Link>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

---

## 4.9 Application Status Badge Component

**File:** `frontend/components/admissions/application-status-badge.tsx`

```tsx
/**
 * SIMS Plus - Application Status Badge
 *
 * Color-coded badge for application status (14 statuses).
 * Used in both public status check and admin dashboard.
 */

import { Badge } from "@/components/ui/badge";
import type { ApplicationStatus } from "@/types/admissions.type";

const STATUS_CONFIG: Record<ApplicationStatus, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  draft: { label: "Draft", variant: "secondary" },
  submitted: { label: "Submitted", variant: "default" },
  under_review: { label: "Under Review", variant: "default" },
  shortlisted: { label: "Shortlisted", variant: "default" },
  exam_scheduled: { label: "Exam Scheduled", variant: "outline" },
  exam_completed: { label: "Exam Completed", variant: "outline" },
  offered: { label: "Offered", variant: "default" },
  accepted: { label: "Accepted", variant: "default" },
  waitlisted: { label: "Waitlisted", variant: "secondary" },
  rejected: { label: "Rejected", variant: "destructive" },
  enrolled: { label: "Enrolled", variant: "default" },
  withdrawn: { label: "Withdrawn", variant: "secondary" },
  expired: { label: "Expired", variant: "destructive" },
  deferred: { label: "Deferred", variant: "secondary" },
};

interface ApplicationStatusBadgeProps {
  status: ApplicationStatus | string;
}

export function ApplicationStatusBadge({ status }: ApplicationStatusBadgeProps) {
  const config = STATUS_CONFIG[status as ApplicationStatus] ?? {
    label: status.replace(/_/g, " "),
    variant: "outline" as const,
  };

  return (
    <Badge variant={config.variant} className="capitalize">
      {config.label}
    </Badge>
  );
}
```

---

## File Summary

| File | Type | Purpose |
|------|------|---------|
| `frontend/types/admissions.type.ts` | Types | All TypeScript interfaces for admissions |
| `frontend/actions/admissions.action.ts` | Server Actions | Public + admin API calls |
| `frontend/app/(auth)/apply/layout.tsx` | Layout | Branded wrapper for public form |
| `frontend/app/(auth)/apply/page.tsx` | Page (RSC) | Landing page — lists open periods |
| `frontend/app/(auth)/apply/[periodId]/page.tsx` | Page (Client) | Multi-step application form wizard |
| `frontend/app/(auth)/apply/status/page.tsx` | Page (Client) | Status check by tracking code |
| `frontend/app/(auth)/apply/pay/callback/page.tsx` | Page (Client) | Paystack payment callback |
| `frontend/components/admissions/application-status-badge.tsx` | Component | Reusable status badge |

### Environment Variables

```env
# frontend/.env.local
NEXT_PUBLIC_TURNSTILE_SITE_KEY=<cloudflare-turnstile-site-key>
```
