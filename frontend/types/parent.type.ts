/**
 * SIMS Plus - Parent Portal Type Definitions
 *
 * Types for the parent-facing portal (Sprint 13-14). These are intentionally
 * separate from admin-facing types because the parent API returns simplified,
 * read-only views of student data, grades, finance, and attendance.
 */

// =========================
// Child / Student Types (parent read-only view)
// =========================

export interface ChildSummary {
  id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  photo_url: string | null;
  class_name: string;
  section_name: string | null;
  admission_number: string;
  date_of_birth: string;
  gender: string;
  /** School ID -- present when the student is assigned to a school (chain tenants) */
  school_id?: string;
  /** School name -- useful for chain tenants where children attend different schools */
  school_name?: string;
}

export interface ChildDetail extends ChildSummary {
  enrollment_status: string;
  class_teacher_name: string | null;
  current_term: string;
  academic_year: string;
  class_id: string;
  section_id: string | null;
}

export interface QuickStats {
  attendance_rate: number;
  average_score: number | null;
  class_position: number | null;
  class_size: number | null;
  outstanding_balance: number;
}

export interface ChildOverview {
  child: ChildDetail;
  stats: QuickStats;
  recent_activity: ActivityItem[];
}

// =========================
// Grades Types
// =========================

export interface SubjectGrade {
  subject_id: string;
  subject_name: string;
  ca_score: number | null;
  ca_max: number;
  exam_score: number | null;
  exam_max: number;
  total: number | null;
  grade: string | null;
  remark: string | null;
  class_average: number | null;
  position: number | null;
}

export interface TermGrades {
  student: ChildSummary;
  term: { id: string; name: string; academic_year: string };
  subjects: SubjectGrade[];
  overall: {
    total_marks: number;
    average: number;
    class_position: number;
    class_size: number;
  };
}

export interface GradeTrend {
  term_id: string;
  term_name: string;
  average: number;
  position: number;
  class_size: number;
}

export interface AssessmentScore {
  id: string;
  subject_name: string;
  assessment_name: string;
  score: number;
  max_score: number;
  percentage: number;
  date: string;
}

// =========================
// Finance Types (parent view)
// =========================

export type ParentInvoiceStatus =
  | "draft"
  | "issued"
  | "partial"
  | "paid"
  | "overdue"
  | "cancelled"
  | "write_off";

export interface ParentInvoiceSummary {
  id: string;
  invoice_number: string;
  term_name: string;
  total_amount: number;
  amount_paid: number;
  balance: number;
  status: ParentInvoiceStatus;
  due_date: string | null;
  created_at: string;
}

export interface ParentInvoiceItem {
  id: string;
  fee_type_name: string;
  amount: number;
  description: string | null;
}

export interface ParentPaymentRecord {
  id: string;
  amount: number;
  method: string;
  reference_number: string | null;
  receipt_number: string;
  date: string;
  invoice_number: string;
}

export interface ParentInvoiceDetail extends ParentInvoiceSummary {
  items: ParentInvoiceItem[];
  payments: ParentPaymentRecord[];
  scholarship_discount: number;
  credit_notes_applied: number;
}

export interface FeeStatement {
  student: ChildSummary;
  term: { id: string; name: string };
  total_billed: number;
  total_paid: number;
  total_credits: number;
  outstanding_balance: number;
  invoices: ParentInvoiceSummary[];
}

export type ParentPaymentMethod = "mobile_money" | "card";

export interface PaymentInitiateRequest {
  invoice_id: string;
  amount: number;
  method: ParentPaymentMethod;
  phone?: string;
}

export interface PaymentInitiateResponse {
  authorization_url: string;
  reference: string;
  access_code: string;
}

export interface PaymentVerifyResponse {
  status: "success" | "failed" | "pending";
  amount: number;
  method: string;
  receipt_number: string | null;
  invoice_number: string;
  balance_remaining: number;
}

// =========================
// Attendance Types (parent view)
// =========================

export type ParentAttendanceStatus =
  | "present"
  | "absent"
  | "late"
  | "excused"
  | "sick";

export interface AttendanceDay {
  date: string;
  status: ParentAttendanceStatus;
  note: string | null;
}

export interface AttendanceSummary {
  student: ChildSummary;
  month: string;
  total_school_days: number;
  present: number;
  absent: number;
  late: number;
  excused: number;
  rate: number;
  daily: AttendanceDay[];
}

export interface AttendanceTrend {
  month: string;
  rate: number;
  present: number;
  total_days: number;
}

// =========================
// Communication Types
// =========================

export type AnnouncementTarget =
  | "all_parents"
  | "specific_class"
  | "specific_house"
  | "boarding_parents"
  | "transport_parents";

export type AnnouncementPriority = "normal" | "important" | "urgent";

export type AnnouncementStatus = "draft" | "published";

export type NoteType = "positive" | "concern" | "information" | "action_required";

export interface Announcement {
  id: string;
  title: string;
  content: string;
  author_name: string;
  target_audience: AnnouncementTarget;
  target_class_id: string | null;
  target_class_name: string | null;
  target_house_id: string | null;
  target_house_name: string | null;
  priority: AnnouncementPriority;
  status: AnnouncementStatus;
  published_at: string | null;
  expires_at: string | null;
  is_pinned: boolean;
  attachment_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface AnnouncementCreate {
  title: string;
  content: string;
  target_audience: AnnouncementTarget;
  target_class_id?: string;
  target_house_id?: string;
  priority: AnnouncementPriority;
  expires_at?: string;
  is_pinned?: boolean;
  attachment_url?: string;
}

export interface AnnouncementUpdate extends Partial<AnnouncementCreate> {}

export interface AnnouncementListResponse {
  items: Announcement[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TeacherNote {
  id: string;
  student_id: string;
  student_name: string;
  teacher_id: string;
  teacher_name: string;
  subject_id: string | null;
  subject_name: string | null;
  note_type: NoteType;
  content: string;
  is_visible_to_parent: boolean;
  parent_acknowledged: boolean;
  parent_acknowledged_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TeacherNoteCreate {
  student_id: string;
  subject_id?: string;
  note_type: NoteType;
  content: string;
  is_visible_to_parent?: boolean;
}

export interface TeacherNoteUpdate {
  subject_id?: string;
  note_type?: NoteType;
  content?: string;
  is_visible_to_parent?: boolean;
}

export interface TeacherNoteListResponse {
  items: TeacherNote[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// =========================
// Notification Preferences Types
// =========================

export interface NotificationPreferences {
  id: string;
  email_enabled: boolean;
  sms_enabled: boolean;
  push_enabled: boolean;
  notify_attendance: boolean;
  notify_grades: boolean;
  notify_finance: boolean;
  notify_announcements: boolean;
  notify_transport: boolean;
  notify_boarding: boolean;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
}

export interface NotificationPreferencesUpdate {
  email_enabled?: boolean;
  sms_enabled?: boolean;
  push_enabled?: boolean;
  notify_attendance?: boolean;
  notify_grades?: boolean;
  notify_finance?: boolean;
  notify_announcements?: boolean;
  notify_transport?: boolean;
  notify_boarding?: boolean;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
}

// =========================
// Dashboard / Activity Types
// =========================

export type ActivityType =
  | "grade"
  | "attendance"
  | "finance"
  | "announcement"
  | "report"
  | "note";

export interface ActivityItem {
  id: string;
  type: ActivityType;
  title: string;
  description: string;
  date: string;
  link: string | null;
  metadata?: Record<string, unknown>;
}

export interface ParentDashboardData {
  children: ChildSummary[];
  overview: ChildOverview | null;
  announcements: Announcement[];
  upcoming: UpcomingItem[];
}

export interface UpcomingItem {
  type: "exam" | "term_start" | "term_end" | "payment_due" | "holiday";
  title: string;
  date: string;
  description: string | null;
  is_overdue?: boolean;
}

// =========================
// Parent Onboarding Types
// =========================

export interface ParentInvitation {
  email: string;
  phone?: string;
  first_name: string;
  last_name: string;
  relationship: string;
}

export interface BulkParentInviteResult {
  created: number;
  linked: number;
  errors: { email: string; error: string }[];
}

export interface ParentProfileCompletion {
  first_name: string;
  last_name: string;
  phone: string;
  relationship: string;
  notification_preferences: NotificationPreferencesUpdate;
}

export interface ParentOnboardingStatus {
  is_complete: boolean;
  has_set_password: boolean;
  has_completed_profile: boolean;
  has_set_notifications: boolean;
}

// =========================
// Parent Engagement (Admin Dashboard)
// =========================

export interface ParentEngagementStats {
  total_parents: number;
  registered_parents: number;
  active_this_week: number;
  announcements_read_rate: number;
  notes_acknowledged_rate: number;
  online_payments_this_month: number;
  online_payments_amount: number;
}

// =========================
// Boarding / Transport Parent View
// =========================

export interface ChildBoardingInfo {
  house_name: string;
  dormitory_name: string;
  bed_number: string | null;
  house_parent_name: string;
  house_parent_phone: string | null;
  recent_roll_calls: { date: string; status: string }[];
  active_exeats: {
    id: string;
    type: string;
    start_date: string;
    end_date: string;
    status: string;
  }[];
}

export interface ChildTransportInfo {
  route_name: string;
  route_number: string | null;
  pickup_stop: string;
  pickup_time: string;
  dropoff_stop: string;
  dropoff_time: string;
  driver_name: string;
  driver_phone: string;
  vehicle_registration: string;
}
