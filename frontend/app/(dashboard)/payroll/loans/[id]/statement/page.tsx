import { Suspense } from "react";
import { Metadata } from "next";
import { LoanStatementView } from "./loan-statement-view";

export const metadata: Metadata = {
  title: "Loan Statement",
  description: "View and download loan statement",
};

export default async function LoanStatementPage({
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
      <LoanStatementView loanId={id} />
    </Suspense>
  );
}
