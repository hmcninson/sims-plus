import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { getClasses, getAcademicYears, getTerms } from "@/actions/academic.action";
import { getLearningAreas, getRatingScales } from "@/actions/preschool.action";
import { AssessmentEntry } from "./assessment-entry";

export const metadata = {
  title: "Skill Assessment - Preschool - SIMS Plus",
  description: "Assess preschool students on developmental skills",
};

// Preschool class levels
const PRESCHOOL_LEVELS = ["creche", "preschool", "nursery_1", "nursery_2", "kg_1", "kg_2"];

export default async function PreschoolAssessmentPage() {
  // Fetch all required data in parallel
  const [classesResult, academicYearsResult, learningAreasResult, ratingScalesResult] =
    await Promise.all([
      getClasses(true), // Include sections
      getAcademicYears(true), // Include terms
      getLearningAreas(),
      getRatingScales(),
    ]);

  // Filter to preschool classes only
  const allClasses = classesResult.success ? classesResult.data || [] : [];
  const preschoolClasses = allClasses.filter(
    (c) => c.level && PRESCHOOL_LEVELS.includes(c.level)
  );

  const academicYears = academicYearsResult.success ? academicYearsResult.data || [] : [];
  const learningAreas = learningAreasResult.success ? learningAreasResult.data || [] : [];
  const ratingScales = ratingScalesResult.success ? ratingScalesResult.data || [] : [];

  // Get default rating scale
  const defaultRatingScale =
    ratingScales.find((s) => s.is_default) || ratingScales[0] || null;

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
        <h1 className="text-2xl font-bold tracking-tight">Skill Assessment</h1>
        <p className="text-muted-foreground">
          Assess students on developmental skills across learning areas
        </p>
      </div>

      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <AssessmentEntry
          classes={preschoolClasses}
          academicYears={academicYears}
          currentAcademicYear={currentAcademicYear}
          learningAreas={learningAreas}
          ratingScale={defaultRatingScale}
        />
      </Suspense>
    </div>
  );
}
