import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableFooter,
} from "@/components/ui/table";
import type { ReportViewProps } from "./types";

/**
 * American Curriculum Report Card Layout
 *
 * Features:
 * - Letter grades (A-F) with GPA points
 * - Credit hours per subject
 * - GPA calculation (semester + cumulative)
 * - Honor Roll designation
 * - No ranking by default
 */
export function AmericanReport({ report, config, curriculumData }: ReportViewProps) {
  const showGpa = config?.show_gpa ?? true;
  const showCredits = config?.show_credits ?? true;
  const showHonorRoll = config?.show_honor_roll ?? true;

  const gpa = curriculumData?.gpa;
  const cumulativeGpa = curriculumData?.cumulative_gpa;
  const totalCredits = curriculumData?.total_credits_earned;
  const cumulativeCredits = curriculumData?.cumulative_credits;
  const isHonorRoll = curriculumData?.honor_roll;

  return (
    <div className="space-y-6">
      {/* Student info */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div className="space-y-1">
              <p>
                <span className="text-muted-foreground">Student:</span>{" "}
                <span className="font-medium">{report.student_name}</span>
              </p>
              <p>
                <span className="text-muted-foreground">Student ID:</span>{" "}
                {report.student_id_number}
              </p>
              <p>
                <span className="text-muted-foreground">Grade Level:</span>{" "}
                {report.class_name}
              </p>
            </div>
            <div className="space-y-1">
              <p>
                <span className="text-muted-foreground">School Year:</span>{" "}
                {report.academic_year_name}
              </p>
              <p>
                <span className="text-muted-foreground">Semester:</span>{" "}
                {report.term_name}
              </p>
              {showHonorRoll && isHonorRoll && (
                <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                  Honor Roll
                </Badge>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* GPA Summary */}
      {showGpa && (gpa != null || cumulativeGpa != null) && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {gpa != null && (
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-3xl font-bold">{gpa.toFixed(2)}</p>
                <p className="text-xs text-muted-foreground mt-1">Semester GPA</p>
              </CardContent>
            </Card>
          )}
          {cumulativeGpa != null && (
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-3xl font-bold">{cumulativeGpa.toFixed(2)}</p>
                <p className="text-xs text-muted-foreground mt-1">Cumulative GPA</p>
              </CardContent>
            </Card>
          )}
          {showCredits && totalCredits != null && (
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-3xl font-bold">{totalCredits}</p>
                <p className="text-xs text-muted-foreground mt-1">Credits Earned</p>
              </CardContent>
            </Card>
          )}
          {showCredits && cumulativeCredits != null && (
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-3xl font-bold">{cumulativeCredits}</p>
                <p className="text-xs text-muted-foreground mt-1">Cumulative Credits</p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Subject results */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Course Grades</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Course</TableHead>
                  {showCredits && (
                    <TableHead className="text-center">Credits</TableHead>
                  )}
                  <TableHead className="text-center">Percentage</TableHead>
                  <TableHead className="text-center">Letter Grade</TableHead>
                  <TableHead className="text-center">GPA Points</TableHead>
                  <TableHead>Instructor Comment</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {report.subject_results.map((result) => (
                  <TableRow key={result.subject_id}>
                    <TableCell className="font-medium text-sm">
                      {result.subject_name}
                    </TableCell>
                    {showCredits && (
                      <TableCell className="text-center text-sm">
                        {"credits" in result
                          ? String((result as unknown as { credits?: number }).credits ?? "-")
                          : "-"}
                      </TableCell>
                    )}
                    <TableCell className="text-center text-sm">
                      {result.total_score != null ? `${result.total_score}%` : "-"}
                    </TableCell>
                    <TableCell className="text-center">
                      {result.grade ? (
                        <Badge
                          variant="secondary"
                          className={getLetterGradeColor(result.grade)}
                        >
                          {result.grade}
                        </Badge>
                      ) : (
                        "-"
                      )}
                    </TableCell>
                    <TableCell className="text-center text-sm">
                      {result.grade_point?.toFixed(1) ?? "-"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-[200px] truncate">
                      {result.teacher_remark || "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
              {showGpa && gpa != null && (
                <TableFooter>
                  <TableRow>
                    <TableCell className="font-semibold">Semester GPA</TableCell>
                    {showCredits && <TableCell />}
                    <TableCell />
                    <TableCell />
                    <TableCell className="text-center font-bold">
                      {gpa.toFixed(2)}
                    </TableCell>
                    <TableCell />
                  </TableRow>
                </TableFooter>
              )}
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Attendance */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Attendance Record</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold">{report.days_present}</p>
              <p className="text-xs text-muted-foreground">Days Present</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{report.days_absent}</p>
              <p className="text-xs text-muted-foreground">Days Absent</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{report.total_school_days}</p>
              <p className="text-xs text-muted-foreground">Total Days</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Comments */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Comments</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-xs text-muted-foreground mb-1">Homeroom Teacher</p>
            <p className="text-sm rounded-lg border p-3 bg-muted/30 min-h-[40px]">
              {report.class_teacher_remark || "No comment provided"}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1">Principal</p>
            <p className="text-sm rounded-lg border p-3 bg-muted/30 min-h-[40px]">
              {report.headmaster_remark || "No comment provided"}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Grade scale */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Grading Scale</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4 text-xs">
            {[
              { grade: "A", range: "90-100", gpa: "4.0" },
              { grade: "B", range: "80-89", gpa: "3.0" },
              { grade: "C", range: "70-79", gpa: "2.0" },
              { grade: "D", range: "60-69", gpa: "1.0" },
              { grade: "F", range: "0-59", gpa: "0.0" },
            ].map((g) => (
              <span key={g.grade} className="flex items-center gap-1.5">
                <Badge variant="secondary" className={`${getLetterGradeColor(g.grade)} text-[10px]`}>
                  {g.grade}
                </Badge>
                <span className="text-muted-foreground">
                  {g.range} ({g.gpa})
                </span>
              </span>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function getLetterGradeColor(grade: string): string {
  const g = grade.toUpperCase().charAt(0);
  if (g === "A") return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
  if (g === "B") return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
  if (g === "C") return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
  if (g === "D") return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200";
  return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
}
