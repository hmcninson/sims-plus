"use client";

/**
 * SIMS Plus - Teacher Schedule Page
 *
 * Displays the teacher's full weekly timetable in a grid view.
 * Each cell shows the subject, class/section, and room. The current
 * day is highlighted for quick reference.
 */

import { useEffect, useState } from "react";
import { AlertCircle, Calendar, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { getTeacherSchedule } from "@/actions/teacher.action";
import type { TeacherWeeklySchedule, TeacherScheduleDay } from "@/types/teacher.type";
import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/format";

const SCHOOL_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];

function getTodayDayOfWeek(): number {
  const day = new Date().getDay();
  // Convert Sunday (0) -> 6, Monday (1) -> 0, etc.
  return day === 0 ? 6 : day - 1;
}

// Soft color assignments for subjects by index
const SUBJECT_COLORS = [
  "bg-blue-50 border-blue-200 text-blue-800",
  "bg-green-50 border-green-200 text-green-800",
  "bg-purple-50 border-purple-200 text-purple-800",
  "bg-amber-50 border-amber-200 text-amber-800",
  "bg-rose-50 border-rose-200 text-rose-800",
  "bg-teal-50 border-teal-200 text-teal-800",
  "bg-indigo-50 border-indigo-200 text-indigo-800",
  "bg-orange-50 border-orange-200 text-orange-800",
];

export default function TeacherSchedulePage() {
  const [schedule, setSchedule] = useState<TeacherWeeklySchedule | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      const result = await getTeacherSchedule();
      if (result.success) {
        setSchedule(result.data);
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

  if (error || !schedule) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error || "Failed to load schedule"}</AlertDescription>
      </Alert>
    );
  }

  const todayIdx = getTodayDayOfWeek();

  // Build a subject-to-color map for consistent coloring
  const subjectColorMap = new Map<string, string>();
  let colorIdx = 0;
  schedule.days.forEach((day) => {
    day.entries.forEach((entry) => {
      const key = entry.subject_id || entry.subject_name || "unknown";
      if (!subjectColorMap.has(key)) {
        subjectColorMap.set(key, SUBJECT_COLORS[colorIdx % SUBJECT_COLORS.length]);
        colorIdx++;
      }
    });
  });

  // Get all unique period numbers across all days, sorted
  const allPeriods = new Set<number>();
  schedule.days.forEach((day) => {
    day.entries.forEach((entry) => allPeriods.add(entry.period_number));
  });
  const periods = Array.from(allPeriods).sort((a, b) => a - b);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">My Schedule</h1>
        <p className="text-muted-foreground">
          Weekly timetable
        </p>
      </div>

      {/* Desktop: Grid view */}
      <Card className="hidden md:block">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground w-20">
                    Period
                  </th>
                  {SCHOOL_DAY_NAMES.map((name, idx) => (
                    <th
                      key={name}
                      className={cn(
                        "p-3 text-left text-xs font-medium text-muted-foreground",
                        idx === todayIdx && "bg-primary/5"
                      )}
                    >
                      <div className="flex items-center gap-1.5">
                        {name}
                        {idx === todayIdx && (
                          <Badge variant="default" className="text-[10px] h-4 px-1">
                            Today
                          </Badge>
                        )}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {periods.map((periodNum) => (
                  <tr key={periodNum} className="border-b last:border-0">
                    <td className="p-3 text-xs text-muted-foreground font-medium">
                      P{periodNum}
                    </td>
                    {SCHOOL_DAY_NAMES.map((_, dayIdx) => {
                      const dayData = schedule.days.find(
                        (d: TeacherScheduleDay) => d.day_of_week === dayIdx
                      );
                      const entry = dayData?.entries.find(
                        (e) => e.period_number === periodNum
                      );
                      return (
                        <td
                          key={dayIdx}
                          className={cn(
                            "p-2",
                            dayIdx === todayIdx && "bg-primary/5"
                          )}
                        >
                          {entry ? (
                            <div
                              className={cn(
                                "rounded-md border p-2 text-xs",
                                subjectColorMap.get(entry.subject_id || entry.subject_name || "unknown") || "bg-gray-50"
                              )}
                            >
                              <p className="font-medium truncate">{entry.subject_name || "Free Period"}</p>
                              <p className="text-[10px] opacity-80 truncate">
                                {entry.class_name}
                                {entry.section_name ? ` (${entry.section_name})` : ""}
                              </p>
                              <div className="flex items-center gap-1 mt-0.5">
                                <span className="text-[10px] opacity-70">
                                  {formatTime(entry.start_time)} - {formatTime(entry.end_time)}
                                </span>
                                {entry.room && (
                                  <span className="text-[10px] opacity-70">| {entry.room}</span>
                                )}
                              </div>
                            </div>
                          ) : (
                            <div className="h-16" />
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Mobile: Day-by-day cards */}
      <div className="space-y-4 md:hidden">
        {schedule.days.map((day: TeacherScheduleDay) => {
          const isToday = day.day_of_week === todayIdx;
          return (
            <Card key={day.day_of_week} className={cn(isToday && "ring-2 ring-primary/20")}>
              <CardHeader className="pb-2 pt-4 px-4">
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <CardTitle className="text-sm">
                    {day.day_name}
                    {isToday && (
                      <Badge variant="default" className="ml-2 text-[10px] h-4 px-1">
                        Today
                      </Badge>
                    )}
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent className="px-4 pb-4">
                {day.entries.length === 0 ? (
                  <p className="text-xs text-muted-foreground py-2">No classes</p>
                ) : (
                  <div className="space-y-2">
                    {day.entries
                      .sort((a, b) => a.period_number - b.period_number)
                      .map((entry) => (
                        <div
                          key={entry.id}
                          className={cn(
                            "rounded-md border p-2.5",
                            subjectColorMap.get(entry.subject_id || entry.subject_name || "unknown") || "bg-gray-50"
                          )}
                        >
                          <div className="flex items-center justify-between">
                            <p className="font-medium text-sm">{entry.subject_name || "Free Period"}</p>
                            <Badge variant="outline" className="text-[10px] h-4">
                              P{entry.period_number}
                            </Badge>
                          </div>
                          <p className="text-xs opacity-80 mt-0.5">
                            {entry.class_name}
                            {entry.section_name ? ` - ${entry.section_name}` : ""}
                          </p>
                          <p className="text-[10px] opacity-70 mt-0.5">
                            {formatTime(entry.start_time)} - {formatTime(entry.end_time)}
                            {entry.room ? ` | ${entry.room}` : ""}
                          </p>
                        </div>
                      ))}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
