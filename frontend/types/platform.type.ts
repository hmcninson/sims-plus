/**
 * Types for the platform admin portal (admin.simsplus.io).
 */

export interface PlatformUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: "platform_admin";
  mfa_enabled: boolean;
}

export interface PlatformLoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: PlatformUser;
}

export interface PlatformMFARequiredResponse {
  mfa_required: true;
  mfa_pending_token: string;
}

export interface PlatformMFASetupRequiredResponse {
  mfa_setup_required: true;
  setup_token: string;
  message: string;
}

export type PlatformLoginResult =
  | PlatformLoginResponse
  | PlatformMFARequiredResponse
  | PlatformMFASetupRequiredResponse;

export interface TenantSummary {
  id: string;
  name: string;
  subdomain: string;
  tenant_type: string;
  status: string;
  subscription_tier: string;
  is_active: boolean;
  max_students: number;
  max_staff: number;
  created_at: string;
  student_count: number;
  staff_count: number;
  school_count: number;
}

export interface TenantDetail extends TenantSummary {
  email: string | null;
  phone: string | null;
  logo_url: string | null;
  primary_color: string | null;
  features: Record<string, unknown> | null;
  subscription_start: string | null;
  subscription_end: string | null;
  trial_ends_at: string | null;
  updated_at: string;
}

export interface TenantListResponse {
  items: TenantSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface ImpersonationResponse {
  access_token: string;
  tenant_id: string;
  tenant_name: string;
  tenant_subdomain: string;
  expires_in: number;
}

export interface PlatformAnalytics {
  total_tenants: number;
  active_tenants: number;
  trial_tenants: number;
  suspended_tenants: number;
  total_students: number;
  total_staff: number;
  total_schools: number;
  tenants_by_plan: Record<string, number>;
  recent_registrations: TenantSummary[];
}

export interface PlatformAuditEntry {
  id: string;
  actor_user_id: string;
  actor_email: string | null;
  action: string;
  target_tenant_id: string | null;
  target_tenant_name: string | null;
  target_entity_type: string | null;
  target_entity_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface PlatformAuditLogResponse {
  items: PlatformAuditEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface MFAGenerateResponse {
  secret: string;
  provisioning_uri: string;
  qr_code_base64: string;
}
