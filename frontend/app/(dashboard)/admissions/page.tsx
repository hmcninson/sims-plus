import { Suspense } from "react";
import { Metadata } from "next";
import { AdmissionsDashboardContent } from "./admissions-dashboard";

export const metadata: Metadata = {
  title: "Admissions",
  description: "Admissions overview and pipeline management",
};

export default function AdmissionsDashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <AdmissionsDashboardContent />
    </Suspense>
  );
}
