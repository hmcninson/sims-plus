/**
 * SIMS Plus - Formatting Utilities
 *
 * Formatting utilities for dates, currency, and phone numbers
 */

/**
 * Format phone number to Ghana standard (+233XXXXXXXXX)
 */
export function formatGhanaPhone(phone: string): string {
  const digits = phone.replace(/\D/g, "");

  if (digits.startsWith("233")) {
    return `+${digits}`;
  } else if (digits.startsWith("0") && digits.length === 10) {
    return `+233${digits.slice(1)}`;
  } else if (digits.length === 9) {
    return `+233${digits}`;
  }

  return phone;
}

/**
 * Format date to Ghana standard (DD/MM/YYYY)
 */
export function formatGhanaDate(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/**
 * Format date to relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;

  return formatGhanaDate(d);
}

/**
 * Format currency to Ghana Cedis (GHS)
 */
export function formatGHS(amount: number): string {
  return new Intl.NumberFormat("en-GH", {
    style: "currency",
    currency: "GHS",
    minimumFractionDigits: 2,
  }).format(amount);
}

/**
 * Generate initials from name
 */
export function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

/**
 * Truncate text with ellipsis
 */
export function truncate(text: string, length: number): string {
  if (text.length <= length) return text;
  return `${text.slice(0, length)}...`;
}

/**
 * Format number with thousands separator and decimal places
 */
export function formatNumber(amount: number | string, decimals: number = 2): string {
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  return new Intl.NumberFormat("en-GH", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num);
}

// Aliases for common naming conventions
export const formatCurrency = formatGHS;
export const formatDate = formatGhanaDate;
