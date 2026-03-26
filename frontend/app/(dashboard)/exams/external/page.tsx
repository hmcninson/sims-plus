import { Suspense } from "react";
import { Loader2 } from "lucide-react";

import { getExternalExamRegistrations } from "@/actions/curriculum.action";
import { getStudents } from "@/actions/students.action";
import { ExternalExamsPage } from "./external-exams-page";

export const metadata = {
  title: "External Exams",
  description: "Manage external exam registrations and results.",
};

export default async function Page() {
  const [registrationsResult, studentsResult] = await Promise.all([
    getExternalExamRegistrations(),
    getStudents({ page_size: 500 }),
  ]);

  const registrations =
    registrationsResult.success && registrationsResult.data
      ? registrationsResult.data.items
      : [];

  const students =
    studentsResult.success && studentsResult.data
      ? studentsResult.data.items.map((s) => ({
          id: s.id,
          name: `${s.first_name} ${s.last_name}`,
          student_number: s.student_id,
        }))
      : [];

  // Build a lookup map for student names used in the table
  const studentNames: Record<string, string> = {};
  for (const s of students) {
    studentNames[s.id] = s.name;
  }

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <ExternalExamsPage
        initialRegistrations={registrations}
        students={students}
        studentNames={studentNames}
      />
    </Suspense>
  );
}
