"use client";

import { useState, useEffect, useTransition } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, ChevronLeft, ChevronRight, Calendar } from "lucide-react";

import { getLeaveCalendar } from "@/actions/leave.action";
import type { LeaveCalendarEntry } from "@/types/leave.type";

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 1).getDay();
}

function formatMonthYear(year: number, month: number): string {
  return new Date(year, month).toLocaleDateString("en-GB", {
    month: "long",
    year: "numeric",
  });
}

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function LeaveCalendarView() {
  const [isPending, startTransition] = useTransition();
  const [entries, setEntries] = useState<LeaveCalendarEntry[]>([]);
  const [currentYear, setCurrentYear] = useState(new Date().getFullYear());
  const [currentMonth, setCurrentMonth] = useState(new Date().getMonth());

  useEffect(() => {
    startTransition(async () => {
      const startDate = `${currentYear}-${String(currentMonth + 1).padStart(2, "0")}-01`;
      const daysInMonth = getDaysInMonth(currentYear, currentMonth);
      const endDate = `${currentYear}-${String(currentMonth + 1).padStart(2, "0")}-${String(daysInMonth).padStart(2, "0")}`;

      const result = await getLeaveCalendar(startDate, endDate);
      if (result.success && result.data) {
        setEntries(result.data);
      }
    });
  }, [currentYear, currentMonth]);

  const goToPreviousMonth = () => {
    if (currentMonth === 0) {
      setCurrentMonth(11);
      setCurrentYear((y) => y - 1);
    } else {
      setCurrentMonth((m) => m - 1);
    }
  };

  const goToNextMonth = () => {
    if (currentMonth === 11) {
      setCurrentMonth(0);
      setCurrentYear((y) => y + 1);
    } else {
      setCurrentMonth((m) => m + 1);
    }
  };

  const goToToday = () => {
    const now = new Date();
    setCurrentYear(now.getFullYear());
    setCurrentMonth(now.getMonth());
  };

  // Build calendar grid
  const daysInMonth = getDaysInMonth(currentYear, currentMonth);
  const firstDay = getFirstDayOfMonth(currentYear, currentMonth);

  // Map entries to days
  const getEntriesForDay = (day: number): LeaveCalendarEntry[] => {
    const dateStr = `${currentYear}-${String(currentMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    return entries.filter((entry) => {
      return dateStr >= entry.start_date && dateStr <= entry.end_date;
    });
  };

  // Collect unique leave types for legend
  const uniqueTypes = Array.from(
    new Map(
      entries.map((e) => [
        e.leave_type_name,
        { name: e.leave_type_name, color: e.leave_type_color },
      ])
    ).values()
  );

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle>Leave Calendar</CardTitle>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" onClick={goToPreviousMonth}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="min-w-[160px] text-center text-sm font-medium">
              {formatMonthYear(currentYear, currentMonth)}
            </span>
            <Button variant="outline" size="icon" onClick={goToNextMonth}>
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={goToToday}>
              Today
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <div className="flex h-[400px] items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <>
            {/* Calendar Grid */}
            <div className="grid grid-cols-7 gap-px rounded-lg border bg-muted overflow-hidden">
              {/* Weekday headers */}
              {WEEKDAY_LABELS.map((day) => (
                <div
                  key={day}
                  className="bg-muted px-2 py-2 text-center text-xs font-medium text-muted-foreground"
                >
                  {day}
                </div>
              ))}

              {/* Empty cells before first day */}
              {Array.from({ length: firstDay }).map((_, i) => (
                <div key={`empty-${i}`} className="bg-background min-h-[80px] p-1" />
              ))}

              {/* Day cells */}
              {Array.from({ length: daysInMonth }).map((_, i) => {
                const day = i + 1;
                const dayEntries = getEntriesForDay(day);
                const isToday =
                  day === new Date().getDate() &&
                  currentMonth === new Date().getMonth() &&
                  currentYear === new Date().getFullYear();
                const isWeekend = (firstDay + i) % 7 === 0 || (firstDay + i) % 7 === 6;

                return (
                  <div
                    key={day}
                    className={`bg-background min-h-[80px] p-1 ${
                      isWeekend ? "bg-muted/50" : ""
                    }`}
                  >
                    <div
                      className={`text-xs font-medium mb-1 ${
                        isToday
                          ? "inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground"
                          : "text-muted-foreground"
                      }`}
                    >
                      {day}
                    </div>
                    <div className="space-y-0.5">
                      {dayEntries.slice(0, 3).map((entry, idx) => (
                        <div
                          key={`${entry.staff_id}-${idx}`}
                          className="truncate rounded px-1 py-0.5 text-[10px] leading-tight text-white"
                          style={{
                            backgroundColor: entry.leave_type_color || "#6B7280",
                          }}
                          title={`${entry.staff_name} - ${entry.leave_type_name}`}
                        >
                          {entry.staff_name.split(" ")[0]}
                        </div>
                      ))}
                      {dayEntries.length > 3 && (
                        <div className="text-[10px] text-muted-foreground px-1">
                          +{dayEntries.length - 3} more
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Legend */}
            {uniqueTypes.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-3">
                {uniqueTypes.map((type) => (
                  <div key={type.name} className="flex items-center gap-1.5 text-xs">
                    <div
                      className="h-3 w-3 rounded-sm"
                      style={{ backgroundColor: type.color || "#6B7280" }}
                    />
                    <span className="text-muted-foreground">{type.name}</span>
                  </div>
                ))}
              </div>
            )}

            {entries.length === 0 && (
              <div className="flex flex-col items-center justify-center gap-2 py-8 text-muted-foreground">
                <Calendar className="h-10 w-10" />
                <p className="text-sm">No leave entries for this month</p>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
