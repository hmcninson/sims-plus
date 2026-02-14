import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Loader2 } from "lucide-react";

import { getExam, getScoreEntryForm } from "@/actions/exams.action";
import { getGradingScales } from "@/actions/academic.action";
import { ScoreEntryForm } from "./score-entry-form";

interface PageProps {
  params: Promise<{ id: string; subjectId: string }>;
}

export default async function ScoreEntryPage({ params }: PageProps) {
  const { id, subjectId } = await params;

  // Fetch exam, score entry form, and grading scales
  const [examResult, formResult, gradingScalesResult] = await Promise.all([
    getExam(id),
    getScoreEntryForm(id, subjectId),
    getGradingScales(),
  ]);

  if (!examResult.success || !examResult.data) {
    notFound();
  }

  if (!formResult.success || !formResult.data) {
    notFound();
  }

  const exam = examResult.data;
  const scoreForm = formResult.data;
  const gradingScales = gradingScalesResult.success ? gradingScalesResult.data || [] : [];

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <ScoreEntryForm
        exam={exam}
        scoreForm={scoreForm}
        gradingScales={gradingScales}
      />
    </Suspense>
  );
}

export async function generateMetadata({ params }: PageProps) {
  const { id, subjectId } = await params;
  const [examResult, formResult] = await Promise.all([
    getExam(id),
    getScoreEntryForm(id, subjectId),
  ]);

  const examName = examResult.success && examResult.data ? examResult.data.name : "Exam";
  const subjectName =
    formResult.success && formResult.data ? formResult.data.subject_name : "Subject";

  return {
    title: `${subjectName} - ${examName} - Score Entry - SIMS Plus`,
    description: `Enter scores for ${subjectName}`,
  };
}
