/**
 * SIMS Plus - Applicant Accounts Type Definitions
 *
 * Types for the applicant portal: registration, login, profile,
 * my-applications dashboard, draft management, and claim flow.
 */

import type {
  ApplicationStatus,
  ApplicationGuardianInfo,
  ApplicationDocument,
  ApplicationPayment,
  StatusHistoryEntry,
  AdmissionDecision,
} from "./admissions.type";

// =========================
// Applicant Profile
// =========================

export interface ApplicantProfile {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  email_verified: boolean;
  created_at: string;
}

// =========================
// Auth — Register / Login
// =========================

export interface ApplicantRegisterData {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  password: string;
  turnstile_token: string;
}

export interface ApplicantRegisterResponse {
  user_id: string;
  email: string;
  message: string;
}

export interface ApplicantLoginData {
  email: string;
  password: string;
}

export interface ApplicantLoginResponse {
  access_token: string;
  refresh_token: string;
  user: ApplicantProfile;
  token_type: string; // Always "bearer"
}

// =========================
// My Applications
// =========================

// Fields match backend MyApplicationListItem schema.
// Optional fields below may not be returned in the list response.
export interface MyApplicationListItem {
  id: string;
  tracking_code: string;
  admission_period_id: string;
  applicant_first_name: string;
  applicant_last_name: string;
  applicant_other_names?: string;
  date_of_birth?: string;
  gender?: string;
  target_class_id?: string;
  target_class_name?: string;
  admission_period_name?: string;
  status: ApplicationStatus;
  fee_waived?: boolean;
  submitted_at?: string;
  created_at: string;
  updated_at: string;
}

export interface MyApplicationListResponse {
  items: MyApplicationListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/**
 * Full application detail for the applicant view.
 * Matches backend MyApplicationDetailResponse schema.
 * Excludes admin-only fields (notes, exam_results, school_id, converted_student_id).
 */
export interface MyApplicationDetail {
  id: string;
  tenant_id: string;
  tracking_code: string;
  admission_period_id: string;
  admission_period_name?: string;
  applicant_first_name: string;
  applicant_last_name: string;
  applicant_other_names?: string;
  date_of_birth?: string;
  gender?: string;
  nationality?: string;
  target_class_id?: string;
  target_class_name?: string;
  status: ApplicationStatus;
  custom_fields: Record<string, unknown>;
  fee_waived: boolean;
  exam_waived: boolean;
  applicant_photo_url?: string;
  previous_school?: string;
  medical_info?: string;
  submitted_at?: string;
  created_at: string;
  updated_at: string;
  guardians: ApplicationGuardianInfo[];
  documents: ApplicationDocument[];
  payments: ApplicationPayment[];
  status_history: StatusHistoryEntry[];
  decision?: AdmissionDecision;
}

// =========================
// Draft Management
// =========================

export interface DraftApplicationData {
  admission_period_id: string;
  applicant_first_name: string;
  applicant_last_name: string;
  applicant_other_names?: string;
  date_of_birth?: string;   // Optional for partial drafts
  gender?: string;           // Optional for partial drafts
  nationality?: string;
  target_class_id?: string;  // Optional for partial drafts
  previous_school?: string;
  medical_info?: string;
  custom_fields?: Record<string, unknown>;
  guardians?: GuardianData[];
}

export interface GuardianData {
  first_name: string;
  last_name: string;
  phone: string;
  email?: string;
  relationship: "father" | "mother" | "guardian" | "other";
  is_primary: boolean;
  occupation?: string;
  address?: string;
}

export interface DraftCreateResponse {
  id: string;
  tracking_code: string;
  status: string;
  payment_required: boolean;
  application_fee_amount?: number;
}

// =========================
// Print View
// =========================

export interface PrintableApplicationResponse {
  id: string;
  tracking_code: string;
  school_name: string;
  school_logo_url?: string;
  admission_period_name: string;
  applicant_first_name: string;
  applicant_last_name: string;
  applicant_other_names?: string;
  date_of_birth?: string;
  gender?: string;
  nationality?: string;
  target_class_name?: string;
  status: string;
  previous_school?: string;
  medical_info?: string;
  custom_fields: Record<string, unknown>;
  submitted_at?: string;
  created_at: string;
  guardians: GuardianData[];
  documents: Array<{
    document_type: string;
    file_name: string;
    created_at: string;
  }>;
  payments: Array<{
    amount: number;
    currency: string;
    status: string;
    paid_at?: string;
  }>;
  decision?: {
    decision_type: string;
    offered_class_name?: string;
    conditions?: string;
    decision_date: string;
  };
  generated_at?: string;
}

// =========================
// Claim Flow
// =========================

export interface ClaimApplicationData {
  tracking_code: string;
}

export interface ClaimApplicationResponse {
  application_id: string;
  tracking_code: string;
  status: string;
  message: string;
}

// =========================
// Password
// =========================

export interface ChangePasswordData {
  current_password: string;
  new_password: string;
}
