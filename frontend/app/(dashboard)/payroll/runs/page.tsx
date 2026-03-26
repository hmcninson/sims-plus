import { Suspense } from "react";
import { Metadata } from "next";
import { PayrollRunsList } from "./payroll-runs-list";

export const metadata: Metadata = {
  title: "Payroll Runs",
  description: "View and manage all payroll runs",
};

export default function PayrollRunsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <PayrollRunsList />
    </Suspense>
  );
}
