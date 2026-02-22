import { getClasses } from "@/actions/academic.action";
import { AttendanceMarking } from "../attendance-marking";

export const metadata = {
  title: "Mark Attendance",
};

export default async function MarkAttendancePage() {
  // Fetch classes with sections
  const classesResult = await getClasses(true);
  const classes = classesResult.success && classesResult.data ? classesResult.data : [];

  return <AttendanceMarking classes={classes} />;
}
