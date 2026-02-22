import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Loader2 } from "lucide-react";

import { getExam, getExamSubjects } from "@/actions/exams.action";
import { ExamResults } from "./exam-results";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ExamResultsPage({ params }: PageProps) {
  const { id } = await params;

  const [examResult, subjectsResult] = await Promise.all([
    getExam(id),
    getExamSubjects(id),
  ]);

  if (!examResult.success || !examResult.data) {
    notFound();
  }

  const exam = examResult.data;
  const subjects = subjectsResult.success ? subjectsResult.data || [] : [];

  // Get unique classes from subjects (sorted by sequence)
  const classesMap = new Map<string, { id: string; name: string; sequence: number }>();
  for (const subject of subjects) {
    if (!classesMap.has(subject.class_id)) {
      classesMap.set(subject.class_id, {
        id: subject.class_id,
        name: subject.class_name || "Unknown Class",
        sequence: subject.class_sequence,
      });
    }
  }
  const classes = Array.from(classesMap.values()).sort((a, b) => a.sequence - b.sequence);

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <ExamResults exam={exam} classes={classes} />
    </Suspense>
  );
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  const result = await getExam(id);
  const examName = result.success && result.data ? result.data.name : "Exam";
  return {
    title: `${examName} Results`,
    description: `View results for ${examName}`,
  };
}
