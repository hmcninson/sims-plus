/**
 * Custom Role types for the granular permissions system.
 * Feature gate: Professional + Enterprise tiers only.
 */

export interface CustomRole {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  base_role: string;
  permissions: string[];
  is_system: boolean;
  user_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface CustomRoleCreate {
  name: string;
  base_role: string;
  permissions: string[];
  description?: string;
}

export interface CustomRoleUpdate {
  name?: string;
  permissions?: string[];
  description?: string;
}

export interface PermissionEntry {
  key: string;
  label: string;
  description: string;
}

export interface PermissionModule {
  module: string;
  permissions: PermissionEntry[];
}

export interface PermissionsCatalog {
  modules: PermissionModule[];
}

export interface CustomRoleListResponse {
  roles: CustomRole[];
}
