import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Loader2 } from "lucide-react";

import { getExam, getExamSubjects } from "@/actions/exams.action";
import { AnalyticsDashboard } from "./analytics-dashboard";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ExamAnalyticsPage({ params }: PageProps) {
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

  // Get unique classes from subjects (sorted by sequence) with their sections
  const classesMap = new Map<string, { id: string; name: string; sequence: number; sections: { id: string; name: string }[] }>();
  for (const subject of subjects) {
    if (!classesMap.has(subject.class_id)) {
      classesMap.set(subject.class_id, {
        id: subject.class_id,
        name: subject.class_name || "Unknown Class",
        sequence: subject.class_sequence,
        sections: [],
      });
    }
    // Add section if it exists and not already added
    if (subject.section_id && subject.section_name) {
      const classEntry = classesMap.get(subject.class_id)!;
      if (!classEntry.sections.find(s => s.id === subject.section_id)) {
        classEntry.sections.push({
          id: subject.section_id,
          name: subject.section_name,
        });
      }
    }
  }
  const classes = Array.from(classesMap.values()).sort((a, b) => a.sequence - b.sequence);

  // Get unique subjects for rankings dropdown
  const subjectsMap = new Map<string, { id: string; name: string; code?: string }>();
  for (const subject of subjects) {
    if (!subjectsMap.has(subject.subject_id)) {
      subjectsMap.set(subject.subject_id, {
        id: subject.subject_id,
        name: subject.subject_name || "Unknown Subject",
        code: subject.subject_code,
      });
    }
  }
  const uniqueSubjects = Array.from(subjectsMap.values());

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <AnalyticsDashboard exam={exam} classes={classes} subjects={uniqueSubjects} />
    </Suspense>
  );
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  const result = await getExam(id);
  const examName = result.success && result.data ? result.data.name : "Exam";
  return {
    title: `${examName} Analytics`,
    description: `View analytics for ${examName}`,
  };
}
