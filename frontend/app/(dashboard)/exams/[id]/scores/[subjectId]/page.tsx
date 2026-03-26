import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Loader2 } from "lucide-react";

import { getExam, getScoreEntryForm } from "@/actions/exams.action";
import { getGradingScales } from "@/actions/academic.action";
import { ScoreEntryForm } from "./score-entry-form";
import { MontessoriAssessmentForm } from "@/components/curriculum/MontessoriAssessmentForm";

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

  // Detect Montessori curriculum: show narrative form instead of numeric score grid
  if (scoreForm.curriculum_type === "montessori") {
    return (
      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <MontessoriAssessmentForm
          exam={exam}
          classId={scoreForm.class_id}
          sectionId={scoreForm.section_id}
          students={scoreForm.students || []}
          backHref={`/exams/${exam.id}/scores`}
        />
      </Suspense>
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

  const isMontessori =
    formResult.success && formResult.data?.curriculum_type === "montessori";

  return {
    title: isMontessori
      ? `Montessori Assessment - ${examName} - SIMS Plus`
      : `${subjectName} - ${examName} - Score Entry - SIMS Plus`,
    description: isMontessori
      ? `Montessori narrative assessment for ${examName}`
      : `Enter scores for ${subjectName}`,
  };
}
