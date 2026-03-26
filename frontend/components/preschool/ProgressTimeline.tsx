"use client";

import { useState } from "react";
import {
  Star,
  Eye,
  AlertTriangle,
  BookOpen,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatGhanaDate } from "@/lib/format";
import type { TimelineEntry } from "@/types";

interface ProgressTimelineProps {
  entries: TimelineEntry[];
  isLoading?: boolean;
}

const TYPE_CONFIG: Record<
  TimelineEntry["type"],
  { icon: typeof Star; color: string; bgColor: string; dotColor: string; label: string }
> = {
  assessment: {
    icon: Star,
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
    dotColor: "bg-blue-500",
    label: "Assessment",
  },
  observation: {
    icon: Eye,
    color: "text-green-600 dark:text-green-400",
    bgColor: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
    dotColor: "bg-green-500",
    label: "Observation",
  },
  incident: {
    icon: AlertTriangle,
    color: "text-red-600 dark:text-red-400",
    bgColor: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
    dotColor: "bg-red-500",
    label: "Incident",
  },
  learning_story: {
    icon: BookOpen,
    color: "text-purple-600 dark:text-purple-400",
    bgColor: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
    dotColor: "bg-purple-500",
    label: "Learning Story",
  },
};

function groupByMonth(entries: TimelineEntry[]): Record<string, TimelineEntry[]> {
  const groups: Record<string, TimelineEntry[]> = {};
  for (const entry of entries) {
    const date = new Date(entry.date);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    if (!groups[key]) groups[key] = [];
    groups[key].push(entry);
  }
  return groups;
}

function formatMonthHeader(key: string): string {
  const [year, month] = key.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}

function TimelineEntryCard({ entry }: { entry: TimelineEntry }) {
  const [expanded, setExpanded] = useState(false);
  const config = TYPE_CONFIG[entry.type];
  const Icon = config.icon;

  return (
    <div className="relative flex gap-4 pb-6 last:pb-0">
      {/* Timeline Line + Dot */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "h-3 w-3 rounded-full border-2 border-background ring-2 ring-offset-0 shrink-0 z-10",
            config.dotColor
          )}
        />
        <div className="w-0.5 flex-1 bg-border" />
      </div>

      {/* Content Card */}
      <Card className="flex-1 -mt-1">
        <CardHeader className="pb-2 pt-3 px-4">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="secondary" className={cn("text-xs", config.bgColor)}>
                <Icon className="mr-1 h-3 w-3" />
                {config.label}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {formatGhanaDate(entry.date)}
              </span>
            </div>
          </div>
          <h4 className="text-sm font-medium leading-tight mt-1">{entry.title}</h4>
        </CardHeader>

        {entry.summary && (
          <CardContent className="px-4 pb-3 pt-0">
            <p className={cn("text-sm text-muted-foreground", !expanded && "line-clamp-2")}>
              {entry.summary}
            </p>
            {entry.summary.length > 120 && (
              <Button
                variant="ghost"
                size="sm"
                className="h-auto p-0 mt-1 text-xs"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? (
                  <>
                    Show less <ChevronUp className="ml-1 h-3 w-3" />
                  </>
                ) : (
                  <>
                    Show more <ChevronDown className="ml-1 h-3 w-3" />
                  </>
                )}
              </Button>
            )}
          </CardContent>
        )}
      </Card>
    </div>
  );
}

function TimelineSkeleton() {
  return (
    <div className="space-y-6">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <div className="flex flex-col items-center">
            <Skeleton className="h-3 w-3 rounded-full" />
            <Skeleton className="w-0.5 flex-1 mt-1" />
          </div>
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-16 w-full rounded-lg" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ProgressTimeline({ entries, isLoading = false }: ProgressTimelineProps) {
  if (isLoading) {
    return <TimelineSkeleton />;
  }

  if (entries.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <BookOpen className="h-10 w-10 text-muted-foreground mb-3" />
          <h3 className="text-sm font-medium">No timeline entries yet</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Assessments, observations, incidents, and learning stories will appear here.
          </p>
        </CardContent>
      </Card>
    );
  }

  const grouped = groupByMonth(entries);
  const sortedKeys = Object.keys(grouped).sort((a, b) => b.localeCompare(a));

  return (
    <div className="space-y-6">
      {sortedKeys.map((monthKey) => (
        <div key={monthKey}>
          <h3 className="text-sm font-semibold text-muted-foreground mb-4 uppercase tracking-wide">
            {formatMonthHeader(monthKey)}
          </h3>
          <div className="space-y-0">
            {grouped[monthKey]
              .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
              .map((entry) => (
                <TimelineEntryCard key={entry.id} entry={entry} />
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}
