import { Suspense } from "react";
import { Metadata } from "next";
import { StaffYearToDate } from "./staff-year-to-date";

export const metadata: Metadata = {
  title: "Staff Payslips & YTD",
  description: "Year-to-date salary breakdown and payslip downloads",
};

export default async function StaffPayslipsPage({
  params,
}: {
  params: Promise<{ staffId: string }>;
}) {
  const { staffId } = await params;

  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <StaffYearToDate staffId={staffId} />
    </Suspense>
  );
}
