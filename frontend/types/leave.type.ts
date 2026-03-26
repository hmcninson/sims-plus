/**
 * Leave Management Types
 * Mirrors backend schemas from app/schemas/leave.py
 */

// =========================
// Leave Types
// =========================

export interface LeaveType {
  id: string;
  name: string;
  code: string;
  description?: string;
  default_days_per_year: number;
  max_carryover_days: number;
  is_paid: boolean;
  requires_approval: boolean;
  is_active: boolean;
  color?: string;
  created_at: string;
}

export interface LeaveTypeCreate {
  name: string;
  code: string;
  description?: string;
  default_days_per_year: number;
  max_carryover_days?: number;
  is_paid?: boolean;
  requires_approval?: boolean;
  color?: string;
}

export interface LeaveTypeUpdate {
  name?: string;
  description?: string;
  default_days_per_year?: number;
  max_carryover_days?: number;
  is_paid?: boolean;
  requires_approval?: boolean;
  is_active?: boolean;
  color?: string;
}

// =========================
// Leave Balances
// =========================

export interface LeaveBalance {
  id: string;
  staff_id: string;
  staff_name?: string;
  leave_type_id: string;
  leave_type_name?: string;
  academic_year_id: string;
  entitled_days: number;
  used_days: number;
  pending_days: number;
  carried_over: number;
  remaining_days: number;
}

export interface LeaveBalanceAdjust {
  entitled_days?: number;
  carried_over?: number;
  reason: string;
}

export interface LeaveBalanceInitialize {
  academic_year_id: string;
  carry_over_from_previous?: boolean;
}

// =========================
// Leave Requests
// =========================

export type LeaveRequestStatus = "pending" | "approved" | "rejected" | "cancelled";

export interface LeaveRequest {
  id: string;
  staff_id: string;
  staff_name?: string;
  leave_type_id: string;
  leave_type_name?: string;
  leave_type_color?: string;
  start_date: string;
  end_date: string;
  days_requested: number;
  reason: string;
  status: LeaveRequestStatus;
  reviewed_by?: string;
  reviewer_name?: string;
  reviewed_at?: string;
  review_notes?: string;
  created_at: string;
}

export interface LeaveRequestCreate {
  leave_type_id: string;
  start_date: string;
  end_date: string;
  reason: string;
}

export interface LeaveRequestUpdate {
  start_date?: string;
  end_date?: string;
  reason?: string;
}

export interface LeaveApproval {
  notes?: string;
}

// =========================
// Leave Calendar
// =========================

export interface LeaveCalendarEntry {
  staff_id: string;
  staff_name: string;
  leave_type_name: string;
  leave_type_color?: string;
  start_date: string;
  end_date: string;
  days: number;
  status: string;
}

// =========================
// Staff Workload
// =========================

export interface StaffWorkloadSection {
  section_id: string;
  section_name: string;
  class_name: string;
  subject_name?: string;
  is_class_teacher: boolean;
  periods_per_week: number;
}

export interface StaffWorkloadResponse {
  staff_id: string;
  staff_name: string;
  total_periods_per_week: number;
  total_sections: number;
  class_teacher_of?: string;
  subjects_taught: string[];
  sections: StaffWorkloadSection[];
}

export interface StaffWorkloadSummaryItem {
  staff_id: string;
  staff_name: string;
  department?: string;
  total_sections: number;
  total_periods_per_week: number;
  is_class_teacher: boolean;
  class_teacher_of?: string;
}
