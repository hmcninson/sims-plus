import { getClasses } from "@/actions/academic.action";
import { ClassesManagement } from "./classes-management";

export const metadata = {
  title: "Classes",
};

export default async function ClassesPage() {
  // Fetch initial data server-side
  const classesResult = await getClasses(true);

  return (
    <ClassesManagement
      initialClasses={classesResult.success ? classesResult.data! : []}
    />
  );
}
