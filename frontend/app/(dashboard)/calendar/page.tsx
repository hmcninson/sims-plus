import { Suspense } from "react";
import { getAcademicYears, getTerms } from "@/actions/academic.action";
import { getSchoolHolidays } from "@/actions/timetable.action";
import { CalendarView } from "./calendar-view";
import CalendarLoading from "./loading";
import type { Term } from "@/types";

export default async function CalendarPage() {
  // Fetch initial data in parallel
  const [academicYearsResult, holidaysResult] = await Promise.all([
    getAcademicYears(),
    getSchoolHolidays(),
  ]);

  const academicYears = academicYearsResult.success
    ? academicYearsResult.data || []
    : [];
  const holidays = holidaysResult.success
    ? holidaysResult.data || []
    : [];

  // Get current academic year
  const currentYear =
    academicYears.find((y) => y.is_current) || academicYears[0];

  // Get terms for current year
  let terms: Term[] = [];
  if (currentYear) {
    const termsResult = await getTerms(currentYear.id);
    terms = termsResult.success ? termsResult.data || [] : [];
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">School Calendar</h1>
        <p className="text-muted-foreground">
          View academic year, terms, holidays, and school events
        </p>
      </div>

      <Suspense fallback={<CalendarLoading />}>
        <CalendarView
          academicYears={academicYears}
          initialTerms={terms}
          initialHolidays={holidays}
          initialAcademicYearId={currentYear?.id}
        />
      </Suspense>
    </div>
  );
}
