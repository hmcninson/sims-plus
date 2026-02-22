import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { getAcademicYears, getClasses } from "@/actions/academic.action";
import { ReportCardsManagement } from "./report-cards-management";

export const metadata = {
  title: "Report Cards",
  description: "Generate and manage student report cards",
};

export default async function ReportCardsPage() {
  const [academicYearsResult, classesResult] = await Promise.all([
    getAcademicYears(true),
    getClasses(true),
  ]);

  const academicYears = academicYearsResult.success ? academicYearsResult.data || [] : [];
  const classes = classesResult.success ? classesResult.data || [] : [];

  // Filter out preschool classes
  const preschoolPatterns = /^(nursery|kg|kindergarten|creche|pre-school|preschool)/i;
  const filteredClasses = classes
    .filter((cls) => cls.level !== "preschool" && !preschoolPatterns.test(cls.name))
    .sort((a, b) => a.sequence - b.sequence);

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <ReportCardsManagement
        academicYears={academicYears}
        classes={filteredClasses}
      />
    </Suspense>
  );
}
