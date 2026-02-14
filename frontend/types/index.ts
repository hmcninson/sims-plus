/**
 * SIMS Plus - TypeScript Type Definitions
 */

// =========================
// User & Auth Types
// =========================

export type UserRole =
  | "platform_admin"
  | "chain_admin"
  | "school_admin"
  | "academic_head"
  | "finance_officer"
  | "teacher"
  | "house_parent"
  | "parent"
  | "student";

export type UserStatus = "pending" | "active" | "suspended" | "deactivated";

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  role: UserRole;
  status: UserStatus;
  tenant_id?: string;
  school_id?: string;
  avatar_url?: string;
  email_verified: boolean;
  mfa_enabled: boolean;
  last_login?: string;
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
  role: UserRole;
  school_id?: string;
}

export interface UserUpdate {
  first_name?: string;
  last_name?: string;
  phone?: string;
  role?: UserRole;
  status?: UserStatus;
  school_id?: string;
}

export interface UserListResponse {
  items: User[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  school_name: string;
  subdomain: string;
  school_type: string;
  admin_email: string;
  admin_first_name: string;
  admin_last_name: string;
  admin_password: string;
  admin_phone?: string;
  plan?: string;
}

export interface RegistrationResponse {
  success: boolean;
  message: string;
  tenant_id: string;
  school_id: string;
  admin_user_id: string;
  subdomain: string;
  portal_url: string;
  admin_email: string;
  trial_ends_at?: string;
}

// =========================
// Tenant & School Types
// =========================

export type TenantType = "single_school" | "school_chain";
export type SubscriptionTier = "trial" | "starter" | "professional" | "enterprise";

export interface TenantBranding {
  logo_url: string | null;
  primary_color: string | null;
}

export interface TenantPublic {
  id: string;
  name: string;
  subdomain: string;
  tenant_type: TenantType;
  is_active: boolean;
  branding: TenantBranding | null;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  subdomain: string;
  tenant_type: TenantType;
  subscription_tier: SubscriptionTier;
  subscription_start?: string;
  subscription_end?: string;
  max_students: number;
  email?: string;
  phone?: string;
  is_active: boolean;
  logo_url?: string;
  primary_color?: string;
  created_at: string;
}

export interface SubdomainCheckResponse {
  subdomain: string;
  available: boolean;
  reason: string | null;
}

export interface TenantValidationResponse {
  valid: boolean;
  tenant: TenantPublic | null;
  error: string | null;
}

export interface School {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  code?: string;
  address?: string;
  city?: string;
  region?: string;
  phone?: string;
  email?: string;
  website?: string;
  logo_url?: string;
  primary_color?: string;
  motto?: string;
  description?: string;
  year_established?: number;
  uses_boarding?: boolean;
  uses_transport?: boolean;
  is_active: boolean;
}

// =========================
// Student Types
// =========================

export type Gender = "male" | "female";
export type StudentStatus =
  | "active"
  | "inactive"
  | "graduated"
  | "withdrawn"
  | "transferred"
  | "suspended";
export type GuardianRelationship =
  | "father"
  | "mother"
  | "guardian"
  | "grandfather"
  | "grandmother"
  | "uncle"
  | "aunt"
  | "sibling"
  | "other";

export interface Student {
  id: string;
  student_id: string; // System-generated (e.g., STU-2026-001)
  previous_student_id?: string; // ID from previous/external system
  first_name: string;
  middle_name?: string;
  last_name: string;
  date_of_birth: string;
  gender: Gender;
  email?: string;
  phone?: string;
  address?: string;
  city?: string;
  region?: string;
  ghana_card_number?: string;
  nhis_number?: string;
  school_id?: string;
  class_id?: string;
  section_id?: string;
  admission_date?: string;
  admission_number?: string;
  status: StudentStatus;
  is_boarder: boolean;
  blood_group?: string;
  medical_conditions?: string;
  allergies?: string;
  photo_url?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface StudentListItem {
  id: string;
  student_id: string; // System-generated
  previous_student_id?: string; // ID from previous/external system
  first_name: string;
  middle_name?: string;
  last_name: string;
  gender: Gender;
  date_of_birth: string;
  status: StudentStatus;
  class_id?: string;
  class_name?: string;
  section_id?: string;
  section_name?: string;
  photo_url?: string;
}

export interface StudentWithGuardians extends Student {
  guardians: StudentGuardianLink[];
  school_name?: string;
  class_name?: string;
  section_name?: string;
}

export interface StudentCreate {
  // Note: student_id is always auto-generated by the system
  previous_student_id?: string; // ID from previous/external system (for migration)
  first_name: string;
  middle_name?: string;
  last_name: string;
  date_of_birth: string;
  gender: Gender;
  email?: string;
  phone?: string;
  address?: string;
  city?: string;
  region?: string;
  ghana_card_number?: string;
  nhis_number?: string;
  school_id?: string;
  class_id?: string;
  section_id?: string;
  admission_date?: string;
  admission_number?: string;
  status?: StudentStatus;
  is_boarder?: boolean;
  blood_group?: string;
  medical_conditions?: string;
  allergies?: string;
  photo_url?: string;
  notes?: string;
  guardians?: GuardianWithRelationship[];
}

export interface StudentUpdate {
  // Note: student_id cannot be changed (system-generated)
  previous_student_id?: string; // ID from previous/external system
  first_name?: string;
  middle_name?: string;
  last_name?: string;
  date_of_birth?: string;
  gender?: Gender;
  email?: string;
  phone?: string;
  address?: string;
  city?: string;
  region?: string;
  ghana_card_number?: string;
  nhis_number?: string;
  school_id?: string;
  class_id?: string;
  section_id?: string;
  admission_date?: string;
  admission_number?: string;
  status?: StudentStatus;
  is_boarder?: boolean;
  blood_group?: string;
  medical_conditions?: string;
  allergies?: string;
  photo_url?: string;
  notes?: string;
}

export interface StudentStats {
  total: number;
  active: number;
  inactive: number;
  graduated: number;
  transferred: number;
  withdrawn: number;
  suspended: number;
  male: number;
  female: number;
  boarders: number;
  day_students: number;
}

export interface StudentBulkResponse {
  created: number;
  failed: number;
  errors: Array<{
    index: number;
    student_id: string;
    error: string;
  }>;
}

// =========================
// Guardian Types
// =========================

export interface Guardian {
  id: string;
  first_name: string;
  last_name: string;
  phone: string;
  phone_secondary?: string;
  email?: string;
  address?: string;
  city?: string;
  region?: string;
  occupation?: string;
  workplace?: string;
  work_phone?: string;
  ghana_card_number?: string;
  photo_url?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  student_count?: number;
}

export interface GuardianCreate {
  first_name: string;
  last_name: string;
  phone: string;
  phone_secondary?: string;
  email?: string;
  address?: string;
  city?: string;
  region?: string;
  occupation?: string;
  workplace?: string;
  work_phone?: string;
  ghana_card_number?: string;
  photo_url?: string;
  notes?: string;
}

export interface GuardianUpdate {
  first_name?: string;
  last_name?: string;
  phone?: string;
  phone_secondary?: string;
  email?: string;
  address?: string;
  city?: string;
  region?: string;
  occupation?: string;
  workplace?: string;
  work_phone?: string;
  ghana_card_number?: string;
  photo_url?: string;
  notes?: string;
}

export interface StudentGuardianLink {
  id: string;
  student_id: string;
  guardian_id: string;
  relationship: GuardianRelationship;
  is_primary: boolean;
  is_emergency_contact: boolean;
  can_pickup: boolean;
  guardian: Guardian;
  created_at: string;
  updated_at: string;
}

export interface StudentGuardianCreate {
  guardian_id: string;
  relationship: GuardianRelationship;
  is_primary?: boolean;
  is_emergency_contact?: boolean;
  can_pickup?: boolean;
}

export interface GuardianWithRelationship {
  guardian: GuardianCreate;
  relationship: GuardianRelationship;
  is_primary?: boolean;
  is_emergency_contact?: boolean;
  can_pickup?: boolean;
}

export interface StudentGuardianUpdate {
  relationship?: GuardianRelationship;
  is_primary?: boolean;
  is_emergency_contact?: boolean;
  can_pickup?: boolean;
}

// =========================
// API Response Types
// =========================

export interface ActionResult<T = void> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

// =========================
// Academic Types
// =========================

export type AcademicYearStatus = "planning" | "active" | "completed";
export type TermStatus = "upcoming" | "active" | "completed";
export type ClassLevel = "preschool" | "primary" | "jhs" | "shs";
export type SubjectCategory = "core" | "elective" | "vocational" | "extra";
export type GradingScaleType = "waec" | "gpa" | "percentage" | "custom";

export interface AcademicYear {
  id: string;
  name: string;
  description?: string;
  start_date: string;
  end_date: string;
  status: AcademicYearStatus;
  is_current: boolean;
  created_at: string;
  updated_at: string;
  terms?: Term[];
}

export interface AcademicYearCreate {
  name: string;
  description?: string;
  start_date: string;
  end_date: string;
  is_current?: boolean;
}

export interface AcademicYearUpdate {
  name?: string;
  description?: string;
  start_date?: string;
  end_date?: string;
  status?: AcademicYearStatus;
  is_current?: boolean;
}

export interface Term {
  id: string;
  academic_year_id: string;
  name: string;
  short_name?: string;
  sequence: number;
  start_date: string;
  end_date: string;
  status: TermStatus;
  is_current: boolean;
  created_at: string;
  updated_at: string;
}

export interface TermCreate {
  academic_year_id: string;
  name: string;
  short_name?: string;
  sequence?: number;
  start_date: string;
  end_date: string;
}

export interface TermUpdate {
  name?: string;
  short_name?: string;
  sequence?: number;
  start_date?: string;
  end_date?: string;
  status?: TermStatus;
  is_current?: boolean;
}

export interface Class {
  id: string;
  name: string;
  short_name?: string;
  level?: ClassLevel;
  sequence: number;
  capacity?: number;
  school_id?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  sections?: ClassSection[];
  // Student enrollment counts
  student_count?: number;
  male_count?: number;
  female_count?: number;
}

export interface ClassCreate {
  name: string;
  short_name?: string;
  level?: ClassLevel;
  sequence?: number;
  capacity?: number;
  school_id?: string;
}

export interface ClassUpdate {
  name?: string;
  short_name?: string;
  level?: ClassLevel;
  sequence?: number;
  capacity?: number;
  is_active?: boolean;
}

export interface ClassSection {
  id: string;
  class_id: string;
  name: string;
  capacity?: number;
  class_teacher_id?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  // Student enrollment counts
  student_count?: number;
  male_count?: number;
  female_count?: number;
}

export interface ClassSectionCreate {
  class_id: string;
  name: string;
  capacity?: number;
  class_teacher_id?: string;
}

export interface ClassSectionUpdate {
  name?: string;
  capacity?: number;
  class_teacher_id?: string;
  is_active?: boolean;
}

export interface Subject {
  id: string;
  name: string;
  code: string;
  description?: string;
  category: SubjectCategory;
  applicable_levels?: ClassLevel[] | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SubjectCreate {
  name: string;
  code: string;
  description?: string;
  category?: SubjectCategory;
  applicable_levels?: ClassLevel[];
}

export interface SubjectUpdate {
  name?: string;
  code?: string;
  description?: string;
  category?: SubjectCategory;
  applicable_levels?: ClassLevel[];
  is_active?: boolean;
}

export interface ClassSubject {
  id: string;
  class_id: string;
  subject_id: string;
  periods_per_week?: number;
  is_compulsory: boolean;
  created_at: string;
  subject?: Subject;
}

export interface ClassSubjectCreate {
  class_id: string;
  subject_id: string;
  periods_per_week?: number;
  is_compulsory?: boolean;
}

export interface Grade {
  id: string;
  grading_scale_id: string;
  grade: string;
  min_score: number;
  max_score: number;
  grade_point?: number;
  remark?: string;
}

export interface GradeCreate {
  grade: string;
  min_score: number;
  max_score: number;
  grade_point?: number;
  remark?: string;
}

export interface GradingScale {
  id: string;
  name: string;
  description?: string;
  scale_type: GradingScaleType;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  grades?: Grade[];
}

export interface GradingScaleCreate {
  name: string;
  description?: string;
  scale_type?: GradingScaleType;
  is_default?: boolean;
  grades?: GradeCreate[];
}

export interface GradingScaleUpdate {
  name?: string;
  description?: string;
  scale_type?: GradingScaleType;
  is_default?: boolean;
  is_active?: boolean;
}

export interface AssessmentWeight {
  id: string;
  academic_year_id?: string;
  class_work_weight: number;
  homework_weight: number;
  midterm_weight: number;
  end_term_weight: number;
  // Report card weights (CA vs Exam split)
  ca_total_weight: number;
  exam_total_weight: number;
  created_at: string;
  updated_at: string;
}

export interface AssessmentWeightCreate {
  academic_year_id?: string;
  class_work_weight?: number;
  homework_weight?: number;
  midterm_weight?: number;
  end_term_weight?: number;
  // Report card weights (CA vs Exam split)
  ca_total_weight?: number;
  exam_total_weight?: number;
}

export interface AcademicSettings {
  id?: string;
  auto_promote_students: boolean;
  allow_grade_amendments: boolean;
  show_position_on_report_cards: boolean;
  require_attendance_for_exams: boolean;
  enable_continuous_assessment: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface AcademicSettingsUpdate {
  auto_promote_students?: boolean;
  allow_grade_amendments?: boolean;
  show_position_on_report_cards?: boolean;
  require_attendance_for_exams?: boolean;
  enable_continuous_assessment?: boolean;
}

// =========================
// Staff Types
// =========================

export type StaffType = "teaching" | "non_teaching" | "administrative";
export type StaffStatus = "active" | "on_leave" | "suspended" | "terminated" | "retired";

export interface Staff {
  id: string;
  staff_id: string;
  first_name: string;
  middle_name?: string;
  last_name: string;
  date_of_birth?: string;
  gender: Gender;
  email: string;
  phone: string;
  phone_secondary?: string;
  address?: string;
  city?: string;
  region?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  emergency_contact_relationship?: string;
  ghana_card_number?: string;
  ssnit_number?: string;
  teacher_license_number?: string;
  staff_type: StaffType;
  status: StaffStatus;
  job_title: string;
  department?: string;
  employment_date: string;
  termination_date?: string;
  qualifications?: Record<string, unknown>[];
  bank_name?: string;
  bank_branch?: string;
  account_number?: string;
  photo_url?: string;
  notes?: string;
  school_id?: string;
  user_id?: string;
  school_name?: string;
  created_at: string;
  updated_at: string;
}

export interface StaffListItem {
  id: string;
  staff_id: string;
  first_name: string;
  middle_name?: string;
  last_name: string;
  gender: Gender;
  email: string;
  phone: string;
  staff_type: StaffType;
  status: StaffStatus;
  job_title: string;
  department?: string;
  photo_url?: string;
}

export interface StaffCreate {
  staff_id?: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  gender: Gender;
  job_title: string;
  employment_date: string;
  middle_name?: string;
  date_of_birth?: string;
  phone_secondary?: string;
  address?: string;
  city?: string;
  region?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  emergency_contact_relationship?: string;
  ghana_card_number?: string;
  ssnit_number?: string;
  teacher_license_number?: string;
  staff_type?: StaffType;
  status?: StaffStatus;
  department?: string;
  termination_date?: string;
  qualifications?: Record<string, unknown>[];
  bank_name?: string;
  bank_branch?: string;
  account_number?: string;
  photo_url?: string;
  notes?: string;
  school_id?: string;
  user_id?: string;
}

export interface StaffUpdate {
  first_name?: string;
  middle_name?: string;
  last_name?: string;
  date_of_birth?: string;
  gender?: Gender;
  email?: string;
  phone?: string;
  phone_secondary?: string;
  address?: string;
  city?: string;
  region?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  emergency_contact_relationship?: string;
  ghana_card_number?: string;
  ssnit_number?: string;
  teacher_license_number?: string;
  staff_type?: StaffType;
  status?: StaffStatus;
  job_title?: string;
  department?: string;
  employment_date?: string;
  termination_date?: string;
  qualifications?: Record<string, unknown>[];
  bank_name?: string;
  bank_branch?: string;
  account_number?: string;
  photo_url?: string;
  notes?: string;
  school_id?: string;
  user_id?: string;
}

export interface StaffStats {
  total: number;
  active: number;
  on_leave: number;
  suspended: number;
  terminated: number;
  retired: number;
  teaching: number;
  non_teaching: number;
  administrative: number;
  male: number;
  female: number;
}

export interface StaffAssignment {
  id: string;
  staff_id: string;
  section_id: string;
  is_class_teacher: boolean;
  subject_id?: string;
  created_at: string;
  updated_at: string;
  section_name?: string;
  class_name?: string;
}

export interface StaffWithAssignments extends Staff {
  assignments: StaffAssignment[];
}

// =========================
// Attendance Types
// =========================

export type AttendanceStatus = "present" | "absent" | "late" | "excused" | "sick";

export interface StudentAttendance {
  id: string;
  student_id: string;
  section_id: string;
  date: string;
  status: AttendanceStatus;
  term_id?: string;
  check_in_time?: string;
  check_out_time?: string;
  remarks?: string;
  excuse_reason?: string;
  marked_by?: string;
  created_at: string;
  updated_at: string;
  student_name?: string;
  student_number?: string;
  section_name?: string;
}

export interface StudentAttendanceListItem {
  student_id: string;
  student_number: string;
  first_name: string;
  middle_name?: string;
  last_name: string;
  gender: Gender;
  photo_url?: string;
  attendance_id?: string;
  status?: AttendanceStatus;
  check_in_time?: string;
  remarks?: string;
}

export interface StudentAttendanceMark {
  student_id: string;
  section_id: string;
  date: string;
  status: AttendanceStatus;
  term_id?: string;
  check_in_time?: string;
  check_out_time?: string;
  remarks?: string;
  excuse_reason?: string;
}

export interface BulkStudentAttendanceRecord {
  student_id: string;
  status: AttendanceStatus;
  check_in_time?: string;
  remarks?: string;
  excuse_reason?: string;
}

export interface BulkStudentAttendanceMark {
  section_id: string;
  date: string;
  term_id?: string;
  records: BulkStudentAttendanceRecord[];
}

export interface StudentAttendanceSummary {
  total_days: number;
  present: number;
  absent: number;
  late: number;
  excused: number;
  sick: number;
  attendance_rate: number;
}

export interface SectionAttendanceSummary {
  date: string;
  total_students: number;
  marked: number;
  unmarked: number;
  present: number;
  absent: number;
  late: number;
  excused: number;
  sick: number;
  attendance_rate: number;
}

export interface DailyAttendanceReport {
  date: string;
  total_students: number;
  marked: number;
  unmarked: number;
  present: number;
  absent: number;
  late: number;
  excused: number;
  sick: number;
  attendance_rate: number;
  marking_rate: number;
}

export interface BulkAttendanceResult {
  created: number;
  updated: number;
  failed: number;
  errors: Array<{ student_id?: string; staff_id?: string; error: string }>;
}

export interface StaffAttendance {
  id: string;
  staff_id: string;
  date: string;
  status: AttendanceStatus;
  term_id?: string;
  check_in_time?: string;
  check_out_time?: string;
  remarks?: string;
  excuse_reason?: string;
  marked_by?: string;
  created_at: string;
  updated_at: string;
  staff_name?: string;
  staff_number?: string;
}

export interface StaffAttendanceMark {
  staff_id: string;
  date: string;
  status: AttendanceStatus;
  term_id?: string;
  check_in_time?: string;
  check_out_time?: string;
  remarks?: string;
  excuse_reason?: string;
}

export interface BulkStaffAttendanceRecord {
  staff_id: string;
  status: AttendanceStatus;
  check_in_time?: string;
  check_out_time?: string;
  remarks?: string;
  excuse_reason?: string;
}

export interface BulkStaffAttendanceMark {
  date: string;
  term_id?: string;
  records: BulkStaffAttendanceRecord[];
}

export interface StaffAttendanceSummary {
  total_days: number;
  present: number;
  absent: number;
  late: number;
  excused: number;
  sick: number;
  attendance_rate: number;
}

// =========================
// Exam Types
// =========================

export type ExamType = "quiz" | "midterm" | "end_term" | "mock" | "practical" | "project";
export type ExamStatus = "draft" | "scheduled" | "ongoing" | "completed" | "results_published" | "cancelled";
export type ExamSubjectStatus = "pending" | "scores_entered" | "submitted" | "published";
export type AssessmentType = "class_work" | "homework" | "test" | "project" | "assignment";

export interface Exam {
  id: string;
  academic_year_id: string;
  term_id: string;
  name: string;
  exam_type: ExamType;
  description?: string;
  start_date?: string;
  end_date?: string;
  status: ExamStatus;
  created_by?: string;
  created_at: string;
  updated_at: string;
  academic_year_name?: string;
  term_name?: string;
  subjects_count?: number;
}

export interface ExamCreate {
  academic_year_id: string;
  term_id: string;
  name: string;
  exam_type: ExamType;
  description?: string;
  start_date?: string;
  end_date?: string;
  status?: ExamStatus;
}

export interface ExamUpdate {
  name?: string;
  exam_type?: ExamType;
  description?: string;
  start_date?: string;
  end_date?: string;
  status?: ExamStatus;
}

export interface ExamWithContext extends Exam {
  academic_year_name?: string;
  term_name?: string;
  subjects_count: number;
}

export interface ExamSubject {
  id: string;
  exam_id: string;
  subject_id: string;
  class_id: string;
  section_id?: string;
  grading_scale_id?: string;
  max_score: number;
  pass_mark: number;
  exam_date?: string;
  exam_time?: string;
  duration_minutes?: number;
  venue?: string;
  status: ExamSubjectStatus;
  created_at: string;
  updated_at: string;
}

export interface ExamSubjectWithDetails extends ExamSubject {
  subject_name: string;
  subject_code: string;
  class_name: string;
  class_sequence: number;
  section_name?: string;
  grading_scale_name?: string;
  scores_count: number;
  students_count: number;
}

export interface ExamSubjectCreate {
  subject_id: string;
  class_id: string;
  section_id?: string;
  grading_scale_id?: string;
  max_score?: number;
  pass_mark?: number;
  exam_date?: string;
  exam_time?: string;
  duration_minutes?: number;
  venue?: string;
}

export interface ExamSubjectBulkCreate {
  class_ids: string[];
  section_ids?: string[];
  subject_ids: string[];
  grading_scale_id?: string;
  max_score?: number;
  pass_mark?: number;
}

export interface ExamSubjectAutoPopulate {
  class_ids: string[];
  section_ids?: string[];
  grading_scale_id?: string;
  max_score?: number;
  pass_mark?: number;
}

export interface ExamSubjectUpdate {
  max_score?: number;
  pass_mark?: number;
  exam_date?: string;
  exam_time?: string;
  duration_minutes?: number;
  venue?: string;
  status?: ExamSubjectStatus;
}

export interface ExamScore {
  id: string;
  exam_subject_id: string;
  student_id: string;
  score?: number;
  grade?: string;
  grade_point?: number;
  grade_remark?: string;
  is_absent: boolean;
  teacher_remark?: string;
  entered_by?: string;
  entered_at: string;
  updated_at: string;
}

export interface ExamScoreWithStudent extends ExamScore {
  student_name: string;
  student_number: string;
}

export interface ScoreEntry {
  student_id: string;
  score?: number;
  is_absent?: boolean;
  teacher_remark?: string;
}

export interface ExamScoreBulkCreate {
  grading_scale_id?: string;
  scores: ScoreEntry[];
}

export interface ExamScoreUpdate {
  score?: number;
  is_absent?: boolean;
  teacher_remark?: string;
  grading_scale_id?: string;
}

export interface ScoreEntryForm {
  exam_subject_id: string;
  subject_name: string;
  subject_code?: string;
  class_id: string;
  class_name: string;
  section_id?: string;
  section_name?: string;
  max_score: number;
  pass_mark: number;
  grading_scale_id?: string;
  students: ScoreEntryStudent[];
}

export interface ScoreEntryStudent {
  student_id: string;
  student_number: string;
  first_name: string;
  last_name: string;
  section_id?: string;
  section_name?: string;
  current_score?: number;
  current_grade?: string;
  is_absent: boolean;
  teacher_remark?: string;
}

export interface BulkScoreResult {
  created: number;
  updated: number;
  failed: number;
  errors: Array<{ student_id: string; error: string }>;
}

export interface ContinuousAssessment {
  id: string;
  academic_year_id: string;
  term_id: string;
  class_id: string;
  subject_id: string;
  student_id: string;
  assessment_type: AssessmentType;
  title: string;
  max_score: number;
  score?: number;
  assessment_date: string;
  entered_by?: string;
  created_at: string;
  updated_at: string;
}

export interface CAWithDetails extends ContinuousAssessment {
  class_name: string;
  subject_name: string;
  subject_code?: string;
  student_name: string;
  student_id_number: string;
}

export interface CACreate {
  academic_year_id: string;
  term_id: string;
  class_id: string;
  subject_id: string;
  student_id: string;
  assessment_type: AssessmentType;
  title: string;
  max_score?: number;
  score?: number;
  date: string;
}

export interface CABulkEntry {
  student_id: string;
  score?: number;
}

export interface CABulkCreate {
  academic_year_id: string;
  term_id: string;
  class_id: string;
  subject_id: string;
  assessment_type: AssessmentType;
  title: string;
  max_score?: number;
  date: string;
  entries: CABulkEntry[];
}

export interface CAUpdate {
  assessment_type?: AssessmentType;
  title?: string;
  max_score?: number;
  score?: number;
  assessment_date?: string;
}

export interface CASummary {
  student_id: string;
  student_name: string;
  student_number: string;
  subject_id: string;
  subject_name: string;
  class_work_total: number;
  class_work_max: number;
  homework_total: number;
  homework_max: number;
  test_total: number;
  test_max: number;
  project_total: number;
  project_max: number;
  assignment_total: number;
  assignment_max: number;
  overall_total: number;
  overall_max: number;
  percentage: number;
}

export interface TermReport {
  id: string;
  academic_year_id: string;
  term_id: string;
  student_id: string;
  class_id: string;
  section_id: string;
  total_score: number;
  average_score: number;
  class_position?: number;
  section_position?: number;
  attendance_percentage?: number;
  days_present: number;
  days_absent: number;
  total_school_days: number;
  conduct_grade?: string;
  interest?: string;
  class_teacher_remark?: string;
  headmaster_remark?: string;
  is_published: boolean;
  published_at?: string;
  created_at: string;
  updated_at: string;
}

export interface TermReportWithDetails extends TermReport {
  student_name: string;
  student_id_number: string;
  class_name: string;
  section_name?: string;
  academic_year_name: string;
  term_name: string;
  subject_results: SubjectResult[];
  class_size?: number;
  subjects_count?: number;
}

export interface TermReportGenerate {
  academic_year_id: string;
  term_id: string;
  class_id: string;
  section_id?: string;
}

export interface TermReportRemarksUpdate {
  class_teacher_remark?: string;
  headmaster_remark?: string;
  conduct_grade?: string;
  interest?: string;
}

/**
 * Subject result for Ghana's assessment structure.
 * Class Score (50%) + Exams Score (50%) = Total (100%)
 */
export interface SubjectResult {
  subject_id: string;
  subject_name: string;
  subject_code?: string;
  // Raw scores for reference
  ca_score?: number;       // Combined CA raw score
  ca_max?: number;         // Combined CA max score
  end_term_score?: number; // End term raw score
  end_term_max?: number;   // End term max score
  // Normalized scores for report card (Ghana 50/50 system)
  class_score?: number;    // CA normalized to 50
  exams_score?: number;    // End term normalized to 50
  total_score?: number;    // Total out of 100
  grade?: string;
  grade_point?: number;
  grade_remark?: string;
  teacher_remark?: string;
  subject_position?: number;
  is_absent?: boolean;
}

export interface StudentExamResult {
  student_id: string;
  student_name: string;
  student_id_number: string;
  class_name: string;
  section_name?: string;
  subjects: SubjectResult[];
  total_score: number;
  average_score: number;
  subjects_count: number;
  class_position: number;
  section_position?: number;
  class_size: number;
  section_size?: number;
}

export interface ClassResultsResponse {
  exam_id: string;
  exam_name: string;
  class_id: string;
  class_name: string;
  term_name: string;
  students: StudentExamResult[];
  class_average: number;
  highest_score: number;
  lowest_score: number;
}

// =========================
// Preschool Types
// =========================

export type ObservationType = "anecdote" | "milestone" | "photo" | "video" | "incident";
export type MoodType = "happy" | "tired" | "upset" | "excited" | "calm" | "sick";
export type MealAmount = "none" | "little" | "some" | "most" | "all";
export type NapQuality = "good" | "restless" | "didnt_sleep";

export interface LearningArea {
  id: string;
  tenant_id: string;
  name: string;
  code: string;
  description?: string;
  icon?: string;
  color?: string;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  skills?: DevelopmentalSkill[];
}

export interface LearningAreaCreate {
  name: string;
  code: string;
  description?: string;
  icon?: string;
  color?: string;
  display_order?: number;
  is_active?: boolean;
}

export interface LearningAreaUpdate {
  name?: string;
  code?: string;
  description?: string;
  icon?: string;
  color?: string;
  display_order?: number;
  is_active?: boolean;
}

export interface DevelopmentalSkill {
  id: string;
  tenant_id: string;
  learning_area_id: string;
  name: string;
  description?: string;
  age_range_months_min?: number;
  age_range_months_max?: number;
  display_order: number;
  is_active: boolean;
  applicable_levels?: string[];
  created_at: string;
  updated_at: string;
}

export interface DevelopmentalSkillCreate {
  learning_area_id: string;
  name: string;
  description?: string;
  age_range_months_min?: number;
  age_range_months_max?: number;
  display_order?: number;
  is_active?: boolean;
  applicable_levels?: string[];
}

export interface DevelopmentalSkillUpdate {
  name?: string;
  description?: string;
  age_range_months_min?: number;
  age_range_months_max?: number;
  display_order?: number;
  is_active?: boolean;
  applicable_levels?: string[];
}

export interface PreschoolRating {
  id: string;
  scale_id: string;
  name: string;
  short_code: string;
  description?: string;
  numeric_value: number;
  color?: string;
  icon?: string;
  display_order: number;
  created_at: string;
  updated_at: string;
}

export interface PreschoolRatingCreate {
  name: string;
  short_code: string;
  description?: string;
  numeric_value: number;
  color?: string;
  icon?: string;
  display_order?: number;
}

export interface PreschoolRatingScale {
  id: string;
  tenant_id: string;
  name: string;
  description?: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  ratings?: PreschoolRating[];
}

export interface PreschoolRatingScaleCreate {
  name: string;
  description?: string;
  is_default?: boolean;
  ratings?: PreschoolRatingCreate[];
}

export interface PreschoolRatingScaleUpdate {
  name?: string;
  description?: string;
  is_default?: boolean;
}

export interface StudentSkillAssessment {
  id: string;
  tenant_id: string;
  student_id: string;
  skill_id: string;
  academic_year_id: string;
  term_id: string;
  rating_id?: string;
  observation_notes?: string;
  evidence_url?: string;
  assessed_by?: string;
  assessed_at?: string;
  created_at: string;
  updated_at: string;
  rating?: PreschoolRating;
  skill?: DevelopmentalSkill;
}

export interface StudentSkillAssessmentCreate {
  student_id: string;
  skill_id: string;
  academic_year_id: string;
  term_id: string;
  rating_id?: string;
  observation_notes?: string;
  evidence_url?: string;
}

export interface SkillAssessmentEntry {
  skill_id: string;
  rating_id?: string;
  observation_notes?: string;
}

export interface StudentSkillAssessmentBulk {
  student_id: string;
  academic_year_id: string;
  term_id: string;
  assessments: SkillAssessmentEntry[];
}

export interface ProgressObservationAttachment {
  url: string;
  type: string;
  thumbnail?: string;
  filename?: string;
}

export interface ProgressObservation {
  id: string;
  tenant_id: string;
  student_id: string;
  learning_area_id?: string;
  observation_type: ObservationType;
  title: string;
  description?: string;
  observation_date: string;
  attachments?: ProgressObservationAttachment[];
  share_with_parents: boolean;
  is_highlight: boolean;
  recorded_by?: string;
  created_at: string;
  updated_at: string;
}

export interface ProgressObservationCreate {
  student_id: string;
  learning_area_id?: string;
  observation_type?: ObservationType;
  title: string;
  description?: string;
  observation_date: string;
  attachments?: ProgressObservationAttachment[];
  share_with_parents?: boolean;
  is_highlight?: boolean;
}

export interface ProgressObservationUpdate {
  learning_area_id?: string;
  observation_type?: ObservationType;
  title?: string;
  description?: string;
  observation_date?: string;
  attachments?: ProgressObservationAttachment[];
  share_with_parents?: boolean;
  is_highlight?: boolean;
}

export interface MealEntry {
  type: string;
  time?: string;
  amount: MealAmount;
  notes?: string;
}

export interface DailyActivityLog {
  id: string;
  tenant_id: string;
  student_id: string;
  log_date: string;
  arrival_time?: string;
  arrival_mood?: MoodType;
  departure_time?: string;
  departure_mood?: MoodType;
  meals?: MealEntry[];
  nap_start?: string;
  nap_end?: string;
  nap_quality?: NapQuality;
  diaper_changes?: number;
  potty_successes?: number;
  accidents?: number;
  activities?: string[];
  notes?: string;
  highlights?: string;
  logged_by?: string;
  created_at: string;
  updated_at: string;
}

export interface DailyActivityLogCreate {
  student_id: string;
  log_date: string;
  arrival_time?: string;
  arrival_mood?: MoodType;
  departure_time?: string;
  departure_mood?: MoodType;
  meals?: MealEntry[];
  nap_start?: string;
  nap_end?: string;
  nap_quality?: NapQuality;
  diaper_changes?: number;
  potty_successes?: number;
  accidents?: number;
  activities?: string[];
  notes?: string;
  highlights?: string;
}

export interface DailyActivityLogUpdate {
  arrival_time?: string;
  arrival_mood?: MoodType;
  departure_time?: string;
  departure_mood?: MoodType;
  meals?: MealEntry[];
  nap_start?: string;
  nap_end?: string;
  nap_quality?: NapQuality;
  diaper_changes?: number;
  potty_successes?: number;
  accidents?: number;
  activities?: string[];
  notes?: string;
  highlights?: string;
}

export interface LearningAreaSummary {
  learning_area_id: string;
  learning_area_name: string;
  rating: string;
  summary?: string;
}

export interface PreschoolReport {
  id: string;
  tenant_id: string;
  student_id: string;
  academic_year_id: string;
  term_id: string;
  class_id: string;
  days_present?: number;
  days_absent?: number;
  total_school_days?: number;
  learning_area_summaries?: LearningAreaSummary[];
  overall_progress?: string;
  strengths?: string;
  areas_for_growth?: string;
  teacher_recommendations?: string;
  highlights?: string[];
  next_term_goals?: string[];
  class_teacher_remark?: string;
  head_teacher_remark?: string;
  is_published: boolean;
  published_at?: string;
  created_at: string;
  updated_at: string;
}

export interface PreschoolReportCreate {
  student_id: string;
  academic_year_id: string;
  term_id: string;
  class_id: string;
  days_present?: number;
  days_absent?: number;
  total_school_days?: number;
  learning_area_summaries?: LearningAreaSummary[];
  overall_progress?: string;
  strengths?: string;
  areas_for_growth?: string;
  teacher_recommendations?: string;
  highlights?: string[];
  next_term_goals?: string[];
  class_teacher_remark?: string;
  head_teacher_remark?: string;
}

export interface PreschoolReportUpdate {
  days_present?: number;
  days_absent?: number;
  total_school_days?: number;
  learning_area_summaries?: LearningAreaSummary[];
  overall_progress?: string;
  strengths?: string;
  areas_for_growth?: string;
  teacher_recommendations?: string;
  highlights?: string[];
  next_term_goals?: string[];
  class_teacher_remark?: string;
  head_teacher_remark?: string;
}

// =========================
// Timetable Types
// =========================

export type DayOfWeek = 0 | 1 | 2 | 3 | 4 | 5 | 6;

export const DAY_NAMES: Record<DayOfWeek, string> = {
  0: "Monday",
  1: "Tuesday",
  2: "Wednesday",
  3: "Thursday",
  4: "Friday",
  5: "Saturday",
  6: "Sunday",
};

export interface TimetableTeacher {
  id: string;
  first_name: string;
  last_name: string;
  staff_id: string;
}

export interface TimetableSubject {
  id: string;
  name: string;
  code: string;
}

export interface TimetableTerm {
  id: string;
  name: string;
  short_name?: string;
}

export interface TimetableEntry {
  id: string;
  class_id: string;
  section_id?: string;
  academic_year_id: string;
  term_id?: string;
  subject_id?: string;
  teacher_id?: string;
  day_of_week: DayOfWeek;
  period_number: number;
  start_time: string;
  end_time: string;
  room?: string;
  is_active: boolean;
  notes?: string;
  created_at: string;
  updated_at: string;
  subject?: TimetableSubject;
  teacher?: TimetableTeacher;
  term?: TimetableTerm;
}

export interface TimetableEntryCreate {
  class_id: string;
  section_id?: string;
  academic_year_id: string;
  term_id?: string; // Optional: if set, timetable applies only to this term
  subject_id?: string;
  teacher_id?: string;
  day_of_week: DayOfWeek;
  period_number: number;
  start_time: string;
  end_time: string;
  room?: string;
  notes?: string;
}

export interface TimetableEntryUpdate {
  subject_id?: string;
  teacher_id?: string;
  start_time?: string;
  end_time?: string;
  room?: string;
  notes?: string;
  is_active?: boolean;
}

export interface TimetableBulkEntry {
  day_of_week: DayOfWeek;
  period_number: number;
  subject_id?: string;
  teacher_id?: string;
  start_time: string;
  end_time: string;
  room?: string;
  notes?: string;
}

export interface TimetableBulkCreate {
  class_id: string;
  section_id?: string;
  academic_year_id: string;
  term_id?: string; // Optional: if set, timetable applies only to this term
  entries: TimetableBulkEntry[];
}

export interface TimetableDay {
  day_of_week: DayOfWeek;
  day_name: string;
  entries: TimetableEntry[];
}

export interface TimetableWeek {
  class_id: string;
  class_name: string;
  section_id?: string;
  section_name?: string;
  academic_year_id: string;
  academic_year_name: string;
  term_id?: string;
  term_name?: string;
  days: TimetableDay[];
  total_periods: number;
}

export interface PeriodTemplate {
  period_number: number;
  start_time: string;
  end_time: string;
  is_break?: boolean;
  label?: string;
}

// =========================
// School Period Types
// =========================

export interface SchoolPeriod {
  id: string;
  class_id?: string;
  section_id?: string;
  period_number: number;
  name?: string;
  start_time: string;
  end_time: string;
  is_break: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SchoolPeriodCreate {
  class_id?: string;  // null = school-wide
  section_id?: string;  // null = class-wide or school-wide
  period_number: number;
  name?: string;
  start_time: string;
  end_time: string;
  is_break?: boolean;
}

export interface SchoolPeriodUpdate {
  name?: string;
  start_time?: string;
  end_time?: string;
  is_break?: boolean;
  is_active?: boolean;
}

export interface SchoolPeriodBulkEntry {
  period_number: number;
  name?: string;
  start_time: string;
  end_time: string;
  is_break?: boolean;
}

export interface SchoolPeriodBulkCreate {
  class_id?: string;
  section_id?: string;
  periods: SchoolPeriodBulkEntry[];
}

// =========================
// School Holiday Types
// =========================

export type HolidayType = "holiday" | "exam" | "event" | "vacation";

export interface SchoolHoliday {
  id: string;
  date: string;
  name: string;
  description?: string;
  holiday_type: HolidayType;
  academic_year_id?: string;
  is_recurring: boolean;
  created_at: string;
  updated_at: string;
}

export interface SchoolHolidayCreate {
  date: string;
  name: string;
  description?: string;
  holiday_type?: HolidayType;
  academic_year_id?: string;
  is_recurring?: boolean;
}

export interface SchoolHolidayUpdate {
  date?: string;
  name?: string;
  description?: string;
  holiday_type?: HolidayType;
  academic_year_id?: string;
  is_recurring?: boolean;
}

// Re-export School types
export type { SchoolProfile, SchoolProfileUpdate, SchoolBrandingUpdate } from "./school.type";

// Re-export Finance types
export * from "./finance.type";
