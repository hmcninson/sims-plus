import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { getClasses } from "@/actions/academic.action";
import { ExtendedCareManager } from "./extended-care-manager";

export const metadata = {
  title: "Extended Care - Preschool - SIMS Plus",
  description: "Manage before and after school care for preschool students",
};

const PRESCHOOL_LEVELS = ["creche", "preschool", "nursery_1", "nursery_2", "kg_1", "kg_2"];

export default async function ExtendedCarePage() {
  const classesResult = await getClasses(true);
  const allClasses = classesResult.success ? classesResult.data || [] : [];
  const preschoolClasses = allClasses.filter(
    (c) => c.level && PRESCHOOL_LEVELS.includes(c.level)
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Extended Care</h1>
        <p className="text-muted-foreground">
          Manage before-school and after-school care check-ins and billing
        </p>
      </div>

      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <ExtendedCareManager classes={preschoolClasses} />
      </Suspense>
    </div>
  );
}
