/**
 * SIMS Plus - Admissions Portal Type Definitions
 *
 * Types for the admissions module covering public application forms,
 * admin application management, entrance exams, decisions, enrollment,
 * class promotions, and return intent surveys.
 */

// =========================
// Enums / Union Types
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

export type EntranceExamStatus =
  | "scheduled"
  | "in_progress"
  | "completed"
  | "cancelled";

export type DecisionType = "accepted" | "rejected" | "waitlisted" | "deferred";

export type PromotionAction =
  | "promote"
  | "repeat"
  | "graduate"
  | "withdraw";

export type PromotionBatchStatus =
  | "draft"
  | "preview"
  | "in_progress"
  | "completed"
  | "failed";

export type ReturnIntentStatus = "draft" | "sent" | "completed";

export type ReturnIntent =
  | "pending"
  | "returning"
  | "not_returning"
  | "undecided";

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
  require_applicant_account: boolean;
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
  require_applicant_account: boolean;
  target_classes: PublicTargetClass[];
}

// =========================
// Application Submission
// =========================

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

// =========================
// Document Upload
// =========================

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

// =========================
// Payment
// =========================

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
// Admin — Admission Periods
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
  require_applicant_account: boolean;
  max_applications?: number;
  target_classes: string[];
  application_count?: number;
  // Phase 2: reminder config
  reminder_enabled?: boolean;
  reminder_days_before_close?: number;
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
  require_applicant_account?: boolean;
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
  require_applicant_account?: boolean;
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

// =========================
// Admin — Form Configuration
// =========================

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

// =========================
// Admin — Application Detail
// =========================

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
  // Phase 2 additions
  rejection_reason?: string;
  rejection_letter_url?: string;
  waitlist_rank?: number;
  waitlist_notes?: string;
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
  // Phase 3: Enrollment confirmation fields
  enrollment_deposit_paid?: boolean;
  enrollment_deposit_amount?: number | null;
  enrollment_deposit_reference?: string | null;
  boarding_status?: string | null;
  enrollment_confirmation_url?: string | null;
  welcome_pack_sent?: boolean;
  enrollment_checklist?: EnrollmentChecklist | null;
}

// =========================
// Admin — Application List
// =========================

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

// =========================
// Admin — Entrance Exams
// =========================

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

export interface ExamResultEntry {
  application_id: string;
  score: number;
  max_score: number;
  grade?: string;
  passed: boolean;
  remarks?: string;
}

export interface ExamRegistration {
  id: string;
  entrance_exam_id: string;
  application_id: string;
  applicant_name?: string;
  seat_number?: string;
  attended: boolean;
}

// =========================
// Admin — Decisions
// =========================

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

// =========================
// Admin — Enrollment
// =========================

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

// =========================
// Admin — Class Promotions
// =========================

export interface ClassPromotion {
  id: string;
  tenant_id: string;
  school_id: string;
  source_academic_year_id: string;
  source_academic_year_name?: string;
  target_academic_year_id: string;
  target_academic_year_name?: string;
  name: string;
  status: PromotionBatchStatus;
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
  action: PromotionAction;
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
  action: PromotionAction;
  target_class_id?: string;
  target_section_id?: string;
  reason?: string;
}

export interface BulkPromotionUpdateResponse {
  succeeded: number;
  failed: Array<{ entry_id: string; error: string }>;
}

// =========================
// Admin — Return Intent Surveys
// =========================

export interface ReturnIntentCampaign {
  id: string;
  tenant_id: string;
  school_id: string;
  academic_year_id: string;
  name: string;
  target_classes: string[];
  message_template?: string;
  status: ReturnIntentStatus;
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
  intent: ReturnIntent;
  responded_at?: string;
  responded_by?: string;
  reason?: string;
}

// =========================
// Admin — Dashboard / Analytics
// =========================

export interface AdmissionsDashboardStats {
  total_applications: number;
  by_status: Record<string, number>;
  by_class: Array<{ class_name: string; count: number }>;
  by_period: Array<{ period_name: string; count: number }>;
  conversion_rate?: number;
  pending_decisions: number;
  pending_enrollment: number;
  recent_applications: ApplicationListItem[];
}

export interface AdmissionsDemographicsData {
  by_gender: Record<string, number>;
  by_nationality: Array<{ nationality: string; count: number }>;
  by_previous_school: Array<{ school: string; count: number }>;
  age_distribution: Array<{ age_range: string; count: number }>;
}

// =========================
// Phase 2: Letters, Offers & Waitlist
// =========================

export type OfferResponse = "accepted" | "declined";

export interface WaitlistEntry {
  decision_id: string;
  application_id: string;
  applicant_name: string;
  tracking_code: string;
  target_class_name: string | null;
  waitlist_rank: number | null;
  waitlist_notes: string | null;
  decision_date: string;
  created_at: string;
}

export interface WaitlistListResponse {
  items: WaitlistEntry[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface OfferDetail {
  application_id: string;
  applicant_name: string;
  tracking_code: string;
  school_name: string;
  offered_class_name: string | null;
  decision_type: string;
  decision_date: string | null;
  conditions: string | null;
  response_deadline: string | null;
  decision_letter_url: string | null;
  offer_responded_at: string | null;
  offer_response: OfferResponse | null;
  offer_response_notes: string | null;
  is_expired: boolean;
}

export interface GenerateLetterResponse {
  decision_id: string;
  letter_url: string;
  letter_type: string;
}

export interface WaitlistPromoteData {
  offered_class_id: string;
  response_deadline?: string;
  conditions?: string;
}

export interface WaitlistReorderData {
  period_id: string;
  ordered_decision_ids: string[];
}

export interface ReminderConfigUpdate {
  reminder_enabled: boolean;
  reminder_days_before_close?: number;
}

// =========================
// Phase 3: Enrollment Checklist + CSSPS
// =========================

export type ChecklistType = "standard" | "boarding";
export type ChecklistItemType = "document" | "payment" | "form" | "boarding" | "medical";
export type BoardingStatus = "boarding" | "day";

export interface EnrollmentChecklistItem {
  id: string;
  checklist_id: string;
  item_type: ChecklistItemType;
  item_name: string;
  description: string | null;
  is_required: boolean;
  is_completed: boolean;
  completed_at: string | null;
  completed_by: string | null;
  completed_by_name: string | null;
  notes: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface EnrollmentChecklist {
  id: string;
  school_id: string;
  application_id: string;
  checklist_type: ChecklistType;
  completed_at: string | null;
  completed_by: string | null;
  completed_by_name: string | null;
  total_items: number;
  completed_items: number;
  required_items: number;
  required_completed: number;
  progress_pct: number;
  items: EnrollmentChecklistItem[];
  created_at: string;
  updated_at: string;
}

export interface EnrollmentDepositResponse {
  application_id: string;
  enrollment_deposit_paid: boolean;
  enrollment_deposit_amount: number | null;
  enrollment_deposit_reference: string | null;
}

export interface BoardingStatusResponse {
  application_id: string;
  boarding_status: string;
  boarding_items_added: number;
}

export interface ConfirmationLetterResponse {
  application_id: string;
  confirmation_url: string;
  applicant_name: string;
}

export interface WelcomePackResponse {
  application_id: string;
  welcome_pack_sent: boolean;
  channels: string[];
}

export interface CSSPSPreviewRow {
  row_number: number;
  index_number: string | null;
  first_name: string | null;
  last_name: string | null;
  other_names: string | null;
  gender: string | null;
  date_of_birth: string | null;
  programme: string | null;
  aggregate: number | null;
  jhs_school: string | null;
  parent_name: string | null;
  parent_phone: string | null;
  residential_status: string | null;
  house: string | null;
  errors: string[];
}

export interface CSSPSPreviewResponse {
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  detected_columns: string[];
  rows: CSSPSPreviewRow[];
}

export interface CSSPSImportResult {
  row_number: number;
  index_number: string;
  status: string;
  application_id: string | null;
  error: string | null;
}

export interface CSSPSImportResponse {
  total_rows: number;
  imported: number;
  skipped: number;
  errors: number;
  results: CSSPSImportResult[];
}

// =========================
// Phase 4: Capacity Planning
// =========================

export interface EnrollmentTarget {
  id: string;
  school_id: string;
  academic_year_id: string;
  class_id: string;
  class_name?: string;
  target_count: number;
  boarding_target: number | null;
  day_target: number | null;
  created_at: string;
  updated_at: string;
}

export interface EnrollmentTargetCreate {
  academic_year_id: string;
  class_id: string;
  target_count: number;
  boarding_target?: number | null;
  day_target?: number | null;
}

export interface EnrollmentTargetListResponse {
  items: EnrollmentTarget[];
  academic_year_id: string;
}

export interface ClassCapacityRow {
  class_id: string;
  class_name: string;
  capacity: number | null;
  target: number | null;
  boarding_target: number | null;
  day_target: number | null;
  current_enrolled: number;
  applications_in_pipeline: number;
  utilization_pct: number;
}

export interface CapacityDashboardResponse {
  academic_year_id: string;
  school_id: string;
  total_capacity: number | null;
  total_target: number | null;
  total_enrolled: number;
  total_pipeline: number;
  classes: ClassCapacityRow[];
}

export interface CapacityCheckResponse {
  class_id: string;
  class_name: string | null;
  capacity: number | null;
  current_enrolled: number;
  remaining: number | null;
  is_full: boolean;
}

// =========================
// Phase 4: School Events
// =========================

export type EventType = "open_day" | "tour" | "orientation";
export type EventStatus = "upcoming" | "completed" | "cancelled";

export interface SchoolEvent {
  id: string;
  school_id: string;
  event_type: EventType;
  name: string;
  description: string | null;
  event_date: string;
  start_time: string | null;
  end_time: string | null;
  venue: string | null;
  capacity: number | null;
  registered_count: number;
  status: EventStatus;
  guide_id: string | null;
  guide_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface EventCreate {
  event_type: EventType;
  name: string;
  description?: string | null;
  event_date: string;
  start_time?: string | null;
  end_time?: string | null;
  venue?: string | null;
  capacity?: number | null;
  guide_id?: string | null;
}

export interface EventUpdate {
  name?: string;
  description?: string | null;
  event_date?: string;
  start_time?: string | null;
  end_time?: string | null;
  venue?: string | null;
  capacity?: number | null;
  guide_id?: string | null;
}

export interface EventListResponse {
  items: SchoolEvent[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface EventRegistration {
  id: string;
  event_id: string;
  registrant_name: string;
  registrant_phone: string;
  registrant_email: string | null;
  student_name: string | null;
  attended: boolean;
  registered_at: string;
  notes: string | null;
  created_at: string;
}

export interface EventRegistrationCreate {
  registrant_name: string;
  registrant_phone: string;
  registrant_email?: string | null;
  student_name?: string | null;
  notes?: string | null;
}

export interface EventStatsResponse {
  event_id: string;
  event_name: string;
  total_registered: number;
  total_attended: number;
  attendance_rate: number;
  capacity: number | null;
  fill_rate: number | null;
}

// =========================
// Phase 4: Enrollment Analytics
// =========================

export interface FunnelStageResponse {
  stage: string;
  count: number;
  conversion_rate: number | null;
}

export interface FunnelResponse {
  school_id: string;
  period_id: string | null;
  stages: FunnelStageResponse[];
}

export interface YearClassCount {
  class_id: string;
  class_name: string;
  count: number;
}

export interface YearTrendRow {
  academic_year_id: string;
  academic_year_name: string;
  total_enrolled: number;
  by_class: YearClassCount[];
}

export interface TrendsResponse {
  school_id: string;
  years: YearTrendRow[];
}

export interface SourceEffectivenessRow {
  source: string;
  inquiry_count: number;
  application_count: number;
  enrollment_count: number;
  inquiry_to_application_rate: number;
  inquiry_to_enrollment_rate: number;
}

export interface SourceEffectivenessResponse {
  school_id: string;
  period_id: string | null;
  sources: SourceEffectivenessRow[];
}

export interface ReEnrollmentYearRow {
  academic_year_id: string;
  academic_year_name: string;
  total_students: number;
  returning_count: number;
  re_enrollment_rate: number;
}

export interface ReEnrollmentResponse {
  school_id: string;
  years: ReEnrollmentYearRow[];
}

export interface AttritionReasonRow {
  reason: string;
  count: number;
}

export interface AttritionResponse {
  school_id: string;
  academic_year_id: string | null;
  withdrawn_count: number;
  not_returning_count: number;
  total_attrition: number;
  withdrawal_reasons: AttritionReasonRow[];
  not_returning_reasons: AttritionReasonRow[];
}

export interface EnrollmentVsCapacityRow {
  class_id: string;
  class_name: string;
  target: number | null;
  actual_enrolled: number;
  capacity: number | null;
  variance: number | null;
  fill_pct: number | null;
}

export interface EnrollmentVsCapacityResponse {
  school_id: string;
  academic_year_id: string;
  classes: EnrollmentVsCapacityRow[];
  total_target: number | null;
  total_enrolled: number;
  total_capacity: number | null;
}

// =========================
// Phase 4: Re-enrollment Summary
// =========================

export interface ReEnrollmentClassBreakdown {
  class_name: string;
  confirmed: number;
  pending: number;
  not_returning: number;
}

export interface ReEnrollmentSummaryResponse {
  campaign_id: string;
  total_intents: number;
  confirmed_count: number;
  pending_count: number;
  not_returning_count: number;
  undecided_count: number;
  total_outstanding_fees: number;
  by_class: ReEnrollmentClassBreakdown[];
}
