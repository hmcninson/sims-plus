/**
 * SIMS Plus - Messaging Type Definitions
 *
 * Shared types for SMS and Email messaging features.
 * Used by both the SMS and Email pages and their server actions.
 */

// =========================
// Recipient Types (shared)
// =========================

export type RecipientType = "all_parents" | "all_staff" | "class_parents" | "specific";

export interface RecipientInfo {
  name: string;
  phone: string | null;
  email: string | null;
  type: string;
}

export interface RecipientListResponse {
  recipients: RecipientInfo[];
  total: number;
}

// =========================
// SMS Types
// =========================

export interface SMSSendRequest {
  recipient_phones: string[];
  message: string;
}

export interface SMSBulkRequest {
  audience: RecipientType;
  class_id?: string;
  message: string;
}

export interface SMSLogEntry {
  id: string;
  recipient_phone: string;
  message: string;
  provider: string;
  status: string;
  sent_at: string | null;
  created_at: string;
}

export interface SMSHistoryResponse {
  items: SMSLogEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SMSStats {
  total_sent: number;
  total_delivered: number;
  total_failed: number;
  total_pending: number;
  credits_used: number;
}

// =========================
// Email Types
// =========================

export interface EmailSendRequest {
  recipient_emails: string[];
  subject: string;
  body: string;
  recipient_names?: string[];
}

export interface EmailBulkRequest {
  audience: RecipientType;
  class_id?: string;
  subject: string;
  body: string;
}

export interface EmailLogEntry {
  id: string;
  recipient_email: string;
  recipient_name: string | null;
  subject: string;
  status: string;
  sent_at: string | null;
  created_at: string;
}

export interface EmailHistoryResponse {
  items: EmailLogEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface EmailStats {
  total_sent: number;
  total_failed: number;
  total_pending: number;
  total_delivered: number;
  total_bounced: number;
}
