/**
 * SIMS Plus - School Type Definitions
 */

export interface SchoolProfile {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  code?: string;
  school_type: string;

  // Contact Information
  email?: string;
  phone?: string;
  website?: string;

  // Address
  address?: string;
  city?: string;
  region?: string;
  gps_address?: string;

  // Branding
  logo_url?: string;
  primary_color?: string;
  motto?: string;
  description?: string;
  year_established?: number;

  // Features
  uses_boarding: boolean;
  uses_transport: boolean;

  // Student ID Settings
  student_id_prefix: string;

  // Status
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SchoolProfileUpdate {
  // Basic Info
  motto?: string;
  description?: string;
  year_established?: number;

  // Contact Information
  email?: string;
  phone?: string;
  website?: string;

  // Address
  address?: string;
  city?: string;
  region?: string;
  gps_address?: string;

  // Branding
  logo_url?: string;
  primary_color?: string;

  // Features
  uses_boarding?: boolean;
  uses_transport?: boolean;

  // Student ID Settings
  student_id_prefix?: string;
}

export interface SchoolBrandingUpdate {
  logo_url?: string;
  primary_color?: string;
}

export interface FileUploadResponse {
  url: string;
  key: string;
  filename: string;
  content_type: string;
  size: number;
}
