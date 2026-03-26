import { Suspense } from "react";
import { Metadata } from "next";
import { CapacityDashboard } from "./capacity-dashboard";

export const metadata: Metadata = {
  title: "Capacity Planning",
  description: "Manage enrollment targets and capacity per class",
};

export default function CapacityPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <CapacityDashboard />
    </Suspense>
  );
}
