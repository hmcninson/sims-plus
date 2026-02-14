"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";
import type { Term, SchoolHoliday, HolidayType } from "@/types";

interface YearViewProps {
  year: number;
  selectedDate: Date | null;
  holidaysByDate: Map<string, SchoolHoliday[]>;
  terms: Term[];
  onDateClick: (date: Date) => void;
  onDateDoubleClick?: (date: Date) => void;
  onMonthClick: (month: number) => void;
  getTermForDate: (date: Date) => Term | undefined;
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const WEEKDAYS_SHORT = ["M", "T", "W", "T", "F", "S", "S"];

// Holiday type to color mapping
const HOLIDAY_DOT_COLORS: Record<HolidayType, string> = {
  holiday: "bg-red-500",
  vacation: "bg-blue-500",
  exam: "bg-yellow-500",
  event: "bg-green-500",
};

// Term index to background color mapping
const TERM_BACKGROUNDS = [
  "bg-blue-500/20",
  "bg-green-500/20",
  "bg-purple-500/20",
  "bg-orange-500/20",
];

export function YearView({
  year,
  selectedDate,
  holidaysByDate,
  terms,
  onDateClick,
  onDateDoubleClick,
  onMonthClick,
  getTermForDate,
}: YearViewProps) {
  // Generate calendar data for all 12 months
  const monthsData = useMemo(() => {
    return MONTHS.map((_, monthIndex) => {
      const firstDay = new Date(year, monthIndex, 1);
      const lastDay = new Date(year, monthIndex + 1, 0);

      // Get the day of week for the first day (0 = Sunday, we want Monday = 0)
      let startDayOfWeek = firstDay.getDay() - 1;
      if (startDayOfWeek < 0) startDayOfWeek = 6;

      // Generate days array with padding
      const days: (Date | null)[] = [];

      // Add padding for days before the first
      for (let i = 0; i < startDayOfWeek; i++) {
        days.push(null);
      }

      // Add actual days
      for (let i = 1; i <= lastDay.getDate(); i++) {
        days.push(new Date(year, monthIndex, i));
      }

      return {
        month: monthIndex,
        name: MONTHS[monthIndex],
        days,
      };
    });
  }, [year]);

  // Get term index for a date
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

  // Get holiday type for a date (returns first one if multiple)
  const getHolidayType = (date: Date): HolidayType | null => {
    const dateKey = date.toISOString().split("T")[0];
    const holidays = holidaysByDate.get(dateKey);
    return holidays && holidays.length > 0 ? holidays[0].holiday_type : null;
  };

  return (
    <div className="bg-card rounded-lg border p-4">
      <div className="grid grid-cols-4 gap-4">
        {monthsData.map((monthData) => (
          <div key={monthData.month} className="space-y-2">
            {/* Month header */}
            <button
              onClick={() => onMonthClick(monthData.month)}
              className="font-medium text-sm hover:text-primary transition-colors w-full text-left"
            >
              {monthData.name}
            </button>

            {/* Weekday headers */}
            <div className="grid grid-cols-7 gap-px">
              {WEEKDAYS_SHORT.map((day, idx) => (
                <div
                  key={idx}
                  className="text-[10px] text-muted-foreground text-center"
                >
                  {day}
                </div>
              ))}
            </div>

            {/* Days grid */}
            <div className="grid grid-cols-7 gap-px">
              {monthData.days.map((day, idx) => {
                if (!day) {
                  return <div key={idx} className="aspect-square" />;
                }

                const termIndex = getTermIndex(day);
                const holidayType = getHolidayType(day);
                const today = isToday(day);
                const selected = isSelected(day);

                return (
                  <button
                    key={idx}
                    onClick={() => onDateClick(day)}
                    onDoubleClick={() => onDateDoubleClick?.(day)}
                    className={cn(
                      "aspect-square flex items-center justify-center text-[10px] rounded-sm relative",
                      "hover:bg-accent transition-colors",
                      termIndex >= 0 && TERM_BACKGROUNDS[termIndex % TERM_BACKGROUNDS.length],
                      today && "ring-1 ring-primary font-bold",
                      selected && "bg-primary text-primary-foreground"
                    )}
                  >
                    {day.getDate()}
                    {holidayType && !selected && (
                      <div
                        className={cn(
                          "absolute bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full",
                          HOLIDAY_DOT_COLORS[holidayType]
                        )}
                      />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 mt-4 pt-4 border-t">
        {terms.map((term, index) => (
          <div key={term.id} className="flex items-center gap-1.5 text-xs">
            <div
              className={cn(
                "w-3 h-3 rounded-sm",
                TERM_BACKGROUNDS[index % TERM_BACKGROUNDS.length]
              )}
            />
            <span className="text-muted-foreground">
              {term.short_name || term.name}
            </span>
          </div>
        ))}
        <div className="flex items-center gap-1.5 text-xs ml-auto">
          <div className="w-1.5 h-1.5 rounded-full bg-red-500" />
          <span className="text-muted-foreground">Holiday</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
          <span className="text-muted-foreground">Vacation</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <div className="w-1.5 h-1.5 rounded-full bg-yellow-500" />
          <span className="text-muted-foreground">Exam</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
          <span className="text-muted-foreground">Event</span>
        </div>
      </div>
    </div>
  );
}
