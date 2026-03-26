import { Suspense } from "react";
import { Loader2, Info } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { getCurriculumProfiles } from "@/actions/curriculum.action";
import { getAcademicYears, getSubjects } from "@/actions/academic.action";
import { getStudents } from "@/actions/students.action";
import { PredictedGradeEntry } from "@/components/curriculum/PredictedGradeEntry";
import type { CurriculumType } from "@/types/curriculum.type";

export const metadata = {
  title: "Predicted Grades",
  description: "Manage predicted and target grades for external exam students.",
};

const PREDICTED_GRADE_TYPES: CurriculumType[] = ["cambridge", "edexcel", "ib"];

export default async function Page() {
  const [profilesResult, academicYearsResult, subjectsResult, studentsResult] =
    await Promise.all([
      getCurriculumProfiles(),
      getAcademicYears(),
      getSubjects(),
      getStudents({ page_size: 500 }),
    ]);

  const profiles = profilesResult.success ? profilesResult.data ?? [] : [];
  const hasApplicableProfile = profiles.some((p) =>
    PREDICTED_GRADE_TYPES.includes(p.curriculum_type),
  );

  if (!hasApplicableProfile) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Predicted Grades</h1>
          <p className="text-sm text-muted-foreground">
            Manage predicted and target grades for students.
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <Info className="mb-3 size-10 text-blue-500" />
            <CardTitle className="mb-2 text-lg">Not Applicable</CardTitle>
            <CardDescription className="max-w-md">
              Predicted grades are used for Cambridge, Edexcel, and IB curricula.
              Your school does not currently have any applicable curriculum profile configured.
            </CardDescription>
          </CardContent>
        </Card>
      </div>
    );
  }

  const academicYears = academicYearsResult.success ? academicYearsResult.data ?? [] : [];
  const subjects = subjectsResult.success
    ? (subjectsResult.data ?? []).map((s) => ({ id: s.id, name: s.name }))
    : [];
  const students =
    studentsResult.success && studentsResult.data
      ? studentsResult.data.items.map((s) => ({
          id: s.id,
          name: `${s.first_name} ${s.last_name}`,
          class_id: s.class_name, // Note: we use class_name as fallback identifier
        }))
      : [];

  // Build grade options from Cambridge-type scales (A*-U etc)
  const gradeOptions = [
    "A*",
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "U",
    "7",
    "6",
    "5",
    "4",
    "3",
    "2",
    "1",
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Predicted Grades</h1>
        <p className="text-sm text-muted-foreground">
          Enter predicted and target grades for Cambridge, Edexcel, and IB students.
        </p>
      </div>

      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <PredictedGradeEntry
          academicYears={academicYears}
          gradeOptions={gradeOptions}
          subjects={subjects}
          students={students}
        />
      </Suspense>
    </div>
  );
}
