import { Suspense } from "react";
import { Metadata } from "next";
import { LoanPortfolioDashboard } from "./loan-portfolio-dashboard";

export const metadata: Metadata = {
  title: "Loan Portfolio",
  description: "Loan portfolio analytics and aging report",
};

export default function LoanPortfolioPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <LoanPortfolioDashboard />
    </Suspense>
  );
}
