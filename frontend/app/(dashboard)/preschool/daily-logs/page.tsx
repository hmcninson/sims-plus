import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { getClasses } from "@/actions/academic.action";
import { DailyLogsManager } from "./daily-logs-manager";

export const metadata = {
  title: "Daily Logs - Preschool - SIMS Plus",
  description: "Track daily activities for preschool students",
};

// Preschool class levels
const PRESCHOOL_LEVELS = ["creche", "preschool", "nursery_1", "nursery_2", "kg_1", "kg_2"];

export default async function DailyLogsPage() {
  // Fetch classes
  const classesResult = await getClasses(true);

  // Filter to preschool classes only
  const allClasses = classesResult.success ? classesResult.data || [] : [];
  const preschoolClasses = allClasses.filter(
    (c) => c.level && PRESCHOOL_LEVELS.includes(c.level)
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Daily Activity Logs</h1>
        <p className="text-muted-foreground">
          Track meals, naps, moods, and daily activities for each child
        </p>
      </div>

      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <DailyLogsManager classes={preschoolClasses} />
      </Suspense>
    </div>
  );
}
