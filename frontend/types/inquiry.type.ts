/**
 * SIMS Plus - Inquiry/Lead Management Type Definitions
 *
 * Types for pre-application inquiry tracking, communications,
 * follow-up tasks, bulk import, and duplicate checking.
 */

// =========================
// Enums / Union Types
// =========================

export type InquirySource =
  | "website"
  | "walk_in"
  | "phone"
  | "referral"
  | "event"
  | "social_media"
  | "other";

export type InquiryStatus =
  | "new"
  | "contacted"
  | "interested"
  | "applied"
  | "enrolled"
  | "lost";

export type CommunicationChannel = "sms" | "email" | "phone" | "in_person";

export type CommunicationDirection = "inbound" | "outbound";

export type FollowUpPriority = "low" | "medium" | "high";

// =========================
// Inquiry
// =========================

export interface Inquiry {
  id: string;
  tenant_id: string;
  school_id: string;
  source: InquirySource;
  status: InquiryStatus;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  gender: string | null;
  target_class_id: string | null;
  guardian_name: string;
  guardian_phone: string;
  guardian_email: string | null;
  assigned_to: string | null;
  referred_by: string | null;
  notes: string | null;
  converted_application_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface InquiryCreate {
  source: InquirySource;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  gender?: string | null;
  target_class_id?: string | null;
  guardian_name: string;
  guardian_phone: string;
  guardian_email?: string | null;
  referred_by?: string | null;
  notes?: string | null;
}

export interface InquiryUpdate {
  first_name?: string;
  last_name?: string;
  date_of_birth?: string | null;
  gender?: string | null;
  target_class_id?: string | null;
  guardian_name?: string;
  guardian_phone?: string;
  guardian_email?: string | null;
  referred_by?: string | null;
  notes?: string | null;
}

export interface InquiryListResponse {
  items: Inquiry[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface InquiryStats {
  total: number;
  by_status: Record<string, number>;
  by_source: Record<string, number>;
  conversion_rate: number;
}

// =========================
// Communication
// =========================

export interface Communication {
  id: string;
  inquiry_id: string;
  channel: CommunicationChannel;
  direction: CommunicationDirection;
  content: string;
  sent_by: string | null;
  sent_at: string;
  created_at: string;
}

export interface CommunicationCreate {
  channel: CommunicationChannel;
  direction: CommunicationDirection;
  content: string;
}

// =========================
// Follow-Up
// =========================

export interface FollowUp {
  id: string;
  inquiry_id: string;
  assigned_to: string;
  due_date: string;
  priority: FollowUpPriority;
  notes: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface FollowUpCreate {
  due_date: string;
  priority?: FollowUpPriority;
  notes?: string | null;
  assigned_to: string;
}

// =========================
// Bulk Import
// =========================

export interface BulkInquiryImportRow {
  first_name: string;
  last_name: string;
  guardian_name: string;
  guardian_phone: string;
  guardian_email?: string | null;
  source?: InquirySource | null;
  notes?: string | null;
}

export interface BulkImportRequest {
  rows: BulkInquiryImportRow[];
}

export interface BulkImportResponse {
  imported: number;
  skipped: number;
  errors: Array<{ row: number; error: string }>;
}

// =========================
// Duplicate Check
// =========================

export interface DuplicateCheckResponse {
  has_duplicates: boolean;
  matches: Inquiry[];
}

// =========================
// Convert
// =========================

export interface InquiryConvert {
  period_id: string;
}
