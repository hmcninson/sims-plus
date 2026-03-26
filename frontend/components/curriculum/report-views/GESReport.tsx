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
 * GES (Ghana Education Service) Report Card Layout
 *
 * Standard Ghana format:
 * - Class Score (50%) + Exam Score (50%) = Total (100%)
 * - Letter grade + remark
 * - Class/section position
 * - Conduct grade and interest
 * - Class teacher and headmaster remarks
 */
export function GESReport({ report, config }: ReportViewProps) {
  const showPosition = config?.show_position ?? true;
  const showClassAverage = config?.show_class_average ?? true;
  const showSubjectPosition = config?.show_subject_position ?? false;

  return (
    <div className="space-y-6">
      {/* Student info header */}
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
              {showPosition && report.class_position && (
                <p>
                  <span className="text-muted-foreground">Position:</span>{" "}
                  <span className="font-semibold">
                    {report.class_position}
                    {report.class_size && ` / ${report.class_size}`}
                  </span>
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Subject results table */}
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
                  <TableHead className="text-center">Class Score (50%)</TableHead>
                  <TableHead className="text-center">Exam Score (50%)</TableHead>
                  <TableHead className="text-center">Total (100%)</TableHead>
                  <TableHead className="text-center">Grade</TableHead>
                  <TableHead>Remark</TableHead>
                  {showSubjectPosition && (
                    <TableHead className="text-center">Position</TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {report.subject_results.map((result) => (
                  <TableRow
                    key={result.subject_id}
                    className={result.is_absent ? "opacity-60" : undefined}
                  >
                    <TableCell className="font-medium text-sm">
                      {result.subject_name}
                      {result.is_absent && (
                        <Badge variant="outline" className="ml-2 text-[10px]">
                          Absent
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-center text-sm">
                      {result.class_score ?? "-"}
                    </TableCell>
                    <TableCell className="text-center text-sm">
                      {result.exams_score ?? "-"}
                    </TableCell>
                    <TableCell className="text-center font-semibold text-sm">
                      {result.total_score ?? "-"}
                    </TableCell>
                    <TableCell className="text-center">
                      {result.grade ? (
                        <Badge variant="secondary" className="text-xs">
                          {result.grade}
                        </Badge>
                      ) : (
                        "-"
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {result.grade_remark || "-"}
                    </TableCell>
                    {showSubjectPosition && (
                      <TableCell className="text-center text-sm">
                        {result.subject_position ?? "-"}
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
              <TableFooter>
                <TableRow>
                  <TableCell className="font-semibold">Overall</TableCell>
                  <TableCell />
                  <TableCell />
                  <TableCell className="text-center font-bold">
                    {report.average_score.toFixed(1)}
                  </TableCell>
                  <TableCell />
                  <TableCell />
                  {showSubjectPosition && <TableCell />}
                </TableRow>
              </TableFooter>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Attendance and conduct */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                <p className="text-2xl font-bold">{report.total_school_days}</p>
                <p className="text-xs text-muted-foreground">Total Days</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Conduct & Interest</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <p className="text-xs text-muted-foreground">Conduct</p>
              <p className="text-sm font-medium">{report.conduct_grade || "Not graded"}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Interest</p>
              <p className="text-sm font-medium">{report.interest || "Not assessed"}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Remarks */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Remarks</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-xs text-muted-foreground mb-1">Class Teacher&apos;s Remark</p>
            <p className="text-sm rounded-lg border p-3 bg-muted/30 min-h-[40px]">
              {report.class_teacher_remark || "No remark provided"}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1">Headmaster&apos;s Remark</p>
            <p className="text-sm rounded-lg border p-3 bg-muted/30 min-h-[40px]">
              {report.headmaster_remark || "No remark provided"}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
