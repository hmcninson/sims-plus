import { Suspense } from "react";
import { notFound } from "next/navigation";
import { Loader2 } from "lucide-react";

import { getClass, getSubjects, getClassSubjects, getSections } from "@/actions/academic.action";
import { getTeachingStaff } from "@/actions/staff.action";
import { TeacherAssignmentsManagement } from "./teacher-assignments-management";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ClassTeachersPage({ params }: PageProps) {
  const { id } = await params;

  // Fetch all required data in parallel
  const [classResult, sectionsResult, staffResult, classSubjectsResult] = await Promise.all([
    getClass(id),
    getSections(id),
    getTeachingStaff(),
    getClassSubjects(id),
  ]);

  if (!classResult.success || !classResult.data) {
    notFound();
  }

  const classData = classResult.data;
  const sections = sectionsResult.success ? sectionsResult.data || [] : [];
  const allTeachers = staffResult.success ? staffResult.data || [] : [];
  const classSubjects = classSubjectsResult.success ? classSubjectsResult.data || [] : [];

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <TeacherAssignmentsManagement
        classData={classData}
        sections={sections}
        allTeachers={allTeachers}
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
    title: `${className} Teachers - SIMS Plus`,
    description: `Manage teacher assignments for ${className}`,
  };
}
