"use client";

/**
 * SIMS Plus - Teacher Dashboard
 *
 * Overview page showing today's schedule, key stats (classes, subjects,
 * students), and pending tasks. Uses the TeacherDashboard schema from
 * the backend which returns teacher_name, staff_id, totals, classes,
 * subjects, today_schedule, and pending_tasks.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  BookOpen,
  Users,
  GraduationCap,
  Clock,
  AlertCircle,
  ArrowRight,
  Loader2,
  CheckCircle2,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { getTeacherDashboard } from "@/actions/teacher.action";
import type { TeacherDashboardData, UpcomingLesson, PendingTask } from "@/types/teacher.type";
import { formatTime } from "@/lib/format";

const WEEK_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function TeacherDashboardPage() {
  const [data, setData] = useState<TeacherDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      const result = await getTeacherDashboard();
      if (result.success) {
        setData(result.data);
      } else {
        setError(result.error);
      }
      setLoading(false);
    }
    load();
  }, []);

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
        <AlertDescription>{error || "Failed to load dashboard"}</AlertDescription>
      </Alert>
    );
  }

  const today = new Date();
  const dayName = WEEK_DAY_NAMES[today.getDay() === 0 ? 6 : today.getDay() - 1];

  return (
    <div className="space-y-6">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Welcome back, {data.teacher_name}
        </h1>
        <p className="text-muted-foreground">
          {dayName}, {today.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}
          {data.staff_id ? ` | ${data.staff_id}` : ""}
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                <BookOpen className="h-5 w-5" />
              </div>
              <div>
                <p className="text-2xl font-bold">{data.total_classes}</p>
                <p className="text-xs text-muted-foreground">My Classes</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50 text-green-600">
                <Users className="h-5 w-5" />
              </div>
              <div>
                <p className="text-2xl font-bold">{data.total_students}</p>
                <p className="text-xs text-muted-foreground">Students</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
                <GraduationCap className="h-5 w-5" />
              </div>
              <div>
                <p className="text-2xl font-bold">{data.total_subjects}</p>
                <p className="text-xs text-muted-foreground">Subjects</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Today's Schedule */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Today&apos;s Schedule</CardTitle>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/teacher/schedule">
                  View Full <ArrowRight className="ml-1 h-3 w-3" />
                </Link>
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {data.today_schedule.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No classes scheduled for today
              </p>
            ) : (
              <div className="space-y-2">
                {data.today_schedule.map((entry: UpcomingLesson, idx: number) => (
                  <div
                    key={entry.timetable_id || idx}
                    className="flex items-center gap-3 rounded-lg border p-3"
                  >
                    <div className="flex flex-col items-center text-xs text-muted-foreground min-w-[60px]">
                      <span className="font-medium">{formatTime(entry.start_time)}</span>
                      <span>{formatTime(entry.end_time)}</span>
                    </div>
                    <div className="h-8 w-px bg-border" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">
                        {entry.subject_name}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">
                        {entry.class_name}
                        {entry.section_name ? ` - ${entry.section_name}` : ""}
                        {entry.room ? ` | ${entry.room}` : ""}
                      </p>
                    </div>
                    <Badge variant="outline" className="text-xs shrink-0">
                      P{entry.period_number}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Pending Tasks */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Pending Tasks</CardTitle>
            <CardDescription>
              {data.pending_tasks.length === 0
                ? "All caught up!"
                : `${data.pending_tasks.length} task${data.pending_tasks.length !== 1 ? "s" : ""} need attention`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {data.pending_tasks.length === 0 ? (
              <div className="flex flex-col items-center py-4 text-center">
                <CheckCircle2 className="h-8 w-8 text-green-500 mb-2" />
                <p className="text-sm text-muted-foreground">Nothing pending</p>
              </div>
            ) : (
              <div className="space-y-2">
                {data.pending_tasks.slice(0, 5).map((task: PendingTask, idx: number) => (
                  <div
                    key={`${task.task_type}-${idx}`}
                    className="flex items-start gap-3 rounded-lg border p-3"
                  >
                    <div className="flex h-6 w-6 items-center justify-center rounded-full text-xs shrink-0 mt-0.5 text-amber-600 bg-amber-50 border-amber-200">
                      {task.count}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm">{task.task_type.replace(/_/g, " ")}</p>
                      <p className="text-xs text-muted-foreground truncate">
                        {task.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Subjects Overview */}
      {data.subjects.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">My Subjects</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {data.subjects.map((subject) => (
                <Badge key={subject.subject_id} variant="outline" className="text-xs py-1.5 px-3">
                  {subject.subject_name}
                  <span className="ml-1 text-muted-foreground">({subject.class_count} class{subject.class_count !== 1 ? "es" : ""})</span>
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
