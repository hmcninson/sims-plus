import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { getClasses, getAcademicYears, getTerms } from "@/actions/academic.action";
import { getLearningAreas } from "@/actions/preschool.action";
import { ReportsManager } from "./reports-manager";

export const metadata = {
  title: "Progress Reports - Preschool - SIMS Plus",
  description: "Generate and manage preschool progress reports",
};

// Preschool class levels
const PRESCHOOL_LEVELS = ["creche", "preschool", "nursery_1", "nursery_2", "kg_1", "kg_2"];

export default async function PreschoolReportsPage() {
  // Fetch all required data in parallel
  const [classesResult, academicYearsResult, learningAreasResult] = await Promise.all([
    getClasses(true),
    getAcademicYears(true),
    getLearningAreas(),
  ]);

  // Filter to preschool classes only
  const allClasses = classesResult.success ? classesResult.data || [] : [];
  const preschoolClasses = allClasses.filter(
    (c) => c.level && PRESCHOOL_LEVELS.includes(c.level)
  );

  const academicYears = academicYearsResult.success ? academicYearsResult.data || [] : [];
  const learningAreas = learningAreasResult.success ? learningAreasResult.data || [] : [];

  // Get current academic year
  let currentAcademicYear =
    academicYears.find((y) => y.is_current) || academicYears[0] || null;

  // If current academic year has no terms, fetch them separately
  if (currentAcademicYear && (!currentAcademicYear.terms || currentAcademicYear.terms.length === 0)) {
    const termsResult = await getTerms(currentAcademicYear.id);
    if (termsResult.success && termsResult.data) {
      currentAcademicYear = {
        ...currentAcademicYear,
        terms: termsResult.data,
      };
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Progress Reports</h1>
        <p className="text-muted-foreground">
          Generate and manage narrative-based developmental progress reports
        </p>
      </div>

      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <ReportsManager
          classes={preschoolClasses}
          academicYears={academicYears}
          currentAcademicYear={currentAcademicYear}
          learningAreas={learningAreas}
        />
      </Suspense>
    </div>
  );
}
