"use client";

import { useMemo } from "react";
import { Calendar, BookOpen, GraduationCap, Clock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { Term, SchoolHoliday } from "@/types";

interface SchoolDaysCounterProps {
  terms: Term[];
  holidays: SchoolHoliday[];
  currentTerm?: Term;
}

/**
 * Calculate school days for a term, excluding weekends and holidays/vacations.
 * This mirrors the backend calculation logic in exam.py.
 */
function calculateSchoolDays(
  startDate: Date,
  endDate: Date,
  holidays: SchoolHoliday[]
): { totalDays: number; holidayCount: number } {
  // Create a set of holiday dates (only 'holiday' and 'vacation' types)
  const holidayDates = new Set(
    holidays
      .filter((h) => h.holiday_type === "holiday" || h.holiday_type === "vacation")
      .map((h) => h.date)
  );

  let totalDays = 0;
  let holidayCount = 0;
  const current = new Date(startDate);

  while (current <= endDate) {
    const dayOfWeek = current.getDay();
    const dateKey = current.toISOString().split("T")[0];

    // Check if it's a weekday (Monday = 1, Friday = 5)
    if (dayOfWeek !== 0 && dayOfWeek !== 6) {
      // Check if it's not a holiday
      if (!holidayDates.has(dateKey)) {
        totalDays++;
      } else {
        holidayCount++;
      }
    }

    // Move to next day
    current.setDate(current.getDate() + 1);
  }

  return { totalDays, holidayCount };
}

/**
 * Calculate elapsed school days from start of term to today.
 */
function calculateElapsedDays(
  startDate: Date,
  holidays: SchoolHoliday[]
): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  if (today < startDate) return 0;

  const { totalDays } = calculateSchoolDays(startDate, today, holidays);
  return totalDays;
}

function formatShortDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export function SchoolDaysCounter({
  terms,
  holidays,
  currentTerm,
}: SchoolDaysCounterProps) {
  // Calculate school days for all terms
  const termStats = useMemo(() => {
    return terms.map((term) => {
      const start = new Date(term.start_date);
      const end = new Date(term.end_date);
      const termHolidays = holidays.filter((h) => {
        const hDate = new Date(h.date);
        return hDate >= start && hDate <= end;
      });
      const { totalDays, holidayCount } = calculateSchoolDays(start, end, termHolidays);
      const elapsed = calculateElapsedDays(start, termHolidays);
      const remaining = Math.max(0, totalDays - elapsed);
      const progress = totalDays > 0 ? (elapsed / totalDays) * 100 : 0;

      return {
        term,
        totalDays,
        holidayCount,
        elapsed,
        remaining,
        progress,
      };
    });
  }, [terms, holidays]);

  // Get current term stats
  const currentTermStats = useMemo(() => {
    if (!currentTerm) return null;
    return termStats.find((s) => s.term.id === currentTerm.id);
  }, [termStats, currentTerm]);

  // Calculate year totals
  const yearTotals = useMemo(() => {
    return termStats.reduce(
      (acc, stat) => ({
        totalDays: acc.totalDays + stat.totalDays,
        holidayCount: acc.holidayCount + stat.holidayCount,
        elapsed: acc.elapsed + stat.elapsed,
      }),
      { totalDays: 0, holidayCount: 0, elapsed: 0 }
    );
  }, [termStats]);

  if (terms.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Calendar className="h-4 w-4" />
            School Days
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-center py-4">
            No terms configured for this academic year
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Calendar className="h-4 w-4" />
          School Days
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Current Term Progress */}
        {currentTermStats && (
          <div className="rounded-lg bg-primary/5 border border-primary/20 p-3 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <GraduationCap className="h-4 w-4 text-primary" />
                <span className="font-medium text-sm">{currentTermStats.term.name}</span>
              </div>
              <span className="text-xs text-muted-foreground">Current</span>
            </div>

            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Progress</span>
                <span className="font-medium">
                  {currentTermStats.elapsed} / {currentTermStats.totalDays} days
                </span>
              </div>
              <Progress value={currentTermStats.progress} className="h-2" />
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <Clock className="h-3 w-3" />
                <span>{currentTermStats.remaining} days left</span>
              </div>
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <BookOpen className="h-3 w-3" />
                <span>{currentTermStats.holidayCount} holidays</span>
              </div>
            </div>
          </div>
        )}

        {/* All Terms Summary */}
        <div className="space-y-2">
          <div className="text-sm font-medium text-muted-foreground">
            Term Summary
          </div>
          {termStats.map((stat) => (
            <div
              key={stat.term.id}
              className="flex items-center justify-between py-2 border-b last:border-0"
            >
              <div className="space-y-0.5">
                <div className="text-sm font-medium">
                  {stat.term.short_name || stat.term.name}
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatShortDate(stat.term.start_date)} -{" "}
                  {formatShortDate(stat.term.end_date)}
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-medium">{stat.totalDays}</div>
                <div className="text-xs text-muted-foreground">school days</div>
              </div>
            </div>
          ))}
        </div>

        {/* Year Totals */}
        <div className="rounded-lg bg-muted/50 p-3">
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <div className="text-lg font-bold">{yearTotals.totalDays}</div>
              <div className="text-xs text-muted-foreground">Total Days</div>
            </div>
            <div>
              <div className="text-lg font-bold">{yearTotals.elapsed}</div>
              <div className="text-xs text-muted-foreground">Completed</div>
            </div>
            <div>
              <div className="text-lg font-bold">{yearTotals.holidayCount}</div>
              <div className="text-xs text-muted-foreground">Holidays</div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
