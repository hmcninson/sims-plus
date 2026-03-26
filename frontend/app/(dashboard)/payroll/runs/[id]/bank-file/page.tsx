import { Suspense } from "react";
import { Metadata } from "next";
import { BankFileGeneration } from "./bank-file-generation";

export const metadata: Metadata = {
  title: "Bank File Generation",
  description: "Generate bank payment files for a payroll run",
};

export default async function BankFilePage({
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
      <BankFileGeneration runId={id} />
    </Suspense>
  );
}
