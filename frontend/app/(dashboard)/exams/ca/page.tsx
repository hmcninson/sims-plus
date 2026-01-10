import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { getAcademicYears, getClasses, getSubjects } from "@/actions/academic.action";
import { CAManagement } from "./ca-management";

export const metadata = {
  title: "Continuous Assessment - SIMS Plus",
  description: "Manage continuous assessment scores.",
};

export default async function CAPage() {
  // Fetch all required data
  const [academicYearsResult, classesResult, subjectsResult] = await Promise.all([
    getAcademicYears(),
    getClasses(true),
    getSubjects(),
  ]);

  const academicYears = academicYearsResult.success ? academicYearsResult.data || [] : [];
  const classes = classesResult.success ? classesResult.data || [] : [];
  const subjects = subjectsResult.success ? subjectsResult.data || [] : [];

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <CAManagement
        academicYears={academicYears}
        classes={classes}
        subjects={subjects}
      />
    </Suspense>
  );
}
