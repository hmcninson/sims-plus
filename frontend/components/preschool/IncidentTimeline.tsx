"use client";

import { format } from "date-fns";
import { Check, Clock } from "lucide-react";

import { cn } from "@/lib/utils";
import type { PreschoolIncident, PreschoolIncidentStatus } from "@/types";

interface IncidentTimelineProps {
  incident: PreschoolIncident;
}

const STEPS: { status: PreschoolIncidentStatus; label: string }[] = [
  { status: "reported", label: "Reported" },
  { status: "reviewed", label: "Reviewed" },
  { status: "parent_notified", label: "Parent Notified" },
  { status: "resolved", label: "Resolved" },
];

const STATUS_ORDER: Record<PreschoolIncidentStatus, number> = {
  reported: 0,
  reviewed: 1,
  parent_notified: 2,
  resolved: 3,
};

function getStepTimestamp(
  incident: PreschoolIncident,
  status: PreschoolIncidentStatus
): string | null {
  switch (status) {
    case "reported":
      return incident.created_at;
    case "parent_notified":
      return incident.parent_notified_at ?? null;
    case "resolved":
      return incident.resolved_at ?? null;
    default:
      return null;
  }
}

function getStepActor(
  incident: PreschoolIncident,
  status: PreschoolIncidentStatus
): string | null {
  switch (status) {
    case "reported":
      return incident.reported_by ?? null;
    case "parent_notified":
      return incident.parent_notified_by ?? null;
    case "resolved":
      return incident.resolved_by ?? null;
    default:
      return null;
  }
}

export function IncidentTimeline({ incident }: IncidentTimelineProps) {
  const currentIndex = STATUS_ORDER[incident.status];

  return (
    <div className="py-4">
      {/* Desktop: horizontal */}
      <div className="hidden md:flex items-start justify-between">
        {STEPS.map((step, index) => {
          const isPast = index < currentIndex;
          const isCurrent = index === currentIndex;
          const isFuture = index > currentIndex;
          const timestamp = getStepTimestamp(incident, step.status);
          const actor = getStepActor(incident, step.status);

          return (
            <div key={step.status} className="flex-1 flex flex-col items-center relative">
              {/* Connector line */}
              {index > 0 && (
                <div
                  className={cn(
                    "absolute top-4 right-1/2 w-full h-0.5",
                    isPast || isCurrent
                      ? "bg-primary"
                      : "bg-muted"
                  )}
                  style={{ transform: "translateX(-50%)" }}
                />
              )}

              {/* Circle */}
              <div
                className={cn(
                  "relative z-10 flex h-8 w-8 items-center justify-center rounded-full border-2",
                  isPast && "border-primary bg-primary text-primary-foreground",
                  isCurrent &&
                    "border-primary bg-primary/10 text-primary ring-4 ring-primary/20",
                  isFuture && "border-muted bg-background text-muted-foreground"
                )}
              >
                {isPast ? (
                  <Check className="h-4 w-4" />
                ) : isCurrent ? (
                  <Clock className="h-4 w-4" />
                ) : (
                  <span className="text-xs">{index + 1}</span>
                )}
              </div>

              {/* Label */}
              <span
                className={cn(
                  "mt-2 text-xs font-medium text-center",
                  isCurrent ? "text-primary" : "text-muted-foreground"
                )}
              >
                {step.label}
              </span>

              {/* Timestamp */}
              {(isPast || isCurrent) && timestamp && (
                <span className="text-[10px] text-muted-foreground mt-0.5">
                  {format(new Date(timestamp), "dd/MM/yyyy HH:mm")}
                </span>
              )}

              {/* Actor */}
              {(isPast || isCurrent) && actor && (
                <span className="text-[10px] text-muted-foreground">
                  {actor}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Mobile: vertical */}
      <div className="md:hidden space-y-0">
        {STEPS.map((step, index) => {
          const isPast = index < currentIndex;
          const isCurrent = index === currentIndex;
          const isFuture = index > currentIndex;
          const timestamp = getStepTimestamp(incident, step.status);
          const actor = getStepActor(incident, step.status);

          return (
            <div key={step.status} className="flex gap-3">
              {/* Vertical line + circle */}
              <div className="flex flex-col items-center">
                <div
                  className={cn(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2",
                    isPast && "border-primary bg-primary text-primary-foreground",
                    isCurrent &&
                      "border-primary bg-primary/10 text-primary ring-2 ring-primary/20",
                    isFuture && "border-muted bg-background text-muted-foreground"
                  )}
                >
                  {isPast ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : isCurrent ? (
                    <Clock className="h-3.5 w-3.5" />
                  ) : (
                    <span className="text-[10px]">{index + 1}</span>
                  )}
                </div>
                {index < STEPS.length - 1 && (
                  <div
                    className={cn(
                      "w-0.5 flex-1 min-h-[20px]",
                      index < currentIndex ? "bg-primary" : "bg-muted"
                    )}
                  />
                )}
              </div>

              {/* Content */}
              <div className="pb-4">
                <span
                  className={cn(
                    "text-sm font-medium",
                    isCurrent ? "text-primary" : "text-muted-foreground"
                  )}
                >
                  {step.label}
                </span>
                {(isPast || isCurrent) && timestamp && (
                  <p className="text-xs text-muted-foreground">
                    {format(new Date(timestamp), "dd/MM/yyyy HH:mm")}
                    {actor && ` by ${actor}`}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
