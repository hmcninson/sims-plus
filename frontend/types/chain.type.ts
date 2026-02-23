/**
 * SIMS Plus - School Chain Type Definitions
 *
 * Types for multi-school chain management (Sprint 17-18). A chain tenant
 * manages multiple schools under one subdomain. Single-school tenants
 * continue to work without any chain-related UI or headers.
 */

// =========================
// School within a Chain
// =========================

export interface ChainSchool {
  id: string;
  tenant_id: string;
  name: string;
  code?: string;
  address?: string;
  phone?: string;
  email?: string;
  logo_url?: string;
  student_id_prefix?: string;
  student_count: number;
  staff_count: number;
  created_at: string;
  updated_at: string;
}

// =========================
// Chain Dashboard
// =========================

export interface ChainSchoolMetrics {
  school_id: string;
  school_name: string;
  school_code?: string;
  logo_url?: string;
  total_students: number;
  total_staff: number;
  attendance_rate: number;
  total_billed: number;
  total_collected: number;
  collection_rate: number;
  outstanding: number;
}

export interface ChainDashboard {
  total_schools: number;
  total_students: number;
  total_staff: number;
  overall_attendance_rate: number;
  total_revenue: number;
  total_outstanding: number;
  schools: ChainSchoolMetrics[];
}

// =========================
// User School Access
// =========================

export interface UserSchoolAccess {
  id: string;
  school_id: string;
  school_name: string;
  school_code?: string;
  role_at_school: string;
  is_primary: boolean;
}

export interface ChainUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  status: string;
  school_accesses: UserSchoolAccess[];
  created_at: string;
  updated_at: string;
}

export interface ChainUserListResponse {
  items: ChainUser[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// =========================
// Chain Registration & Management
// =========================

export interface ChainRegistrationData {
  chain_name: string;
  subdomain: string;
  admin_email: string;
  admin_first_name: string;
  admin_last_name: string;
  admin_password: string;
  admin_phone?: string;
  plan?: string;
}

export interface AddSchoolData {
  name: string;
  code: string;
  address?: string;
  phone?: string;
  email?: string;
  student_id_prefix?: string;
}

export interface AssignUserToSchoolData {
  user_id: string;
  school_id: string;
  role_at_school: string;
  is_primary?: boolean;
}

export interface RemoveUserFromSchoolData {
  user_id: string;
  school_id: string;
}

// =========================
// School Switcher State
// =========================

/** Lightweight school info used in the school switcher dropdown. */
export interface SwitcherSchool {
  id: string;
  name: string;
  code?: string;
  logo_url?: string;
}
