import { Suspense } from "react";
import { Metadata } from "next";
import { PayrollRunDetail } from "./payroll-run-detail";

export const metadata: Metadata = {
  title: "Payroll Run Detail",
  description: "View payroll run details and manage processing",
};

export default async function PayrollRunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <PayrollRunDetail runId={id} />
    </Suspense>
  );
}
