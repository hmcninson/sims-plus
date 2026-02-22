import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Loader2 } from "lucide-react";

import { getExam, getExamTimetable, checkTimetableConflicts } from "@/actions/exams.action";
import { TimetableManager } from "./timetable-manager";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ExamTimetablePage({ params }: PageProps) {
  const { id } = await params;

  const [examResult, timetableResult, conflictsResult] = await Promise.all([
    getExam(id),
    getExamTimetable(id),
    checkTimetableConflicts(id),
  ]);

  if (!examResult.success || !examResult.data) {
    notFound();
  }

  const exam = examResult.data;
  const timetable = timetableResult.success ? timetableResult.data ?? null : null;
  const conflicts = conflictsResult.success ? conflictsResult.data ?? null : null;

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <TimetableManager exam={exam} initialTimetable={timetable} initialConflicts={conflicts} />
    </Suspense>
  );
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  const result = await getExam(id);
  const examName = result.success && result.data ? result.data.name : "Exam";
  return {
    title: `${examName} Timetable`,
    description: `Manage timetable for ${examName}`,
  };
}
