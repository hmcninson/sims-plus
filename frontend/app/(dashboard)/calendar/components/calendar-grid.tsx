"use client";

import { useMemo, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { updateSchoolHoliday } from "@/actions/timetable.action";
import type { Term, SchoolHoliday, HolidayType } from "@/types";

interface CalendarGridProps {
  currentMonth: Date;
  selectedDate: Date | null;
  holidaysByDate: Map<string, SchoolHoliday[]>;
  terms: Term[];
  onDateClick: (date: Date) => void;
  onDateDoubleClick?: (date: Date) => void;
  onEventClick?: (event: SchoolHoliday) => void;
  onEventMoved?: () => void;
  getTermForDate: (date: Date) => Term | undefined;
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// Holiday type to color mapping
const HOLIDAY_COLORS: Record<HolidayType, string> = {
  holiday: "bg-red-500",
  vacation: "bg-blue-500",
  exam: "bg-yellow-500",
  event: "bg-green-500",
};

const HOLIDAY_BG_COLORS: Record<HolidayType, string> = {
  holiday: "bg-red-100 border-red-300 text-red-800",
  vacation: "bg-blue-100 border-blue-300 text-blue-800",
  exam: "bg-yellow-100 border-yellow-300 text-yellow-800",
  event: "bg-green-100 border-green-300 text-green-800",
};

// Term index to background color mapping
const TERM_BACKGROUNDS = [
  "bg-blue-500/10",
  "bg-green-500/10",
  "bg-purple-500/10",
  "bg-orange-500/10",
];

export function CalendarGrid({
  currentMonth,
  selectedDate,
  holidaysByDate,
  terms,
  onDateClick,
  onDateDoubleClick,
  onEventClick,
  onEventMoved,
  getTermForDate,
}: CalendarGridProps) {
  // Drag state
  const [draggedEvent, setDraggedEvent] = useState<SchoolHoliday | null>(null);
  const [dragOverDate, setDragOverDate] = useState<string | null>(null);

  // Generate calendar days for the current month
  const calendarDays = useMemo(() => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();

    // First day of the month
    const firstDay = new Date(year, month, 1);
    // Last day of the month
    const lastDay = new Date(year, month + 1, 0);

    // Get the day of week for the first day (0 = Sunday, we want Monday = 0)
    let startDayOfWeek = firstDay.getDay() - 1;
    if (startDayOfWeek < 0) startDayOfWeek = 6; // Sunday becomes 6

    // Days from previous month to show
    const prevMonthDays: Date[] = [];
    const prevMonth = new Date(year, month, 0);
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      prevMonthDays.push(new Date(year, month - 1, prevMonth.getDate() - i));
    }

    // Days of current month
    const currentMonthDays: Date[] = [];
    for (let i = 1; i <= lastDay.getDate(); i++) {
      currentMonthDays.push(new Date(year, month, i));
    }

    // Days from next month to fill the grid (6 rows * 7 days = 42 total)
    const nextMonthDays: Date[] = [];
    const totalDays = prevMonthDays.length + currentMonthDays.length;
    const daysNeeded = 42 - totalDays; // Always show 6 rows
    for (let i = 1; i <= daysNeeded; i++) {
      nextMonthDays.push(new Date(year, month + 1, i));
    }

    return {
      prevMonth: prevMonthDays,
      currentMonth: currentMonthDays,
      nextMonth: nextMonthDays,
    };
  }, [currentMonth]);

  // Get term index for a date (for consistent coloring)
  const getTermIndex = (date: Date): number => {
    const term = getTermForDate(date);
    if (!term) return -1;
    return terms.findIndex((t) => t.id === term.id);
  };

  // Check if date is today
  const isToday = (date: Date): boolean => {
    const today = new Date();
    return (
      date.getDate() === today.getDate() &&
      date.getMonth() === today.getMonth() &&
      date.getFullYear() === today.getFullYear()
    );
  };

  // Check if date is selected
  const isSelected = (date: Date): boolean => {
    if (!selectedDate) return false;
    return (
      date.getDate() === selectedDate.getDate() &&
      date.getMonth() === selectedDate.getMonth() &&
      date.getFullYear() === selectedDate.getFullYear()
    );
  };

  // Check if date is a weekend
  const isWeekend = (date: Date): boolean => {
    const day = date.getDay();
    return day === 0 || day === 6;
  };

  // Drag handlers
  const handleDragStart = useCallback(
    (e: React.DragEvent, event: SchoolHoliday) => {
      e.stopPropagation();
      setDraggedEvent(event);
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", event.id);
    },
    []
  );

  const handleDragOver = useCallback((e: React.DragEvent, dateKey: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverDate(dateKey);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOverDate(null);
  }, []);

  const handleDrop = useCallback(
    async (e: React.DragEvent, date: Date) => {
      e.preventDefault();
      setDragOverDate(null);

      if (!draggedEvent) return;

      const newDateKey = date.toISOString().split("T")[0];
      const oldDateKey = draggedEvent.date;

      // Don't do anything if dropped on the same date
      if (newDateKey === oldDateKey) {
        setDraggedEvent(null);
        return;
      }

      // Update the event date
      const result = await updateSchoolHoliday(draggedEvent.id, {
        date: newDateKey,
      });

      if (result.success) {
        toast.success(`"${draggedEvent.name}" moved to ${date.toLocaleDateString()}`);
        onEventMoved?.();
      } else {
        toast.error(result.error || "Failed to move event");
      }

      setDraggedEvent(null);
    },
    [draggedEvent, onEventMoved]
  );

  const handleDragEnd = useCallback(() => {
    setDraggedEvent(null);
    setDragOverDate(null);
  }, []);

  // Double-click handler
  const handleDoubleClick = useCallback(
    (date: Date) => {
      onDateDoubleClick?.(date);
    },
    [onDateDoubleClick]
  );

  // Render a single day cell
  const renderDayCell = (date: Date, isCurrentMonth: boolean) => {
    const dateKey = date.toISOString().split("T")[0];
    const dayHolidays = holidaysByDate.get(dateKey) || [];
    const termIndex = getTermIndex(date);
    const hasHoliday = dayHolidays.length > 0;
    const weekend = isWeekend(date);
    const isDragOver = dragOverDate === dateKey;

    return (
      <div
        key={dateKey}
        onClick={() => onDateClick(date)}
        onDoubleClick={() => handleDoubleClick(date)}
        onDragOver={(e) => handleDragOver(e, dateKey)}
        onDragLeave={handleDragLeave}
        onDrop={(e) => handleDrop(e, date)}
        className={cn(
          "relative h-24 p-1 border border-border/50 transition-colors cursor-pointer",
          "hover:bg-accent/50 focus:outline-none",
          !isCurrentMonth && "text-muted-foreground/50 bg-muted/30",
          isCurrentMonth && termIndex >= 0 && TERM_BACKGROUNDS[termIndex % TERM_BACKGROUNDS.length],
          weekend && isCurrentMonth && "bg-muted/50",
          isSelected(date) && "ring-2 ring-primary",
          isToday(date) && "ring-2 ring-primary ring-offset-2",
          isDragOver && "bg-accent ring-2 ring-primary ring-dashed"
        )}
      >
        {/* Date number */}
        <div
          className={cn(
            "text-sm font-medium",
            isToday(date) &&
              "bg-primary text-primary-foreground w-6 h-6 rounded-full flex items-center justify-center"
          )}
        >
          {date.getDate()}
        </div>

        {/* Holiday indicators */}
        {hasHoliday && (
          <div className="absolute bottom-1 left-1 right-1 space-y-0.5">
            {dayHolidays.slice(0, 2).map((holiday) => (
              <div
                key={holiday.id}
                draggable
                onDragStart={(e) => handleDragStart(e, holiday)}
                onDragEnd={handleDragEnd}
                onClick={(e) => {
                  e.stopPropagation();
                  onEventClick?.(holiday);
                }}
                className={cn(
                  "text-[10px] px-1 py-0.5 rounded border truncate cursor-grab active:cursor-grabbing",
                  HOLIDAY_BG_COLORS[holiday.holiday_type],
                  "hover:opacity-80 transition-opacity"
                )}
                title={`${holiday.name} (drag to reschedule)`}
              >
                {holiday.name}
              </div>
            ))}
            {dayHolidays.length > 2 && (
              <div className="text-[10px] text-muted-foreground px-1">
                +{dayHolidays.length - 2} more
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="bg-card rounded-lg border overflow-hidden">
      {/* Weekday headers */}
      <div className="grid grid-cols-7 bg-muted/50">
        {WEEKDAYS.map((day) => (
          <div
            key={day}
            className="p-2 text-center text-sm font-medium text-muted-foreground border-b"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7">
        {/* Previous month days */}
        {calendarDays.prevMonth.map((date) => renderDayCell(date, false))}

        {/* Current month days */}
        {calendarDays.currentMonth.map((date) => renderDayCell(date, true))}

        {/* Next month days */}
        {calendarDays.nextMonth.map((date) => renderDayCell(date, false))}
      </div>
    </div>
  );
}
