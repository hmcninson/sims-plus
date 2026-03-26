import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { getClasses } from "@/actions/academic.action";
import { IncidentsManager } from "./incidents-manager";

export const metadata = {
  title: "Incidents - Preschool - SIMS Plus",
  description: "Track and manage preschool incidents",
};

const PRESCHOOL_LEVELS = ["creche", "preschool", "nursery_1", "nursery_2", "kg_1", "kg_2"];

export default async function IncidentsPage() {
  const classesResult = await getClasses(true);
  const allClasses = classesResult.success ? classesResult.data || [] : [];
  const preschoolClasses = allClasses.filter(
    (c) => c.level && PRESCHOOL_LEVELS.includes(c.level)
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Incident Reports</h1>
        <p className="text-muted-foreground">
          Track and manage incidents, accidents, and behavioural events
        </p>
      </div>

      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <IncidentsManager classes={preschoolClasses} />
      </Suspense>
    </div>
  );
}
