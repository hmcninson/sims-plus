import { getStudents, getStudentStats } from "@/actions/students.action";
import { getClasses } from "@/actions/academic.action";
import { StudentsManagement } from "./students-management";

export const metadata = {
  title: "Students",
};

interface StudentsPageProps {
  searchParams: Promise<{ class_id?: string }>;
}

export default async function StudentsPage({ searchParams }: StudentsPageProps) {
  const params = await searchParams;
  const classId = params.class_id;

  // Fetch initial data server-side, filtering by class_id if provided
  const [studentsResult, statsResult, classesResult] = await Promise.all([
    getStudents({
      page: 1,
      page_size: 20,
      class_id: classId || undefined,
    }),
    getStudentStats(),
    getClasses(true), // Include sections
  ]);

  // Default data for empty/error states
  const defaultStudents = {
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    total_pages: 0,
    has_next: false,
    has_previous: false,
  };

  const defaultStats = {
    total: 0,
    active: 0,
    inactive: 0,
    graduated: 0,
    transferred: 0,
    withdrawn: 0,
    suspended: 0,
    male: 0,
    female: 0,
    boarders: 0,
    day_students: 0,
  };

  return (
    <StudentsManagement
      initialData={studentsResult.success ? studentsResult.data! : defaultStudents}
      stats={statsResult.success ? statsResult.data! : defaultStats}
      classes={classesResult.success ? classesResult.data! : []}
      initialClassFilter={classId}
    />
  );
}
