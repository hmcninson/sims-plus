import { Suspense } from "react";
import { Metadata } from "next";
import { PayrollAuditLog } from "./payroll-audit-log";

export const metadata: Metadata = {
  title: "Payroll Audit Log",
  description: "View payroll audit trail and change history",
};

export default function PayrollAuditPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <PayrollAuditLog />
    </Suspense>
  );
}
