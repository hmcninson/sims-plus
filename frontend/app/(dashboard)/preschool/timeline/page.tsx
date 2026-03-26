import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { getClasses } from "@/actions/academic.action";
import { StudentTimelinePage } from "./student-timeline";

export const metadata = {
  title: "Student Timeline - Preschool - SIMS Plus",
  description: "View a chronological timeline of a student's preschool journey",
};

const PRESCHOOL_LEVELS = ["creche", "preschool", "nursery_1", "nursery_2", "kg_1", "kg_2"];

export default async function TimelinePage() {
  const classesResult = await getClasses(true);
  const allClasses = classesResult.success ? classesResult.data || [] : [];
  const preschoolClasses = allClasses.filter(
    (c) => c.level && PRESCHOOL_LEVELS.includes(c.level)
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Student Timeline</h1>
        <p className="text-muted-foreground">
          View a chronological timeline of assessments, observations, incidents, and learning stories
        </p>
      </div>

      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <StudentTimelinePage classes={preschoolClasses} />
      </Suspense>
    </div>
  );
}
