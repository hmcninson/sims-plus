import { Suspense } from "react";
import { Metadata } from "next";
import { FinanceDashboard } from "./finance-dashboard";

export const metadata: Metadata = {
  title: "Finance",
  description: "Finance overview and management",
};

export default function FinancePage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <FinanceDashboard />
    </Suspense>
  );
}
