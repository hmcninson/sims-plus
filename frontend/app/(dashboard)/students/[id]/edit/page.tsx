import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";

import { getStudent } from "@/actions/students.action";
import { getClasses } from "@/actions/academic.action";
import { EditStudentForm } from "./edit-student-form";

interface EditStudentPageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ step?: string }>;
}

export default async function EditStudentPage({ params, searchParams }: EditStudentPageProps) {
  const { id } = await params;
  const { step } = await searchParams;

  // Map step names to step numbers
  const stepMap: Record<string, number> = {
    personal: 1,
    contact: 2,
    academic: 3,
    health: 4,
    review: 5,
  };
  const initialStep = step ? (stepMap[step.toLowerCase()] || parseInt(step) || 1) : 1;

  // Fetch student and classes server-side
  const [studentResult, classesResult] = await Promise.all([
    getStudent(id),
    getClasses(true),
  ]);

  if (!studentResult.success || !studentResult.data) {
    notFound();
  }

  const student = studentResult.data;
  const classes = classesResult.success && classesResult.data ? classesResult.data : [];

  const studentName = `${student.first_name} ${student.last_name}`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/students/${id}`}>
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Edit Student</h1>
          <p className="text-muted-foreground">
            Update information for {studentName}
          </p>
        </div>
      </div>

      {/* Form */}
      <EditStudentForm student={student} classes={classes} initialStep={initialStep} />
    </div>
  );
}
