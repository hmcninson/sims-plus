import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ReportViewProps } from "./types";

/**
 * Cambridge International Report Card Layout
 *
 * Features:
 * - Component-based grades (subject split into components)
 * - Effort grade per subject (A-E scale)
 * - No ranking/position by default
 * - Grade descriptors (A*-U for IGCSE, a-e for AS/A-Level)
 */
export function CambridgeReport({ report, config, curriculumData }: ReportViewProps) {
  const showEffortGrade = config?.show_effort_grade ?? true;
  const showPredictedGrades = config?.show_predicted_grades ?? false;

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
                <span className="text-muted-foreground">Class:</span>{" "}
                {report.class_name}
                {report.section_name && ` (${report.section_name})`}
              </p>
            </div>
            <div className="space-y-1">
              <p>
                <span className="text-muted-foreground">Academic Year:</span>{" "}
                {report.academic_year_name}
              </p>
              <p>
                <span className="text-muted-foreground">Term:</span>{" "}
                {report.term_name}
              </p>
              <p>
                <span className="text-muted-foreground">Programme:</span>{" "}
                <Badge variant="secondary" className="text-xs">
                  Cambridge
                </Badge>
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Subject results */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Subject Results</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Subject</TableHead>
                  <TableHead className="text-center">Coursework</TableHead>
                  <TableHead className="text-center">Exam</TableHead>
                  <TableHead className="text-center">Overall Grade</TableHead>
                  {showEffortGrade && (
                    <TableHead className="text-center">Effort</TableHead>
                  )}
                  {showPredictedGrades && (
                    <TableHead className="text-center">Predicted</TableHead>
                  )}
                  <TableHead>Teacher Comment</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {report.subject_results.map((result) => {
                  // Effort grade may be provided as an extra field on the result
                  const effortGrade = "effort_grade" in result
                    ? (result as unknown as { effort_grade?: string }).effort_grade
                    : undefined;

                  return (
                    <TableRow key={result.subject_id}>
                      <TableCell className="font-medium text-sm">
                        {result.subject_name}
                        {result.subject_code && (
                          <span className="text-xs text-muted-foreground ml-1">
                            ({result.subject_code})
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-center text-sm">
                        {result.ca_score != null
                          ? `${result.ca_score}${result.ca_max ? `/${result.ca_max}` : ""}`
                          : "-"}
                      </TableCell>
                      <TableCell className="text-center text-sm">
                        {result.end_term_score != null
                          ? `${result.end_term_score}${result.end_term_max ? `/${result.end_term_max}` : ""}`
                          : "-"}
                      </TableCell>
                      <TableCell className="text-center">
                        {result.grade ? (
                          <Badge
                            variant="secondary"
                            className={getGradeColor(result.grade)}
                          >
                            {result.grade}
                          </Badge>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                      {showEffortGrade && (
                        <TableCell className="text-center">
                          {effortGrade ? (
                            <Badge variant="outline" className="text-xs">
                              {effortGrade}
                            </Badge>
                          ) : (
                            "-"
                          )}
                        </TableCell>
                      )}
                      {showPredictedGrades && (
                        <TableCell className="text-center text-sm text-muted-foreground">
                          -
                        </TableCell>
                      )}
                      <TableCell className="text-sm text-muted-foreground max-w-[200px] truncate">
                        {result.teacher_remark || "-"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Attendance */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Attendance</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold">{report.days_present}</p>
              <p className="text-xs text-muted-foreground">Present</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{report.days_absent}</p>
              <p className="text-xs text-muted-foreground">Absent</p>
            </div>
            <div>
              <p className="text-2xl font-bold">
                {report.attendance_percentage != null
                  ? `${report.attendance_percentage}%`
                  : `${Math.round((report.days_present / Math.max(report.total_school_days, 1)) * 100)}%`}
              </p>
              <p className="text-xs text-muted-foreground">Attendance Rate</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Remarks */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Remarks</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-xs text-muted-foreground mb-1">Form Tutor&apos;s Comment</p>
            <p className="text-sm rounded-lg border p-3 bg-muted/30 min-h-[40px]">
              {report.class_teacher_remark || "No comment provided"}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1">Head of School&apos;s Comment</p>
            <p className="text-sm rounded-lg border p-3 bg-muted/30 min-h-[40px]">
              {report.headmaster_remark || "No comment provided"}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Grade key */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Grade Key</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3 text-xs">
            {["A*", "A", "B", "C", "D", "E", "F", "G", "U"].map((g) => (
              <span key={g} className="flex items-center gap-1.5">
                <Badge variant="secondary" className={`${getGradeColor(g)} text-[10px]`}>
                  {g}
                </Badge>
                <span className="text-muted-foreground">{getGradeDescriptor(g)}</span>
              </span>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function getGradeColor(grade: string): string {
  const g = grade.toUpperCase().replace("*", "");
  if (g === "A") return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
  if (g === "B") return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
  if (g === "C") return "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200";
  if (g === "D") return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
  if (g === "E") return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200";
  return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
}

function getGradeDescriptor(grade: string): string {
  const map: Record<string, string> = {
    "A*": "Outstanding",
    A: "Excellent",
    B: "Very Good",
    C: "Good",
    D: "Satisfactory",
    E: "Sufficient",
    F: "Weak",
    G: "Very Weak",
    U: "Ungraded",
  };
  return map[grade] || "";
}
