import { getSubjects } from "@/actions/academic.action";
import { SubjectsManagement } from "./subjects-management";

export const metadata = {
  title: "Subjects",
};

export default async function SubjectsPage() {
  const result = await getSubjects();
  const subjects = result.success && result.data ? result.data : [];

  return <SubjectsManagement initialSubjects={subjects} />;
}
