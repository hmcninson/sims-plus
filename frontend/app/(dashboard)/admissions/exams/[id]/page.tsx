import { Suspense } from "react";
import { Metadata } from "next";
import { ExamDetail } from "./exam-detail";

export const metadata: Metadata = {
  title: "Exam Detail",
  description: "View entrance exam details and manage results",
};

interface ExamDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function ExamDetailPage({
  params,
}: ExamDetailPageProps) {
  const { id } = await params;

  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <ExamDetail examId={id} />
    </Suspense>
  );
}
