/**
 * SIMS Plus - Interview & Screening Type Definitions
 *
 * Types for interview scheduling, feedback recording,
 * and screening checklist management.
 */

// =========================
// Enums / Union Types
// =========================

export type InterviewStatus =
  | "scheduled"
  | "completed"
  | "cancelled"
  | "no_show"
  | "rescheduled";

export type ScreeningCategory = "documents" | "academic" | "medical" | "other";

// =========================
// Interview
// =========================

export interface Interview {
  id: string;
  school_id: string;
  application_id: string;
  interviewer_id: string | null;
  interviewer_name: string | null;
  applicant_name: string | null;
  scheduled_date: string;
  scheduled_time: string | null;
  duration_minutes: number;
  venue: string;
  status: InterviewStatus;
  feedback: string | null;
  score: number | null;
  max_score: number | null;
  scoring_criteria: Record<string, { score: number; max: number }>;
  created_at: string;
  updated_at: string;
}

export interface InterviewCreate {
  application_id: string;
  interviewer_id: string;
  scheduled_date: string;
  scheduled_time?: string | null;
  duration_minutes?: number;
  venue: string;
}

export interface InterviewUpdate {
  scheduled_date?: string;
  scheduled_time?: string | null;
  duration_minutes?: number;
  venue?: string;
  interviewer_id?: string;
}

export interface InterviewFeedback {
  status: "completed" | "no_show";
  feedback?: string | null;
  score?: number | null;
  max_score?: number | null;
  scoring_criteria?: Record<string, { score: number; max: number }> | null;
}

export interface InterviewListResponse {
  items: Interview[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// =========================
// Screening Checklist
// =========================

export interface ScreeningItem {
  id: string;
  application_id: string;
  item_name: string;
  item_category: ScreeningCategory;
  is_completed: boolean;
  completed_by: string | null;
  completed_by_name: string | null;
  completed_at: string | null;
  notes: string | null;
  created_at: string;
}

export interface ScreeningItemCreate {
  item_name: string;
  item_category: ScreeningCategory;
}

export interface ScreeningItemBulkCreate {
  items: ScreeningItemCreate[];
}

export interface ScreeningItemComplete {
  notes?: string | null;
}

export interface ScreeningProgress {
  application_id: string;
  total_items: number;
  completed_items: number;
  progress_pct: number;
  items: ScreeningItem[];
}
