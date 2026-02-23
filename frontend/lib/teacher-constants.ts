/**
 * SIMS Plus - Teacher Portal Constants
 *
 * Shared constants used across the teacher portal pages.
 * Centralised here to avoid duplication and ensure consistency.
 */

import type { TeacherNoteType } from "@/types/teacher.type";

/**
 * Badge/chip color classes for each note type.
 * Includes background, text, and border classes for flexible use.
 */
export const NOTE_TYPE_COLORS: Record<TeacherNoteType, string> = {
  positive: "bg-green-100 text-green-800 border-green-300",
  concern: "bg-red-100 text-red-800 border-red-300",
  information: "bg-blue-100 text-blue-800 border-blue-300",
  action_required: "bg-amber-100 text-amber-800 border-amber-300",
};

/**
 * Human-readable labels for each note type.
 */
export const NOTE_TYPE_LABELS: Record<TeacherNoteType, string> = {
  positive: "Positive",
  concern: "Concern",
  information: "Information",
  action_required: "Action Required",
};
