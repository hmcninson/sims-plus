/**
 * SIMS Plus - Finance Module Type Definitions
 */

// =========================
// Fee Type Types
// =========================

export type FeeTypeCategory = "tuition" | "examination" | "facilities" | "activities" | "other";

export interface FeeType {
  id: string;
  tenant_id: string;
  school_id: string;
  name: string;
  description?: string;
  category?: FeeTypeCategory;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FeeTypeCreate {
  name: string;
  description?: string;
  category?: FeeTypeCategory;
  is_active?: boolean;
}

export interface FeeTypeUpdate {
  name?: string;
  description?: string;
  category?: FeeTypeCategory;
  is_active?: boolean;
}

export interface FeeTypeListResponse {
  items: FeeType[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// =========================
// Fee Structure Types
// =========================

export interface FeeItem {
  id: string;
  tenant_id: string;
  fee_structure_id: string;
  fee_type_id?: string;
  fee_type_name?: string;
  name: string;
  description?: string;
  amount: number;
  is_optional: boolean;
  sequence: number;
  created_at: string;
  updated_at: string;
}

export interface FeeItemCreate {
  fee_type_id?: string;
  name: string;
  description?: string;
  amount: number;
  is_optional?: boolean;
  sequence?: number;
}

export interface FeeItemUpdate {
  fee_type_id?: string;
  name?: string;
  description?: string;
  amount?: number;
  is_optional?: boolean;
  sequence?: number;
}

export type LevelCategory = "preschool" | "primary" | "jhs" | "shs";
export type StudentType = "all" | "boarding" | "day";

export interface FeeStructure {
  id: string;
  tenant_id: string;
  school_id: string;
  name: string;
  description?: string;
  academic_year_id?: string;
  term_id?: string;
  class_id?: string;
  level?: string;
  level_category?: LevelCategory;
  student_type: StudentType;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FeeStructureWithItems extends FeeStructure {
  items: FeeItem[];
  total_amount: number;
  academic_year_name?: string;
  term_name?: string;
  class_name?: string;
}

export interface FeeStructureCreate {
  name: string;
  description?: string;
  academic_year_id?: string;
  term_id?: string;
  class_id?: string;
  level?: string;
  level_category?: LevelCategory;
  student_type?: StudentType;
  is_active?: boolean;
  items?: FeeItemCreate[];
}

export interface FeeItemUpdateInStructure {
  id?: string;
  fee_type_id?: string;
  name: string;
  description?: string;
  amount: number;
  is_optional?: boolean;
  sequence?: number;
}

export interface FeeStructureUpdate {
  name?: string;
  description?: string;
  academic_year_id?: string;
  term_id?: string;
  class_id?: string;
  level?: string;
  level_category?: LevelCategory;
  student_type?: StudentType;
  is_active?: boolean;
  items?: FeeItemUpdateInStructure[];
}

export interface FeeStructureListResponse {
  items: FeeStructureWithItems[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// =========================
// Invoice Types
// =========================

export type InvoiceStatus =
  | "draft"
  | "issued"
  | "partial"
  | "paid"
  | "overdue"
  | "cancelled"
  | "write_off";

export interface InvoiceItem {
  id: string;
  tenant_id: string;
  invoice_id: string;
  fee_item_id?: string;
  description: string;
  quantity: number;
  unit_price: number;
  amount: number;
  created_at: string;
}

export interface InvoiceScholarshipItem {
  id: string;
  tenant_id: string;
  invoice_id: string;
  student_scholarship_id?: string;
  scholarship_id?: string;
  scholarship_name: string;
  scholarship_code?: string;
  coverage_type: string;
  coverage_value: number;
  calculated_amount: number;
  applicable_subtotal: number;
  created_at: string;
}

export interface InvoiceItemCreate {
  fee_item_id?: string;
  description: string;
  quantity?: number;
  unit_price: number;
}

export interface Invoice {
  id: string;
  tenant_id: string;
  school_id: string;
  invoice_number: string;
  student_id: string;
  fee_structure_id?: string;
  academic_year_id: string;
  term_id: string;
  subtotal: number;
  discount_amount: number;
  scholarship_discount: number;
  tax_amount: number;
  total_amount: number;
  amount_paid: number;
  balance: number;
  status: InvoiceStatus;
  issue_date?: string;
  due_date?: string;
  currency: string;
  notes?: string;
  cancel_reason?: string;
  cancelled_at?: string;
  // Adjustment tracking
  adjustment_for_invoice_id?: string;
  adjustment_type?: string;
  adjustment_reason?: string;
  created_at: string;
  updated_at: string;
}

export interface InvoiceWithDetails extends Invoice {
  student_name: string;
  student_id_number: string;
  class_name?: string;
  academic_year_name: string;
  term_name: string;
  items: InvoiceItem[];
  scholarship_items?: InvoiceScholarshipItem[];
  payments?: Payment[];
}

export interface InvoiceCreate {
  student_id: string;
  fee_structure_id?: string;
  academic_year_id: string;
  term_id: string;
  due_date?: string;
  discount_amount?: number;
  notes?: string;
  items?: InvoiceItemCreate[];
}

export interface InvoiceUpdate {
  due_date?: string;
  discount_amount?: number;
  notes?: string;
}

export interface InvoiceListResponse {
  items: InvoiceWithDetails[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface InvoiceBulkGenerate {
  fee_structure_id: string;
  academic_year_id: string;
  term_id: string;
  class_id?: string;
  section_id?: string;
  due_date?: string;
  student_ids?: string[];
  issue_immediately?: boolean;
}

export interface InvoiceBulkResult {
  created: number;
  skipped: number;
  failed: number;
  errors: { student_id: string; error: string }[];
  invoice_ids: string[];
}

export interface InvoiceSyncRequest {
  fee_structure_id: string;
  academic_year_id: string;
  term_id: string;
}

export interface InvoiceSyncPreview {
  draft_count: number;
  issued_count: number;
  partial_count: number;
  paid_count: number;
  total_invoices: number;
  can_sync_count: number;
  cannot_sync_count: number;
  new_fee_structure_total: number;
}

export interface InvoiceSyncSkippedReasons {
  issued: number;
  partial: number;
  paid: number;
}

export interface InvoiceSyncResult {
  updated: number;
  skipped: number;
  failed: number;
  errors: string[];
  skipped_reasons: InvoiceSyncSkippedReasons;
}

export interface InvoiceIssue {
  issue_date?: string;
}

export interface InvoiceCancel {
  reason: string;
}

// =========================
// Missing Invoice Types
// =========================

export interface StudentMissingInvoice {
  id: string;
  student_id: string;
  first_name: string;
  middle_name?: string;
  last_name: string;
  class_id?: string;
  class_name?: string;
  section_id?: string;
  section_name?: string;
}

export interface StudentsMissingInvoicesResponse {
  students: StudentMissingInvoice[];
  total: number;
  fee_structure_name: string;
  academic_year_name: string;
  term_name: string;
}

// =========================
// Payment Types
// =========================

export type PaymentMethod =
  | "cash"
  | "momo_mtn"
  | "momo_vodafone"
  | "momo_airteltigo"
  | "bank_transfer"
  | "cheque"
  | "card"
  | "other";

export type PaymentStatus =
  | "pending"
  | "completed"
  | "failed"
  | "refunded"
  | "cancelled";

export interface Payment {
  id: string;
  tenant_id: string;
  school_id: string;
  receipt_number: string;
  invoice_id?: string;
  student_id: string;
  amount: number;
  currency: string;
  payment_method: PaymentMethod;
  momo_phone?: string;
  momo_transaction_id?: string;
  momo_provider?: string;
  bank_name?: string;
  bank_reference?: string;
  cheque_number?: string;
  payer_name?: string;
  payer_phone?: string;
  payer_email?: string;
  status: PaymentStatus;
  payment_date: string;
  notes?: string;
  is_voided: boolean;
  created_at: string;
  updated_at: string;
}

export interface PaymentWithDetails extends Payment {
  student_name: string;
  student_id_number: string;
  invoice_number?: string;
  recorded_by_name?: string;
}

export interface PaymentCreate {
  invoice_id?: string;
  student_id: string;
  amount: number;
  payment_method: PaymentMethod;
  payment_date?: string;
  payer_name?: string;
  payer_phone?: string;
  payer_email?: string;
  notes?: string;
  momo_phone?: string;
  momo_transaction_id?: string;
  bank_name?: string;
  bank_reference?: string;
  cheque_number?: string;
}

export interface PaymentListResponse {
  items: PaymentWithDetails[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface PaymentVoid {
  reason: string;
}

export interface PaymentReceipt {
  school_name: string;
  school_address?: string;
  school_phone?: string;
  school_email?: string;
  school_logo_url?: string;
  receipt_number: string;
  payment_date: string;
  student_name: string;
  student_id_number: string;
  class_name?: string;
  amount: number;
  amount_in_words: string;
  currency: string;
  payment_method: string;
  payer_name?: string;
  invoice_number?: string;
  notes?: string;
  recorded_by_name?: string;
}

// =========================
// Scholarship Types
// =========================

export type ScholarshipType =
  | "full"
  | "partial"
  | "merit"
  | "need_based"
  | "athletic"
  | "special";

export type CoverageType = "percentage" | "fixed_amount";

export type ScholarshipStatus = "active" | "suspended" | "revoked" | "expired";

export type ApplicationStatus =
  | "pending"
  | "under_review"
  | "approved"
  | "rejected";

export interface Scholarship {
  id: string;
  tenant_id: string;
  school_id: string;
  name: string;
  code: string;
  description?: string;
  scholarship_type: ScholarshipType;
  coverage_type: CoverageType;
  coverage_value: number;
  applicable_fees?: string[];
  max_recipients?: number;
  academic_year_id?: string;
  eligibility_criteria?: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ScholarshipWithStats extends Scholarship {
  recipients_count: number;
  active_recipients_count: number;
  academic_year_name?: string;
  total_discount_given?: number;
}

export interface ScholarshipCreate {
  name: string;
  code: string;
  description?: string;
  scholarship_type: ScholarshipType;
  coverage_type: CoverageType;
  coverage_value: number;
  applicable_fees?: string[];
  max_recipients?: number;
  academic_year_id?: string;
  eligibility_criteria?: Record<string, unknown>;
  is_active?: boolean;
}

export interface ScholarshipUpdate {
  name?: string;
  code?: string;
  description?: string;
  scholarship_type?: ScholarshipType;
  coverage_type?: CoverageType;
  coverage_value?: number;
  applicable_fees?: string[];
  max_recipients?: number;
  academic_year_id?: string;
  eligibility_criteria?: Record<string, unknown>;
  is_active?: boolean;
}

export interface ScholarshipListResponse {
  items: ScholarshipWithStats[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// =========================
// Student Scholarship Types
// =========================

export type RenewalType = "one_time" | "annual" | "until_graduation";

export interface StudentScholarship {
  id: string;
  tenant_id: string;
  scholarship_id: string;
  student_id: string;
  academic_year_id: string;
  awarded_by?: string;
  awarded_at: string;
  status: ScholarshipStatus;
  effective_from: string;
  effective_to?: string;
  coverage_override?: number;
  notes?: string;
  // Enhanced award settings
  justification?: string;
  renewal_type: RenewalType;
  is_provisional: boolean;
  provisional_conditions?: string;
  // Revocation info
  revoked_at?: string;
  revoked_by?: string;
  revoke_reason?: string;
  // Reinstatement tracking
  reinstated_from?: string;
  created_at: string;
  updated_at: string;
}

export interface StudentScholarshipWithDetails extends StudentScholarship {
  scholarship_name: string;
  scholarship_code: string;
  scholarship_type: ScholarshipType;
  coverage_type: CoverageType;
  coverage_value: number;
  student_name: string;
  student_id_number: string;
  academic_year_name: string;
  awarded_by_name?: string;
  // Note: Enhanced fields (justification, renewal_type, etc.) are inherited from StudentScholarship
}

export interface ScholarshipAward {
  student_id: string;
  effective_from: string;
  effective_to?: string;
  coverage_override?: number;
  notes?: string;
  // Enhanced award settings
  justification?: string;
  renewal_type?: RenewalType;
  is_provisional?: boolean;
  provisional_conditions?: string;
  // Reinstatement (for re-awarding after revocation)
  reinstated_from?: string;
}

export interface ScholarshipBulkAward {
  student_ids: string[];
  effective_from: string;
  effective_to?: string;
  coverage_override?: number;
  notes?: string;
  // Enhanced award settings
  justification?: string;
  renewal_type?: RenewalType;
  is_provisional?: boolean;
  provisional_conditions?: string;
}

export interface ScholarshipBulkAwardResult {
  awarded: number;
  skipped: number;
  failed: number;
  errors: string[];
  student_scholarship_ids: string[];
  // Aliases for frontend convenience
  success_count?: number;
  failed_count?: number;
}

export interface ScholarshipRevoke {
  reason: string;
}

export interface StudentScholarshipListResponse {
  items: StudentScholarshipWithDetails[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// =========================
// Scholarship Application Types
// =========================

export interface ApplicationDocument {
  name: string;
  url: string;
  type?: string;
}

export interface ScholarshipApplication {
  id: string;
  tenant_id: string;
  scholarship_id: string;
  student_id: string;
  academic_year_id: string;
  applied_at: string;
  status: ApplicationStatus;
  supporting_documents?: ApplicationDocument[];
  application_notes?: string;
  reviewer_id?: string;
  reviewed_at?: string;
  reviewer_notes?: string;
  created_at: string;
  updated_at: string;
}

export interface ScholarshipApplicationWithDetails extends ScholarshipApplication {
  scholarship_name: string;
  scholarship_code: string;
  student_name: string;
  student_id_number: string;
  academic_year_name: string;
  reviewer_name?: string;
}

export interface ScholarshipApplicationCreate {
  scholarship_id: string;
  academic_year_id: string;
  supporting_documents?: ApplicationDocument[];
  application_notes?: string;
}

export interface ScholarshipApplicationReview {
  reviewer_notes?: string;
}

export interface ScholarshipApplicationListResponse {
  items: ScholarshipApplicationWithDetails[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// =========================
// Dashboard Types
// =========================

export interface FinanceDashboardStats {
  expected_revenue: number;
  collected_revenue: number;
  outstanding_balance: number;
  total_invoices: number;
  paid_invoices: number;
  partial_invoices: number;
  overdue_invoices: number;
  total_payments: number;
  total_scholarships_value: number;
  scholarship_recipients: number;
}

export interface RecentPayment {
  id: string;
  receipt_number: string;
  student_name: string;
  amount: number;
  payment_method: string;
  payment_date: string;
}

export interface OutstandingByClass {
  class_id: string;
  class_name: string;
  student_count: number;
  total_outstanding: number;
}

export interface FinanceDashboard {
  stats: FinanceDashboardStats;
  recent_payments: RecentPayment[];
  outstanding_by_class: OutstandingByClass[];
}

// =========================
// Invoice Email Types
// =========================

export interface InvoiceEmailRequest {
  email: string;
  recipient_name?: string;
  cc_emails?: string[];
}

export interface InvoiceEmailResponse {
  success: boolean;
  message: string;
  email: string;
}

// =========================
// Credit Note Types
// =========================

export type CreditNoteStatus =
  | "draft"
  | "issued"
  | "applied"
  | "refunded"
  | "cancelled";

export type CreditNoteType =
  | "overpayment"
  | "fee_reduction"
  | "error_correction"
  | "scholarship_adjustment"
  | "other";

export interface CreditNote {
  id: string;
  tenant_id: string;
  school_id: string;
  credit_note_number: string;
  credit_note_type: CreditNoteType;
  original_invoice_id?: string;
  student_id: string;
  amount: number;
  currency: string;
  reason: string;
  status: CreditNoteStatus;
  issued_by?: string;
  issued_at?: string;
  applied_to_invoice_id?: string;
  applied_amount?: number;
  applied_by?: string;
  applied_at?: string;
  refund_method?: string;
  refund_reference?: string;
  refunded_by?: string;
  refunded_at?: string;
  cancelled_by?: string;
  cancelled_at?: string;
  cancel_reason?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface CreditNoteWithDetails extends CreditNote {
  student_name: string;
  student_id_number: string;
  original_invoice_number?: string;
  applied_to_invoice_number?: string;
  issued_by_name?: string;
}

export interface CreditNoteCreate {
  credit_note_type: CreditNoteType;
  original_invoice_id?: string;
  student_id: string;
  amount: number;
  currency?: string;
  reason: string;
  notes?: string;
}

export interface CreditNoteUpdate {
  credit_note_type?: CreditNoteType;
  original_invoice_id?: string;
  amount?: number;
  reason?: string;
  notes?: string;
}

export interface CreditNoteApply {
  invoice_id: string;
  amount?: number;
}

export interface CreditNoteRefund {
  refund_method: string;
  refund_reference?: string;
}

export interface CreditNoteCancel {
  reason: string;
}

export interface CreditNoteListResponse {
  items: CreditNoteWithDetails[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface StudentCreditBalance {
  student_id: string;
  credit_balance: number;
  currency: string;
}
