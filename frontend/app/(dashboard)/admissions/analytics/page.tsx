import { Suspense } from "react";
import { Metadata } from "next";
import { AnalyticsDashboard } from "./analytics-dashboard";

export const metadata: Metadata = {
  title: "Admissions Analytics",
  description: "Enrollment funnel, trends, and analytics",
};

export default function AnalyticsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <AnalyticsDashboard />
    </Suspense>
  );
}
