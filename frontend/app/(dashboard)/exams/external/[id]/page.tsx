import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { getExternalExamRegistration } from "@/actions/curriculum.action";
import { ExternalExamDetail } from "./external-exam-detail";

export const metadata = {
  title: "External Exam Detail",
  description: "View and manage an external exam registration.",
};

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  const result = await getExternalExamRegistration(id);

  if (!result.success || !result.data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <p className="text-lg font-semibold">Registration not found</p>
        <p className="text-sm text-muted-foreground">
          {result.success ? "No data returned." : result.error}
        </p>
      </div>
    );
  }

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <ExternalExamDetail registration={result.data} />
    </Suspense>
  );
}
