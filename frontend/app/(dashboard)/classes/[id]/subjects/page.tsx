import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Loader2 } from "lucide-react";

import { getClass, getSubjects, getClassSubjects } from "@/actions/academic.action";
import { ClassSubjectsManagement } from "./class-subjects-management";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ClassSubjectsPage({ params }: PageProps) {
  const { id } = await params;

  // First get the class to know its level
  const classResult = await getClass(id);

  if (!classResult.success || !classResult.data) {
    notFound();
  }

  const classData = classResult.data;

  // Map specific grade levels to category levels for API filtering
  const getLevelCategory = (level?: string): string | undefined => {
    if (!level) return undefined;
    const PRESCHOOL_LEVELS = ["creche", "preschool", "nursery_1", "nursery_2", "kg_1", "kg_2"];
    const PRIMARY_LEVELS = ["primary", "primary_1", "primary_2", "primary_3", "primary_4", "primary_5", "primary_6"];
    const JHS_LEVELS = ["jhs", "jhs_1", "jhs_2", "jhs_3"];
    const SHS_LEVELS = ["shs", "shs_1", "shs_2", "shs_3"];

    if (PRESCHOOL_LEVELS.includes(level)) return "preschool";
    if (PRIMARY_LEVELS.includes(level)) return "primary";
    if (JHS_LEVELS.includes(level)) return "jhs";
    if (SHS_LEVELS.includes(level)) return "shs";
    return level;
  };

  // Now fetch subjects filtered by class level, and class subjects in parallel
  const [subjectsResult, classSubjectsResult] = await Promise.all([
    getSubjects(getLevelCategory(classData.level)), // Pass category level to filter subjects
    getClassSubjects(id),
  ]);

  const allSubjects = subjectsResult.success ? subjectsResult.data || [] : [];
  const classSubjects = classSubjectsResult.success ? classSubjectsResult.data || [] : [];

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <ClassSubjectsManagement
        classData={classData}
        allSubjects={allSubjects}
        initialClassSubjects={classSubjects}
      />
    </Suspense>
  );
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  const result = await getClass(id);
  const className = result.success && result.data ? result.data.name : "Class";
  return {
    title: `${className} Subjects - SIMS Plus`,
    description: `Manage subjects for ${className}`,
  };
}
