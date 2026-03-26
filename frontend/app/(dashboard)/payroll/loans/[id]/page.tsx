import { Suspense } from "react";
import { Metadata } from "next";
import { LoanDetail } from "./loan-detail";

export const metadata: Metadata = {
  title: "Loan Detail",
  description: "View loan details and manage lifecycle",
};

export default async function LoanDetailPage({
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
      <LoanDetail loanId={id} />
    </Suspense>
  );
}
