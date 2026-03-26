import { Suspense } from "react";
import { Metadata } from "next";
import { ExamsList } from "./exams-list";

export const metadata: Metadata = {
  title: "Entrance Exams",
  description: "Manage entrance exam sessions",
};

export default function ExamsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <ExamsList />
    </Suspense>
  );
}
