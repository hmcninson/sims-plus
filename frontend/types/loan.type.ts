/**
 * Loan Management Module Types
 * Mirrors backend schemas from app/schemas/loan.py
 */

// =========================
// Enums
// =========================

export type LoanStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "active"
  | "completed"
  | "written_off"
  | "restructured"
  | "rejected";

export type InterestMethod = "flat" | "reducing_balance";

export type LoanPaymentMethod = "cash" | "bank_transfer" | "mobile_money" | "payroll";

// =========================
// Loan Types (Configuration)
// =========================

export interface LoanType {
  id: string;
  tenant_id: string;
  school_id: string | null;
  name: string;
  code: string;
  description: string | null;
  default_interest_rate: number;
  default_interest_method: InterestMethod;
  max_amount: number | null;
  max_tenure_months: number | null;
  max_active_loans: number;
  requires_guarantor: boolean;
  min_service_months: number;
  max_deduction_pct: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoanTypeCreate {
  name: string;
  code: string;
  description?: string;
  default_interest_rate?: number;
  default_interest_method?: InterestMethod;
  max_amount?: number;
  max_tenure_months?: number;
  max_active_loans?: number;
  requires_guarantor?: boolean;
  min_service_months?: number;
  max_deduction_pct?: number;
  school_id?: string;
}

export interface LoanTypeUpdate {
  name?: string;
  code?: string;
  description?: string | null;
  default_interest_rate?: number;
  default_interest_method?: InterestMethod;
  max_amount?: number | null;
  max_tenure_months?: number | null;
  max_active_loans?: number;
  requires_guarantor?: boolean;
  min_service_months?: number;
  max_deduction_pct?: number;
  is_active?: boolean;
}

// =========================
// Staff Loans
// =========================

export interface StaffLoan {
  id: string;
  tenant_id: string;
  school_id: string | null;
  loan_number: string;
  staff_id: string;
  staff_name: string | null;
  loan_type: LoanType | null;
  status: LoanStatus;
  principal_amount: number;
  interest_rate: number;
  interest_method: InterestMethod;
  total_interest: number;
  total_repayable: number;
  tenure_months: number;
  monthly_installment: number;
  total_paid: number;
  outstanding_balance: number;
  installments_paid: number;
  installments_remaining: number;
  application_date: string;
  approval_date: string | null;
  disbursement_date: string | null;
  first_deduction_date: string | null;
  expected_completion_date: string | null;
  actual_completion_date: string | null;
  purpose: string | null;
  notes: string | null;
  guarantors: LoanGuarantor[];
  created_at: string;
  updated_at: string;
}

/** Loan summary for list views (matches backend LoanListItem). */
export interface StaffLoanListItem {
  id: string;
  loan_number: string;
  staff_id: string;
  staff_name: string | null;
  loan_type_name: string | null;
  status: LoanStatus;
  principal_amount: number;
  total_repayable: number;
  total_paid: number;
  outstanding_balance: number;
  tenure_months: number;
  installments_paid: number;
  installments_remaining: number;
  application_date: string;
  first_deduction_date: string | null;
}

/** Paginated loan list response (matches backend LoanListResponse). */
export interface StaffLoanListResponse {
  items: StaffLoanListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface StaffLoanCreate {
  staff_id: string;
  loan_type_id: string;
  principal_amount: number;
  interest_rate?: number;
  interest_method?: InterestMethod;
  tenure_months: number;
  first_deduction_date: string;
  purpose?: string;
  guarantor_staff_ids?: string[];
  school_id?: string;
}

export interface StaffLoanUpdate {
  principal_amount?: number;
  interest_rate?: number;
  interest_method?: InterestMethod;
  tenure_months?: number;
  first_deduction_date?: string;
  purpose?: string;
  notes?: string;
}

// =========================
// Loan Installments
// =========================

export interface LoanInstallment {
  id: string;
  loan_id: string;
  installment_number: number;
  due_date: string;
  principal_component: number;
  interest_component: number;
  installment_amount: number;
  opening_balance: number;
  closing_balance: number;
  is_paid: boolean;
  paid_date: string | null;
  paid_amount: number | null;
  payroll_run_id: string | null;
  notes: string | null;
}

// =========================
// Loan Guarantors
// =========================

export interface LoanGuarantor {
  id: string;
  loan_id: string;
  guarantor_staff_id: string;
  guarantor_staff_name: string | null;
  relationship: string | null;
  guaranteed_amount: number | null;
  consent_given: boolean;
  consent_date: string | null;
  notes: string | null;
  created_at: string;
}

export interface LoanGuarantorInput {
  guarantor_staff_id: string;
  relationship?: string;
  guaranteed_amount?: number;
  notes?: string;
}

// =========================
// Loan Payments
// =========================

export interface LoanPayment {
  id: string;
  loan_id: string;
  payment_number: string;
  amount: number;
  payment_date: string;
  payment_method: LoanPaymentMethod;
  reference: string | null;
  installments_covered: unknown[] | null;
  is_early_repayment: boolean;
  recorded_by: string;
  notes: string | null;
  created_at: string;
}

// =========================
// Portfolio & Analytics
// =========================

export interface LoanPortfolio {
  total_loans: number;
  active_loans: number;
  total_disbursed: number;
  total_outstanding: number;
  total_collected: number;
  total_written_off: number;
  average_loan_amount: number;
  by_type: LoanTypeBreakdown[];
  by_status: Record<string, number>;
  overdue_count: number;
  overdue_amount: number;
}

export interface LoanTypeBreakdown {
  loan_type_id: string;
  loan_type_name: string;
  count: number;
  total_principal: number;
  total_outstanding: number;
}

export interface LoanAgingBucket {
  bucket: string;
  count: number;
  total_amount: number;
  loans: Record<string, unknown>[];
}

export interface LoanAgingResponse {
  total_overdue: number;
  total_overdue_count: number;
  buckets: LoanAgingBucket[];
}

export interface LoanEligibility {
  eligible: boolean;
  reasons: string[];
  max_eligible_amount: number | null;
  max_eligible_tenure: number | null;
}

// =========================
// Action Payloads
// =========================

export interface LoanRejectPayload {
  reason: string;
}

export interface EarlyRepaymentPayload {
  amount: number;
  payment_date: string;
  payment_method: "cash" | "bank_transfer" | "mobile_money";
  reference?: string;
  is_full_settlement: boolean;
  notes?: string;
}

export interface LoanRestructurePayload {
  new_interest_rate: number;
  new_interest_method: InterestMethod;
  new_tenure_months: number;
  new_first_deduction_date: string;
  reason: string;
}

export interface LoanWriteOffPayload {
  reason: string;
}
