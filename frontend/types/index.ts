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
  tenant_id: string;
  school_id?: string;
  avatar_url?: string;
  email_verified: boolean;
  mfa_enabled: boolean;
  created_at: string;
  updated_at: string;
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

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  tenant_type: TenantType;
  subscription_tier: SubscriptionTier;
  email?: string;
  phone?: string;
  is_active: boolean;
  created_at: string;
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
  is_active: boolean;
}

// =========================
// Student Types
// =========================

export type Gender = "male" | "female";
export type StudentStatus = "active" | "inactive" | "graduated" | "withdrawn" | "transferred";

export interface Student {
  id: string;
  tenant_id: string;
  school_id: string;
  student_id: string;
  first_name: string;
  last_name: string;
  other_names?: string;
  gender: Gender;
  date_of_birth: string;
  admission_date: string;
  admission_number?: string;
  status: StudentStatus;
  class_id?: string;
  section_id?: string;
  photo_url?: string;
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
