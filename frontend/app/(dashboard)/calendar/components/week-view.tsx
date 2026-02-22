"use client";

import { useMemo, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { updateSchoolHoliday } from "@/actions/timetable.action";
import type { Term, SchoolHoliday, HolidayType } from "@/types";

interface WeekViewProps {
  currentDate: Date;
  selectedDate: Date | null;
  holidaysByDate: Map<string, SchoolHoliday[]>;
  terms: Term[];
  onDateClick: (date: Date) => void;
  onDateDoubleClick?: (date: Date) => void;
  onEventClick: (event: SchoolHoliday) => void;
  onEventMoved?: () => void;
  getTermForDate: (date: Date) => Term | undefined;
}

const WEEKDAYS_FULL = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

// Holiday type to color mapping
const HOLIDAY_COLORS: Record<HolidayType, { bg: string; border: string; text: string }> = {
  holiday: { bg: "bg-red-100", border: "border-red-300", text: "text-red-800" },
  vacation: { bg: "bg-blue-100", border: "border-blue-300", text: "text-blue-800" },
  exam: { bg: "bg-yellow-100", border: "border-yellow-300", text: "text-yellow-800" },
  event: { bg: "bg-green-100", border: "border-green-300", text: "text-green-800" },
};

// Term index to background color mapping
const TERM_BACKGROUNDS = [
  "bg-blue-500/5",
  "bg-green-500/5",
  "bg-purple-500/5",
  "bg-orange-500/5",
];

export function WeekView({
  currentDate,
  selectedDate,
  holidaysByDate,
  terms,
  onDateClick,
  onDateDoubleClick,
  onEventClick,
  onEventMoved,
  getTermForDate,
}: WeekViewProps) {
  // Drag state
  const [draggedEvent, setDraggedEvent] = useState<SchoolHoliday | null>(null);
  const [dragOverDate, setDragOverDate] = useState<string | null>(null);

  // Get the week days for the current date
  const weekDays = useMemo(() => {
    const days: Date[] = [];
    const current = new Date(currentDate);

    // Get Monday of the current week
    const dayOfWeek = current.getDay();
    const diff = dayOfWeek === 0 ? -6 : 1 - dayOfWeek; // Adjust to start on Monday
    current.setDate(current.getDate() + diff);

    // Generate 7 days
    for (let i = 0; i < 7; i++) {
      days.push(new Date(current));
      current.setDate(current.getDate() + 1);
    }

    return days;
  }, [currentDate]);

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

  // Format date for display
  const formatDate = (date: Date): string => {
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
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

      if (newDateKey === oldDateKey) {
        setDraggedEvent(null);
        return;
      }

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

  // Hours to display (school hours)
  const hours = useMemo(() => {
    const h: string[] = [];
    for (let i = 6; i <= 18; i++) {
      h.push(`${i.toString().padStart(2, "0")}:00`);
    }
    return h;
  }, []);

  return (
    <div className="bg-card rounded-lg border overflow-hidden">
      {/* Header with day names and dates */}
      <div className="grid grid-cols-8 border-b">
        {/* Time column header */}
        <div className="p-2 text-center text-sm font-medium text-muted-foreground bg-muted/50 border-r">
          Time
        </div>

        {/* Day headers */}
        {weekDays.map((day, index) => {
          const termIndex = getTermIndex(day);
          const weekend = isWeekend(day);

          return (
            <div
              key={index}
              className={cn(
                "p-2 text-center border-r last:border-r-0",
                termIndex >= 0 && TERM_BACKGROUNDS[termIndex % TERM_BACKGROUNDS.length],
                weekend && "bg-muted/30",
                isToday(day) && "bg-primary/10"
              )}
            >
              <div className="text-sm font-medium">{WEEKDAYS_FULL[index]}</div>
              <div
                className={cn(
                  "text-xs",
                  isToday(day)
                    ? "bg-primary text-primary-foreground px-2 py-0.5 rounded-full inline-block"
                    : "text-muted-foreground"
                )}
              >
                {formatDate(day)}
              </div>
            </div>
          );
        })}
      </div>

      {/* All-day events row */}
      <div className="grid grid-cols-8 border-b min-h-[80px]">
        <div className="p-2 text-xs text-muted-foreground bg-muted/50 border-r flex items-start">
          All Day
        </div>

        {weekDays.map((day, dayIndex) => {
          const dateKey = day.toISOString().split("T")[0];
          const dayHolidays = holidaysByDate.get(dateKey) || [];
          const termIndex = getTermIndex(day);
          const weekend = isWeekend(day);
          const isDragOver = dragOverDate === dateKey;

          return (
            <div
              key={dayIndex}
              onClick={() => onDateClick(day)}
              onDoubleClick={() => onDateDoubleClick?.(day)}
              onDragOver={(e) => handleDragOver(e, dateKey)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, day)}
              className={cn(
                "p-1 border-r last:border-r-0 cursor-pointer transition-colors",
                "hover:bg-accent/50",
                termIndex >= 0 && TERM_BACKGROUNDS[termIndex % TERM_BACKGROUNDS.length],
                weekend && "bg-muted/30",
                isSelected(day) && "ring-2 ring-primary ring-inset",
                isDragOver && "bg-accent ring-2 ring-primary ring-dashed"
              )}
            >
              {dayHolidays.map((event) => (
                <div
                  key={event.id}
                  draggable
                  onDragStart={(e) => handleDragStart(e, event)}
                  onDragEnd={handleDragEnd}
                  onClick={(e) => {
                    e.stopPropagation();
                    onEventClick(event);
                  }}
                  className={cn(
                    "w-full text-left text-xs p-1 mb-1 rounded border truncate",
                    "cursor-grab active:cursor-grabbing",
                    HOLIDAY_COLORS[event.holiday_type].bg,
                    HOLIDAY_COLORS[event.holiday_type].border,
                    HOLIDAY_COLORS[event.holiday_type].text,
                    "hover:opacity-80 transition-opacity"
                  )}
                  title={`${event.name} (drag to reschedule)`}
                >
                  {event.name}
                </div>
              ))}
            </div>
          );
        })}
      </div>

      {/* Time grid */}
      <div className="max-h-[400px] overflow-y-auto">
        {hours.map((hour) => (
          <div key={hour} className="grid grid-cols-8 border-b last:border-b-0">
            {/* Time label */}
            <div className="p-2 text-xs text-muted-foreground bg-muted/50 border-r">
              {hour}
            </div>

            {/* Day cells */}
            {weekDays.map((day, dayIndex) => {
              const termIndex = getTermIndex(day);
              const weekend = isWeekend(day);
              const dateKey = day.toISOString().split("T")[0];
              const isDragOver = dragOverDate === dateKey;

              return (
                <div
                  key={dayIndex}
                  onClick={() => onDateClick(day)}
                  onDoubleClick={() => onDateDoubleClick?.(day)}
                  onDragOver={(e) => handleDragOver(e, dateKey)}
                  onDragLeave={handleDragLeave}
                  onDrop={(e) => handleDrop(e, day)}
                  className={cn(
                    "min-h-[40px] border-r last:border-r-0 cursor-pointer transition-colors",
                    "hover:bg-accent/30",
                    termIndex >= 0 && TERM_BACKGROUNDS[termIndex % TERM_BACKGROUNDS.length],
                    weekend && "bg-muted/20",
                    isSelected(day) && "bg-accent/20",
                    isDragOver && "bg-accent"
                  )}
                />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
