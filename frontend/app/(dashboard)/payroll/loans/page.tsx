import { Suspense } from "react";
import { Metadata } from "next";
import { LoansList } from "./loans-list";

export const metadata: Metadata = {
  title: "Staff Loans",
  description: "Manage staff loan applications and repayments",
};

export default function LoansPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <LoansList />
    </Suspense>
  );
}
