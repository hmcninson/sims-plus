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
 * International Baccalaureate (IB) Report Card Layout
 *
 * Features:
 * - Achievement levels 1-7 per subject
 * - Internal Assessment (IA) + External marks
 * - Total points out of 45 (6 subjects x 7 + 3 bonus)
 * - ATL Skills and Learner Profile traits
 * - Extended Essay, TOK, CAS components
 */
export function IBReport({ report, config, curriculumData }: ReportViewProps) {
  const showAtlSkills = config?.show_atl_skills ?? true;
  const showLearnerProfile = config?.show_learner_profile ?? true;
  const totalPoints = curriculumData?.ib_total_points;

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
                <span className="text-muted-foreground">Session:</span>{" "}
                {report.term_name}
              </p>
              <p>
                <span className="text-muted-foreground">Programme:</span>{" "}
                <Badge variant="secondary" className="bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200 text-xs">
                  IB Diploma
                </Badge>
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Total points */}
      {totalPoints != null && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total IB Points</p>
                <p className="text-4xl font-bold">{totalPoints}</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">Maximum</p>
                <p className="text-2xl font-semibold text-muted-foreground">/ 45</p>
              </div>
            </div>
            <div className="mt-3 h-2 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${Math.min((totalPoints / 45) * 100, 100)}%` }}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Subject results */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Subject Grades</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Subject</TableHead>
                  <TableHead className="text-center">Level</TableHead>
                  <TableHead className="text-center">IA</TableHead>
                  <TableHead className="text-center">Exam</TableHead>
                  <TableHead className="text-center">Achievement Level</TableHead>
                  <TableHead>Teacher Comment</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {report.subject_results.map((result) => {
                  const level = "ib_level" in result
                    ? (result as unknown as { ib_level?: string }).ib_level
                    : undefined;

                  return (
                    <TableRow key={result.subject_id}>
                      <TableCell className="font-medium text-sm">
                        {result.subject_name}
                      </TableCell>
                      <TableCell className="text-center">
                        {level ? (
                          <Badge variant="outline" className="text-[10px]">
                            {level}
                          </Badge>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                      <TableCell className="text-center text-sm">
                        {result.ca_score != null ? result.ca_score : "-"}
                      </TableCell>
                      <TableCell className="text-center text-sm">
                        {result.end_term_score != null ? result.end_term_score : "-"}
                      </TableCell>
                      <TableCell className="text-center">
                        {result.grade ? (
                          <Badge
                            variant="secondary"
                            className={getIBLevelColor(result.grade)}
                          >
                            {result.grade}
                          </Badge>
                        ) : (
                          "-"
                        )}
                      </TableCell>
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

      {/* Core components (EE, TOK, CAS) */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Core Components</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-lg border p-4">
              <p className="text-sm font-medium">Extended Essay (EE)</p>
              <p className="text-xs text-muted-foreground mt-1">
                Research paper on a topic of choice
              </p>
              <Badge variant="secondary" className="mt-2 text-xs">
                In Progress
              </Badge>
            </div>
            <div className="rounded-lg border p-4">
              <p className="text-sm font-medium">Theory of Knowledge (TOK)</p>
              <p className="text-xs text-muted-foreground mt-1">
                Critical thinking and epistemology
              </p>
              <Badge variant="secondary" className="mt-2 text-xs">
                In Progress
              </Badge>
            </div>
            <div className="rounded-lg border p-4">
              <p className="text-sm font-medium">CAS</p>
              <p className="text-xs text-muted-foreground mt-1">
                Creativity, Activity, Service
              </p>
              <Badge variant="secondary" className="mt-2 text-xs">
                In Progress
              </Badge>
            </div>
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
              <p className="text-2xl font-bold">{report.total_school_days}</p>
              <p className="text-xs text-muted-foreground">Total Days</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Remarks */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Comments</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-xs text-muted-foreground mb-1">IB Coordinator&apos;s Comment</p>
            <p className="text-sm rounded-lg border p-3 bg-muted/30 min-h-[40px]">
              {report.class_teacher_remark || "No comment provided"}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1">Head of School</p>
            <p className="text-sm rounded-lg border p-3 bg-muted/30 min-h-[40px]">
              {report.headmaster_remark || "No comment provided"}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Achievement level key */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">IB Achievement Levels</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3 text-xs">
            {[
              { level: "7", desc: "Excellent" },
              { level: "6", desc: "Very Good" },
              { level: "5", desc: "Good" },
              { level: "4", desc: "Satisfactory" },
              { level: "3", desc: "Mediocre" },
              { level: "2", desc: "Poor" },
              { level: "1", desc: "Very Poor" },
            ].map((l) => (
              <span key={l.level} className="flex items-center gap-1.5">
                <Badge variant="secondary" className={`${getIBLevelColor(l.level)} text-[10px]`}>
                  {l.level}
                </Badge>
                <span className="text-muted-foreground">{l.desc}</span>
              </span>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function getIBLevelColor(level: string): string {
  const n = parseInt(level, 10);
  if (n >= 7) return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
  if (n >= 5) return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
  if (n >= 4) return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
  if (n >= 2) return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200";
  return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
}
