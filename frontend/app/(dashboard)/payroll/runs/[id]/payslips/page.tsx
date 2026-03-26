import { Suspense } from "react";
import { Metadata } from "next";
import { PayslipsList } from "./payslips-list";

export const metadata: Metadata = {
  title: "Payslips",
  description: "View and generate payslips for a payroll run",
};

export default async function PayslipsPage({
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
      <PayslipsList runId={id} />
    </Suspense>
  );
}
