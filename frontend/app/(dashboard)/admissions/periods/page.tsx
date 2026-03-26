import { Suspense } from "react";
import { Metadata } from "next";
import { PeriodsManagement } from "./periods-management";

export const metadata: Metadata = {
  title: "Admission Periods",
  description: "Manage admission periods and application windows",
};

export default function PeriodsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <PeriodsManagement />
    </Suspense>
  );
}
