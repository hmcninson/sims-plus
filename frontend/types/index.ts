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
  | "hr_officer"
  | "teacher"
  | "house_parent"
  | "transport_officer"
  | "parent"
  | "student"
  | "applicant";

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
  phone_verified: boolean;
  phone_verified_at: string | null;
  mfa_enabled: boolean;
  last_login?: string;
  custom_role_id?: string | null;
  custom_role_name?: string | null;
  school_roles?: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface MySchoolRole {
  school_id: string;
  school_name: string;
  role_at_school: string | null;
  is_primary: boolean;
  is_active: boolean;
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
  remember_me?: boolean;
}

// =========================
// Session Management
// =========================

export interface UserSession {
  id: string;
  device_info: string | null;
  ip_address: string | null;
  last_activity_at: string;
  created_at: string;
  is_current: boolean;
}

export interface SessionListResponse {
  sessions: UserSession[];
  count: number;
}

export interface RegisterData {
  school_name: string;
  subdomain: string;
  school_type: string;
  school_category?: string;
  boarding_type?: string;
  admin_email: string;
  admin_first_name: string;
  admin_last_name: string;
  admin_password: string;
  admin_phone?: string;
  tenant_type?: "single_school" | "school_chain";
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

/**
 * Session context returned by getCurrentUserContext().
 * Contains user info, tenant metadata, and permission strings
 * for the authenticated session.
 */
export interface SessionContext {
  user: User;
  tenant: {
    id: string;
    name: string;
    subdomain: string;
    subscription_tier: string;
    logo_url?: string;
    primary_color?: string;
  };
  permissions: string[];
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
  code?: string | null;
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
  category?: "public" | "private" | "international" | "faith_based" | null;
  boarding_type?: "day_only" | "boarding_only" | "mixed" | null;
  school_type: string;
  setup_completed: boolean;
  setup_wizard_step: number;
  calendar_type: string;
  ges_registration_number: string | null;
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
  structured_medical?: StructuredMedical | null;
  birth_certificate_number?: string;
  photo_url?: string;
  notes?: string;
  enrollment_session?: PreschoolSessionType;
  dietary_requirements?: DietaryRequirements;
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
  structured_medical?: StructuredMedical | null;
  birth_certificate_number?: string;
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
  structured_medical?: StructuredMedical | null;
  birth_certificate_number?: string;
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

/**
 * Discriminated union for server action results.
 * Enables TypeScript narrowing: if (result.success) { result.data } is safe.
 * The optional `code` on failure lets UI distinguish 401/403/429 etc.
 */
export type ActionResult<T = void> =
  | { success: true; data: T; error?: undefined; code?: undefined }
  | { success: false; error: string; code?: number; data?: undefined };

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

export type AcademicYearStatus = "planning" | "active" | "completed" | "archived";
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
  curriculum_profile_id?: string;
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
  curriculum_profile_id?: string;
}

export interface ClassUpdate {
  name?: string;
  short_name?: string;
  level?: ClassLevel;
  sequence?: number;
  capacity?: number;
  is_active?: boolean;
  curriculum_profile_id?: string;
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
export type EmploymentType = "full_time" | "part_time" | "contract" | "temporary" | "intern";
export type StaffDocumentType = "contract" | "certificate" | "cv_resume" | "id_document" | "reference_letter" | "disciplinary" | "training" | "medical" | "other";
export type EmploymentEventType = "hired" | "promoted" | "demoted" | "transferred" | "title_changed" | "department_changed" | "status_changed" | "salary_changed" | "contract_renewed";

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
  tin_number?: string;
  employment_type?: EmploymentType;
  ges_staff_id?: string;
  nationality?: string;
  marital_status?: string;
  created_at: string;
  updated_at: string;
}

export interface StaffDocument {
  id: string;
  staff_id: string;
  document_type: StaffDocumentType;
  file_name: string;
  file_size: number;
  mime_type: string;
  description?: string;
  download_url: string;
  uploaded_by?: string;
  created_at: string;
}

export interface StaffEmploymentHistory {
  id: string;
  staff_id: string;
  event_type: EmploymentEventType;
  effective_date: string;
  previous_value?: string;
  new_value?: string;
  previous_department_id?: string;
  new_department_id?: string;
  previous_job_title?: string;
  new_job_title?: string;
  notes?: string;
  recorded_by?: string;
  created_at: string;
}

export interface CreateEmploymentEvent {
  event_type: EmploymentEventType;
  effective_date: string;
  previous_value?: string;
  new_value?: string;
  previous_department_id?: string;
  new_department_id?: string;
  previous_job_title?: string;
  new_job_title?: string;
  notes?: string;
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
  tin_number?: string;
  employment_type?: EmploymentType;
  ges_staff_id?: string;
  nationality?: string;
  marital_status?: string;
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
  tin_number?: string;
  employment_type?: EmploymentType;
  ges_staff_id?: string;
  nationality?: string;
  marital_status?: string;
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

export interface StaffAttendanceEntry {
  id?: string;
  staff_id: string;
  staff_name: string;
  staff_code: string;
  department?: string;
  staff_type: StaffType;
  photo_url?: string;
  status: AttendanceStatus;
  remarks?: string;
  check_in_time?: string;
  check_out_time?: string;
  date: string;
}

export interface StaffAttendanceReportData {
  total_staff: number;
  date_range: { start: string; end: string };
  overall_rate: number;
  daily_breakdown: Array<{
    date: string;
    present: number;
    absent: number;
    late: number;
    excused: number;
    sick: number;
    rate: number;
  }>;
  by_department: Array<{
    department: string;
    total: number;
    present_rate: number;
    absent_rate: number;
    late_rate: number;
  }>;
  by_staff: Array<{
    staff_id: string;
    staff_name: string;
    department?: string;
    total_days: number;
    present: number;
    absent: number;
    late: number;
    rate: number;
  }>;
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
  effort_grade?: string | null;
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
  effort_grade?: string | null;
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
  curriculum_type?: string;
  show_effort_grade?: boolean;
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
  effort_grade?: string | null;
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
  /** Curriculum type from the curriculum profile (e.g., "ges", "montessori", "cambridge") */
  curriculum_type?: string;
  /** Template key from report config (e.g., "dual_track") */
  template_key?: string;
  /** JSONB extra data (Montessori narratives, dual-track data, etc.) */
  extra_data?: Record<string, unknown>;
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
  report_type: "term" | "interim" | "progress_update";
  photo_urls?: { url: string; caption?: string }[];
  chart_data?: { labels: string[]; values: number[]; max_value: number };
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
// Preschool Phase 1: Safety & Enrollment Types
// =========================

// Enums
export type PreschoolSessionType = "half_day_morning" | "half_day_afternoon" | "full_day" | "extended";
export type PreschoolIncidentType = "accident" | "illness" | "behavioral" | "allergic_reaction" | "other";
export type PreschoolIncidentSeverity = "minor" | "moderate" | "serious";
export type PreschoolIncidentStatus = "reported" | "reviewed" | "parent_notified" | "resolved";

// Allergy / Dietary
export interface AllergyEntry {
  allergen: string;
  severity: "mild" | "moderate" | "severe";
  reaction?: string;
  medication?: string;
}

export interface DietaryRequirements {
  allergies: AllergyEntry[];
  dietary_restrictions: string[];
  notes?: string;
}

export interface AllergyAlertResponse {
  student_id: string;
  student_name: string;
  allergies: AllergyEntry[];
  dietary_restrictions: string[];
  notes?: string;
}

// Incidents
export interface PreschoolIncident {
  id: string;
  tenant_id: string;
  student_id: string;
  incident_type: PreschoolIncidentType;
  severity: PreschoolIncidentSeverity;
  status: PreschoolIncidentStatus;
  incident_date: string;
  incident_time?: string;
  location?: string;
  description: string;
  action_taken?: string;
  first_aid_given: boolean;
  medical_attention_required: boolean;
  parent_notified_at?: string;
  parent_notified_by?: string;
  witnesses?: string[];
  attachments?: ProgressObservationAttachment[];
  follow_up_notes?: string;
  resolved_at?: string;
  resolved_by?: string;
  reported_by?: string;
  created_at: string;
  updated_at: string;
}

export interface PreschoolIncidentCreate {
  student_id: string;
  incident_type: PreschoolIncidentType;
  severity: PreschoolIncidentSeverity;
  incident_date: string;
  incident_time?: string;
  location?: string;
  description: string;
  action_taken?: string;
  first_aid_given?: boolean;
  medical_attention_required?: boolean;
  witnesses?: string[];
  attachments?: ProgressObservationAttachment[];
}

export interface PreschoolIncidentUpdate {
  incident_type?: PreschoolIncidentType;
  severity?: PreschoolIncidentSeverity;
  location?: string;
  description?: string;
  action_taken?: string;
  first_aid_given?: boolean;
  medical_attention_required?: boolean;
  witnesses?: string[];
  attachments?: ProgressObservationAttachment[];
  follow_up_notes?: string;
}

// Authorized Pickups
export interface AuthorizedPickup {
  id: string;
  tenant_id: string;
  student_id: string;
  full_name: string;
  phone: string;
  relationship_to_student?: string;
  photo_url?: string;
  id_document_url?: string;
  is_active: boolean;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface AuthorizedPickupCreate {
  full_name: string;
  phone: string;
  relationship_to_student?: string;
  photo_url?: string;
  id_document_url?: string;
  notes?: string;
}

export interface AuthorizedPickupUpdate {
  full_name?: string;
  phone?: string;
  relationship_to_student?: string;
  photo_url?: string;
  id_document_url?: string;
  is_active?: boolean;
  notes?: string;
}

// Pickup Logs
export interface PickupLog {
  id: string;
  tenant_id: string;
  student_id: string;
  pickup_date: string;
  pickup_time: string;
  picked_up_by_type: "guardian" | "authorized_person";
  picked_up_by_guardian_id?: string;
  picked_up_by_authorized_id?: string;
  verified_by?: string;
  notes?: string;
  created_at: string;
}

export interface PickupLogCreate {
  student_id: string;
  pickup_time: string;
  picked_up_by_type: "guardian" | "authorized_person";
  picked_up_by_guardian_id?: string;
  picked_up_by_authorized_id?: string;
  notes?: string;
}

// =========================
// Preschool Phase 2: Enhancement & Integration Types
// =========================

// Learning Stories
export interface LearningStory {
  id: string;
  tenant_id: string;
  student_id: string;
  term_id?: string;
  title: string;
  narrative: string;
  learning_area_ids?: string[];
  skill_ids?: string[];
  observation_ids?: string[];
  attachments?: ProgressObservationAttachment[];
  is_shared_with_parents: boolean;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface LearningStoryCreate {
  student_id: string;
  term_id?: string;
  title: string;
  narrative: string;
  learning_area_ids?: string[];
  skill_ids?: string[];
  observation_ids?: string[];
  attachments?: ProgressObservationAttachment[];
  is_shared_with_parents?: boolean;
}

export interface LearningStoryUpdate {
  title?: string;
  narrative?: string;
  learning_area_ids?: string[];
  skill_ids?: string[];
  observation_ids?: string[];
  attachments?: ProgressObservationAttachment[];
  is_shared_with_parents?: boolean;
}

// Extended Care
export type ExtendedCareSessionType = "before_care" | "after_care";

export interface ExtendedCareSession {
  id: string;
  tenant_id: string;
  student_id: string;
  session_date: string;
  session_type: ExtendedCareSessionType;
  check_in_time: string;
  check_out_time?: string;
  duration_minutes?: number;
  checked_in_by?: string;
  checked_out_by?: string;
  notes?: string;
  created_at: string;
}

export interface ExtendedCareBillingSummary {
  student_id: string;
  student_name: string;
  total_sessions: number;
  total_minutes: number;
  total_hours: number;
  rate_per_hour?: number;
  flat_rate?: number;
  estimated_charge: number;
}

// Caregiver Ratios
export interface CaregiverRatio {
  id: string;
  tenant_id: string;
  class_id: string;
  academic_year_id: string;
  max_children_per_caregiver: number;
  current_caregiver_count: number;
  max_capacity: number;
  current_enrollment: number;
  is_compliant: boolean;
}

// Timeline
export interface TimelineEntry {
  date: string;
  type: "assessment" | "observation" | "incident" | "learning_story";
  title: string;
  summary?: string;
  details: Record<string, unknown>;
  id: string;
}

// =========================
// Preschool Phase 3: Supplies Types
// =========================

export interface PreschoolSupply {
  id: string;
  tenant_id: string;
  student_id: string;
  item_name: string;
  quantity_remaining: number;
  low_stock_threshold: number;
  is_low_stock: boolean;
  last_restocked_at?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface PreschoolSupplyCreate {
  item_name: string;
  quantity_remaining?: number;
  low_stock_threshold?: number;
  notes?: string;
}

export interface PreschoolSupplyUpdate {
  item_name?: string;
  low_stock_threshold?: number;
  notes?: string;
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

// =========================
// Notification Types
// =========================

export type NotificationType = "info" | "success" | "warning" | "error" | "system";
export type NotificationCategory = "academic" | "finance" | "attendance" | "exam" | "general" | "admin";

export interface Notification {
  id: string;
  user_id: string;
  title: string;
  message: string;
  type: NotificationType;
  category: NotificationCategory;
  reference_id?: string;
  reference_type?: string;
  is_read: boolean;
  read_at?: string;
  created_at: string;
  updated_at: string;
}

export interface NotificationListResponse {
  items: Notification[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface UnreadCountResponse {
  count: number;
}

// =========================
// Report Types
// =========================

export type FinancialReportType = "fee_collection" | "outstanding_fees" | "payment_summary";

export interface FinancialReportRequest {
  report_type: FinancialReportType;
  academic_year_id: string;
  term_id?: string;
  class_id?: string;
  date_from?: string;
  date_to?: string;
}

export interface AttendanceReportRequest {
  class_id: string;
  section_id?: string;
  date_from: string;
  date_to: string;
}

export interface ReportGenerationResponse {
  report_type: string;
  generated_at: string;
  filters: Record<string, unknown>;
}

// =========================
// User Invite Types
// =========================

export interface UserInviteRequest {
  email: string;
  role: UserRole;
  first_name: string;
  last_name: string;
}

export interface UserInviteResponse {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  status: UserStatus;
  created_at: string;
}

// =========================
// Bulk User Import Types
// =========================

export interface UserImportRowError {
  row: number;
  field: string;
  error: string;
}

export interface UserImportRow {
  row_number: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  phone: string | null;
  valid: boolean;
  errors: string[];
}

export interface UserImportCredential {
  email: string;
  temporary_password: string;
}

export interface UserImportResult {
  total: number;
  valid: number;
  created: number;
  errors: UserImportRowError[];
  preview: UserImportRow[];
  credentials: UserImportCredential[] | null;
}

// =========================
// Audit Log Types
// =========================

export interface AuditLogEntry {
  id: string;
  event_type: string;
  user_id?: string;
  user_email?: string;
  ip_address?: string;
  details?: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// =========================
// Dashboard Types
// =========================

export interface AttendanceTodayStats {
  present: number;
  absent: number;
  rate: number;
}

export interface FinanceSummaryStats {
  total_billed: number;
  total_collected: number;
  collection_rate: number;
  outstanding: number;
}

export interface DashboardStats {
  total_students: number;
  total_staff: number;
  total_classes: number;
  attendance_today: AttendanceTodayStats;
  finance: FinanceSummaryStats;
}

export interface AttendanceTrendPoint {
  date: string;
  present: number;
  absent: number;
  late: number;
  rate: number;
}

export interface FeeCollectionTrendPoint {
  month: string;
  billed: number;
  collected: number;
}

export interface ClassPerformancePoint {
  class_name: string;
  average: number;
  highest: number;
  lowest: number;
}

export interface GenderDistribution {
  male: number;
  female: number;
}

export interface RecentActivityItem {
  event_type: string;
  description: string;
  timestamp: string;
  user_name?: string;
}

export interface DashboardResponse {
  stats: DashboardStats;
  recent_activity: RecentActivityItem[];
}

export interface StudentPromotionRequest {
  from_class_id: string;
  to_class_id: string;
  student_ids: string[];
}

export interface StudentPromotionResponse {
  promoted: number;
  failed: number;
  errors: Array<{ student_id: string; error: string }>;
}

// =========================
// Boarding Types
// =========================

export type HouseGender = "male" | "female" | "mixed";
export type DormitoryType = "room" | "hall" | "cubicle";
export type BedType = "single" | "bunk_upper" | "bunk_lower";
export type BedStatus = "available" | "occupied" | "maintenance";
export type BoardingStatus = "active" | "withdrawn" | "suspended" | "graduated";
export type RollCallType = "morning" | "evening" | "lights_out" | "emergency";
export type RollCallEntryStatus = "present" | "absent" | "sick_bay" | "exeat" | "awol";
export type ExeatType = "weekend" | "medical" | "emergency" | "funeral" | "other";
export type ExeatStatus = "pending" | "approved" | "denied" | "active" | "overdue" | "returned";
export type BoardingIncidentType =
  | "disciplinary"
  | "health"
  | "property_damage"
  | "missing_student"
  | "bullying"
  | "theft"
  | "other";
export type IncidentSeverity = "low" | "medium" | "high" | "critical";
export type DiningMealType = "breakfast" | "lunch" | "dinner" | "snack";

// Houses

export interface House {
  id: string;
  tenant_id: string;
  school_id: string;
  name: string;
  house_code: string;
  gender: HouseGender;
  capacity: number;
  house_parent_id?: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface HouseCreate {
  name: string;
  house_code: string;
  gender: HouseGender;
  capacity: number;
  house_parent_id?: string;
  description?: string;
  is_active?: boolean;
}

export interface HouseUpdate {
  name?: string;
  house_code?: string;
  gender?: HouseGender;
  capacity?: number;
  house_parent_id?: string;
  description?: string;
  is_active?: boolean;
}

export interface HouseDetail extends House {
  house_parent_name?: string;
  dormitory_count: number;
  current_occupancy: number;
}

export interface HouseListResponse {
  items: House[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Dormitories

export interface Dormitory {
  id: string;
  tenant_id: string;
  school_id: string;
  house_id: string;
  name: string;
  floor?: string;
  capacity: number;
  dormitory_type: DormitoryType;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DormitoryDetail extends Dormitory {
  house_name?: string;
  bed_count: number;
  occupied_beds: number;
  available_beds: number;
}

export interface DormitoryCreate {
  house_id: string;
  name: string;
  floor?: string;
  capacity: number;
  dormitory_type: DormitoryType;
  is_active?: boolean;
}

export interface DormitoryUpdate {
  name?: string;
  floor?: string;
  capacity?: number;
  dormitory_type?: DormitoryType;
  is_active?: boolean;
}

export interface DormitoryListResponse {
  items: Dormitory[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Beds

export interface Bed {
  id: string;
  tenant_id: string;
  school_id: string;
  dormitory_id: string;
  bed_number: string;
  bed_type: BedType;
  status: BedStatus;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BedDetail extends Bed {
  dormitory_name?: string;
  house_name?: string;
  occupant_name?: string;
  occupant_id?: string;
}

export interface BedCreate {
  dormitory_id: string;
  bed_number: string;
  bed_type: BedType;
  status?: BedStatus;
  is_active?: boolean;
}

export interface BedBulkCreate {
  dormitory_id: string;
  bed_type: BedType;
  count: number;
  prefix?: string;
}

export interface BedUpdate {
  bed_number?: string;
  bed_type?: BedType;
  status?: BedStatus;
  is_active?: boolean;
}

export interface BedListResponse {
  items: Bed[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Student Boarding Assignments

export interface StudentBoarding {
  id: string;
  tenant_id: string;
  school_id: string;
  student_id: string;
  house_id: string;
  dormitory_id?: string;
  bed_id?: string;
  academic_year_id: string;
  boarding_status: BoardingStatus;
  check_in_date: string;
  check_out_date?: string;
  created_at: string;
  updated_at: string;
}

export interface StudentBoardingDetail extends StudentBoarding {
  student_name?: string;
  house_name?: string;
  dormitory_name?: string;
  bed_number?: string;
  academic_year_name?: string;
}

export interface StudentBoardingCreate {
  student_id: string;
  house_id: string;
  dormitory_id?: string;
  bed_id?: string;
  academic_year_id: string;
  boarding_status?: BoardingStatus;
  check_in_date: string;
}

export interface StudentBoardingUpdate {
  house_id?: string;
  dormitory_id?: string;
  bed_id?: string;
  boarding_status?: BoardingStatus;
  check_out_date?: string;
}

export interface StudentBoardingBulkAssign {
  student_ids: string[];
  house_id: string;
  academic_year_id: string;
  check_in_date: string;
}

export interface StudentBoardingListResponse {
  items: StudentBoardingDetail[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Roll Calls

export interface RollCallEntry {
  id: string;
  roll_call_id: string;
  student_id: string;
  status: RollCallEntryStatus;
  notes?: string;
  student_name?: string;
  created_at: string;
  updated_at: string;
}

export interface RollCallEntryCreate {
  student_id: string;
  status: RollCallEntryStatus;
  notes?: string;
}

export interface BoardingRollCall {
  id: string;
  tenant_id: string;
  school_id: string;
  house_id: string;
  date: string;
  roll_call_type: RollCallType;
  conducted_by_id: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface BoardingRollCallDetail extends BoardingRollCall {
  house_name?: string;
  conducted_by_name?: string;
  entries: RollCallEntry[];
  present_count: number;
  absent_count: number;
  total_count: number;
}

export interface BoardingRollCallCreate {
  house_id: string;
  date: string;
  roll_call_type: RollCallType;
  notes?: string;
}

export interface BoardingRollCallSubmit {
  house_id: string;
  date: string;
  roll_call_type: RollCallType;
  notes?: string;
  entries: RollCallEntryCreate[];
}

export interface BoardingRollCallListResponse {
  items: BoardingRollCall[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Exeats

export interface Exeat {
  id: string;
  tenant_id: string;
  school_id: string;
  student_id: string;
  requested_by_id: string;
  approved_by_id?: string;
  exeat_type: ExeatType;
  reason: string;
  start_date: string;
  end_date: string;
  actual_return_date?: string;
  status: ExeatStatus;
  guardian_notified: boolean;
  guardian_phone?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface ExeatDetail extends Exeat {
  student_name?: string;
  requested_by_name?: string;
  approved_by_name?: string;
}

export interface ExeatCreate {
  student_id: string;
  exeat_type: ExeatType;
  reason: string;
  start_date: string;
  end_date: string;
  guardian_phone?: string;
  notes?: string;
}

export interface ExeatApprovalUpdate {
  status: "approved" | "denied";
  notes?: string;
}

export interface ExeatReturnUpdate {
  actual_return_date: string;
  notes?: string;
}

export interface ExeatListResponse {
  items: ExeatDetail[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Boarding Incidents

export interface BoardingIncident {
  id: string;
  tenant_id: string;
  school_id: string;
  student_id: string;
  reported_by_id: string;
  incident_type: BoardingIncidentType;
  severity: IncidentSeverity;
  description: string;
  action_taken?: string;
  resolved: boolean;
  resolved_by_id?: string;
  resolved_at?: string;
  parent_notified: boolean;
  created_at: string;
  updated_at: string;
}

export interface BoardingIncidentDetail extends BoardingIncident {
  student_name?: string;
  reported_by_name?: string;
  resolved_by_name?: string;
}

export interface BoardingIncidentCreate {
  student_id: string;
  incident_type: BoardingIncidentType;
  severity: IncidentSeverity;
  description: string;
  action_taken?: string;
}

export interface BoardingIncidentUpdate {
  incident_type?: BoardingIncidentType;
  severity?: IncidentSeverity;
  description?: string;
  action_taken?: string;
}

export interface BoardingIncidentResolve {
  action_taken: string;
  parent_notified?: boolean;
}

export interface BoardingIncidentListResponse {
  items: BoardingIncidentDetail[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Dining

export interface DiningMeal {
  id: string;
  tenant_id: string;
  school_id: string;
  date: string;
  meal_type: DiningMealType;
  menu_description?: string;
  head_count?: number;
  prepared_by?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface DiningMealCreate {
  date: string;
  meal_type: DiningMealType;
  menu_description?: string;
  head_count?: number;
  prepared_by?: string;
  notes?: string;
}

export interface DiningMealUpdate {
  meal_type?: DiningMealType;
  menu_description?: string;
  head_count?: number;
  prepared_by?: string;
  notes?: string;
}

export interface DiningMealListResponse {
  items: DiningMeal[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Boarding Stats

export interface BoardingStats {
  total_houses: number;
  total_dormitories: number;
  total_beds: number;
  available_beds: number;
  occupied_beds: number;
  total_boarders: number;
  active_exeats: number;
  pending_exeats: number;
  unresolved_incidents: number;
}

// =========================
// Transport Types
// =========================

export type VehicleType = "bus" | "minibus" | "van" | "car";
export type VehicleStatus = "active" | "maintenance" | "retired";
export type DriverStatus = "active" | "on_leave" | "terminated";
export type RouteType = "morning_pickup" | "afternoon_dropoff" | "both";
export type StudentTransportStatus = "active" | "suspended" | "cancelled";
export type TripType = "morning_pickup" | "afternoon_dropoff" | "field_trip" | "other";
export type TripStatus = "scheduled" | "in_progress" | "completed" | "cancelled";
export type MaintenanceType = "routine" | "repair" | "inspection" | "emergency";

// Vehicles

export interface Vehicle {
  id: string;
  tenant_id: string;
  school_id: string;
  registration_number: string;
  vehicle_type: VehicleType;
  make?: string;
  model_name?: string;
  year?: number;
  capacity: number;
  status: VehicleStatus;
  insurance_expiry?: string;
  roadworthy_expiry?: string;
  gps_tracker_id?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface VehicleDetail extends Vehicle {
  active_route_count: number;
  last_maintenance_date?: string;
  next_maintenance_date?: string;
}

export interface VehicleCreate {
  registration_number: string;
  vehicle_type: VehicleType;
  make?: string;
  model_name?: string;
  year?: number;
  capacity: number;
  status?: VehicleStatus;
  insurance_expiry?: string;
  roadworthy_expiry?: string;
  gps_tracker_id?: string;
  notes?: string;
}

export interface VehicleUpdate {
  registration_number?: string;
  vehicle_type?: VehicleType;
  make?: string;
  model_name?: string;
  year?: number;
  capacity?: number;
  status?: VehicleStatus;
  insurance_expiry?: string;
  roadworthy_expiry?: string;
  gps_tracker_id?: string;
  notes?: string;
}

export interface VehicleListResponse {
  items: Vehicle[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Drivers

export interface Driver {
  id: string;
  tenant_id: string;
  school_id: string;
  staff_id?: string;
  first_name: string;
  last_name: string;
  phone: string;
  license_number: string;
  license_expiry: string;
  license_class: string;
  status: DriverStatus;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  created_at: string;
  updated_at: string;
}

export interface DriverCreate {
  staff_id?: string;
  first_name: string;
  last_name: string;
  phone: string;
  license_number: string;
  license_expiry: string;
  license_class: string;
  status?: DriverStatus;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
}

export interface DriverUpdate {
  staff_id?: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  license_number?: string;
  license_expiry?: string;
  license_class?: string;
  status?: DriverStatus;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
}

export interface DriverListResponse {
  items: Driver[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Route Stops

export interface RouteStop {
  id: string;
  tenant_id: string;
  route_id: string;
  stop_name: string;
  stop_order: number;
  pickup_time?: string;
  dropoff_time?: string;
  latitude?: number;
  longitude?: number;
  landmark?: string;
  created_at: string;
  updated_at: string;
}

export interface RouteStopCreate {
  stop_name: string;
  stop_order: number;
  pickup_time?: string;
  dropoff_time?: string;
  latitude?: number;
  longitude?: number;
  landmark?: string;
}

export interface RouteStopUpdate {
  stop_name?: string;
  stop_order?: number;
  pickup_time?: string;
  dropoff_time?: string;
  latitude?: number;
  longitude?: number;
  landmark?: string;
}

// Routes

export interface TransportRoute {
  id: string;
  tenant_id: string;
  school_id: string;
  name: string;
  route_code: string;
  description?: string;
  distance_km?: number;
  estimated_duration_minutes?: number;
  vehicle_id?: string;
  driver_id?: string;
  route_type: RouteType;
  is_active: boolean;
  transport_fee_per_term?: number;
  created_at: string;
  updated_at: string;
}

export interface TransportRouteDetail extends TransportRoute {
  vehicle_registration?: string;
  driver_name?: string;
  stops: RouteStop[];
  student_count: number;
}

export interface TransportRouteCreate {
  name: string;
  route_code: string;
  description?: string;
  distance_km?: number;
  estimated_duration_minutes?: number;
  vehicle_id?: string;
  driver_id?: string;
  route_type: RouteType;
  is_active?: boolean;
  transport_fee_per_term?: number;
  stops?: RouteStopCreate[];
}

export interface TransportRouteUpdate {
  name?: string;
  route_code?: string;
  description?: string;
  distance_km?: number;
  estimated_duration_minutes?: number;
  vehicle_id?: string;
  driver_id?: string;
  route_type?: RouteType;
  is_active?: boolean;
  transport_fee_per_term?: number;
}

export interface TransportRouteListResponse {
  items: TransportRoute[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Student Transport Assignments

export interface StudentTransport {
  id: string;
  tenant_id: string;
  school_id: string;
  student_id: string;
  route_id: string;
  stop_id: string;
  academic_year_id: string;
  status: StudentTransportStatus;
  pickup_guardian_phone?: string;
  special_instructions?: string;
  created_at: string;
  updated_at: string;
}

export interface StudentTransportDetail extends StudentTransport {
  student_name?: string;
  route_name?: string;
  stop_name?: string;
  academic_year_name?: string;
  pickup_time?: string;
  dropoff_time?: string;
}

export interface StudentTransportCreate {
  student_id: string;
  route_id: string;
  stop_id: string;
  academic_year_id: string;
  status?: StudentTransportStatus;
  pickup_guardian_phone?: string;
  special_instructions?: string;
}

export interface StudentTransportUpdate {
  route_id?: string;
  stop_id?: string;
  status?: StudentTransportStatus;
  pickup_guardian_phone?: string;
  special_instructions?: string;
}

export interface StudentTransportListResponse {
  items: StudentTransportDetail[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Trip Logs

export interface TripLog {
  id: string;
  tenant_id: string;
  school_id: string;
  route_id: string;
  vehicle_id: string;
  driver_id: string;
  trip_date: string;
  trip_type: TripType;
  departure_time?: string;
  arrival_time?: string;
  odometer_start?: number;
  odometer_end?: number;
  student_count: number;
  status: TripStatus;
  incidents?: string;
  logged_by_id: string;
  created_at: string;
  updated_at: string;
}

export interface TripLogDetail extends TripLog {
  route_name?: string;
  vehicle_registration?: string;
  driver_name?: string;
  logged_by_name?: string;
}

export interface TripLogCreate {
  route_id: string;
  vehicle_id: string;
  driver_id: string;
  trip_date: string;
  trip_type: TripType;
  departure_time?: string;
  arrival_time?: string;
  odometer_start?: number;
  odometer_end?: number;
  student_count: number;
  status?: TripStatus;
  incidents?: string;
}

export interface TripLogUpdate {
  departure_time?: string;
  arrival_time?: string;
  odometer_start?: number;
  odometer_end?: number;
  student_count?: number;
  status?: TripStatus;
  incidents?: string;
}

export interface TripLogListResponse {
  items: TripLogDetail[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Vehicle Maintenance

export interface VehicleMaintenance {
  id: string;
  tenant_id: string;
  school_id: string;
  vehicle_id: string;
  maintenance_type: MaintenanceType;
  description: string;
  cost?: number;
  service_date: string;
  next_service_date?: string;
  odometer_reading?: number;
  service_provider?: string;
  invoice_number?: string;
  logged_by_id: string;
  created_at: string;
  updated_at: string;
}

export interface VehicleMaintenanceDetail extends VehicleMaintenance {
  vehicle_registration?: string;
  logged_by_name?: string;
}

export interface VehicleMaintenanceCreate {
  vehicle_id: string;
  maintenance_type: MaintenanceType;
  description: string;
  cost?: number;
  service_date: string;
  next_service_date?: string;
  odometer_reading?: number;
  service_provider?: string;
  invoice_number?: string;
}

export interface VehicleMaintenanceUpdate {
  maintenance_type?: MaintenanceType;
  description?: string;
  cost?: number;
  service_date?: string;
  next_service_date?: string;
  odometer_reading?: number;
  service_provider?: string;
  invoice_number?: string;
}

export interface VehicleMaintenanceListResponse {
  items: VehicleMaintenanceDetail[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Transport Stats

export interface TransportStats {
  total_vehicles: number;
  active_vehicles: number;
  maintenance_vehicles: number;
  total_drivers: number;
  active_drivers: number;
  total_routes: number;
  active_routes: number;
  total_students_assigned: number;
  trips_today: number;
}

// =========================
// Student History Types
// =========================

export interface ClassHistoryRecord {
  id: string;
  student_id: string;
  school_id: string;
  class_id: string;
  section_id: string | null;
  academic_year_id: string;
  enrolled_date: string;
  left_date: string | null;
  reason: string | null;
  created_at: string;
  class_name: string | null;
  section_name: string | null;
  academic_year_name: string | null;
}

export interface ClassHistoryListResponse {
  records: ClassHistoryRecord[];
  total: number;
}

export interface StatusChangeRecord {
  id: string;
  student_id: string;
  school_id: string;
  from_status: string | null;
  to_status: string;
  reason: string | null;
  effective_date: string;
  performed_by: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
  performed_by_name: string | null;
}

export interface StatusHistoryListResponse {
  records: StatusChangeRecord[];
  total: number;
}

export interface ClassEnrollmentBreakdown {
  class_id: string;
  class_name: string;
  total: number;
  male: number;
  female: number;
  boarders: number;
  day_students: number;
}

export interface EnrollmentTrend {
  academic_year_id: string;
  academic_year_name: string;
  total_enrolled: number;
  new_enrollments: number;
  withdrawals: number;
  transfers_out: number;
  graduations: number;
}

export interface EnrollmentAnalyticsResponse {
  total_active: number;
  total_inactive: number;
  total_graduated: number;
  total_transferred: number;
  total_withdrawn: number;
  total_suspended: number;
  by_class: ClassEnrollmentBreakdown[];
  trends: EnrollmentTrend[];
  attrition_rate: number;
  new_enrollment_rate: number;
}

// =========================
// Withdrawal & Transfer Types
// =========================

export interface OutstandingInvoiceSummary {
  invoice_id: string;
  invoice_number: string;
  amount: number;
  balance: number;
  status: string;
  due_date: string | null;
}

export interface OutstandingFeeCheckResponse {
  has_outstanding: boolean;
  total_outstanding: number;
  invoice_count: number;
  invoices: OutstandingInvoiceSummary[];
}

export interface WithdrawalInitiateRequest {
  reason: string;
  effective_date: string;
  fee_override?: boolean;
}

export interface WithdrawalClearanceResponse {
  id: string;
  student_id: string;
  status_change_id: string | null;
  type: string;
  library_cleared: boolean;
  finance_cleared: boolean;
  property_cleared: boolean;
  boarding_cleared: boolean | null;
  outstanding_fees: number | null;
  fee_override: boolean;
  notes: string | null;
  is_complete: boolean;
  cleared_by: string | null;
  cleared_at: string | null;
  created_at: string;
}

export interface ClearanceUpdateRequest {
  library_cleared?: boolean;
  finance_cleared?: boolean;
  property_cleared?: boolean;
  boarding_cleared?: boolean;
  notes?: string;
}

export interface WithdrawalCompleteResponse {
  student_id: string;
  status: string;
  clearance_completed: boolean;
  withdrawal_letter_available: boolean;
}

export interface TransferInitiateRequest {
  destination_school: string;
  reason: string;
  effective_date: string;
  fee_override?: boolean;
}

export interface ChainTransferRequest {
  to_school_id: string;
  to_class_id: string;
  to_section_id?: string;
  reason: string;
  effective_date: string;
  fee_override?: boolean;
}

export interface ChainTransferResponse {
  student_id: string;
  from_school_id: string;
  to_school_id: string;
  to_class_id: string;
  status: string;
}

// =========================
// Student Documents
// =========================

export interface StudentDocumentResponse {
  id: string;
  student_id: string;
  document_type: string;
  title: string;
  file_size: number;
  mime_type: string;
  uploaded_by: string | null;
  notes: string | null;
  created_at: string;
}

export interface DocumentListResponse {
  documents: StudentDocumentResponse[];
  total: number;
  total_size_bytes: number;
}

export interface DocumentDownloadResponse {
  download_url: string;
  expires_in: number;
}

// =========================
// Previous Schools
// =========================

export interface PreviousSchoolRecord {
  id: string;
  student_id: string;
  school_name: string;
  school_address: string | null;
  last_class: string | null;
  years_attended: string | null;
  transfer_reason: string | null;
  leaving_certificate_ref: string | null;
  created_at: string;
}

export interface PreviousSchoolCreate {
  school_name: string;
  school_address?: string;
  last_class?: string;
  years_attended?: string;
  transfer_reason?: string;
  leaving_certificate_ref?: string;
}

export interface PreviousSchoolUpdate {
  school_name?: string;
  school_address?: string;
  last_class?: string;
  years_attended?: string;
  transfer_reason?: string;
  leaving_certificate_ref?: string;
}

// =========================
// Structured Medical
// =========================

export interface MedicalCondition {
  name: string;
  severity?: string;
  diagnosed_date?: string;
  notes?: string;
}

export interface MedicalAllergy {
  name: string;
  severity?: string;
  reaction?: string;
}

export interface MedicalMedication {
  name: string;
  dosage?: string;
  frequency?: string;
  prescriber?: string;
}

export interface StructuredMedical {
  conditions: MedicalCondition[];
  allergies: MedicalAllergy[];
  medications: MedicalMedication[];
  emergency_protocol?: string;
  doctor_name?: string;
  doctor_phone?: string;
  hospital?: string;
  blood_group?: string;
}

// =========================
// Promotion Rules
// =========================

export interface PromotionRule {
  id: string;
  academic_year_id: string;
  academic_year_name?: string;
  class_id: string | null;
  class_name?: string | null;
  min_average: number | null;
  min_attendance_percent: number | null;
  core_passes_required: number | null;
  pass_mark: number | null;
  auto_apply: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PromotionRuleCreate {
  academic_year_id: string;
  class_id?: string | null;
  min_average?: number | null;
  min_attendance_percent?: number | null;
  core_passes_required?: number | null;
  pass_mark?: number | null;
  auto_apply?: boolean;
  is_active?: boolean;
}

export interface PromotionRuleUpdate {
  academic_year_id?: string;
  class_id?: string | null;
  min_average?: number | null;
  min_attendance_percent?: number | null;
  core_passes_required?: number | null;
  pass_mark?: number | null;
  auto_apply?: boolean;
  is_active?: boolean;
}

export interface PromotionRuleListResponse {
  items: PromotionRule[];
  total: number;
}

// Re-export School types
export type { SchoolProfile, SchoolProfileUpdate, SchoolBrandingUpdate } from "./school.type";

// Re-export Finance types
export * from "./finance.type";

// Re-export Communication types
export type {
  SMSSettings,
  EmailSettings,
  NotificationDefaults,
  CommunicationSettings,
} from "./communication.type";
