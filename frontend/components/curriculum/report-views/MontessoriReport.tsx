import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ReportViewProps } from "./types";

/**
 * Montessori Report Card Layout
 *
 * Features:
 * - Narrative-based assessment (no letter grades or percentages)
 * - Progress levels: Introduced, Developing, Practicing, Mastered
 * - Organized by learning areas
 * - Focus on developmental progress, not ranking
 * - Teacher narratives per subject area
 */

type ProgressLevel = "introduced" | "developing" | "practicing" | "mastered";

const PROGRESS_LEVELS: { value: ProgressLevel; label: string; color: string }[] = [
  {
    value: "introduced",
    label: "Introduced",
    color: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
  },
  {
    value: "developing",
    label: "Developing",
    color: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  },
  {
    value: "practicing",
    label: "Practicing",
    color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  },
  {
    value: "mastered",
    label: "Mastered",
    color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  },
];

export function MontessoriReport({ report, config }: ReportViewProps) {
  // Group subjects by broad categories for Montessori presentation
  const groupedResults = groupByArea(report.subject_results.map((r) => ({
    ...r,
    progressLevel: mapGradeToProgress(r.grade),
  })));

  return (
    <div className="space-y-6">
      {/* Student info */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div className="space-y-1">
              <p>
                <span className="text-muted-foreground">Child:</span>{" "}
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
                <span className="text-muted-foreground">Period:</span>{" "}
                {report.term_name}
              </p>
              <p>
                <span className="text-muted-foreground">Approach:</span>{" "}
                <Badge variant="secondary" className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200 text-xs">
                  Montessori
                </Badge>
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Progress level key */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-3">
            {PROGRESS_LEVELS.map((level) => (
              <div key={level.value} className="flex items-center gap-2">
                <div className={`h-3 w-3 rounded-full ${level.color.split(" ")[0]}`} />
                <span className="text-xs text-muted-foreground">{level.label}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Learning areas */}
      {Object.entries(groupedResults).map(([area, results]) => (
        <Card key={area}>
          <CardHeader>
            <CardTitle className="text-base">{area}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {results.map((result) => (
              <div
                key={result.subject_id}
                className="rounded-lg border p-4 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <p className="font-medium text-sm">{result.subject_name}</p>
                  <Badge
                    variant="secondary"
                    className={`text-xs ${getProgressColor(result.progressLevel)}`}
                  >
                    {getProgressLabel(result.progressLevel)}
                  </Badge>
                </div>

                {/* Visual progress bar */}
                <div className="flex gap-1">
                  {PROGRESS_LEVELS.map((level, idx) => (
                    <div
                      key={level.value}
                      className={`
                        h-2 flex-1 rounded-full transition-colors
                        ${idx <= getProgressIndex(result.progressLevel)
                          ? getProgressBarColor(result.progressLevel)
                          : "bg-muted"
                        }
                      `}
                    />
                  ))}
                </div>

                {/* Narrative */}
                {(result.teacher_remark || result.grade_remark) && (
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {result.teacher_remark || result.grade_remark}
                  </p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      ))}

      {/* Attendance */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Attendance</CardTitle>
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

      {/* Guide's narrative */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Guide&apos;s Narrative</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-xs text-muted-foreground mb-1">Classroom Guide</p>
            <p className="text-sm rounded-lg border p-4 bg-muted/30 min-h-[60px] leading-relaxed">
              {report.class_teacher_remark || "No narrative provided"}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-1">Head of School</p>
            <p className="text-sm rounded-lg border p-4 bg-muted/30 min-h-[60px] leading-relaxed">
              {report.headmaster_remark || "No narrative provided"}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

interface SubjectWithProgress {
  subject_id: string;
  subject_name: string;
  subject_code?: string;
  grade?: string;
  grade_remark?: string;
  teacher_remark?: string;
  progressLevel: ProgressLevel;
}

function groupByArea(
  results: SubjectWithProgress[],
): Record<string, SubjectWithProgress[]> {
  // Group by broad learning areas based on subject name patterns
  const groups: Record<string, SubjectWithProgress[]> = {};
  const areaMap: Record<string, string> = {
    math: "Mathematics",
    language: "Language Arts",
    science: "Science & Nature",
    social: "Cultural Studies",
    art: "Creative Arts",
    music: "Creative Arts",
    physical: "Physical Development",
    practical: "Practical Life",
    sensorial: "Sensorial",
  };

  for (const result of results) {
    const name = result.subject_name.toLowerCase();
    let area = "General Studies";

    for (const [key, value] of Object.entries(areaMap)) {
      if (name.includes(key)) {
        area = value;
        break;
      }
    }

    if (!groups[area]) groups[area] = [];
    groups[area].push(result);
  }

  return groups;
}

function mapGradeToProgress(grade?: string): ProgressLevel {
  if (!grade) return "introduced";
  const g = grade.toLowerCase();
  if (g === "mastered" || g === "m" || g === "4") return "mastered";
  if (g === "practicing" || g === "p" || g === "3") return "practicing";
  if (g === "developing" || g === "d" || g === "2") return "developing";
  return "introduced";
}

function getProgressIndex(level: ProgressLevel): number {
  const map: Record<ProgressLevel, number> = {
    introduced: 0,
    developing: 1,
    practicing: 2,
    mastered: 3,
  };
  return map[level];
}

function getProgressColor(level: ProgressLevel): string {
  const level_ = PROGRESS_LEVELS.find((l) => l.value === level);
  return level_?.color || "";
}

function getProgressLabel(level: ProgressLevel): string {
  const level_ = PROGRESS_LEVELS.find((l) => l.value === level);
  return level_?.label || "Unknown";
}

function getProgressBarColor(level: ProgressLevel): string {
  const map: Record<ProgressLevel, string> = {
    introduced: "bg-gray-400 dark:bg-gray-500",
    developing: "bg-amber-400 dark:bg-amber-500",
    practicing: "bg-blue-400 dark:bg-blue-500",
    mastered: "bg-green-400 dark:bg-green-500",
  };
  return map[level];
}
