import type { SchoolHoliday, Term, AcademicYear } from "@/types";

/**
 * Generate iCal format for events
 */
export function generateICalendar(
  events: SchoolHoliday[],
  terms: Term[],
  academicYear?: AcademicYear
): string {
  const lines: string[] = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//SIMS Plus//School Calendar//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    `X-WR-CALNAME:${academicYear?.name || "School Calendar"}`,
  ];

  // Add term events
  terms.forEach((term) => {
    const startDate = formatICalDate(new Date(term.start_date));
    const endDate = formatICalDate(addDays(new Date(term.end_date), 1)); // End date is exclusive in iCal

    lines.push(
      "BEGIN:VEVENT",
      `DTSTART;VALUE=DATE:${startDate}`,
      `DTEND;VALUE=DATE:${endDate}`,
      `SUMMARY:${escapeICalText(term.name)}`,
      `DESCRIPTION:${escapeICalText(`Academic term: ${term.name}`)}`,
      `UID:term-${term.id}@simsplus`,
      "TRANSP:TRANSPARENT",
      "END:VEVENT"
    );
  });

  // Add holiday/event entries
  events.forEach((event) => {
    const eventDate = formatICalDate(new Date(event.date));
    const nextDay = formatICalDate(addDays(new Date(event.date), 1));

    lines.push(
      "BEGIN:VEVENT",
      `DTSTART;VALUE=DATE:${eventDate}`,
      `DTEND;VALUE=DATE:${nextDay}`,
      `SUMMARY:${escapeICalText(event.name)}`,
      event.description ? `DESCRIPTION:${escapeICalText(event.description)}` : "",
      `CATEGORIES:${getCategoryFromType(event.holiday_type)}`,
      `UID:event-${event.id}@simsplus`,
      "TRANSP:TRANSPARENT",
      "END:VEVENT"
    );
  });

  lines.push("END:VCALENDAR");

  return lines.filter((line) => line).join("\r\n");
}

/**
 * Generate Google Calendar URL for a single event
 */
export function generateGoogleCalendarUrl(event: SchoolHoliday): string {
  const baseUrl = "https://calendar.google.com/calendar/render";
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: event.name,
    dates: `${formatGoogleDate(event.date)}/${formatGoogleDate(addDays(new Date(event.date), 1))}`,
    details: event.description || "",
  });

  return `${baseUrl}?${params.toString()}`;
}

/**
 * Generate Google Calendar URL for multiple events (term view)
 */
export function generateGoogleCalendarUrlForTerm(term: Term): string {
  const baseUrl = "https://calendar.google.com/calendar/render";
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: term.name,
    dates: `${formatGoogleDate(term.start_date)}/${formatGoogleDate(addDays(new Date(term.end_date), 1))}`,
    details: `Academic term: ${term.name}`,
  });

  return `${baseUrl}?${params.toString()}`;
}

/**
 * Download iCal file
 */
export function downloadICalFile(
  events: SchoolHoliday[],
  terms: Term[],
  academicYear?: AcademicYear,
  filename = "school-calendar.ics"
): void {
  const icalContent = generateICalendar(events, terms, academicYear);
  const blob = new Blob([icalContent], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// Helper functions

function formatICalDate(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}${month}${day}`;
}

function formatGoogleDate(date: Date | string): string {
  return formatICalDate(date);
}

function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

function escapeICalText(text: string): string {
  return text
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,")
    .replace(/\n/g, "\\n");
}

function getCategoryFromType(type: string): string {
  switch (type) {
    case "holiday":
      return "Public Holiday";
    case "vacation":
      return "Vacation";
    case "exam":
      return "Examination";
    case "event":
      return "School Event";
    default:
      return "Event";
  }
}
