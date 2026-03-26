import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format a role string for display: replace underscores with spaces and
 * capitalize each word. e.g. "finance_officer" -> "Finance Officer"
 */
export function formatRoleLabel(role: string): string {
  return role
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
