"use client";

/**
 * SIMS Plus - Head Teacher Overview Page
 *
 * School-wide overview for head teachers/academic heads. Uses the
 * performance endpoint as the primary data source since the backend
 * has no dedicated /head-teacher/overview endpoint:
 *   GET /teacher/head-teacher/performance -> TeacherPerformanceSummary
 *
 * Displays overall teacher metrics and completion rates. Links to the
 * detailed performance page for per-teacher breakdowns.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  Loader2,
  Users,
  BookOpen,
  ClipboardCheck,
  TrendingUp,
  ArrowRight,
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

export default function HeadTeacherPage() {
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
        <AlertDescription>{error || "Failed to load overview"}</AlertDescription>
      </Alert>
    );
  }

  // Aggregate stats from teacher data
  const totalStudents = data.teachers.reduce((sum, t) => sum + t.total_students, 0);
  const totalClasses = data.teachers.reduce((sum, t) => sum + t.total_classes, 0);
  const totalSubjects = data.teachers.reduce((sum, t) => sum + t.total_subjects, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">School Overview</h1>
          <p className="text-muted-foreground">
            {data.total_teachers} teacher{data.total_teachers !== 1 ? "s" : ""}
          </p>
        </div>
        <Button size="sm" asChild>
          <Link href="/teacher/head-teacher/performance">
            <TrendingUp className="h-3.5 w-3.5 mr-1" />
            Performance
          </Link>
        </Button>
      </div>

      {/* Key Stats */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                <Users className="h-5 w-5" />
              </div>
              <div>
                <p className="text-2xl font-bold">{data.total_teachers}</p>
                <p className="text-xs text-muted-foreground">Teachers</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50 text-green-600">
                <BookOpen className="h-5 w-5" />
              </div>
              <div>
                <p className="text-2xl font-bold">{totalClasses}</p>
                <p className="text-xs text-muted-foreground">Class Assignments</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
                <BookOpen className="h-5 w-5" />
              </div>
              <div>
                <p className="text-2xl font-bold">{totalSubjects}</p>
                <p className="text-xs text-muted-foreground">Subject Assignments</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                <ClipboardCheck className="h-5 w-5" />
              </div>
              <div>
                <p className="text-2xl font-bold">{totalStudents}</p>
                <p className="text-xs text-muted-foreground">Total Students</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Completion Rates */}
      <div className="grid gap-4 sm:grid-cols-2">
        {data.overall_lesson_plan_completion !== null && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Lesson Plan Completion</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
                <Progress value={data.overall_lesson_plan_completion} className="flex-1" />
                <span className="text-lg font-bold">
                  {Math.round(data.overall_lesson_plan_completion)}%
                </span>
              </div>
            </CardContent>
          </Card>
        )}

        {data.overall_score_entry_completion !== null && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Score Entry Completion</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
                <Progress value={data.overall_score_entry_completion} className="flex-1" />
                <span className="text-lg font-bold">
                  {Math.round(data.overall_score_entry_completion)}%
                </span>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Teacher Summary */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Teacher Summary</CardTitle>
          <CardDescription>
            {data.total_teachers} teacher{data.total_teachers !== 1 ? "s" : ""} in the school
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {data.teachers.map((teacher: TeacherPerformanceItem) => (
              <div
                key={teacher.staff_id}
                className="flex items-center gap-4 rounded-lg border p-3"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-sm">{teacher.teacher_name}</p>
                    <Badge variant="outline" className="text-[10px]">
                      {teacher.staff_id}
                    </Badge>
                  </div>
                  <div className="flex gap-4 mt-1 text-xs text-muted-foreground">
                    <span>{teacher.total_classes} classes</span>
                    <span>{teacher.total_subjects} subjects</span>
                    <span>{teacher.total_students} students</span>
                  </div>
                </div>
                <div className="text-right hidden sm:block">
                  <p className="text-xs">
                    <span className="text-muted-foreground">Scores: </span>
                    <span className="font-medium">
                      {teacher.scores_entered}/{teacher.scores_entered + teacher.scores_pending}
                    </span>
                  </p>
                  <p className="text-xs">
                    <span className="text-muted-foreground">Plans: </span>
                    <span className="font-medium">
                      {teacher.lesson_plans_taught}/{teacher.lesson_plans_created}
                    </span>
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
