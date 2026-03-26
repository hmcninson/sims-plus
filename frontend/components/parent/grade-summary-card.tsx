"use client";

import { Award } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { TermGrades, CurriculumType } from "@/types/parent.type";

interface GradeSummaryCardProps {
  grades: TermGrades;
}

function MiniStat({
  label,
  value,
  variant,
}: {
  label: string;
  value: string;
  variant?: "default" | "success";
}) {
  return (
    <Card className={variant === "success" ? "bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800" : "bg-muted/30"}>
      <CardContent className="p-3">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-lg font-bold">{value}</p>
      </CardContent>
    </Card>
  );
}

/**
 * Curriculum-aware grade summary card.
 *
 * Switches the displayed stats based on the curriculum type:
 * - american: Term GPA, Cumulative GPA, Credits Earned, Honor Roll badge
 * - ib: IB Total Points (/45), Class Position, Average Score
 * - french: Average (/20), Mention, Class Position
 * - default (GES/Cambridge/Edexcel/Montessori/custom): Total Score, Average, Position, Subjects
 */
export function GradeSummaryCard({ grades }: GradeSummaryCardProps) {
  const curriculum = grades.curriculum_type ?? "ges";

  switch (curriculum) {
    case "american":
      return (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MiniStat
            label="Term GPA"
            value={grades.gpa != null ? grades.gpa.toFixed(2) : "N/A"}
          />
          <MiniStat
            label="Cumulative GPA"
            value={
              grades.cumulative_gpa != null
                ? grades.cumulative_gpa.toFixed(2)
                : "N/A"
            }
          />
          <MiniStat
            label="Credits Earned"
            value={
              grades.total_credits_earned != null
                ? grades.total_credits_earned.toString()
                : "N/A"
            }
          />
          <Card
            className={
              grades.honor_roll
                ? "bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800"
                : "bg-muted/30"
            }
          >
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground">Honor Roll</p>
              <div className="flex items-center gap-1.5">
                {grades.honor_roll && (
                  <Award className="h-4 w-4 text-green-600 dark:text-green-400" />
                )}
                <p className="text-lg font-bold">
                  {grades.honor_roll ? "Yes" : "No"}
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      );

    case "ib":
      return (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <MiniStat
            label="IB Total Points"
            value={
              grades.ib_total_points != null
                ? `${grades.ib_total_points}/45`
                : "N/A"
            }
          />
          <MiniStat
            label="Position"
            value={
              grades.overall
                ? `${grades.overall.class_position}/${grades.overall.class_size}`
                : "N/A"
            }
          />
          <MiniStat
            label="Average Score"
            value={
              grades.overall
                ? grades.overall.average.toFixed(1)
                : "N/A"
            }
          />
        </div>
      );

    case "french":
      return (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <MiniStat
            label="Average"
            value={
              grades.overall
                ? `${grades.overall.average.toFixed(1)}/20`
                : "N/A"
            }
          />
          <Card className="bg-muted/30">
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground">Mention</p>
              <div className="flex items-center gap-1.5">
                <p className="text-lg font-bold">
                  {grades.french_mention ?? "N/A"}
                </p>
                {grades.french_mention && (
                  <Badge variant="secondary" className="text-xs">
                    {grades.french_mention}
                  </Badge>
                )}
              </div>
            </CardContent>
          </Card>
          <MiniStat
            label="Position"
            value={
              grades.overall
                ? `${grades.overall.class_position}/${grades.overall.class_size}`
                : "N/A"
            }
          />
        </div>
      );

    default:
      // GES, Cambridge, Edexcel, Montessori, custom
      return (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MiniStat
            label="Total Marks"
            value={
              grades.overall
                ? grades.overall.total_marks.toString()
                : "N/A"
            }
          />
          <MiniStat
            label="Average"
            value={
              grades.overall
                ? `${grades.overall.average.toFixed(1)}%`
                : "N/A"
            }
          />
          <MiniStat
            label="Position"
            value={
              grades.overall
                ? `${grades.overall.class_position}/${grades.overall.class_size}`
                : "N/A"
            }
          />
          <MiniStat
            label="Subjects"
            value={grades.subjects.length.toString()}
          />
        </div>
      );
  }
}

/**
 * Determine if position column should be hidden for this curriculum.
 * Cambridge, IB, and Montessori typically don't show position.
 */
export function shouldHidePosition(curriculum: CurriculumType | undefined): boolean {
  return curriculum === "cambridge" || curriculum === "ib" || curriculum === "montessori";
}

/**
 * Format a score value based on the score display mode.
 */
export function formatScoreDisplay(
  score: number | null | undefined,
  grade: string | null | undefined,
  displayMode: string | undefined
): string {
  if (score == null && grade == null) return "--";

  switch (displayMode) {
    case "gpa":
      return score != null ? score.toFixed(1) : grade ?? "--";
    case "level":
      return score != null ? `Level ${score}` : "--";
    case "grade_only":
      return grade ?? "--";
    case "narrative":
      return grade ?? "--";
    case "mention":
      return grade ?? "--";
    case "percentage":
      return score != null ? `${score}%` : "--";
    case "grade_and_score":
    default:
      return score != null ? score.toString() : "--";
  }
}
