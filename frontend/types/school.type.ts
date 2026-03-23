/**
 * SIMS Plus - School Type Definitions
 */

export interface PreschoolSettings {
  enabled: boolean;
  daily_logs_enabled: boolean;
  meal_tracking: boolean;
  nap_tracking: boolean;
  diaper_tracking: boolean;
  potty_training_tracking: boolean;
  observation_photos_enabled: boolean;
  parent_daily_updates: boolean;
  default_rating_scale_id?: string;
}

export interface PreschoolSettingsUpdate {
  enabled?: boolean;
  daily_logs_enabled?: boolean;
  meal_tracking?: boolean;
  nap_tracking?: boolean;
  diaper_tracking?: boolean;
  potty_training_tracking?: boolean;
  observation_photos_enabled?: boolean;
  parent_daily_updates?: boolean;
  default_rating_scale_id?: string;
}

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

  // Classification
  category?: "public" | "private" | "international" | "faith_based" | null;
  boarding_type?: "day_only" | "boarding_only" | "mixed" | null;

  // ID Prefix Settings
  student_id_prefix: string;
  staff_id_prefix: string;

  // Preschool Settings
  preschool_settings?: PreschoolSettings;

  // Setup Wizard State
  setup_completed: boolean;
  setup_wizard_step: number;

  // Calendar & Registration
  calendar_type: string;
  ges_registration_number: string | null;

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

  // School Type
  school_type?: string;

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

  // Classification
  category?: "public" | "private" | "international" | "faith_based" | null;
  boarding_type?: "day_only" | "boarding_only" | "mixed" | null;

  // ID Prefix Settings
  student_id_prefix?: string;
  staff_id_prefix?: string;

  // GES Registration
  ges_registration_number?: string | null;

  // Calendar
  calendar_type?: string;
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
