import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { getClasses } from "@/actions/academic.action";
import { getLearningAreas } from "@/actions/preschool.action";
import { ObservationsManager } from "./observations-manager";

export const metadata = {
  title: "Observations - Preschool - SIMS Plus",
  description: "Record and manage student progress observations",
};

// Preschool class levels
const PRESCHOOL_LEVELS = ["creche", "preschool", "nursery_1", "nursery_2", "kg_1", "kg_2"];

export default async function ObservationsPage() {
  // Fetch classes and learning areas
  const [classesResult, learningAreasResult] = await Promise.all([
    getClasses(true),
    getLearningAreas(),
  ]);

  // Filter to preschool classes only
  const allClasses = classesResult.success ? classesResult.data || [] : [];
  const preschoolClasses = allClasses.filter(
    (c) => c.level && PRESCHOOL_LEVELS.includes(c.level)
  );

  const learningAreas = learningAreasResult.success ? learningAreasResult.data || [] : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Progress Observations</h1>
        <p className="text-muted-foreground">
          Record anecdotes, milestones, and observations for each child
        </p>
      </div>

      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <ObservationsManager
          classes={preschoolClasses}
          learningAreas={learningAreas}
        />
      </Suspense>
    </div>
  );
}
