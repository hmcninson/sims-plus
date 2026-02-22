"use client";

import { CalendarDays, Clock, Info, Plus, Edit } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { Term, SchoolHoliday, HolidayType } from "@/types";

interface EventSidebarProps {
  selectedDate: Date | null;
  events: SchoolHoliday[];
  term?: Term;
  onEventClick?: (event: SchoolHoliday) => void;
  onAddEvent?: () => void;
}

// Holiday type to badge variant mapping
const HOLIDAY_BADGE_VARIANTS: Record<HolidayType, "destructive" | "default" | "secondary" | "outline"> = {
  holiday: "destructive",
  vacation: "default",
  exam: "secondary",
  event: "outline",
};

const HOLIDAY_TYPE_LABELS: Record<HolidayType, string> = {
  holiday: "Public Holiday",
  vacation: "Vacation",
  exam: "Exam Period",
  event: "School Event",
};

function formatDate(date: Date): string {
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function formatShortDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export function EventSidebar({
  selectedDate,
  events,
  term,
  onEventClick,
  onAddEvent,
}: EventSidebarProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <CalendarDays className="h-4 w-4" />
            {selectedDate ? formatDate(selectedDate) : "Select a Date"}
          </CardTitle>
          {selectedDate && onAddEvent && (
            <Button variant="ghost" size="icon" onClick={onAddEvent} title="Add event">
              <Plus className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Term Info */}
        {term && (
          <div className="rounded-lg bg-muted/50 p-3 space-y-1">
            <div className="text-sm font-medium">{term.name}</div>
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatShortDate(term.start_date)} - {formatShortDate(term.end_date)}
            </div>
            <Badge variant={term.is_current ? "default" : "secondary"} className="text-xs">
              {term.is_current ? "Current Term" : term.status}
            </Badge>
          </div>
        )}

        {/* No date selected */}
        {!selectedDate && (
          <div className="text-center py-8 text-muted-foreground">
            <CalendarDays className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">Click on a date to see events</p>
          </div>
        )}

        {/* Events for selected date */}
        {selectedDate && events.length === 0 && (
          <div className="text-center py-6 text-muted-foreground">
            <Info className="h-6 w-6 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No events on this date</p>
            {onAddEvent && (
              <Button
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={onAddEvent}
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Event
              </Button>
            )}
          </div>
        )}

        {selectedDate && events.length > 0 && (
          <div className="space-y-3">
            <div className="text-sm font-medium text-muted-foreground">
              Events ({events.length})
            </div>
            <Separator />
            {events.map((event) => (
              <button
                key={event.id}
                onClick={() => onEventClick?.(event)}
                className="w-full text-left rounded-lg border p-3 space-y-2 hover:bg-muted/50 transition-colors group"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="font-medium text-sm">{event.name}</div>
                  <div className="flex items-center gap-1">
                    <Badge
                      variant={HOLIDAY_BADGE_VARIANTS[event.holiday_type]}
                      className="text-xs shrink-0"
                    >
                      {HOLIDAY_TYPE_LABELS[event.holiday_type]}
                    </Badge>
                    {onEventClick && (
                      <Edit className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                    )}
                  </div>
                </div>
                {event.description && (
                  <p className="text-xs text-muted-foreground">
                    {event.description}
                  </p>
                )}
                {event.is_recurring && (
                  <Badge variant="outline" className="text-xs">
                    Recurring annually
                  </Badge>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Quick info about the selected date */}
        {selectedDate && (
          <>
            <Separator />
            <div className="text-xs text-muted-foreground space-y-1">
              <div className="flex justify-between">
                <span>Day of year:</span>
                <span>
                  {Math.ceil(
                    (selectedDate.getTime() - new Date(selectedDate.getFullYear(), 0, 1).getTime()) /
                      (1000 * 60 * 60 * 24)
                  ) + 1}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Week number:</span>
                <span>
                  {Math.ceil(
                    ((selectedDate.getTime() - new Date(selectedDate.getFullYear(), 0, 1).getTime()) /
                      (1000 * 60 * 60 * 24) +
                      new Date(selectedDate.getFullYear(), 0, 1).getDay()) /
                      7
                  )}
                </span>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
