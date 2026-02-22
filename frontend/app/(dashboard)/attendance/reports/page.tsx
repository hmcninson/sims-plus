import { getClasses } from "@/actions/academic.action";
import { AttendanceReports } from "./attendance-reports";

export const metadata = {
  title: "Attendance Reports",
};

export default async function AttendanceReportsPage() {
  const classesResult = await getClasses(true);
  const classes =
    classesResult.success && classesResult.data ? classesResult.data : [];

  return <AttendanceReports classes={classes} />;
}
