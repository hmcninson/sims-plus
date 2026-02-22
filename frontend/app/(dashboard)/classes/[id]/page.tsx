import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Loader2 } from "lucide-react";

import { getClass, getClassSubjects, getSections } from "@/actions/academic.action";
import { ClassDetail } from "./class-detail";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ClassDetailPage({ params }: PageProps) {
  const { id } = await params;

  // Fetch class data with sections, plus subjects and sections in parallel
  const [classResult, classSubjectsResult, sectionsResult] = await Promise.all([
    getClass(id),
    getClassSubjects(id),
    getSections(id),
  ]);

  if (!classResult.success || !classResult.data) {
    notFound();
  }

  const classData = classResult.data;
  const classSubjects = classSubjectsResult.success ? classSubjectsResult.data || [] : [];
  const sections = sectionsResult.success ? sectionsResult.data || [] : [];

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <ClassDetail
        classData={classData}
        sections={sections}
        classSubjects={classSubjects}
      />
    </Suspense>
  );
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  const result = await getClass(id);
  const className = result.success && result.data ? result.data.name : "Class";
  return {
    title: `${className} - SIMS Plus`,
    description: `View details for ${className}`,
  };
}
