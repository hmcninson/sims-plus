import { Suspense } from "react";
import { Metadata } from "next";
import { PayrollReports } from "./payroll-reports";

export const metadata: Metadata = {
  title: "Payroll Reports",
  description: "Payroll reports, statutory returns, and department summaries",
};

export default function PayrollReportsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <PayrollReports />
    </Suspense>
  );
}
