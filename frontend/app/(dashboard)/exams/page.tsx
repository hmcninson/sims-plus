import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { getExams } from "@/actions/exams.action";
import { getAcademicYears } from "@/actions/academic.action";
import { ExamsManagement } from "./exams-management";

export const metadata = {
  title: "Examinations",
  description: "Manage exams and assessments.",
};

export default async function ExamsPage() {
  // Fetch exams and academic years in parallel
  const [examsResult, academicYearsResult] = await Promise.all([
    getExams({ page_size: 50 }),
    getAcademicYears(),
  ]);

  const exams = examsResult.success && examsResult.data ? examsResult.data.items : [];
  const academicYears = academicYearsResult.success ? academicYearsResult.data || [] : [];

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <ExamsManagement
        initialExams={exams}
        academicYears={academicYears}
      />
    </Suspense>
  );
}
