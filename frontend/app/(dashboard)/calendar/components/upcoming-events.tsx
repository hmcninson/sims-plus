"use client";

import { useMemo } from "react";
import { CalendarClock, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { SchoolHoliday, HolidayType } from "@/types";

interface UpcomingEventsProps {
  holidays: SchoolHoliday[];
  onEventClick?: (event: SchoolHoliday) => void;
  daysAhead?: number;
}

const HOLIDAY_BADGE_COLORS: Record<HolidayType, string> = {
  holiday: "bg-red-100 text-red-800 border-red-200",
  vacation: "bg-blue-100 text-blue-800 border-blue-200",
  exam: "bg-yellow-100 text-yellow-800 border-yellow-200",
  event: "bg-green-100 text-green-800 border-green-200",
};

function formatEventDate(dateString: string): string {
  const date = new Date(dateString);
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const eventDate = new Date(date);
  eventDate.setHours(0, 0, 0, 0);

  const diffTime = eventDate.getTime() - today.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  if (diffDays < 7) return `In ${diffDays} days`;

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function formatFullDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function UpcomingEvents({
  holidays,
  onEventClick,
  daysAhead = 30,
}: UpcomingEventsProps) {
  // Filter and sort upcoming events
  const upcomingEvents = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const futureDate = new Date(today);
    futureDate.setDate(futureDate.getDate() + daysAhead);

    return holidays
      .filter((h) => {
        const eventDate = new Date(h.date);
        eventDate.setHours(0, 0, 0, 0);
        return eventDate >= today && eventDate <= futureDate;
      })
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .slice(0, 5); // Show max 5 upcoming events
  }, [holidays, daysAhead]);

  if (upcomingEvents.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarClock className="h-4 w-4" />
          Upcoming Events
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {upcomingEvents.map((event) => (
          <button
            key={event.id}
            onClick={() => onEventClick?.(event)}
            className={cn(
              "w-full flex items-center gap-3 p-2 rounded-lg border",
              "hover:bg-muted/50 transition-colors text-left group"
            )}
          >
            {/* Date badge */}
            <div className="flex-shrink-0 text-center min-w-[50px]">
              <div className="text-xs text-muted-foreground">
                {formatEventDate(event.date)}
              </div>
            </div>

            {/* Event info */}
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{event.name}</div>
              <div className="text-xs text-muted-foreground">
                {formatFullDate(event.date)}
              </div>
            </div>

            {/* Type badge */}
            <Badge
              variant="outline"
              className={cn("text-[10px] shrink-0", HOLIDAY_BADGE_COLORS[event.holiday_type])}
            >
              {event.holiday_type}
            </Badge>

            <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
          </button>
        ))}
      </CardContent>
    </Card>
  );
}
