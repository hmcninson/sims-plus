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
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SubjectCreate {
  name: string;
  code: string;
  description?: string;
  category?: SubjectCategory;
}

export interface SubjectUpdate {
  name?: string;
  code?: string;
  description?: string;
  category?: SubjectCategory;
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
  created_at: string;
  updated_at: string;
}

export interface AssessmentWeightCreate {
  academic_year_id?: string;
  class_work_weight?: number;
  homework_weight?: number;
  midterm_weight?: number;
  end_term_weight?: number;
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

// Re-export School types
export type { SchoolProfile, SchoolProfileUpdate, SchoolBrandingUpdate } from "./school.type";
