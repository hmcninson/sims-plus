import { Suspense } from "react";
import { Metadata } from "next";
import { LoanApplicationWizard } from "./loan-application-wizard";

export const metadata: Metadata = {
  title: "New Loan Application",
  description: "Apply for a new staff loan",
};

export default function NewLoanPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <LoanApplicationWizard />
    </Suspense>
  );
}
