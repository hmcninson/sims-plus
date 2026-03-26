import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { getClasses } from "@/actions/academic.action";
import { getAcademicYears } from "@/actions/academic.action";
import { PortfolioManager } from "./portfolio-manager";

export const metadata = {
  title: "Learning Portfolio - Preschool - SIMS Plus",
  description: "Create and manage learning stories for preschool students",
};

const PRESCHOOL_LEVELS = ["creche", "preschool", "nursery_1", "nursery_2", "kg_1", "kg_2"];

export default async function PortfolioPage() {
  const [classesResult, yearsResult] = await Promise.all([
    getClasses(true),
    getAcademicYears(true),
  ]);

  const allClasses = classesResult.success ? classesResult.data || [] : [];
  const preschoolClasses = allClasses.filter(
    (c) => c.level && PRESCHOOL_LEVELS.includes(c.level)
  );

  const academicYears = yearsResult.success ? yearsResult.data || [] : [];
  // Get terms from the active academic year
  const activeYear = academicYears.find((y) => y.status === "active");
  const terms = activeYear?.terms || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Learning Portfolio</h1>
        <p className="text-muted-foreground">
          Document and share children&apos;s learning journeys through narrative stories
        </p>
      </div>

      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <PortfolioManager classes={preschoolClasses} terms={terms} />
      </Suspense>
    </div>
  );
}
