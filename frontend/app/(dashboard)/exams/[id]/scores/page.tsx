import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Loader2 } from "lucide-react";

import { getExam, getExamSubjects } from "@/actions/exams.action";
import { getClasses } from "@/actions/academic.action";
import { ScoreEntrySelector } from "./score-entry-selector";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ExamScoresPage({ params }: PageProps) {
  const { id } = await params;

  // Fetch exam and subjects in parallel
  const [examResult, examSubjectsResult, classesResult] = await Promise.all([
    getExam(id),
    getExamSubjects(id),
    getClasses(true),
  ]);

  if (!examResult.success || !examResult.data) {
    notFound();
  }

  const exam = examResult.data;
  const examSubjects = examSubjectsResult.success ? examSubjectsResult.data || [] : [];
  const classes = classesResult.success ? classesResult.data || [] : [];

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <ScoreEntrySelector
        exam={exam}
        examSubjects={examSubjects}
        classes={classes}
      />
    </Suspense>
  );
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  const result = await getExam(id);
  const examName = result.success && result.data ? result.data.name : "Exam";
  return {
    title: `${examName} - Score Entry`,
    description: `Enter scores for ${examName}`,
  };
}
