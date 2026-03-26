"use client";

import { LeaveCalendarView } from "@/components/hr/leave-calendar";

export default function LeaveCalendarPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Leave Calendar</h1>
        <p className="text-muted-foreground">
          View approved and pending leave across all staff
        </p>
      </div>
      <LeaveCalendarView />
    </div>
  );
}
