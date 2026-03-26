/**
 * Payroll Module Types
 * Mirrors backend schemas from app/schemas/payroll.py
 */

// =========================
// Enums
// =========================

export type CalculationMethod = "fixed" | "percentage_basic" | "percentage_gross";

export type PayrollPaymentMethod = "bank_transfer" | "cash" | "mobile_money";

export type DeductionCategory =
  | "statutory"
  | "voluntary"
  | "loan"
  | "union"
  | "other";

export type PayrollRunStatus =
  | "draft"
  | "processing"
  | "calculated"
  | "pending_approval"
  | "approved"
  | "paid"
  | "cancelled";

export type PayrollRunType = "regular" | "supplementary" | "bonus" | "arrears";

export type PayrollApprovalAction = "approve" | "reject" | "return_for_review";

// =========================
// Payroll Runs
// =========================

export interface PayrollRun {
  id: string;
  month: number;
  year: number;
  run_number: number;
  status: PayrollRunStatus;
  run_type: PayrollRunType;
  total_basic: number;
  total_allowances: number;
  total_gross: number;
  total_paye: number;
  total_ssnit_ee: number;
  total_ssnit_er: number;
  total_tier2_er: number;
  total_tier3: number;
  total_other_deductions: number;
  total_net: number;
  total_employer_cost: number;
  staff_count: number;
  currency: string;
  notes: string | null;
  processed_by: string | null;
  processed_by_name: string | null;
  processed_at: string | null;
  approved_by: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  paid_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PayrollRunCreate {
  month: number;
  year: number;
  run_type?: PayrollRunType;
  notes?: string;
}

export interface PayrollItem {
  id: string;
  payroll_run_id: string;
  staff_id: string;
  staff_name: string;
  staff_code: string;
  department_name: string | null;
  salary_grade_name: string | null;
  basic_salary: number;
  total_allowances: number;
  gross_salary: number;
  taxable_income: number;
  paye_tax: number;
  ssnit_employee: number;
  ssnit_employer: number;
  tier2_employer: number;
  tier3_employee: number;
  total_deductions: number;
  net_salary: number;
  payment_method: string | null;
}

export interface PayrollItemEarning {
  id: string;
  name: string;
  amount: number;
  is_taxable: boolean;
}

export interface PayrollItemDeduction {
  id: string;
  name: string;
  amount: number;
  is_statutory: boolean;
  is_employer_portion: boolean;
  deduction_category: string | null;
}

export interface PayrollItemDetail extends PayrollItem {
  earnings: PayrollItemEarning[];
  deductions: PayrollItemDeduction[];
}

export interface PayrollRunSummary {
  run: PayrollRun;
  by_department: PayrollDepartmentBreakdown[];
  by_payment_method: PayrollPaymentMethodBreakdown[];
}

export interface PayrollDepartmentBreakdown {
  department_name: string;
  staff_count: number;
  total_gross: number;
  total_net: number;
}

export interface PayrollPaymentMethodBreakdown {
  payment_method: string;
  staff_count: number;
  total_net: number;
}

export interface PayrollItemAdjustment {
  field: string;
  new_value: number;
  reason: string;
}

// =========================
// Salary Grades
// =========================

export interface SalaryGrade {
  id: string;
  name: string;
  code: string | null;
  basic_salary: number;
  min_salary: number | null;
  max_salary: number | null;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SalaryGradeCreate {
  name: string;
  code?: string;
  basic_salary: number;
  min_salary?: number;
  max_salary?: number;
  description?: string;
}

export interface SalaryGradeUpdate {
  name?: string;
  code?: string;
  basic_salary?: number;
  min_salary?: number | null;
  max_salary?: number | null;
  description?: string | null;
  is_active?: boolean;
}

// =========================
// Allowance Types
// =========================

export interface AllowanceType {
  id: string;
  name: string;
  code: string;
  calculation_method: CalculationMethod;
  default_amount: number;
  is_taxable: boolean;
  is_active: boolean;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface AllowanceTypeCreate {
  name: string;
  code: string;
  calculation_method: CalculationMethod;
  default_amount: number;
  is_taxable?: boolean;
  description?: string;
}

export interface AllowanceTypeUpdate {
  name?: string;
  code?: string;
  calculation_method?: CalculationMethod;
  default_amount?: number;
  is_taxable?: boolean;
  is_active?: boolean;
  description?: string | null;
}

// =========================
// Deduction Types
// =========================

export interface DeductionType {
  id: string;
  name: string;
  code: string;
  calculation_method: CalculationMethod;
  default_amount: number;
  is_statutory: boolean;
  is_employer_portion: boolean;
  deduction_category: DeductionCategory;
  is_active: boolean;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeductionTypeCreate {
  name: string;
  code: string;
  calculation_method: CalculationMethod;
  default_amount: number;
  is_statutory?: boolean;
  is_employer_portion?: boolean;
  deduction_category: DeductionCategory;
  description?: string;
}

export interface DeductionTypeUpdate {
  name?: string;
  code?: string;
  calculation_method?: CalculationMethod;
  default_amount?: number;
  is_statutory?: boolean;
  is_employer_portion?: boolean;
  deduction_category?: DeductionCategory;
  is_active?: boolean;
  description?: string | null;
}

// =========================
// Tax Brackets
// =========================

export interface TaxBracket {
  id: string;
  effective_year: number;
  band_number: number;
  lower_limit: number;
  upper_limit: number | null;
  rate: number;
  cumulative_tax: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TaxBracketUpdate {
  lower_limit?: number;
  upper_limit?: number | null;
  rate?: number;
  cumulative_tax?: number;
  is_active?: boolean;
}

export interface TaxBracketSeedRequest {
  effective_year: number;
}

// =========================
// Bank File Configs
// =========================

export interface ColumnMappingEntry {
  header: string;
  source: string;
  format?: string;
  template?: string;
  width?: number | null;
}

export interface BankFileConfig {
  id: string;
  bank_name: string;
  file_format: string;
  delimiter: string;
  column_mapping: ColumnMappingEntry[];
  header_template: string | null;
  footer_template: string | null;
  include_header_row: boolean;
  date_format: string;
  amount_format: string;
  encoding: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface BankFileConfigCreate {
  bank_name: string;
  file_format?: string;
  delimiter?: string;
  column_mapping: ColumnMappingEntry[];
  header_template?: string;
  footer_template?: string;
  include_header_row?: boolean;
  date_format?: string;
  amount_format?: string;
  encoding?: string;
  is_default?: boolean;
}

export interface BankFileConfigUpdate {
  bank_name?: string;
  file_format?: string;
  delimiter?: string;
  column_mapping?: ColumnMappingEntry[];
  header_template?: string | null;
  footer_template?: string | null;
  include_header_row?: boolean;
  date_format?: string;
  amount_format?: string;
  encoding?: string;
  is_default?: boolean;
}

// =========================
// Staff Salary Config
// =========================

export interface StaffAllowance {
  id: string;
  allowance_type_id: string;
  allowance_type_name?: string;
  allowance_type_code?: string;
  amount: number;
  calculation_method: CalculationMethod | null;
}

export interface StaffDeduction {
  id: string;
  deduction_type_id: string;
  deduction_type_name?: string;
  deduction_type_code?: string;
  amount: number;
  calculation_method: CalculationMethod | null;
}

export interface StaffSalaryConfig {
  id: string;
  staff_id: string;
  salary_grade_id: string | null;
  salary_grade_name?: string;
  basic_salary: number;
  effective_date: string;
  end_date: string | null;
  payment_method: PayrollPaymentMethod;
  bank_name: string | null;
  bank_branch: string | null;
  account_number: string | null;
  mobile_money_number: string | null;
  mobile_money_provider: string | null;
  tin_number: string | null;
  ssnit_number: string | null;
  notes: string | null;
  is_active: boolean;
  allowances: StaffAllowance[];
  deductions: StaffDeduction[];
  created_at: string;
  updated_at: string;
}

export interface StaffAllowanceInput {
  allowance_type_id: string;
  amount: number;
  calculation_method?: CalculationMethod;
}

export interface StaffDeductionInput {
  deduction_type_id: string;
  amount: number;
  calculation_method?: CalculationMethod;
}

export interface StaffSalaryConfigCreate {
  salary_grade_id?: string;
  basic_salary: number;
  effective_date: string;
  payment_method?: PayrollPaymentMethod;
  bank_name?: string;
  bank_branch?: string;
  account_number?: string;
  mobile_money_number?: string;
  mobile_money_provider?: string;
  tin_number?: string;
  ssnit_number?: string;
  notes?: string;
  allowances?: StaffAllowanceInput[];
  deductions?: StaffDeductionInput[];
}

export interface BulkSalaryGradeAssign {
  staff_ids: string[];
  salary_grade_id: string;
  effective_date: string;
}

export interface BulkSalaryAssignResult {
  assigned_count: number;
  skipped_count: number;
  errors: string[];
}

// =========================
// Salary History
// =========================

/**
 * Salary history entries are full StaffSalaryConfig objects returned by the backend.
 * Using a type alias for semantic clarity in history-related contexts.
 */
export type SalaryHistoryEntry = StaffSalaryConfig;

// =========================
// Report Types (Phase 4C)
// =========================

export interface MonthlySummary {
  month: number;
  year: number;
  total_staff: number;
  total_basic: number;
  total_allowances: number;
  total_gross: number;
  total_paye: number;
  total_ssnit_ee: number;
  total_ssnit_er: number;
  total_tier2_er: number;
  total_tier3: number;
  total_other_deductions: number;
  total_net: number;
  total_employer_cost: number;
  currency: string;
  by_department: MonthlySummaryDepartment[];
  by_payment_method: PayrollPaymentMethodBreakdown[];
}

export interface MonthlySummaryDepartment {
  department_name: string;
  staff_count: number;
  total_gross: number;
  total_net: number;
  total_employer_cost: number;
}

export interface SSNITReturn {
  staff_id: string;
  staff_name: string;
  staff_code: string;
  ssnit_number: string | null;
  basic_salary: number;
  ssnit_employee: number;
  ssnit_employer: number;
  tier2_employer: number;
}

export interface SSNITReturnReport {
  month: number;
  year: number;
  entries: SSNITReturn[];
  totals: {
    basic_salary: number;
    ssnit_employee: number;
    ssnit_employer: number;
    tier2_employer: number;
  };
}

export interface PAYEReturn {
  staff_id: string;
  staff_name: string;
  staff_code: string;
  tin_number: string | null;
  taxable_income: number;
  paye_tax: number;
}

export interface PAYEReturnReport {
  month: number;
  year: number;
  entries: PAYEReturn[];
  totals: {
    taxable_income: number;
    paye_tax: number;
  };
}

export interface DepartmentSummary {
  department_name: string;
  staff_count: number;
  total_basic: number;
  total_allowances: number;
  total_gross: number;
  total_paye: number;
  total_ssnit_ee: number;
  total_ssnit_er: number;
  total_net: number;
  total_employer_cost: number;
}

export interface DepartmentSummaryReport {
  month: number;
  year: number;
  departments: DepartmentSummary[];
  totals: {
    staff_count: number;
    total_gross: number;
    total_net: number;
    total_employer_cost: number;
  };
}

export interface YearToDateEntry {
  month: number;
  month_name: string;
  basic_salary: number;
  total_allowances: number;
  gross_salary: number;
  paye_tax: number;
  ssnit_employee: number;
  tier3_employee: number;
  total_deductions: number;
  net_salary: number;
  payslip_url: string | null;
}

export interface YearToDateReport {
  staff_id: string;
  staff_name: string;
  staff_code: string;
  year: number;
  entries: YearToDateEntry[];
  totals: {
    gross_salary: number;
    paye_tax: number;
    ssnit_employee: number;
    total_deductions: number;
    net_salary: number;
  };
}

export interface PayrollAuditLogEntry {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  field_name: string | null;
  old_value: string | null;
  new_value: string | null;
  reason: string | null;
  performed_by: string;
  performed_by_name: string | null;
  performed_at: string;
  ip_address: string | null;
}

export interface PayrollAuditLogResponse {
  items: PayrollAuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface BulkPayslipStatus {
  run_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  total: number;
  completed: number;
  failed: number;
}

export interface BankFileResult {
  url: string;
  file_name: string;
  total_amount: number;
  staff_count: number;
  by_payment_method: PayrollPaymentMethodBreakdown[];
}
