"use client";

/**
 * SIMS Plus - Head Teacher Performance Page
 *
 * Teacher-level performance analytics for the head teacher.
 * Backend: GET /teacher/head-teacher/performance -> TeacherPerformanceSummary
 *
 * Shows per-teacher performance metrics: lesson plan completion,
 * score entry progress, notes created, and reports signed.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  Loader2,
  BarChart3,
  ShieldAlert,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import { useSession } from "@/components/providers/SessionProvider";
import { getHeadTeacherPerformance } from "@/actions/teacher.action";
import type { TeacherPerformanceSummary, TeacherPerformanceItem } from "@/types/teacher.type";

function getCompletionColor(rate: number): string {
  if (rate >= 80) return "text-green-600";
  if (rate >= 60) return "text-amber-600";
  return "text-red-600";
}

export default function HeadTeacherPerformancePage() {
  const { user } = useSession();
  const [data, setData] = useState<TeacherPerformanceSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isAuthorized = user.role === "academic_head" || user.role === "school_admin";

  useEffect(() => {
    if (!isAuthorized) return;
    async function load() {
      const result = await getHeadTeacherPerformance();
      if (result.success) {
        setData(result.data);
      } else {
        setError(result.error);
      }
      setLoading(false);
    }
    load();
  }, [isAuthorized]);

  // Client-side access control: only academic heads and school admins
  if (!isAuthorized) {
    return (
      <div className="flex items-center justify-center p-8">
        <Card className="max-w-md">
          <CardContent className="pt-6 text-center">
            <ShieldAlert className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            <h2 className="text-lg font-semibold mb-2">Access Restricted</h2>
            <p className="text-muted-foreground">
              This page is only accessible to academic heads and school admins.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error || "Failed to load performance data"}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="icon" asChild className="mt-1">
          <Link href="/teacher/head-teacher">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Teacher Performance</h1>
          <p className="text-muted-foreground">
            {data.total_teachers} teacher{data.total_teachers !== 1 ? "s" : ""} | Per-teacher performance metrics
          </p>
        </div>
      </div>

      {/* Overall Completion Rates */}
      <div className="grid gap-4 sm:grid-cols-2">
        {data.overall_lesson_plan_completion !== null && (
          <Card>
            <CardContent className="p-4">
              <p className="text-sm font-medium text-muted-foreground mb-2">
                Overall Lesson Plan Completion
              </p>
              <div className="flex items-center gap-4">
                <Progress value={data.overall_lesson_plan_completion} className="flex-1" />
                <span className={`text-lg font-bold ${getCompletionColor(data.overall_lesson_plan_completion)}`}>
                  {Math.round(data.overall_lesson_plan_completion)}%
                </span>
              </div>
            </CardContent>
          </Card>
        )}
        {data.overall_score_entry_completion !== null && (
          <Card>
            <CardContent className="p-4">
              <p className="text-sm font-medium text-muted-foreground mb-2">
                Overall Score Entry Completion
              </p>
              <div className="flex items-center gap-4">
                <Progress value={data.overall_score_entry_completion} className="flex-1" />
                <span className={`text-lg font-bold ${getCompletionColor(data.overall_score_entry_completion)}`}>
                  {Math.round(data.overall_score_entry_completion)}%
                </span>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {data.teachers.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BarChart3 className="h-12 w-12 text-muted-foreground/50 mb-3" />
            <p className="text-muted-foreground">No teacher performance data available</p>
            <p className="text-xs text-muted-foreground mt-1">
              Data appears once teachers are assigned to classes
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {data.teachers.map((teacher: TeacherPerformanceItem) => {
            const totalScores = teacher.scores_entered + teacher.scores_pending;
            const scoreRate = totalScores > 0
              ? Math.round((teacher.scores_entered / totalScores) * 100)
              : null;
            const planRate = teacher.lesson_plans_created > 0
              ? Math.round((teacher.lesson_plans_taught / teacher.lesson_plans_created) * 100)
              : null;

            return (
              <Card key={teacher.staff_id}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base">{teacher.teacher_name}</CardTitle>
                      <CardDescription>
                        {teacher.staff_id}
                        {" | "}
                        {teacher.total_classes} class{teacher.total_classes !== 1 ? "es" : ""}
                        {", "}
                        {teacher.total_subjects} subject{teacher.total_subjects !== 1 ? "s" : ""}
                        {", "}
                        {teacher.total_students} student{teacher.total_students !== 1 ? "s" : ""}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b">
                          <th className="pb-2 text-left text-xs font-medium text-muted-foreground">
                            Metric
                          </th>
                          <th className="pb-2 text-center text-xs font-medium text-muted-foreground">
                            Progress
                          </th>
                          <th className="pb-2 text-center text-xs font-medium text-muted-foreground">
                            Rate
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-b">
                          <td className="py-2.5 text-sm font-medium">Score Entry</td>
                          <td className="py-2.5 text-center text-sm">
                            {teacher.scores_entered} / {totalScores}
                          </td>
                          <td className="py-2.5">
                            {scoreRate !== null ? (
                              <div className="flex items-center gap-2 justify-center">
                                <Progress value={scoreRate} className="w-16 h-2" />
                                <span className={`text-xs font-medium ${getCompletionColor(scoreRate)}`}>
                                  {scoreRate}%
                                </span>
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground text-center block">--</span>
                            )}
                          </td>
                        </tr>
                        <tr className="border-b">
                          <td className="py-2.5 text-sm font-medium">Lesson Plans</td>
                          <td className="py-2.5 text-center text-sm">
                            {teacher.lesson_plans_taught} / {teacher.lesson_plans_created}
                          </td>
                          <td className="py-2.5">
                            {planRate !== null ? (
                              <div className="flex items-center gap-2 justify-center">
                                <Progress value={planRate} className="w-16 h-2" />
                                <span className={`text-xs font-medium ${getCompletionColor(planRate)}`}>
                                  {planRate}%
                                </span>
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground text-center block">--</span>
                            )}
                          </td>
                        </tr>
                        <tr className="border-b last:border-0">
                          <td className="py-2.5 text-sm font-medium">Notes Created</td>
                          <td className="py-2.5 text-center text-sm">
                            {teacher.notes_created}
                          </td>
                          <td className="py-2.5 text-center">
                            <span className="text-xs text-muted-foreground">--</span>
                          </td>
                        </tr>
                        <tr>
                          <td className="py-2.5 text-sm font-medium">Reports Signed</td>
                          <td className="py-2.5 text-center text-sm">
                            {teacher.reports_signed}
                          </td>
                          <td className="py-2.5 text-center">
                            <span className="text-xs text-muted-foreground">--</span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
