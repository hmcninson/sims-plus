import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { getClasses, getAcademicYears, getSubjects } from "@/actions/academic.action";
import { getTeachingStaff } from "@/actions/staff.action";
import { getSchoolPeriods } from "@/actions/timetable.action";
import { TimetableManagement } from "./timetable-management";

export const metadata = {
  title: "Class Timetable",
  description: "Manage weekly class schedules and timetables",
};

export default async function TimetablePage() {
  // Fetch all required data in parallel
  // Note: School-wide periods are fetched here as default; class/section-specific
  // periods are fetched dynamically in the client component
  const [classesResult, academicYearsResult, subjectsResult, teachersResult, defaultPeriodsResult] = await Promise.all([
    getClasses(),
    getAcademicYears(false),
    getSubjects(),
    getTeachingStaff(),
    getSchoolPeriods(), // School-wide periods (default)
  ]);

  const classes = classesResult.success ? classesResult.data || [] : [];
  const academicYears = academicYearsResult.success ? academicYearsResult.data || [] : [];
  const subjects = subjectsResult.success ? subjectsResult.data || [] : [];
  const teachers = teachersResult.success ? teachersResult.data || [] : [];
  const defaultPeriods = defaultPeriodsResult.success ? defaultPeriodsResult.data || [] : [];

  // Find current academic year
  const currentYear = academicYears.find((y) => y.is_current) || academicYears[0];

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <TimetableManagement
        classes={classes}
        academicYears={academicYears}
        subjects={subjects}
        teachers={teachers}
        defaultPeriods={defaultPeriods}
        defaultAcademicYearId={currentYear?.id}
      />
    </Suspense>
  );
}
